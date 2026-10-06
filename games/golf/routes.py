"""
The Pay Sheet — Routes
========================
All route handlers for the The Pay Sheet game.
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
from sqlalchemy import func, select
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
from games.golf.services.sheet import (
    build_board,
    build_sheet,
    event_clock,
    live_event,
    week_lines,
)
from games.golf.utils import (
    format_lock,
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

def _viewer_is_golf_admin():
    """The sub-nav's Admin pill: platform admin, or the season's enrollment admin."""
    if not current_user.is_authenticated:
        return False
    if current_user.is_admin:
        return True
    enrollment = GolfEnrollment.query.filter_by(
        user_id=current_user.id, season_year=current_app.config['SEASON_YEAR']
    ).first()
    return bool(enrollment and enrollment.is_admin)


@golf_bp.context_processor
def inject_golf_globals():
    """Inject golf-specific variables into all golf templates."""
    return {
        'body_class': 'game-golf',
        'golf_is_admin': _viewer_is_golf_admin(),
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

def _season_enrollments(season_year):
    """A season's enrollees with their users loaded (no query per row)."""
    return db.session.scalars(
        select(GolfEnrollment)
        .options(joinedload(GolfEnrollment.user))
        .filter_by(season_year=season_year)
    ).all()


def _tournament_picks(tournament_id):
    """A tournament's picks with the member and both golfers loaded."""
    return db.session.scalars(
        select(GolfPick)
        .options(
            joinedload(GolfPick.user),
            joinedload(GolfPick.primary_player),
            joinedload(GolfPick.backup_player),
        )
        .filter_by(tournament_id=tournament_id)
    ).all()


def _tournament_results(tournament_id):
    return db.session.scalars(
        select(GolfTournamentResult).filter_by(tournament_id=tournament_id)
    ).all()


# ============================================================================
# Public Routes
# ============================================================================

@golf_bp.route('/')
def index():
    """The Sheet: the season's standings."""
    season_year = current_app.config['SEASON_YEAR']
    viewer_id = current_user.id if current_user.is_authenticated else None

    # Standings are golf-enrollment-scoped (ADR-036): only current-season golf
    # enrollees have a line. The sheet is never padded with platform users.
    enrollments = _season_enrollments(season_year)
    tournaments = db.session.scalars(
        select(GolfTournament)
        .filter_by(season_year=season_year)
        .order_by(GolfTournament.start_date)
    ).all()

    # The week turns over at the lock (the pick form's own test), never at a
    # status. The event the sheet is pencilling, on the course or played and
    # not yet final, is past its lock; its picks and results load once and
    # every row reads from them.
    event = live_event([t for t in tournaments if t.is_deadline_passed()])
    lines = clock = None
    if event:
        results = _tournament_results(event.id)
        lines = week_lines(event, _tournament_picks(event.id), results)
        clock = event_clock(event, results, get_current_time())
    sheet = build_sheet(enrollments, viewer_id, lines)

    # The next pick is the first tournament still before its lock. Status
    # decides only for one with no deadline yet, which the lock reads as open
    # forever (a field sync that never ran leaves a played week without one).
    next_tournament = next(
        (t for t in tournaments
         if (not t.is_deadline_passed() if t.pick_deadline else t.status == 'upcoming')),
        None,
    )
    field_open = bool(next_tournament and next_tournament.has_sufficient_field())
    next_pick = None
    if next_tournament and sheet.mine:
        next_pick = db.session.scalar(
            select(GolfPick)
            .options(
                joinedload(GolfPick.primary_player),
                joinedload(GolfPick.backup_player),
            )
            .filter_by(user_id=viewer_id, tournament_id=next_tournament.id)
        )

    # A signed-in visitor with no line is offered a seat while the room takes them.
    # (Imported here like games/common.py does: the registry imports every game.)
    from games.registry import get_entry
    entry = get_entry('golf')
    can_join = (
        current_user.is_authenticated
        and sheet.mine is None
        and entry.status == 'open'
        and (entry.join_open is None or entry.join_open())
    )

    banked_boards = [t for t in tournaments if t.results_finalized]

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
        sheet=sheet,
        clock=clock,
        next_tournament=next_tournament,
        next_lock=format_lock(next_tournament.pick_deadline) if next_tournament else None,
        field_open=field_open,
        next_pick=next_pick,
        last_board=banked_boards[-1] if banked_boards else None,
        can_join=can_join,
        entry_total=entry_total,
        total_penalty_pot=total_penalty_pot,
    )


@golf_bp.route('/join', methods=['GET', 'POST'])
@login_required
@game_must_be_open('golf')
def join():
    """Enrollment page for The Pay Sheet."""
    season_year = current_app.config['SEASON_YEAR']
    existing = GolfEnrollment.query.filter_by(
        user_id=current_user.id, season_year=season_year
    ).first()
    if existing:
        flash("You are already enrolled in The Pay Sheet!", 'info')
        return redirect(url_for('golf.index'))

    if request.method == 'POST':
        enrollment = GolfEnrollment(
            user_id=current_user.id,
            season_year=season_year,
        )
        db.session.add(enrollment)
        db.session.commit()
        flash("Welcome to The Pay Sheet!", 'success')
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
    """The Board: one tournament's picks and what each is worth."""
    tournament = db.get_or_404(GolfTournament, tournament_id)
    viewer_id = current_user.id if current_user.is_authenticated else None

    picks = _tournament_picks(tournament_id)
    my_pick = next((p for p in picks if p.user_id == viewer_id), None)

    # Picks open to the room at the lock, the pick form's own test, never at a
    # status (a sync writes 'active' from Thursday midnight, before the first
    # tee). Until then the template is handed the viewer's own pick and a
    # count, never another member's golfer.
    locked = tournament.is_deadline_passed()
    board = clock = None
    can_pick = False
    if locked:
        results = _tournament_results(tournament_id)
        board = build_board(
            week_lines(tournament, picks, results),
            _season_enrollments(tournament.season_year),
            viewer_id,
        )
        if not tournament.results_finalized:
            clock = event_clock(tournament, results, get_current_time())
    else:
        can_pick = tournament.has_sufficient_field()

    # The board is one leaf of the Season Book: its neighbours ride the pager.
    season = db.session.scalars(
        select(GolfTournament)
        .filter_by(season_year=tournament.season_year)
        .order_by(GolfTournament.start_date)
    ).all()
    at = season.index(tournament)

    return render_template('golf/tournament_detail.html',
        tournament=tournament,
        previous_week=season[at - 1] if at else None,
        next_week=season[at + 1] if at + 1 < len(season) else None,
        weeks=max(t.week_number or 0 for t in season),
        board=board,
        clock=clock,
        my_pick=my_pick,
        lines_in=len(picks),
        can_pick=can_pick,
        lock=format_lock(tournament.pick_deadline),
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
                    "User must be enrolled in The Pay Sheet before an admin "
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
