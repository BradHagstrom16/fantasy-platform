"""
Tests for World Cup public + admin routes that depend on deadline or
state guards. Complements tests/test_worldcup_scoring.py (engine tests).
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment


PAST_DEADLINE = datetime(2000, 1, 1, tzinfo=timezone.utc)
FUTURE_DEADLINE = datetime(2099, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _make_enrolled_user_with_tiebreaker(app, guess=7):
    """Create an enrollment with a known USA goals tiebreaker."""
    with app.app_context():
        user = User(username='tbplayer', email='tbplayer@test.com')
        user.set_password('pass')
        db.session.add(user)
        db.session.flush()

        enrollment = WorldCupEnrollment(
            user_id=user.id,
            season_year=2026,
            picks_submitted=True,
            usa_goals_guess=guess,
            total_score=5.0,
        )
        db.session.add(enrollment)
        db.session.commit()
        return user.id, enrollment.id


# ── Leaderboard tiebreaker visibility ────────────────────────────────────

def test_leaderboard_hides_tiebreaker_pre_deadline(client, app):
    _make_enrolled_user_with_tiebreaker(app, guess=7)
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    # The tiebreaker column header should not be in the desktop table
    assert b'Tiebreaker' not in resp.data
    # The mobile "TB: N" label should not be in the response
    assert b'TB:' not in resp.data
    # And the actual value should not leak
    assert b'>7<' not in resp.data


def test_leaderboard_shows_tiebreaker_post_deadline(client, app):
    _make_enrolled_user_with_tiebreaker(app, guess=7)
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Tiebreaker' in resp.data
    assert b'>7<' in resp.data
