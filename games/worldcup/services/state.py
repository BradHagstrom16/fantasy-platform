"""World Cup tournament-state detection for home-page rendering.

Two functions:
- ``worldcup_state()`` returns 'pre' | 'live' | 'post' (used by the platform
  home page in core/main/routes.py — Spec B).
- ``worldcup_hub_state(user)`` returns 'out' | 'pre' | 'live' | 'post'
  (used by the WC blueprint home — Plan 4). 'out' overrides phase: anonymous
  or unenrolled-for-current-season users always see the marketing surface.

Spec B section 4a is the canonical reference for the 3-state semantics;
Plan 4 of Spec C extends it with 'out'.
"""
import os
from datetime import datetime, timezone
from typing import Literal, Optional

from games.worldcup.constants import SEASON_YEAR, TOURNAMENT_DEADLINE_UTC
from games.worldcup.models import WorldCupMatch, WorldCupEnrollment

WorldCupState = Literal['pre', 'live', 'post']
WorldCupHubState = Literal['out', 'pre', 'live', 'post']

FINAL_MATCH_NUMBER = 104  # The Final per FIFA bracket numbering


def now_utc() -> datetime:
    """Current UTC time, with a non-production test seam.

    In development or testing (ENVIRONMENT in {'development', 'testing'}),
    if WC_FAKE_NOW is set to an ISO 8601 string, return that instead of
    real time. A naive ISO string is treated as UTC. Malformed values
    are logged and ignored (falls through to real time). Production
    never reads WC_FAKE_NOW.
    """
    if os.environ.get('ENVIRONMENT') in ('development', 'testing'):
        fake = os.environ.get('WC_FAKE_NOW')
        if fake:
            try:
                dt = datetime.fromisoformat(fake.replace('Z', '+00:00'))
            except ValueError:
                import logging
                logging.getLogger(__name__).warning(
                    'WC_FAKE_NOW is not a valid ISO 8601 datetime: %r — falling back to real time',
                    fake,
                )
            else:
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def worldcup_state() -> WorldCupState:
    """Return the current World Cup phase.

    pre  — picks open, deadline not yet passed
    live — deadline passed, final (#104) not yet marked complete
    post — final match marked complete (single source of truth per Spec B D7)
    """
    if now_utc() < TOURNAMENT_DEADLINE_UTC:
        return 'pre'
    final = WorldCupMatch.query.filter_by(
        match_number=FINAL_MATCH_NUMBER, is_completed=True
    ).first()
    return 'post' if final is not None else 'live'


def worldcup_hub_state(user) -> WorldCupHubState:
    """Resolve the WC hub state for a given user. 4-state.

    'out' overrides phase: anonymous OR unenrolled-for-current-season users
    always see the marketing surface, regardless of tournament phase.
    Otherwise delegates to worldcup_state() (3-state).

    Accepts None or any object with `is_authenticated` (Flask-Login's
    AnonymousUserMixin returns False for that attribute).
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return 'out'

    enrolled = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR,
    ).first() is not None
    if not enrolled:
        return 'out'

    return worldcup_state()
