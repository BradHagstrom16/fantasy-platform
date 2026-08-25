"""The Docket — the member-facing "Settle the Tab" payment nudge.

Gate (games/docket/services/payment.payment_nudge_for): an enrolled member
who has not paid sees the card — on the sheet (including the pre-season
"awaiting the docket" state) and the ledger, and as a paragraph in the
picks-open email; a paid member and the platform admin never do. Payment
stays admin-confirmed from /docket/admin/payments — no member self-mark.
"""
from datetime import datetime
from html import unescape
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from extensions import db
from games.docket.cli import _run_import
from games.docket.services.notifications import notify_picks_open
from games.docket.services.payment import payment_nudge_for
from games.docket.services.weeks import SEASON_YEAR
from tests._docket_fixtures import (
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

KICK = datetime(2026, 9, 5, 18, 0)


def _member(name, *, has_paid=False, is_admin=False, display_name=None):
    user = make_user(name, is_admin=is_admin)
    enrollment = make_enrollment(user, has_paid=has_paid,
                                 display_name=display_name)
    db.session.commit()
    return user, enrollment


# ── Unit: the gate ───────────────────────────────────────────────────────

def test_unpaid_member_gets_docket_rails_with_prefilled_memo(app):
    _, enrollment = _member('payer', display_name='Clerk')
    with app.app_context():
        nudge = payment_nudge_for(enrollment, is_platform_admin=False)
    assert nudge['entry_fee'] == app.config['DOCKET_ENTRY_FEE']
    assert nudge['zelle_phone'] == app.config['PAYMENT_ZELLE_PHONE']
    q = parse_qs(urlsplit(nudge['venmo_url']).query)
    assert q['amount'] == [str(app.config['DOCKET_ENTRY_FEE'])]
    assert q['note'] == [f'CCC The Docket {SEASON_YEAR} - Clerk']


def test_gate_hidden_when_paid_or_absent_or_admin(app):
    _, paid = _member('paid', has_paid=True)
    _, commish = _member('brad', is_admin=True)
    with app.app_context():
        assert payment_nudge_for(paid, is_platform_admin=False) is None
        assert payment_nudge_for(None, is_platform_admin=False) is None
        assert payment_nudge_for(commish, is_platform_admin=True) is None


# ── Rendered: the room surfaces ──────────────────────────────────────────

def _assert_nudge(body, app):
    text = unescape(body)
    assert 'Settle the Tab' in text
    assert 'https://venmo.com/' + app.config['PAYMENT_VENMO_HANDLE'] in text
    assert 'txn=pay&amount=' + str(app.config['DOCKET_ENTRY_FEE']) in text
    assert app.config['PAYMENT_ZELLE_PHONE'] in text


def test_sheet_awaiting_state_shows_nudge(client, app):
    """Pre-season: no week imported yet, the sheet is the 'Court convenes'
    empty state — and the tab still shows, because that is exactly when a
    new member is primed to pay."""
    user, _ = _member('early')
    login(client, user)
    body = client.get('/docket/').get_data(as_text=True)
    assert 'Awaiting the docket' in body
    _assert_nudge(body, app)


def test_sheet_with_a_posted_week_shows_nudge(client, app):
    week = make_week(1)
    make_game(week, kickoff=KICK)
    user, _ = _member('sheet')
    login(client, user)
    _assert_nudge(client.get('/docket/').get_data(as_text=True), app)


def test_ledger_shows_nudge(client, app):
    user, _ = _member('ledger')
    login(client, user)
    _assert_nudge(client.get('/docket/ledger').get_data(as_text=True), app)


def test_nudge_hidden_for_paid_member_and_admin(client):
    paid, _ = _member('settled', has_paid=True)
    login(client, paid)
    for path in ('/docket/', '/docket/ledger'):
        assert 'Settle the Tab' not in client.get(path).get_data(as_text=True)
    brad, _ = _member('brad', is_admin=True)
    login(client, brad)
    assert 'Settle the Tab' not in client.get('/docket/').get_data(as_text=True)


def test_no_member_self_mark_control(client):
    user, _ = _member('honest')
    login(client, user)
    body = client.get('/docket/').get_data(as_text=True)
    assert 'update-payment' not in body
    assert 'I paid' not in body


# ── Email: the picks-open announcement carries the tab, unpaid only ──────

def _capture():
    calls = []

    def fake(to, subject, plain, html=None):
        calls.append({'to': to, 'plain': plain, 'html': html})
        return True

    return calls, patch(
        'games.docket.services.notifications.send_platform_email',
        side_effect=fake)


def test_notify_picks_open_tells_unpaid_member_how_to_pay(app):
    week = make_week(1)
    user, enrollment = _member('owes')

    calls, patcher = _capture()
    with patcher:
        notify_picks_open(week, [(user, enrollment)])

    (msg,) = calls
    venmo = 'https://venmo.com/' + app.config['PAYMENT_VENMO_HANDLE']
    assert venmo in msg['plain'] and 'Settle the tab' in msg['plain']
    assert app.config['PAYMENT_ZELLE_PHONE'] in msg['plain']
    assert venmo in unescape(msg['html'])
    assert app.config['PAYMENT_ZELLE_PHONE'] in msg['html']


def test_notify_picks_open_omits_the_tab_for_paid_and_admin(app):
    week = make_week(1)
    paid = _member('settled', has_paid=True)
    brad = _member('brad', is_admin=True)

    calls, patcher = _capture()
    with patcher:
        notify_picks_open(week, [paid, brad])

    assert len(calls) == 2
    for msg in calls:
        assert 'venmo.com' not in msg['plain']
        assert 'venmo.com' not in msg['html']


@patch('games.docket.cli.import_week', return_value={'status': 'ok'})
def test_import_announcement_carries_the_tab_per_enrollment(mock_import, app):
    """The real trigger path: the Sep 1 import resolves each roster member's
    enrollment so the tab lands only in unpaid inboxes."""
    week = make_week(1)
    make_game(week, kickoff=KICK)
    _member('owes')
    _member('settled', has_paid=True)

    calls, patcher = _capture()
    with patcher:
        _run_import(1, False, 'setup')

    by_to = {c['to']: c for c in calls}
    assert set(by_to) == {'owes@test.com', 'settled@test.com'}
    assert 'venmo.com' in by_to['owes@test.com']['plain']
    assert 'venmo.com' not in by_to['settled@test.com']['plain']
