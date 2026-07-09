"""Admin 'Load from API' proposal endpoint."""
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
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
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.auth_id


def test_advancement_proposal_endpoint_requires_admin(client):
    resp = client.get('/worldcup/admin/advancement/proposal')
    assert resp.status_code in (302, 401, 403)


def test_advancement_proposal_endpoint_returns_json(client, app):
    auth_id = _make_admin(app)
    fake = {'groups': [{'letter': 'A', 'group_winner': 'MEX',
                        'runner_up': 'RSA', 'best_third': 'KOR',
                        'third_advances': True, 'table': []}],
            'ko_pairings': []}
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    with patch('games.worldcup.routes.fetch_advancement_proposal', return_value=fake):
        resp = client.get('/worldcup/admin/advancement/proposal')
    assert resp.status_code == 200
    assert resp.get_json()['groups'][0]['group_winner'] == 'MEX'
