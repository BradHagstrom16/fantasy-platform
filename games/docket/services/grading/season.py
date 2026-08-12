"""Season rollup: drop-worst, cumulative keys, competition rank.

Three ranking keys in order: points (desc, after the drop), wins (desc),
cumulative tiebreaker error (asc, integer tenths). The drop removes ONE
week's points once more than one week is graded — earliest week on an
equal-lowest tie — and never touches wins or error ("the liability
account never forgives"). Roster members absent from a week take 0 points,
0 wins, and that week's default error (late joiners buy no advantage).
"""
from games.docket.services.grading.snapshots import (
    SeasonStanding,
    WeekGrade,
)


def _player_rows(week_grades, player_id):
    """(week_number, points, wins, error_tenths) per graded week, charging
    the week's default error to absent roster members."""
    rows = []
    for week_grade in week_grades:
        graded = next((p for p in week_grade.players
                       if p.player_id == player_id), None)
        if graded is not None:
            rows.append((week_grade.week_number, graded.points,
                         graded.wins, graded.error_tenths))
        else:
            rows.append((week_grade.week_number, 0.0, 0,
                         week_grade.default_error_tenths))
    return rows


def season_standings(week_grades: list[WeekGrade] | tuple[WeekGrade, ...],
                     roster: list[str] | tuple[str, ...],
                     ) -> tuple[SeasonStanding, ...]:
    """Standings for every roster member over the graded weeks, ordered by
    (rank keys, player_id) — equal-rank players share a competition rank
    (1, 1, 3, 4; the platform convention) in deterministic display order."""
    totals = {}
    for player_id in roster:
        rows = _player_rows(week_grades, player_id)
        wins = sum(r[2] for r in rows)
        error = sum(r[3] for r in rows)
        dropped_week = dropped_points = None
        points = sum(r[1] for r in rows)
        if len(rows) > 1:
            drop = min(rows, key=lambda r: (r[1], r[0]))
            dropped_week, dropped_points = drop[0], drop[1]
            points -= drop[1]
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
