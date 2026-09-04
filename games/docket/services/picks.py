"""The Docket pick service — every binding sheet rule lands here.

Write path for DocketPick / DocketTiebreakerPrediction: the routes stay
declarative and this module owns validation order, the line snapshot,
slot assignment, lock enforcement, and commits (exactly one per public
function). The pure grading engine never sees any of this; it grades the
rows these functions write.

Rules enforced (2026-08-11 design SSoT):

- Deadline is strict: a mutation at exactly ``deadline_at`` is late.
- Per-game kickoff lock: ``now >= kickoff`` freezes held picks on that game
  and closes its markets (Big Noon kickoffs agree with the deadline rule by
  construction, no special case).
- One side per market, structurally: re-picking a held market's other side
  moves the pick in place (same slot); it never creates a second row.
- Slots: scoring picks fill the lowest free slot 1-8; removing a pick
  leaves a gap (autopick fills gaps ascending by contract, renumbering
  would mutate kickoff-locked rows, and slot order at the deadline drives
  same-instant No Contest substitution determinism). The backup is slot 9,
  always explicit, never overflow.
- Line snapshot parity (models.py contract): ``line_value``/``book`` are
  copied from the game's locked market at creation, never from any client
  input, and a side flip does not re-snapshot.
- Headliner (best pick): never slot 9; never set onto a kicked-off market;
  frozen once its own game kicks off.
- Tiebreaker: integer tenths end-to-end (D20), pure string parsing, locked
  at min(deadline, designated kickoff); an empty submission clears the row
  so the grading-time default rule applies.

Datetime contract: naive UTC everywhere (D6). ``now_naive()`` is the one
"now" in this module; every comparison is naive-vs-naive column math.
"""
from datetime import UTC, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from extensions import db
from games.docket.models import (
    DocketGame,
    DocketPick,
    DocketTiebreakerPrediction,
    DocketWeek,
)
from games.docket.services.grading.snapshots import (
    BACKUP_SLOT,
    SCORING_SLOTS,
    Market,
    Side,
)
from games.docket.services.weeks import CT
from games.docket.utils import now_utc, to_naive_utc

# Legal sides per market. The engine enforces the same pairing at its own
# boundary (snapshots.PickSnapshot construction); both derive from the one
# Market/Side enum pair, so they cannot drift independently.
SIDES_FOR_MARKET = {
    Market.SPREAD: frozenset({Side.HOME, Side.AWAY}),
    Market.TOTAL: frozenset({Side.OVER, Side.UNDER}),
}

# Combined-score predictions above this are a dropped decimal ("515" for
# 51.5), not an opinion: no football game has combined for 200 points.
MAX_PREDICTION_TENTHS = 2000

# The ask escalates inside this window before the deadline (DESIGN.md 2.2:
# "escalation only near the deadline").
URGENT_HOURS = 6

# The deadline, said the way every sheet surface says it.
CLOSE_LABEL = 'Saturday 11:00 AM CT'

# The rungs on which the sheet is filed: nothing is owed but the optional
# reserve. They take the complete tint and never the urgent countdown.
FILED_STAGES = ('reserve', 'complete')


class PickError(Exception):
    """A refused sheet mutation, in user-facing terms.

    ``code`` is the stable machine key (JSON clients branch on it),
    ``message`` is the flash/JSON text, ``status`` is the HTTP status the
    route should answer with: 409 = legal request refused by state,
    400 = input the sheet UI cannot produce.
    """

    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def now_naive():
    """The module's single clock: seam-aware now, stripped to naive UTC."""
    return to_naive_utc(now_utc())


def current_week(now=None) -> DocketWeek | None:
    """The week containing now, or None outside the season/import window."""
    if now is None:
        now = now_naive()
    return DocketWeek.query.filter(
        DocketWeek.start_at <= now, DocketWeek.end_at > now
    ).first()


def upcoming_week(now=None) -> DocketWeek | None:
    """The next not-yet-started week, if one has been imported.

    Read only by the pre-season posted-docket preview (2026-08-19 ruling):
    the sheet shows the frozen board before court convenes. Every mutation
    still resolves through current_week(), which stays None until the start
    boundary, so nothing pickable can ever come from here."""
    if now is None:
        now = now_naive()
    return db.session.scalars(
        select(DocketWeek).filter(DocketWeek.start_at > now)
        .order_by(DocketWeek.start_at)).first()


def game_locked(game: DocketGame, now) -> bool:
    """Kickoff lock: t >= kickoff freezes the case (live kickoff column;
    ``kickoff_at_deadline`` is the grading pass's frozen copy, never read
    here)."""
    return now >= game.kickoff


def locked_line(game: DocketGame, market: Market) -> tuple[float, str] | None:
    """The game's frozen (value, book) for a market, or None if unposted.

    A market exists only when both the number and its bookmaker are locked;
    the pair is what set_pick snapshots onto the pick row.
    """
    if market is Market.SPREAD:
        if game.home_spread is not None and game.spread_book:
            return game.home_spread, game.spread_book
        return None
    if game.total_points is not None and game.total_book:
        return game.total_points, game.total_book
    return None


def _parse_market(raw) -> Market:
    try:
        return Market(raw)
    except ValueError:
        raise PickError('invalid', 'Unknown market.', status=400) from None


def _parse_side(raw, market: Market) -> Side:
    try:
        side = Side(raw)
    except ValueError:
        raise PickError('invalid', 'Unknown side.', status=400) from None
    if side not in SIDES_FOR_MARKET[market]:
        raise PickError('invalid', 'That side does not belong to that market.',
                        status=400)
    return side


def _require_open_week(week: DocketWeek | None, now) -> None:
    if week is None:
        raise PickError('no_active_week', 'No docket is open right now.')
    if now >= week.deadline_at:
        raise PickError('deadline_passed',
                        'The docket closed Saturday at 11:00 AM CT.')


def _get_week_game(week: DocketWeek, game_id, now) -> DocketGame:
    game = db.session.get(DocketGame, game_id) if game_id else None
    if game is None or game.week_id != week.id:
        raise PickError('invalid', 'Unknown case on this docket.', status=400)
    return game


def _market_row(user_id: int, week: DocketWeek, game_id: int,
                market: Market) -> DocketPick | None:
    return DocketPick.query.filter_by(
        user_id=user_id, week_id=week.id, game_id=game_id,
        market=market.value,
    ).first()


def set_pick(user_id: int, week: DocketWeek, game_id, market, side,
             backup: bool = False) -> DocketPick:
    """Create or move a pick: one side of one market on one case.

    Existing row on the same market: same side is an idempotent no-op;
    the other side moves the pick in place (slot, headliner designation,
    and line snapshot unchanged; ``backup`` is ignored because the slot is
    already assigned). New row: lowest free scoring slot, or slot 9 when
    ``backup`` is set.
    """
    now = now_naive()
    _require_open_week(week, now)
    game = _get_week_game(week, game_id, now)
    market = _parse_market(market)
    line = locked_line(game, market)
    if line is None:
        raise PickError('no_line', 'No line is posted for that market.')
    side = _parse_side(side, market)
    if game_locked(game, now):
        raise PickError('game_locked',
                        'That case locked at kickoff. Your other picks are safe.')

    existing = _market_row(user_id, week, game.id, market)
    if existing is not None:
        if existing.side == side.value:
            return existing
        existing.side = side.value
        existing.is_autopick = False
        db.session.commit()
        return existing

    taken = {
        p.slot for p in DocketPick.query.filter_by(
            user_id=user_id, week_id=week.id).all()
    }
    if backup:
        if BACKUP_SLOT in taken:
            raise PickError('backup_taken',
                            'You already hold a case in reserve.')
        slot = BACKUP_SLOT
    else:
        free = sorted(set(range(1, SCORING_SLOTS + 1)) - taken)
        if not free:
            if BACKUP_SLOT in taken:
                raise PickError(
                    'sheet_full',
                    'Your sheet is full: eight sides plus a reserve. '
                    'Remove a pick to swap this one in.')
            raise PickError(
                'sheet_full',
                'All eight scoring slots are filled. Remove a pick, '
                'or file this one as your reserve.')
        slot = free[0]

    value, book = line
    pick = DocketPick(
        user_id=user_id,
        week_id=week.id,
        game_id=game.id,
        market=market.value,
        side=side.value,
        slot=slot,
        is_best=False,
        is_autopick=False,
        line_value=value,
        book=book,
    )
    db.session.add(pick)
    try:
        db.session.commit()
    except IntegrityError:
        # Double submit or a concurrent tab: the constraints are the
        # backstop. If the row that won matches this request, report success.
        db.session.rollback()
        existing = _market_row(user_id, week, game.id, market)
        if existing is not None:
            if existing.side == side.value:
                return existing
            raise PickError(
                'conflict',
                'That pick was already recorded. Refresh the sheet.'
            ) from None
        # Market still free: a concurrent add claimed the slot instead
        # (uq_docket_pick_slot). Nothing was recorded; a retry recomputes
        # the lowest free slot and succeeds.
        raise PickError('slot_taken',
                        'The sheet moved under you. Try that pick again.'
                        ) from None
    return pick


def remove_pick(user_id: int, week: DocketWeek, game_id, market) -> None:
    """Withdraw a pick. Its slot stays open in place (gaps are real)."""
    now = now_naive()
    _require_open_week(week, now)
    market = _parse_market(market)
    row = _market_row(user_id, week, game_id, market) if game_id else None
    if row is None:
        raise PickError('invalid', 'No such pick on your sheet.', status=400)
    if game_locked(row.game, now):
        raise PickError('game_locked',
                        'That case locked at kickoff; the pick stands.')
    db.session.delete(row)
    db.session.commit()


def set_best(user_id: int, week: DocketWeek, game_id, market) -> DocketPick:
    """Designate the headliner (worth double) on a held pick.

    Never slot 9; never onto a kicked-off case; frozen once the current
    headliner's own game kicks off (the designation locks with its pick).
    """
    now = now_naive()
    _require_open_week(week, now)
    market = _parse_market(market)
    row = _market_row(user_id, week, game_id, market) if game_id else None
    if row is None:
        raise PickError('invalid', 'No such pick on your sheet.', status=400)
    if row.slot == BACKUP_SLOT:
        raise PickError('best_on_backup',
                        'The reserve cannot be the headliner.')
    if game_locked(row.game, now):
        raise PickError('game_locked',
                        'That case has kicked off; the headliner cannot '
                        'move onto it.')
    current = DocketPick.query.filter_by(
        user_id=user_id, week_id=week.id
    ).filter(DocketPick.is_best.is_(True)).first()
    if current is not None:
        if current.id == row.id:
            return row
        if game_locked(current.game, now):
            raise PickError('best_locked',
                            'Your headliner locked at its kickoff.')
        # Clear before set, flushed in between: the partial unique index is
        # statement-time on Postgres, so set-before-clear would refuse.
        current.is_best = False
        current.is_auto_best = False
        db.session.flush()
    row.is_best = True
    # A designation the player moves is theirs, whatever put it there first
    # (a forced deadline pass in development can auto-designate pre-deadline).
    row.is_auto_best = False
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise PickError('conflict',
                        'The headliner changed elsewhere. Refresh the sheet.'
                        ) from None
    return row


def clear_best(user_id: int, week: DocketWeek) -> None:
    """Remove the headliner designation (idempotent).

    Legal pre-kickoff; at the deadline auto-designation covers an unset
    headliner, so clearing is never a trap.
    """
    now = now_naive()
    _require_open_week(week, now)
    current = DocketPick.query.filter_by(
        user_id=user_id, week_id=week.id
    ).filter(DocketPick.is_best.is_(True)).first()
    if current is None:
        return
    if game_locked(current.game, now):
        raise PickError('best_locked',
                        'Your headliner locked at its kickoff.')
    current.is_best = False
    current.is_auto_best = False
    db.session.commit()


def parse_prediction_tenths(raw: str) -> int:
    """Parse a combined-score prediction ("51.5", "51") to integer tenths.

    Pure string/int arithmetic: no float ever enters key 3 (D20). At most
    one decimal digit; negatives, bare fractions, and trailing dots refuse.
    """
    s = raw.strip()
    whole, dot, frac = s.partition('.')
    # isdecimal, not isdigit: isdigit() accepts superscripts ('²') that
    # int() then refuses, which would surface as a 500 instead of a 400.
    if not whole.isdecimal() or (dot and (len(frac) != 1
                                          or not frac.isdecimal())):
        raise PickError('invalid',
                        'Enter a combined score like 51.5.', status=400)
    tenths = int(whole) * 10 + (int(frac) if dot else 0)
    if tenths > MAX_PREDICTION_TENTHS:
        raise PickError(
            'invalid',
            'That looks high for a combined score. Enter it like 51.5.',
            status=400)
    return tenths


def set_tiebreaker(user_id: int, week: DocketWeek,
                   raw: str) -> DocketTiebreakerPrediction | None:
    """Upsert (or clear, on empty input) the tiebreaker prediction.

    Locked at min(deadline, designated kickoff) so nobody predicts a score
    already in progress. Clearing restores the grading-time default (the
    designated game's locked total).
    """
    now = now_naive()
    _require_open_week(week, now)
    designated = week.tiebreaker_game
    if designated is None:
        raise PickError('invalid',
                        'No tiebreaker case is designated yet.')
    lock_at = min(week.deadline_at, designated.kickoff)
    if now >= lock_at:
        raise PickError('prediction_locked',
                        'The tiebreaker locked at kickoff.')
    row = DocketTiebreakerPrediction.query.filter_by(
        user_id=user_id, week_id=week.id).first()
    if not raw or not raw.strip():
        if row is not None:
            db.session.delete(row)
            db.session.commit()
        return None
    tenths = parse_prediction_tenths(raw)
    if row is not None:
        row.prediction_tenths = tenths
        db.session.commit()
        return row
    row = DocketTiebreakerPrediction(
        user_id=user_id, week_id=week.id, prediction_tenths=tenths)
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        row = DocketTiebreakerPrediction.query.filter_by(
            user_id=user_id, week_id=week.id).first()
        if row is None:
            raise PickError('conflict',
                            'The prediction changed elsewhere. Refresh the '
                            'sheet.') from None
        row.prediction_tenths = tenths
        db.session.commit()
    return row


def format_tenths(tenths: int) -> str:
    """Render integer tenths for display ("515" -> "51.5") without floats."""
    return f'{tenths // 10}.{tenths % 10}'


def describe_pick(pick: DocketPick) -> str:
    """'Utah Utes -3.5' / 'Over 51.5': a pick as its own snapshot reads."""
    game = pick.game
    if pick.market == Market.SPREAD.value:
        is_home = pick.side == Side.HOME.value
        team = game.home_team if is_home else game.away_team
        if pick.line_value == 0:
            return f'{team} PK'
        num = pick.line_value if is_home else -pick.line_value
        return f'{team} {num:+g}'
    side = 'Over' if pick.side == Side.OVER.value else 'Under'
    return f'{side} {pick.line_value:g}'


def _closes_in(delta: timedelta) -> str:
    total = max(0, int(delta.total_seconds() // 60))
    hours, minutes = divmod(total, 60)
    return f'{hours}h {minutes}m' if hours else f'{minutes}m'


def _number_open(week: DocketWeek, now) -> bool:
    designated = week.tiebreaker_game
    if designated is None:
        return False
    return now < min(week.deadline_at, designated.kickoff)


def next_step(state: dict, week: DocketWeek, now=None) -> dict:
    """What the sheet asks for next, in one sentence, by priority.

    The sheet's facts (n of 8, headliner, number, reserve) were always
    visible; the critique of 2026-09-01 found they never named an action.
    This is the one ask, rendered in the bar, the drawer, and the rail so
    the three cannot disagree, and appended to every success message.

    Ladder: sides -> x2 -> number (only while a tiebreaker case is
    designated and unlocked) -> reserve (optional) -> complete. Preview and
    closed weeks get their own rung. Inside URGENT_HOURS the ask is prefixed
    with the time left. Never routes reminders.outstanding(): that prose is
    the email's and is locked separately.
    """
    if now is None:
        now = now_naive()
    if now < week.start_at:
        opens = week.start_at.replace(tzinfo=UTC).astimezone(CT)
        return {'stage': 'preview',
                'ask': f"Picks open {opens.strftime('%A, %B %-d')}.",
                'urgent': False, 'remaining': SCORING_SLOTS}
    if now >= week.deadline_at:
        return {'stage': 'closed',
                'ask': 'The docket is closed. Verdicts to follow.',
                'urgent': False, 'remaining': 0}

    n = state['scoring_count']
    remaining = max(0, SCORING_SLOTS - n)
    if n == 0:
        stage, ask = 'blank', f'Tap {SCORING_SLOTS} sides to fill your sheet.'
    elif remaining:
        plural = '' if remaining == 1 else 's'
        stage, ask = 'sides', f'{remaining} more side{plural} to pick.'
    elif state['best'] is None:
        stage, ask = 'x2', (f'All {SCORING_SLOTS} held. Now pick your x2: '
                            'it scores double.')
    elif state['prediction'] is None and _number_open(week, now):
        stage, ask = 'number', 'Now your number: predict the tiebreaker score.'
    elif state['backup'] is None:
        # The reserve is optional (DESIGN.md 1.5), so this rung leads with
        # the confirmation: the member is done, the reserve is an offer.
        stage, ask = 'reserve', ('Sheet filed. A reserve is optional: tap one '
                                 'more side to hold one.')
    else:
        stage, ask = 'complete', f'Sheet filed. Change anything until {CLOSE_LABEL}.'

    left = week.deadline_at - now
    # A filed sheet is never late, with or without the optional reserve.
    urgent = (stage not in FILED_STAGES
              and left < timedelta(hours=URGENT_HOURS))
    if urgent:
        ask = f'Closes in {_closes_in(left)}. {ask}'
    return {'stage': stage, 'ask': ask, 'urgent': urgent,
            'remaining': remaining}


def sheet_state(user_id: int, week: DocketWeek) -> dict:
    """The player's sheet as one dict: the GET render and every mutation
    response read the same assembly, so JS repaints from server truth."""
    now = now_naive()
    picks = (
        DocketPick.query.filter_by(user_id=user_id, week_id=week.id)
        .order_by(DocketPick.slot)
        .all()
    )
    prediction = DocketTiebreakerPrediction.query.filter_by(
        user_id=user_id, week_id=week.id).first()
    locked_game_ids = [
        g.id for g in DocketGame.query.filter_by(week_id=week.id).all()
        if game_locked(g, now)
    ]
    pick_dicts = [
        {
            'game_id': p.game_id,
            'market': p.market,
            'side': p.side,
            'slot': p.slot,
            'is_best': p.is_best,
            'is_autopick': p.is_autopick,
            'is_auto_best': p.is_auto_best,
            'line_value': p.line_value,
            'book': p.book,
            'locked': p.game_id in locked_game_ids,
            # The side as the sheet prints it ("Utah Utes -3.5"), so a
            # surface that names a pick in prose (the filed card) reads the
            # same snapshot the rail renders.
            'label': describe_pick(p),
        }
        for p in picks
    ]
    best = next((p for p in pick_dicts if p['is_best']), None)
    state = {
        'week_number': week.week_number,
        'deadline_at': week.deadline_at.isoformat(),
        'deadline_passed': now >= week.deadline_at,
        'picks': pick_dicts,
        'scoring_count': sum(1 for p in pick_dicts if p['slot'] != BACKUP_SLOT),
        # How many of the sheet's sides the deadline pass filed. Travels with
        # the other progress facts (the rail carries them as one unit), and
        # is the count the post-deadline explainer states.
        'autopick_count': sum(1 for p in pick_dicts if p['is_autopick']),
        'backup': next(
            (p for p in pick_dicts if p['slot'] == BACKUP_SLOT), None),
        'best': best,
        'prediction': (
            format_tenths(prediction.prediction_tenths)
            if prediction is not None else None
        ),
        'locked_game_ids': locked_game_ids,
    }
    # The ask rides with the facts (the Clerk's-Ledger Rule: progress facts
    # travel together), so template, JSON, and toast read one value.
    state['next_step'] = next_step(state, week, now)
    return state
