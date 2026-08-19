"""The Docket — the clerk's office (T9).

Separate module from routes.py by design: that file is the player's room,
this one is the desk. Both register on the same blueprint, and the two-tier
admin gate lives here because nothing outside this module needs it.

Three rulings, one per screen, because each has a different gate: a
designation is pre-deadline only, a correction is pre-deadline AND
pre-kickoff, and a No Contest ruling can land at any time. Every rule lives
in games/docket/services/admin_ops.py; these handlers stay declarative and
do nothing but resolve the week, hand over the form, and flash the outcome.
Court costs (the entry-fee ledger) sit at the end: a season screen, not a
weekly ruling, so it touches enrollments and never admin_ops.

Both ruling screens take an optional ``?game=<id>`` so the page stays light
on a 90-case docket: the list shows state, the selected case shows controls.
"""
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

from extensions import db
from games.docket.blueprint import docket_bp
from games.docket.models import DocketEnrollment, DocketGame, DocketWeek
from games.docket.services import admin_ops
from games.docket.services.admin_ops import AdminOpError
from games.docket.services.deadline_pass import check_designation
from games.docket.services.enrollment import get_enrollment
from games.docket.services.picks import now_naive
from games.docket.services.weeks import SEASON_YEAR
from models.user import User


def docket_admin_required(f):
    """Two-tier admin gate: platform admin always passes; otherwise the
    user's current-season enrollment must carry ``is_admin``."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_admin:
            return f(*args, **kwargs)
        enrollment = get_enrollment(current_user.id)
        if not enrollment or not enrollment.is_admin:
            flash('Docket admin access required.', 'error')
            return redirect(url_for('docket.index'))
        return f(*args, **kwargs)
    return decorated_function


def _week_or_none(week_number):
    return db.session.scalar(
        select(DocketWeek).filter_by(week_number=week_number))


def _week_games(week):
    return db.session.scalars(
        select(DocketGame).filter_by(week_id=week.id)
        .order_by(DocketGame.kickoff, DocketGame.api_event_id)).all()


def _selected_game(week, games):
    """The ``?game=<id>`` case, when it is on this docket."""
    raw = request.args.get('game', type=int)
    if raw is None:
        return None
    return next((g for g in games if g.id == raw), None)


def _count(n, singular, plural=None):
    """'1 pick' / '2 picks'. These numbers are usually 1 in a real week."""
    return f'{n} {singular if n == 1 else (plural or singular + "s")}'


def _flash_grading(result):
    """Report a D14 auto-recalc. ``not_ready`` is a normal state before the
    deadline pass has run, so it reports as information, not failure."""
    if result.get('status') == 'ok':
        flash(f'Week re-graded: {_count(result["graded"], "player")}.',
              'success')
    else:
        flash(f'Ruling recorded. The week is not gradeable yet: '
              f'{result.get("reason")}', 'info')


def _refuse(exc: AdminOpError):
    flash(exc.message, 'error')
    for problem in exc.problems:
        flash(problem, 'error')


# --------------------------------------------------------------------------
# The desk
# --------------------------------------------------------------------------

@docket_bp.route('/admin/')
@docket_admin_required
def admin_dashboard():
    weeks = db.session.scalars(
        select(DocketWeek).order_by(DocketWeek.week_number)).all()
    now = now_naive()
    rows = []
    for week in weeks:
        games = _week_games(week)
        rows.append({
            'week': week,
            'games': len(games),
            'thrown_out': sum(1 for g in games if g.no_contest),
            'designated': week.tiebreaker_game,
            'problems': check_designation(week),
            'open': now < week.deadline_at,
        })
    return render_template('docket/admin/dashboard.html', rows=rows, now=now)


@docket_bp.route('/admin/week/<int:week_number>/tiebreaker',
                 methods=['GET', 'POST'])
@docket_admin_required
def admin_tiebreaker(week_number):
    week = _week_or_none(week_number)
    if week is None:
        flash(f'No docket week {week_number} yet.', 'error')
        return redirect(url_for('docket.admin_dashboard'))

    if request.method == 'POST':
        try:
            result = admin_ops.designate_tiebreaker(
                week, request.form.get('game_id', type=int))
        except AdminOpError as exc:
            _refuse(exc)
        else:
            game = result['game']
            if not result['changed']:
                flash(f'{game.away_team} at {game.home_team} was already '
                      f'the tiebreaker case.', 'info')
            else:
                flash(f'Tiebreaker case for week {week_number}: '
                      f'{game.away_team} at {game.home_team}.', 'success')
                if result['cleared']:
                    flash(f'{_count(result["cleared"], "prediction")} '
                          f'cleared to the new default; '
                          f'{_count(result["notified"], "player")} notified '
                          f'they may resubmit.', 'info')
        # Redirect on both outcomes, like the two sibling screens: one
        # failure shape across the desk, and flashes survive the redirect.
        return redirect(url_for('docket.admin_tiebreaker',
                                week_number=week_number))

    return render_template(
        'docket/admin/tiebreaker.html',
        week=week,
        eligible=admin_ops.eligible_tiebreaker_games(week),
        problems=check_designation(week),
        is_open=now_naive() < week.deadline_at)


@docket_bp.route('/admin/week/<int:week_number>/rulings',
                 methods=['GET', 'POST'])
@docket_admin_required
def admin_rulings(week_number):
    week = _week_or_none(week_number)
    if week is None:
        flash(f'No docket week {week_number} yet.', 'error')
        return redirect(url_for('docket.admin_dashboard'))

    if request.method == 'POST':
        game_id = request.form.get('game_id', type=int)
        try:
            if request.form.get('action') == 'clear':
                result = admin_ops.clear_no_contest(week, game_id)
                flash('No Contest cleared.', 'success')
            else:
                result = admin_ops.rule_no_contest(
                    week, game_id, request.form.get('reason'))
                game = result['game']
                flash(f'{game.away_team} at {game.home_team} thrown out.',
                      'success')
                if game.id == week.tiebreaker_game_id \
                        and now_naive() < week.deadline_at:
                    flash('That was the tiebreaker case. Designate another '
                          'one before the deadline: predictions will be '
                          'cleared to the new default.', 'warning')
        except AdminOpError as exc:
            _refuse(exc)
        else:
            _flash_grading(result['grading'])
        return redirect(url_for('docket.admin_rulings',
                                week_number=week_number))

    games = _week_games(week)
    return render_template('docket/admin/rulings.html', week=week,
                           games=games,
                           selected=_selected_game(week, games))


@docket_bp.route('/admin/week/<int:week_number>/lines',
                 methods=['GET', 'POST'])
@docket_admin_required
def admin_lines(week_number):
    week = _week_or_none(week_number)
    if week is None:
        flash(f'No docket week {week_number} yet.', 'error')
        return redirect(url_for('docket.admin_dashboard'))

    if request.method == 'POST':
        try:
            result = admin_ops.correct_line(
                week,
                request.form.get('game_id', type=int),
                request.form.get('market'),
                request.form.get('value'),
                request.form.get('book'),
                request.form.get('reason'),
                current_user.id)
        except AdminOpError as exc:
            _refuse(exc)
        else:
            flash(f'Line corrected. '
                  f'{_count(result["resnapshotted"], "pick")} '
                  f're-snapshotted, '
                  f'{_count(result["notified"], "picker")} notified.',
                  'success')
        return redirect(url_for('docket.admin_lines',
                                week_number=week_number,
                                game=request.form.get('game_id', type=int)))

    games = _week_games(week)
    now = now_naive()
    return render_template('docket/admin/lines.html', week=week,
                           games=games,
                           selected=_selected_game(week, games),
                           is_open=now < week.deadline_at,
                           now=now)


# --------------------------------------------------------------------------
# Court costs (entry-fee collection)
# --------------------------------------------------------------------------

@docket_bp.route('/admin/payments')
@docket_admin_required
def admin_payments():
    """Entry-fee tracking for the current season's roster."""
    entry_fee = current_app.config.get('DOCKET_ENTRY_FEE', 60)
    enrollments = db.session.scalars(
        select(DocketEnrollment)
        .filter_by(season_year=SEASON_YEAR)
        .join(User)
        .order_by(func.lower(User.username))).all()
    paid_count = sum(1 for e in enrollments if e.has_paid)
    return render_template(
        'docket/admin/payments.html',
        enrollments=enrollments,
        entry_fee=entry_fee,
        paid_count=paid_count,
        total_users=len(enrollments),
        total_collected=paid_count * entry_fee,
    )


@docket_bp.route('/admin/update-payment/<int:user_id>', methods=['POST'])
@docket_admin_required
def admin_update_payment(user_id):
    """Toggle a member's payment status (AJAX; CFB's endpoint shape)."""
    enrollment = db.session.scalar(
        select(DocketEnrollment).filter_by(
            user_id=user_id, season_year=SEASON_YEAR))
    if not enrollment:
        return jsonify({'success': False,
                        'error': 'Enrollment not found'}), 404
    data = request.get_json(silent=True)
    if (not isinstance(data, dict)
            or not isinstance(data.get('has_paid'), bool)):
        return jsonify({'success': False,
                        'error': 'Invalid request body'}), 400
    has_paid = data['has_paid']
    enrollment.has_paid = has_paid
    db.session.commit()
    return jsonify({'success': True, 'has_paid': has_paid})
