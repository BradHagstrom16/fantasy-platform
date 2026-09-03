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
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from extensions import db

# Display-only conference lookup for the sheet's filter chips (design review
# 2026-08-19): the CFB master list is keyed by the exact Odds-API participant
# names DocketGame stores. Game identity stays api_event_id (D22 — this is
# render-time classification, never matching); an unmapped name fails open.
from games.cfb.constants import TEAM_CONFERENCES, TEAM_NAME_MAP
from games.common import enrollment_required, game_must_be_open
from games.docket.blueprint import docket_bp
from games.docket.models import DocketEnrollment, DocketGame
from games.docket.services import picks as picks_service
from games.docket.services.bridge_sheet import SPORT_LABELS
from games.docket.services.enrollment import get_enrollment
from games.docket.services.grading.engine import slot_points
from games.docket.services.grading.snapshots import BACKUP_SLOT, SCORING_SLOTS, Outcome
from games.docket.services.importer import BOOKMAKER_LABELS, BOOKMAKER_PRIORITY
from games.docket.services.payment import payment_nudge_for
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


_NCAAF = 'americanfootball_ncaaf'

# The find field's haystack words for a sport: the label plus the plain
# words a member types ("pros" was the ask that prompted the field).
_SPORT_SEARCH_WORDS = {
    _NCAAF: 'CFB college NCAA',
    'americanfootball_nfl': 'NFL pro pros',
}
FIND_QUERY_MAX = 60


def _game_conferences(game) -> set[str]:
    """The conferences a CFB case belongs to, by either side's mapped name.

    Display-only (the filter chips); NFL cases classify to nothing and are
    never filtered. An FCS visitor with no mapping classifies by its mapped
    opponent, so a case never vanishes just because one side is obscure."""
    if game.sport != _NCAAF:
        return set()
    confs = set()
    for name in (game.home_team, game.away_team):
        conf = TEAM_CONFERENCES.get(TEAM_NAME_MAP.get(name, ''))
        if conf:
            confs.add(conf)
    return confs


def _conf_slug(name: str) -> str:
    return name.lower().replace(' ', '-')


def _find_query(raw: str | None) -> str:
    """Normalize the find field: collapse whitespace, cap the length."""
    return ' '.join((raw or '').split())[:FIND_QUERY_MAX].strip()


def _case_matches(game, tokens: list[str]) -> bool:
    """Every typed word appears somewhere on the case: either team, the
    sport's search words, a conference name (display-only, D22), or the
    CT day's name ("sunday" is the pro slate in one word)."""
    haystack = ' '.join([
        game.away_team,
        game.home_team,
        _SPORT_SEARCH_WORDS.get(game.sport, SPORT_LABELS.get(game.sport, '')),
        _kickoff_ct(game.kickoff).strftime('%A'),
        *sorted(_game_conferences(game)),
    ]).casefold()
    return all(token in haystack for token in tokens)


def _group_by_day(games: list) -> list[dict]:
    """Bucket kickoff-sorted games by CT calendar day, each day carrying
    its session waves. In the route, never Jinja sort/group."""
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
    for day in days:
        day['sessions'] = _sessions_for(day['games'])
    return days


def _sessions_for(games: list) -> list[tuple[str, list]]:
    """Court sessions: kickoff waves inside a day (morning < noon CT,
    afternoon < 5 PM, evening after). Keeps the 60-case Saturday orderly;
    a day with a single session renders no sub-heads."""
    sessions: list[tuple[str, list]] = []
    for game in games:
        hour = _kickoff_ct(game.kickoff).hour
        if hour < 12:
            label = 'Morning session'
        elif hour < 17:
            label = 'Afternoon session'
        else:
            label = 'Evening session'
        if not sessions or sessions[-1][0] != label:
            sessions.append((label, []))
        sessions[-1][1].append(game)
    return sessions


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
        'docket_entry_fee': current_app.config.get('DOCKET_ENTRY_FEE', 60),
        'docket_sport_labels': SPORT_LABELS,
        # "Settle the Tab": available to every Docket template but only
        # renders where templates/_settle_tab.html is included (sheet, ledger).
        'payment_nudge': payment_nudge_for(
            docket_enrollment, getattr(current_user, 'is_admin', False)),
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
        # No per-pool name: the member stands under their one platform
        # display name (ADR-057), edited on /profile.
        enrollment = DocketEnrollment(
            user_id=current_user.id,
            season_year=SEASON_YEAR,
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
    preview = False
    if week is None:
        # Pre-season posted-docket preview (2026-08-19 ruling): once a
        # future week has been imported, members read the frozen board
        # before court convenes. Display only — every mutation resolves
        # through current_week() and _require_open_week, both still closed.
        week = picks_service.upcoming_week()
        preview = week is not None

    games = []
    if week is not None:
        games = db.session.scalars(
            select(DocketGame).filter_by(week_id=week.id)
            .order_by(DocketGame.kickoff, DocketGame.api_event_id)).all()

    if week is None or (preview and not games):
        # Pre-season (or between-season) empty state; the date derives from
        # the week math, never hardcoded prose. An imported-but-empty future
        # week reads the same as no docket at all.
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
            preview=False,
            find_query='',
            sheet_return={},
        )
    sheet = picks_service.sheet_state(current_user.id, week)
    held = {(p['game_id'], p['market']): p for p in sheet['picks']}
    slot_map = {p['slot']: p for p in sheet['picks']}
    locked_ids = set(sheet['locked_game_ids'])

    days = _group_by_day(games)
    find_query = _find_query(request.args.get('q'))

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

    # The index (design review 2026-09-02): the find field is week-wide,
    # so a member who knows the team but not the day still finds the case.
    # A plain GET (?q=) on the no-JS spine, navigation never mutation, like
    # the chips; the day param is only the way back ("All cases"). While a
    # query is in force the day-scoped aids (chips, session jumps) step
    # aside and no day tab is current.
    find_days: list[dict] = []
    find_total = 0
    return_day = None
    if find_query:
        tokens = find_query.casefold().split()
        find_days = _group_by_day(
            [g for g in games if _case_matches(g, tokens)])
        find_total = sum(len(d['games']) for d in find_days)
        if requested and any(d['key'] == requested for d in days):
            return_day = requested

    # Conference chips (design review 2026-08-19): day-scoped, so a chip
    # always yields at least one case and the empty filtered view is
    # unreachable. Chips are plain GET links (?conf=), never forms — the
    # filter is navigation, so it works identically in preview, open,
    # locked, and closed states. Day-tab links drop the param (switching
    # day resets the filter); an unknown slug falls back to unfiltered.
    conf_counts: Counter[str] = Counter()
    if active_day is not None and not find_query:
        for game in active_day['games']:
            conf_counts.update(_game_conferences(game))
    conferences = [
        {'name': name, 'slug': _conf_slug(name), 'count': count}
        for name, count in sorted(
            conf_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]
    active_conf = None
    requested_conf = request.args.get('conf')
    if requested_conf and active_day is not None:
        active_conf = next(
            (c for c in conferences if c['slug'] == requested_conf), None)
    day_case_total = len(active_day['games']) if active_day else 0
    if active_conf is not None:
        filtered = [
            g for g in active_day['games']
            if g.sport != _NCAAF
            or active_conf['name'] in _game_conferences(g)
        ]
        active_day = {
            **active_day,
            'games': filtered,
            'sessions': _sessions_for(filtered),
        }

    designated = week.tiebreaker_game
    tb_locked = bool(
        designated is not None
        and (designated.id in locked_ids or sheet['deadline_passed'])
    )

    # The return fields: the view every mutation form was submitted from,
    # carried as hidden inputs so the PRG redirect lands back on it
    # (_back_to_sheet reads the same keys).
    if find_query:
        sheet_return = {'day': return_day, 'q': find_query}
    else:
        sheet_return = {
            'day': active_day['key'] if active_day else None,
            'conf': active_conf['slug'] if active_conf else None,
        }

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
        preview=preview,
        conferences=conferences,
        active_conf=active_conf,
        day_case_total=day_case_total,
        find_query=find_query,
        find_days=find_days,
        find_total=find_total,
        week_case_total=len(games),
        sheet_return=sheet_return,
    )


# --------------------------------------------------------------------------
# Sheet mutations (POST-only; PRG for forms, sheet-state JSON for fetch)
# --------------------------------------------------------------------------

def _wants_json() -> bool:
    return 'application/json' in request.headers.get('Accept', '')


def _back_to_sheet():
    """PRG target preserving the view the form was submitted from: the
    day tab, its conference filter, and the find query (the return fields
    every mutation form carries via docket/_return_fields.html)."""
    view = {key: request.form.get(key) or None for key in ('day', 'conf', 'q')}
    return redirect(url_for('docket.index', **view))


def _sheet_error(err: PickError):
    if _wants_json():
        payload = {'ok': False, 'error': err.code, 'message': err.message}
        return jsonify(payload), err.status
    flash(err.message, 'error' if err.status == 400 else 'warning')
    return _back_to_sheet()


def _sheet_success(week, action):
    """Confirm a mutation in words: what just happened plus what the sheet
    asks for next (one message for the flash and the JSON toast, built from
    the same sheet state the client repaints from)."""
    state = picks_service.sheet_state(current_user.id, week)
    message = f"{action} {state['next_step']['ask']}".strip()
    if _wants_json():
        return jsonify({'ok': True, 'message': message, 'sheet': state})
    flash(message, 'success')
    return _back_to_sheet()


@docket_bp.route('/picks/set', methods=['POST'])
@enrollment_required('docket')
def set_pick():
    """Add a pick, or move a held market to its other side."""
    week = picks_service.current_week()
    try:
        pick = picks_service.set_pick(
            current_user.id,
            week,
            game_id=request.form.get('game_id', type=int),
            market=request.form.get('market', ''),
            side=request.form.get('side', ''),
            backup=request.form.get('backup') == '1',
        )
    except PickError as err:
        return _sheet_error(err)
    if pick.slot == BACKUP_SLOT:
        action = ('Filed as your reserve. It only plays if a case is '
                  'thrown out.')
    else:
        action = f'Filed, slot {pick.slot}.'
    return _sheet_success(week, action)


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
    return _sheet_success(week, 'Pick removed.')


@docket_bp.route('/best', methods=['POST'])
@enrollment_required('docket')
def set_best():
    """Set, move, or clear the headliner designation."""
    week = picks_service.current_week()
    try:
        if request.form.get('clear') == '1':
            picks_service.clear_best(current_user.id, week)
            action = 'x2 cleared.'
        else:
            row = picks_service.set_best(
                current_user.id,
                week,
                game_id=request.form.get('game_id', type=int),
                market=request.form.get('market', ''),
            )
            action = f'x2 set: {picks_service.describe_pick(row)}.'
    except PickError as err:
        return _sheet_error(err)
    return _sheet_success(week, action)


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
    if row is not None:
        action = (f'Number saved: '
                  f'{picks_service.format_tenths(row.prediction_tenths)}.')
    else:
        action = 'Number cleared.'
    return _sheet_success(week, action)


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
