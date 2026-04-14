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


# ── WC index helpers ─────────────────────────────────────────────────────────

def _make_enrolled_user_with_picks(app):
    """Create a user enrolled in WC with 9 picks submitted. Returns user.id."""
    with app.app_context():
        user = User(username='player1', email='player1@test.com')
        user.set_password('pass')
        db.session.add(user)
        db.session.flush()

        enrollment = WorldCupEnrollment(
            user_id=user.id,
            season_year=2026,
            picks_submitted=True,
            usa_goals_guess=4,
        )
        db.session.add(enrollment)
        db.session.flush()

        # Create 9 minimal teams across tiers and add picks
        tier_map = {1: 2, 2: 1, 3: 2, 4: 2, 5: 2}
        pick_num = 1
        for tier, count in tier_map.items():
            for _ in range(count):
                team = WorldCupTeam(
                    fifa_code=f'T{pick_num:02d}',
                    name=f'Team {pick_num}',
                    display_name=f'Team {pick_num}',
                    tier=tier,
                    multiplier=float(5 - tier) + 1.0,
                    confederation='TEST',
                    group_letter='A',
                )
                db.session.add(team)
                db.session.flush()
                pick = WorldCupPick(
                    enrollment_id=enrollment.id,
                    team_id=team.id,
                    tier=tier,
                )
                db.session.add(pick)
                pick_num += 1

        db.session.commit()
        return user.id


# ── WC index tests ───────────────────────────────────────────────────────────

def test_wc_index_shows_youre_in_post_deadline(client, app):
    user_id = _make_enrolled_user_with_picks(app)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True

    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get('/worldcup/')
    assert resp.status_code == 200
    assert b"You&#39;re In!" in resp.data or b"You're In!" in resp.data
    assert b'View My Picks' in resp.data
    assert b'Edit My Picks' not in resp.data
    assert b'/worldcup/join' not in resp.data


def test_wc_index_shows_tournament_underway_unenrolled_post_deadline(client):
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get('/worldcup/')
    assert resp.status_code == 200
    assert b'Tournament Underway' in resp.data
    assert b'View Leaderboard' in resp.data
    # The WC join CTA link (/worldcup/join) must not appear after deadline
    assert b'/worldcup/join' not in resp.data


def test_wc_index_shows_join_cta_pre_deadline_unenrolled(client):
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get('/worldcup/')
    assert resp.status_code == 200
    assert b'Join Now' in resp.data
