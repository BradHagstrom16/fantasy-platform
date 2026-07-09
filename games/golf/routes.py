"""
Golf Pick 'Em — Routes
========================
All route handlers for the Golf Pick 'Em game.
Mounted at /golf/ via blueprint url_prefix.
"""
import logging
from datetime import UTC, datetime
from functools import wraps

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload

from extensions import db
from games.common import enrollment_required, game_must_be_open
from games.golf import golf_bp
from games.golf.models import (
    PENALTY_PER_INCIDENT,
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfSeasonPlayerUsage,
    GolfTournament,
    GolfTournamentField,
    GolfTournamentResult,
)
from games.golf.utils import (
    calculate_projected_earnings,
    format_score_to_par,
    get_current_time,
)
from models.user import User

logger = logging.getLogger(__name__)


# ============================================================================
# Decorators
# ============================================================================

def golf_admin_required(f):
    """Decorator requiring Golf admin access.

    Two-tier check: platform admin (User.is_admin) always passes.
    Otherwise requires GolfEnrollment.is_admin for the current season.
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_admin:
            return f(*args, **kwargs)
        season_year = current_app.config['SEASON_YEAR']
        enrollment = GolfEnrollment.query.filter_by(
            user_id=current_user.id, season_year=season_year
        ).first()
        if not enrollment or not enrollment.is_admin:
            flash('Golf admin access required.', 'error')
            return redirect(url_for('golf.index'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# Context Processor — inject golf-specific globals into golf templates
# ============================================================================

@golf_bp.context_processor
def inject_golf_globals():
    """Inject golf-specific variables into all golf templates."""
    return {
        'body_class': 'game-golf',
        'golf_current_time': get_current_time(),
        'season_year': current_app.config['SEASON_YEAR'],
        'entry_fee': current_app.config['ENTRY_FEE'],
        'penalty_per_incident': PENALTY_PER_INCIDENT,
        'format_score_to_par': format_score_to_par,
    }


# ============================================================================
# Before Request — Auto-refresh tournament statuses
# ============================================================================

@golf_bp.before_request
def refresh_tournament_states():
    """Ensure tournament statuses reflect current time."""
    if not request.endpoint or request.endpoint == 'static':
        return

    now = get_current_time()
    refresh_interval = current_app.config.get('STATUS_REFRESH_INTERVAL_SECONDS', 300)
    last_refresh = current_app.config.get('_GOLF_LAST_STATUS_REFRESH')

    if last_refresh and (now - last_refresh).total_seconds() < refresh_interval:
        return

    tournaments = GolfTournament.query.filter(
        GolfTournament.season_year == current_app.config['SEASON_YEAR'],
        GolfTournament.status.in_(['upcoming', 'active'])
    ).all()
    updated = False
    for tournament in tournaments:
        previous = tournament.status
        if tournament.update_status_from_time(now) != previous:
            updated = True
            logger.info("Auto-updated tournament %s: %s -> %s",
                       tournament.name, previous, tournament.status)
    if updated:
        db.session.commit()
    current_app.config['_GOLF_LAST_STATUS_REFRESH'] = now


# ============================================================================
# Helpers
# ============================================================================

def get_cumulative_scores(user_ids, season_year):
    """Calculate cumulative score to par using a single efficient query."""
    if not user_ids:
        return {}

    rows = (
        db.session.query(
            GolfPick.user_id,
            func.sum(GolfTournamentResult.score_to_par)
        )
        .join(GolfTournament, GolfPick.tournament_id == GolfTournament.id)
        .join(
            GolfTournamentResult,
            and_(
                GolfTournamentResult.tournament_id == GolfPick.tournament_id,
                GolfTournamentResult.player_id == GolfPick.active_player_id
            )
        )
        .filter(
            GolfTournament.status == 'complete',
            GolfTournament.season_year == season_year,
            GolfPick.active_player_id.isnot(None),
            GolfTournamentResult.score_to_par.isnot(None)
        )
        .group_by(GolfPick.user_id)
        .all()
    )

    score_map = {user_id: total for user_id, total in rows}
    cumulative = {}
    for uid in user_ids:
        total = score_map.get(uid, 0) or 0
        cumulative[uid] = {
            'total': total,
            'display': format_score_to_par(total)
        }
    return cumulative


# ============================================================================
# Public Routes
# ============================================================================

@golf_bp.route('/')
def index():
    """Golf Pick 'Em standings page."""
    season_year = current_app.config['SEASON_YEAR']

    # Get all enrolled users for this season, ordered by total_points.
    # Eager-load .user so building the standings rows doesn't fire a query
    # per enrollee (N+1, audit §5).
    enrollments = (
        GolfEnrollment.query
        .options(joinedload(GolfEnrollment.user))
        .filter_by(season_year=season_year)
        .order_by(GolfEnrollment.total_points.desc())
        .all()
    )

    # Standings are golf-enrollment-scoped (ADR-036): only current-season golf
    # enrollees appear. The board is NOT padded with every platform user —
    # that polluted it with World Cup / CFB-only accounts sitting at 0 points.
    users = []
    for enrollment in enrollments:
        users.append({
            'user': enrollment.user,
            'enrollment': enrollment,
            'total_points': enrollment.total_points,
            'has_paid': enrollment.has_paid,
        })

    # Tournament data
    all_tournaments = (
        GolfTournament.query
        .filter_by(season_year=season_year)
        .order_by(GolfTournament.start_date)
        .all()
    )

    completed_tournaments = [t for t in all_tournaments if t.status == 'complete']
    active_tournament = next((t for t in all_tournaments if t.status == 'active'), None)
    upcoming_tournaments = [t for t in all_tournaments if t.status == 'upcoming']
    next_tournament = upcoming_tournaments[0] if upcoming_tournaments else None

    # Cumulative scores
    all_user_ids = [u['user'].id for u in users]
    cumulative_scores = get_cumulative_scores(all_user_ids, season_year)

    # Active tournament picks and results
    active_picks = {}
    active_results = {}
    all_positions = []
    if active_tournament:
        picks = GolfPick.query.filter_by(tournament_id=active_tournament.id).all()
        for pick in picks:
            active_picks[pick.user_id] = pick

        results = GolfTournamentResult.query.filter_by(
            tournament_id=active_tournament.id
        ).all()
        for result in results:
            active_results[result.player_id] = result
            if result.final_position:
                all_positions.append(result.final_position)

    # Check if current user has picked for next tournament
    user_has_picked_next = False
    if current_user.is_authenticated and next_tournament:
        user_has_picked_next = GolfPick.query.filter_by(
            user_id=current_user.id,
            tournament_id=next_tournament.id
        ).first() is not None

    # Prize pool: entry fees (season-scoped enrollments) + the major cut/DQ
    # side pot (ADR-034). Pot = flagged picks x $15 across the active season.
    entry_total = len(enrollments) * current_app.config['ENTRY_FEE']
    penalty_pick_count = (
        db.session.query(func.count(GolfPick.id))
        .join(GolfTournament, GolfPick.tournament_id == GolfTournament.id)
        .filter(
            GolfPick.penalty_triggered.is_(True),
            GolfTournament.season_year == season_year,
        )
        .scalar()
    ) or 0
    total_penalty_pot = penalty_pick_count * PENALTY_PER_INCIDENT

    return render_template('golf/index.html',
        users=users,
        all_tournaments=all_tournaments,
        completed_tournaments=completed_tournaments,
        active_tournament=active_tournament,
        next_tournament=next_tournament,
        cumulative_scores=cumulative_scores,
        active_picks=active_picks,
        active_results=active_results,
        all_positions=all_positions,
        user_has_picked_next=user_has_picked_next,
        entry_total=entry_total,
        total_penalty_pot=total_penalty_pot,
        calculate_projected_earnings=calculate_projected_earnings,
    )


@golf_bp.route('/join', methods=['GET', 'POST'])
@login_required
@game_must_be_open('golf')
def join():
    """Enrollment page for Golf Pick 'Em."""
    season_year = current_app.config['SEASON_YEAR']
    existing = GolfEnrollment.query.filter_by(
        user_id=current_user.id, season_year=season_year
    ).first()
    if existing:
        flash("You are already enrolled in Golf Pick 'Em!", 'info')
        return redirect(url_for('golf.index'))

    if request.method == 'POST':
        enrollment = GolfEnrollment(
            user_id=current_user.id,
            season_year=season_year,
        )
        db.session.add(enrollment)
        db.session.commit()
        flash("Welcome to Golf Pick 'Em!", 'success')
        return redirect(url_for('golf.index'))

    return render_template('golf/join.html')


@golf_bp.route('/leaderboard')
def leaderboard():
    """Redirect to standings page."""
    return redirect(url_for('golf.index'))


@golf_bp.route('/schedule')
def schedule():
    """Season schedule page."""
    season_year = current_app.config['SEASON_YEAR']

    tournaments = (
        GolfTournament.query
        .filter_by(season_year=season_year)
        .order_by(GolfTournament.start_date)
        .all()
    )

    return render_template('golf/schedule.html', tournaments=tournaments)


@golf_bp.route('/tournament/<int:tournament_id>')
def tournament_detail(tournament_id):
    """Tournament detail/results page."""
    tournament = db.get_or_404(GolfTournament, tournament_id)
    season_year = current_app.config['SEASON_YEAR']

    # Get all picks for this tournament. Eager-load the user + player
    # relationships the standings table renders (sort key, avatar, primary /
    # backup / active names) so each pick row doesn't fire its own queries
    # (N+1, audit §5).
    picks = (
        GolfPick.query
        .options(
            joinedload(GolfPick.user),
            joinedload(GolfPick.primary_player),
            joinedload(GolfPick.backup_player),
            joinedload(GolfPick.active_player),
        )
        .filter_by(tournament_id=tournament_id)
        .all()
    )

    # Get results
    results = GolfTournamentResult.query.filter_by(
        tournament_id=tournament_id
    ).all()
    results_map = {r.player_id: r for r in results}

    # All positions for projected earnings calculation
    all_positions = [r.final_position for r in results if r.final_position]

    # Determine if picks should be visible (after deadline)
    picks_visible = tournament.is_deadline_passed()

    # Check if any backup was activated
    any_backup_activated = any(
        p.active_player_id == p.backup_player_id and p.active_player_id is not None
        for p in picks
    )

    return render_template('golf/tournament_detail.html',
        tournament=tournament,
        picks=picks,
        results_map=results_map,
        all_positions=all_positions,
        picks_visible=picks_visible,
        any_backup_activated=any_backup_activated,
        calculate_projected_earnings=calculate_projected_earnings,
    )


@golf_bp.route('/results')
def results():
    """Redirect to most recent completed tournament."""
    season_year = current_app.config['SEASON_YEAR']

    tournament = (
        GolfTournament.query
        .filter_by(season_year=season_year, status='complete')
        .order_by(GolfTournament.end_date.desc())
        .first()
    )

    if tournament:
        return redirect(url_for('golf.tournament_detail', tournament_id=tournament.id))

    flash('No completed tournaments yet.', 'info')
    return redirect(url_for('golf.index'))


# ============================================================================
# Authenticated Routes
# ============================================================================

@golf_bp.route('/pick/<int:tournament_id>', methods=['GET', 'POST'])
@login_required
@enrollment_required('golf')
def make_pick(tournament_id):
    """Pick submission form."""
    tournament = db.get_or_404(GolfTournament, tournament_id)
    season_year = current_app.config['SEASON_YEAR']

    # Check deadline
    if tournament.is_deadline_passed():
        flash('The pick deadline for this tournament has passed.', 'error')
        return redirect(url_for('golf.index'))

    # Check field availability
    if not tournament.has_sufficient_field():
        flash('The tournament field is not yet available. Check back later.', 'info')
        return redirect(url_for('golf.schedule'))

    # Enrollment is required; decorator above already short-circuits,
    # but we still need the object for used-player-ids lookup.
    enrollment = GolfEnrollment.query.filter_by(
        user_id=current_user.id, season_year=season_year
    ).first()

    # Get used player IDs for this season
    used_player_ids = enrollment.get_used_player_ids()

    # Get existing pick for this tournament (if editing)
    existing_pick = GolfPick.query.filter_by(
        user_id=current_user.id, tournament_id=tournament_id
    ).first()

    # If editing, the current pick's players aren't "used" for availability purposes
    if existing_pick:
        used_player_ids = [
            pid for pid in used_player_ids
            if pid not in (existing_pick.primary_player_id, existing_pick.backup_player_id)
        ]

    # Get available players (in tournament field, not already used)
    field_entries = (
        GolfTournamentField.query
        .filter_by(tournament_id=tournament_id)
        .join(GolfPlayer)
        .order_by(GolfPlayer.last_name)
        .all()
    )
    available_players = [
        entry.player for entry in field_entries
        if entry.player_id not in used_player_ids
    ]

    if request.method == 'POST':
        primary_id = request.form.get('primary_player_id', type=int)
        backup_id = request.form.get('backup_player_id', type=int)

        if not primary_id or not backup_id:
            flash('Please select both a primary and backup player.', 'error')
        elif primary_id == backup_id:
            flash('Primary and backup players must be different.', 'error')
        else:
            if existing_pick:
                existing_pick.primary_player_id = primary_id
                existing_pick.backup_player_id = backup_id
                existing_pick.updated_at = datetime.now(UTC)
                pick = existing_pick
            else:
                pick = GolfPick(
                    user_id=current_user.id,
                    tournament_id=tournament_id,
                    primary_player_id=primary_id,
                    backup_player_id=backup_id,
                )
                db.session.add(pick)

            # Validate availability
            errors = pick.validate_availability(season_year)
            if errors:
                for error in errors:
                    flash(error, 'error')
                # Discard the invalid insert/mutation so it can't autoflush and
                # the re-rendered form shows persisted (valid) state (audit §2).
                db.session.rollback()
            else:
                db.session.commit()
                primary_player = db.session.get(GolfPlayer, primary_id)
                backup_player = db.session.get(GolfPlayer, backup_id)
                flash(
                    f'Pick submitted: {primary_player.full_name()} '
                    f'(backup: {backup_player.full_name()})',
                    'success'
                )
                return redirect(url_for('golf.my_picks'))

    return render_template('golf/make_pick.html',
        tournament=tournament,
        available_players=available_players,
        existing_pick=existing_pick,
        used_player_ids=used_player_ids,
    )


@golf_bp.route('/my-picks')
@login_required
@enrollment_required('golf')
def my_picks():
    """User's pick history for the season."""
    season_year = current_app.config['SEASON_YEAR']

    enrollment = GolfEnrollment.query.filter_by(
        user_id=current_user.id, season_year=season_year
    ).first()

    tournaments = (
        GolfTournament.query
        .filter_by(season_year=season_year)
        .order_by(GolfTournament.start_date)
        .all()
    )

    picks = GolfPick.query.filter_by(user_id=current_user.id).all()
    picks_map = {p.tournament_id: p for p in picks}

    # Calculate stats
    total_points = enrollment.total_points if enrollment else 0
    picks_made = len(picks_map)
    best_pick = None
    if picks:
        completed_picks = [p for p in picks if p.points_earned is not None and p.points_earned > 0]
        if completed_picks:
            best_pick = max(completed_picks, key=lambda p: p.points_earned)

    # Get used players count
    used_count = GolfSeasonPlayerUsage.query.filter_by(
        user_id=current_user.id, season_year=season_year
    ).count()

    return render_template('golf/my_picks.html',
        enrollment=enrollment,
        tournaments=tournaments,
        picks_map=picks_map,
        total_points=total_points,
        picks_made=picks_made,
        best_pick=best_pick,
        used_count=used_count,
    )


# ============================================================================
# Admin Routes
# ============================================================================

@golf_bp.route('/admin/')
@golf_admin_required
def admin_dashboard():
    """Golf admin overview."""
    season_year = current_app.config['SEASON_YEAR']

    tournaments = GolfTournament.query.filter_by(season_year=season_year).all()
    upcoming_count = sum(1 for t in tournaments if t.status == 'upcoming')
    active_count = sum(1 for t in tournaments if t.status == 'active')
    complete_count = sum(1 for t in tournaments if t.status == 'complete')
    pending_finalization = [t for t in tournaments if t.status == 'complete' and not t.results_finalized]

    enrollments = GolfEnrollment.query.filter_by(season_year=season_year).all()
    total_enrolled = len(enrollments)
    total_paid = sum(1 for e in enrollments if e.has_paid)

    total_users = User.query.count()
    total_players = GolfPlayer.query.count()

    return render_template('golf/admin/dashboard.html',
        tournaments=tournaments,
        upcoming_count=upcoming_count,
        active_count=active_count,
        complete_count=complete_count,
        pending_finalization=pending_finalization,
        total_enrolled=total_enrolled,
        total_paid=total_paid,
        total_users=total_users,
        total_players=total_players,
    )


@golf_bp.route('/admin/tournaments')
@golf_admin_required
def admin_tournaments():
    """Tournament management page."""
    season_year = current_app.config['SEASON_YEAR']

    tournaments = (
        GolfTournament.query
        .filter_by(season_year=season_year)
        .order_by(GolfTournament.start_date)
        .all()
    )

    return render_template('golf/admin/tournaments.html', tournaments=tournaments)


@golf_bp.route('/admin/users')
@golf_admin_required
def admin_users():
    """Golf user management page."""
    season_year = current_app.config['SEASON_YEAR']

    users = User.query.order_by(User.username).all()
    enrollments = GolfEnrollment.query.filter_by(season_year=season_year).all()
    enrollment_map = {e.user_id: e for e in enrollments}

    return render_template('golf/admin/users.html',
        users=users,
        enrollment_map=enrollment_map,
    )


@golf_bp.route('/admin/payments')
@golf_admin_required
def admin_payments():
    """Payment tracking page."""
    season_year = current_app.config['SEASON_YEAR']

    enrollments = (
        GolfEnrollment.query
        .filter_by(season_year=season_year)
        .all()
    )

    total_paid = sum(1 for e in enrollments if e.has_paid)
    total_unpaid = sum(1 for e in enrollments if not e.has_paid)
    total_collected = total_paid * current_app.config['ENTRY_FEE']

    # Major cut/DQ side pot (ADR-034): one grouped query for flagged-pick counts,
    # then owed/paid/outstanding per enrollment + pot totals.
    penalty_counts = dict(
        db.session.query(GolfPick.user_id, func.count(GolfPick.id))
        .join(GolfTournament, GolfPick.tournament_id == GolfTournament.id)
        .filter(
            GolfPick.penalty_triggered.is_(True),
            GolfTournament.season_year == season_year,
        )
        .group_by(GolfPick.user_id)
        .all()
    )
    penalty_summary = {}
    for e in enrollments:
        owed = penalty_counts.get(e.user_id, 0) * PENALTY_PER_INCIDENT
        paid = e.penalty_paid or 0
        penalty_summary[e.user_id] = {
            'owed': owed,
            'paid': paid,
            'outstanding': max(0, owed - paid),
        }
    total_penalty_pot = sum(s['owed'] for s in penalty_summary.values())
    total_penalty_collected = sum(s['paid'] for s in penalty_summary.values())

    return render_template('golf/admin/payments.html',
        enrollments=enrollments,
        total_paid=total_paid,
        total_unpaid=total_unpaid,
        total_collected=total_collected,
        penalty_summary=penalty_summary,
        total_penalty_pot=total_penalty_pot,
        total_penalty_collected=total_penalty_collected,
        penalty_per_incident=PENALTY_PER_INCIDENT,
    )


@golf_bp.route('/admin/update-payment/<int:user_id>', methods=['POST'])
@golf_admin_required
def admin_update_payment(user_id):
    """Toggle golf payment status (AJAX)."""
    season_year = current_app.config['SEASON_YEAR']
    enrollment = GolfEnrollment.query.filter_by(
        user_id=user_id, season_year=season_year
    ).first()
    if not enrollment:
        return jsonify({
            'success': False,
            'error': 'User is not enrolled in Golf Pick \'Em.',
        }), 400

    data = request.get_json() or {}

    def _parse_non_negative_int(value):
        """Whole non-negative dollars only; reject floats/non-numeric — no silent
        truncation of a JSON float like 12.75 into 12. Negatives clamp to 0."""
        if isinstance(value, bool):
            raise ValueError
        if isinstance(value, int):
            return max(0, value)
        if isinstance(value, str):
            return max(0, int(value.strip()))  # int() rejects '12.5'/'abc'
        raise ValueError

    # Penalty-paid update (ADR-034) — handled independently of has_paid so a
    # penalty-only save never resets the entry fee.
    if 'penalty_paid' in data:
        try:
            enrollment.penalty_paid = _parse_non_negative_int(data['penalty_paid'])
        except (TypeError, ValueError):
            return jsonify({
                'success': False,
                'error': 'penalty_paid must be a non-negative integer',
            }), 400
    if 'has_paid' in data:
        enrollment.has_paid = bool(data['has_paid'])
    db.session.commit()
    return jsonify({
        'success': True,
        'has_paid': enrollment.has_paid,
        'penalty_paid': enrollment.penalty_paid,
    })


@golf_bp.route('/admin/override-pick', methods=['GET', 'POST'])
@golf_admin_required
def admin_override_pick():
    """Admin pick override page."""
    season_year = current_app.config['SEASON_YEAR']

    tournaments = (
        GolfTournament.query
        .filter_by(season_year=season_year)
        .filter(GolfTournament.status.in_(['upcoming', 'active', 'complete']))
        .order_by(GolfTournament.start_date)
        .all()
    )

    users = User.query.order_by(User.username).all()

    selected_tournament = None
    selected_user = None
    field_players = []
    existing_pick = None
    used_player_ids = []

    if request.method == 'POST':
        tournament_id = request.form.get('tournament_id', type=int)
        user_id = request.form.get('user_id', type=int)
        primary_id = request.form.get('primary_player_id', type=int)
        backup_id = request.form.get('backup_player_id', type=int)
        override_note = request.form.get('override_note', '').strip()

        if tournament_id and user_id and primary_id and backup_id:
            selected_tournament = db.session.get(GolfTournament, tournament_id)
            selected_user = db.session.get(User, user_id)

            if not (selected_tournament and selected_user):
                flash('Tournament or user not found.', 'error')
                return redirect(url_for('golf.admin_override_pick'))

            # Re-scope the POSTed tournament to the same season + statuses the
            # selectable list is built from — a crafted tournament_id must not
            # write a pick for another season while validating against this
            # season's enrollment/usage.
            if (selected_tournament.season_year != season_year
                    or selected_tournament.status not in ('upcoming', 'active', 'complete')):
                flash('Tournament is not eligible for admin overrides.', 'error')
                return redirect(url_for('golf.admin_override_pick'))

            existing_pick = GolfPick.query.filter_by(
                user_id=user_id, tournament_id=tournament_id
            ).first()
            enrollment = GolfEnrollment.query.filter_by(
                user_id=user_id, season_year=season_year
            ).first()

            # Server-side eligibility validation (audit §2 HIGH): never trust the
            # disabled-option UI. Check field membership + season usage BEFORE
            # mutating anything, excluding the pick's own current players
            # (re-selecting them is legal). A failure mutates nothing.
            field_player_ids = {
                entry.player_id for entry in
                GolfTournamentField.query.filter_by(tournament_id=tournament_id)
            }
            used_player_ids = set(enrollment.get_used_player_ids()) if enrollment else set()
            if existing_pick:
                used_player_ids.discard(existing_pick.primary_player_id)
                used_player_ids.discard(existing_pick.backup_player_id)

            errors = []
            if primary_id == backup_id:
                errors.append('Primary and backup players must be different.')
            if primary_id not in field_player_ids:
                errors.append('Primary player is not in the tournament field.')
            if backup_id not in field_player_ids:
                errors.append('Backup player is not in the tournament field.')
            if primary_id in used_player_ids:
                errors.append('Primary player has already been used this season.')
            if backup_id in used_player_ids:
                errors.append('Backup player has already been used this season.')
            if not enrollment:
                # Never create enrollment rows from admin paths — admins add
                # users via Platform Admin → Enrollments first.
                errors.append(
                    "User must be enrolled in Golf Pick 'Em before an admin "
                    'override can be applied. Add them via Admin → Enrollments first.'
                )

            if errors:
                for error in errors:
                    flash(error, 'error')
                # Discard any autoflush-pending state; re-render the form clean.
                db.session.rollback()
                return redirect(url_for(
                    'golf.admin_override_pick',
                    tournament_id=tournament_id, user_id=user_id,
                ))

            # Validated — safe to mutate.
            if existing_pick:
                # Clear old resolution for completed tournaments
                if selected_tournament.status == 'complete':
                    existing_pick.clear_resolution(season_year)
                existing_pick.primary_player_id = primary_id
                existing_pick.backup_player_id = backup_id
                existing_pick.admin_override = True
                existing_pick.admin_override_note = override_note or 'Admin override'
                existing_pick.updated_at = datetime.now(UTC)
                pick = existing_pick
            else:
                pick = GolfPick(
                    user_id=user_id,
                    tournament_id=tournament_id,
                    primary_player_id=primary_id,
                    backup_player_id=backup_id,
                    admin_override=True,
                    admin_override_note=override_note or 'Admin override',
                )
                db.session.add(pick)

            # Re-resolve for completed tournaments (enrollment guaranteed above).
            # A failed resolve leaves cleared resolution + stale totals — roll the
            # whole override back rather than persist that inconsistent state.
            if selected_tournament.status == 'complete':
                db.session.flush()
                if not pick.resolve_pick():
                    db.session.rollback()
                    flash(
                        'Override could not be resolved — result data is missing '
                        'for the selected players.',
                        'error',
                    )
                    return redirect(url_for(
                        'golf.admin_override_pick',
                        tournament_id=tournament_id, user_id=user_id,
                    ))
                enrollment.calculate_total_points()

            db.session.commit()

            primary_player = db.session.get(GolfPlayer, primary_id)
            backup_player = db.session.get(GolfPlayer, backup_id)
            flash(
                f'Override saved for {selected_user.username}: '
                f'{primary_player.full_name()} / {backup_player.full_name()}',
                'success'
            )
            return redirect(url_for('golf.admin_override_pick'))

    # For GET or when loading form data
    tournament_id = request.args.get('tournament_id', type=int)
    user_id = request.args.get('user_id', type=int)

    if tournament_id:
        selected_tournament = db.session.get(GolfTournament, tournament_id)
        if selected_tournament:
            field_entries = (
                GolfTournamentField.query
                .filter_by(tournament_id=tournament_id)
                .join(GolfPlayer)
                .order_by(GolfPlayer.last_name)
                .all()
            )
            field_players = [entry.player for entry in field_entries]

    if user_id:
        selected_user = db.session.get(User, user_id)
        if selected_user:
            enrollment = GolfEnrollment.query.filter_by(
                user_id=user_id, season_year=season_year
            ).first()
            used_player_ids = enrollment.get_used_player_ids() if enrollment else []

            if tournament_id:
                existing_pick = GolfPick.query.filter_by(
                    user_id=user_id, tournament_id=tournament_id
                ).first()
                # The pick's own players aren't "used" for its own edit — drop
                # them so the form doesn't render them disabled (audit §2).
                if existing_pick:
                    used_player_ids = [
                        pid for pid in used_player_ids
                        if pid not in (existing_pick.primary_player_id,
                                       existing_pick.backup_player_id)
                    ]

    # Recent overrides
    recent_overrides = (
        GolfPick.query
        .filter_by(admin_override=True)
        .join(GolfTournament)
        .filter(GolfTournament.season_year == season_year)
        .order_by(GolfPick.updated_at.desc())
        .limit(10)
        .all()
    )

    return render_template('golf/admin/override_pick.html',
        tournaments=tournaments,
        users=users,
        selected_tournament=selected_tournament,
        selected_user=selected_user,
        field_players=field_players,
        existing_pick=existing_pick,
        used_player_ids=used_player_ids,
        recent_overrides=recent_overrides,
    )


@golf_bp.route('/admin/process-results/<int:tournament_id>', methods=['POST'])
@golf_admin_required
def admin_process_results(tournament_id):
    """Manually process results for a completed tournament."""
    from games.golf.services.sync import SlashGolfAPI, TournamentSync

    tournament = db.get_or_404(GolfTournament, tournament_id)
    if tournament.status != 'complete':
        flash('Tournament must be complete before processing results.', 'error')
        return redirect(url_for('golf.admin_tournaments'))

    api_key = current_app.config.get('SLASHGOLF_API_KEY', '')
    sync_mode = current_app.config.get('SYNC_MODE', 'standard')
    api = SlashGolfAPI(api_key, sync_mode=sync_mode)
    sync = TournamentSync(api, sync_mode=sync_mode)
    processed = sync.process_tournament_picks(tournament)

    flash(f'Processed results for {processed} picks.', 'success')
    return redirect(url_for('golf.admin_tournaments'))
