"""Sentry error tracking: off without a DSN, and never sends member data.

utils/observability.py::init_sentry runs from create_app. A blank SENTRY_DSN
(dev, the suite, production until the DSN is set) must leave Sentry
uninitialized; with a DSN, the privacy options are locked here.
"""
from unittest.mock import patch

from flask import Flask

from utils.observability import init_sentry


def _app(dsn):
    app = Flask(__name__)
    app.config['SENTRY_DSN'] = dsn
    return app


def test_blank_dsn_never_initializes_sentry():
    with patch('utils.observability.sentry_sdk.init') as init:
        init_sentry(_app(''), 'production')
    init.assert_not_called()


def test_dsn_initializes_with_the_privacy_options(monkeypatch):
    monkeypatch.setenv('ASSET_VERSION', 'abc1234')
    with patch('utils.observability.sentry_sdk.init') as init:
        init_sentry(_app('https://key@o0.ingest.example.invalid/1'), 'production')

    init.assert_called_once()
    kwargs = init.call_args.kwargs
    assert kwargs['dsn'] == 'https://key@o0.ingest.example.invalid/1'
    assert kwargs['environment'] == 'production'
    assert kwargs['release'] == 'abc1234'
    assert kwargs['send_default_pii'] is False
    assert kwargs['max_request_body_size'] == 'never'
    assert kwargs['traces_sample_rate'] == 0


def test_the_testing_app_runs_without_sentry(app):
    assert app.config['SENTRY_DSN'] == ''
