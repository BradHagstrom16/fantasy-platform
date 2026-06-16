"""
CFB Survivor Pool — The Odds API Client
=======================================
One resilient entry point for every CFB call to The Odds API (scores, events,
odds). Retries transient failures (network errors, 429, 5xx) with capped
exponential backoff + jitter so a momentary blip on the droplet (a DNS hiccup
or ephemeral source-address "address unavailable"/EADDRNOTAVAIL failure)
doesn't skip a weekly run and fire a false admin alert — the next attempt
self-heals within seconds. Only a *sustained* outage raises OddsApiError.

Mirrors the Golf sync's _make_request (games/golf/services/sync.py) and the
World Cup _api_get (games/worldcup/services/sync.py, PR #82).
"""
import logging
import random
import time

import requests

logger = logging.getLogger(__name__)

# 4 attempts with capped exponential backoff worst-cases well under the CFB
# timers' run budgets.
ODDS_API_MAX_RETRIES = 4
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class OddsApiError(Exception):
    """Raised when The Odds API is unreachable after exhausting retries."""


def odds_api_get(url, params=None, timeout=30, retries=ODDS_API_MAX_RETRIES):
    """GET an Odds API endpoint with retry on transient failures.

    Returns the requests.Response so callers keep inspecting
    .status_code / .json() / .headers exactly as before. Network errors and
    429/5xx are retried; a permanent 4xx response is returned immediately for
    the caller's existing ``if status != 200`` branch to handle. Raises
    OddsApiError only when a transient failure persists across every attempt.
    """
    backoff = 1.5
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:  # transient network error: retry
            last_error = str(exc)
            logger.warning('Odds API network error on %s (attempt %s/%s): %s',
                           url, attempt, retries, exc)
        else:
            # 200, or a permanent (non-retryable) status — hand back to caller.
            if resp.status_code == 200 or resp.status_code not in _RETRYABLE_STATUS:
                return resp
            last_error = f'HTTP {resp.status_code}'
            logger.warning('Odds API returned HTTP %s on %s (attempt %s/%s)',
                           resp.status_code, url, attempt, retries)
        if attempt < retries:
            sleep_for = min(60, backoff * (2 ** (attempt - 1)))
            sleep_for *= (1 + random.uniform(-0.25, 0.25))
            time.sleep(max(0.5, sleep_for))
    raise OddsApiError(last_error or f'request to {url} failed after {retries} attempts')
