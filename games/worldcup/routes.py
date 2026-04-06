"""
World Cup Fantasy Pool — Routes
==================================
All route handlers for the World Cup Fantasy Pool game.
Mounted at /worldcup/ via blueprint url_prefix.
"""
from datetime import datetime, timezone
from functools import wraps
from collections import defaultdict

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from extensions import db
from games.worldcup import worldcup_bp
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick
from games.worldcup.constants import (
    SEASON_YEAR, ENTRY_FEE, TOURNAMENT_DEADLINE_UTC,
    TIER_PICK_COUNTS, TOTAL_PICKS, WORLDCUP_TZ,
    KNOCKOUT_POINTS, ADVANCE_GROUP_WINNER, ADVANCE_RUNNER_UP, ADVANCE_BEST_THIRD,
)


# ============================================================================
# Decorators
# ============================================================================

def worldcup_admin_required(f):
    """Decorator requiring World Cup admin access (WorldCupEnrollment.is_admin)."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
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
    deadline_passed = datetime.now(timezone.utc) >= TOURNAMENT_DEADLINE_UTC
    total_enrolled = WorldCupEnrollment.query.filter_by(season_year=SEASON_YEAR).count()

    return render_template('worldcup/index.html',
        enrollment=enrollment,
        top_enrollments=top_enrollments,
        recent_matches=recent_matches,
        deadline_ct=deadline_ct,
        deadline_passed=deadline_passed,
        total_enrolled=total_enrolled,
    )


@worldcup_bp.route('/join', methods=['GET', 'POST'])
@login_required
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

    deadline_passed = datetime.now(timezone.utc) >= TOURNAMENT_DEADLINE_UTC
    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)

    teams = WorldCupTeam.query.order_by(WorldCupTeam.tier, WorldCupTeam.display_name).all()
    teams_by_tier = defaultdict(list)
    for team in teams:
        teams_by_tier[team.tier].append(team)

    from games.worldcup.world_cup_countries import TIERS

    existing_picks = WorldCupPick.query.filter_by(enrollment_id=enrollment.id).all()
    selected_team_ids = {p.team_id for p in existing_picks}

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
                deadline_passed=deadline_passed,
                deadline_ct=deadline_ct,
                usa_goals_guess=request.form.get('usa_goals_guess', ''),
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
        deadline_passed=deadline_passed,
        deadline_ct=deadline_ct,
        usa_goals_guess=enrollment.usa_goals_guess,
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

    return render_template('worldcup/leaderboard.html',
        ranked_enrollments=ranked,
        total_players=len(enrollments),
    )


@worldcup_bp.route('/leaderboard/<int:enrollment_id>')
def player_detail(enrollment_id):
    """One player's 9 picks with per-team scores."""
    enrollment = db.get_or_404(WorldCupEnrollment, enrollment_id)
    picks = (
        WorldCupPick.query
        .filter_by(enrollment_id=enrollment.id)
        .join(WorldCupTeam)
        .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
        .all()
    )

    from games.worldcup.world_cup_countries import TIERS

    return render_template('worldcup/player_detail.html',
        enrollment=enrollment,
        picks=picks,
        tiers=TIERS,
    )


@worldcup_bp.route('/schedule')
def schedule():
    """Match schedule with results."""
    matches = (
        WorldCupMatch.query
        .order_by(WorldCupMatch.match_number)
        .all()
    )

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
