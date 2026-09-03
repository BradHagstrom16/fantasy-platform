"""Season rollup: drop-worst, cumulative keys, competition rank.

Three ranking keys in order: points (desc, after the drop), wins (desc),
cumulative tiebreaker error (asc, integer tenths). The drop removes ONE
week's points once more than one week is graded — earliest week on an
equal-lowest tie — and never touches wins or error ("the liability
account never forgives"). Roster members absent from a week take 0 points,
0 wins, and that week's default error (late joiners buy no advantage).

The input is WeekRollup, never WeekGrade: a PlayerWeekGrade carries exactly
eight SlotGrades and the persisted rollup (D14-eng) stores no slot trace, so
the two paths meet at the smaller type. ``week_rollup`` projects an engine
grade onto it; the ORM adapter builds one from docket_week_result rows.
"""
from collections.abc import Sequence

from games.docket.services.grading.snapshots import (
    PlayerWeekRow,
    PlayerWeekTotal,
    SeasonStanding,
    WeekGrade,
    WeekRollup,
)


def week_rollup(week_grade: WeekGrade) -> WeekRollup:
    """Project an engine WeekGrade onto the season pass's input type."""
    return WeekRollup(
        week_number=week_grade.week_number,
        default_error_tenths=week_grade.default_error_tenths,
        players=tuple(
            PlayerWeekTotal(
                player_id=p.player_id,
                points=p.points,
                wins=p.wins,
                error_tenths=p.error_tenths,
            )
            for p in week_grade.players
        ),
    )


def player_week_rows(week_rollups: Sequence[WeekRollup],
                     player_id: str) -> tuple[PlayerWeekRow, ...]:
    """One player's charged week per graded week, in the given order.

    THE place the absent-member rule lives: a roster member with no grade
    that week is charged 0 points, 0 wins, and the week's default error.
    Both season_standings and the ledger's week strip read it here rather
    than each re-deriving the charge (which is how the displayed weeks and
    the ranked totals would drift apart).
    """
    rows = []
    for rollup in week_rollups:
        graded = next((p for p in rollup.players
                       if p.player_id == player_id), None)
        if graded is not None:
            rows.append(PlayerWeekRow(
                week_number=rollup.week_number,
                points=graded.points,
                wins=graded.wins,
                error_tenths=graded.error_tenths,
                submitted=True,
            ))
        else:
            rows.append(PlayerWeekRow(
                week_number=rollup.week_number,
                points=0.0,
                wins=0,
                error_tenths=rollup.default_error_tenths,
                submitted=False,
            ))
    return tuple(rows)


def season_standings(week_rollups: Sequence[WeekRollup],
                     roster: Sequence[str],
                     ) -> tuple[SeasonStanding, ...]:
    """Standings for every roster member over the graded weeks, ordered by
    (rank keys, player_id) — equal-rank players share a competition rank
    (1, 1, 3, 4; the platform convention) in deterministic display order."""
    totals = {}
    for player_id in roster:
        rows = player_week_rows(week_rollups, player_id)
        wins = sum(r.wins for r in rows)
        error = sum(r.error_tenths for r in rows)
        dropped_week = dropped_points = None
        points = sum(r.points for r in rows)
        if len(rows) > 1:
            drop = min(rows, key=lambda r: (r.points, r.week_number))
            dropped_week, dropped_points = drop.week_number, drop.points
            points -= drop.points
        totals[player_id] = (points, wins, error, dropped_week,
                             dropped_points)

    def sort_key(player_id):
        points, wins, error, _, _ = totals[player_id]
        return (-points, -wins, error)

    ordered = sorted(roster, key=lambda pid: (sort_key(pid), pid))
    standings = []
    for player_id in ordered:
        points, wins, error, dropped_week, dropped_points = totals[player_id]
        rank = 1 + sum(1 for other in roster
                       if sort_key(other) < sort_key(player_id))
        standings.append(SeasonStanding(
            player_id=player_id,
            rank=rank,
            total_points=points,
            wins=wins,
            error_tenths=error,
            dropped_week=dropped_week,
            dropped_points=dropped_points,
        ))
    return tuple(standings)


def week_winners(rollup: WeekRollup) -> tuple[str, ...]:
    """The player ids that top one graded week: the ledger's three keys
    applied to that week alone — points (desc), wins (desc), that week's
    tiebreaker error (asc) — in player_id order (the engine's tie device).
    More than one id means the week's prize splits (rulings Amendments,
    2026-09-03). A roster member with no sheet is absent from the rollup
    and therefore never in the running; an ungraded week has no winner.
    """
    if not rollup.players:
        return ()
    best = min((-p.points, -p.wins, p.error_tenths) for p in rollup.players)
    return tuple(sorted(
        p.player_id for p in rollup.players
        if (-p.points, -p.wins, p.error_tenths) == best))
