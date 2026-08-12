"""The Docket — Deadline Pass (D7 freeze + the D5 autopick package)

Runs once at or after a week's Saturday 11:00 AM CT deadline, in this order
(the order IS the contract):

1. **Stamp** ``kickoff_at_deadline`` from the live kickoff column — the D7
   slot-substitution ordering input, and the input the autopick pool reads.
   Nothing downstream can build a WeekSnapshot until this has run.
2. **Check the designation** — the Grading Clarifications contract for the
   week's tiebreaker game (exists, on this docket, locked whole-tenth total,
   kickoff at-or-after the deadline).
3. **Complete every enrolled player's sheet** with the D5 package: top-up to
   eight scoring picks, then auto-designate the headliner.

The two halves are deliberately independent. Stamping is time-critical — it
must capture kickoffs as they stood at the deadline — so it runs
unconditionally. Autopick is a pure replay of Tuesday-locked lines over
already-frozen picks, so it is safe to run late: nobody can submit after the
deadline, and the completion is a deterministic function of state that stopped
moving at 11:00. A missing designation therefore blocks autopick (loudly, with
nothing written) instead of blocking the freeze.

**Persisted autopick rows are transparency, not correctness.** ``grade_week``
calls ``complete_player_input`` for every player itself, so a week grades
identically whether or not these rows exist. They exist so the player can SEE
the sheet they were dealt. Both paths run the same pure function; the parity
is test-locked.
"""
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from extensions import db
from games.docket.models import DocketPick, DocketWeek
from games.docket.services.enrollment import roster_user_ids
from games.docket.services.grading.autopick import (
    complete_player_input,
    total_to_tenths,
)
from games.docket.services.grading_pass import (
    build_week_snapshot,
    player_inputs_for,
)
from games.docket.services.picks import locked_line
from games.docket.services.weeks import week_number_for
from games.docket.utils import now_utc, to_naive_utc

logger = logging.getLogger(__name__)


class DeadlinePassError(Exception):
    """The pass refused, or could not finish, in operator-facing terms."""


def _current_week_number():
    """The docket week containing now, or a refusal naming the fix."""
    week_number = week_number_for(now_utc())
    if week_number is None:
        raise DeadlinePassError(
            'the current time is outside the docket season — pass --week')
    return week_number


def stamp_kickoffs(week: DocketWeek) -> dict:
    """Freeze each game's kickoff as of the deadline. Idempotent.

    Only-if-null IS the freeze: a later run must never re-stamp a kickoff
    that moved after the deadline, or D6 substitution ordering would shift
    under already-graded weeks. A game first imported after the deadline has
    no better value available than its current kickoff — it gets stamped
    (the engine requires every game stamped) and logged, since it was not on
    the docket the players saw.
    """
    stamped = late = 0
    for game in week.games:
        if game.kickoff_at_deadline is not None:
            continue
        game.kickoff_at_deadline = game.kickoff
        stamped += 1
        if game.created_at is not None and game.created_at > week.deadline_at:
            late += 1
            logger.warning(
                'Week %s: %s @ %s (%s) was imported AFTER the deadline; '
                'freezing its ordering kickoff at %s',
                week.week_number, game.away_team, game.home_team,
                game.api_event_id, game.kickoff)
    db.session.commit()
    return {'stamped': stamped, 'stamped_late_arrivals': late}


def check_designation(week: DocketWeek) -> list[str]:
    """Every designation problem on this week, in operator-facing terms.

    The Grading Clarifications designation contract in one place: a locked
    whole-tenth O/U total (key 3's default prediction is computed from it)
    and a kickoff at-or-after the deadline (so nobody ever predicts a score
    already in progress). Returns [] when the week is sound.

    Called twice on different clocks: as the gate on the autopick half of
    this pass, and by the Tuesday-through-Friday ``lines`` runs, where it is
    the early warning that keeps a missing designation from first surfacing
    at 11:00 on Saturday.
    """
    problems = []
    game = week.tiebreaker_game
    if game is None:
        return [f'week {week.week_number} has no designated tiebreaker game']
    if game.week_id != week.id:
        problems.append(
            f'week {week.week_number}: designated tiebreaker game '
            f'{game.api_event_id} belongs to another week')
    try:
        total_to_tenths(game.total_points,
                        f'week {week.week_number} tiebreaker '
                        f'({game.away_team} @ {game.home_team})')
    except ValueError as exc:
        problems.append(str(exc))
    # Post-stamp the frozen kickoff is the honest one; pre-stamp (the
    # Tuesday early warning) only the live column exists.
    kickoff = game.kickoff_at_deadline or game.kickoff
    if kickoff < week.deadline_at:
        problems.append(
            f'week {week.week_number}: designated tiebreaker '
            f'({game.away_team} @ {game.home_team}) kicks off at {kickoff}, '
            f'before the {week.deadline_at} deadline — predictions would '
            f'lock early')
    return problems


def _add_autopick_rows(week, user_id, added, game_by_event, summary):
    """Persist one player's top-up picks; returns the slots actually written.

    A market whose value is locked without a bookmaker key is unpostable —
    ``locked_line`` refuses it exactly as the pick sheet does, and inventing
    provenance to satisfy a NOT NULL column would corrupt the D17 audit
    trail. Such a slot is left empty (the engine grades it 0) and counted.
    """
    written = set()
    for pick in added:
        game = game_by_event[pick.api_event_id]
        line = locked_line(game, pick.market)
        if line is None:
            logger.error(
                'Week %s user %s: autopick chose %s/%s on %s but that market '
                'has no bookmaker recorded — slot %s left empty',
                week.week_number, user_id, pick.market.value, pick.side.value,
                game.api_event_id, pick.slot)
            summary['line_gaps'] += 1
            continue
        value, book = line
        db.session.add(DocketPick(
            user_id=user_id,
            week_id=week.id,
            game_id=game.id,
            market=pick.market.value,
            side=pick.side.value,
            slot=pick.slot,
            is_best=pick.is_best,
            is_autopick=True,
            line_value=value,
            book=book,
        ))
        written.add(pick.slot)
    return written


def run_autopick(week: DocketWeek, user_ids=None) -> dict:
    """Deal every roster member the D5 package. Idempotent.

    A completed sheet passes through ``complete_player_input`` unchanged, so
    re-running writes nothing. The default tiebreaker prediction is NEVER
    materialized — ``grade_week`` applies it so ``used_default_prediction``
    survives into the grade (models.py, DocketTiebreakerPrediction).
    """
    if user_ids is None:
        user_ids = roster_user_ids()
    snapshot = build_week_snapshot(week)
    players = player_inputs_for(week, user_ids)
    game_by_event = {g.api_event_id: g for g in week.games}
    summary = {'players': len(players), 'picks_added': 0,
               'designations': 0, 'line_gaps': 0}

    for player in players:
        completed = complete_player_input(snapshot, player)
        if completed.picks == player.picks:
            continue
        user_id = int(player.player_id)
        held_slots = {p.slot for p in player.picks}
        added = [p for p in completed.picks if p.slot not in held_slots]
        written = _add_autopick_rows(week, user_id, added, game_by_event,
                                     summary)
        summary['picks_added'] += len(written)

        # Auto-designation: only ever sets a headliner where the player had
        # none, so the partial unique index needs no clear-before-set dance.
        if any(p.is_best for p in player.picks):
            continue
        best = next((p for p in completed.picks if p.is_best), None)
        if best is None:
            continue
        if best.slot in held_slots:
            row = db.session.scalar(select(DocketPick).filter_by(
                user_id=user_id, week_id=week.id, slot=best.slot))
            if row is None:  # pragma: no cover - held slots come from rows
                continue
            row.is_best = True
        elif best.slot not in written:
            continue  # its row was skipped for a missing book
        summary['designations'] += 1

    try:
        db.session.commit()
    except IntegrityError as exc:
        # Post-deadline the sheet is frozen, so the only realistic collision
        # is a submission that committed as the deadline struck. Nothing is
        # written; a re-run recomputes from the settled rows.
        db.session.rollback()
        raise DeadlinePassError(
            f'week {week.week_number}: the sheet moved during the pass '
            f'({exc.orig}) — nothing was written; re-run the deadline pass'
        ) from exc
    return summary


def run_deadline_pass(week_number=None, force=False) -> dict:
    """Stamp the week's kickoffs, then deal autopicks. Idempotent.

    Refuses before the deadline: stamping early would freeze the wrong
    ordering input, and autopicking early would fill sheets while players are
    still deciding. ``force`` is a development escape only.

    Returns a summary whose ``problems`` list is non-empty when the autopick
    half was skipped — the caller reports it and exits non-zero.
    """
    if week_number is None:
        week_number = _current_week_number()
    week = db.session.scalar(
        select(DocketWeek).filter_by(week_number=week_number))
    if week is None:
        raise DeadlinePassError(
            f'no docket week {week_number} — run `flask docket sync '
            f'--mode setup --week {week_number}` first')

    now = to_naive_utc(now_utc())
    if now < week.deadline_at and not force:
        raise DeadlinePassError(
            f'week {week.week_number} does not close until '
            f'{week.deadline_at} UTC (now {now}) — the sheet is still open')

    summary = {'week_number': week.week_number, 'problems': []}
    summary.update(stamp_kickoffs(week))

    problems = check_designation(week)
    if problems:
        summary['problems'] = problems
        summary.update(players=0, picks_added=0, designations=0, line_gaps=0)
        logger.error('Week %s: kickoffs frozen, autopick SKIPPED — %s',
                     week.week_number, '; '.join(problems))
        return summary

    summary.update(run_autopick(week))
    return summary
