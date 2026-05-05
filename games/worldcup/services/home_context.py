"""Per-state data assembly for the WC blueprint home (Spec C Plan 4).

Mirrors core/main/home_context for the platform home (Spec B). The WC home
adds a 4th state — 'out' — for anonymous-or-unenrolled visitors. State is
resolved by games.worldcup.services.state.worldcup_hub_state(user) and
passed in.

Public entry point: build_worldcup_home_context(user, state) — dispatches
to one of four private builders. Each builder returns a flat dict
consumed by the matching _home_<state>.html partial.

Each builder's return-shape contract is documented at the function level.
"""
from typing import Any

from extensions import db
from games.worldcup.constants import (
    SEASON_YEAR, ENTRY_FEE, TOURNAMENT_DEADLINE_UTC, WORLDCUP_TZ,
)
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupMatch, WorldCupPick, WorldCupTeam,
)
from games.worldcup.services.ranking import compute_rank_neighbors
from games.worldcup.services.scoring import (
    compute_team_score_events, points_for_pick_on_match,
)
from games.worldcup.services.stage import stage_label
from games.worldcup.services.state import WorldCupHubState, worldcup_state
from games.worldcup.services.trends import (
    compute_trend_by_enrollment, show_trend_column,
)
from games.worldcup.services.voice import hub_copy, rank_tier


def _derive_tournament_phase() -> str:
    """Match-data derived tournament phase. Returns one of:
    'pre_tournament' | 'group_stage' | 'knockout' | 'completed'.

    Mirrors games.worldcup.routes._derive_tournament_phase exactly.
    Duplicated here (rather than imported) to avoid a circular import
    between the routes module and a service it depends on. CLAUDE.md
    "phase != stage" — distinct value space from stage_label.
    """
    completed_group = db.session.query(WorldCupMatch).filter_by(
        stage='group', is_completed=True
    ).count()
    completed_knockout = db.session.query(WorldCupMatch).filter(
        WorldCupMatch.stage != 'group',
        WorldCupMatch.is_completed == True  # noqa: E712
    ).count()
    final_completed = db.session.query(WorldCupMatch).filter_by(
        stage='final', is_completed=True
    ).count()

    if final_completed > 0:
        return 'completed'
    if completed_knockout > 0:
        return 'knockout'
    if completed_group > 0:
        return 'group_stage'
    return 'pre_tournament'


def build_worldcup_home_context(user: Any, state: WorldCupHubState) -> dict:
    """Dispatch to the per-state context builder.

    Raises ValueError on unknown state — fail loud per CLAUDE.md.
    """
    if state == 'out':
        return _context_out(user)
    if state == 'pre':
        return _context_pre(user)
    if state == 'live':
        return _context_live(user)
    if state == 'post':
        return _context_post(user)
    raise ValueError(f'unknown worldcup hub state: {state!r}')


# =====================================================================
# Per-state builders
# =====================================================================

def _context_out(user: Any) -> dict:
    """Marketing surface for anonymous + authenticated-unenrolled users.

    cta_state branches on (auth, tournament phase):
    - anon                       -> 'guest'
    - authenticated, pre kickoff -> 'unenrolled_pre'
    - authenticated, live        -> 'unenrolled_live'
    - authenticated, post        -> 'unenrolled_post'
    """
    is_authenticated = (
        user is not None
        and getattr(user, 'is_authenticated', False)
    )
    display_name = (
        user.get_display_name() if is_authenticated else None
    )

    if not is_authenticated:
        cta_state = 'guest'
    else:
        # 'out' state is set; phase still relevant for cta variant
        phase_state = worldcup_state()  # 'pre' | 'live' | 'post'
        cta_state = {
            'pre': 'unenrolled_pre',
            'live': 'unenrolled_live',
            'post': 'unenrolled_post',
        }[phase_state]

    total_enrolled = WorldCupEnrollment.query.filter_by(
        season_year=SEASON_YEAR,
    ).count()

    top_3_preview = []
    if cta_state in ('unenrolled_live', 'unenrolled_post'):
        top_3_preview = (
            WorldCupEnrollment.query
            .filter_by(season_year=SEASON_YEAR)
            .order_by(
                WorldCupEnrollment.total_score.desc(),
                WorldCupEnrollment.id.asc(),
            )
            .limit(3)
            .all()
        )

    return {
        'state': 'out',
        'cta_state': cta_state,
        'copy': hub_copy('out', cta_state),
        'tournament_phase': _derive_tournament_phase(),
        'entry_fee': ENTRY_FEE,
        'total_enrolled': total_enrolled,
        'deadline_ct': TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ),
        'is_authenticated': is_authenticated,
        'display_name': display_name,
        'top_3_preview': top_3_preview,
    }


def _context_pre(user: Any) -> dict:
    """Pre-deadline state for enrolled users.

    Branch: 'submitted' | 'unsubmitted' (drives voice copy variant).
    """
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR,
    ).first()
    # _context_pre is only invoked when state == 'pre' which requires the
    # user to be enrolled (worldcup_hub_state guarantees this). Asserting
    # rather than redirecting — fail loud if invariant violated.
    assert enrollment is not None, (
        f'_context_pre invoked for user {user.id} with no SEASON_YEAR enrollment'
    )

    branch = 'submitted' if enrollment.picks_submitted else 'unsubmitted'

    user_picks = []
    if enrollment.picks_submitted:
        user_picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )

    top_3_preview = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .limit(3)
        .all()
    )

    total_enrolled = WorldCupEnrollment.query.filter_by(
        season_year=SEASON_YEAR,
    ).count()

    return {
        'state': 'pre',
        'branch': branch,
        'copy': hub_copy('pre', branch),
        'enrollment': enrollment,
        'display_name': enrollment.get_display_name(),
        'deadline_ct': TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ),
        'picks_submitted': enrollment.picks_submitted,
        'user_picks': user_picks,
        'top_3_preview': top_3_preview,
        'total_enrolled': total_enrolled,
        'tournament_phase': _derive_tournament_phase(),
    }


def _context_live(user: Any) -> dict:
    """Live-tournament state — full dossier for an enrolled user.

    Branch: 'leader' | 'chasing' | 'mid' | 'tail' (drives voice copy variant).

    Combines: rank/lead deltas via compute_rank_neighbors, top-5 leaderboard
    preview, user picks with transient score_events, recent matches with
    per-pick points-earned, trend payload (gated on show_trend_column),
    and a rank-tier-keyed voice copy variant.
    """
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR,
    ).first()
    # _context_live is only invoked when state == 'live' which requires the
    # user to be enrolled (worldcup_hub_state guarantees this). Asserting
    # rather than redirecting — fail loud if invariant violated.
    assert enrollment is not None, (
        f'_context_live invoked for user {user.id} with no SEASON_YEAR enrollment'
    )

    # Rank/standing — reuses Plan 2's helper (parity with leaderboard).
    neighbors = compute_rank_neighbors(enrollment.id)
    total_enrolled = WorldCupEnrollment.query.filter_by(
        season_year=SEASON_YEAR,
    ).count()
    your_standing = {
        'rank': neighbors['rank'],
        'total': neighbors['points'],
        'of_n': total_enrolled,
        'lead_delta_up': neighbors['lead_delta_up'],
        'lead_delta_down': neighbors['lead_delta_down'],
    }

    # Voice tier
    branch = rank_tier(neighbors['rank'], total_enrolled)

    # Top-5 preview
    top_5 = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .limit(5)
        .all()
    )

    # User's picks with transient score_events
    user_picks = (
        WorldCupPick.query
        .filter_by(enrollment_id=enrollment.id)
        .join(WorldCupTeam)
        .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
        .all()
    )
    user_team_ids = {p.team_id for p in user_picks}
    user_picks_by_team_id = {p.team_id: p for p in user_picks}
    for pick in user_picks:
        # Transient attr — never persisted (CLAUDE.md ORM safety rule).
        # ~18 queries per render (2 per pick × 9 picks). Acceptable at current
        # pool size (~25 enrollments). Revisit with a batched
        # compute_team_score_events_for_teams(...) helper if the pool grows.
        pick.score_events = compute_team_score_events(pick.team)

    # Recent matches with per-match points-earned for user's roster
    recent = (
        WorldCupMatch.query
        .filter_by(is_completed=True)
        .order_by(WorldCupMatch.kickoff_utc.desc())
        .limit(5)
        .all()
    )
    recent_matches = []
    for match in recent:
        points_earned = None
        matched_picks = [
            user_picks_by_team_id[tid]
            for tid in (match.home_team_id, match.away_team_id)
            if tid in user_team_ids
        ]
        if matched_picks:
            points_earned = sum(
                points_for_pick_on_match(p, match) for p in matched_picks
            )
        recent_matches.append({
            'match': match,
            'points_earned': points_earned,
            'stage_label': stage_label(match.stage),
        })

    # Trend payload — gated globally
    show_trend = show_trend_column()
    delta = None
    if show_trend:
        delta_map = compute_trend_by_enrollment([enrollment.id])
        delta = delta_map.get(enrollment.id)

    return {
        'state': 'live',
        'branch': branch,
        'copy': hub_copy('live', branch),
        'enrollment': enrollment,
        'display_name': enrollment.get_display_name(),
        'your_standing': your_standing,
        'user_picks': user_picks,
        'top_5_preview': top_5,
        'recent_matches': recent_matches,
        'stage_label': stage_label,
        'trend': {'show_column': show_trend, 'delta': delta},
        'tournament_phase': _derive_tournament_phase(),
    }


def _context_post(user: Any) -> dict:
    """Stub — replaced in Task 9."""
    return {'_marker_post': True}
