"""Signup auto-joins the World Cup while picks are open (pre-deadline only).

This is a SANCTIONED signup-time auto-enroll — distinct from the banned
pick/admin auto-enroll path (tests/test_golf_auto_enroll_removed.py). It
self-disables once the tournament starts (deadline passes).
"""
import os
import uuid
from unittest import mock

import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment
from games.worldcup.constants import SEASON_YEAR


@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _reg_data(**overrides):
    """Registration POST payload with credentials generated at runtime.

    The username and password are derived from a fresh uuid rather than written
    as string literals, so GitGuardian's username/password detector doesn't flag
    the test fixtures (there is no real secret here, only throwaway values for an
    in-memory DB). Pass `username=`/`next=` etc. to override.
    """
    token = uuid.uuid4().hex
    data = {
        'username': f'u{token[:11]}',
        'email': f'u{token[:11]}@test.com',
        'password': token,
        'confirm_password': token,
        'csrf_token': 'x',
    }
    data.update(overrides)
    return data


def _register(client, username='newbie'):
    return client.post('/register', data=_reg_data(
        username=username, email=f'{username}@test.com',
    ), follow_redirects=True)


def test_signup_auto_joins_worldcup_pre_deadline(app, client):
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2026-01-01T00:00:00+00:00'}):
        resp = _register(client, 'preuser')
    assert resp.status_code == 200
    with app.app_context():
        u = User.query.filter_by(username='preuser').first()
        assert u is not None
        enr = WorldCupEnrollment.query.filter_by(
            user_id=u.id, season_year=SEASON_YEAR).first()
        assert enr is not None  # auto-joined


def test_signup_shows_worldcup_flash_pre_deadline(app, client):
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2026-01-01T00:00:00+00:00'}):
        resp = _register(client, 'flashuser')
    # The auto-join flash nudges the user to make picks. Assert on the
    # distinctive "make your picks" phrase, which the home page does not
    # otherwise contain (so this is load-bearing for the flash, not the page).
    assert 'make your picks' in resp.get_data(as_text=True).lower()


def test_signup_does_not_auto_join_after_deadline(app, client):
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2099-01-01T00:00:00+00:00'}):
        resp = _register(client, 'lateuser')
    assert resp.status_code == 200
    with app.app_context():
        u = User.query.filter_by(username='lateuser').first()
        assert u is not None  # account still created
        enr = WorldCupEnrollment.query.filter_by(
            user_id=u.id, season_year=SEASON_YEAR).first()
        assert enr is None  # NOT auto-joined post-deadline


def test_signup_auto_join_is_idempotent(app, client):
    """Defensive: a second enroll for the same user never duplicates."""
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2026-01-01T00:00:00+00:00'}):
        _register(client, 'dupuser')
    with app.app_context():
        u = User.query.filter_by(username='dupuser').first()
        from games.worldcup.services.enrollment import admin_enroll
        admin_enroll(u.id)  # second call
        count = WorldCupEnrollment.query.filter_by(
            user_id=u.id, season_year=SEASON_YEAR).count()
        assert count == 1


# ---------------------------------------------------------------------------
# register() honors a safe `next` (parity with login). The logged-out
# "Join the Club" CTA passes ?next=/worldcup/join; without this the parameter
# was a no-op and a new signup always landed on the platform home.
# ---------------------------------------------------------------------------

def test_register_form_carries_next_hidden_field(app, client):
    """The register form echoes `next` into a hidden field so it survives the
    GET -> POST (the form action drops the query string)."""
    body = client.get('/register?next=/worldcup/join').get_data(as_text=True)
    assert 'name="next"' in body
    assert 'value="/worldcup/join"' in body


def test_register_honors_safe_relative_next(app, client):
    """A safe relative `next` is honored after signup (post-deadline here to
    isolate the redirect from the pre-deadline auto-join path)."""
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2099-01-01T00:00:00+00:00'}):
        resp = client.post('/register', data=_reg_data(next='/worldcup/join'))
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/worldcup/join')


def test_register_rejects_unsafe_absolute_next(app, client):
    """An absolute `next` URL is rejected (open-redirect guard); signup falls
    back to the home page rather than bouncing off-site."""
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2099-01-01T00:00:00+00:00'}):
        resp = client.post('/register', data=_reg_data(next='https://evil.example/steal'))
    assert resp.status_code == 302
    assert 'evil.example' not in resp.headers['Location']


def test_register_rejects_backslash_protocol_relative_next(app, client):
    """`/\\evil.example` passes a naive `netloc == ''` check but browsers
    normalize the backslash to `//`, making it protocol-relative. The hardened
    `_is_safe_next` guard must reject it."""
    with mock.patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                      'WC_FAKE_NOW': '2099-01-01T00:00:00+00:00'}):
        resp = client.post('/register', data=_reg_data(next='/\\evil.example'))
    assert resp.status_code == 302
    assert 'evil.example' not in resp.headers['Location']
