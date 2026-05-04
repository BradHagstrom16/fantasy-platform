"""Tests for the public /worldcup/team/<int:team_id> route."""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupPick, WorldCupMatch,
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


def test_team_detail_returns_404_for_invalid_team(client):
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


def test_team_detail_ownership_hidden_pre_deadline(client, app):
    """Pre-deadline + non-owner: no ownership ribbon, no count, no picker names."""
    team_id = _seed_team(app)
    _seed_owner_with_pick(app, team_id, username='alice')
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    # No ownership ribbon block content
    assert b'You Own This Nation' not in resp.data
    assert b'Roster ownership' not in resp.data
    assert b'Who Picked This' not in resp.data
    # Specifically: 'alice' must not appear in the response
    assert b'alice' not in resp.data
    # Path-to-crown section still renders (it's not gated by deadline)
    assert b'Path to the Crown' in resp.data or b'Out of the running' in resp.data


def test_team_detail_ownership_visible_post_deadline(client, app):
    """Post-deadline + non-owner: ribbon shows count/percent; picker list renders."""
    team_id = _seed_team(app)
    _seed_owner_with_pick(app, team_id, username='alice')
    _seed_owner_with_pick(app, team_id, username='bob')
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'Roster ownership' in resp.data
    assert b'Who Picked This' in resp.data
    assert b'alice' in resp.data
    assert b'bob' in resp.data


def test_team_detail_user_owns_ribbon(client, app):
    """Authenticated user with a pick on this team sees red 'You Own This Nation' ribbon."""
    team_id = _seed_team(app)
    user_id = _seed_owner_with_pick(app, team_id, username='alice')
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'You Own This Nation' in resp.data


def test_team_detail_user_owns_ribbon_pre_deadline(client, app):
    """Even pre-deadline, the owner sees their own 'You Own This Nation' ribbon
    (no privacy concern — it's their own pick)."""
    team_id = _seed_team(app)
    user_id = _seed_owner_with_pick(app, team_id, username='alice')
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'You Own This Nation' in resp.data
    # But ownership counts/names of OTHERS still hidden pre-deadline
    assert b'Who Picked This' not in resp.data


def test_team_detail_match_log_includes_all_team_fixtures(client, app):
    """Both home and away fixtures appear in the match log."""
    team_id = _seed_team(app, fifa='USA')
    other_id = _seed_team(app, fifa='ENG')
    with app.app_context():
        # Match where USA is home, vs ENG
        m1 = WorldCupMatch(
            match_number=1, stage='group', group_letter='A',
            home_team_id=team_id, away_team_id=other_id,
            home_score=2, away_score=1, is_completed=True,
        )
        # Match where USA is away, vs ENG
        m2 = WorldCupMatch(
            match_number=2, stage='group', group_letter='A',
            home_team_id=other_id, away_team_id=team_id,
            home_score=0, away_score=3, is_completed=True,
        )
        db.session.add_all([m1, m2])
        db.session.commit()

    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    # Both fixture lines should be visible (each has the opponent's FIFA code)
    # Two ENG fixture rows means 'ENG' appears at least twice in the response.
    assert resp.data.count(b'ENG') >= 2


def test_team_detail_score_events_match_canonical_helper(client, app):
    """Sum of displayed per-match points equals compute_team_score_events total — SSoT parity."""
    from games.worldcup.services.scoring import compute_team_score_events

    team_id = _seed_team(app, fifa='USA')
    with app.app_context():
        team = db.session.get(WorldCupTeam, team_id)
        assert team is not None
        # Simulate a completed group win for USA
        opponent = WorldCupTeam(
            fifa_code='ENG', name='ENG', display_name='ENG',
            tier=1, multiplier=1.0, confederation='UEFA',
            group_letter='A',
        )
        db.session.add(opponent)
        db.session.flush()
        m = WorldCupMatch(
            match_number=10, stage='group', group_letter='A',
            home_team_id=team.id, away_team_id=opponent.id,
            home_score=2, away_score=0, is_completed=True,
            winner_team_id=team.id, is_draw=False,
        )
        db.session.add(m)
        # Update USA group_wins to reflect the result for compute_team_score_events
        team.group_wins = 1
        team.base_points = 3.0  # GROUP_WIN
        db.session.commit()

        canonical_total = sum(ev.base_points for ev in compute_team_score_events(team))

    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    # The hero's "Base" stat block should display the canonical total
    base_str = "%.1f" % canonical_total
    assert base_str.encode() in resp.data
