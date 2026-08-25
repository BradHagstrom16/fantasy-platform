"""CFB Survivor — the member-facing "Settle the Tab" payment nudge.

Gate (games/cfb/services/payment.payment_nudge_for): an enrolled member who
has not paid sees the card — in the room (index, pick, my-picks) and as a
paragraph in the picks-open email; a paid member and the platform admin
never do. Join IS the commitment for Survivor (no picks_submitted step), so
the nudge appears the moment a member joins. Payment stays admin-confirmed
from /cfb/admin/payments — there is no member self-mark, so these tests only
assert presence/absence, never a paid mutation.
"""
from datetime import datetime
from html import unescape
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from extensions import db
from games.cfb.services.payment import payment_nudge_for
from games.cfb.services.reminders import send_picks_open_email
from tests._cfb_fixtures import make_enrollment, make_user, make_week

FUTURE_DEADLINE = datetime(2099, 9, 5, 11, 0)


def _member(name, *, has_paid=False, is_admin=False, display_name=None):
    user = make_user(name, is_admin=is_admin)
    enrollment = make_enrollment(user, display_name=display_name)
    enrollment.has_paid = has_paid
    db.session.commit()
    return user, enrollment


def _login(client, user):
    # Session identity is auth_id, never str(user.id) (CLAUDE.md invariant).
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


# ── Unit: the gate ───────────────────────────────────────────────────────

def test_unpaid_member_gets_cfb_rails_with_prefilled_memo(app):
    _, enrollment = _member('payer', display_name='Big Pay')
    with app.app_context():
        nudge = payment_nudge_for(enrollment, is_platform_admin=False)
    assert nudge['entry_fee'] == app.config['CFB_ENTRY_FEE']
    assert nudge['zelle_phone'] == app.config['PAYMENT_ZELLE_PHONE']
    q = parse_qs(urlsplit(nudge['venmo_url']).query)
    assert q['amount'] == [str(app.config['CFB_ENTRY_FEE'])]
    assert q['note'] == [f'CCC CFB Survivor {app.config["CFB_SEASON_YEAR"]} - Big Pay']


def test_memo_falls_back_to_username(app):
    _, enrollment = _member('plainname')
    with app.app_context():
        nudge = payment_nudge_for(enrollment, is_platform_admin=False)
    assert parse_qs(urlsplit(nudge['venmo_url']).query)['note'][0].endswith('- plainname')


def test_gate_hidden_when_paid(app):
    _, enrollment = _member('paid', has_paid=True)
    with app.app_context():
        assert payment_nudge_for(enrollment, is_platform_admin=False) is None


def test_gate_hidden_without_enrollment(app):
    with app.app_context():
        assert payment_nudge_for(None, is_platform_admin=False) is None


def test_gate_suppressed_for_platform_admin(app):
    _, enrollment = _member('commish', is_admin=True)
    with app.app_context():
        assert payment_nudge_for(enrollment, is_platform_admin=True) is None


# ── Rendered: the room surfaces ──────────────────────────────────────────

def _assert_nudge(body, app):
    text = unescape(body)
    assert 'Settle the Tab' in text
    assert 'https://venmo.com/' + app.config['PAYMENT_VENMO_HANDLE'] in text
    assert 'txn=pay&amount=' + str(app.config['CFB_ENTRY_FEE']) in text
    assert app.config['PAYMENT_ZELLE_PHONE'] in text


def test_index_shows_nudge_to_unpaid_member(client, app):
    user, _ = _member('idx')
    _login(client, user)
    _assert_nudge(client.get('/cfb/').get_data(as_text=True), app)


def test_index_shows_nudge_even_before_any_week_exists(client, app):
    """Launch-week state: a member who joins before Week 1 is imported still
    sees how to pay."""
    user, _ = _member('early')
    _login(client, user)
    body = client.get('/cfb/').get_data(as_text=True)
    assert 'Settle the Tab' in body


def test_pick_page_shows_nudge_below_the_call(client, app):
    make_week(1, deadline=FUTURE_DEADLINE, is_active=True)
    user, _ = _member('picker')
    _login(client, user)
    body = client.get('/cfb/pick/1').get_data(as_text=True)
    _assert_nudge(body, app)
    # The pick is the page's center of gravity: the tab sits under it.
    assert body.index('Picks Lock') < body.index('Settle the Tab')


def test_my_picks_shows_nudge(client, app):
    user, _ = _member('card')
    _login(client, user)
    _assert_nudge(client.get('/cfb/my-picks').get_data(as_text=True), app)


def test_nudge_hidden_for_paid_member(client):
    user, _ = _member('settled', has_paid=True)
    _login(client, user)
    for path in ('/cfb/', '/cfb/my-picks'):
        assert 'Settle the Tab' not in client.get(path).get_data(as_text=True)


def test_nudge_hidden_for_platform_admin(client):
    user, _ = _member('brad', is_admin=True)
    _login(client, user)
    assert 'Settle the Tab' not in client.get('/cfb/').get_data(as_text=True)


def test_nudge_absent_for_anonymous_visitor(client):
    assert 'Settle the Tab' not in client.get('/cfb/').get_data(as_text=True)


def test_no_member_self_mark_control(client):
    """Payment is admin-confirmed only: no 'I paid' form on the card."""
    user, _ = _member('honest')
    _login(client, user)
    body = client.get('/cfb/').get_data(as_text=True)
    assert 'update-payment' not in body
    assert 'I paid' not in body


# ── Email: the picks-open announcement carries the tab, unpaid only ──────

def _capture():
    calls = []

    def fake(to, subject, plain, html=None):
        calls.append({'to': to, 'plain': plain, 'html': html})
        return True

    return calls, patch(
        'games.cfb.services.reminders.send_platform_email', side_effect=fake)


def test_picks_open_email_tells_unpaid_member_how_to_pay(app):
    week = make_week(1, is_active=True)
    _member('owes')
    db.session.commit()

    calls, patcher = _capture()
    with patcher:
        send_picks_open_email(week.id)

    (msg,) = calls
    venmo = 'https://venmo.com/' + app.config['PAYMENT_VENMO_HANDLE']
    assert venmo in msg['plain'] and 'Settle the tab' in msg['plain']
    assert app.config['PAYMENT_ZELLE_PHONE'] in msg['plain']
    assert venmo in unescape(msg['html'])
    assert app.config['PAYMENT_ZELLE_PHONE'] in msg['html']


def test_picks_open_email_omits_the_tab_for_paid_and_admin(app):
    week = make_week(1, is_active=True)
    _member('settled', has_paid=True)
    _member('brad', is_admin=True)
    db.session.commit()

    calls, patcher = _capture()
    with patcher:
        send_picks_open_email(week.id)

    assert len(calls) == 2            # both still get the announcement
    for msg in calls:
        assert 'venmo.com' not in msg['plain']
        assert 'venmo.com' not in msg['html']
        assert 'Settle the tab' not in msg['plain']
