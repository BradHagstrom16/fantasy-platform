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
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupMatch


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


# ── Admin dashboard completed-matches list ──────────────────────────────

def _make_admin_user(app):
    """Create a platform admin user and return their id."""
    with app.app_context():
        user = User(username='wcadmin', email='wcadmin@test.com', is_admin=True)
        user.set_password('pass')
        db.session.add(user)
        db.session.commit()
        return user.id


def _seed_two_completed_group_matches(app):
    """Seed two completed group matches with different update times."""
    with app.app_context():
        a = WorldCupTeam(
            fifa_code='AAA', name='Alpha', display_name='Alpha',
            tier=3, multiplier=2.5, confederation='TEST', group_letter='A',
        )
        b = WorldCupTeam(
            fifa_code='BBB', name='Beta', display_name='Beta',
            tier=3, multiplier=2.5, confederation='TEST', group_letter='A',
        )
        c = WorldCupTeam(
            fifa_code='CCC', name='Gamma', display_name='Gamma',
            tier=3, multiplier=2.5, confederation='TEST', group_letter='A',
        )
        d = WorldCupTeam(
            fifa_code='DDD', name='Delta', display_name='Delta',
            tier=3, multiplier=2.5, confederation='TEST', group_letter='A',
        )
        db.session.add_all([a, b, c, d])
        db.session.flush()

        from games.worldcup.services.scoring import process_match_result
        m1 = WorldCupMatch(
            match_number=1, stage='group', group_letter='A',
            home_team_id=a.id, away_team_id=b.id,
        )
        m2 = WorldCupMatch(
            match_number=2, stage='group', group_letter='A',
            home_team_id=c.id, away_team_id=d.id,
        )
        db.session.add_all([m1, m2])
        db.session.commit()

        process_match_result(
            match_id=m1.id, home_score=1, away_score=0,
            winner_fifa_code='AAA',
        )
        process_match_result(
            match_id=m2.id, home_score=2, away_score=1,
            winner_fifa_code='CCC',
        )
        return m1.id, m2.id


def test_admin_dashboard_lists_completed_matches(client, app):
    admin_id = _make_admin_user(app)
    _seed_two_completed_group_matches(app)

    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True

    resp = client.get('/worldcup/admin/')
    assert resp.status_code == 200
    # Card header must be rendered
    assert b'Completed Matches' in resp.data
    # Both match numbers surface
    assert b'>1<' in resp.data or b'#1' in resp.data
    assert b'>2<' in resp.data or b'#2' in resp.data
