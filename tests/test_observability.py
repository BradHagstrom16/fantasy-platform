"""Sentry error tracking: off without a DSN, and never sends member data.

utils/observability.py::init_sentry runs from create_app. A blank SENTRY_DSN
(dev, the suite, production until the DSN is set) must leave Sentry
uninitialized; with a DSN, the privacy options are locked here.
"""
from unittest.mock import patch

from flask import Flask

from utils.observability import init_sentry, scrub_event


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
    assert kwargs['include_local_variables'] is False
    assert kwargs['before_send'] is scrub_event


def test_scrub_drops_the_query_string_and_referer_and_redacts_reset_tokens():
    event = {'request': {
        'url': 'https://cccfantasy.com/reset-password/IjEyMw.abc-DEF_1',
        'query_string': 'next=/docket/sheets&q=alice@example.com',
        'headers': {'Referer': 'https://cccfantasy.com/reset-password/IjEyMw.abc',
                    'User-Agent': 'x'},
    }}
    request = scrub_event(event, {})['request']
    assert request['url'] == 'https://cccfantasy.com/reset-password/[redacted]'
    assert 'query_string' not in request
    assert request['headers'] == {'User-Agent': 'x'}


def test_scrub_leaves_an_event_without_a_request_alone():
    event = {'exception': {'values': []}}
    assert scrub_event(event, {}) == {'exception': {'values': []}}


def test_the_testing_app_runs_without_sentry(app):
    assert app.config['SENTRY_DSN'] == ''
