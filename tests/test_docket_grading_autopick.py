"""Autopick property tests: invariants cheaper as code than as fixtures.

The fixture catalog locks the concrete D5-session behaviors; these lock the
shape of the completion function across a grid of partial inputs — it never
overwrites, never assigns the backup, always terminates deterministically,
and degrades sanely on an exhausted pool.
"""
from datetime import datetime, timedelta

import pytest

DEADLINE = datetime(2026, 9, 5, 16, 0)


def _game(eid, total=50.0, spread=-7.0, hours_after_deadline=2,
          score=(30, 20)):
    from games.docket.services.grading.snapshots import GameSnapshot

    return GameSnapshot(
        api_event_id=eid,
        sport='americanfootball_ncaaf',
        home_team=f'H-{eid}',
        away_team=f'A-{eid}',
        kickoff_at_deadline=DEADLINE + timedelta(hours=hours_after_deadline),
        home_spread=spread,
        total=total,
        home_score=score[0] if score else None,
        away_score=score[1] if score else None,
    )


def _week(n_games=12, **kw):
    from games.docket.services.grading.snapshots import WeekSnapshot

    games = tuple(
        _game(f'e-{i}', total=40.0 + i, spread=-(i + 0.5))
        for i in range(1, n_games + 1))
    return WeekSnapshot(week_number=1, deadline_at=DEADLINE, games=games,
                        tiebreaker_event_id='e-1', **kw)


def _player(picks=(), tiebreaker_tenths=500):
    from games.docket.services.grading.snapshots import PlayerWeekInput

    return PlayerWeekInput(player_id='p', picks=tuple(picks),
                           tiebreaker_tenths=tiebreaker_tenths)


def _pick(slot, eid, market='spread', side='home', **kw):
    from games.docket.services.grading.snapshots import PickSnapshot

    return PickSnapshot(slot=slot, api_event_id=eid, market=market,
                        side=side, **kw)


def _held_subsets():
    """A grid of partial-input shapes: 0..7 held picks, mixed markets."""
    shapes = [()]
    shapes.append((_pick(1, 'e-12', is_best=True),))
    shapes.append((_pick(1, 'e-12'), _pick(4, 'e-11', 'total', 'under')))
    shapes.append(tuple(_pick(s, f'e-{s}') for s in range(1, 6)))
    shapes.append(tuple(_pick(s, f'e-{s}', 'total', 'over')
                        for s in (2, 3, 7)))
    shapes.append(tuple(_pick(s, f'e-{s}') for s in range(1, 8))
                  + (_pick(9, 'e-12', 'total', 'over'),))
    return shapes


@pytest.mark.parametrize('held', _held_subsets(),
                         ids=[f'held{len(s)}' for s in _held_subsets()])
def test_completion_never_overwrites_and_fills_to_eight(held):
    from games.docket.services.grading.autopick import complete_player_input
    from games.docket.services.grading.snapshots import BACKUP_SLOT

    week = _week()
    completed = complete_player_input(week, _player(held))
    scoring = [p for p in completed.picks if p.slot != BACKUP_SLOT]
    assert len(scoring) == 8
    # every held pick survives with its market intact — auto-designation
    # may add is_best to an owned pick (Grading Clarifications: the chain
    # evaluates the final 8-slot set), but never moves the pick itself
    held_keys = {(p.slot, p.api_event_id, p.market, p.side, p.is_autopick)
                 for p in held}
    completed_keys = {(p.slot, p.api_event_id, p.market, p.side,
                       p.is_autopick) for p in completed.picks}
    assert held_keys <= completed_keys
    # exactly one best, never on the backup
    bests = [p for p in completed.picks if p.is_best]
    assert len(bests) == 1
    assert bests[0].slot != BACKUP_SLOT
    # autopick never creates a backup (D5-session)
    added = [p for p in completed.picks
             if (p.slot, p.api_event_id, p.market, p.side, p.is_autopick)
             not in held_keys]
    assert all(p.slot != BACKUP_SLOT for p in added)
    assert all(p.is_autopick for p in added)


@pytest.mark.parametrize('held', _held_subsets(),
                         ids=[f'held{len(s)}' for s in _held_subsets()])
def test_completion_is_idempotent_and_deterministic(held):
    from games.docket.services.grading.autopick import complete_player_input

    week = _week()
    once = complete_player_input(week, _player(held))
    twice = complete_player_input(week, once)
    assert twice.picks == once.picks
    again = complete_player_input(week, _player(held))
    assert again.picks == once.picks


def test_completion_respects_one_side_per_market_against_held_picks():
    """The output must always validate: no added pick may collide with a
    held market (PlayerWeekInput construction enforces it — this proves
    completion routes around the collision instead of raising)."""
    from games.docket.services.grading.autopick import complete_player_input

    week = _week()
    # hold the top-4 totals as UNDERS: the Over bucket must skip them all
    held = tuple(_pick(s, f'e-{12 - i}', 'total', 'under')
                 for i, s in enumerate((1, 2, 3, 4)))
    completed = complete_player_input(week, _player(held))
    markets = [(p.api_event_id, p.market) for p in completed.picks]
    assert len(markets) == len(set(markets))


def test_exhausted_pool_degrades_to_fewer_than_eight():
    """3 pool games for 8 slots: bucket exclusivity is per GAME (D5-session
    — a game claimed by one bucket can't also fill the other), so autopick
    yields at most one pick per pool game. The engine grades the missing
    slots as empty (0 points); it never invents picks."""
    from games.docket.services.grading.autopick import complete_player_input
    from games.docket.services.grading.engine import grade_week
    from games.docket.services.grading.snapshots import BACKUP_SLOT

    week = _week(n_games=3)
    completed = complete_player_input(week, _player(()))
    scoring = [p for p in completed.picks if p.slot != BACKUP_SLOT]
    assert len(scoring) == 3  # one per pool game, never two markets of one
    assert len({p.api_event_id for p in scoring}) == 3
    grade = grade_week(week, [completed]).players[0]
    assert len(grade.slots) == 8
    empties = [s for s in grade.slots if s.via == 'empty']
    assert len(empties) == 5
    assert all(s.points == 0.0 and s.outcome is None for s in empties)


def test_grade_week_points_always_within_zero_and_nine():
    from games.docket.services.grading.autopick import complete_player_input
    from games.docket.services.grading.engine import grade_week

    week = _week()
    for held in _held_subsets():
        completed = complete_player_input(week, _player(held))
        grade = grade_week(week, [completed]).players[0]
        assert 0.0 <= grade.points <= 9.0
