"""Signup auto-joins the World Cup while picks are open (pre-deadline only).

This is a SANCTIONED signup-time auto-enroll — distinct from the banned
pick/admin auto-enroll path (tests/test_golf_auto_enroll_removed.py). It
self-disables once the tournament starts (deadline passes).
"""
import os
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


def _register(client, username='newbie'):
    return client.post('/register', data={
        'username': username,
        'email': f'{username}@test.com',
        'password': 'secret1',
        'confirm_password': 'secret1',
        'csrf_token': 'x',
    }, follow_redirects=True)


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
    # The auto-join flash nudges the user to make picks (exact copy finalized
    # by impeccable in Phase 5; assert on the distinctive "make your picks"
    # phrase, which the home page does not otherwise contain). If impeccable
    # changes the wording, update this assertion alongside it.
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
