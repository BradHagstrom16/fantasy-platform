"""
World Cup Fantasy Pool — Ranking helpers
==========================================
Pure read-only ranking computations shared across surfaces:
- player_detail.html hero (Plan 2)
- leaderboard.html "Your Standing" block (Plan 3)
- worldcup home _live state dossier (Plan 4, optional reuse)

Ranks are dense — tied scores share a rank. The sort order matches
games/worldcup/routes.leaderboard():
    total_score DESC, usa_goals_guess ASC.
"""
from datetime import timedelta
from typing import Optional, TypedDict

from extensions import db
from games.worldcup.constants import SEASON_YEAR, WORLDCUP_TZ
from games.worldcup.models import WorldCupEnrollment, WorldCupRankSnapshot
from games.worldcup.services.state import now_utc


class RankNeighbors(TypedDict):
    rank: int
    points: float
    lead_delta_up: Optional[float]   # points behind rank 1; None if leader
    lead_delta_down: Optional[float]  # points ahead of next-ranked; None if last


def compute_rank_neighbors(enrollment_id: int) -> RankNeighbors:
    """Return rank + points + lead deltas for one enrollment in the SEASON_YEAR pool.

    Sort matches the public leaderboard (total_score DESC, usa_goals_guess ASC).
    Ranks are dense: tied total_scores share the same rank.

    Raises ValueError if enrollment_id is not found in the SEASON_YEAR pool.
    """
    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.usa_goals_guess.asc(),
        )
        .all()
    )

    target_idx = next(
        (i for i, e in enumerate(enrollments) if e.id == enrollment_id),
        None,
    )
    if target_idx is None:
        raise ValueError(
            f'enrollment {enrollment_id} not found in season {SEASON_YEAR}'
        )

    target = enrollments[target_idx]

    # Dense rank: count distinct scores strictly greater than target's, plus 1.
    rank = 1 + len(
        {e.total_score for e in enrollments if e.total_score > target.total_score}
    )

    leader_points = enrollments[0].total_score
    lead_delta_up: Optional[float] = (
        None if rank == 1 else round(leader_points - target.total_score, 2)
    )

    # "Next-ranked" delta is to the next enrollment with a strictly lower score.
    next_lower = next(
        (e for e in enrollments[target_idx + 1:] if e.total_score < target.total_score),
        None,
    )
    lead_delta_down: Optional[float] = (
        None if next_lower is None
        else round(target.total_score - next_lower.total_score, 2)
    )

    return RankNeighbors(
        rank=rank,
        points=float(target.total_score),
        lead_delta_up=lead_delta_up,
        lead_delta_down=lead_delta_down,
    )


def compute_rank_delta(
    enrollment: WorldCupEnrollment, window_days: int = 1
) -> Optional[int]:
    """Signed change in rank over ``window_days`` for one enrollment.

    Positive = rank improved (smaller rank number is better). Negative = rank
    dropped. Zero = held. None = insufficient snapshot history (no prior
    snapshot at or before today minus ``window_days``).

    Snapshots are scoped per enrollment, which is itself season-scoped via the
    enrollment FK (CLAUDE.md: WorldCupRankSnapshot aggregates must be
    season-scoped). The "today" pole is the latest snapshot row; the "prior"
    pole is the latest snapshot on or before the cutoff date.
    """
    cutoff = now_utc().astimezone(WORLDCUP_TZ).date() - timedelta(days=window_days)

    today = (
        db.session.query(WorldCupRankSnapshot)
        .filter(WorldCupRankSnapshot.enrollment_id == enrollment.id)
        .order_by(WorldCupRankSnapshot.captured_date.desc())
        .first()
    )
    prior = (
        db.session.query(WorldCupRankSnapshot)
        .filter(
            WorldCupRankSnapshot.enrollment_id == enrollment.id,
            WorldCupRankSnapshot.captured_date <= cutoff,
        )
        .order_by(WorldCupRankSnapshot.captured_date.desc())
        .first()
    )
    if today is None or prior is None:
        return None
    return prior.rank - today.rank
