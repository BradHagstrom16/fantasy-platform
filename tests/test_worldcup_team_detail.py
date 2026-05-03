"""Tests for the public /worldcup/team/<int:team_id> route."""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupPick,
)


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


def _seed_team(app, fifa='USA'):
    with app.app_context():
        t = WorldCupTeam(
            fifa_code=fifa, name=fifa, display_name=fifa,
            tier=1, multiplier=1.0, confederation='CONCACAF',
            group_letter='A',
        )
        db.session.add(t)
        db.session.commit()
        return t.id


def _seed_owner_with_pick(app, team_id, username='owner'):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.flush()
        e = WorldCupEnrollment(user_id=u.id, season_year=2026, picks_submitted=True)
        db.session.add(e)
        db.session.flush()
        p = WorldCupPick(enrollment_id=e.id, team_id=team_id, tier=1)
        db.session.add(p)
        db.session.commit()
        return u.id


def test_team_detail_returns_200_for_valid_team(client, app):
    team_id = _seed_team(app)
    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200


def test_team_detail_returns_404_for_invalid_team(client, app):
    resp = client.get('/worldcup/team/99999')
    assert resp.status_code == 404


def test_team_detail_public_no_auth_required(client, app):
    """Anonymous users see the page (matches leaderboard/stats access policy)."""
    team_id = _seed_team(app)
    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'USA' in resp.data


def test_team_detail_renders_team_name_and_fifa_code(client, app):
    team_id = _seed_team(app, fifa='ENG')
    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'ENG' in resp.data
