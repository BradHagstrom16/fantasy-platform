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
    WorldCupRankSnapshot,
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


def _tagline_for(rank: int, week_delta_rank: Optional[int],
                 alive_count: int, is_you: bool = False) -> Optional[str]:
    """Return a contextual one-liner for a leaderboard row, or None.

    Finite string set per Spec B D11 — server-derived from data, not LLM-style
    free-form text.
    """
    if is_you and week_delta_rank is not None:
        if week_delta_rank <= -10:
            return f"Climbed {abs(week_delta_rank)} · the Commish takes notes."
        if week_delta_rank < 0:
            return f"Climbing {abs(week_delta_rank)} spots quietly."
        if week_delta_rank == 0:
            return "Holding steady."
        if week_delta_rank < 10:
            return f"Slipped {week_delta_rank} spots. The Commish notices."
        return f"Down {week_delta_rank} · the Commish averts his eyes."
    if rank == 1:
        return "Paid tribute. Paid off."
    if rank in (2, 3) and alive_count == 9:
        return "Still warm. Still winning."
    if rank in (2, 3):
        return "Played the favorites."
    return None


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


def _context_live(user, enrollment) -> dict:
    """Live-tournament state: dossier, leaderboard preview, recent results."""
    is_enrolled = enrollment is not None

    # Leaderboard query — used for both rank and top-3
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(WorldCupEnrollment.total_score.desc())
        .all()
    )
    total_count = len(all_enrollments)

    dossier = None
    if is_enrolled:
        # Find user's rank (1-indexed)
        user_rank = next(
            (i + 1 for i, e in enumerate(all_enrollments) if e.id == enrollment.id),
            None,
        )

        # Alive count
        picks_with_teams = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .all()
        )
        alive_count = sum(1 for p in picks_with_teams if not p.team.is_eliminated)

        # Week-delta from snapshot history
        week_delta_rank = None
        week_delta_points = None
        sparkline_data = []
        recent_snapshots = (
            WorldCupRankSnapshot.query
            .filter_by(enrollment_id=enrollment.id)
            .order_by(WorldCupRankSnapshot.captured_at.asc())
            .limit(7)
            .all()
        )
        if recent_snapshots:
            sparkline_data = [s.rank for s in recent_snapshots]
            if len(recent_snapshots) >= 2:
                oldest = recent_snapshots[0]
                week_delta_rank = (user_rank or 0) - oldest.rank
                week_delta_points = float(enrollment.total_score) - float(oldest.total_score)

        dossier = {
            'rank': user_rank,
            'total_count': total_count,
            'total_score': enrollment.total_score,
            'alive_count': alive_count,
            'week_delta_rank': week_delta_rank,
            'week_delta_points': week_delta_points,
            'sparkline_data': sparkline_data,
        }

    # Top 3 + you row (if user is enrolled and outside top 3)
    top_3 = all_enrollments[:3]
    top_3_plus_you = []
    for i, enr in enumerate(top_3, start=1):
        top_3_plus_you.append({
            'rank': i,
            'enrollment': enr,
            'is_you': is_enrolled and enr.id == enrollment.id,
            'tagline': _tagline_for(i, None, 0, is_you=False),
        })
    if is_enrolled and dossier and dossier['rank'] and dossier['rank'] > 3:
        top_3_plus_you.append({
            'rank': dossier['rank'],
            'enrollment': enrollment,
            'is_you': True,
            'tagline': _tagline_for(
                dossier['rank'], dossier['week_delta_rank'],
                dossier['alive_count'], is_you=True,
            ),
            'separator_above': True,
        })

    # Recent results — last 5 completed matches
    recent_results = (
        WorldCupMatch.query
        .filter_by(is_completed=True)
        .order_by(WorldCupMatch.match_number.desc())
        .limit(5)
        .all()
    )

    # Roster intersection — for foot-row rendering
    user_team_ids = set()
    if is_enrolled:
        user_team_ids = {p.team_id for p in WorldCupPick.query.filter_by(
            enrollment_id=enrollment.id
        ).all()}

    your_pick_results = []
    for match in recent_results:
        roster_match = None
        if match.home_team_id in user_team_ids:
            roster_match = {'team_id': match.home_team_id, 'side': 'home'}
        elif match.away_team_id in user_team_ids:
            roster_match = {'team_id': match.away_team_id, 'side': 'away'}
        your_pick_results.append({'match': match, 'roster_match': roster_match})

    # Court line + stage label
    most_recent = recent_results[0] if recent_results else None
    stage_label = _stage_label(most_recent.stage if most_recent else 'group')
    weekday = datetime.now(WORLDCUP_TZ).strftime('%A')
    if dossier and dossier['week_delta_rank'] is not None:
        if dossier['week_delta_rank'] < 0:
            trend = "you're climbing"
        elif dossier['week_delta_rank'] == 0:
            trend = "you're holding"
        else:
            trend = "you're slipping"
    else:
        trend = "the Council is in session"
    court_line = f'{weekday} ◆ {stage_label} ◆ {trend}'

    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'dossier': dossier,
        'top_3_plus_you': top_3_plus_you,
        'your_pick_results': your_pick_results,
        'court_line': court_line,
        'stage_label': stage_label,
        'display_name': display_name,
        'joined_games': joined_games(user),
        'coming_soon_games': coming_soon_games(),
    }


# Stub for the post-state; filled in by Task 8.
def _context_post(user, enrollment): raise NotImplementedError


def _stage_label(stage: str) -> str:
    """Map WorldCupMatch.stage to a display label."""
    return {
        'group': 'Group Stage',
        'r32': 'Round of 32',
        'r16': 'Round of 16',
        'qf': 'Quarterfinals',
        'sf': 'Semifinals',
        'final': 'The Final',
    }.get(stage, 'Group Stage')
