"""Authenticated responses must carry `Cache-Control: ... no-store` so no shared
cache (CDN / proxy / browser) can store one user's rendered page and serve it to
another. Public/anonymous responses must stay cacheable (no `no-store`) so the CDN
can still front the marketing/public surfaces.

Defense-in-depth follow-up to the auth-identity fix: even with a misconfigured
edge "Cache Everything" rule (which ignores Vary: Cookie), an authenticated page
can never be cached.
"""
import os

import pytest

from app import create_app
from extensions import db
from models.user import User


@pytest.fixture
def app():
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


def _make_user(username='alice', email='alice@example.com'):
    user = User(username=username, email=email)
    user.set_password('test1234')
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.get_id()
        sess['_fresh'] = True


def test_authenticated_response_is_no_store(client, app):
    user = _make_user()
    _login(client, user)
    resp = client.get('/profile')  # @login_required → always authenticated 200
    assert resp.status_code == 200
    assert 'no-store' in resp.headers.get('Cache-Control', '')


def test_anonymous_public_response_is_not_no_store(client):
    """Logged-out pages stay cacheable — the header must not forbid storage."""
    resp = client.get('/login')
    assert resp.status_code == 200
    assert 'no-store' not in resp.headers.get('Cache-Control', '')


def test_anonymous_home_response_is_not_no_store(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert 'no-store' not in resp.headers.get('Cache-Control', '')
