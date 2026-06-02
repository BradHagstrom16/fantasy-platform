"""
World Cup Fantasy Pool — football-data.org Sync Service
=======================================================
Pulls final match results (auto-applied) and group-advancement / knockout-bracket
data (admin-confirmed) from football-data.org (free tier). Match data stays the
single source of truth; this service only feeds the existing scoring engine and
pre-fills the existing admin forms. It never recomputes scores.

Endpoints used (one request each):
    GET /v4/competitions/WC/matches    (all 104 fixtures + scores)
    GET /v4/competitions/WC/standings  (12 group tables)
Auth: header X-Auth-Token. Free tier: 10 req/min, no daily cap.
"""
import logging

import requests
from flask import current_app

from extensions import db
from games.worldcup.models import WorldCupTeam, WorldCupMatch
from games.worldcup.services.scoring import process_match_result

logger = logging.getLogger(__name__)

API_BASE_URL = 'https://api.football-data.org/v4'
COMPETITION_CODE = 'WC'

# football-data.org stage string -> our WorldCupMatch.stage code.
STAGE_MAP = {
    'GROUP_STAGE': 'group',
    'LAST_32': 'R32',
    'LAST_16': 'R16',
    'QUARTER_FINALS': 'QF',
    'SEMI_FINALS': 'SF',
    'THIRD_PLACE': 'third_place',
    'FINAL': 'final',
}

# A fixture is final (apply it) only in one of these statuses.
FINISHED_STATUSES = {'FINISHED'}

# football-data.org 3-letter team code (tla) -> our fifa_code, ONLY where they
# differ. Most align (MEX==MEX). Fill in during the `link` verification run.
TEAM_TLA_OVERRIDES: dict[str, str] = {}


class SyncError(Exception):
    """Raised when the football-data.org API is unreachable or misconfigured."""


def _api_get(path: str, params: dict | None = None) -> dict:
    """GET a football-data.org endpoint, returning parsed JSON. Raises SyncError."""
    api_key = current_app.config.get('FOOTBALL_DATA_API_KEY', '')
    if not api_key:
        raise SyncError('FOOTBALL_DATA_API_KEY is not configured')
    url = f'{API_BASE_URL}/{path}'
    try:
        resp = requests.get(
            url, headers={'X-Auth-Token': api_key}, params=params, timeout=30,
        )
    except Exception as exc:  # network error
        raise SyncError(f'request to {path} failed: {exc}') from exc
    if resp.status_code != 200:
        raise SyncError(f'{path} returned HTTP {resp.status_code}')
    # Defensive rate-limit logging (free tier = 10/min); back off if near zero.
    remaining = resp.headers.get('X-Requests-Available-Minute')
    if remaining is not None and remaining.isdigit() and int(remaining) <= 1:
        logger.warning('football-data.org minute budget nearly exhausted (%s left)', remaining)
    return resp.json()


def _fifa_for_tla(tla: str | None) -> str | None:
    """Map a football-data.org tla to our fifa_code (override map, else identity)."""
    if not tla:
        return None
    return TEAM_TLA_OVERRIDES.get(tla, tla)
