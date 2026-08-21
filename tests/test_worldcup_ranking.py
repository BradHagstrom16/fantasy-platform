"""Tests for games/worldcup/services/ranking helpers."""
from datetime import timedelta

import pytest

from extensions import db
from games.worldcup.constants import SEASON_YEAR, WORLDCUP_TZ
from games.worldcup.models import WorldCupEnrollment, WorldCupRankSnapshot
from games.worldcup.services.ranking import (
    compute_rank_delta,
    compute_rank_deltas_bulk,
    compute_rank_neighbors,
)
from games.worldcup.services.state import now_utc
from models.user import User


def _seed_enrollments(scores: list[float]) -> list[int]:
    """Seed N enrollments with the given scores in input order. Returns ids."""
    ids = []
    for i, score in enumerate(scores):
        u = User(username=f'p{i}', email=f'p{i}@test.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.flush()
        e = WorldCupEnrollment(
            user_id=u.id, season_year=SEASON_YEAR,
            picks_submitted=True, total_score=score,
            usa_goals_guess=5,
        )
        db.session.add(e)
        db.session.flush()
        ids.append(e.id)
    db.session.commit()
    return ids


def test_compute_rank_neighbors_for_leader(app):
    with app.app_context():
        # scores: [50, 40, 30] — first is leader
        ids = _seed_enrollments([50.0, 40.0, 30.0])
        result = compute_rank_neighbors(ids[0])
        assert result['rank'] == 1
        assert result['points'] == 50.0
        assert result['lead_delta_up'] is None
        assert result['lead_delta_down'] == 10.0  # ahead of rank 2 by 10


def test_compute_rank_neighbors_for_middle(app):
    with app.app_context():
        ids = _seed_enrollments([50.0, 40.0, 30.0])
        result = compute_rank_neighbors(ids[1])
        assert result['rank'] == 2
        assert result['points'] == 40.0
        assert result['lead_delta_up'] == 10.0   # 10 behind rank 1
        assert result['lead_delta_down'] == 10.0  # 10 ahead of rank 3


def test_compute_rank_neighbors_for_last(app):
    with app.app_context():
        ids = _seed_enrollments([50.0, 40.0, 30.0])
        result = compute_rank_neighbors(ids[2])
        assert result['rank'] == 3
        assert result['points'] == 30.0
        assert result['lead_delta_up'] == 20.0
        assert result['lead_delta_down'] is None


def test_compute_rank_neighbors_handles_ties(app):
    with app.app_context():
        # Competition rank: [50, 40, 40, 30] -> ranks 1, 2, 2, 4. The two
        # tied at 40 share rank 2; the next distinct score (30) gaps to 4,
        # NOT dense-rank 3. Locks the competition-rank invariant.
        ids = _seed_enrollments([50.0, 40.0, 40.0, 30.0])
        assert compute_rank_neighbors(ids[0])['rank'] == 1
        assert compute_rank_neighbors(ids[1])['rank'] == 2
        assert compute_rank_neighbors(ids[2])['rank'] == 2
        assert compute_rank_neighbors(ids[3])['rank'] == 4


def test_compute_rank_neighbors_unknown_id_raises(app):
    with app.app_context(), pytest.raises(ValueError):
        compute_rank_neighbors(99999)


# ---------------------------------------------------------------------------
# compute_rank_delta — P1 S1.1
# ---------------------------------------------------------------------------
def _seed_one_enrollment() -> int:
    """Seed a single enrollment, return its id (no snapshots yet)."""
    u = User(username='solo', email='solo@test.com')
    u.set_password('pass')
    db.session.add(u)
    db.session.flush()
    e = WorldCupEnrollment(
        user_id=u.id, season_year=SEASON_YEAR,
        picks_submitted=True, total_score=10.0, usa_goals_guess=3,
    )
    db.session.add(e)
    db.session.commit()
    return e.id


def _add_snapshot(enrollment_id: int, days_ago: int, rank: int, total_score: float) -> None:
    today = now_utc().astimezone(WORLDCUP_TZ).date()
    db.session.add(WorldCupRankSnapshot(
        enrollment_id=enrollment_id,
        captured_date=today - timedelta(days=days_ago),
        rank=rank,
        total_score=total_score,
    ))
    db.session.commit()


def test_compute_rank_delta_positive_when_rank_improves(app):
    """Yesterday rank 5, today rank 3 → delta = +2 (smaller rank number is better)."""
    with app.app_context():
        eid = _seed_one_enrollment()
        _add_snapshot(eid, days_ago=1, rank=5, total_score=10.0)
        _add_snapshot(eid, days_ago=0, rank=3, total_score=18.0)
        e = db.session.get(WorldCupEnrollment, eid)
        assert compute_rank_delta(e, window_days=1) == 2


def test_compute_rank_delta_negative_when_rank_drops(app):
    """Yesterday rank 3, today rank 5 → delta = -2."""
    with app.app_context():
        eid = _seed_one_enrollment()
        _add_snapshot(eid, days_ago=1, rank=3, total_score=18.0)
        _add_snapshot(eid, days_ago=0, rank=5, total_score=18.0)
        e = db.session.get(WorldCupEnrollment, eid)
        assert compute_rank_delta(e, window_days=1) == -2


def test_compute_rank_delta_zero_when_held(app):
    """Yesterday rank 3, today rank 3 → delta = 0."""
    with app.app_context():
        eid = _seed_one_enrollment()
        _add_snapshot(eid, days_ago=1, rank=3, total_score=10.0)
        _add_snapshot(eid, days_ago=0, rank=3, total_score=12.0)
        e = db.session.get(WorldCupEnrollment, eid)
        assert compute_rank_delta(e, window_days=1) == 0


def test_compute_rank_delta_none_when_no_snapshots(app):
    """No snapshot history → None (template renders 'Pending')."""
    with app.app_context():
        eid = _seed_one_enrollment()
        e = db.session.get(WorldCupEnrollment, eid)
        assert compute_rank_delta(e, window_days=1) is None


def test_compute_rank_delta_none_when_only_today_snapshot(app):
    """Latest exists but nothing on or before the cutoff → None."""
    with app.app_context():
        eid = _seed_one_enrollment()
        _add_snapshot(eid, days_ago=0, rank=3, total_score=12.0)
        e = db.session.get(WorldCupEnrollment, eid)
        assert compute_rank_delta(e, window_days=1) is None


def test_compute_rank_delta_uses_window_days(app):
    """window_days=7 looks back ~a week. A snapshot from 3 days ago is not 'prior'
    when window_days=7; cutoff = today - 7 means prior must be on or before that."""
    with app.app_context():
        eid = _seed_one_enrollment()
        _add_snapshot(eid, days_ago=3, rank=4, total_score=10.0)
        _add_snapshot(eid, days_ago=0, rank=2, total_score=18.0)
        e = db.session.get(WorldCupEnrollment, eid)
        # No snapshot ≤ today - 7 days exists.
        assert compute_rank_delta(e, window_days=7) is None
        # A snapshot from 8 days ago does count.
        _add_snapshot(eid, days_ago=8, rank=10, total_score=2.0)
        assert compute_rank_delta(e, window_days=7) == 8  # 10 - 2


# ---------------------------------------------------------------------------
# compute_rank_deltas_bulk — PR #12 R2 (perf parity with compute_trend_by_enrollment)
# ---------------------------------------------------------------------------
def test_compute_rank_deltas_bulk_empty_input(app):
    """No ids in → empty dict out (no DB round-trip needed)."""
    with app.app_context():
        assert compute_rank_deltas_bulk([], window_days=1) == {}


def test_compute_rank_deltas_bulk_matches_single_helper(app):
    """For every enrollment, bulk[eid] must equal compute_rank_delta(enrollment).

    Three enrollments with mixed snapshot histories: improver, dropper, no-history.
    """
    with app.app_context():
        ids = _seed_enrollments([50.0, 40.0, 30.0])
        # Enrollment 0 — improver: yesterday rank 5, today rank 2 → +3
        _add_snapshot(ids[0], days_ago=1, rank=5, total_score=20.0)
        _add_snapshot(ids[0], days_ago=0, rank=2, total_score=50.0)
        # Enrollment 1 — dropper: yesterday rank 1, today rank 4 → -3
        _add_snapshot(ids[1], days_ago=1, rank=1, total_score=30.0)
        _add_snapshot(ids[1], days_ago=0, rank=4, total_score=40.0)
        # Enrollment 2 — no snapshot history → None

        bulk = compute_rank_deltas_bulk(ids, window_days=1)
        for eid in ids:
            e = db.session.get(WorldCupEnrollment, eid)
            assert bulk[eid] == compute_rank_delta(e, window_days=1), (
                f'bulk[{eid}]={bulk[eid]} differs from single helper'
            )
        # Spot-check the values themselves.
        assert bulk[ids[0]] == 3
        assert bulk[ids[1]] == -3
        assert bulk[ids[2]] is None


def test_compute_rank_deltas_bulk_season_scoped(app):
    """Snapshots whose enrollment is in a different season must not contribute.

    Mirrors the show_trend_column / compute_trend_by_enrollment season-scoping
    invariant (CLAUDE.md: WorldCupRankSnapshot aggregates must be season-scoped).
    """
    with app.app_context():
        # Active-season enrollment with a clean history.
        active_ids = _seed_enrollments([50.0])
        _add_snapshot(active_ids[0], days_ago=1, rank=5, total_score=20.0)
        _add_snapshot(active_ids[0], days_ago=0, rank=2, total_score=50.0)

        # Prior-season enrollment with snapshots that would otherwise pollute.
        prior_user = User(username='archie', email='archie@test.com')
        prior_user.set_password('pass')
        db.session.add(prior_user)
        db.session.flush()
        prior_e = WorldCupEnrollment(
            user_id=prior_user.id, season_year=SEASON_YEAR - 4,
            picks_submitted=True, total_score=99.0, usa_goals_guess=5,
        )
        db.session.add(prior_e)
        db.session.flush()
        today = now_utc().astimezone(WORLDCUP_TZ).date()
        for i in range(5):
            db.session.add(WorldCupRankSnapshot(
                enrollment_id=prior_e.id,
                captured_date=today - timedelta(days=i + 1),
                rank=1, total_score=99.0,
            ))
        db.session.commit()

        # Bulk lookup including the prior-season id should NOT find any rows
        # for the prior-season enrollment, even though raw snapshot rows exist.
        result = compute_rank_deltas_bulk([active_ids[0], prior_e.id], window_days=1)
        assert result[active_ids[0]] == 3
        assert result[prior_e.id] is None  # season filter blocks the join


def test_compute_rank_deltas_bulk_respects_window_days(app):
    """Same boundary semantics as the single helper — cutoff = today - window_days."""
    with app.app_context():
        ids = _seed_enrollments([50.0])
        _add_snapshot(ids[0], days_ago=3, rank=4, total_score=10.0)
        _add_snapshot(ids[0], days_ago=0, rank=2, total_score=50.0)

        # No snapshot ≤ today - 7 → None.
        assert compute_rank_deltas_bulk(ids, window_days=7) == {ids[0]: None}

        _add_snapshot(ids[0], days_ago=8, rank=10, total_score=2.0)
        assert compute_rank_deltas_bulk(ids, window_days=7) == {ids[0]: 8}


def test_compute_rank_deltas_bulk_runs_constant_queries(app):
    """Two queries total regardless of N — locks the perf contract that
    motivates the bulk helper (CR R2 #1 on PR #12).
    """
    from sqlalchemy import event

    with app.app_context():
        # Seed 5 enrollments with full snapshot history each.
        ids = _seed_enrollments([50.0, 40.0, 30.0, 20.0, 10.0])
        for i, eid in enumerate(ids):
            _add_snapshot(eid, days_ago=1, rank=i + 1, total_score=float(50 - i * 10))
            _add_snapshot(eid, days_ago=0, rank=i + 1, total_score=float(50 - i * 10))

        select_count = 0

        def _count_selects(conn, cursor, statement, *args, **kwargs):
            nonlocal select_count
            if statement.lstrip().upper().startswith('SELECT'):
                select_count += 1

        event.listen(db.engine, 'before_cursor_execute', _count_selects)
        try:
            compute_rank_deltas_bulk(ids, window_days=1)
        finally:
            event.remove(db.engine, 'before_cursor_execute', _count_selects)

        # Two SELECTs: one "today" join, one "prior" join. The per-call helper
        # would emit 2 * len(ids) = 10 queries here.
        assert select_count == 2, (
            f'compute_rank_deltas_bulk ran {select_count} SELECTs for {len(ids)} '
            f'enrollments — expected 2 (one for "today", one for "prior").'
        )
