"""Tests for games.worldcup.services.state.worldcup_hub_state.

4-state resolver for the WC hub. 'out' overrides phase — anonymous OR
unenrolled-for-current-season users always see the marketing surface,
regardless of where the tournament is.
"""
import os
from datetime import timedelta
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from games.worldcup.constants import SEASON_YEAR, TOURNAMENT_DEADLINE_UTC
from games.worldcup.models import WorldCupEnrollment, WorldCupMatch
from games.worldcup.services.state import worldcup_hub_state
from models.user import User


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(email='u@test'):
    username = email.split('@', 1)[0]
    u = User(
        email=email,
        username=username,
        password_hash='x',
        display_name='U',
    )
    db.session.add(u)
    db.session.flush()
    return u


def _enroll(user, season=SEASON_YEAR):
    e = WorldCupEnrollment(user_id=user.id, season_year=season)
    db.session.add(e)
    db.session.flush()
    return e


def test_anonymous_user_resolves_out(app):
    """None or AnonymousUserMixin → 'out'."""
    assert worldcup_hub_state(None) == 'out'


def test_authenticated_unenrolled_user_resolves_out(app):
    user = _make_user()
    db.session.commit()
    assert worldcup_hub_state(user) == 'out'


def test_authenticated_enrolled_pre_deadline_resolves_pre(app):
    user = _make_user()
    _enroll(user)
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    # ENVIRONMENT=testing activates the WC_FAKE_NOW seam in now_utc()
    # without depending on outside process env.
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing', 'WC_FAKE_NOW': fake_pre}):
        assert worldcup_hub_state(user) == 'pre'


def test_authenticated_enrolled_post_deadline_resolves_live_when_final_open(app):
    user = _make_user()
    _enroll(user)
    db.session.commit()
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing', 'WC_FAKE_NOW': fake_live}):
        assert worldcup_hub_state(user) == 'live'


def test_authenticated_enrolled_resolves_post_when_final_completed(app):
    user = _make_user()
    _enroll(user)
    # Insert match #104 marked complete to flip the 'post' branch
    final = WorldCupMatch(
        match_number=104, stage='final', is_completed=True,
    )
    db.session.add(final)
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=30)).isoformat()
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing', 'WC_FAKE_NOW': fake_post}):
        assert worldcup_hub_state(user) == 'post'


def test_enrollment_for_prior_season_does_not_count_as_enrolled(app):
    """A user enrolled in a previous cup but not the current one is 'out'."""
    user = _make_user()
    _enroll(user, season=SEASON_YEAR - 4)
    db.session.commit()
    assert worldcup_hub_state(user) == 'out'
