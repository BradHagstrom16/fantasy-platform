"""The Docket — the commissioner's three rulings (T9).

Every admin mutation lands here, the way games/docket/services/picks.py owns
every sheet mutation: the routes stay declarative and this module owns
validation order, the audit trail, the recalcs, and the commits.

The three rulings, from the 2026-08-11 design SSoT:

- **Tiebreaker designation** (Grading Clarifications). Validation is not
  re-derived here — ``deadline_pass.check_designation`` already owns the
  contract (a locked whole-tenth total, a kickoff at or after the deadline,
  the game on this docket), and this module sets the designation, asks that
  function, and rolls back if it objects. Re-designating clears every
  prediction for the week to the new game's default and tells the roster.
- **No Contest** (D14). A ruling no sync run may make, and the only cure for
  a bad line found after the deadline. It auto-triggers that week's recalc.
- **Line correction** (D18). Data errors only, pre-deadline only, reason
  required, audited, and the market's already-made picks are explicitly
  re-snapshotted — grading reads a pick's own numbers, so a correction that
  did not re-snapshot would leave players grading against the old line.

Notifications are sent AFTER the commit and never gate it: a mail outage
must not roll back a ruling the commissioner already made.
"""
import logging

from sqlalchemy import select

from extensions import db
from games.docket.models import (
    DocketEnrollment,
    DocketGame,
    DocketLineCorrection,
    DocketPick,
    DocketTiebreakerPrediction,
)
from games.docket.services import notifications
from games.docket.services.deadline_pass import check_designation
from games.docket.services.enrollment import roster_user_ids_as_of
from games.docket.services.grading.snapshots import Market
from games.docket.services.grading_pass import try_grade_week
from games.docket.services.picks import locked_line, now_naive
from games.docket.services.weeks import SEASON_YEAR

logger = logging.getLogger(__name__)

# Matches DocketLineCorrection.reason / DocketGame.nc_reason.
MAX_REASON = 200
# Sanity bounds for a corrected number. Deliberately wide: this tool exists
# to fix a bad import, and a granularity rule strict enough to be useful
# would eventually block the very correction it was meant to allow.
MAX_ABS_SPREAD = 100.0
MAX_TOTAL = 200.0


class AdminOpError(Exception):
    """A refused admin ruling, in commissioner-facing terms."""

    def __init__(self, code: str, message: str, problems=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.problems = problems or []


def _clean_reason(raw, *, required=True):
    reason = (raw or '').strip()
    if not reason:
        if required:
            raise AdminOpError('reason_required',
                               'A reason is required. It goes in the record.')
        return None
    if len(reason) > MAX_REASON:
        raise AdminOpError(
            'reason_too_long',
            f'Keep the reason under {MAX_REASON} characters.')
    return reason


def _week_game(week, game_id) -> DocketGame:
    game = db.session.get(DocketGame, game_id) if game_id else None
    if game is None or game.week_id != week.id:
        raise AdminOpError('invalid', 'That case is not on this docket.')
    return game


# ── Tiebreaker designation ───────────────────────────────────────────────

def eligible_tiebreaker_games(week):
    """The week's games that satisfy the designation contract today.

    A convenience for the admin form only — ``check_designation`` remains
    the authority, and designate_tiebreaker re-asks it on every write.
    """
    games = db.session.scalars(
        select(DocketGame).filter_by(week_id=week.id)
        .order_by(DocketGame.kickoff, DocketGame.api_event_id)).all()
    return [g for g in games
            if g.total_points is not None
            and (g.kickoff_at_deadline or g.kickoff) >= week.deadline_at
            and not g.no_contest]


def designate_tiebreaker(week, game_id, *, notify=True) -> dict:
    """Designate the week's tiebreaker case, pre-deadline only.

    Changing an existing designation clears every prediction for the week
    (no row ⇒ the new game's locked total is the default) and notifies the
    roster that they may resubmit. A first-time set clears nothing and
    mails nobody.
    """
    if now_naive() >= week.deadline_at:
        raise AdminOpError(
            'deadline_passed',
            'The docket has closed. A designation cannot move now; if the '
            'case died after the deadline the week accrues no error at all.')
    game = _week_game(week, game_id)
    # eligible_tiebreaker_games hides thrown-out cases from the form, but
    # the form is not the guard: check_designation tests the total and the
    # kickoff, not no_contest, so a stale form or a direct POST would
    # otherwise land the week's tiebreaker on a void case.
    if game.no_contest:
        raise AdminOpError(
            'no_contest',
            'That case is thrown out. Reinstate it or designate another.')
    previous_id = week.tiebreaker_game_id
    if previous_id == game.id:
        return {'changed': False, 'game': game, 'cleared': 0, 'notified': 0}
    previous = db.session.get(DocketGame, previous_id) if previous_id else None

    week.tiebreaker_game_id = game.id
    db.session.flush()
    problems = check_designation(week)
    if problems:
        db.session.rollback()
        raise AdminOpError(
            'unsound',
            'That case does not satisfy the designation contract.',
            problems=problems)

    cleared = 0
    recipients = []
    if previous is not None:
        rows = db.session.scalars(
            select(DocketTiebreakerPrediction).filter_by(
                week_id=week.id)).all()
        cleared = len(rows)
        for row in rows:
            db.session.delete(row)
        # Reached through the enrollment relationship rather than importing
        # User: models/__init__ pulls the whole frozen worldcup graph in, and
        # routes.py already documents a cycle that comes from exactly that.
        recipients = [e.user for e in db.session.scalars(
            select(DocketEnrollment).filter_by(season_year=SEASON_YEAR)).all()]
    db.session.commit()

    notified = 0
    if notify and recipients:
        notified = notifications.notify_redesignation(
            week, game, previous, recipients)
    return {'changed': True, 'game': game, 'previous': previous,
            'cleared': cleared, 'notified': notified}


# ── No Contest ───────────────────────────────────────────────────────────

def rule_no_contest(week, game_id, reason) -> dict:
    """Throw a case out, then re-grade the week (D14).

    The recalc runs through ``try_grade_week`` exactly as the scores sync
    does, so a week that is not gradeable yet reports ``not_ready`` with its
    reason instead of raising. That catch stays as narrow as it is: only a
    missing deadline pass, a missing designation, or a missing final score
    are waits. Anything else is corrupt data and must still surface.
    """
    game = _week_game(week, game_id)
    reason = _clean_reason(reason)
    if game.no_contest:
        raise AdminOpError('already_ruled',
                           'That case is already thrown out.')
    game.no_contest = True
    game.nc_reason = reason
    db.session.commit()
    logger.info('Docket week %s: %s @ %s ruled No Contest (%s)',
                week.week_number, game.away_team, game.home_team, reason)
    return {'game': game, 'grading': _recalc(week)}


def clear_no_contest(week, game_id) -> dict:
    """Reverse a No Contest ruling and re-grade. The recalc is idempotent,
    which is what makes a misruling recoverable rather than permanent."""
    game = _week_game(week, game_id)
    if not game.no_contest:
        raise AdminOpError('not_ruled', 'That case is not thrown out.')
    game.no_contest = False
    game.nc_reason = None
    db.session.commit()
    logger.info('Docket week %s: No Contest cleared on %s @ %s',
                week.week_number, game.away_team, game.home_team)
    return {'game': game, 'grading': _recalc(week)}


def _recalc(week) -> dict:
    # The roster as of the deadline, not the live one: a No Contest ruling
    # lands after the week closed, and re-grading must not deal a package to
    # anyone who joined since.
    return try_grade_week(
        week.id, user_ids=roster_user_ids_as_of(week.deadline_at))


# ── D18 line correction ──────────────────────────────────────────────────

def _validate_number(market: Market, value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise AdminOpError('invalid_number',
                           'Enter the corrected number, like -3.5 or 51.5.'
                           ) from None
    if number != number or number in (float('inf'), float('-inf')):
        raise AdminOpError('invalid_number', 'Enter a real number.')
    if market is Market.SPREAD:
        if abs(number) > MAX_ABS_SPREAD:
            raise AdminOpError(
                'invalid_number',
                f'A spread beyond {MAX_ABS_SPREAD:g} is not a correction.')
    elif not 0 < number <= MAX_TOTAL:
        raise AdminOpError(
            'invalid_number',
            f'A total must sit between 0 and {MAX_TOTAL:g}.')
    return number


def correct_line(week, game_id, market, value, book, reason,
                 admin_user_id, *, notify=True) -> dict:
    """Correct one locked market, audited, and re-snapshot its picks (D18).

    Pre-deadline only, and refused once the case has kicked off: those picks
    are frozen, and moving the number under them would rewrite a locked
    record. A bad line found later is a No Contest ruling, not a correction.
    """
    if now_naive() >= week.deadline_at:
        raise AdminOpError(
            'deadline_passed',
            'The docket has closed. A bad line now resolves as No Contest.')
    game = _week_game(week, game_id)
    if now_naive() >= game.kickoff:
        raise AdminOpError(
            'game_locked',
            'That case kicked off. Its picks are frozen; rule No Contest '
            'instead.')
    try:
        market = Market(market)
    except ValueError:
        raise AdminOpError('invalid', 'Unknown market.') from None
    current = locked_line(game, market)
    if current is None:
        raise AdminOpError(
            'not_locked',
            'That market has no locked line to correct. An unposted market '
            'fills from the next lines run.')
    reason = _clean_reason(reason)
    number = _validate_number(market, value)
    book = (book or '').strip()
    if not book:
        raise AdminOpError('book_required',
                           'Name the bookmaker the corrected number is from.')
    if len(book) > 40:
        raise AdminOpError('book_required', 'That bookmaker key is too long.')

    old_value, old_book = current
    if (old_value, old_book) == (number, book):
        raise AdminOpError('no_change', 'That is the number already on file.')

    if market is Market.SPREAD:
        game.home_spread, game.spread_book = number, book
    else:
        game.total_points, game.total_book = number, book

    # A corrected total on the DESIGNATED case feeds key 3's default
    # prediction, so the designation contract has to survive the edit — the
    # number range check above is looser than total_to_tenths, so a typo
    # like 48.55 would otherwise leave the week ungradeable. Same authority
    # as designate_tiebreaker: ask check_designation, roll back if it
    # objects.
    if market is Market.TOTAL and game.id == week.tiebreaker_game_id:
        db.session.flush()
        problems = check_designation(week)
        if problems:
            db.session.rollback()
            raise AdminOpError(
                'unsound_designation',
                'That number would break the designation contract on the '
                'tiebreaker case.',
                problems=problems)

    # The pick's own snapshot is what grades (models.py), so the correction
    # has to reach the rows already made on this market. Explicit
    # re-snapshot, never silent drift.
    picks = db.session.scalars(
        select(DocketPick).filter_by(game_id=game.id,
                                     market=market.value)).all()
    for pick in picks:
        pick.line_value = number
        pick.book = book

    correction = DocketLineCorrection(
        game_id=game.id, market=market.value,
        old_value=old_value, old_book=old_book,
        new_value=number, new_book=book,
        reason=reason, admin_user_id=admin_user_id,
        picks_resnapshotted=len(picks))
    db.session.add(correction)
    db.session.commit()
    logger.info('Docket week %s: %s %s corrected %s (%s) -> %s (%s); '
                '%s picks re-snapshotted',
                week.week_number, game.api_event_id, market.value,
                old_value, old_book, number, book, len(picks))

    notified = 0
    if notify and picks:
        notified = notifications.notify_line_correction(
            correction, game, picks)
    return {'correction': correction, 'game': game,
            'resnapshotted': len(picks), 'notified': notified}
