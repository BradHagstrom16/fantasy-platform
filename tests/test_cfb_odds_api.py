"""Tests for the CFB resilient Odds API client (games/cfb/services/odds_api.py).

Mirrors the World Cup sync retry hardening (PR #82): a transient network blip
on the droplet must be absorbed by retry rather than skipping a weekly run and
firing a false admin alert. All traffic is mocked at the requests boundary
(games.cfb.services.odds_api.requests.get); time.sleep is patched out so the
backoff loop doesn't actually wait.
"""
from unittest.mock import patch

import pytest
import requests


def _resp(code, payload=None):
    class _R:
        status_code = code
        headers = {'x-requests-remaining': '42'}
        def json(self): return payload if payload is not None else []
    return _R()


def test_odds_api_get_retries_transient_network_error_then_succeeds():
    """A single network blip is retried, not surfaced as a failure."""
    from games.cfb.services import odds_api

    side = [requests.exceptions.ConnectionError('Address unavailable'), _resp(200, [{'id': 'x'}])]
    with patch.object(odds_api.time, 'sleep'), \
         patch.object(odds_api.requests, 'get', side_effect=side) as g:
        resp = odds_api.odds_api_get('https://api.example/scores', params={'apiKey': 'k'})
    assert resp.status_code == 200
    assert resp.json() == [{'id': 'x'}]
    assert g.call_count == 2  # failed once, retried, succeeded


def test_odds_api_get_raises_only_after_exhausting_retries():
    """A sustained outage raises OddsApiError once retries run out."""
    from games.cfb.services import odds_api
    from games.cfb.services.odds_api import OddsApiError

    boom = requests.exceptions.ConnectionError('Address unavailable')
    with (
        patch.object(odds_api.time, 'sleep'),
        patch.object(odds_api.requests, 'get', side_effect=boom) as g,
        pytest.raises(OddsApiError),
    ):
        odds_api.odds_api_get('https://api.example/scores')
    assert odds_api.ODDS_API_MAX_RETRIES > 1
    assert g.call_count == odds_api.ODDS_API_MAX_RETRIES  # every attempt made


def test_odds_api_get_retries_5xx_then_succeeds():
    """A transient 5xx is retried (server-side blip)."""
    from games.cfb.services import odds_api

    with patch.object(odds_api.time, 'sleep'), \
         patch.object(odds_api.requests, 'get', side_effect=[_resp(503), _resp(200, [])]) as g:
        resp = odds_api.odds_api_get('https://api.example/odds')
    assert resp.status_code == 200
    assert g.call_count == 2


def test_odds_api_get_returns_4xx_immediately_without_retry():
    """A permanent client error (e.g. bad key -> 401) is returned for the caller
    to handle -- never retried, never raised. This preserves each call site's
    existing `if status != 200` branch."""
    from games.cfb.services import odds_api

    with patch.object(odds_api.time, 'sleep'), \
         patch.object(odds_api.requests, 'get', return_value=_resp(401)) as g:
        resp = odds_api.odds_api_get('https://api.example/events')
    assert resp.status_code == 401
    assert g.call_count == 1  # no retry on 4xx


def test_odds_api_get_passes_params_and_timeout():
    """The client forwards params and a bounded timeout (no naked, hang-forever GET)."""
    from games.cfb.services import odds_api

    with patch.object(odds_api.time, 'sleep'), \
         patch.object(odds_api.requests, 'get', return_value=_resp(200, [])) as g:
        odds_api.odds_api_get('https://api.example/scores', params={'apiKey': 'k', 'daysFrom': 3})
    assert g.call_args.kwargs['params'] == {'apiKey': 'k', 'daysFrom': 3}
    assert g.call_args.kwargs['timeout'] > 0
