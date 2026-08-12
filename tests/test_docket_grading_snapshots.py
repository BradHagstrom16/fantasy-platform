"""Grading-engine snapshot types: frozenness + construction-time validation.

The engine's I/O is typed frozen dataclasses (D9-eng) — invalid inputs are
refused at construction, so the grading functions never re-validate. All
datetimes are NAIVE UTC (the D6-eng contract carried into pure data);
tz-aware values raise instead of silently shifting.
"""
import dataclasses
from datetime import UTC, datetime

import pytest

KICKOFF = datetime(2026, 9, 5, 16, 0)
DEADLINE = datetime(2026, 9, 5, 16, 0)


def _game(eid='e-1', **kw):
    from games.docket.services.grading.snapshots import GameSnapshot

    defaults = {
        'api_event_id': eid,
        'sport': 'americanfootball_ncaaf',
        'home_team': 'Notre Dame Fighting Irish',
        'away_team': 'Wisconsin Badgers',
        'kickoff_at_deadline': KICKOFF,
        'home_spread': -20.5,
        'total': 47.5,
        'home_score': None,
        'away_score': None,
    }
    defaults.update(kw)
    return GameSnapshot(**defaults)


def _week(games=None, tiebreaker='e-1', **kw):
    from games.docket.services.grading.snapshots import WeekSnapshot

    defaults = {
        'week_number': 1,
        'deadline_at': DEADLINE,
        'games': tuple(games) if games is not None else (_game(),),
        'tiebreaker_event_id': tiebreaker,
    }
    defaults.update(kw)
    return WeekSnapshot(**defaults)


def _pick(slot=1, eid='e-1', market='spread', side='home', **kw):
    from games.docket.services.grading.snapshots import PickSnapshot

    return PickSnapshot(slot=slot, api_event_id=eid, market=market,
                        side=side, **kw)


def _player(picks, player_id='alice', tiebreaker_tenths=475):
    from games.docket.services.grading.snapshots import PlayerWeekInput

    return PlayerWeekInput(player_id=player_id, picks=tuple(picks),
                           tiebreaker_tenths=tiebreaker_tenths)


# --- Frozenness


def test_every_snapshot_dataclass_is_frozen_with_slots():
    """D9-eng: engine I/O is immutable — every dataclass in snapshots.py is
    frozen (and slotted, so no dict escape hatch exists either)."""
    from games.docket.services.grading import snapshots

    dc_types = [obj for obj in vars(snapshots).values()
                if isinstance(obj, type) and dataclasses.is_dataclass(obj)]
    assert len(dc_types) >= 8, 'expected the full snapshot type family'
    for dc in dc_types:
        assert dc.__dataclass_params__.frozen, f'{dc.__name__} must be frozen'
        assert '__slots__' in vars(dc), f'{dc.__name__} must use slots'


def test_snapshot_attributes_cannot_be_assigned():
    game = _game()
    with pytest.raises(dataclasses.FrozenInstanceError):
        game.home_score = 21
    pick = _pick()
    with pytest.raises(dataclasses.FrozenInstanceError):
        pick.slot = 2


# --- GameSnapshot validation


def test_game_rejects_timezone_aware_kickoff():
    """Naive UTC only: an aware datetime is a caller bug, refused loudly —
    never comparable-but-shifted."""
    with pytest.raises(ValueError, match='naive'):
        _game(kickoff_at_deadline=datetime(2026, 9, 5, 16, 0, tzinfo=UTC))


def test_game_rejects_one_sided_score():
    """Scores are both-or-neither: a half-entered final can never grade."""
    with pytest.raises(ValueError, match='both'):
        _game(home_score=21, away_score=None)
    with pytest.raises(ValueError, match='both'):
        _game(home_score=None, away_score=17)


def test_game_accepts_final_score_and_no_contest():
    game = _game(home_score=27, away_score=20)
    assert (game.home_score, game.away_score) == (27, 20)
    assert _game(no_contest=True).no_contest is True


@pytest.mark.parametrize('kw', [
    {'home_spread': 1.1}, {'total': 33.3}, {'home_spread': True},
])
def test_game_rejects_non_quarter_point_lines(kw):
    """Lines are quarter-point multiples — dyadic and float-exact; a 1.1
    would silently corrupt push comparisons."""
    with pytest.raises(ValueError):
        _game(**kw)


def test_game_accepts_quarter_point_line():
    assert _game(home_spread=-6.25).home_spread == -6.25


def test_week_normalizes_games_list_to_tuple():
    """A caller-held list must not be a mutation escape hatch out of the
    frozen contract: the snapshot owns an immutable copy."""
    from games.docket.services.grading.snapshots import WeekSnapshot

    games = [_game('e-1'), _game('e-2')]
    week = WeekSnapshot(week_number=1, deadline_at=DEADLINE, games=games,
                        tiebreaker_event_id='e-1')
    assert isinstance(week.games, tuple)
    games.append(_game('e-3'))
    assert len(week.games) == 2

    from games.docket.services.grading.snapshots import PlayerWeekInput

    picks = [_pick(slot=1, eid='e-1')]
    player = PlayerWeekInput(player_id='p', picks=picks,
                             tiebreaker_tenths=None)
    assert isinstance(player.picks, tuple)
    picks.append(_pick(slot=2, eid='e-2'))
    assert len(player.picks) == 1


# --- WeekSnapshot validation


def test_week_rejects_duplicate_event_ids():
    with pytest.raises(ValueError, match='api_event_id'):
        _week(games=(_game('dup'), _game('dup')))


def test_week_rejects_tiebreaker_not_on_docket():
    """The designated game must be one of the week's games — a dangling
    designation would make key 3 ungradeable."""
    with pytest.raises(ValueError, match='tiebreaker'):
        _week(tiebreaker='e-missing')


def test_week_rejects_timezone_aware_deadline():
    with pytest.raises(ValueError, match='naive'):
        _week(deadline_at=datetime(2026, 9, 5, 16, 0, tzinfo=UTC))


def test_week_game_lookup_by_event_id():
    week = _week(games=(_game('e-1'), _game('e-2')))
    assert week.game('e-2').api_event_id == 'e-2'
    with pytest.raises(KeyError):
        week.game('e-nope')


# --- PickSnapshot validation


@pytest.mark.parametrize('bad_slot', [0, 10, -1])
def test_pick_rejects_out_of_range_slot(bad_slot):
    with pytest.raises(ValueError, match='slot'):
        _pick(slot=bad_slot)


@pytest.mark.parametrize('market,side', [
    ('spread', 'over'), ('spread', 'under'),
    ('total', 'home'), ('total', 'away'),
])
def test_pick_rejects_market_side_mismatch(market, side):
    """spread picks take home/away; total picks take over/under — a crossed
    pair is a construction error, not a graded loss."""
    with pytest.raises(ValueError, match='side'):
        _pick(market=market, side=side)


def test_pick_rejects_best_on_backup_slot():
    """D6-session: the designation lives on a SCORING slot; slot 9 can never
    carry it."""
    with pytest.raises(ValueError, match='backup'):
        _pick(slot=9, is_best=True)


def test_pick_coerces_market_and_side_strings_to_enums():
    from games.docket.services.grading.snapshots import Market, Side

    pick = _pick(market='total', side='over')
    assert pick.market is Market.TOTAL
    assert pick.side is Side.OVER


def test_pick_rejects_unknown_market_or_side():
    with pytest.raises(ValueError):
        _pick(market='moneyline', side='home')
    with pytest.raises(ValueError):
        _pick(market='spread', side='push')


# --- PlayerWeekInput validation


def test_player_rejects_duplicate_slots():
    with pytest.raises(ValueError, match='slot'):
        _player([_pick(slot=1, eid='e-1'),
                 _pick(slot=1, eid='e-2')])


def test_player_rejects_both_sides_of_one_market():
    """Core ruling: one side per market. Same event+market twice — even with
    different sides, even across different slots — is invalid input."""
    with pytest.raises(ValueError, match='market'):
        _player([_pick(slot=1, eid='e-1', side='home'),
                 _pick(slot=2, eid='e-1', side='away')])


def test_player_allows_spread_and_total_on_same_game():
    player = _player([_pick(slot=1, eid='e-1', market='spread', side='home'),
                      _pick(slot=2, eid='e-1', market='total', side='over')])
    assert len(player.picks) == 2


def test_player_rejects_two_best_picks():
    with pytest.raises(ValueError, match='best'):
        _player([_pick(slot=1, eid='e-1', is_best=True),
                 _pick(slot=2, eid='e-2', is_best=True)])


def test_player_rejects_more_than_nine_picks():
    picks = [_pick(slot=s, eid=f'e-{s}') for s in range(1, 10)]
    with pytest.raises(ValueError, match='nine|9'):
        from games.docket.services.grading.snapshots import (
            PickSnapshot,
            PlayerWeekInput,
        )
        # force a 10th by duplicating outside the slot range guard: build
        # a raw tuple with a valid extra pick on an already-used slot count
        PlayerWeekInput(player_id='x',
                        picks=tuple(picks) + (PickSnapshot(
                            slot=1, api_event_id='e-extra', market='spread',
                            side='home'),),
                        tiebreaker_tenths=None)


def test_player_tiebreaker_tenths_is_int_or_none_never_bool():
    """D20-eng: key 3 is integer tenths — bool is a Python int subtype and
    must be refused explicitly, not laundered into arithmetic."""
    _player([_pick()], tiebreaker_tenths=None)
    _player([_pick()], tiebreaker_tenths=515)
    with pytest.raises(ValueError, match='tenths'):
        _player([_pick()], tiebreaker_tenths=True)
    with pytest.raises(ValueError, match='tenths'):
        _player([_pick()], tiebreaker_tenths=51.5)


# --- Output types sanity


def test_player_week_grade_requires_exactly_eight_slots():
    from games.docket.services.grading.snapshots import (
        Outcome,
        PlayerWeekGrade,
        SlotGrade,
    )

    def slot(n):
        return SlotGrade(slot=n, api_event_id=f'e-{n}', market='spread',
                         side='home', outcome=Outcome.WIN, is_best=False,
                         is_autopick=False, via='pick', points=1.0)

    grade = PlayerWeekGrade(player_id='alice',
                            slots=tuple(slot(n) for n in range(1, 9)),
                            points=8.0, wins=8, error_tenths=0,
                            used_default_prediction=False)
    assert len(grade.slots) == 8
    with pytest.raises(ValueError, match='eight|8'):
        PlayerWeekGrade(player_id='alice',
                        slots=tuple(slot(n) for n in range(1, 8)),
                        points=7.0, wins=7, error_tenths=0,
                        used_default_prediction=False)


def test_slot_grade_rejects_unknown_via():
    from games.docket.services.grading.snapshots import Outcome, SlotGrade

    with pytest.raises(ValueError, match='via'):
        SlotGrade(slot=1, api_event_id='e-1', market='spread', side='home',
                  outcome=Outcome.WIN, is_best=False, is_autopick=False,
                  via='teleport', points=1.0)
