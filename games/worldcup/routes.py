"""
World Cup Fantasy Pool — Routes
==================================
All route handlers for the World Cup Fantasy Pool game.
Mounted at /worldcup/ via blueprint url_prefix.
"""
from functools import wraps
from collections import defaultdict

from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db
from models import User
from games.worldcup import worldcup_bp
from games.common import game_must_be_open
from games.worldcup.services.state import now_utc
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick
from games.worldcup.constants import (
    SEASON_YEAR, ENTRY_FEE, TOURNAMENT_DEADLINE_UTC,
    TIER_PICK_COUNTS, TOTAL_PICKS, WORLDCUP_TZ,
    KNOCKOUT_POINTS, ADVANCE_GROUP_WINNER, ADVANCE_RUNNER_UP, ADVANCE_BEST_THIRD,
    ADVANCEMENT_METHODS,
)
from games.worldcup.services.scoring import (
    process_match_result,
    apply_group_advancement,
    set_knockout_teams,
    recalculate_all_scores,
    compute_match_attribution,
    compute_team_score_events,
)
from games.worldcup.services.stats import (
    get_country_stats,
    get_tier_stats,
    get_overview_kpis,
    get_tier_combos,
)
from games.worldcup.services.ranking import compute_rank_neighbors


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


def _format_ct(dt_utc):
    """Convert a UTC datetime to Central Time for display."""
    if dt_utc is None:
        return None
    from zoneinfo import ZoneInfo
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
    return dt_utc.astimezone(WORLDCUP_TZ)


@worldcup_bp.context_processor
def inject_worldcup_globals():
    """Inject World Cup-specific variables into all World Cup templates."""
    worldcup_enrollment = None
    if current_user.is_authenticated:
        worldcup_enrollment = WorldCupEnrollment.query.filter_by(
            user_id=current_user.id, season_year=SEASON_YEAR
        ).first()

    return {
        'body_class': 'game-worldcup',
        'season_year': SEASON_YEAR,
        'entry_fee': ENTRY_FEE,
        'tournament_phase': _derive_tournament_phase(),
        'worldcup_enrollment': worldcup_enrollment,
        'format_ct': _format_ct,
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
    """World Cup dashboard / landing page."""
    enrollment = None
    if current_user.is_authenticated:
        enrollment = WorldCupEnrollment.query.filter_by(
            user_id=current_user.id, season_year=SEASON_YEAR
        ).first()

    top_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(WorldCupEnrollment.total_score.desc())
        .limit(10)
        .all()
    )

    recent_matches = (
        WorldCupMatch.query
        .filter_by(is_completed=True)
        .order_by(WorldCupMatch.match_number.desc())
        .limit(5)
        .all()
    )

    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)
    deadline_passed = now_utc() >= TOURNAMENT_DEADLINE_UTC
    total_enrolled = WorldCupEnrollment.query.filter_by(season_year=SEASON_YEAR).count()

    user_picks = None
    if enrollment and enrollment.picks_submitted:
        user_picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )

    return render_template('worldcup/index.html',
        enrollment=enrollment,
        top_enrollments=top_enrollments,
        recent_matches=recent_matches,
        deadline_ct=deadline_ct,
        deadline_passed=deadline_passed,
        total_enrolled=total_enrolled,
        user_picks=user_picks,
    )


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
            )

        # Save picks
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
    )


@worldcup_bp.route('/leaderboard')
def leaderboard():
    """Public leaderboard — no login required."""
    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.usa_goals_guess.asc(),
        )
        .all()
    )

    ranked = []
    current_rank = 0
    prev_score = None
    for i, e in enumerate(enrollments):
        if e.total_score != prev_score:
            current_rank = i + 1
        ranked.append({'rank': current_rank, 'enrollment': e})
        prev_score = e.total_score

    deadline_passed = now_utc() >= TOURNAMENT_DEADLINE_UTC

    return render_template('worldcup/leaderboard.html',
        ranked_enrollments=ranked,
        total_players=len(enrollments),
        deadline_passed=deadline_passed,
    )


@worldcup_bp.route('/leaderboard/<int:enrollment_id>')
def player_detail(enrollment_id):
    """One player's 9 picks with per-team scores and drill-down events."""
    enrollment = db.get_or_404(WorldCupEnrollment, enrollment_id)
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

    return render_template('worldcup/player_detail.html',
        enrollment=enrollment,
        picks=picks,
        events_by_pick=events_by_pick,
        tiers=TIERS,
        picks_visible=picks_visible,
        deadline_passed=deadline_passed,
        deadline_ct=deadline_ct,
        neighbors=neighbors,
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

    group_matches = [m for m in matches if m.stage == 'group']
    r32_matches = [m for m in matches if m.stage == 'R32']
    r16_matches = [m for m in matches if m.stage == 'R16']
    qf_matches = [m for m in matches if m.stage == 'QF']
    sf_matches = [m for m in matches if m.stage == 'SF']
    third_place = [m for m in matches if m.stage == 'third_place']
    final = [m for m in matches if m.stage == 'final']

    return render_template('worldcup/schedule.html',
        group_matches=group_matches,
        r32_matches=r32_matches,
        r16_matches=r16_matches,
        qf_matches=qf_matches,
        sf_matches=sf_matches,
        third_place=third_place,
        final=final,
        attribution_by_match=attribution_by_match,
    )


@worldcup_bp.route('/groups')
def groups():
    """Group standings — 12 groups."""
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
    )


@worldcup_bp.route('/rules')
def rules():
    """How it works / scoring rules."""
    from games.worldcup.world_cup_countries import TIERS
    return render_template('worldcup/rules.html',
        tiers=TIERS,
        knockout_points=KNOCKOUT_POINTS,
        advance_group_winner=ADVANCE_GROUP_WINNER,
        advance_runner_up=ADVANCE_RUNNER_UP,
        advance_best_third=ADVANCE_BEST_THIRD,
    )


@worldcup_bp.route('/stats')
def stats():
    """Stats Hub — public, no login required."""
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
        country_stats=country_stats,
        tier_stats=tier_stats,
        kpis=kpis,
        combos=combos,
        my_picks=my_picks,
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
        all_complete = all(m.is_completed for m in group_matches) and len(group_matches) == 3
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

    return render_template('worldcup/admin/dashboard.html',
        total_matches=total_matches,
        completed_count=completed_count,
        completed_matches=completed_matches,
        pending_matches=pending_matches,
        groups_needing_advancement=groups_needing_advancement,
        knockout_unassigned=knockout_unassigned,
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

        all_complete = all(m.is_completed for m in group_matches) and len(group_matches) == 3
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

    available_teams = (
        WorldCupTeam.query
        .order_by(WorldCupTeam.display_name)
        .all()
    )

    return render_template('worldcup/admin/set_knockout.html',
        match=match,
        available_teams=available_teams,
    )


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


@worldcup_bp.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@worldcup_admin_required
def admin_reset_password(user_id):
    """Reset password for an enrolled user (scoped to WC enrollments)."""
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user_id, season_year=SEASON_YEAR,
    ).first_or_404()
    user = enrollment.user
    new_password = request.form.get('new_password')

    if new_password:
        user.set_password(new_password)
        db.session.commit()
        flash(f'Password reset for {user.username}.', 'success')
    else:
        flash('No password provided.', 'error')

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
