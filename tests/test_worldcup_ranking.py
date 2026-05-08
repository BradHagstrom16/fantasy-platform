"""Tests for games/worldcup/services/ranking helpers."""
from datetime import timedelta

import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.constants import SEASON_YEAR, WORLDCUP_TZ
from games.worldcup.models import WorldCupEnrollment, WorldCupRankSnapshot
from games.worldcup.services.ranking import (
    compute_rank_delta,
    compute_rank_neighbors,
)
from games.worldcup.services.state import now_utc


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


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
        # Two enrollments tied at 40 — both rank 2 (dense rank).
        ids = _seed_enrollments([50.0, 40.0, 40.0])
        r1 = compute_rank_neighbors(ids[1])
        r2 = compute_rank_neighbors(ids[2])
        assert r1['rank'] == 2
        assert r2['rank'] == 2


def test_compute_rank_neighbors_unknown_id_raises(app):
    with app.app_context():
        with pytest.raises(ValueError):
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
