"""Autopick completion: top-up, auto-designation, default tiebreaker.

D5-session package + the Grading Clarifications partial-picker matrix.
Pure functions of (WeekSnapshot, picks) — deterministic replays of
Tuesday-locked lines, which is why post-deadline auto-completion is exempt
from the designation lock. Every tie anywhere breaks deterministically:
bucket ranks tie on api_event_id, designation ties on lowest slot.
"""
from dataclasses import replace
from decimal import Decimal

from games.docket.services.grading.snapshots import (
    BACKUP_SLOT,
    SCORING_SLOTS,
    GameSnapshot,
    Market,
    PickSnapshot,
    PlayerWeekInput,
    Side,
    WeekSnapshot,
)


def default_tiebreaker_tenths(week: WeekSnapshot) -> int:
    """The designated game's locked O/U total, in integer tenths.

    Raises when the total is missing (designation requires a locked total)
    or not a whole tenth (a .25 total is an admin re-designation, never
    silent rounding — F7)."""
    total = week.tiebreaker_game.total
    if total is None:
        raise ValueError(
            f'designated game {week.tiebreaker_event_id!r} has no locked '
            f'total — designation requires one')
    scaled = Decimal(str(total)) * 10
    if scaled != scaled.to_integral_value():
        raise ValueError(
            f'designated total {total!r} is not a whole tenth — '
            f're-designate rather than round')
    return int(scaled)


def _favored_side(game: GameSnapshot) -> Side | None:
    """The favorite side of a locked spread; None for PK (0) or no line —
    a pick'em game has no favorite and is not favorite-bucket-eligible."""
    if game.home_spread is None or game.home_spread == 0:
        return None
    return Side.HOME if game.home_spread < 0 else Side.AWAY


def _pool(week: WeekSnapshot) -> list[GameSnapshot]:
    """The autopick candidate pool: kickoff at-or-after the deadline
    instant (t == deadline is IN — the Big Noon triple-agreement)."""
    return [g for g in week.games
            if g.kickoff_at_deadline >= week.deadline_at]


def autopick_topup(week: WeekSnapshot,
                   picks: tuple[PickSnapshot, ...]) -> tuple[PickSnapshot,
                                                             ...]:
    """The added picks for a partial picker (D5-session, interleaved).

    Over bucket: pool games with a locked total, descending total.
    Favorite bucket: pool games with a non-PK locked spread, favorite
    side, descending |spread|. Ties rank by api_event_id. Interleave
    O1,F1,O2,F2,... skipping markets the player holds and games already
    claimed this run (bucket exclusivity per game); a short bucket
    backfills from the other. First k fill the empty slots ascending.
    Never touches held picks; never adds a backup.
    """
    scoring = [p for p in picks if p.slot != BACKUP_SLOT]
    k = SCORING_SLOTS - len(scoring)
    if k <= 0:
        return ()

    held_markets = {(p.api_event_id, p.market) for p in picks}
    pool = _pool(week)
    overs = sorted((g for g in pool if g.total is not None),
                   key=lambda g: (-g.total, g.api_event_id))
    favorites = sorted((g for g in pool if _favored_side(g) is not None),
                       key=lambda g: (-abs(g.home_spread), g.api_event_id))
    free_slots = sorted(set(range(1, SCORING_SLOTS + 1))
                        - {p.slot for p in scoring})

    # Bucket exclusivity is a property of the autopick SET, not this run:
    # games already claimed by earlier autopicks stay claimed, so
    # re-completing a short (pool-exhausted) input is a no-op instead of
    # double-dipping the other market of the same game.
    claimed: set[str] = {p.api_event_id for p in picks if p.is_autopick}
    added: list[PickSnapshot] = []
    indexes = {'O': 0, 'F': 0}
    buckets = {'O': overs, 'F': favorites}
    markets = {'O': Market.TOTAL, 'F': Market.SPREAD}

    def take(bucket_key):
        """Next unclaimed, unheld candidate from a bucket, or None."""
        bucket = buckets[bucket_key]
        while indexes[bucket_key] < len(bucket):
            game = bucket[indexes[bucket_key]]
            indexes[bucket_key] += 1
            if game.api_event_id in claimed:
                continue
            if (game.api_event_id, markets[bucket_key]) in held_markets:
                continue
            return game
        return None

    turn = 'O'
    while len(added) < k:
        game = take(turn)
        if game is None:
            other = 'F' if turn == 'O' else 'O'
            game = take(other)
            if game is None:
                break  # pool exhausted — the engine grades empties
            bucket_key = other
        else:
            bucket_key = turn
        side = (Side.OVER if bucket_key == 'O'
                else _favored_side(game))
        claimed.add(game.api_event_id)
        added.append(PickSnapshot(
            slot=free_slots[len(added)],
            api_event_id=game.api_event_id,
            market=markets[bucket_key],
            side=side,
            is_autopick=True,
        ))
        turn = 'F' if turn == 'O' else 'O'
    return tuple(added)


def auto_designate(week: WeekSnapshot,
                   picks: tuple[PickSnapshot, ...]) -> tuple[PickSnapshot,
                                                             ...]:
    """Assign the best pick when none is designated, on the FINAL 8-slot
    set (Grading Clarifications): largest favorite-side spread pick; else
    the highest-total Over pick; else the earliest-kickoff pick. Every
    tie breaks by lowest slot. No-op when a designation exists or there
    is nothing to designate."""
    if any(p.is_best for p in picks):
        return picks
    scoring = [p for p in picks if p.slot != BACKUP_SLOT]
    if not scoring:
        return picks

    favorite_picks = [
        p for p in scoring
        if p.market is Market.SPREAD
        and p.side == _favored_side(week.game(p.api_event_id))]
    over_picks = [p for p in scoring
                  if p.market is Market.TOTAL and p.side is Side.OVER
                  and week.game(p.api_event_id).total is not None]
    if favorite_picks:
        target = min(favorite_picks,
                     key=lambda p: (-abs(week.game(p.api_event_id)
                                         .home_spread), p.slot))
    elif over_picks:
        target = min(over_picks,
                     key=lambda p: (-week.game(p.api_event_id).total,
                                    p.slot))
    else:
        target = min(scoring,
                     key=lambda p: (week.game(p.api_event_id)
                                    .kickoff_at_deadline, p.slot))
    return tuple(replace(p, is_best=True) if p is target else p
                 for p in picks)


def complete_player_input(week: WeekSnapshot,
                          player: PlayerWeekInput) -> PlayerWeekInput:
    """Grading-ready input: top-up, then auto-designation. Idempotent —
    a completed input passes through unchanged. The default tiebreaker
    prediction is NOT materialized here; grade_week applies it so the
    used-default fact survives into the grade."""
    picks = player.picks + autopick_topup(week, player.picks)
    picks = auto_designate(week, picks)
    if picks == player.picks:
        return player
    return replace(player, picks=picks)
