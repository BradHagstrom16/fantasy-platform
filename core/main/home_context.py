"""Per-state data assembly for the home page (Spec B section 4).

Public entry point: ``build_home_context(user, state)`` dispatches to
one of four private builders based on state, returning a dict the
template consumes via ``**ctx``.
"""
from datetime import datetime, timezone
from typing import Optional, Any

from flask_login import AnonymousUserMixin

from games.worldcup.constants import (
    SEASON_YEAR, TOURNAMENT_DEADLINE_UTC, WORLDCUP_TZ,
)
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupPick, WorldCupTeam, WorldCupMatch,
)
from games.worldcup.services.state import WorldCupState
from games.registry import (
    available_games, coming_soon_games, joined_games,
)


def build_home_context(user: Any, state: Optional[WorldCupState]) -> dict:
    """Assemble the render context for the home page in the given state.

    state=None for unauthenticated users (logged-out marketing surface).
    For authenticated users, state must be 'pre' | 'live' | 'post'.
    """
    if state is None:
        return _context_out()
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR
    ).first()
    if state == 'pre':
        return _context_pre(user, enrollment)
    if state == 'live':
        return _context_live(user, enrollment)
    return _context_post(user, enrollment)


def _context_out() -> dict:
    """Logged-out marketing surface — no user, no WC enrollment."""
    anon = AnonymousUserMixin()
    return {
        'available_games': available_games(anon),
        'coming_soon_games': coming_soon_games(),
        'total_enrolled': WorldCupEnrollment.query.filter_by(
            season_year=SEASON_YEAR
        ).count(),
    }


def _context_pre(user, enrollment) -> dict:
    """Pre-deadline state: countdown card, optional ballot, opening matches."""
    is_enrolled = enrollment is not None
    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )

    picks = []
    if is_enrolled and enrollment.picks_submitted:
        picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )

    next_3_matches = (
        WorldCupMatch.query
        .filter(WorldCupMatch.kickoff_utc.isnot(None))
        .order_by(WorldCupMatch.kickoff_utc.asc())
        .limit(3)
        .all()
    )

    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)

    # court_line: "Thursday ◆ Tribute window open ◆ 2 days to kickoff"
    now_local = datetime.now(WORLDCUP_TZ)
    weekday = now_local.strftime('%A')
    delta = TOURNAMENT_DEADLINE_UTC - datetime.now(timezone.utc)
    days = delta.days
    hours = delta.seconds // 3600
    if days > 1:
        proximity = f'{days} days to kickoff'
    elif days == 1:
        proximity = '1 day to kickoff'
    elif hours > 1:
        proximity = f'{hours} hours to kickoff'
    elif delta.total_seconds() > 0:
        minutes = (delta.seconds // 60) % 60
        proximity = f'{minutes} minutes to kickoff'
    else:
        proximity = 'kickoff imminent'
    court_line = f'{weekday} ◆ Tribute window open ◆ {proximity}'

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'picks': picks,
        'display_name': display_name,
        'deadline_utc': TOURNAMENT_DEADLINE_UTC,
        'deadline_ct': deadline_ct,
        'total_enrolled': WorldCupEnrollment.query.filter_by(
            season_year=SEASON_YEAR
        ).count(),
        'next_3_matches': next_3_matches,
        'court_line': court_line,
        'joined_games': joined_games(user),
        'coming_soon_games': coming_soon_games(),
    }


# Stubs for the other two; filled in by Tasks 7-8.
def _context_live(user, enrollment): raise NotImplementedError
def _context_post(user, enrollment): raise NotImplementedError
