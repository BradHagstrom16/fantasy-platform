"""The Brief (DESIGN.md §8.13): the Docket's analyst layer, argued from the
record.

Every figure here derives from GRADED weeks only (``SeasonLedger.week_numbers``):
graded weeks are fully revealed and their points are final, so nothing sealed
can appear and no point is shown before a grade (§7.13). Reads the picks
and games of those weeks, the tiebreaker predictions, and the season ledger;
grades every side with the engine's own rule (``sheets._result``), never a
second one. No market data, no API call, no projection: counts and records,
each with its denominator.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from games.docket.models import (
    DocketPick,
    DocketTiebreakerPrediction,
    DocketWeek,
)
from games.docket.services.grading.snapshots import BACKUP_SLOT, Market, Side
from games.docket.services.picks import describe_pick
from games.docket.services.season_pass import SeasonLedger, season_ledger
from games.docket.services.sheets import _caption, _result, _snapshot

DECIDED = ('win', 'loss', 'push')


@dataclass(frozen=True, slots=True)
class Record:
    wins: int = 0
    losses: int = 0
    pushes: int = 0

    @property
    def decided(self) -> int:
        return self.wins + self.losses + self.pushes

    @property
    def label(self) -> str:
        """'7-3' / '7-3-1': the room's record figure."""
        base = f'{self.wins}-{self.losses}'
        return f'{base}-{self.pushes}' if self.pushes else base


@dataclass(frozen=True, slots=True)
class Habit:
    """One of the field's four sides: how often it was taken, how it did."""
    key: str                     # 'favorites' | 'underdogs' | 'overs' | 'unders'
    label: str
    count: int
    record: Record


@dataclass(frozen=True, slots=True)
class LoneWolf:
    enrollment: object
    pick: str
    caption: str


@dataclass(frozen=True, slots=True)
class WeekConsensus:
    """The side most sheets held in one graded week, and what it did."""
    week_number: int
    pick: str                    # 'Utah Utes -3.5'
    caption: str                 # 'Idaho Vandals at Utah Utes'
    holders: int
    sheets: int                  # scoring sheets filed that week
    result: str | None
    lone_wolves: tuple[LoneWolf, ...]   # sides one sheet held alone and won


@dataclass(frozen=True, slots=True)
class X2Row:
    enrollment: object
    record: Record


@dataclass(frozen=True, slots=True)
class ClosestCall:
    enrollment: object
    week_number: int
    guess_tenths: int
    actual_tenths: int

    @property
    def off_tenths(self) -> int:
        return abs(self.guess_tenths - self.actual_tenths)


@dataclass(frozen=True, slots=True)
class NumberSection:
    rows: tuple                  # (enrollment, weeks_guessed, avg_off_tenths) ascending by avg
    closest: ClosestCall | None
    over: int                    # guesses above the frozen total
    under: int
    on_the_number: int


@dataclass(frozen=True, slots=True)
class MemberRow:
    enrollment: object
    rank: int
    sides: int                   # scoring sides graded
    contrarian: int              # sides held against the field's majority
    favorites: int
    underdogs: int
    overs: int
    unders: int
    x2: Record
    weeks_guessed: int
    avg_off_tenths: int | None
    best_week: int | None
    best_points: float | None
    struck_week: int | None

    @property
    def contrarian_share(self) -> float:
        return self.contrarian / self.sides if self.sides else 0.0


@dataclass(frozen=True, slots=True)
class Brief:
    week_numbers: tuple[int, ...]
    sheets_graded: int
    habits: tuple[Habit, ...]
    weeks: tuple[WeekConsensus, ...]
    x2_field: Record
    x2_rows: tuple[X2Row, ...]
    number: NumberSection
    members: tuple[MemberRow, ...]

    @property
    def is_graded(self) -> bool:
        return bool(self.week_numbers)


def _bucket(pick: DocketPick) -> str:
    """Which of the field's four sides a scoring pick is: a spread pick is a
    favorite or an underdog by the frozen number from the picked side (a
    pick'em counts as neither), a total pick an over or an under."""
    if pick.market == Market.SPREAD.value:
        is_home = pick.side == Side.HOME.value
        line = pick.line_value if is_home else -pick.line_value
        if line < 0:
            return 'favorites'
        if line > 0:
            return 'underdogs'
        return 'pickem'
    return 'overs' if pick.side == Side.OVER.value else 'unders'


_OPPOSITE = {Side.HOME.value: Side.AWAY.value, Side.AWAY.value: Side.HOME.value,
             Side.OVER.value: Side.UNDER.value, Side.UNDER.value: Side.OVER.value}
_HABIT_LABELS = (('favorites', 'Favorites'), ('underdogs', 'Underdogs'),
                 ('overs', 'Overs'), ('unders', 'Unders'))


def _tally(results) -> Record:
    counts = Counter(r for r in results if r in DECIDED)
    return Record(wins=counts['win'], losses=counts['loss'], pushes=counts['push'])


def build_brief(ledger: SeasonLedger | None = None) -> Brief:
    """THE read the Brief route makes."""
    if ledger is None:
        ledger = season_ledger()
    weeks = db.session.scalars(
        select(DocketWeek)
        .filter(DocketWeek.week_number.in_(list(ledger.week_numbers)))
        .options(joinedload(DocketWeek.tiebreaker_game))
        .order_by(DocketWeek.week_number)
    ).all() if ledger.week_numbers else []
    rows_by_user = {row.enrollment.user_id: row for row in ledger.rows}
    empty_number = NumberSection(rows=(), closest=None, over=0, under=0, on_the_number=0)
    if not weeks or not rows_by_user:
        return Brief(week_numbers=tuple(ledger.week_numbers), sheets_graded=0,
                     habits=(), weeks=(), x2_field=Record(), x2_rows=(),
                     number=empty_number, members=())

    week_ids = [w.id for w in weeks]
    number_of = {w.id: w.week_number for w in weeks}
    picks = db.session.scalars(
        select(DocketPick)
        .filter(DocketPick.week_id.in_(week_ids),
                DocketPick.user_id.in_(list(rows_by_user)),
                DocketPick.slot != BACKUP_SLOT)
        .options(joinedload(DocketPick.game))
    ).all()
    predictions = db.session.scalars(
        select(DocketTiebreakerPrediction)
        .filter(DocketTiebreakerPrediction.week_id.in_(week_ids),
                DocketTiebreakerPrediction.user_id.in_(list(rows_by_user)))
    ).all()

    # One grade per pick, the engine's rule.
    graded = []   # (pick, result, bucket)
    for pick in picks:
        game = pick.game
        result = _result(pick, game, _snapshot(game))
        graded.append((pick, result, _bucket(pick)))

    # The field's habits.
    by_bucket = defaultdict(list)
    for _pick, result, bucket in graded:
        by_bucket[bucket].append(result)
    habits = tuple(Habit(key=key, label=label, count=len(by_bucket[key]),
                         record=_tally(by_bucket[key]))
                   for key, label in _HABIT_LABELS)

    # Holders per side per market per week: consensus, lone wolves, and the
    # majority each pick sat with or against.
    holders = Counter((p.week_id, p.game_id, p.market, p.side) for p, _r, _b in graded)
    sheets_per_week = defaultdict(set)
    for p, _r, _b in graded:
        sheets_per_week[p.week_id].add(p.user_id)
    week_consensus = []
    for week in weeks:
        wk_picks = [(p, r) for p, r, _b in graded if p.week_id == week.id]
        if not wk_picks:
            continue
        top_key = max(
            (k for k in holders if k[0] == week.id),
            key=lambda k: (holders[k], -min(p.game.kickoff.timestamp()
                                            for p, _r in wk_picks
                                            if p.game_id == k[1])))
        sample, sample_result = next((p, r) for p, r in wk_picks
                                     if (p.week_id, p.game_id, p.market, p.side) == top_key)
        wolves = tuple(
            LoneWolf(enrollment=rows_by_user[p.user_id].enrollment,
                     pick=describe_pick(p), caption=_caption(p.game))
            for p, r in sorted(wk_picks, key=lambda pr: pr[0].game.kickoff)
            if r == 'win' and holders[(p.week_id, p.game_id, p.market, p.side)] == 1)
        week_consensus.append(WeekConsensus(
            week_number=week.week_number, pick=describe_pick(sample),
            caption=_caption(sample.game), holders=holders[top_key],
            sheets=len(sheets_per_week[week.id]), result=sample_result,
            lone_wolves=wolves))

    # The x2 ledger.
    x2_by_user = defaultdict(list)
    for p, r, _b in graded:
        if p.is_best:
            x2_by_user[p.user_id].append(r)
    x2_field = _tally([r for rs in x2_by_user.values() for r in rs])
    x2_rows = tuple(sorted(
        (X2Row(enrollment=rows_by_user[uid].enrollment, record=_tally(rs))
         for uid, rs in x2_by_user.items()),
        key=lambda row: (-row.record.wins, row.record.losses,
                         row.enrollment.get_display_name().casefold())))

    # The number: every guess against the real combined score of the
    # designated game, and against the frozen total it was guessed over.
    actual_by_week = {}
    total_by_week = {}
    for week in weeks:
        game = week.tiebreaker_game
        if game is None:
            continue
        snap = _snapshot(game)
        if snap is not None:
            actual_by_week[week.id] = (snap.home_score + snap.away_score) * 10
        if game.total_points is not None:
            total_by_week[week.id] = round(game.total_points * 10)
    offs_by_user = defaultdict(list)
    closest = None
    over = under = on_the_number = 0
    for pred in predictions:
        actual = actual_by_week.get(pred.week_id)
        if actual is not None:
            offs_by_user[pred.user_id].append(abs(pred.prediction_tenths - actual))
            call = ClosestCall(enrollment=rows_by_user[pred.user_id].enrollment,
                               week_number=number_of[pred.week_id],
                               guess_tenths=pred.prediction_tenths,
                               actual_tenths=actual)
            if closest is None or call.off_tenths < closest.off_tenths:
                closest = call
        total = total_by_week.get(pred.week_id)
        if total is not None:
            if pred.prediction_tenths > total:
                over += 1
            elif pred.prediction_tenths < total:
                under += 1
            else:
                on_the_number += 1
    number_rows = tuple(sorted(
        ((rows_by_user[uid].enrollment, len(offs), round(sum(offs) / len(offs)))
         for uid, offs in offs_by_user.items()),
        key=lambda row: (row[2], row[0].get_display_name().casefold())))
    number = NumberSection(rows=number_rows, closest=closest, over=over,
                           under=under, on_the_number=on_the_number)

    # The members' rows, in ledger order.
    per_user = defaultdict(lambda: {'sides': 0, 'contrarian': 0, 'favorites': 0,
                                    'underdogs': 0, 'overs': 0, 'unders': 0})
    for p, _r, bucket in graded:
        stats = per_user[p.user_id]
        stats['sides'] += 1
        if bucket in stats:
            stats[bucket] += 1
        mine = holders[(p.week_id, p.game_id, p.market, p.side)]
        theirs = holders[(p.week_id, p.game_id, p.market, _OPPOSITE[p.side])]
        if mine < theirs:
            stats['contrarian'] += 1
    members = []
    for row in ledger.rows:
        uid = row.enrollment.user_id
        stats = per_user[uid]
        offs = offs_by_user.get(uid, [])
        submitted = [w for w in row.weeks if w.submitted]
        best = max(submitted, key=lambda w: (w.points, -w.week_number), default=None)
        members.append(MemberRow(
            enrollment=row.enrollment, rank=row.standing.rank,
            sides=stats['sides'], contrarian=stats['contrarian'],
            favorites=stats['favorites'], underdogs=stats['underdogs'],
            overs=stats['overs'], unders=stats['unders'],
            x2=_tally(x2_by_user.get(uid, [])),
            weeks_guessed=len(offs),
            avg_off_tenths=round(sum(offs) / len(offs)) if offs else None,
            best_week=best.week_number if best else None,
            best_points=best.points if best else None,
            struck_week=row.standing.dropped_week))

    return Brief(week_numbers=tuple(ledger.week_numbers),
                 sheets_graded=len({p.user_id for p, _r, _b in graded}),
                 habits=habits, weeks=tuple(week_consensus), x2_field=x2_field,
                 x2_rows=x2_rows, number=number, members=tuple(members))
