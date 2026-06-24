"""
World Cup Fantasy Pool — Routes
==================================
All route handlers for the World Cup Fantasy Pool game.
Mounted at /worldcup/ via blueprint url_prefix.
"""
from functools import wraps
from collections import Counter, defaultdict, OrderedDict

from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload, contains_eager

from extensions import db
from models import User
from games.worldcup import worldcup_bp
from games.common import game_must_be_open
from games.worldcup.services.state import now_utc, worldcup_state, FINAL_MATCH_NUMBER
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick
from games.worldcup.constants import (
    SEASON_YEAR, ENTRY_FEE, TOURNAMENT_DEADLINE_UTC,
    TIER_PICK_COUNTS, TOTAL_PICKS, WORLDCUP_TZ,
    KNOCKOUT_POINTS, ADVANCE_GROUP_WINNER, ADVANCE_RUNNER_UP, ADVANCE_BEST_THIRD,
    ADVANCEMENT_METHODS, GROUP_WIN, GROUP_DRAW, GROUP_LOSS,
)
from games.worldcup.services.scoring import (
    process_match_result,
    apply_group_advancement,
    set_knockout_teams,
    recalculate_all_scores,
    compute_match_attribution,
    compute_team_score_events,
)
from games.worldcup.services.elimination import eliminated_team_ids
from games.worldcup.services.notifications import send_picks_confirmation
from games.worldcup.services.sync import (
    fetch_advancement_proposal, fetch_bracket_proposal,
    populatable_bracket_stages, KO_STAGES, SyncError,
)
# Platform tz helper. Re-exported as `format_ct` in the WC blueprint context
# processor (see below) so existing WC templates (`{{ format_ct(dt).strftime(...) }}`)
# keep working with the same datetime-returning contract. Platform templates
# use the `|ct` Jinja filter registered in `app.create_app` instead.
from utils.time import to_ct as _format_ct
from games.worldcup.services.stats import (
    get_country_stats,
    get_tier_stats,
    get_overview_kpis,
    get_tier_combos,
)
from games.worldcup.services.ranking import (
    compute_rank_delta, compute_rank_deltas_bulk, compute_rank_neighbors,
)
from games.worldcup.services.stage import stage_label
from games.worldcup.services.team_detail import (
    compute_team_ownership, current_user_owns_team, compute_path_to_crown,
)
from games.worldcup.services.trends import (
    show_trend_column, compute_trend_by_enrollment,
)
from games.worldcup.services.state import worldcup_hub_state
from games.worldcup.services.home_context import build_worldcup_home_context
from games.worldcup.services.payment import payment_nudge_for


# Round-robin: each group of 4 teams plays 6 matches.
GROUP_MATCH_COUNT = 6


def _group_is_complete(group_matches):
    """True when the full group round-robin is present and every match is final."""
    return (
        len(group_matches) == GROUP_MATCH_COUNT
        and all(m.is_completed for m in group_matches)
    )


# ============================================================================
# Decorators
# ============================================================================

def worldcup_admin_required(f):
    """Decorator requiring World Cup admin access.

    Two-tier check: platform admin (User.is_admin) always passes.
    Otherwise requires WorldCupEnrollment.is_admin for the current season.
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_admin:
            return f(*args, **kwargs)
        enrollment = WorldCupEnrollment.query.filter_by(
            user_id=current_user.id, season_year=SEASON_YEAR
        ).first()
        if not enrollment or not enrollment.is_admin:
            flash('World Cup admin access required.', 'error')
            return redirect(url_for('worldcup.index'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# Context Processor
# ============================================================================

def _derive_tournament_phase():
    """Derive the current tournament phase from match data."""
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


@worldcup_bp.context_processor
def inject_worldcup_globals():
    """Inject World Cup-specific variables into all World Cup templates."""
    worldcup_enrollment = None
    if current_user.is_authenticated:
        worldcup_enrollment = WorldCupEnrollment.query.filter_by(
            user_id=current_user.id, season_year=SEASON_YEAR
        ).first()

    # Compute the phase once; reused for both the public phase indicator and
    # the payment-nudge gate (no extra query — `worldcup_enrollment` is already
    # in hand). `payment_nudge` is available to every WC template but only
    # *renders* where `_settle_tab.html` is included (hub pre/live, picks,
    # leaderboard), so admin/stats/rules/schedule pages stay clean.
    tournament_phase = _derive_tournament_phase()

    return {
        'body_class': 'game-worldcup',
        'season_year': SEASON_YEAR,
        'entry_fee': ENTRY_FEE,
        'tournament_phase': tournament_phase,
        'worldcup_enrollment': worldcup_enrollment,
        'payment_nudge': payment_nudge_for(
            worldcup_enrollment, tournament_phase,
            getattr(current_user, 'is_admin', False),
        ),
        'format_ct': _format_ct,
        'stage_label': stage_label,
    }


# ============================================================================
# Before Request
# ============================================================================

@worldcup_bp.before_request
def worldcup_before_request():
    """World Cup before-request hook. Pass-through for now."""
    pass


# ============================================================================
# Routes
# ============================================================================

@worldcup_bp.route('/')
def index():
    """World Cup hub — dispatches to a state-keyed partial.

    State resolved by worldcup_hub_state(user) (4-state: out/pre/live/post).
    Each state's context is built by games.worldcup.services.home_context;
    home_shell.html includes the matching _home_<state>.html partial.
    """
    user = current_user if current_user.is_authenticated else None
    state = worldcup_hub_state(user)
    context = build_worldcup_home_context(user, state)
    context['state'] = state
    return render_template('worldcup/home_shell.html', **context)


@worldcup_bp.route('/join', methods=['GET', 'POST'])
@login_required
@game_must_be_open('worldcup')
def join():
    """Enrollment page."""
    existing = WorldCupEnrollment.query.filter_by(
        user_id=current_user.id, season_year=SEASON_YEAR
    ).first()
    if existing:
        flash('You are already enrolled in the World Cup Fantasy Pool!', 'info')
        return redirect(url_for('worldcup.index'))

    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        enrollment = WorldCupEnrollment(
            user_id=current_user.id,
            season_year=SEASON_YEAR,
            display_name=display_name or None,
        )
        db.session.add(enrollment)
        db.session.commit()
        flash('Welcome to the World Cup Fantasy Pool! Now submit your picks.', 'success')
        return redirect(url_for('worldcup.picks'))

    return render_template('worldcup/join.html')


@worldcup_bp.route('/picks', methods=['GET', 'POST'])
@login_required
def picks():
    """Pick submission (pre-deadline) / read-only view (post-deadline)."""
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=current_user.id, season_year=SEASON_YEAR
    ).first()
    if not enrollment:
        flash('Join the pool first!', 'info')
        return redirect(url_for('worldcup.join'))

    deadline_passed = now_utc() >= TOURNAMENT_DEADLINE_UTC
    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)

    teams = WorldCupTeam.query.order_by(WorldCupTeam.tier, WorldCupTeam.display_name).all()
    teams_by_tier = defaultdict(list)
    for team in teams:
        teams_by_tier[team.tier].append(team)

    from games.worldcup.world_cup_countries import TIERS

    existing_picks = WorldCupPick.query.filter_by(enrollment_id=enrollment.id).all()
    selected_team_ids = {p.team_id for p in existing_picks}
    events_by_pick = {p.id: compute_team_score_events(p.team) for p in existing_picks}
    # Mirrors the hub Leverage Board's alive signal (services/home_context) so
    # the ROSTER and HUB tabs agree on "X of 9 alive": a pick is alive unless
    # its team is out of the tournament (group exit OR knockout loss). Derived
    # via eliminated_team_ids() — is_eliminated alone is group-stage-only.
    eliminated_ids = eliminated_team_ids()
    alive_count = sum(1 for p in existing_picks if p.team_id not in eliminated_ids)

    # Determine display mode for GET requests
    edit_mode = request.args.get('edit') == '1'
    has_picks = enrollment.picks_submitted and bool(existing_picks)
    show_edit_form = not deadline_passed and (not has_picks or edit_mode)

    if request.method == 'POST':
        if deadline_passed:
            flash('The pick deadline has passed. Picks are locked.', 'error')
            return redirect(url_for('worldcup.picks'))

        selected_ids = []
        for tier in range(1, 6):
            tier_picks = request.form.getlist(f'tier_{tier}')
            selected_ids.extend(int(tid) for tid in tier_picks if tid)

        usa_goals = request.form.get('usa_goals_guess', '').strip()

        errors = []

        if not usa_goals or not usa_goals.isdigit() or int(usa_goals) < 0:
            errors.append('USA goals tiebreaker must be a non-negative integer.')
        else:
            usa_goals = int(usa_goals)

        if len(selected_ids) != TOTAL_PICKS:
            errors.append(f'You must select exactly {TOTAL_PICKS} teams (you selected {len(selected_ids)}).')

        if len(selected_ids) != len(set(selected_ids)):
            errors.append('Duplicate team selections are not allowed.')

        if not errors:
            selected_teams = WorldCupTeam.query.filter(WorldCupTeam.id.in_(selected_ids)).all()
            team_map = {t.id: t for t in selected_teams}

            if len(selected_teams) != len(selected_ids):
                errors.append('One or more selected teams are invalid.')
            else:
                tier_counts = defaultdict(int)
                for tid in selected_ids:
                    tier_counts[team_map[tid].tier] += 1

                for tier_num, required in TIER_PICK_COUNTS.items():
                    actual = tier_counts.get(tier_num, 0)
                    if actual != required:
                        tier_name = TIERS[tier_num]['name']
                        errors.append(f'{tier_name} (Tier {tier_num}): requires {required} pick(s), you selected {actual}.')

        if errors:
            for error in errors:
                flash(error, 'error')
            # Reconstruct selected_team_ids from form data for re-render
            form_ids = set()
            for tier in range(1, 6):
                for tid in request.form.getlist(f'tier_{tier}'):
                    if tid:
                        form_ids.add(int(tid))
            return render_template('worldcup/picks.html',
                enrollment=enrollment,
                teams_by_tier=dict(teams_by_tier),
                tiers=TIERS,
                selected_team_ids=form_ids,
                existing_picks=existing_picks,
                events_by_pick=events_by_pick,
                deadline_passed=deadline_passed,
                deadline_ct=deadline_ct,
                usa_goals_guess=request.form.get('usa_goals_guess', ''),
                show_edit_form=True,
                has_picks=has_picks,
                alive_count=alive_count,
                eliminated_ids=eliminated_ids,
            )

        # Save picks
        was_update = enrollment.picks_submitted  # pre-mutation: drives email subject
        WorldCupPick.query.filter_by(enrollment_id=enrollment.id).delete()

        for tid in selected_ids:
            team = team_map[tid]
            pick = WorldCupPick(
                enrollment_id=enrollment.id,
                team_id=tid,
                tier=team.tier,
            )
            db.session.add(pick)

        enrollment.picks_submitted = True
        enrollment.usa_goals_guess = usa_goals
        db.session.commit()

        # Roster receipt — fire-and-forget; send_picks_confirmation never
        # raises and a failed send must not affect the submission.
        send_picks_confirmation(enrollment, is_update=was_update)

        flash('Your picks have been submitted! You can edit them anytime before the tournament starts.', 'success')
        return redirect(url_for('worldcup.index'))

    return render_template('worldcup/picks.html',
        enrollment=enrollment,
        teams_by_tier=dict(teams_by_tier),
        tiers=TIERS,
        selected_team_ids=selected_team_ids,
        existing_picks=existing_picks,
        events_by_pick=events_by_pick,
        deadline_passed=deadline_passed,
        deadline_ct=deadline_ct,
        usa_goals_guess=enrollment.usa_goals_guess,
        show_edit_form=show_edit_form,
        has_picks=has_picks,
        alive_count=alive_count,
        eliminated_ids=eliminated_ids,
    )


def _compute_your_standing(enrollments, total_players):
    """Return Your Standing block dict for the current user, or None.

    Returns None when the viewer is anonymous or has no WorldCupEnrollment
    in SEASON_YEAR. Otherwise returns rank, of_n, rank_delta, and a voice
    caption shaped for the Tribune sidebar (P1 S1.1).
    """
    if not current_user.is_authenticated:
        return None

    enrollment = next(
        (e for e in enrollments if e.user_id == current_user.id), None
    )
    if enrollment is None:
        return None

    neighbors = compute_rank_neighbors(enrollment.id)
    rank_delta = compute_rank_delta(enrollment, window_days=1)

    return {
        'rank': neighbors['rank'],
        'of_n': total_players,
        'rank_delta': rank_delta,
        'caption': _standing_caption(
            rank=neighbors['rank'],
            total_players=total_players,
            lead_delta_up=neighbors['lead_delta_up'],
            lead_delta_down=neighbors['lead_delta_down'],
            rank_delta=rank_delta,
        ),
    }


def _standing_caption(rank, total_players, lead_delta_up, lead_delta_down, rank_delta):
    """Voice caption for the Your Position tribune block.

    Sharp, competitive, pleasure-coded. Leads with the rank-delta when there is
    one (Up N / Down N), otherwise reports the user's position relative to the
    leader and the next chaser. Dense-rank ties at the floor surface as
    "Cellar for now"; the lone enrollment surfaces as "the only one in the
    running."
    """
    if total_players == 1:
        return 'You are the only one in the running.'

    if lead_delta_up is None:  # rank 1 (or tied at top)
        if rank_delta and rank_delta > 0:
            return "You took the top. Don't look down."
        return 'Top of the table. The chase is yours to lose.'

    if lead_delta_down is None:  # no one strictly below — at the floor
        if rank_delta and rank_delta < 0:
            return f'Down {-rank_delta}. {lead_delta_up:.0f} from the top.'
        return f'Cellar for now. {lead_delta_up:.0f} from the top.'

    if rank_delta and rank_delta > 0:
        return (f'Up {rank_delta}. {lead_delta_up:.0f} from the top, '
                f'{lead_delta_down:.0f} ahead of the chase.')
    if rank_delta and rank_delta < 0:
        return (f'Down {-rank_delta}. {lead_delta_up:.0f} from the top, '
                f'{lead_delta_down:.0f} ahead of the chase.')
    return (f'Holding {rank}. {lead_delta_up:.0f} from the top, '
            f'{lead_delta_down:.0f} ahead of the chase.')


@worldcup_bp.route('/leaderboard')
def leaderboard():
    """Public leaderboard — no login required.

    Payload keys:
    - your_standing: dict | None (rank-neighbor block for authenticated+enrolled user)
    - rank_delta_by_enrollment: dict[int, int | None] (per-row rank-delta; None = "Pending")
    - trend_by_enrollment: dict[int, float | None] (per-row points-delta tooltip; empty
      until services.trends.show_trend_column() opens at >= 7 distinct snapshot days)

    The Move column always renders — its "Pending" state covers days 0-6 of the
    season. The points-delta tooltip is the only thing the snapshot-history gate
    governs in the UI.
    """
    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.usa_goals_guess.asc(),
        )
        .all()
    )

    # Competition rank: tied scores share a rank, the next distinct score
    # gaps by the size of the tie (1, 1, 3 — not dense 1, 1, 2). Matches
    # compute_rank_neighbors() so a player's rank on the board agrees with
    # /worldcup/leaderboard/<id> hero rank.
    ranked = []
    current_rank = 0
    prev_score = None
    for i, e in enumerate(enrollments):
        if e.total_score != prev_score:
            current_rank = i + 1
        ranked.append({'rank': current_rank, 'enrollment': e})
        prev_score = e.total_score

    # Mark shared ranks so the board can say "tied" out loud — competition
    # rank otherwise surfaces three players as "1" with no explanation.
    rank_counts = Counter(item['rank'] for item in ranked)
    for item in ranked:
        item['tied'] = rank_counts[item['rank']] > 1

    deadline_passed = now_utc() >= TOURNAMENT_DEADLINE_UTC
    tournament_state = worldcup_state()  # 'pre' | 'live' | 'post'
    total_players = len(enrollments)

    # Post-tournament: the top row (tiebreaker-resolved order) is the pool
    # champion; the Final's winner names the crowned country (contextual line).
    pool_champion = None
    champion_team = None
    if tournament_state == 'post' and ranked:
        pool_champion = ranked[0]['enrollment'].get_display_name()
        final_match = db.session.scalar(
            select(WorldCupMatch).filter_by(match_number=FINAL_MATCH_NUMBER)
        )
        if final_match and final_match.winner_team_id:
            champion_team = final_match.winner_team

    your_standing = _compute_your_standing(enrollments, total_players)
    enrollment_ids = [e.id for e in enrollments]
    rank_delta_by_enrollment = compute_rank_deltas_bulk(enrollment_ids, window_days=1)
    trend_by_enrollment = (
        compute_trend_by_enrollment(enrollment_ids)
        if show_trend_column() else {}
    )

    # Inline rosters (D11 privacy): only surface picks once the deadline has
    # passed — pre-deadline rosters stay sealed, matching player_detail's
    # picks_visible gate. One query, contains_eager populates pick.team from
    # the join so the template's 9-flags-per-row stays N+1-free.
    roster_by_enrollment: dict[int, list] = {}
    your_team_ids: set[int] = set()
    if deadline_passed and enrollment_ids:
        pick_rows = (
            WorldCupPick.query
            .join(WorldCupPick.team)
            .options(contains_eager(WorldCupPick.team))
            .filter(WorldCupPick.enrollment_id.in_(enrollment_ids))
            .order_by(WorldCupTeam.tier.asc(), WorldCupTeam.display_name.asc())
            .all()
        )
        grouped = defaultdict(list)
        for p in pick_rows:
            grouped[p.enrollment_id].append(p)
        roster_by_enrollment = dict(grouped)

        # The viewer's own picks drive the "shared with you" highlight on other
        # players' rows (their own row never rings — every flag would match).
        if current_user.is_authenticated:
            mine = next((e for e in enrollments if e.user_id == current_user.id), None)
            if mine:
                your_team_ids = {p.team_id for p in roster_by_enrollment.get(mine.id, [])}

    # Tournament-wide "out" (group exit OR knockout loss) — is_eliminated alone
    # is group-stage-only and under-reports KO losers. Computed once; the
    # template does set-membership only (no ORM mutation).
    eliminated_ids = eliminated_team_ids()

    return render_template('worldcup/leaderboard.html',
        ranked_enrollments=ranked,
        total_players=total_players,
        deadline_passed=deadline_passed,
        tournament_state=tournament_state,
        pool_champion=pool_champion,
        champion_team=champion_team,
        your_standing=your_standing,
        rank_delta_by_enrollment=rank_delta_by_enrollment,
        trend_by_enrollment=trend_by_enrollment,
        roster_by_enrollment=roster_by_enrollment,
        your_team_ids=your_team_ids,
        eliminated_ids=eliminated_ids,
    )


@worldcup_bp.route('/leaderboard/<int:enrollment_id>')
def player_detail(enrollment_id):
    """One player's 9 picks with per-team scores and drill-down events."""
    # Restrict to the current SEASON_YEAR pool — compute_rank_neighbors() raises
    # ValueError for stale-season enrollments, which would surface as a 500
    # after season rollover. 404 is the correct user-facing response.
    enrollment = WorldCupEnrollment.query.filter_by(
        id=enrollment_id, season_year=SEASON_YEAR
    ).first_or_404()
    deadline_passed = now_utc() >= TOURNAMENT_DEADLINE_UTC

    is_owner = (
        current_user.is_authenticated
        and current_user.id == enrollment.user_id
    )
    is_admin = current_user.is_authenticated and current_user.is_admin
    picks_visible = deadline_passed or is_owner or is_admin

    picks = []
    events_by_pick: dict[int, list] = {}
    if picks_visible:
        picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )
        events_by_pick = {p.id: compute_team_score_events(p.team) for p in picks}

    from games.worldcup.world_cup_countries import TIERS

    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)

    # Rank + lead deltas for hero stat block. Always computed (cheap query).
    neighbors = compute_rank_neighbors(enrollment.id)

    # Tournament-wide "out" for the pick rows (group exit OR knockout loss);
    # is_eliminated alone is group-stage-only. Consumed by _pick_row.html.
    eliminated_ids = eliminated_team_ids()

    return render_template('worldcup/player_detail.html',
        enrollment=enrollment,
        picks=picks,
        events_by_pick=events_by_pick,
        tiers=TIERS,
        picks_visible=picks_visible,
        deadline_passed=deadline_passed,
        deadline_ct=deadline_ct,
        neighbors=neighbors,
        eliminated_ids=eliminated_ids,
    )


@worldcup_bp.route('/team/<int:team_id>')
def team_detail(team_id):
    """Public per-team surface: fixtures, score events, ownership, path to crown.

    No @login_required — matches access policy of leaderboard/stats. Pre-deadline,
    ownership data is strictly hidden (no count, no names) per spec D11.
    """
    team = db.get_or_404(WorldCupTeam, team_id)

    matches = (
        WorldCupMatch.query
        .filter(or_(
            WorldCupMatch.home_team_id == team_id,
            WorldCupMatch.away_team_id == team_id,
        ))
        .order_by(WorldCupMatch.match_number)
        .all()
    )

    score_events = compute_team_score_events(team)

    # Per-match points map (match_id → sum of base_points for events on that match).
    # 'team.multiplier' applied at display time only; SSoT keeps base in events.
    points_by_match: dict[int, float] = {}
    for ev in score_events:
        if ev.match_id is not None:
            points_by_match[ev.match_id] = points_by_match.get(ev.match_id, 0.0) + ev.base_points

    # Non-match scoring events (advancement milestone + podium bonus) carry
    # match_id=None, so the per-match log above skips them. Surface them as their
    # own line items — otherwise the champion's +50 (the single largest event in
    # the game) is invisible and the Final reads a misleading "+0.0" (audit F2).
    # Multiply at display time to match the hero's "Scored" unit, like the match
    # log does (compute_team_score_events keeps base as the SSoT).
    bonus_events = [
        {'label': ev.label, 'points': ev.base_points * team.multiplier}
        for ev in score_events if ev.match_id is None
    ]

    # Pre-format kickoff dates in CT for the template — kickoff_utc is naive UTC
    # in the DB, so build a (match.id → CT-aware datetime) map here rather than
    # smuggling tzinfo logic into Jinja.
    from zoneinfo import ZoneInfo
    match_dates_ct: dict[int, str] = {}
    for m in matches:
        if m.kickoff_utc:
            aware = m.kickoff_utc.replace(tzinfo=ZoneInfo('UTC')).astimezone(WORLDCUP_TZ)
            match_dates_ct[m.id] = aware.strftime('%b %-d')

    deadline_passed = now_utc() >= TOURNAMENT_DEADLINE_UTC

    ownership = compute_team_ownership(team_id, deadline_passed)

    user_owns = (
        current_user.is_authenticated
        and current_user_owns_team(current_user.id, team_id)
    )

    path = compute_path_to_crown(team)

    # Picker links: post-deadline only, list of (display_name, enrollment_id) for
    # "Who Picked This". The joinedload chain eager-loads enrollment AND its
    # user so get_display_name()'s null-display-name fallback to user.username
    # doesn't trigger N+1 lazy SELECTs (CLAUDE.md stats-layer rule: never
    # traverse enrollment.picks-style relationships in public analytics paths).
    picker_links: list[tuple[str, int]] = []
    if deadline_passed:
        picks = (
            WorldCupPick.query
            .join(WorldCupEnrollment)
            .options(
                joinedload(WorldCupPick.enrollment)
                .joinedload(WorldCupEnrollment.user)
            )
            .filter(
                WorldCupPick.team_id == team_id,
                WorldCupEnrollment.season_year == SEASON_YEAR,
            )
            .all()
        )
        picker_links = sorted(
            (p.enrollment.get_display_name(), p.enrollment.id) for p in picks
        )

    return render_template('worldcup/team_detail.html',
        team=team,
        matches=matches,
        points_by_match=points_by_match,
        bonus_events=bonus_events,
        match_dates_ct=match_dates_ct,
        ownership=ownership,
        user_owns=user_owns,
        deadline_passed=deadline_passed,
        path=path,
        picker_links=picker_links,
        stage_label=stage_label,
    )


@worldcup_bp.route('/schedule')
def schedule():
    """Match schedule with results."""
    matches = (
        WorldCupMatch.query
        .order_by(WorldCupMatch.match_number)
        .all()
    )

    attribution_by_match = {
        m.id: compute_match_attribution(m) for m in matches if m.is_completed
    }

    # Roster highlight: the set of team ids the viewer has picked, so the
    # schedule can flag "your team plays here" rows. Public route, so this is
    # empty for anonymous viewers and for authenticated-but-unenrolled users.
    my_team_ids: set[int] = set()
    if current_user.is_authenticated:
        enrollment = db.session.execute(
            select(WorldCupEnrollment).filter_by(
                user_id=current_user.id, season_year=SEASON_YEAR
            )
        ).scalar_one_or_none()
        if enrollment:
            my_team_ids = set(
                db.session.execute(
                    select(WorldCupPick.team_id).filter_by(
                        enrollment_id=enrollment.id
                    )
                ).scalars().all()
            )

    # S2.2.1 — group stage rendered by matchday (Central-Time date), not by
    # group letter. Match rows are sorted by match_number which interleaves the
    # 12 groups chronologically; the previous group_letter divider therefore
    # fired up to 48 times across the group stage as a per-match label rather
    # than as a real section separator. Day grouping preserves the chronology
    # the schedule promises and lets live-state surface "today" naturally.
    today_ct_date = _format_ct(now_utc()).date()
    matchdays_group = []
    by_day = OrderedDict()
    tbd_group_matches = []
    for m in matches:
        if m.stage != 'group':
            continue
        if m.kickoff_utc is None:
            tbd_group_matches.append(m)
            continue
        ct_dt = _format_ct(m.kickoff_utc)
        day_key = ct_dt.date().isoformat()
        by_day.setdefault(day_key, {'sample_dt': ct_dt, 'matches': []})
        by_day[day_key]['matches'].append(m)
    for day_key, bucket in by_day.items():
        sample_dt = bucket['sample_dt']
        matchdays_group.append({
            'day_iso': day_key,
            'date_label': sample_dt.strftime('%a %b %-d'),
            'is_today': sample_dt.date() == today_ct_date,
            'matches': bucket['matches'],
        })
    if tbd_group_matches:
        matchdays_group.append({
            'day_iso': None,
            'date_label': 'Date TBD',
            'is_today': False,
            'matches': tbd_group_matches,
        })

    r32_matches = [m for m in matches if m.stage == 'R32']
    r16_matches = [m for m in matches if m.stage == 'R16']
    qf_matches = [m for m in matches if m.stage == 'QF']
    sf_matches = [m for m in matches if m.stage == 'SF']
    third_place = [m for m in matches if m.stage == 'third_place']
    final = [m for m in matches if m.stage == 'final']

    return render_template('worldcup/schedule.html',
        matchdays_group=matchdays_group,
        r32_matches=r32_matches,
        r16_matches=r16_matches,
        qf_matches=qf_matches,
        sf_matches=sf_matches,
        third_place=third_place,
        final=final,
        attribution_by_match=attribution_by_match,
        my_team_ids=my_team_ids,
    )


@worldcup_bp.route('/groups')
def groups():
    """Group standings — 12 groups."""
    from games.worldcup.services.state import worldcup_state
    teams = WorldCupTeam.query.order_by(WorldCupTeam.group_letter).all()
    groups_dict = defaultdict(list)
    for team in teams:
        groups_dict[team.group_letter].append(team)

    for letter in groups_dict:
        groups_dict[letter].sort(
            key=lambda t: (t.group_wins * 3 + t.group_draws, t.group_wins),
            reverse=True,
        )

    return render_template('worldcup/groups.html',
        groups=dict(sorted(groups_dict.items())),
        wc_state=worldcup_state(),
    )


@worldcup_bp.route('/rules')
def rules():
    """How it works / scoring rules."""
    from games.worldcup.world_cup_countries import TIERS, teams_by_tier

    # Single source of truth: every points value below is read from
    # constants.py, so the reference page can never drift from the engine.
    scoring_matrix = [
        ("Per match", [
            ("Win a match", GROUP_WIN),
            ("Draw a match", GROUP_DRAW),
        ]),
        ("Group advancement", [
            ("Group winner", ADVANCE_GROUP_WINNER),
            ("Runner-up", ADVANCE_RUNNER_UP),
            ("Best 3rd", ADVANCE_BEST_THIRD),
        ]),
        ("Knockouts", [
            ("Win Round of 32", KNOCKOUT_POINTS['R32']),
            ("Win Round of 16", KNOCKOUT_POINTS['R16']),
            ("Win Quarterfinal", KNOCKOUT_POINTS['QF']),
            ("Win Semifinal", KNOCKOUT_POINTS['SF']),
            ("Win 3rd-place match", KNOCKOUT_POINTS['third_place']),
            ("Runner-up (lost final)", KNOCKOUT_POINTS['runner_up']),
            ("Champion", KNOCKOUT_POINTS['champion']),
        ]),
    ]
    tier_multipliers = [TIERS[n]['multiplier'] for n in range(1, 6)]

    return render_template('worldcup/rules.html',
        tiers=TIERS,
        tier_teams=teams_by_tier(),
        tier_multipliers=tier_multipliers,
        scoring_matrix=scoring_matrix,
        group_win=GROUP_WIN,
        group_draw=GROUP_DRAW,
        group_loss=GROUP_LOSS,
        knockout_points=KNOCKOUT_POINTS,
        advance_group_winner=ADVANCE_GROUP_WINNER,
        advance_runner_up=ADVANCE_RUNNER_UP,
        advance_best_third=ADVANCE_BEST_THIRD,
    )


@worldcup_bp.route('/stats')
def stats():
    """Stats Hub — admins preview anytime; everyone else unlocks at kickoff.

    The page aggregates the whole field's picks/scores, so revealing it
    pre-deadline would leak the field's collective roster (same privacy
    concern as leaderboard/<id> and spec D11). Mirror that gate: only
    platform admins see the data before the pick deadline passes.
    """
    deadline_passed = now_utc() >= TOURNAMENT_DEADLINE_UTC
    is_admin = current_user.is_authenticated and current_user.is_admin
    stats_visible = deadline_passed or is_admin
    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)

    if not stats_visible:
        return render_template(
            'worldcup/stats.html',
            stats_visible=False,
            deadline_ct=deadline_ct,
            current_phase=_derive_tournament_phase(),
        )

    country_stats, total_players = get_country_stats(SEASON_YEAR)
    tier_stats = get_tier_stats(country_stats)
    kpis = get_overview_kpis(country_stats, total_players)
    combos = get_tier_combos(SEASON_YEAR)

    my_picks: list[str] = []
    if current_user.is_authenticated:
        enrollment = WorldCupEnrollment.query.filter_by(
            user_id=current_user.id, season_year=SEASON_YEAR
        ).first()
        if enrollment:
            picks = (
                WorldCupPick.query
                .filter_by(enrollment_id=enrollment.id)
                .join(WorldCupTeam)
                .all()
            )
            my_picks = [p.team.display_name for p in picks]

    return render_template(
        'worldcup/stats.html',
        stats_visible=True,
        country_stats=country_stats,
        tier_stats=tier_stats,
        kpis=kpis,
        combos=combos,
        my_picks=my_picks,
        current_phase=_derive_tournament_phase(),
    )


@worldcup_bp.route('/rosters')
def rosters():
    """Every roster in the pool, country names written out — the find-on-page surface.

    Exists so a member can land on one page and search "who picked Bosnia"
    by full country name; the leaderboard's roster rail is flags-only and the
    admin grid renders FIFA codes. Everything renders in the DOM (no
    accordions) so browser find-in-page works.

    Privacy mirrors stats(): the page aggregates the whole field's picks, so
    it stays sealed for everyone until the deadline passes (spec D11
    corollary — roster data hidden from all viewers pre-lock, not just
    non-owners); platform admins preview anytime.
    """
    deadline_passed = now_utc() >= TOURNAMENT_DEADLINE_UTC
    is_admin = current_user.is_authenticated and current_user.is_admin
    rosters_visible = deadline_passed or is_admin
    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)

    if not rosters_visible:
        return render_template(
            'worldcup/rosters.html',
            rosters_visible=False,
            deadline_ct=deadline_ct,
            current_phase=_derive_tournament_phase(),
        )

    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.usa_goals_guess.asc(),
        )
        .all()
    )

    # Competition rank — same idiom as leaderboard() so a player's rank here
    # agrees with the board and with compute_rank_neighbors().
    ranked = []
    current_rank = 0
    prev_score = None
    for i, e in enumerate(enrollments):
        if e.total_score != prev_score:
            current_rank = i + 1
        ranked.append({'rank': current_rank, 'enrollment': e})
        prev_score = e.total_score

    # One query for the whole field's picks; contains_eager populates
    # pick.team from the join so the 9-rows-per-player template stays
    # N+1-free (the admin all-picks grid's per-enrollment loop is the
    # anti-pattern here).
    enrollment_ids = [e.id for e in enrollments]
    picks_by_enrollment: dict[int, list] = {}
    if enrollment_ids:
        pick_rows = (
            WorldCupPick.query
            .join(WorldCupPick.team)
            .options(contains_eager(WorldCupPick.team))
            .filter(WorldCupPick.enrollment_id.in_(enrollment_ids))
            .order_by(WorldCupTeam.tier.asc(), WorldCupTeam.display_name.asc())
            .all()
        )
        grouped = defaultdict(list)
        for p in pick_rows:
            grouped[p.enrollment_id].append(p)
        picks_by_enrollment = dict(grouped)

    return render_template(
        'worldcup/rosters.html',
        rosters_visible=True,
        ranked_enrollments=ranked,
        total_players=len(enrollments),
        picks_by_enrollment=picks_by_enrollment,
        eliminated_ids=eliminated_team_ids(),
        current_phase=_derive_tournament_phase(),
    )


# ============================================================================
# Admin Routes
# ============================================================================

@worldcup_bp.route('/admin/')
@worldcup_admin_required
def admin_dashboard():
    """Admin overview: tournament status, pending actions, pool stats."""
    total_matches = WorldCupMatch.query.count()
    completed_count = WorldCupMatch.query.filter_by(is_completed=True).count()

    # Matches needing results (incomplete, with both teams assigned)
    pending_matches = (
        WorldCupMatch.query
        .filter_by(is_completed=False)
        .filter(WorldCupMatch.home_team_id.isnot(None))
        .filter(WorldCupMatch.away_team_id.isnot(None))
        .order_by(WorldCupMatch.kickoff_utc)
        .all()
    )

    completed_matches = (
        WorldCupMatch.query
        .filter_by(is_completed=True)
        .order_by(
            WorldCupMatch.updated_at.desc(),
            WorldCupMatch.match_number.desc(),
        )
        .all()
    )

    # Groups needing advancement confirmation
    groups_needing_advancement = []
    for letter in 'ABCDEFGHIJKL':
        group_matches = WorldCupMatch.query.filter_by(stage='group', group_letter=letter).all()
        all_complete = _group_is_complete(group_matches)
        if all_complete:
            group_teams = WorldCupTeam.query.filter_by(group_letter=letter).all()
            any_unset = any(t.advancement_method is None and not t.is_eliminated for t in group_teams)
            if any_unset:
                groups_needing_advancement.append(letter)

    # Knockout matches needing team assignment
    knockout_unassigned = (
        WorldCupMatch.query
        .filter(WorldCupMatch.stage != 'group')
        .filter(
            db.or_(
                WorldCupMatch.home_team_id.is_(None),
                WorldCupMatch.away_team_id.is_(None),
            )
        )
        .order_by(WorldCupMatch.match_number)
        .all()
    )

    # Pool stats
    total_enrolled = WorldCupEnrollment.query.filter_by(season_year=SEASON_YEAR).count()
    total_paid = WorldCupEnrollment.query.filter_by(season_year=SEASON_YEAR, has_paid=True).count()
    picks_submitted = WorldCupEnrollment.query.filter_by(season_year=SEASON_YEAR, picks_submitted=True).count()

    # Knockout rounds ready to bulk-populate from the API.
    populatable_stages = populatable_bracket_stages()

    return render_template('worldcup/admin/dashboard.html',
        total_matches=total_matches,
        completed_count=completed_count,
        completed_matches=completed_matches,
        pending_matches=pending_matches,
        groups_needing_advancement=groups_needing_advancement,
        knockout_unassigned=knockout_unassigned,
        populatable_stages=populatable_stages,
        total_enrolled=total_enrolled,
        total_paid=total_paid,
        picks_submitted=picks_submitted,
    )


@worldcup_bp.route('/admin/match/<int:match_id>', methods=['GET', 'POST'])
@worldcup_admin_required
def admin_match_result(match_id):
    """Enter or view a match result."""
    match = db.get_or_404(WorldCupMatch, match_id)

    if request.method == 'POST':
        action = request.form.get('action')

        # Handle clear/reset action
        if action == 'clear' and match.is_completed:
            match.is_completed = False
            match.home_score = None
            match.away_score = None
            match.winner_team_id = None
            match.is_draw = False
            match.extra_time = False
            match.penalties = False
            db.session.commit()
            recalculate_all_scores()
            flash(f'Match #{match.match_number} result cleared. Scores recalculated.', 'warning')
            return redirect(url_for('worldcup.admin_match_result', match_id=match_id))

        # Process new result
        try:
            home_score = int(request.form.get('home_score', ''))
            away_score = int(request.form.get('away_score', ''))
        except (ValueError, TypeError):
            flash('Scores must be integers.', 'error')
            return redirect(url_for('worldcup.admin_match_result', match_id=match_id))

        if home_score < 0 or away_score < 0:
            flash('Scores cannot be negative.', 'error')
            return redirect(url_for('worldcup.admin_match_result', match_id=match_id))

        winner_choice = request.form.get('winner')  # 'home', 'away', or 'draw'
        is_draw = winner_choice == 'draw'
        extra_time_flag = 'extra_time' in request.form
        penalties_flag = 'penalties' in request.form

        # Validation
        if match.stage != 'group' and is_draw:
            flash('Knockout matches cannot be draws. Select a winner.', 'error')
            return redirect(url_for('worldcup.admin_match_result', match_id=match_id))

        if not is_draw and winner_choice not in ('home', 'away'):
            flash('Select a winner or mark as draw.', 'error')
            return redirect(url_for('worldcup.admin_match_result', match_id=match_id))

        # Determine winner FIFA code
        winner_fifa_code = None
        if not is_draw:
            if winner_choice == 'home' and match.home_team:
                winner_fifa_code = match.home_team.fifa_code
            elif winner_choice == 'away' and match.away_team:
                winner_fifa_code = match.away_team.fifa_code

        result = process_match_result(
            match_id=match.id,
            home_score=home_score,
            away_score=away_score,
            winner_fifa_code=winner_fifa_code,
            is_draw=is_draw,
            extra_time=extra_time_flag,
            penalties=penalties_flag,
        )

        if 'error' in result:
            flash(result['error'], 'error')
        else:
            home_name = match.home_team.display_name if match.home_team else '?'
            away_name = match.away_team.display_name if match.away_team else '?'
            flash(
                f'Match #{match.match_number}: {home_name} {home_score}\u2013{away_score} {away_name} recorded. Scores updated.',
                'success',
            )
            return redirect(url_for('worldcup.admin_dashboard'))

    return render_template('worldcup/admin/match_result.html', match=match)


@worldcup_bp.route('/admin/advancement', methods=['GET', 'POST'])
@worldcup_admin_required
def admin_advancement():
    """Group advancement confirmation — set winner, runner-up, best 3rd."""
    if request.method == 'POST':
        group_letter = request.form.get('group_letter', '').upper()
        winner_code = request.form.get('group_winner', '').strip()
        runner_up_code = request.form.get('runner_up', '').strip()
        best_third_code = request.form.get('best_third', '').strip()

        if not group_letter or not winner_code or not runner_up_code:
            flash('Group winner and runner-up are required.', 'error')
            return redirect(url_for('worldcup.admin_advancement'))

        if winner_code == runner_up_code:
            flash('Winner and runner-up must be different teams.', 'error')
            return redirect(url_for('worldcup.admin_advancement'))

        advancements = {
            winner_code: 'group_winner',
            runner_up_code: 'runner_up',
        }
        if best_third_code and best_third_code not in (winner_code, runner_up_code):
            advancements[best_third_code] = 'best_third'

        result = apply_group_advancement(group_letter, advancements)
        flash(
            f'Group {group_letter}: {len(result["advanced"])} advanced, '
            f'{len(result["eliminated"])} eliminated. Scores recalculated.',
            'success',
        )
        return redirect(url_for('worldcup.admin_advancement'))

    # GET: build group status for all 12 groups
    groups_status = []
    for letter in 'ABCDEFGHIJKL':
        group_matches = WorldCupMatch.query.filter_by(
            stage='group', group_letter=letter,
        ).all()
        group_teams = WorldCupTeam.query.filter_by(
            group_letter=letter,
        ).order_by(
            (WorldCupTeam.group_wins * 3 + WorldCupTeam.group_draws).desc(),
            WorldCupTeam.group_wins.desc(),
        ).all()

        all_complete = _group_is_complete(group_matches)
        advancement_confirmed = all(
            t.advancement_method is not None or t.is_eliminated
            for t in group_teams
        )

        groups_status.append({
            'letter': letter,
            'teams': group_teams,
            'matches': group_matches,
            'all_complete': all_complete,
            'advancement_confirmed': advancement_confirmed,
        })

    return render_template('worldcup/admin/advancement.html',
        groups_status=groups_status,
        advancement_methods=ADVANCEMENT_METHODS,
    )


@worldcup_bp.route('/admin/advancement/proposal')
@worldcup_admin_required
def admin_advancement_proposal():
    """Return the football-data.org advancement/bracket proposal as JSON.

    Read-only. Powers the 'Load from API' pre-fill on the advancement +
    set-knockout admin pages. Confirming still goes through the existing
    apply_group_advancement() / set_knockout_teams() write paths.
    """
    from games.worldcup.services.sync import SyncError
    try:
        return jsonify(fetch_advancement_proposal())
    except SyncError as exc:
        return jsonify({'error': str(exc)}), 502


@worldcup_bp.route('/admin/recalc', methods=['POST'])
@worldcup_admin_required
def admin_recalc():
    """Trigger a full idempotent score recalculation."""
    result = recalculate_all_scores()
    flash(
        f'Recalculation complete: {result["teams_updated"]} teams, '
        f'{result["picks_updated"]} picks, {result["enrollments_updated"]} enrollments.',
        'success',
    )
    return redirect(url_for('worldcup.admin_dashboard'))


@worldcup_bp.route('/admin/picks')
@worldcup_admin_required
def admin_all_picks():
    """View all players' picks in a tier-grouped grid."""
    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(WorldCupEnrollment.total_score.desc())
        .all()
    )

    from games.worldcup.world_cup_countries import TIERS

    picks_by_enrollment: dict[int, dict[int, list]] = {}
    for enrollment in enrollments:
        picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )
        picks_by_tier: dict[int, list] = defaultdict(list)
        for pick in picks:
            picks_by_tier[pick.tier].append(pick)
        picks_by_enrollment[enrollment.id] = dict(picks_by_tier)

    return render_template('worldcup/admin/all_picks.html',
        enrollments=enrollments,
        picks_by_enrollment=picks_by_enrollment,
        tiers=TIERS,
    )


@worldcup_bp.route('/admin/set-knockout/<int:match_id>', methods=['GET', 'POST'])
@worldcup_admin_required
def admin_set_knockout(match_id):
    """Assign teams to a knockout match shell."""
    match = db.get_or_404(WorldCupMatch, match_id)

    if match.stage == 'group':
        flash('Cannot set teams for group stage matches.', 'error')
        return redirect(url_for('worldcup.admin_dashboard'))

    if request.method == 'POST':
        action = request.form.get('action')

        # Handle clear action
        if action == 'clear':
            if match.is_completed:
                flash(
                    'Clear the match result first before clearing the team assignment.',
                    'error',
                )
                return redirect(url_for('worldcup.admin_set_knockout', match_id=match_id))
            match.home_team_id = None
            match.away_team_id = None
            db.session.commit()
            flash(
                f'Match #{match.match_number}: team assignment cleared.',
                'warning',
            )
            return redirect(url_for('worldcup.admin_dashboard'))

        # Handle assign action (default)
        home_code = request.form.get('home_team', '').strip()
        away_code = request.form.get('away_team', '').strip()

        if not home_code or not away_code:
            flash('Both teams are required.', 'error')
            return redirect(url_for('worldcup.admin_set_knockout', match_id=match_id))

        if home_code == away_code:
            flash('Home and away teams must be different.', 'error')
            return redirect(url_for('worldcup.admin_set_knockout', match_id=match_id))

        result = set_knockout_teams(match.id, home_code, away_code)
        if 'error' in result:
            flash(result['error'], 'error')
        else:
            flash(f'Match #{match.match_number}: teams set to {home_code} vs {away_code}.', 'success')
            return redirect(url_for('worldcup.admin_dashboard'))

    # Only teams that survived the group stage can play a knockout match.
    # Exclude group-stage-eliminated teams so they're not assignable to a
    # bracket shell (audit F3). is_eliminated is nullable, so treat NULL
    # (pre-advancement) as not-eliminated.
    available_teams = (
        WorldCupTeam.query
        .filter(WorldCupTeam.is_eliminated.isnot(True))
        .order_by(WorldCupTeam.display_name)
        .all()
    )

    return render_template('worldcup/admin/set_knockout.html',
        match=match,
        available_teams=available_teams,
    )


@worldcup_bp.route('/admin/bracket/<target_stage>', methods=['GET', 'POST'])
@worldcup_admin_required
def admin_bracket(target_stage):
    """Bulk-populate one knockout round's shells from the API (review-then-confirm)."""
    if target_stage not in KO_STAGES:
        flash('Not a knockout stage.', 'error')
        return redirect(url_for('worldcup.admin_dashboard'))

    if request.method == 'POST':
        shell_ids = request.form.getlist('shell_id')
        home_fifas = request.form.getlist('home_fifa')
        away_fifas = request.form.getlist('away_fifa')
        assigned = skipped = failed = 0
        for sid, home, away in zip(shell_ids, home_fifas, away_fifas):
            shell = db.session.get(WorldCupMatch, int(sid)) if sid.isdigit() else None
            # Guard the client-supplied hidden fields: only assign an empty shell
            # of THIS knockout stage to two distinct teams. (set_knockout_teams
            # itself only checks existence — these mirror the single-shell route.)
            if not shell or shell.is_completed or shell.stage != target_stage:
                skipped += 1
                continue
            if not home or not away or home == away:
                skipped += 1
                continue
            res = set_knockout_teams(shell.id, home, away)
            if 'error' in res:
                failed += 1
            else:
                assigned += 1
        flash(
            f'{target_stage}: {assigned} assigned, {skipped} skipped, {failed} failed.',
            'warning' if failed else 'success',
        )
        return redirect(url_for('worldcup.admin_dashboard'))

    try:
        proposal = fetch_bracket_proposal(target_stage)
    except SyncError as exc:
        flash(f'Could not load bracket from API: {exc}', 'error')
        return redirect(url_for('worldcup.admin_dashboard'))
    return render_template('worldcup/admin/bracket.html',
        proposal=proposal, target_stage=target_stage)


@worldcup_bp.route('/admin/users')
@worldcup_admin_required
def admin_users():
    """User and enrollment management."""
    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .join(User)
        .order_by(func.lower(User.username))
        .all()
    )
    return render_template('worldcup/admin/users.html', enrollments=enrollments)


@worldcup_bp.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@worldcup_admin_required
def admin_toggle_admin(user_id):
    """Toggle World Cup admin status for an enrolled user."""
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user_id, season_year=SEASON_YEAR,
    ).first_or_404()
    enrollment.is_admin = not enrollment.is_admin
    db.session.commit()
    action = 'granted' if enrollment.is_admin else 'revoked'
    flash(f'World Cup admin {action} for {enrollment.get_display_name()}.', 'success')
    return redirect(url_for('worldcup.admin_users'))


@worldcup_bp.route('/admin/payments')
@worldcup_admin_required
def admin_payments():
    """Payment tracking dashboard."""
    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .join(User)
        .order_by(func.lower(User.username))
        .all()
    )

    paid_count = sum(1 for e in enrollments if e.has_paid)
    unpaid_count = len(enrollments) - paid_count
    total_collected = paid_count * ENTRY_FEE

    return render_template('worldcup/admin/payments.html',
        enrollments=enrollments,
        paid_count=paid_count,
        unpaid_count=unpaid_count,
        total_enrolled=len(enrollments),
        total_collected=total_collected,
    )


@worldcup_bp.route('/admin/update-payment/<int:user_id>', methods=['POST'])
@worldcup_admin_required
def admin_update_payment(user_id):
    """Toggle payment status via AJAX."""
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user_id, season_year=SEASON_YEAR,
    ).first()
    if not enrollment:
        return jsonify({'success': False, 'error': 'Enrollment not found'}), 404
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request body'}), 400
    enrollment.has_paid = data.get('has_paid', False)
    db.session.commit()
    return jsonify({'success': True, 'has_paid': enrollment.has_paid})
