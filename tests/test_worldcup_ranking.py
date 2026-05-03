"""Tests for games/worldcup/services/ranking.compute_rank_neighbors."""
import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment
from games.worldcup.services.ranking import compute_rank_neighbors


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
            user_id=u.id, season_year=2026,
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
