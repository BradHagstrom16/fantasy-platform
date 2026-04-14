"""
Tests for post-deadline UI state across homepage and WC index.
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupPick


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


# ── Homepage tests ──────────────────────────────────────────────────────────

def test_homepage_shows_view_standings_post_deadline(client):
    with patch('core.main.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get('/')
    assert resp.status_code == 200
    assert b'View Standings' in resp.data


def test_homepage_shows_enter_pool_pre_deadline_authenticated(client, app):
    with app.app_context():
        user = User(username='homer', email='homer@test.com')
        user.set_password('pass')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True

    with patch('core.main.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get('/')
    assert resp.status_code == 200
    assert b'Enter the Pool' in resp.data


def test_homepage_shows_join_pool_pre_deadline_anonymous(client):
    with patch('core.main.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get('/')
    assert resp.status_code == 200
    assert b'Join the World Cup Pool' in resp.data
