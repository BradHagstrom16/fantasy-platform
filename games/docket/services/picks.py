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
from games.docket.utils import now_utc, to_naive_utc

# Legal sides per market. The engine enforces the same pairing at its own
# boundary (snapshots.PickSnapshot construction); both derive from the one
# Market/Side enum pair, so they cannot drift independently.
SIDES_FOR_MARKET = {
    Market.SPREAD: frozenset({Side.HOME, Side.AWAY}),
    Market.TOTAL: frozenset({Side.OVER, Side.UNDER}),
}

# Combined-score predictions above this are data errors, not opinions.
MAX_PREDICTION_TENTHS = 9990


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
            raise PickError(
                'sheet_full',
                'All eight slots are filled. Remove a pick first, or add '
                'this one as your reserve.')
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
        if existing is not None and existing.side == side.value:
            return existing
        raise PickError('conflict',
                        'That pick was already recorded. Refresh the sheet.'
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
        db.session.flush()
    row.is_best = True
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
    db.session.commit()


def parse_prediction_tenths(raw: str) -> int:
    """Parse a combined-score prediction ("51.5", "51") to integer tenths.

    Pure string/int arithmetic: no float ever enters key 3 (D20). At most
    one decimal digit; negatives, bare fractions, and trailing dots refuse.
    """
    s = raw.strip()
    whole, dot, frac = s.partition('.')
    if not whole.isdigit() or (dot and (len(frac) != 1 or not frac.isdigit())):
        raise PickError('invalid',
                        'Enter a combined score like 51.5.', status=400)
    tenths = int(whole) * 10 + (int(frac) if dot else 0)
    if tenths > MAX_PREDICTION_TENTHS:
        raise PickError('invalid',
                        'Enter a combined score like 51.5.', status=400)
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
            'line_value': p.line_value,
            'book': p.book,
            'locked': p.game_id in locked_game_ids,
        }
        for p in picks
    ]
    best = next((p for p in pick_dicts if p['is_best']), None)
    return {
        'week_number': week.week_number,
        'deadline_at': week.deadline_at.isoformat(),
        'deadline_passed': now >= week.deadline_at,
        'picks': pick_dicts,
        'scoring_count': sum(1 for p in pick_dicts if p['slot'] != BACKUP_SLOT),
        'backup': next(
            (p for p in pick_dicts if p['slot'] == BACKUP_SLOT), None),
        'best': best,
        'prediction': (
            format_tenths(prediction.prediction_tenths)
            if prediction is not None else None
        ),
        'locked_game_ids': locked_game_ids,
    }
