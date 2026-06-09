"""Member-facing "Settle the Tab" payment nudge — gate logic + rendered surfaces.

The nudge shows to an enrolled member who has submitted picks but not paid,
while the tournament is pre-kickoff or live (hidden once completed), and never
to a platform admin. Payment stays admin-confirmed (toggled from
/worldcup/admin/payments); there is no member-facing self-mark control, so
these tests only assert presence/absence of the nudge, never a paid mutation.
"""
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.constants import (
    SEASON_YEAR, ENTRY_FEE, VENMO_URL, ZELLE_PHONE,
)
from games.worldcup.models import WorldCupEnrollment
from games.worldcup.services.payment import payment_nudge_for


LIVE_PHASES = ('pre_tournament', 'group_stage', 'knockout')


def _enr(picks_submitted=True, has_paid=False):
    return SimpleNamespace(picks_submitted=picks_submitted, has_paid=has_paid)


# ---------------------------------------------------------------------------
# Unit: gate logic (payment_nudge_for)
# ---------------------------------------------------------------------------

def test_nudge_shows_for_unpaid_submitted_member_across_live_phases():
    for phase in LIVE_PHASES:
        out = payment_nudge_for(_enr(), phase, is_platform_admin=False)
        assert out == {
            'entry_fee': ENTRY_FEE,
            'venmo_url': VENMO_URL,
            'zelle_phone': ZELLE_PHONE,
        }, f'nudge payload wrong/missing in phase {phase}'


def test_nudge_hidden_once_tournament_completed():
    assert payment_nudge_for(_enr(), 'completed', is_platform_admin=False) is None


def test_nudge_hidden_when_already_paid():
    assert payment_nudge_for(_enr(has_paid=True), 'group_stage', False) is None


def test_nudge_hidden_when_picks_not_submitted():
    assert payment_nudge_for(_enr(picks_submitted=False), 'pre_tournament', False) is None


def test_nudge_hidden_when_no_enrollment():
    assert payment_nudge_for(None, 'pre_tournament', False) is None


def test_nudge_suppressed_for_platform_admin():
    # A fully-eligible enrollment is still suppressed for the Commish.
    assert payment_nudge_for(_enr(), 'pre_tournament', is_platform_admin=True) is None


def test_payment_constants_present():
    assert VENMO_URL == 'https://venmo.com/u/Bradley-Hagstrom'
    assert ZELLE_PHONE.strip()
    assert ENTRY_FEE == 25


# ---------------------------------------------------------------------------
# Rendered: the nudge on real WC-room surfaces
# ---------------------------------------------------------------------------

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


def _member(username, *, picks_submitted=True, has_paid=False, is_admin=False):
    u = User(username=username, email=f'{username}@test.com', is_admin=is_admin)
    u.set_password('pass')
    db.session.add(u)
    db.session.flush()
    e = WorldCupEnrollment(
        user_id=u.id, season_year=SEASON_YEAR,
        picks_submitted=picks_submitted, has_paid=has_paid,
        usa_goals_guess=5,
    )
    db.session.add(e)
    db.session.commit()
    return u


def _login(client, user):
    # Session identity is auth_id, never str(user.id) (CLAUDE.md auth invariant).
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def test_picks_page_shows_nudge_with_both_rails(client):
    _login(client, _member('payer'))
    body = client.get('/worldcup/picks').get_data(as_text=True)
    assert 'Settle the Tab' in body
    assert VENMO_URL in body
    assert ZELLE_PHONE in body


def test_leaderboard_shows_nudge(client):
    _login(client, _member('payer2'))
    body = client.get('/worldcup/leaderboard').get_data(as_text=True)
    assert 'Settle the Tab' in body


def test_hub_pre_state_shows_nudge(client):
    _login(client, _member('hubber'))
    # Pin "now" before the June 11 deadline so the hub resolves to the pre
    # state (WC_FAKE_NOW seam only activates with ENVIRONMENT in dev/testing).
    with patch.dict(os.environ, {
        'WC_FAKE_NOW': '2026-06-01T00:00:00+00:00', 'ENVIRONMENT': 'testing',
    }):
        body = client.get('/worldcup/').get_data(as_text=True)
    assert 'Settle the Tab' in body


def test_nudge_hidden_for_paid_member(client):
    _login(client, _member('paid', has_paid=True))
    body = client.get('/worldcup/picks').get_data(as_text=True)
    assert 'Settle the Tab' not in body


def test_nudge_hidden_without_submitted_picks(client):
    _login(client, _member('nopicks', picks_submitted=False))
    body = client.get('/worldcup/picks').get_data(as_text=True)
    assert 'Settle the Tab' not in body


def test_nudge_hidden_for_admin(client):
    _login(client, _member('commish', is_admin=True))
    body = client.get('/worldcup/picks').get_data(as_text=True)
    assert 'Settle the Tab' not in body
