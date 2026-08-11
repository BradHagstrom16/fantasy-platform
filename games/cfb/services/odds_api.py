"""
CFB Survivor Pool — Odds API client (compatibility re-export)
=============================================================
The resilient client moved to utils/odds_api.py (D5, Docket eng review
2026-08-11): one shared, sport-parameterized implementation with credit
logging built into the wrapper. This module re-exports it so historical
imports and the locked retry suite (tests/test_cfb_odds_api.py) keep pointing
at the single real implementation — no second copy may drift.

``time`` and ``requests`` are re-exported deliberately: the locked tests patch
``odds_api.time.sleep`` / ``odds_api.requests.get``, and those names must keep
resolving to the same module objects the shared implementation calls.
"""
import time

import requests

from utils.odds_api import ODDS_API_MAX_RETRIES, OddsApiError, odds_api_get

__all__ = ['ODDS_API_MAX_RETRIES', 'OddsApiError', 'odds_api_get', 'requests', 'time']
