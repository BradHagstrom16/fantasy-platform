"""The Docket routes — the room: join, the pick sheet, the ledger, the rules.

The pick sheet stays the room's index; the season ledger has its own route.
The weekly obligation is what members land here for between Tuesday and
Saturday, and the ledger is where they go to see what it bought them.
Every mutation is a plain POST form (PRG + flash, fully functional without
JS); a client sending ``Accept: application/json`` gets the authoritative
sheet state back instead of a redirect, which is what the sheet's
enhancement script repaints from. All rule enforcement lives in
games/docket/services/picks.py; these handlers stay declarative.
"""
from collections import Counter
from datetime import UTC

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
from sqlalchemy.exc import IntegrityError

from extensions import db
from games.common import enrollment_required, game_must_be_open
from games.docket.blueprint import docket_bp
from games.docket.models import DocketEnrollment, DocketGame
from games.docket.services import picks as picks_service
from games.docket.services.bridge_sheet import SPORT_LABELS
from games.docket.services.enrollment import get_enrollment
from games.docket.services.grading.engine import slot_points
from games.docket.services.grading.snapshots import BACKUP_SLOT, SCORING_SLOTS, Outcome
from games.docket.services.importer import BOOKMAKER_LABELS, BOOKMAKER_PRIORITY
from games.docket.services.picks import PickError
from games.docket.services.season_pass import season_ledger
from games.docket.services.weeks import (
    CT,
    SEASON_YEAR,
    TOTAL_WEEKS,
    WEEK_1_BOUNDARY_LOCAL,
)


def _kickoff_ct(dt):
    """Render seam: naive-UTC column value -> aware America/Chicago.

    Deliberately NOT utils.time.to_ct: that module transitively imports the
    frozen worldcup package, which re-enters utils.time when the docket
    package loads first (the models/__init__.py re-export) — an import
    cycle. The Jinja ``ct`` filter is unaffected (registered at app boot).
    """
    return dt.replace(tzinfo=UTC).astimezone(CT)


def _ordinal(n):
    """1 -> '1st'. The teens are the exception every naive version gets
    wrong: 11th, 12th, 13th, not 11st/12nd/13rd."""
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


@docket_bp.context_processor
def inject_docket_globals():
    docket_enrollment = None
    if current_user.is_authenticated:
        docket_enrollment = get_enrollment(current_user.id)
    return {
        'body_class': 'game-docket',
        'docket_enrollment': docket_enrollment,
        'docket_season_year': SEASON_YEAR,
        'docket_entry_fee': current_app.config.get('DOCKET_ENTRY_FEE', 25),
        'docket_sport_labels': SPORT_LABELS,
    }


@docket_bp.before_request
def before_request():
    """Blueprint-pattern hook; The Docket has no request-time refresh work
    (line import and grading run via CLI/timers, T8+)."""


# --------------------------------------------------------------------------
# Enrollment
# --------------------------------------------------------------------------

@docket_bp.route('/join', methods=['GET', 'POST'])
@login_required
@game_must_be_open('docket')
def join():
    """Enrollment page for The Docket."""
    existing = get_enrollment(current_user.id)
    if existing:
        flash('You are already on the docket.', 'info')
        return redirect(url_for('docket.index'))

    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()[:80]
        enrollment = DocketEnrollment(
            user_id=current_user.id,
            season_year=SEASON_YEAR,
            display_name=display_name or None,
        )
        db.session.add(enrollment)
        try:
            db.session.commit()
        except IntegrityError:
            # Concurrent double-submit: the unique (user, season) constraint
            # is the backstop — the first POST won, this one is a no-op.
            # Anything else (no row appeared) is a real failure: re-raise.
            db.session.rollback()
            if get_enrollment(current_user.id) is None:
                raise
        flash('Welcome to The Docket. Court is in session.', 'success')
        return redirect(url_for('docket.index'))

    return render_template('docket/join.html')


# --------------------------------------------------------------------------
# The pick sheet
# --------------------------------------------------------------------------

@docket_bp.route('/')
@enrollment_required('docket')
def index():
    """The weekly pick sheet — the room's index.

    The slate is a court calendar: one day of cases at a time, navigated by
    day-tab links (``?day=YYYY-MM-DD``, the CT calendar date). Server-side
    tabs keep the no-JS spine intact; the sheet rail persists across days.
    """
    week = picks_service.current_week()
    if week is None:
        # Pre-season (or between-season) empty state; the date derives from
        # the week math, never hardcoded prose.
        season_opens_label = WEEK_1_BOUNDARY_LOCAL.strftime('%B %-d')
        return render_template(
            'docket/sheet.html',
            week=None,
            days=[],
            active_day=None,
            sheet=None,
            held={},
            designated=None,
            season_opens_label=season_opens_label,
        )

    games = (
        DocketGame.query.filter_by(week_id=week.id)
        .order_by(DocketGame.kickoff, DocketGame.api_event_id)
        .all()
    )
    sheet = picks_service.sheet_state(current_user.id, week)
    held = {(p['game_id'], p['market']): p for p in sheet['picks']}
    slot_map = {p['slot']: p for p in sheet['picks']}
    locked_ids = set(sheet['locked_game_ids'])

    # Group by CT calendar day in the route (never Jinja sort/group).
    days: list[dict] = []
    for game in games:
        kickoff_ct = _kickoff_ct(game.kickoff)
        key = kickoff_ct.date().isoformat()
        if not days or days[-1]['key'] != key:
            days.append({
                'key': key,
                'label': kickoff_ct.strftime('%A, %B %-d'),
                'tab_label': kickoff_ct.strftime('%a %-m/%-d'),
                'games': [],
                'sessions': [],
            })
        days[-1]['games'].append(game)

    # Court sessions: kickoff waves inside a day (morning < noon CT,
    # afternoon < 5 PM, evening after). Keeps the 60-case Saturday orderly;
    # a day with a single session renders no sub-heads.
    for day in days:
        for game in day['games']:
            hour = _kickoff_ct(game.kickoff).hour
            if hour < 12:
                label = 'Morning session'
            elif hour < 17:
                label = 'Afternoon session'
            else:
                label = 'Evening session'
            if not day['sessions'] or day['sessions'][-1][0] != label:
                day['sessions'].append((label, []))
            day['sessions'][-1][1].append(game)

    # Active day: the requested tab if it exists, else the first day still
    # holding an unlocked case, else the last day.
    requested = request.args.get('day')
    active_day = None
    if requested:
        active_day = next((d for d in days if d['key'] == requested), None)
    if active_day is None:
        active_day = next(
            (d for d in days
             if any(g.id not in locked_ids for g in d['games'])),
            days[-1] if days else None,
        )

    designated = week.tiebreaker_game
    tb_locked = bool(
        designated is not None
        and (designated.id in locked_ids or sheet['deadline_passed'])
    )

    return render_template(
        'docket/sheet.html',
        week=week,
        days=days,
        active_day=active_day,
        sheet=sheet,
        held=held,
        slot_map=slot_map,
        backup_slot=BACKUP_SLOT,
        games_by_id={g.id: g for g in games},
        designated=designated,
        tb_locked=tb_locked,
        season_opens_label=None,
    )


# --------------------------------------------------------------------------
# Sheet mutations (POST-only; PRG for forms, sheet-state JSON for fetch)
# --------------------------------------------------------------------------

def _wants_json() -> bool:
    return 'application/json' in request.headers.get('Accept', '')


def _back_to_sheet():
    """PRG target preserving the day tab the form was submitted from."""
    day = request.form.get('day') or None
    return redirect(url_for('docket.index', day=day))


def _sheet_error(err: PickError):
    if _wants_json():
        payload = {'ok': False, 'error': err.code, 'message': err.message}
        return jsonify(payload), err.status
    flash(err.message, 'error' if err.status == 400 else 'warning')
    return _back_to_sheet()


def _sheet_success(week, message=None):
    if _wants_json():
        return jsonify({
            'ok': True,
            'sheet': picks_service.sheet_state(current_user.id, week),
        })
    if message:
        flash(message, 'success')
    return _back_to_sheet()


@docket_bp.route('/picks/set', methods=['POST'])
@enrollment_required('docket')
def set_pick():
    """Add a pick, or move a held market to its other side."""
    week = picks_service.current_week()
    try:
        picks_service.set_pick(
            current_user.id,
            week,
            game_id=request.form.get('game_id', type=int),
            market=request.form.get('market', ''),
            side=request.form.get('side', ''),
            backup=request.form.get('backup') == '1',
        )
    except PickError as err:
        return _sheet_error(err)
    return _sheet_success(week, 'Pick recorded.')


@docket_bp.route('/picks/remove', methods=['POST'])
@enrollment_required('docket')
def remove_pick():
    """Withdraw an unlocked pick; its slot stays open in place."""
    week = picks_service.current_week()
    try:
        picks_service.remove_pick(
            current_user.id,
            week,
            game_id=request.form.get('game_id', type=int),
            market=request.form.get('market', ''),
        )
    except PickError as err:
        return _sheet_error(err)
    return _sheet_success(week, 'Pick withdrawn.')


@docket_bp.route('/best', methods=['POST'])
@enrollment_required('docket')
def set_best():
    """Set, move, or clear the headliner designation."""
    week = picks_service.current_week()
    try:
        if request.form.get('clear') == '1':
            picks_service.clear_best(current_user.id, week)
            message = 'Headliner cleared.'
        else:
            picks_service.set_best(
                current_user.id,
                week,
                game_id=request.form.get('game_id', type=int),
                market=request.form.get('market', ''),
            )
            message = 'Headliner set.'
    except PickError as err:
        return _sheet_error(err)
    return _sheet_success(week, message)


@docket_bp.route('/tiebreaker', methods=['POST'])
@enrollment_required('docket')
def set_tiebreaker():
    """Submit (or clear, on empty input) the combined-score prediction."""
    week = picks_service.current_week()
    try:
        row = picks_service.set_tiebreaker(
            current_user.id, week, request.form.get('prediction', ''))
    except PickError as err:
        return _sheet_error(err)
    message = 'Prediction recorded.' if row is not None else 'Prediction cleared.'
    return _sheet_success(week, message)


# --------------------------------------------------------------------------
# The season ledger
# --------------------------------------------------------------------------

@docket_bp.route('/ledger')
@enrollment_required('docket')
def ledger():
    """The season ledger: where every filed sheet ends up.

    Reads the persisted rollup through the season pass (D14-eng) and renders
    it. Nothing is computed here: rank, the drop, and every charged week come
    from the pure engine, so the page and `flask docket recalc` can never tell
    different stories.
    """
    ledger = season_ledger()
    # Presentation derived in the route, never in Jinja (the room's rule).
    # A shared rank is stated out loud: competition rank otherwise shows two
    # players as "2" with nothing saying why.
    counts = Counter(row.standing.rank for row in ledger.rows)
    shared_ranks = {rank for rank, n in counts.items() if n > 1}
    your_row = None
    if current_user.is_authenticated:
        your_row = next((row for row in ledger.rows
                         if row.enrollment.user_id == current_user.id), None)
    return render_template(
        'docket/ledger.html',
        ledger=ledger,
        shared_ranks=shared_ranks,
        your_row=your_row,
        your_rank_label=_ordinal(your_row.standing.rank) if your_row else None,
        season_opens_label=WEEK_1_BOUNDARY_LOCAL.strftime('%B %-d'),
    )


# --------------------------------------------------------------------------
# The published rules
# --------------------------------------------------------------------------

@docket_bp.route('/rules')
def rules():
    """The rulebook. Public, so a prospective member can read the terms
    before joining (the worldcup.rules shape).

    Every number comes from the engine, the week math, or config — never a
    literal in the template. A rules page that restates the scoring as prose
    is a rules page that will eventually be wrong. D17-eng (bookmaker
    provenance) and D23-eng (overtime and NFL ties) both say "on the rules
    page" in as many words; they are requirements, not decoration.
    """
    scoring = [
        ('A verdict (win)', slot_points(Outcome.WIN, doubled=False),
         slot_points(Outcome.WIN, doubled=True)),
        ('A mistrial (push)', slot_points(Outcome.PUSH, doubled=False),
         slot_points(Outcome.PUSH, doubled=True)),
        ('A loss', slot_points(Outcome.LOSS, doubled=False),
         slot_points(Outcome.LOSS, doubled=True)),
    ]
    # The perfect week, derived: seven ordinary wins plus the doubled one.
    max_week = ((SCORING_SLOTS - 1) * slot_points(Outcome.WIN, doubled=False)
                + slot_points(Outcome.WIN, doubled=True))
    return render_template(
        'docket/rules.html',
        scoring=scoring,
        max_week=max_week,
        scoring_slots=SCORING_SLOTS,
        backup_slot=BACKUP_SLOT,
        total_weeks=TOTAL_WEEKS,
        bookmakers=[BOOKMAKER_LABELS.get(key, key)
                    for key in BOOKMAKER_PRIORITY],
    )


# The admin desk (the gate included) lives in games/docket/admin_routes.py.
