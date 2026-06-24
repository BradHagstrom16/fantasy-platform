"""Admin bulk bracket populate (review-then-confirm)."""
from unittest.mock import patch

import pytest
from app import create_app
from extensions import db
from games.worldcup.models import WorldCupTeam, WorldCupMatch
from models.user import User


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


def _make_admin(app):
    with app.app_context():
        u = User(username='boss', email='boss@test.com', is_admin=True)
        u.set_password('x')
        db.session.add(u)
        db.session.commit()
        return u.auth_id


def _login(client, auth_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


def test_admin_bracket_requires_admin(client):
    resp = client.get('/worldcup/admin/bracket/R32')
    assert resp.status_code in (302, 401, 403)


def test_admin_bracket_get_renders_proposal(client, app):
    auth_id = _make_admin(app)
    _login(client, auth_id)
    fake = {'target_stage': 'R32', 'error': None, 'unresolved': [],
            'proposals': [{'match_number': 73, 'shell_id': 1, 'home_fifa': 'BRA',
                           'away_fifa': 'KSA', 'home_name': 'Brazil', 'away_name': 'Saudi Arabia',
                           'current_home': None, 'current_away': None,
                           'already_set': False, 'is_completed': False}]}
    with patch('games.worldcup.routes.fetch_bracket_proposal', return_value=fake):
        resp = client.get('/worldcup/admin/bracket/R32')
    assert resp.status_code == 200
    assert b'BRA' in resp.data and b'KSA' in resp.data


def test_admin_bracket_post_assigns_shells(client, app):
    auth_id = _make_admin(app)
    with app.app_context():
        for code, name in [('BRA', 'Brazil'), ('KSA', 'Saudi Arabia')]:
            db.session.add(WorldCupTeam(fifa_code=code, name=name, display_name=name,
                                        tier=1, multiplier=1.0, confederation='X', group_letter='A'))
        shell = WorldCupMatch(match_number=73, stage='R32')
        db.session.add(shell)
        db.session.commit()
        shell_id = shell.id
    _login(client, auth_id)
    resp = client.post('/worldcup/admin/bracket/R32', data={
        'csrf_token': 'x',
        'shell_id': str(shell_id), 'home_fifa': 'BRA', 'away_fifa': 'KSA',
    }, follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        s = db.session.get(WorldCupMatch, shell_id)
        assert s.home_team.fifa_code == 'BRA'
        assert s.away_team.fifa_code == 'KSA'


def test_admin_bracket_post_skips_completed_shell(client, app):
    auth_id = _make_admin(app)
    with app.app_context():
        for code, name in [('BRA', 'Brazil'), ('KSA', 'Saudi Arabia')]:
            db.session.add(WorldCupTeam(fifa_code=code, name=name, display_name=name,
                                        tier=1, multiplier=1.0, confederation='X', group_letter='A'))
        shell = WorldCupMatch(match_number=73, stage='R32', is_completed=True)
        db.session.add(shell)
        db.session.commit()
        shell_id = shell.id
    _login(client, auth_id)
    client.post('/worldcup/admin/bracket/R32', data={
        'csrf_token': 'x',
        'shell_id': str(shell_id), 'home_fifa': 'BRA', 'away_fifa': 'KSA',
    })
    with app.app_context():
        s = db.session.get(WorldCupMatch, shell_id)
        assert s.home_team_id is None  # completed shell left untouched
