"""ORM→snapshot adapter for the season ledger (D14-eng).

The read-side sibling of grading_pass.py: that module turns a week's rows
into a WeekGrade and persists it, this one turns the persisted rollup back
into pure WeekRollups and runs the season pass over them.

D14-eng, structurally: this module reads docket_week and
docket_week_result and NOTHING else. It never touches docket_pick or
docket_game, so the ledger cannot quietly become a re-grade. The one query
that leaves those two tables is the display join onto docket_enrollment and
users, which supplies avatars and display names, never numbers.

The drop is DERIVED here, every read. DocketWeekResult.is_dropped is
deliberately left unwritten: the drop moves every time any week grades, so a
persisted copy would be a second source of truth for a fact nothing reads.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from games.docket.models import DocketEnrollment, DocketWeek, DocketWeekResult
from games.docket.services.grading.season import (
    player_week_rows,
    season_standings,
    week_winners,
)
from games.docket.services.grading.snapshots import (
    PlayerWeekRow,
    PlayerWeekTotal,
    SeasonStanding,
    WeekRollup,
)
from games.docket.services.weeks import SEASON_YEAR, TOTAL_WEEKS


@dataclass(frozen=True, slots=True)
class LedgerRow:
    """One player's line: the ranked standing plus what it took to get there.

    ``enrollment`` carries the avatar and display name (the platform
    integration point); every number comes from ``standing`` and ``weeks``,
    which the pure engine produced.
    """
    standing: SeasonStanding
    enrollment: DocketEnrollment
    weeks: tuple[PlayerWeekRow, ...]
    prize_weeks: frozenset[int] = frozenset()  # weeks this line took or split

    @property
    def dropped_week(self) -> int | None:
        return self.standing.dropped_week


@dataclass(frozen=True, slots=True)
class LedgerVerdict:
    """One graded week's top sheet (the purse's weekly prize): the three
    keys applied to that week alone; ``split`` when more than one line was
    level on all three. ``winners`` are enrollments (avatar + name), in
    display-name order."""
    week_number: int
    winners: tuple[DocketEnrollment, ...]
    points: float
    wins: int
    error_tenths: int
    split: bool


@dataclass(frozen=True, slots=True)
class SeasonLedger:
    rows: tuple[LedgerRow, ...]
    week_numbers: tuple[int, ...]   # graded weeks, ascending
    total_weeks: int                # TOTAL_WEEKS, never a literal
    season_complete: bool           # every week graded; gates the ceremony
    verdicts: tuple[LedgerVerdict, ...] = ()   # one per graded week

    @property
    def is_graded(self) -> bool:
        """Any week graded at all. False is the state the ledger ships in:
        prod docket tables stay empty until the Week-1 import."""
        return bool(self.week_numbers)

    @property
    def drop_active(self) -> bool:
        """The drop applies only once more than one week is graded."""
        return len(self.week_numbers) > 1

    @property
    def leader(self) -> LedgerRow | None:
        return self.rows[0] if self.rows else None


def week_rollups_from_db() -> tuple[WeekRollup, ...]:
    """Every GRADED week as a pure WeekRollup, ascending by week number.

    A week with no result rows is not graded and is absent entirely: it
    charges nobody a default error and does not count toward the drop.

    Docket weeks carry no season column (week_number is globally unique and
    SEASON_YEAR is a module constant in services/weeks.py), so week reads are
    not season-scoped and must not pretend to be. Only the roster is.
    """
    results = db.session.scalars(
        select(DocketWeekResult).order_by(DocketWeekResult.week_id)).all()
    if not results:
        return ()

    week_ids = {row.week_id for row in results}
    weeks = {
        week.id: week
        for week in db.session.scalars(
            select(DocketWeek).filter(DocketWeek.id.in_(week_ids)))
    }

    by_week: dict[int, list[DocketWeekResult]] = {}
    for row in results:
        by_week.setdefault(row.week_id, []).append(row)

    rollups = []
    for week_id, rows in by_week.items():
        week = weeks[week_id]
        if week.default_error_tenths is None:
            # Graded rows but no default error means the week was graded
            # before the column existed. Refuse loudly rather than dropping
            # the week from the ledger: a silently absent week changes
            # everyone's totals and therefore everyone's rank.
            raise ValueError(
                f'docket week {week.week_number} has graded results but no '
                f'default_error_tenths — run `flask docket recalc` to '
                f'restamp it')
        rollups.append(WeekRollup(
            week_number=week.week_number,
            default_error_tenths=week.default_error_tenths,
            players=tuple(
                PlayerWeekTotal(
                    player_id=str(row.user_id),
                    points=row.points,
                    wins=row.wins,
                    error_tenths=row.error_tenths,
                )
                for row in sorted(rows, key=lambda r: r.user_id)
            ),
        ))
    return tuple(sorted(rollups, key=lambda r: r.week_number))


def season_ledger(season_year: int = SEASON_YEAR) -> SeasonLedger:
    """THE single read the ledger route makes.

    Ranking comes from the pure engine; this function only joins names and
    avatars onto it and settles display order inside a shared rank.
    """
    enrollments = db.session.scalars(
        select(DocketEnrollment)
        .filter_by(season_year=season_year)
        .options(joinedload(DocketEnrollment.user))
    ).all()
    by_player_id = {str(e.user_id): e for e in enrollments}

    rollups = week_rollups_from_db()
    standings = season_standings(rollups, tuple(by_player_id))

    # The weekly verdicts: the engine names the week's top sheet(s); this
    # only joins the enrollments on. A result row for a player no longer on
    # the roster is ignored here exactly as season_standings ignores it.
    verdicts = []
    prize_weeks: dict[str, set[int]] = {}
    for rollup in rollups:
        winner_ids = [pid for pid in week_winners(rollup) if pid in by_player_id]
        if not winner_ids:
            continue
        top = next(p for p in rollup.players if p.player_id == winner_ids[0])
        verdicts.append(LedgerVerdict(
            week_number=rollup.week_number,
            winners=tuple(sorted(
                (by_player_id[pid] for pid in winner_ids),
                key=lambda e: e.get_display_name().lower())),
            points=top.points,
            wins=top.wins,
            error_tenths=top.error_tenths,
            split=len(winner_ids) > 1,
        ))
        for pid in winner_ids:
            prize_weeks.setdefault(pid, set()).add(rollup.week_number)

    rows = [
        LedgerRow(
            standing=standing,
            enrollment=by_player_id[standing.player_id],
            weeks=player_week_rows(rollups, standing.player_id),
            prize_weeks=frozenset(prize_weeks.get(standing.player_id, ())),
        )
        for standing in standings
    ]
    # The engine breaks a full three-key tie by player_id to stay
    # deterministic, which is str(user_id) and therefore sorts "10" above
    # "2". That is a determinism device, not a presentation choice: inside a
    # shared rank, order by name. The rank itself is never re-derived.
    rows.sort(key=lambda r: (r.standing.rank,
                             r.enrollment.get_display_name().lower()))

    week_numbers = tuple(r.week_number for r in rollups)
    return SeasonLedger(
        rows=tuple(rows),
        week_numbers=week_numbers,
        total_weeks=TOTAL_WEEKS,
        season_complete=len(week_numbers) == TOTAL_WEEKS,
        verdicts=tuple(verdicts),
    )
