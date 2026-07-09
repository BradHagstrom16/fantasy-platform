"""World Cup Fantasy Pool — Trend helpers
==========================================
Snapshot-derived helpers shared across surfaces:
- leaderboard.html Trend column (Plan 3)
- worldcup home _live state trend payload (Plan 4)

The "show trend column" gate uses a season-scoped count of distinct
captured_date values from WorldCupRankSnapshot. Without the season filter
(joined via WorldCupEnrollment.season_year == SEASON_YEAR), a prior cup's
snapshots would falsely satisfy the gate at the start of the next one —
that bug was caught in PR #7 (Plan 3) and is locked by
tests/test_worldcup_leaderboard.py::test_trend_column_gate_scoped_to_active_season.

The "compute trend" helper resolves "latest snapshot per enrollment" by
MAX(captured_date) — SQLite-friendly subquery, no window functions.
"""
from sqlalchemy import distinct, func

from extensions import db
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment, WorldCupRankSnapshot


def show_trend_column() -> bool:
    """True iff count(distinct captured_date) >= 7 in the active season.

    Single global gate (not per-user) per Plan 3 ambiguity-A1 resolution.
    Mirrors Spec B's >= 7 gating on the home-page sparkline.
    """
    distinct_days = (
        db.session.query(func.count(distinct(WorldCupRankSnapshot.captured_date)))
        .join(
            WorldCupEnrollment,
            WorldCupEnrollment.id == WorldCupRankSnapshot.enrollment_id,
        )
        .filter(WorldCupEnrollment.season_year == SEASON_YEAR)
        .scalar() or 0
    )
    return distinct_days >= 7


def compute_trend_by_enrollment(enrollment_ids):
    """For each enrollment id, return current_score - latest_snapshot_score.

    Latest = MAX(captured_date) per enrollment. Returns None for enrollments
    with no snapshot history (template renders '—').

    One round-trip — pull the latest snapshot per enrollment via a
    (enrollment_id, MAX(captured_date)) subquery joined back for total_score.
    Returns dict[int, float | None] keyed by enrollment id.
    """
    if not enrollment_ids:
        return {}

    # Season-scoped: any aggregate over WorldCupRankSnapshot must join
    # WorldCupEnrollment and filter season_year (CLAUDE.md invariant; the
    # show_trend_column() gate scopes the same way).
    latest_dates = (
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
        .group_by(WorldCupRankSnapshot.enrollment_id)
        .subquery()
    )

    rows = (
        db.session.query(
            WorldCupRankSnapshot.enrollment_id,
            WorldCupRankSnapshot.total_score,
        )
        .join(
            latest_dates,
            (WorldCupRankSnapshot.enrollment_id == latest_dates.c.eid) &
            (WorldCupRankSnapshot.captured_date == latest_dates.c.max_date),
        )
        .all()
    )

    snapshot_score_by_eid = dict(rows)

    enrollments_by_id = {
        e.id: e for e in WorldCupEnrollment.query
        .filter(
            WorldCupEnrollment.id.in_(enrollment_ids),
            WorldCupEnrollment.season_year == SEASON_YEAR,
        )
        .all()
    }

    trend = {}
    for eid in enrollment_ids:
        snap = snapshot_score_by_eid.get(eid)
        enr = enrollments_by_id.get(eid)
        if snap is None or enr is None:
            trend[eid] = None
        else:
            trend[eid] = round(enr.total_score - snap, 2)
    return trend
