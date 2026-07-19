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
    ENTRY_FEE,
    SEASON_YEAR,
    TOURNAMENT_DEADLINE_UTC,
    WORLDCUP_TZ,
)
from games.worldcup.models import (
    WorldCupEnrollment,
    WorldCupMatch,
    WorldCupPick,
    WorldCupRankSnapshot,
    WorldCupTeam,
)
from games.worldcup.services.elimination import eliminated_team_ids
from games.worldcup.services.ranking import compute_rank_neighbors
from games.worldcup.services.scoring import display_points_for_pick_on_match
from games.worldcup.services.stage import best_finish_label, stage_label
from games.worldcup.services.state import (
    FINAL_MATCH_NUMBER,
    WorldCupHubState,
    now_utc,
    worldcup_state,
)
from games.worldcup.services.trends import (
    compute_trend_by_enrollment,
    show_trend_column,
)
from games.worldcup.services.voice import hub_copy, rank_tier
from games.worldcup.world_cup_countries import TIERS

# best_finish display labels now live in services/stage.best_finish_label (the
# SSoT, shared with the lounge builder so the two post-state recaps can't
# diverge — audit finding B1). Plumbed through the post-state roster recap.

# Leverage Board bar floor — a pick that has banked any points keeps a
# visible minimum sliver even when one carrier dominates the roster, so the
# bar comparison doesn't collapse to "the leader, and nothing else"
# ($impeccable critique 2026-05-24 P2: USA=100% dwarfed SCO/GER into
# invisible 2-9% slivers). Dormant picks (0 points) stay at 0 — the empty
# track is the "hasn't fired yet" signal and must read as distinct from a
# tiny-but-scoring bar.
LEVERAGE_BAR_MIN_SHARE = 0.06


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

    # Editorial rules teaser — replaces the prior 4-up `.stat-block` hero-
    # metric strip (impeccable absolute-ban + DESIGN.md §6 Don't #8). The
    # multiplier system IS the interesting fact about WC scoring; surfacing
    # it as an editorial row-list converts the canvas into an activation
    # beat rather than a CMS widget. multiplier_display trims trailing .0
    # so whole numbers render as "1" / "4" / "7" and halves stay "1.5" /
    # "2.5". Numbered for accessibility (the five tiers are ordered by
    # risk/multiplier).
    tier_summary = [
        {
            'num': num,
            'name': info['name'],
            'picks': info['picks'],
            'multiplier_display': (
                f'{info["multiplier"]:.1f}'.rstrip('0').rstrip('.')
            ),
        }
        for num, info in TIERS.items()
    ]

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
        'tier_summary': tier_summary,
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

    total_enrolled = WorldCupEnrollment.query.filter_by(
        season_year=SEASON_YEAR,
    ).count()

    # Opening fixtures — replaces the pre-kickoff zeroed leaderboard with
    # content the pre-state actually has signal about. Limit to 3 so the
    # card fits the hub's editorial proportions; uses kickoff_utc to skip
    # knockout shells (kickoff_utc null until advancement).
    next_3_matches = (
        WorldCupMatch.query
        .filter(WorldCupMatch.kickoff_utc.isnot(None))
        .filter(WorldCupMatch.is_completed == False)  # noqa: E712
        .order_by(WorldCupMatch.kickoff_utc.asc(), WorldCupMatch.match_number.asc())
        .limit(3)
        .all()
    )

    _now = now_utc()
    clamped_days = max(0, (TOURNAMENT_DEADLINE_UTC - _now).days)

    # Delight beat (Hub coherence pass 2026-05): when a submitted user
    # comes back inside the final 24h window, the lead-card softens. The
    # red-rule urgency (`.is-lead`) and the primary `.btn-game` CTA both
    # demote — the user's roster is already on file, the page should
    # communicate "you're safe" rather than "act now." Unsubmitted users
    # in the same window still get the loud presentation. The 24h
    # threshold is matched to the typical "I should double-check before
    # kickoff" return-visit pattern.
    #
    # The `0 <= hours_to_deadline < 24` range guards a tiny race window:
    # worldcup_state() and now_utc() inside _context_pre call now_utc()
    # at slightly different moments, so a deadline that crossed between
    # the two calls could leave _context_pre with negative hours. The
    # explicit lower bound keeps the calm variant gated to the upcoming-
    # deadline window only.
    hours_to_deadline = (TOURNAMENT_DEADLINE_UTC - _now).total_seconds() / 3600
    is_sealed_near = (
        branch == 'submitted' and 0 <= hours_to_deadline < 24
    )

    return {
        'state': 'pre',
        'branch': branch,
        'copy': hub_copy('pre', branch),
        'enrollment': enrollment,
        'display_name': enrollment.get_display_name(),
        # deadline_utc + now_utc power the live countdown ticker on the
        # lead card. deadline_ct stays for the "Picks lock at ..." prose
        # derivation that needs a CT-local display. clamped_days is the
        # SSR fallback for the masthead numeral (precomputed so the
        # template avoids an inline `>` that trips HTMLHint).
        'deadline_utc': TOURNAMENT_DEADLINE_UTC,
        'now_utc': _now,
        'clamped_days': clamped_days,
        'deadline_ct': TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ),
        'picks_submitted': enrollment.picks_submitted,
        'user_picks': user_picks,
        'next_3_matches': next_3_matches,
        'total_enrolled': total_enrolled,
        'tournament_phase': _derive_tournament_phase(),
        'is_sealed_near': is_sealed_near,
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
        podium_label = None
        matched_picks = [
            user_picks_by_team_id[tid]
            for tid in (match.home_team_id, match.away_team_id)
            if tid in user_team_ids
        ]
        if matched_picks:
            # Display helper folds podium bonuses (champion / runner-up / 3rd)
            # into their deciding match — the base helper renders a won bronze
            # final as 0.0 (the 2026-07-19 England "NO POINTS" incident).
            scored = [
                display_points_for_pick_on_match(p, match)
                for p in matched_picks
            ]
            points_earned = sum(pts for pts, _ in scored)
            # Composite label when BOTH finalists are on the roster (the final
            # awards podium bonuses to both sides): points_earned is the sum,
            # so the label must name every contributor. Ordered by points so
            # the champion leads.
            podium_hits = sorted(
                ((pts, code) for pts, code in scored if code is not None),
                key=lambda hit: hit[0], reverse=True,
            )
            if podium_hits:
                podium_label = ' & '.join(
                    best_finish_label(code) for _, code in podium_hits
                )
        recent_matches.append({
            'match': match,
            'points_earned': points_earned,
            'podium_label': podium_label,
            'stage_label': stage_label(match.stage),
        })

    # Trend payload — gated globally
    show_trend = show_trend_column()
    delta = None
    if show_trend:
        delta_map = compute_trend_by_enrollment([enrollment.id])
        delta = delta_map.get(enrollment.id)

    # Week-over-week points delta — gated on >=7 daily snapshots so an
    # early-deploy 2-day trend doesn't overstate. Feeds the standing
    # points-line trend clause. (The rank-trend sparkline the parity
    # dossier carried moved fully to the lounge `/` per the $impeccable
    # critique 2026-05-24 "differentiate the hub" direction — the hub now
    # leads with the Leverage Board below, not a rank chart.) `.offset(6)`
    # fetches the 7th-most-recent snapshot directly; null when fewer exist.
    oldest_snapshot = (
        WorldCupRankSnapshot.query
        .filter_by(enrollment_id=enrollment.id)
        .order_by(WorldCupRankSnapshot.captured_date.desc())
        .offset(6)
        .first()
    )
    week_delta_points: float | None = None
    # Direction + magnitude precomputed here (not in the template) so the
    # Jinja avoids inline `>` comparisons that trip HTMLHint — the same
    # precompute pattern _context_pre uses for clamped_days. None direction
    # = no trend clause (no snapshots, or a flat week).
    week_delta_direction: str | None = None
    week_delta_points_abs: float | None = None
    # Only a meaningful 7-day swing if the baseline reflects real prior
    # accumulation. A zero baseline (7 days ago nothing was scored, e.g. an
    # early-tournament or fresh-deploy window) makes the delta equal the
    # current total — redundant with the points total already on the line and
    # reads as a glitch ($impeccable critique 2026-05-24). Gate the points-
    # delta on a non-zero baseline, the same spirit as the >=7-snapshot gate.
    if oldest_snapshot is not None and float(oldest_snapshot.total_score) > 0:
        week_delta_points = (
            float(enrollment.total_score) - float(oldest_snapshot.total_score)
        )
        if week_delta_points:
            week_delta_direction = 'up' if week_delta_points > 0 else 'down'
            week_delta_points_abs = abs(week_delta_points)

    # Tournament-wide "out" (group exit OR knockout loss); is_eliminated alone
    # is group-stage-only and would read every KO loser as still alive.
    eliminated_ids = eliminated_team_ids()
    alive_count = sum(1 for p in user_picks if p.team_id not in eliminated_ids)

    # Leverage Board — the WC hub's differentiated standing hero. The lounge
    # `/` keeps the rank-trend dossier as the canonical surface; the hub
    # leans into the multiplier system (the WC custom-game identity per
    # PRODUCT.md "custom games earn custom layers"). Each pick is one
    # leverage row: tier multiplier + a realized-points bar (its share of
    # the roster's top earner) + alive/dormant/out status, so "where your
    # points live" and "where upside still sleeps" read at a glance. The
    # board replaces BOTH the parity dossier and the separate 9-row roster
    # table the live state used to stack — so the lead card is the single
    # focal point (resolves the $impeccable critique 2026-05-24 P1 hierarchy
    # finding: the table out-shouted the lead).
    #
    # Ordering: carriers (any realized points) sit above dormant picks; within
    # the carriers, biggest contribution on top so the bars descend ("where
    # your points live"); the multiplier is only a tiebreak, which surfaces
    # the highest-multiplier dormant picks (the upside) at the top of the
    # dormant tail. The carrier flag is the explicit primary key so the
    # contract reads off the code; multiplier is deliberately NOT ranked
    # above points among carriers (that would break the descending-bar read).
    max_pts = max(
        (float(p.multiplied_points or 0) for p in user_picks), default=0.0,
    )
    leverage = []
    for p in sorted(
        user_picks,
        key=lambda pk: (
            float(pk.multiplied_points or 0) > 0,   # carriers above dormant
            float(pk.multiplied_points or 0),        # biggest contribution on top
            float(pk.team.multiplier),               # tiebreak: higher upside first
        ),
        reverse=True,
    ):
        pts = float(p.multiplied_points or 0)
        raw_share = (pts / max_pts) if max_pts > 0 else 0.0
        # Floor nonzero carriers to a visible minimum (see LEVERAGE_BAR_MIN_SHARE);
        # dormant picks stay at exactly 0 so the empty track keeps signalling
        # "no points yet". The bar is decorative (aria-hidden) and the points
        # value is the text equivalent, so a visual floor doesn't misreport data.
        share = max(raw_share, LEVERAGE_BAR_MIN_SHARE) if pts > 0 else 0.0
        leverage.append({
            'code': p.team.fifa_code,
            'iso': p.team.iso_code,
            'name': p.team.display_name,
            'team_id': p.team_id,
            'tier': p.team.tier,
            'mult_display': f'{float(p.team.multiplier):g}',
            'points': pts,
            'share': share,
            'status': (
                'out' if p.team_id in eliminated_ids
                else ('scoring' if pts > 0 else 'dormant')
            ),
        })

    # Dormant upside — alive, not-yet-scoring picks at the highest dormant
    # tier (tiers 4/5 = x4 and x7). Surfaced in the summary as the "where
    # upside still sleeps" beat. Only tiers >= 4 read as "upside"; a dormant
    # x1 favorite isn't a leverage story worth a callout.
    dormant = [lv for lv in leverage if lv['status'] == 'dormant']
    upside_tier = max((lv['tier'] for lv in dormant), default=0)
    dormant_upside = (
        [lv for lv in dormant if lv['tier'] == upside_tier]
        if upside_tier >= 4 else []
    )
    # scored_count = picks that have banked points. Surfaced alongside
    # alive_count so the summary can distinguish "still in" (not eliminated)
    # from "on the board" (has scored) — without it, "9 of 9 alive" next to
    # six 0.0 rows read as a contradiction ($impeccable critique 2026-05-24 r2).
    scored_count = sum(1 for lv in leverage if lv['points'] > 0)
    leverage_summary = {
        'alive_count': alive_count,
        'scored_count': scored_count,
        # alive_low precomputed (template can't do `<= 4` without a raw `<`
        # that trips HTMLHint). Drives the --wc-red survival alert.
        'alive_low': alive_count <= 4,
        'dormant_upside_codes': [lv['code'] for lv in dormant_upside],
        'dormant_upside_mult': (
            dormant_upside[0]['mult_display'] if dormant_upside else None
        ),
    }

    dossier = {
        'alive_count': alive_count,
        'week_delta_points': week_delta_points,
        'week_delta_direction': week_delta_direction,
        'week_delta_points_abs': week_delta_points_abs,
    }

    return {
        'state': 'live',
        'branch': branch,
        'copy': hub_copy('live', branch),
        'enrollment': enrollment,
        'display_name': enrollment.get_display_name(),
        'your_standing': your_standing,
        'user_picks': user_picks,
        'leverage': leverage,
        'leverage_summary': leverage_summary,
        'top_5_preview': top_5,
        'recent_matches': recent_matches,
        'stage_label': stage_label,
        'trend': {'show_column': show_trend, 'delta': delta},
        'dossier': dossier,
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
                    f'{winner_score}–{loser_score} in the Final{suffix}'
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

    # Competition rank — tied scores share a rank, the next distinct score
    # gaps by the size of the tie (CLAUDE.md "competition rank everywhere":
    # parity with routes.leaderboard() / compute_rank_neighbors).
    your_final_rank = None
    comp_rank = 0
    prev_score = None
    for i, e in enumerate(all_enrollments):
        if e.total_score != prev_score:
            comp_rank = i + 1
            prev_score = e.total_score
        if e.id == enrollment.id:
            your_final_rank = comp_rank
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
        your_roster_recap.append({
            'pick': pick,
            'tier_name': TIERS[pick.team.tier]['name'],
            'best_finish': best_finish_label(pick.team.best_finish),
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
