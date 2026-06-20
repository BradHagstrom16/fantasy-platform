"""
World Cup Fantasy Pool — Ranking helpers
==========================================
Pure read-only ranking computations shared across surfaces:
- player_detail.html hero (Plan 2)
- leaderboard.html "Your Standing" block (Plan 3)
- worldcup home _live state dossier (Plan 4, optional reuse)

Ranks are competition rank — tied scores share a rank, the next distinct
score gaps by the size of the tie (1, 1, 3). The sort order matches
games/worldcup/routes.leaderboard():
    total_score DESC, usa_goals_guess ASC.
"""
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Optional, TypedDict

from sqlalchemy import func

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
    Ranks are competition rank: tied total_scores share a rank, the next
    distinct score gaps by the size of the tie.

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

    # Competition rank: count enrollments scoring strictly higher, plus 1.
    # Tied scores share a rank; the next distinct score gaps by the size of
    # the tie (1, 1, 3, 4 — not dense 1, 1, 2, 3). CLAUDE.md "Competition
    # rank everywhere": this must match routes.leaderboard().
    rank = 1 + sum(
        1 for e in enrollments if e.total_score > target.total_score
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


def compute_rank_deltas_bulk(
    enrollment_ids: Iterable[int], window_days: int = 1
) -> dict[int, Optional[int]]:
    """Bulk variant of compute_rank_delta — one round-trip for all enrollments.

    Returns dict[enrollment_id, signed_rank_delta | None]. Mirrors the per-call
    semantics of compute_rank_delta (positive = improved, negative = dropped,
    None = insufficient history).

    Replaces the N+1 pattern of `{e.id: compute_rank_delta(e) for e in es}` —
    each per-call invocation runs two snapshot queries; this helper runs two
    queries total regardless of N. Shape mirrors
    services.trends.compute_trend_by_enrollment: a season-scoped subquery for
    "latest captured_date per enrollment", joined back for the rank value.

    Season-scoped via WorldCupEnrollment.season_year (CLAUDE.md:
    WorldCupRankSnapshot aggregates must be season-scoped).
    """
    eids = list(enrollment_ids)
    if not eids:
        return {}

    today_local: date = now_utc().astimezone(WORLDCUP_TZ).date()
    cutoff: date = today_local - timedelta(days=window_days)

    today_rank_by_eid = _latest_rank_by_enrollment(eids, captured_on_or_before=None)
    prior_rank_by_eid = _latest_rank_by_enrollment(eids, captured_on_or_before=cutoff)

    deltas: dict[int, Optional[int]] = {}
    for eid in eids:
        t = today_rank_by_eid.get(eid)
        p = prior_rank_by_eid.get(eid)
        deltas[eid] = (p - t) if (t is not None and p is not None) else None
    return deltas


def _latest_rank_by_enrollment(
    enrollment_ids: list[int], captured_on_or_before: Optional[date]
) -> dict[int, int]:
    """Resolve the latest snapshot rank per enrollment in one round-trip.

    If captured_on_or_before is None, "latest" = max(captured_date) overall.
    Otherwise, "latest" = max(captured_date) where captured_date <= cutoff.
    Returns dict[enrollment_id, rank]; missing enrollments are absent.

    Season-scoped via the WorldCupEnrollment join (the snapshot row itself has
    no season_year column).
    """
    max_date_q = (
        db.session.query(
            WorldCupRankSnapshot.enrollment_id.label('eid'),
            func.max(WorldCupRankSnapshot.captured_date).label('max_date'),
        )
        .join(
            WorldCupEnrollment,
            WorldCupEnrollment.id == WorldCupRankSnapshot.enrollment_id,
        )
        .filter(WorldCupRankSnapshot.enrollment_id.in_(enrollment_ids))
        .filter(WorldCupEnrollment.season_year == SEASON_YEAR)
    )
    if captured_on_or_before is not None:
        max_date_q = max_date_q.filter(
            WorldCupRankSnapshot.captured_date <= captured_on_or_before
        )
    max_dates = max_date_q.group_by(WorldCupRankSnapshot.enrollment_id).subquery()

    rows = (
        db.session.query(
            WorldCupRankSnapshot.enrollment_id,
            WorldCupRankSnapshot.rank,
        )
        .join(
            max_dates,
            (WorldCupRankSnapshot.enrollment_id == max_dates.c.eid) &
            (WorldCupRankSnapshot.captured_date == max_dates.c.max_date),
        )
        .all()
    )
    return dict(rows)
