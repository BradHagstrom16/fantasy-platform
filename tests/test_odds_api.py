"""Tests for the shared platform Odds API client (utils/odds_api.py).

D5 (Docket eng review): the resilient client is lifted out of the CFB blueprint
into a shared, sport-parameterized module, and credit logging
(x-requests-remaining) lives INSIDE the wrapper so every caller — CFB today,
Docket's two-sport import next — reports burn on every call with no
per-call-site discipline required. Retry semantics are locked by the existing
CFB suite (tests/test_cfb_odds_api.py), which exercises the same implementation
through the compatibility re-export.
"""
import logging
from unittest.mock import patch


def _resp(code=200, payload=None, headers=None):
    class _R:
        status_code = code

        def json(self):
            return payload if payload is not None else []

    r = _R()
    r.headers = headers if headers is not None else {
        'x-requests-remaining': '447',
        'x-requests-used': '53',
    }
    return r


def test_wrapper_logs_credits_remaining_on_success(caplog):
    """A 200 response logs the API's x-requests-remaining header at INFO."""
    from utils import odds_api

    with patch.object(odds_api.time, 'sleep'), \
         patch.object(odds_api.requests, 'get', return_value=_resp(200)), \
         caplog.at_level(logging.INFO, logger='utils.odds_api'):
        odds_api.odds_api_get('https://api.example/odds', params={'apiKey': 'k'})
    credit_lines = [r for r in caplog.records if '447' in r.getMessage()]
    assert credit_lines, 'wrapper must log x-requests-remaining on every call'


def test_wrapper_logs_credits_on_permanent_4xx(caplog):
    """Credit logging covers EVERY returned response, including permanent 4xx
    (a 401 from a bad key still spends the caller's attention budget)."""
    from utils import odds_api

    with patch.object(odds_api.time, 'sleep'), \
         patch.object(odds_api.requests, 'get', return_value=_resp(401)), \
         caplog.at_level(logging.INFO, logger='utils.odds_api'):
        resp = odds_api.odds_api_get('https://api.example/events')
    assert resp.status_code == 401
    assert any('447' in r.getMessage() for r in caplog.records)


def test_wrapper_logs_unknown_when_header_missing(caplog):
    """A response without credit headers still logs — 'unknown', never a crash."""
    from utils import odds_api

    with patch.object(odds_api.time, 'sleep'), \
         patch.object(odds_api.requests, 'get', return_value=_resp(200, headers={})), \
         caplog.at_level(logging.INFO, logger='utils.odds_api'):
        odds_api.odds_api_get('https://api.example/scores')
    assert any('unknown' in r.getMessage() for r in caplog.records)


def test_sport_base_url_parameterizes_sport():
    """The client layer carries no hardcoded sport: any sport key builds its
    own v4 base URL (Docket needs ncaaf + nfl side by side)."""
    from utils.odds_api import sport_base_url

    assert sport_base_url('americanfootball_nfl') == \
        'https://api.the-odds-api.com/v4/sports/americanfootball_nfl'
    assert sport_base_url('americanfootball_ncaaf') == \
        'https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf'


def test_cfb_base_url_derives_from_shared_client():
    """Zero-behavior-change lock: CFB's API_BASE_URL is the shared builder
    applied to CFB's own SPORT_KEY — same string as before the lift."""
    from games.cfb.constants import API_BASE_URL, SPORT_KEY
    from utils.odds_api import sport_base_url

    assert SPORT_KEY == 'americanfootball_ncaaf'
    assert sport_base_url(SPORT_KEY) == API_BASE_URL


def test_cfb_shim_reexports_shared_client():
    """games/cfb/services/odds_api.py stays as a compatibility re-export so the
    locked CFB retry suite and historical imports keep pointing at the one real
    implementation — no second copy may drift."""
    from games.cfb.services import odds_api as cfb_shim
    from utils import odds_api as shared

    assert cfb_shim.odds_api_get is shared.odds_api_get
    assert cfb_shim.OddsApiError is shared.OddsApiError
    assert cfb_shim.ODDS_API_MAX_RETRIES is shared.ODDS_API_MAX_RETRIES
