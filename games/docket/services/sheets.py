"""The Docket — All Sheets: everyone's picks, revealed case by case.

Brad's ruling 2026-09-04, after a member asked to see the master sheet on
Thursday: *once a pick locks it releases visibility for everyone.* Before
this page the room had no everyone's-picks surface at all.

The reveal predicate is the sheet's own lock, reused rather than restated:
``deadline_passed or picks.game_locked(game, now)``. A Thursday side is on
record Thursday while the rest of the sheet stays sealed; at the Sunday
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
    is_substituted: bool         # a reserve that came into use (No Contest)
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
class StripMark:
    """One square of the mark strip under a member's record (7.13): the
    kickoff-ordered revealed lines, then the sealed count, then the open
    slots, the reserve last. A kind, never a side."""
    kind: str                    # 'win' | 'loss' | 'push' | 'no_contest' | 'pending' | 'sealed' | 'open'
    is_reserve: bool


@dataclass(frozen=True, slots=True)
class SlotMark:
    """One of the viewer's OWN nine slots, as the lounge board paints it.

    Nothing here is sealed from its owner, so every held slot carries its
    result the moment the case is final; ``in_play`` is a kicked-off case
    still waiting on a score (the live dot)."""
    slot: int
    held: bool
    is_reserve: bool
    is_best: bool
    in_play: bool
    result: str | None           # 'win' | 'loss' | 'push' | 'no_contest' | None


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
    # Drawer-only, owner's own eyes: their scoring sides shown early (before
    # the case locks) and their own number, so a member can always read their
    # own sheet. Empty/None for everyone else and once nothing is sealed. These
    # never touch the collapsed row or the mark strip (see _member_sheet).
    own_lines: tuple[SheetLine, ...] = ()
    own_number: str | None = None

    def marks(self) -> tuple[StripMark, ...]:
        """The mark strip: eight scoring squares in the order the lines
        print (revealed first, then sealed, then open), plus the reserve
        square when one is held. Reveals only what the lines already do."""
        squares = [StripMark(line.result or 'pending', False)
                   for line in self.lines if not line.is_reserve]
        squares += [StripMark('sealed', False)] * self.sealed_count
        squares += [StripMark('open', False)] * max(0, SCORING_SLOTS - len(squares))
        reserve = next((line for line in self.lines if line.is_reserve), None)
        if reserve is not None:
            squares.append(StripMark(reserve.result or 'pending', True))
        elif self.sealed_reserve:
            squares.append(StripMark('sealed', True))
        return tuple(squares)


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


def record_label(tally: Tally) -> str:
    """The record as one string ("3-1", "3-1-1 · 4 to play"): the room's
    summary and the lounge card read the same words from the same tally."""
    text = f'{tally.wins}-{tally.losses}'
    if tally.pushes:
        text += f'-{tally.pushes}'
    if tally.pending:
        text += f' · {tally.pending} to play'
    return text


def _tally(results, *, pending_extra=0) -> Tally | None:
    """A count of the marks (never a grade): None until a scoring side is
    final; ``pending`` is every scoring side without a final result."""
    finals = [r for r in results if r in FINAL_RESULTS]
    if not finals:
        return None
    return Tally(
        wins=finals.count('win'),
        losses=finals.count('loss'),
        pushes=finals.count('push'),
        pending=sum(1 for r in results if r is None) + pending_extra,
    )


def _summary(*, held, revealed, tally) -> str:
    if tally is not None:
        return record_label(tally)
    if revealed:
        return f'{revealed} of {SCORING_SLOTS} locked'
    return f'{held} of {SCORING_SLOTS} held'


def _reserve_in_use(picks, games_by_id) -> bool:
    """Whether the reserve came into use this week (Brad, 2026-09-12): the
    reserve is noise ~99% of weeks, so it is hidden until it substitutes.

    This mirrors the grading engine's substitution condition exactly
    (``grading/engine.py::_resolve_slots``): a reserve exists, its own game is
    NOT thrown out (the backup is alive), and at least one scoring slot's game
    IS thrown out. It can only be true after a No Contest ruling, which is what
    "came into use" means. A pure read-time derivation from picks already in
    hand, matching the engine so the sheet never disagrees with the ledger."""
    reserve = next((p for p in picks if p.slot == BACKUP_SLOT), None)
    if reserve is None or games_by_id[reserve.game_id].no_contest:
        return False
    return any(games_by_id[p.game_id].no_contest
               for p in picks if p.slot != BACKUP_SLOT)


def _member_sheet(enrollment, picks, prediction_tenths, *, games_by_id,
                  snapshots, revealed_ids, number_revealed,
                  is_owner=False) -> MemberSheet:
    keyed = []                   # (sort key, line): kickoff order, reserve last
    owner_keyed = []             # the owner's own scoring sides, sealed or not
    held = sealed = 0
    x2_sealed = sealed_reserve = False
    reserve_in_use = _reserve_in_use(picks, games_by_id)
    for pick in picks:
        is_reserve = pick.slot == BACKUP_SLOT
        # Hide the reserve until it actually substitutes; it is noise otherwise
        # (true for the owner too, by decision — the reserve waits for use).
        if is_reserve and not reserve_in_use:
            continue
        game = games_by_id[pick.game_id]
        if not is_reserve:
            held += 1
        revealed = pick.game_id in revealed_ids
        snap = snapshots.get(game.id)
        line = SheetLine(
            slot=pick.slot,
            is_reserve=is_reserve,
            is_substituted=is_reserve,   # a revealed reserve is one in use
            is_best=pick.is_best,
            is_auto_best=pick.is_auto_best,
            is_autopick=pick.is_autopick,
            sport=SPORT_LABELS.get(game.sport, game.sport),
            caption=_caption(game),
            kickoff=game.kickoff,
            pick=describe_pick(pick),
            # An owner's early-view side is held, not yet graded: no verdict.
            result=_result(pick, game, snap) if revealed else None,
            final_score=(f'{snap.away_score}-{snap.home_score}'
                         if revealed and snap is not None else None),
        )
        key = (is_reserve, game.kickoff, game.api_event_id, pick.slot)
        if revealed:
            keyed.append((key, line))
        else:
            if is_reserve:
                sealed_reserve = True
            else:
                sealed += 1
            if pick.is_best:
                x2_sealed = True
        # The owner always sees their own sheet in their own drawer, whether
        # each case has locked or not: every scoring side, plus a reserve that
        # has come into use (dormant reserves already `continue`d above). This
        # never feeds the collapsed row (summary, mark strip, tally stay on the
        # true lock state).
        if is_owner:
            owner_keyed.append((key, line))
    lines = [line for _, line in sorted(keyed, key=lambda item: item[0])]
    scoring = [line for line in lines if not line.is_reserve]
    tally = _tally([line.result for line in scoring], pending_extra=sealed)
    number_in = prediction_tenths is not None
    # Owner-preview surfaces (drawer only), populated only while something of
    # theirs is still sealed from the room — a scoring side, or a substituted
    # reserve whose own case has not yet locked; otherwise `lines`/`number`
    # already carry the whole sheet.
    own_preview = is_owner and (sealed > 0 or sealed_reserve)
    own_lines = (tuple(line for _, line in
                       sorted(owner_keyed, key=lambda item: item[0]))
                 if own_preview else ())
    own_number = (format_tenths(prediction_tenths)
                  if is_owner and number_in and not number_revealed else None)
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
        own_lines=own_lines,
        own_number=own_number,
    )


def all_sheets(week: DocketWeek, now: datetime,
               viewer_id: int | None = None) -> WeekSheets:
    """Every member's sheet for the week as of ``now`` (naive UTC).

    ``viewer_id`` is the logged-in member: their own row reveals its scoring
    sides (and number) in the drawer whether or not each case has locked, so a
    member can always read their own sheet. Everyone else's sides stay sealed
    until kickoff; the collapsed row is identical either way."""
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
            revealed_ids=revealed_ids, number_revealed=number_revealed,
            is_owner=enrollment.user_id == viewer_id)
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


def viewer_marks(user_id: int, week: DocketWeek, now: datetime) -> tuple[SlotMark, ...]:
    """The viewer's own nine slots for the lounge board, one query: their
    picks joined to their games (at most nine rows; the rest of the week's
    docket stays in the room). Results are the engine's rule through the
    same final gate All Sheets uses, so the card and the sheet agree on
    every case."""
    rows = db.session.execute(
        select(DocketPick, DocketGame)
        .join(DocketGame, DocketGame.id == DocketPick.game_id)
        .filter(DocketPick.user_id == user_id, DocketPick.week_id == week.id)
    ).all()
    by_slot = {pick.slot: (pick, game) for pick, game in rows}
    marks = []
    for slot in (*range(1, SCORING_SLOTS + 1), BACKUP_SLOT):
        is_reserve = slot == BACKUP_SLOT
        entry = by_slot.get(slot)
        if entry is None:
            marks.append(SlotMark(slot=slot, held=False, is_reserve=is_reserve,
                                  is_best=False, in_play=False, result=None))
            continue
        pick, game = entry
        result = _result(pick, game, _snapshot(game))
        marks.append(SlotMark(
            slot=slot, held=True, is_reserve=is_reserve, is_best=pick.is_best,
            in_play=result is None and game_locked(game, now), result=result))
    return tuple(marks)


def marks_tally(marks: tuple[SlotMark, ...]) -> Tally | None:
    """The record behind a board of slot marks: the scoring slots only
    (the reserve never counts), None until one of them is final."""
    return _tally([m.result for m in marks if m.held and not m.is_reserve])


@dataclass(frozen=True, slots=True)
class CaseVerdict:
    """One decided case on the viewer's own sheet: the engine's result and
    the final score for the case row and its rail slot. The owner sees their
    own sides, so this lands the moment the case is final."""
    result: str                  # 'win' | 'loss' | 'push' | 'no_contest'
    final_score: str | None      # 'away-home'; None on a No Contest


def viewer_sheet(
    user_id: int, week: DocketWeek, now: datetime,
) -> tuple[MemberSheet | None, dict[tuple[int, str], CaseVerdict]]:
    """The viewer's OWN sheet, decided (My Sheet, DESIGN.md 7.3 final state).

    Returns the viewer's ``MemberSheet`` (so the room's running record reads
    the same figure and mark strip All Sheets and the ledger do, from
    ``_record.html``) and a per-``(game_id, market)`` verdict map for the case
    rows and the rail slots. The owner always sees their own sides and a final
    case is always locked, so the record's reveal set (locked-or-deadline)
    already carries every verdict; the map keys the scoring slots only (the
    reserve scores only on a substitution, so its case shows its score but
    never a win or loss). Every result is the grading engine's rule through
    the same final gate All Sheets uses (``_result``/``_snapshot``), so the
    sheet can never disagree with All Sheets, the ledger, or the lounge.
    """
    enrollment = db.session.scalar(
        select(DocketEnrollment).filter_by(
            user_id=user_id, season_year=SEASON_YEAR))
    if enrollment is None:
        return None, {}
    rows = db.session.execute(
        select(DocketPick, DocketGame)
        .join(DocketGame, DocketGame.id == DocketPick.game_id)
        .filter(DocketPick.user_id == user_id, DocketPick.week_id == week.id)
    ).all()
    picks = [pick for pick, _ in rows]
    games_by_id = {game.id: game for _, game in rows}
    snapshots = {gid: snap for gid, game in games_by_id.items()
                 if (snap := _snapshot(game)) is not None}
    deadline_passed = now >= week.deadline_at
    revealed_ids = {gid for gid, game in games_by_id.items()
                    if deadline_passed or game_locked(game, now)}
    prediction = db.session.scalar(
        select(DocketTiebreakerPrediction).filter_by(
            user_id=user_id, week_id=week.id))
    designated = week.tiebreaker_game
    number_lock_at = (min(week.deadline_at, designated.kickoff)
                      if designated is not None else week.deadline_at)
    record = _member_sheet(
        enrollment, picks,
        prediction.prediction_tenths if prediction is not None else None,
        games_by_id=games_by_id, snapshots=snapshots,
        revealed_ids=revealed_ids, number_revealed=now >= number_lock_at)

    verdicts: dict[tuple[int, str], CaseVerdict] = {}
    for pick in picks:
        if pick.slot == BACKUP_SLOT:
            continue
        game = games_by_id[pick.game_id]
        result = _result(pick, game, snapshots.get(pick.game_id))
        if result is None:
            continue
        verdicts[(pick.game_id, pick.market)] = CaseVerdict(
            result=result,
            final_score=(f'{game.away_score}-{game.home_score}'
                         if game.is_final and not game.no_contest else None))
    return record, verdicts
