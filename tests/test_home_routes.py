"""Route-level rendering tests for the four home states (Spec B follow-up B1)."""
import os
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db


@pytest.fixture
def app():
    """Testing app with in-memory SQLite + WC_FAKE_NOW disabled at start."""
    os.environ.pop('WC_FAKE_NOW', None)
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _wc_era_registry(monkeypatch):
    """Pin the WC-era registry (post-2026-08-11 changeover the real config
    features CFB). This module renders the archived WC lounge states — the
    frozen-WC regression net — so every test runs against the WC era."""
    from tests._registry_helpers import set_is_featured, set_status
    set_status(monkeypatch, 'worldcup', 'open')
    set_is_featured(monkeypatch, 'worldcup', True)
    set_status(monkeypatch, 'cfb', 'coming_soon')
    set_is_featured(monkeypatch, 'cfb', False)


def _make_user(username='alice', email='alice@example.com'):
    from models.user import User
    user = User(username=username, email=email)
    user.set_password('test1234')
    db.session.add(user)
    db.session.commit()
    return user


def _make_enrollment(user, picks_submitted=False, total_score=0.0):
    from games.worldcup.constants import SEASON_YEAR
    from games.worldcup.models import WorldCupEnrollment
    enr = WorldCupEnrollment(
        user_id=user.id,
        season_year=SEASON_YEAR,
        picks_submitted=picks_submitted,
        total_score=total_score,
    )
    db.session.add(enr)
    db.session.commit()
    return enr


def _make_team(fifa_code, name, tier=1, multiplier=1.0, group='A'):
    from games.worldcup.models import WorldCupTeam
    team = WorldCupTeam(
        fifa_code=fifa_code, name=name, display_name=name,
        tier=tier, multiplier=multiplier, confederation='TEST',
        group_letter=group,
    )
    db.session.add(team)
    db.session.commit()
    return team


def _make_pick(enrollment, team, tier=1):
    from games.worldcup.models import WorldCupPick
    pick = WorldCupPick(enrollment_id=enrollment.id, team_id=team.id, tier=tier)
    db.session.add(pick)
    db.session.commit()
    return pick


def _make_match(match_number, stage, home_team, away_team, completed=False,
                winner_team_id=None, group_letter=None, kickoff_utc=None):
    from games.worldcup.models import WorldCupMatch
    match = WorldCupMatch(
        match_number=match_number,
        stage=stage,
        group_letter=group_letter,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        is_completed=completed,
        winner_team_id=winner_team_id,
        kickoff_utc=kickoff_utc or datetime(2026, 6, 14, 19, 0, tzinfo=UTC),
    )
    db.session.add(match)
    db.session.commit()
    return match


def _login(client, user_id):
    from models.user import User
    auth_id = db.session.get(User, user_id).auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


def test_home_renders_logged_out(client):
    """Anonymous GET / renders the logged-out shell."""
    resp = client.get('/')
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'home-shell--out' in body
    assert 'Join the Club' in body  # logged-out CTA token from _home_out.html


def test_home_renders_pre_unenrolled(app, client):
    """Logged-in pre-deadline + no WC enrollment renders the join CTA."""
    with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        with app.app_context():
            user = _make_user()
            _login(client, user.id)
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--pre' in body
        assert 'Join the World Cup pool' in body  # decree CTA, unenrolled branch
        assert 'data-deadline-utc=' in body  # countdown markup


def test_home_renders_pre_enrolled_no_picks(app, client):
    """Pre-deadline + enrolled + picks_submitted=False renders the seal-roster CTA."""
    with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        with app.app_context():
            user = _make_user()
            _make_enrollment(user, picks_submitted=False)
            _login(client, user.id)
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--pre' in body
        assert 'Make your picks' in body  # decree CTA, enrolled-no-picks branch


def test_home_renders_pre_enrolled_sealed(app, client):
    """Pre-deadline + enrolled + sealed → ballot card renders + countdown present."""
    with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        with app.app_context():
            user = _make_user()
            enr = _make_enrollment(user, picks_submitted=True)
            team = _make_team('USA', 'United States')
            _make_pick(enr, team, tier=1)
            _login(client, user.id)
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--pre' in body
        assert 'data-deadline-utc=' in body
        # Sealed decree CTA routes to the WC hub.
        assert 'Enter the World Cup' in body
        # Ballot card renders the picked team's display_name in the flag's title attr
        assert 'United States' in body


def test_home_renders_live_unenrolled(app, client):
    """Live state + unenrolled renders the view-CTA with 'in session' eyebrow (CR3 live branch)."""
    with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T00:00:00Z'}):
        with app.app_context():
            user = _make_user()
            _login(client, user.id)
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--live' in body
        assert 'cta-card--view' in body
        assert 'Tournament in session' in body


def test_home_renders_live_enrolled(app, client):
    """Live + enrolled with one completed group match where pick rosters home side."""
    with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T00:00:00Z'}):
        with app.app_context():
            user = _make_user()
            enr = _make_enrollment(user, picks_submitted=True, total_score=10.0)
            usa = _make_team('USA', 'United States', tier=1, multiplier=1.0)
            mex = _make_team('MEX', 'Mexico', tier=1, multiplier=1.0, group='B')
            _make_pick(enr, usa, tier=1)
            _make_match(1, 'group', usa, mex, completed=True, winner_team_id=usa.id, group_letter='A')
            _login(client, user.id)
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--live' in body
        assert 'Dossier' in body  # greet-title in _home_live.html
        assert 'Recent Results' in body
        assert 'USA' in body  # picked team's FIFA code surfaces in result strip


def test_home_renders_post_with_champion(app, client):
    """Post state with match #104 completed renders champion banner + 'Tournament complete' CTA (CR3 post branch)."""
    with app.app_context():
        bra = _make_team('BRA', 'Brazil', tier=2, multiplier=1.5, group='C')
        arg = _make_team('ARG', 'Argentina', tier=2, multiplier=1.5, group='B')
        # Match #104 completed → triggers post state (no WC_FAKE_NOW needed once final is_completed)
        from games.worldcup.models import WorldCupMatch
        final = WorldCupMatch(
            match_number=104, stage='final',
            home_team_id=bra.id, away_team_id=arg.id,
            home_score=3, away_score=2, extra_time=True,
            winner_team_id=bra.id, is_completed=True,
            kickoff_utc=datetime(2026, 7, 19, 19, 0, tzinfo=UTC),
        )
        db.session.add(final)
        db.session.commit()

        user = _make_user()
        # No enrollment → unenrolled post path, which renders the view-CTA
        _login(client, user.id)
        # WC_FAKE_NOW after the final-match kickoff so worldcup_state() returns 'post'
        with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-07-20T00:00:00Z'}):
            resp = client.get('/')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'home-shell--post' in body
        assert 'Brazil' in body  # champion display name in banner
        assert 'Tournament complete' in body  # CR3 post branch
