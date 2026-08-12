"""Week grading: market outcomes, slot resolution, points, wins, error.

Pure functions over snapshots (D9-eng). All grading uses the final score
INCLUDING overtime (D23-eng) — the snapshot's score IS the graded score.
Lines are dyadic floats, scores are ints, so every comparison here is
float-exact; key 3 is all-integer tenths (D20-eng).
"""
from games.docket.services.grading.autopick import (
    complete_player_input,
    default_tiebreaker_tenths,
)
from games.docket.services.grading.snapshots import (
    BACKUP_SLOT,
    SCORING_SLOTS,
    VIA_BACKUP,
    VIA_EMPTY,
    VIA_NC_PUSH,
    VIA_PICK,
    GameSnapshot,
    Market,
    Outcome,
    PlayerWeekGrade,
    PlayerWeekInput,
    Side,
    SlotGrade,
    WeekGrade,
    WeekSnapshot,
)


class EngineError(ValueError):
    """A week reached grading in an ungradeable state (caller bug)."""


def grade_pick_outcome(game: GameSnapshot, market: Market,
                       side: Side) -> Outcome:
    """Grade one market side against the game's frozen line + final score.

    Spread (home perspective, negative = home favored): home covers iff
    margin + home_spread > 0; equality is a push; NFL ties grade normally
    by the number (a PK/0 spread on a tie IS the equality case — push,
    D23-eng). Totals: over wins iff combined > total; equality pushes.
    """
    if game.home_score is None:
        raise EngineError(f'{game.api_event_id} has no final score')
    if market is Market.SPREAD:
        if game.home_spread is None:
            raise EngineError(f'{game.api_event_id} has no locked spread')
        adjusted = (game.home_score - game.away_score) + game.home_spread
        if adjusted == 0:
            return Outcome.PUSH
        home_covered = adjusted > 0
        return (Outcome.WIN if home_covered == (side is Side.HOME)
                else Outcome.LOSS)
    if game.total is None:
        raise EngineError(f'{game.api_event_id} has no locked total')
    combined = game.home_score + game.away_score
    if combined == game.total:
        return Outcome.PUSH
    over_hit = combined > game.total
    return (Outcome.WIN if over_hit == (side is Side.OVER)
            else Outcome.LOSS)


def _points(outcome: Outcome, doubled: bool) -> float:
    """Win 1 / push 0.5 / loss 0; the best-pick slot doubles (D4-session):
    win 2 / push 1 / loss 0. Exact half-step floats."""
    if outcome is Outcome.WIN:
        return 2.0 if doubled else 1.0
    if outcome is Outcome.PUSH:
        return 1.0 if doubled else 0.5
    return 0.0


def _resolve_slots(week: WeekSnapshot,
                   player: PlayerWeekInput) -> tuple[SlotGrade, ...]:
    """Grade the 8 scoring slots with D6-session slot resolution.

    1. NC slots = scoring slots whose game is No Contest.
    2. The backup is ALIVE iff submitted and its own game is not NC.
    3. An alive backup substitutes its own graded result into the NC slot
       with the earliest kickoff_at_deadline (same instant -> lowest slot),
       inheriting that slot's best-pick designation. At most once.
    4. Every remaining NC slot is a push (doubled push in the best slot).
    """
    scoring = sorted((p for p in player.picks if p.slot != BACKUP_SLOT),
                     key=lambda p: p.slot)
    backup = next((p for p in player.picks if p.slot == BACKUP_SLOT), None)
    backup_alive = (backup is not None
                    and not week.game(backup.api_event_id).no_contest)
    nc_picks = [p for p in scoring if week.game(p.api_event_id).no_contest]
    substituted = None
    if backup_alive and nc_picks:
        substituted = min(
            nc_picks,
            key=lambda p: (week.game(p.api_event_id).kickoff_at_deadline,
                           p.slot))

    grades = []
    for pick in scoring:
        if week.game(pick.api_event_id).no_contest:
            if pick is substituted:
                backup_game = week.game(backup.api_event_id)
                outcome = grade_pick_outcome(backup_game, backup.market,
                                             backup.side)
                grades.append(SlotGrade(
                    slot=pick.slot,
                    api_event_id=backup.api_event_id,
                    market=backup.market,
                    side=backup.side,
                    outcome=outcome,
                    is_best=pick.is_best,  # the double lives on the SLOT
                    is_autopick=backup.is_autopick,
                    via=VIA_BACKUP,
                    points=_points(outcome, doubled=pick.is_best),
                ))
            else:
                grades.append(SlotGrade(
                    slot=pick.slot,
                    api_event_id=None,
                    market=None,
                    side=None,
                    outcome=Outcome.PUSH,
                    is_best=pick.is_best,
                    is_autopick=pick.is_autopick,
                    via=VIA_NC_PUSH,
                    points=_points(Outcome.PUSH, doubled=pick.is_best),
                ))
            continue
        game = week.game(pick.api_event_id)
        outcome = grade_pick_outcome(game, pick.market, pick.side)
        grades.append(SlotGrade(
            slot=pick.slot,
            api_event_id=pick.api_event_id,
            market=pick.market,
            side=pick.side,
            outcome=outcome,
            is_best=pick.is_best,
            is_autopick=pick.is_autopick,
            via=VIA_PICK,
            points=_points(outcome, doubled=pick.is_best),
        ))
    # Defensive: a slot the pool couldn't fill grades empty (0 points) —
    # the engine never invents picks.
    filled = {g.slot for g in grades}
    for slot in range(1, SCORING_SLOTS + 1):
        if slot not in filled:
            grades.append(SlotGrade(
                slot=slot, api_event_id=None, market=None, side=None,
                outcome=None, is_best=False, is_autopick=False,
                via=VIA_EMPTY, points=0.0))
    return tuple(sorted(grades, key=lambda g: g.slot))


def _actual_combined_tenths(week: WeekSnapshot) -> int:
    game = week.tiebreaker_game
    if game.home_score is None:
        raise EngineError(
            f'designated game {game.api_event_id} has no final score')
    return (game.home_score + game.away_score) * 10


def grade_week(week: WeekSnapshot,
               players: tuple[PlayerWeekInput, ...] | list) -> WeekGrade:
    """Grade every submitted player. Raises EngineError on an incomplete
    week (grade complete weeks only — the pass, not the engine, decides
    when a week is ready)."""
    designated_dead = week.tiebreaker_game.no_contest
    if designated_dead:
        # Post-deadline designation death: zero error for EVERYONE this
        # week, submitted predictions included (Grading Clarifications).
        default_error = 0
    else:
        default_prediction = default_tiebreaker_tenths(week)
        actual = _actual_combined_tenths(week)
        default_error = abs(default_prediction - actual)

    graded = []
    for player in players:
        completed = complete_player_input(week, player)
        slots = _resolve_slots(week, completed)
        used_default = completed.tiebreaker_tenths is None
        if designated_dead:
            error = 0
        else:
            prediction = (default_prediction if used_default
                          else completed.tiebreaker_tenths)
            error = abs(prediction - actual)
        graded.append(PlayerWeekGrade(
            player_id=completed.player_id,
            slots=slots,
            points=sum(s.points for s in slots),
            wins=sum(1 for s in slots if s.outcome is Outcome.WIN),
            error_tenths=error,
            used_default_prediction=used_default,
        ))
    return WeekGrade(
        week_number=week.week_number,
        default_error_tenths=default_error,
        players=tuple(graded),
    )
