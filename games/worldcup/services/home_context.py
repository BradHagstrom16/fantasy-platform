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
    WorldCupEnrollment, WorldCupMatch, WorldCupPick, WorldCupRankSnapshot,
    WorldCupTeam,
)
from games.worldcup.world_cup_countries import TIERS
from games.worldcup.services.ranking import compute_rank_neighbors
from games.worldcup.services.scoring import points_for_pick_on_match
from games.worldcup.services.stage import stage_label
from games.worldcup.services.state import (
    FINAL_MATCH_NUMBER, WorldCupHubState, worldcup_state,
)
from games.worldcup.services.trends import (
    compute_trend_by_enrollment, show_trend_column,
)
from games.worldcup.services.voice import hub_copy, rank_tier

# Display labels for `WorldCupTeam.best_finish` values (canonical keys per
# scoring.STAGE_ORDER). Plumbed through the post-state roster recap so the
# Best Finish column reads as proper UI copy ("Champion", "Round of 16")
# instead of raw codes ("champion", "R16").
_BEST_FINISH_LABELS: dict[str, str] = {
    'group': 'Group',
    'R32': 'Round of 32',
    'R16': 'Round of 16',
    'QF': 'Quarterfinals',
    'SF': 'Semifinals',
    '3rd': '3rd Place',
    'runner_up': 'Runner-up',
    'champion': 'Champion',
}


def _top_n_preview(n: int) -> list[WorldCupEnrollment]:
    """Season-scoped leaderboard slice — top-N by total_score DESC, tiebreak by id ASC.

    Used by every state builder (out shows top-3 in live/post; pre shows
    top-3; live shows top-5). Centralized so the season-scope filter and
    deterministic tiebreak don't drift between sites.
    """
    return (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .limit(n)
        .all()
    )


def _resolve_enrollment_or_die(user: Any, state_name: str) -> WorldCupEnrollment:
    """Fetch the SEASON_YEAR enrollment for `user`; assert non-null because
    worldcup_hub_state guarantees enrollment for non-'out' states.
    """
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR,
    ).first()
    assert enrollment is not None, (
        f'_context_{state_name} invoked for user {user.id} with no SEASON_YEAR enrollment'
    )
    return enrollment


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
        top_3_preview = _top_n_preview(3)

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
    enrollment = _resolve_enrollment_or_die(user, 'pre')

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

    top_3_preview = _top_n_preview(3)

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
    preview, user picks (team + multiplier + multiplied_points), recent
    matches with per-pick points-earned, trend payload (gated on
    show_trend_column), and a rank-tier-keyed voice copy variant.
    """
    enrollment = _resolve_enrollment_or_die(user, 'live')

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
    top_5 = _top_n_preview(5)

    # User's picks — _home_live.html renders team, multiplier, and
    # multiplied_points only; no per-event drill-down.
    user_picks = (
        WorldCupPick.query
        .filter_by(enrollment_id=enrollment.id)
        .join(WorldCupTeam)
        .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
        .all()
    )
    user_team_ids = {p.team_id for p in user_picks}
    user_picks_by_team_id = {p.team_id: p for p in user_picks}

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
    """Tournament-complete state — champion banner, podium, roster recap.

    Branch: 'champion' | 'top_3' | 'mid' | 'tail' (mapped from rank_tier:
    'leader' -> 'champion', 'chasing' -> 'top_3').
    """
    enrollment = _resolve_enrollment_or_die(user, 'post')

    # Champion data — match #104. Defensive guards mirror Spec B's
    # core/main/home_context._context_post:
    #   - winner_team_id may be None (admin error)
    #   - winner_team_id may FK to neither home nor away (admin error)
    #   - scores may be None even on is_completed=True (admin oversight)
    # In any of those cases, surface the banner WITHOUT a defeat summary
    # rather than rendering "Defeated X 0-0" or score-flipped nonsense.
    final_match = WorldCupMatch.query.filter_by(match_number=FINAL_MATCH_NUMBER).first()
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
                    f'Defeated {loser.display_name} '
                    f'{winner_score}–{loser_score}{suffix}'
                )

    # Final podium + total
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

    # Dense rank — tied scores share a rank (CLAUDE.md "dense rank everywhere":
    # parity with routes.leaderboard() / compute_rank_neighbors).
    your_final_rank = None
    dense_rank = 0
    prev_score = None
    for e in all_enrollments:
        if e.total_score != prev_score:
            dense_rank += 1
            prev_score = e.total_score
        if e.id == enrollment.id:
            your_final_rank = dense_rank
            break

    # Climbed-N — first snapshot vs final rank (positive = climbed, since a
    # lower rank number is better)
    snapshots = (
        WorldCupRankSnapshot.query
        .filter_by(enrollment_id=enrollment.id)
        .order_by(WorldCupRankSnapshot.captured_date.asc())
        .all()
    )
    your_climbed_n = None
    if snapshots and your_final_rank:
        # May be negative if the player dropped from their first snapshot to final.
        # Templates must branch on sign rather than always labeling "climbed".
        your_climbed_n = snapshots[0].rank - your_final_rank

    # Roster recap — every pick with points + best_finish
    picks = (
        WorldCupPick.query
        .filter_by(enrollment_id=enrollment.id)
        .join(WorldCupTeam)
        .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
        .all()
    )
    your_roster_recap = []
    for pick in picks:
        # Fall back to the raw code (not 'Group') if scoring.py grows a new
        # finish value not yet in _BEST_FINISH_LABELS — surfacing the unknown
        # code beats silently mislabeling a deep run as a group-stage exit.
        finish_code = pick.team.best_finish or 'group'
        your_roster_recap.append({
            'pick': pick,
            'tier_name': TIERS[pick.team.tier]['name'],
            'best_finish': _BEST_FINISH_LABELS.get(finish_code, finish_code),
            'points': pick.multiplied_points,
            'is_champion': (
                champion_team is not None
                and pick.team_id == champion_team.id
            ),
        })

    # Voice variant: 'leader' -> 'champion', 'chasing' -> 'top_3', else passthrough
    raw_branch = rank_tier(your_final_rank or total_count, total_count)
    branch = {
        'leader': 'champion',
        'chasing': 'top_3',
    }.get(raw_branch, raw_branch)

    return {
        'state': 'post',
        'branch': branch,
        'copy': hub_copy('post', branch),
        'enrollment': enrollment,
        'display_name': enrollment.get_display_name(),
        'champion_team': champion_team,
        'champion_summary': champion_summary,
        'final_match': final_match,
        'your_final_rank': your_final_rank,
        'your_climbed_n': your_climbed_n,
        'your_roster_recap': your_roster_recap,
        'top_3_final': top_3_final,
        'total_count': total_count,
        'tournament_phase': _derive_tournament_phase(),
    }
