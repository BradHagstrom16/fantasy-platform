"""Tests for utils/email.send_platform_email From-header handling."""
import importlib
import os
from unittest import mock

from app import create_app
from utils.email import PLATFORM_FROM_NAME, send_platform_email


def test_config_plumbs_mail_from_address_from_env():
    """config.Config reads MAIL_FROM_ADDRESS from the environment.

    Regression lock: without this, production sends from the SMTP-login address
    (ad3460001@smtp-brevo.com) instead of commish@cccfantasy.com, and Gmail drops
    the unauthenticated message. The .env had the key; config.py wasn't reading it.
    """
    import config
    with mock.patch.dict(os.environ, {'MAIL_FROM_ADDRESS': 'commish@cccfantasy.com'}):
        importlib.reload(config)
        try:
            assert config.Config.MAIL_FROM_ADDRESS == 'commish@cccfantasy.com'
        finally:
            importlib.reload(config)  # restore module under the ambient environment


def _send_and_capture(config_overrides):
    """Run send_platform_email with a mocked SMTP, return (ok, sent message)."""
    app = create_app('testing')
    app.config.update(config_overrides)
    captured = {}
    with app.app_context(), mock.patch('utils.email.smtplib.SMTP') as MockSMTP:
        server = MockSMTP.return_value.__enter__.return_value
        server.send_message.side_effect = lambda msg: captured.update(msg=msg)
        ok = send_platform_email('player@example.com', 'Subject', 'plain body')
    return ok, captured.get('msg')


def test_from_header_uses_mail_from_address_when_set():
    """When MAIL_FROM_ADDRESS is set, it drives the From header (not the SMTP login)."""
    ok, msg = _send_and_capture({
        'EMAIL_ADDRESS': 'brevo-login@example.com',
        'EMAIL_PASSWORD': 'smtp-key',
        'MAIL_FROM_ADDRESS': 'commish@cccfantasy.com',
    })
    assert ok is True
    assert msg['From'] == f'{PLATFORM_FROM_NAME} <commish@cccfantasy.com>'


def test_from_header_falls_back_to_email_address_when_unset():
    """With MAIL_FROM_ADDRESS unset, the From header falls back to EMAIL_ADDRESS."""
    ok, msg = _send_and_capture({
        'EMAIL_ADDRESS': 'fallback@example.com',
        'EMAIL_PASSWORD': 'pw',
        'MAIL_FROM_ADDRESS': None,
    })
    assert ok is True
    assert msg['From'] == f'{PLATFORM_FROM_NAME} <fallback@example.com>'


def test_send_returns_false_when_credentials_missing():
    """Missing SMTP credentials short-circuit to False without building a message."""
    ok, msg = _send_and_capture({
        'EMAIL_ADDRESS': '',
        'EMAIL_PASSWORD': '',
        'MAIL_FROM_ADDRESS': 'commish@cccfantasy.com',
    })
    assert ok is False
    assert msg is None
