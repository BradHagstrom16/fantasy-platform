"""Per-state data assembly for the home page (Spec B section 4).

Public entry point: ``build_home_context(user, state)`` dispatches to
one of four private builders based on state, returning a dict the
template consumes via ``**ctx``.
"""
from typing import Optional, Any

from flask_login import AnonymousUserMixin
from sqlalchemy.orm import joinedload

from games.worldcup.constants import (
    SEASON_YEAR, TOURNAMENT_DEADLINE_UTC, WORLDCUP_TZ,
)
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupPick, WorldCupTeam, WorldCupMatch,
    WorldCupRankSnapshot,
)
from games.worldcup.services.stage import stage_label as _stage_label
from games.worldcup.services.state import WorldCupState, now_utc
from games.worldcup.services.scoring import points_for_pick_on_match
from games.worldcup.world_cup_countries import TIERS
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
        .filter(WorldCupMatch.is_completed == False)  # noqa: E712
        .order_by(WorldCupMatch.kickoff_utc.asc())
        .limit(3)
        .all()
    )

    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)

    # court_line: "Thursday ◆ Tribute window open ◆ 2 days to kickoff"
    now = now_utc()
    now_local = now.astimezone(WORLDCUP_TZ)
    weekday = now_local.strftime('%A')
    delta = TOURNAMENT_DEADLINE_UTC - now
    days = delta.days
    hours = delta.seconds // 3600
    if days > 1:
        proximity = f'{days} days to kickoff'
    elif days == 1:
        proximity = '1 day to kickoff'
    elif hours >= 2:
        proximity = f'{hours} hours to kickoff'
    elif hours == 1:
        proximity = '1 hour to kickoff'
    elif delta.total_seconds() > 0:
        minutes = (delta.seconds // 60) % 60
        proximity = f'{minutes} minute{"s" if minutes != 1 else ""} to kickoff'
    else:
        proximity = 'kickoff imminent'
    court_line = f'{weekday} ◆ Tribute window open ◆ {proximity}'

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'picks': picks,
        'display_name': display_name,
        'deadline_utc': TOURNAMENT_DEADLINE_UTC,
        'now_utc': now,
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
    now = now_utc()

    # Leaderboard query — used for both rank and top-3
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .all()
    )
    total_count = len(all_enrollments)
    top_3 = all_enrollments[:3]

    # Single batched picks fetch for the leaderboard rows we render
    # (top 3 + the viewer if enrolled). Joined with WorldCupTeam so we
    # can derive both alive_count and the viewer's roster set without
    # round-tripping per enrollment.
    relevant_ids = [e.id for e in top_3]
    if is_enrolled and enrollment.id not in relevant_ids:
        relevant_ids.append(enrollment.id)

    picks_by_enr: dict[int, list] = {}
    if relevant_ids:
        # joinedload(WorldCupPick.team) so _alive_count below can read
        # p.team.is_eliminated without firing one query per pick.
        rows = (
            WorldCupPick.query
            .filter(WorldCupPick.enrollment_id.in_(relevant_ids))
            .options(joinedload(WorldCupPick.team))
            .all()
        )
        for p in rows:
            picks_by_enr.setdefault(p.enrollment_id, []).append(p)

    def _alive_count(eid: int) -> int:
        return sum(1 for p in picks_by_enr.get(eid, []) if not p.team.is_eliminated)

    user_team_ids: set[int] = set()
    user_picks_by_team_id: dict[int, WorldCupPick] = {}
    if is_enrolled:
        user_team_ids = {p.team_id for p in picks_by_enr.get(enrollment.id, [])}
        for p in picks_by_enr.get(enrollment.id, []):
            user_picks_by_team_id[p.team_id] = p

    dossier = None
    if is_enrolled:
        user_rank = next(
            (i + 1 for i, e in enumerate(all_enrollments) if e.id == enrollment.id),
            None,
        )

        # Week-delta + sparkline from snapshot history
        week_delta_rank = None
        week_delta_points = None
        sparkline_data = []
        recent_snapshots = list(reversed(
            WorldCupRankSnapshot.query
            .filter_by(enrollment_id=enrollment.id)
            .order_by(WorldCupRankSnapshot.captured_date.desc())
            .limit(7)
            .all()
        ))
        if recent_snapshots:
            sparkline_data = [s.rank for s in recent_snapshots]
            # Only surface the "week delta" trend once we actually have a
            # week of data — otherwise early-deploy days overstate trends
            # (e.g., "you're climbing" computed from a 2-day window).
            if len(recent_snapshots) >= 7:
                oldest = recent_snapshots[0]
                week_delta_rank = (user_rank or 0) - oldest.rank
                week_delta_points = float(enrollment.total_score) - float(oldest.total_score)

        dossier = {
            'rank': user_rank,
            'total_count': total_count,
            'total_score': enrollment.total_score,
            'alive_count': _alive_count(enrollment.id),
            'week_delta_rank': week_delta_rank,
            'week_delta_points': week_delta_points,
            'sparkline_data': sparkline_data,
        }

    # Top 3 + you row (if user is enrolled and outside top 3)
    top_3_plus_you = []
    for i, enr in enumerate(top_3, start=1):
        top_3_plus_you.append({
            'rank': i,
            'enrollment': enr,
            'is_you': is_enrolled and enr.id == enrollment.id,
            'tagline': _tagline_for(i, None, _alive_count(enr.id), is_you=False),
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
        .order_by(WorldCupMatch.kickoff_utc.desc())
        .limit(5)
        .all()
    )

    your_pick_results = []
    for match in recent_results:
        roster_match = None
        points_earned: Optional[float] = None
        if match.home_team_id in user_team_ids:
            roster_match = {'team_id': match.home_team_id, 'side': 'home'}
            points_earned = points_for_pick_on_match(
                user_picks_by_team_id[match.home_team_id], match
            )
        elif match.away_team_id in user_team_ids:
            roster_match = {'team_id': match.away_team_id, 'side': 'away'}
            points_earned = points_for_pick_on_match(
                user_picks_by_team_id[match.away_team_id], match
            )
        your_pick_results.append({
            'match': match,
            'roster_match': roster_match,
            'points_earned': points_earned,
            'is_draw': match.is_draw,
            # Display-ready label so the template doesn't fall back to
            # `match.stage|title` (which mangles 'SF' → 'Sf', 'QF' → 'Qf',
            # 'third_place' → 'Third_Place'). _stage_label is the same
            # mapping the court_line uses below — single source of truth.
            'stage_label': _stage_label(match.stage),
        })

    # Court line + stage label
    most_recent = recent_results[0] if recent_results else None
    stage_label = _stage_label(most_recent.stage if most_recent else 'group')
    weekday = now.astimezone(WORLDCUP_TZ).strftime('%A')
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


def _context_post(user, enrollment) -> dict:
    """Post-tournament state: champion banner + podium + roster recap."""
    is_enrolled = enrollment is not None

    # Champion data — match #104. Guards against malformed Final rows
    # (admin manual edit dropping a winner FK to neither side, or scores
    # left null on a row marked complete). In either case we surface the
    # champion banner without the defeat summary rather than silently
    # rendering "Defeated X 0-0" or score-flipped nonsense.
    final_match = WorldCupMatch.query.filter_by(match_number=104).first()
    champion_team = None
    champion_summary = ''
    if final_match and final_match.winner_team_id:
        champion_team = final_match.winner_team
        winner_id = final_match.winner_team_id
        winner_is_home = winner_id == final_match.home_team_id
        winner_is_away = winner_id == final_match.away_team_id
        scores_present = (
            final_match.home_score is not None
            and final_match.away_score is not None
        )
        if (winner_is_home or winner_is_away) and scores_present:
            if winner_is_home:
                loser = final_match.away_team
                winner_score = final_match.home_score
                loser_score = final_match.away_score
            else:
                loser = final_match.home_team
                winner_score = final_match.away_score
                loser_score = final_match.home_score
            suffix = ''
            if final_match.penalties:
                suffix = ' on penalties'
            elif final_match.extra_time:
                suffix = ' in extra time'
            if loser:
                champion_summary = (
                    f'Defeated {loser.display_name} {winner_score}–{loser_score}{suffix}'
                )

    # Final podium — top 3
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .all()
    )
    top_3_final = all_enrollments[:3]
    total_count = len(all_enrollments)

    your_final_rank = None
    your_climbed_n = None
    your_roster_recap = []
    if is_enrolled:
        your_final_rank = next(
            (i + 1 for i, e in enumerate(all_enrollments) if e.id == enrollment.id),
            None,
        )
        # Climbed N spots — first snapshot vs latest
        snapshots = (
            WorldCupRankSnapshot.query
            .filter_by(enrollment_id=enrollment.id)
            .order_by(WorldCupRankSnapshot.captured_date.asc())
            .all()
        )
        if snapshots and your_final_rank:
            first = snapshots[0]
            your_climbed_n = first.rank - your_final_rank  # positive = climbed

        # Roster recap — every pick with points + best_finish
        picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )
        for pick in picks:
            your_roster_recap.append({
                'pick': pick,
                'tier_name': TIERS[pick.tier]['name'],
                'best_finish': pick.team.best_finish or 'Group',
                'points': pick.multiplied_points,
                'is_champion': champion_team and pick.team_id == champion_team.id,
            })

    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'champion_team': champion_team,
        'champion_summary': champion_summary,
        'final_match': final_match,
        'top_3_final': top_3_final,
        'total_count': total_count,
        'your_final_rank': your_final_rank,
        'your_climbed_n': your_climbed_n,
        'your_roster_recap': your_roster_recap,
        'display_name': display_name,
        'joined_games': joined_games(user),
        'coming_soon_games': coming_soon_games(),
    }
