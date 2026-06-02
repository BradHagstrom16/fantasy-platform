"""Regression lock: session/cookie identity must not be the reusable integer PK.

Incident (2026-06-01 production): the §14 launch DB wipe runs `db downgrade base`
→ `db upgrade`, which restarts the users id sequence. A second signup after the
wipe inherited a recycled id, and a pre-wipe Flask-Login remember-me cookie
(still validly signed — SECRET_KEY unchanged) loaded that recycled id, logging
one person into another's account.

Fix: identity is User.auth_id (a random, never-reused token) via get_id(), and
the user_loader looks up by auth_id. A stale cookie carrying an integer id (or
any token a current user doesn't own) matches nobody → logged out, never a
cross-login.
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


def _make_user(username, email):
    user = User(username=username, email=email)
    user.set_password('test1234')
    db.session.add(user)
    db.session.commit()
    return user


def _load_user(app, cookie_value):
    """Invoke the app's registered Flask-Login user_loader exactly as a request would."""
    return app.login_manager._user_callback(cookie_value)


def test_get_id_returns_auth_id_not_integer_pk(app):
    user = _make_user('alice', 'alice@example.com')
    assert user.auth_id is not None
    assert user.get_id() == user.auth_id
    assert user.get_id() != str(user.id)


def test_each_user_gets_a_unique_auth_id(app):
    a = _make_user('alice', 'alice@example.com')
    b = _make_user('bob', 'bob@example.com')
    assert a.auth_id and b.auth_id
    assert a.auth_id != b.auth_id


def test_user_loader_resolves_by_auth_id(app):
    user = _make_user('alice', 'alice@example.com')
    assert _load_user(app, user.auth_id).id == user.id


def test_stale_integer_id_cookie_does_not_authenticate(app):
    """A pre-fix cookie carrying the integer PK string must not load a user."""
    user = _make_user('alice', 'alice@example.com')
    assert _load_user(app, str(user.id)) is None


def test_db_wipe_with_recycled_id_does_not_cross_authenticate(app):
    """The exact incident: wipe restarts the id sequence; the pre-wipe cookie
    must not authenticate as the new user who inherits the recycled id."""
    alex = _make_user('alex', 'alex@example.com')
    alex_auth_id = alex.auth_id
    alex_id = alex.id

    # Destructive reset: drop + recreate restarts the id sequence (mirrors
    # `flask db downgrade base` → `db upgrade`).
    db.session.remove()
    db.drop_all()
    db.create_all()

    ben = _make_user('ben', 'ben@example.com')
    assert ben.id == alex_id  # recycled PK — the precondition for the incident

    # Alex's old remember-me cookie carried his auth_id; it now matches nobody.
    assert _load_user(app, alex_auth_id) is None
    # And a stale integer-id cookie (the pre-fix identity) also matches nobody —
    # crucially it does NOT load Ben.
    assert _load_user(app, str(alex_id)) is None
    # Ben only loads via his own (distinct) auth_id.
    assert ben.auth_id != alex_auth_id
    assert _load_user(app, ben.auth_id).username == 'ben'
