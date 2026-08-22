"""The Docket — the rule-derived default tiebreaker (league vote, 2026-08-22).

The tiebreaker case is the LAST game on the docket: the latest-kickoff NFL
game of the week — Monday Night Football; the later kickoff of a doubleheader;
Sunday night when no Monday game exists — from ``weeks.FIRST_NFL_WEEK`` on.
Week 1 carries no NFL game, so its pool is the whole slate, which resolves
the 2026 schedule to SMU @ Florida State on Labor Day. The selection ranks by
the same ``(kickoff, api_event_id)`` order every docket listing uses, read in
reverse, so a same-instant tie is deterministic.

Two doctrines, both deliberate:

- **Fill only, never move.** The rule designates when the week has NO
  tiebreaker on file and otherwise reports ``kept`` — the commissioner's hand
  designation (the admin desk, ``flask docket set-tiebreaker``) is the
  override and always wins. Re-designation clears every prediction and mails
  the roster, which no timer should do on its own.
- **Wait, don't slide.** When the rule's game has no locked total yet it
  reports ``waiting`` and designates nothing; the Tue–Fri ``lines`` runs
  retry. On Tuesday the Monday night total is the one most likely still
  unposted, and sliding to the next game would make Sunday night sticky for
  the week (the rule never moves a designation). A total that never posts
  surfaces exactly as before: WARNINGs all week, exit 1 at the deadline pass.

Every write goes through ``admin_ops.designate_tiebreaker`` so the contract
(``deadline_pass.check_designation``) stays the single authority; callers
commit before calling, because an ``unsound`` refusal rolls the session back.
"""
import logging

from sqlalchemy import select

from extensions import db
from games.docket.models import DocketGame
from games.docket.services.admin_ops import AdminOpError, designate_tiebreaker
from games.docket.services.picks import now_naive
from games.docket.services.weeks import FIRST_NFL_WEEK

logger = logging.getLogger(__name__)

# The Odds API sport key stored on DocketGame.sport (importer.SPORTS[1]).
NFL = 'americanfootball_nfl'


def _kickoff(game):
    """Parity with check_designation: the frozen kickoff once stamped."""
    return game.kickoff_at_deadline or game.kickoff


def default_tiebreaker_game(week):
    """The game the rule names for this week, or ``(None, why-not)``.

    Read-only. Queries the week's games rather than reading ``week.games`` so
    a game added or ruled on moments ago (and merely flushed) is seen.
    """
    games = db.session.scalars(
        select(DocketGame).filter_by(week_id=week.id)
        .order_by(DocketGame.kickoff, DocketGame.api_event_id)).all()
    pool = [g for g in games
            if not g.no_contest and _kickoff(g) >= week.deadline_at]
    nfl_week = week.week_number >= FIRST_NFL_WEEK
    if nfl_week:
        pool = [g for g in pool if g.sport == NFL]
    if not pool:
        return None, ('no NFL game on the docket yet' if nfl_week
                      else 'no eligible game on the docket yet')
    return max(pool, key=lambda g: (_kickoff(g), g.api_event_id)), ''


def apply_default_tiebreaker(week) -> dict:
    """Fill an empty designation with the rule's game; never move one.

    Returns ``{'status', 'game', 'rule_game', 'reason'}`` where status is one
    of ``kept`` (a designation is on file — ``game`` is it, ``rule_game`` what
    the rule would name today), ``closed`` (past the deadline), ``none`` (the
    rule names nothing, or its game fails the contract), ``waiting`` (its game
    has no locked total yet) or ``designated``. Never raises AdminOpError.

    Fill-only is decided on a fresh, row-locked read of the week (``SELECT …
    FOR UPDATE`` on Postgres; SQLite ignores the lock), so a hand designation
    that landed after this session loaded the row is seen and kept, and one
    that lands during this call serializes behind it and arrives as the
    re-designation it is (predictions cleared, roster told). Every path ends
    the transaction — the write through ``designate_tiebreaker`` commits or
    rolls back, the read-only outcomes commit nothing-pending — so the lock
    never outlives the decision.
    """
    db.session.refresh(week, with_for_update=True)
    outcome = _decide(week)
    if outcome['status'] != 'designated':
        db.session.commit()
    return outcome


def _decide(week) -> dict:
    rule_game, reason = default_tiebreaker_game(week)
    if week.tiebreaker_game_id is not None:
        return {'status': 'kept', 'game': week.tiebreaker_game,
                'rule_game': rule_game, 'reason': reason}
    if now_naive() >= week.deadline_at:
        return {'status': 'closed', 'game': None, 'rule_game': rule_game,
                'reason': 'the docket has closed; the rule does not '
                          'designate after the deadline'}
    if rule_game is None:
        return {'status': 'none', 'game': None, 'rule_game': None,
                'reason': reason}
    if rule_game.total_points is None:
        return {'status': 'waiting', 'game': None, 'rule_game': rule_game,
                'reason': f'no locked total yet on {rule_game.away_team} @ '
                          f'{rule_game.home_team}'}
    try:
        result = designate_tiebreaker(week, rule_game.id, notify=False)
    except AdminOpError as exc:
        return {'status': 'none', 'game': None, 'rule_game': rule_game,
                'reason': '; '.join([exc.message, *exc.problems])}
    game = result['game']
    logger.info('Docket week %s: tiebreaker designated by rule — %s @ %s (%s)',
                week.week_number, game.away_team, game.home_team,
                game.api_event_id)
    return {'status': 'designated', 'game': game, 'rule_game': rule_game,
            'reason': ''}
