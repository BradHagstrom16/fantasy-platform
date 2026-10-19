"""The Pay Sheet's "Settle the Tab" nudge (ADR-056; ADR-075 D4): per league.

Gate (games/golf/services/payment.payment_nudge_for): a member holding an
unpaid line in a league sees the card on THAT league's sheet, with that
league's own fee, and the strip in that league's picks-open letter; a paid
line, a platform admin, that league's commissioner and blank rails never do.
``has_paid`` stays admin-confirmed from The Roster and The Tab: there is no
member self-mark, so these tests assert presence and absence only.
"""
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from extensions import db
from games.golf.services.payment import payment_nudge_for
from games.golf.services.reminders import send_picks_open_email
from tests.test_golf_leagues import (
    _line_of,
    _member,
    _platform_admin,
    _season_event,
    _viewer,
)


def _two_sheets(app, golf_leagues, *, username='brad_tab', paid_handicap=True, admin_in=None):
    """Brad on both sheets: paid on the Handicap, owing on the Pollyanna at $30."""
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    pollyanna.entry_fee = 30
    brad = _member(username, handicap, pollyanna, app=app, admin_in=admin_in,
                   display_name='Brad Tab')
    _line_of(brad, handicap).has_paid = paid_handicap
    db.session.commit()
    return brad


def test_nudge_shows_for_an_unpaid_line_in_that_league_only(app, golf_leagues):
    handicap, pollyanna = golf_leagues['handicap'], golf_leagues['pollyanna']
    brad = _two_sheets(app, golf_leagues)

    nudge = payment_nudge_for(_line_of(brad, pollyanna), is_platform_admin=False)
    assert nudge['entry_fee'] == 30 and nudge['league_name'] == 'Pollyanna Pay Sheet'
    assert nudge['zelle_phone'] == app.config['PAYMENT_ZELLE_PHONE']
    q = parse_qs(urlsplit(nudge['venmo_url']).query)
    assert q['amount'] == ['30']
    assert q['note'] == [f'CCC Pollyanna Pay Sheet {app.config["SEASON_YEAR"]} - Brad Tab']
    assert payment_nudge_for(_line_of(brad, handicap), is_platform_admin=False) is None
    assert payment_nudge_for(None, is_platform_admin=False) is None

    with _viewer(app, brad) as client:
        pollyanna_sheet = client.get('/golf/pollyanna/').get_data(as_text=True)
        assert 'id="golf-settle-tab"' in pollyanna_sheet
        card = pollyanna_sheet.split('id="golf-settle-tab"', 1)[1].split('</section>', 1)[0]
        assert 'Settle the tab' in card and '$30' in card and 'Pollyanna Pay Sheet' in card
        assert 'Unpaid' in card and nudge['venmo_url'].replace('&', '&amp;') in card
        assert app.config['PAYMENT_ZELLE_PHONE'] in card
        # After your line, before the sheet itself (the room's order).
        assert (pollyanna_sheet.index('Your line') < pollyanna_sheet.index('id="golf-settle-tab"')
                < pollyanna_sheet.index('>The Sheet</h1>'))
        handicap_sheet = client.get('/golf/handicap/').get_data(as_text=True)
        assert 'golf-settle-tab' not in handicap_sheet and 'Settle the tab' not in handicap_sheet


def test_nudge_hides_for_admins_commissioners_and_blank_rails(app, golf_leagues):
    pollyanna = golf_leagues['pollyanna']
    owing = _two_sheets(app, golf_leagues, username='owing_member')
    commish = _member('polly_commish_tab', pollyanna, app=app, admin_in=pollyanna)
    platform = _platform_admin('platform_tab')
    _member_line = _line_of(owing, pollyanna)

    assert payment_nudge_for(_member_line, is_platform_admin=True) is None
    assert payment_nudge_for(_line_of(commish, pollyanna), is_platform_admin=False) is None

    app.config['PAYMENT_VENMO_HANDLE'] = ''
    assert payment_nudge_for(_member_line, is_platform_admin=False) is None
    app.config['PAYMENT_VENMO_HANDLE'] = 'Somebody'
    app.config['PAYMENT_ZELLE_PHONE'] = '   '
    assert payment_nudge_for(_member_line, is_platform_admin=False) is None
    with _viewer(app, owing) as client:
        assert 'golf-settle-tab' not in client.get('/golf/pollyanna/').get_data(as_text=True)
    app.config['PAYMENT_ZELLE_PHONE'] = '(212) 555-0123'

    with _viewer(app, platform) as client:
        assert 'golf-settle-tab' not in client.get('/golf/pollyanna/').get_data(as_text=True)
    with _viewer(app, commish) as client:
        assert 'golf-settle-tab' not in client.get('/golf/pollyanna/').get_data(as_text=True)
    with _viewer(app) as anonymous:
        assert 'golf-settle-tab' not in anonymous.get('/golf/pollyanna/').get_data(as_text=True)


def test_no_member_self_mark_control(app, golf_leagues):
    brad = _two_sheets(app, golf_leagues, username='no_self_mark')
    with _viewer(app, brad) as client:
        sheet = client.get('/golf/pollyanna/').get_data(as_text=True)
        assert 'id="golf-settle-tab"' in sheet
        assert 'update-payment' not in sheet and 'I paid' not in sheet
        assert 'payment-toggle' not in sheet


def test_picks_open_letter_carries_the_leagues_fee_strip(app, golf_leagues):
    """Brad's two letters: the Pollyanna one carries the strip with Pollyanna's
    fee, the Handicap one (paid) none; a commissioner's letter carries none."""
    pollyanna = golf_leagues['pollyanna']
    _two_sheets(app, golf_leagues, username='brad_letters')
    _member('polly_commish_letters', pollyanna, app=app, admin_in=pollyanna)
    app.config.update(EMAIL_ADDRESS='commish@example.com', EMAIL_PASSWORD='x',
                      SITE_URL='https://cccfantasy.com')
    event = _season_event(app, 'Tab Open', status='upcoming', deadline_in=timedelta(days=2))

    sent = []
    with patch('games.golf.services.reminders.send_platform_email',
               side_effect=lambda to, subject, plain, html: sent.append((to, plain, html)) or True):
        assert send_picks_open_email(event.id) == 3

    pollyanna_letters = [v for v in sent if v[1].startswith('Pollyanna Pay Sheet')]
    handicap_letters = [v for v in sent if v[1].startswith('Handicap Pay Sheet')]
    assert len(pollyanna_letters) == 2 and len(handicap_letters) == 1
    brad_pollyanna = next(v for v in pollyanna_letters if v[0] == 'brad_letters@example.com')
    commish_pollyanna = next(v for v in pollyanna_letters if v[0] != 'brad_letters@example.com')
    assert 'Settle the tab. Pollyanna Pay Sheet: the $30 entry is due' in brad_pollyanna[1]
    assert 'Pay on Venmo' in brad_pollyanna[2] and 'amount=30' in brad_pollyanna[2]
    assert 'Settle the tab' not in handicap_letters[0][1]
    assert 'Settle the tab' not in commish_pollyanna[1]
