"""The Docket — All Sheets: everyone's picks, revealed case by case.

Brad's ruling 2026-09-04, after a member asked to see the master sheet on
Thursday: *once a pick locks it releases visibility for everyone.* Before
this page the room had no everyone's-picks surface at all.

The reveal predicate is the sheet's own lock, reused rather than restated:
``deadline_passed or picks.game_locked(game, now)``. A Thursday side is on
record Thursday while the rest of the sheet stays sealed; at the Saturday
deadline everything is on record. What is sealed is stated in words and
counts ("5 sides sealed until kickoff · x2 named"), never a side.

Result marks come from the grading engine (``grade_pick_outcome``) behind
the same final gate the week grade uses (``is_final and not no_contest``),
so the page can never disagree with the ledger about a single case. No
points are shown before the week grades: the x2 double, the No Contest
fallback and the reserve substitution resolve at week grade, and a second
implementation here would disagree with the ledger in every No Contest
week. The tally is a count of the marks on the page, not a grade.

The roster is live before the deadline and as-of the deadline after it
(ADR-048), which is what a closed week grades; a post-deadline joiner has no
dealt sheet and would otherwise render as an empty row.

Five queries, whatever the roster size: the roster ids (the ADR-048 helper,
kept as the one source of the as-of rule), enrollments with their users,
the week's games, the week's picks, the week's predictions. Every pick
resolves its game from the games already in the session, never through a
lazy load; the count is locked by ``tests/test_docket_all_sheets.py``.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from games.docket.models import (
    DocketEnrollment,
    DocketGame,
    DocketPick,
    DocketTiebreakerPrediction,
    DocketWeek,
)
from games.docket.services.bridge_sheet import SPORT_LABELS
from games.docket.services.enrollment import (
    roster_user_ids,
    roster_user_ids_as_of,
)
from games.docket.services.grading.engine import grade_pick_outcome
from games.docket.services.grading.snapshots import (
    BACKUP_SLOT,
    SCORING_SLOTS,
    GameSnapshot,
    Market,
    Side,
)
from games.docket.services.picks import (
    describe_pick,
    format_tenths,
    game_locked,
)
from games.docket.services.weeks import SEASON_YEAR

FINAL_RESULTS = ('win', 'loss', 'push')


@dataclass(frozen=True, slots=True)
class SheetLine:
    """One revealed pick, as the sheet prints it."""
    slot: int
    is_reserve: bool
    is_best: bool
    is_auto_best: bool
    is_autopick: bool
    sport: str
    caption: str                 # 'Idaho Vandals at Utah Utes'
    kickoff: datetime            # naive UTC; the template renders with |ct
    pick: str                    # 'Utah Utes -3.5' / 'Over 51.5'
    result: str | None           # 'win' | 'loss' | 'push' | 'no_contest' | None
    final_score: str | None      # 'away-home' once final


@dataclass(frozen=True, slots=True)
class Tally:
    wins: int
    losses: int
    pushes: int
    pending: int                 # unfinal revealed sides + sealed sides


@dataclass(frozen=True, slots=True)
class MemberSheet:
    enrollment: DocketEnrollment
    user_id: int
    lines: tuple[SheetLine, ...]
    held_count: int              # scoring sides held, revealed or not
    sealed_count: int            # scoring sides not yet revealed
    sealed_reserve: bool
    x2_sealed: bool
    number_in: bool
    number: str | None           # revealed at the number's own lock
    tally: Tally | None          # None until a scoring line is final
    sealed_sentence: str
    summary: str


@dataclass(frozen=True, slots=True)
class WeekSheets:
    week_number: int
    deadline_passed: bool
    any_revealed: bool
    total_cases: int
    locked_cases: int
    first_kickoff: datetime | None
    next_lock: datetime | None   # the next case to open; None once all are
    number_lock_at: datetime | None
    number_revealed: bool
    designated_caption: str | None
    members: tuple[MemberSheet, ...]


def _caption(game: DocketGame) -> str:
    return f'{game.away_team} at {game.home_team}'


def _snapshot(game: DocketGame) -> GameSnapshot | None:
    """The engine's view of a final game; None while it is not final. The
    gate is the week grade's own (grading_pass.build_week_snapshot)."""
    if not (game.is_final and not game.no_contest):
        return None
    return GameSnapshot(
        api_event_id=game.api_event_id,
        sport=game.sport,
        home_team=game.home_team,
        away_team=game.away_team,
        # The ordering input, irrelevant to one pick's outcome; the frozen
        # copy is NULL until the deadline pass.
        kickoff_at_deadline=game.kickoff_at_deadline or game.kickoff,
        home_spread=game.home_spread,
        total=game.total_points,
        home_score=game.home_score,
        away_score=game.away_score,
        no_contest=game.no_contest,
    )


def _result(pick: DocketPick, game: DocketGame,
            snap: GameSnapshot | None) -> str | None:
    if game.no_contest:
        return 'no_contest'
    if snap is None:
        return None
    market = Market(pick.market)
    line = snap.home_spread if market is Market.SPREAD else snap.total
    if line is None:
        return None
    return grade_pick_outcome(snap, market, Side(pick.side)).value


def _sealed_sentence(*, held, sealed, x2_sealed, sealed_reserve,
                     number_pending) -> str:
    if held == 0:
        return 'Nothing held yet.'
    parts = []
    if sealed:
        parts.append(f'{sealed} side{"" if sealed == 1 else "s"} sealed '
                     'until kickoff')
    if x2_sealed:
        parts.append('x2 named')
    if sealed_reserve:
        parts.append('reserve held')
    if number_pending:
        parts.append('number in')
    return ' · '.join(parts) + '.' if parts else ''


def _summary(*, held, revealed, tally) -> str:
    if tally is not None:
        text = f'{tally.wins}-{tally.losses}'
        if tally.pushes:
            text += f'-{tally.pushes}'
        if tally.pending:
            text += f' · {tally.pending} to play'
        return text
    if revealed:
        return f'{revealed} of {SCORING_SLOTS} locked'
    return f'{held} of {SCORING_SLOTS} held'


def _member_sheet(enrollment, picks, prediction_tenths, *, games_by_id,
                  snapshots, revealed_ids, number_revealed) -> MemberSheet:
    keyed = []                   # (sort key, line): kickoff order, reserve last
    held = sealed = 0
    x2_sealed = sealed_reserve = False
    for pick in picks:
        game = games_by_id[pick.game_id]
        is_reserve = pick.slot == BACKUP_SLOT
        if not is_reserve:
            held += 1
        if pick.game_id not in revealed_ids:
            if is_reserve:
                sealed_reserve = True
            else:
                sealed += 1
            if pick.is_best:
                x2_sealed = True
            continue
        snap = snapshots.get(game.id)
        keyed.append((
            (is_reserve, game.kickoff, game.api_event_id, pick.slot),
            SheetLine(
                slot=pick.slot,
                is_reserve=is_reserve,
                is_best=pick.is_best,
                is_auto_best=pick.is_auto_best,
                is_autopick=pick.is_autopick,
                sport=SPORT_LABELS.get(game.sport, game.sport),
                caption=_caption(game),
                kickoff=game.kickoff,
                pick=describe_pick(pick),
                result=_result(pick, game, snap),
                final_score=(f'{snap.away_score}-{snap.home_score}'
                             if snap is not None else None),
            ),
        ))
    lines = [line for _, line in sorted(keyed, key=lambda item: item[0])]
    scoring = [line for line in lines if not line.is_reserve]
    finals = [line for line in scoring if line.result in FINAL_RESULTS]
    tally = None
    if finals:
        pending = sum(1 for line in scoring if line.result is None) + sealed
        tally = Tally(
            wins=sum(1 for line in finals if line.result == 'win'),
            losses=sum(1 for line in finals if line.result == 'loss'),
            pushes=sum(1 for line in finals if line.result == 'push'),
            pending=pending,
        )
    number_in = prediction_tenths is not None
    return MemberSheet(
        enrollment=enrollment,
        user_id=enrollment.user_id,
        lines=tuple(lines),
        held_count=held,
        sealed_count=sealed,
        sealed_reserve=sealed_reserve,
        x2_sealed=x2_sealed,
        number_in=number_in,
        number=(format_tenths(prediction_tenths)
                if number_in and number_revealed else None),
        tally=tally,
        sealed_sentence=_sealed_sentence(
            held=held, sealed=sealed, x2_sealed=x2_sealed,
            sealed_reserve=sealed_reserve,
            number_pending=number_in and not number_revealed),
        summary=_summary(held=held, revealed=len(scoring), tally=tally),
    )


def all_sheets(week: DocketWeek, now: datetime) -> WeekSheets:
    """Every member's sheet for the week as of ``now`` (naive UTC)."""
    deadline_passed = now >= week.deadline_at
    ids = (roster_user_ids() if not deadline_passed
           else roster_user_ids_as_of(week.deadline_at))
    enrollments = db.session.scalars(
        select(DocketEnrollment)
        .filter(DocketEnrollment.user_id.in_(ids),
                DocketEnrollment.season_year == SEASON_YEAR)
        .options(joinedload(DocketEnrollment.user))
    ).all()
    games = db.session.scalars(
        select(DocketGame).filter_by(week_id=week.id)).all()
    games_by_id = {g.id: g for g in games}
    revealed_ids = {g.id for g in games
                    if deadline_passed or game_locked(g, now)}
    snapshots = {g.id: snap for g in games
                 if (snap := _snapshot(g)) is not None}
    picks_by_user: dict[int, list[DocketPick]] = {}
    for pick in db.session.scalars(
            select(DocketPick).filter_by(week_id=week.id)
            .order_by(DocketPick.user_id, DocketPick.slot)):
        picks_by_user.setdefault(pick.user_id, []).append(pick)
    predictions = {
        row.user_id: row.prediction_tenths
        for row in db.session.scalars(
            select(DocketTiebreakerPrediction).filter_by(week_id=week.id))
    }

    designated = games_by_id.get(week.tiebreaker_game_id)
    number_lock_at = (min(week.deadline_at, designated.kickoff)
                      if designated is not None else week.deadline_at)
    number_revealed = now >= number_lock_at

    members = [
        _member_sheet(
            enrollment, picks_by_user.get(enrollment.user_id, []),
            predictions.get(enrollment.user_id),
            games_by_id=games_by_id, snapshots=snapshots,
            revealed_ids=revealed_ids, number_revealed=number_revealed)
        for enrollment in enrollments
    ]
    members.sort(key=lambda m: (m.enrollment.get_display_name().casefold(),
                                m.user_id))

    kickoffs = sorted(g.kickoff for g in games)
    unlocked = sorted(g.kickoff for g in games if g.id not in revealed_ids)
    return WeekSheets(
        week_number=week.week_number,
        deadline_passed=deadline_passed,
        any_revealed=bool(revealed_ids),
        total_cases=len(games),
        locked_cases=len(revealed_ids),
        first_kickoff=kickoffs[0] if kickoffs else None,
        next_lock=unlocked[0] if unlocked else None,
        number_lock_at=number_lock_at if games else None,
        number_revealed=number_revealed,
        designated_caption=_caption(designated) if designated else None,
        members=tuple(members),
    )
