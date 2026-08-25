"""Platform payment rails — ``utils/payment.py::payment_rails``.

The single builder every member-facing "Settle the Tab" nudge (CFB, Docket,
future Golf) and picks-open email reads. Rails are platform config
(``PAYMENT_VENMO_HANDLE`` / ``PAYMENT_ZELLE_PHONE``), never per-game
constants. The frozen World Cup keeps its own constants and is not covered
here (tests/test_worldcup_payment_nudge.py).
"""
import importlib
import os
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from utils.payment import payment_rails


def test_venmo_url_prefills_pay_amount_and_memo(app):
    with app.app_context():
        rails = payment_rails(25, 'CCC CFB Survivor 2026 - brad')
    parts = urlsplit(rails['venmo_url'])
    assert parts.scheme == 'https'
    assert parts.netloc == 'venmo.com'
    assert parts.path == '/' + app.config['PAYMENT_VENMO_HANDLE']
    q = parse_qs(parts.query)
    assert q['txn'] == ['pay']
    assert q['amount'] == ['25']
    assert q['note'] == ['CCC CFB Survivor 2026 - brad']


def test_memo_is_url_encoded_not_raw(app):
    with app.app_context():
        rails = payment_rails(60, "The Docket 2026 - o'brien & co")
    url = rails['venmo_url']
    assert ' ' not in url and "'" not in url and '&co' not in url
    assert parse_qs(urlsplit(url).query)['note'] == ["The Docket 2026 - o'brien & co"]


def test_payload_carries_fee_and_zelle_phone(app):
    with app.app_context():
        rails = payment_rails(25, 'memo')
    assert rails['entry_fee'] == 25
    assert rails['zelle_phone'] == app.config['PAYMENT_ZELLE_PHONE']
    assert set(rails) == {'entry_fee', 'venmo_url', 'zelle_phone'}


def test_defaults_are_the_live_rails(app):
    # Launch week needs no prod .env edit: the defaults ARE the live values
    # (already public in games/worldcup/constants.py, so no new exposure).
    assert app.config['PAYMENT_VENMO_HANDLE'] == 'Bradley-Hagstrom'
    assert app.config['PAYMENT_ZELLE_PHONE'] == '(630) 408-3424'


def test_env_overrides_both_rails():
    # The config-plumbing gotcha: a key read via current_app.config must have
    # a matching os.environ.get() line in config.py.
    import config as config_module
    with patch.dict(os.environ, {
        'PAYMENT_VENMO_HANDLE': 'Someone-Else',
        'PAYMENT_ZELLE_PHONE': '(312) 555-0100',
    }):
        cfg = importlib.reload(config_module).Config
        assert cfg.PAYMENT_VENMO_HANDLE == 'Someone-Else'
        assert cfg.PAYMENT_ZELLE_PHONE == '(312) 555-0100'
    importlib.reload(config_module)  # restore module-level defaults


def test_blank_venmo_handle_hides_every_nudge(app):
    app.config['PAYMENT_VENMO_HANDLE'] = ''
    with app.app_context():
        assert payment_rails(25, 'memo') is None


def test_blank_zelle_phone_hides_every_nudge(app):
    app.config['PAYMENT_ZELLE_PHONE'] = '   '
    with app.app_context():
        assert payment_rails(25, 'memo') is None
