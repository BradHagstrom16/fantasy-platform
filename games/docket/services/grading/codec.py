"""Strict JSON fixture codec: case files <-> snapshot types (D10-eng).

Shipped code, not test scaffolding: the runner loads every fixture through
here, and the bridge/export path writes permanent real-world fixtures
through dump_week_case — one format, one codec, no drift.

Strictness contract: unknown keys fail at every nesting level, naming the
key; required keys must be present (nullable values are spelled null, never
omitted); datetimes must be naive ISO strings; predictions are 0.1-step
decimals converted EXACTLY to integer tenths (a non-tenth value is a data
error, refused, never rounded); expected error values are already integer
tenths (bool refused).
"""
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from games.docket.services.grading.snapshots import (
    GameSnapshot,
    Market,
    Outcome,
    PickSnapshot,
    PlayerWeekInput,
    Side,
    WeekSnapshot,
)


@dataclass(frozen=True, slots=True)
class ExpectedSlot:
    """One asserted slot-trace line. Explicit by design: event/market/side/
    outcome must be spelled (null for nc_push/empty slots), so a fixture
    can never under-assert by omission."""
    slot: int
    api_event_id: str | None
    market: Market | None
    side: Side | None
    outcome: Outcome | None
    via: str
    is_best: bool
    is_autopick: bool
    points: float


@dataclass(frozen=True, slots=True)
class ExpectedPlayer:
    points: float
    wins: int
    error_tenths: int
    used_default_prediction: bool | None  # None = fixture doesn't assert it
    slots: tuple[ExpectedSlot, ...] | None  # None = no trace assertion


@dataclass(frozen=True, slots=True)
class ExpectedStanding:
    player_id: str
    rank: int
    points: float
    wins: int
    error_tenths: int
    dropped_week: int | None
    dropped_points: float | None


@dataclass(frozen=True, slots=True)
class WeekCase:
    description: str
    rulings: tuple[str, ...]
    week: WeekSnapshot
    players: tuple[PlayerWeekInput, ...]
    expected: dict  # player_id -> ExpectedPlayer; may be empty (season weeks)


@dataclass(frozen=True, slots=True)
class SeasonCase:
    description: str
    rulings: tuple[str, ...]
    roster: tuple[str, ...]
    weeks: tuple[WeekCase, ...]
    expected_standings: tuple[ExpectedStanding, ...]


def _check_keys(mapping, where, required, optional=frozenset()):
    if not isinstance(mapping, dict):
        raise ValueError(f'{where}: expected an object')
    unknown = set(mapping) - set(required) - set(optional)
    if unknown:
        raise ValueError(f'{where}: unknown key(s) {sorted(unknown)}')
    missing = set(required) - set(mapping)
    if missing:
        raise ValueError(f'{where}: missing required key(s) '
                         f'{sorted(missing)}')


def _naive_datetime(value, where):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        raise ValueError(
            f'{where}: datetimes must be naive UTC ISO strings, '
            f'got {value!r}')
    return parsed


def _strict_int(value, where):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f'{where}: must be an integer, got {value!r}')
    return value


def _strict_bool(value, where):
    """JSON true/false only — bool("false") is True, so a string or 0/1
    flag would silently flip a No Contest or a designation."""
    if not isinstance(value, bool):
        raise ValueError(f'{where}: must be true or false, got {value!r}')
    return value


def _number(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{where}: must be a number, got {value!r}')
    return float(value)


def _optional_number(value, where):
    return None if value is None else _number(value, where)


def _to_tenths(value, where):
    """Human-readable 0.1-step decimal -> integer tenths, exactly.

    Decimal(str(x)) sees the written digits, so 41.7 -> 417 with no float
    residue; 41.75 is refused loudly (never rounded)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{where}: must be a number or null, got {value!r}')
    scaled = Decimal(str(value)) * 10
    if scaled != scaled.to_integral_value():
        raise ValueError(
            f'{where}: {value!r} is not a whole tenth (0.1-step rule)')
    return int(scaled)


def _parse_game(raw, where):
    _check_keys(
        raw, where,
        required=('api_event_id', 'sport', 'home_team', 'away_team',
                  'kickoff_at_deadline', 'home_spread', 'total',
                  'home_score', 'away_score'),
        optional=('no_contest',))
    return GameSnapshot(
        api_event_id=raw['api_event_id'],
        sport=raw['sport'],
        home_team=raw['home_team'],
        away_team=raw['away_team'],
        kickoff_at_deadline=_naive_datetime(
            raw['kickoff_at_deadline'], f'{where}.kickoff_at_deadline'),
        home_spread=_optional_number(
            raw['home_spread'], f'{where}.home_spread'),
        total=_optional_number(raw['total'], f'{where}.total'),
        home_score=(None if raw['home_score'] is None
                    else _strict_int(raw['home_score'],
                                     f'{where}.home_score')),
        away_score=(None if raw['away_score'] is None
                    else _strict_int(raw['away_score'],
                                     f'{where}.away_score')),
        no_contest=_strict_bool(raw.get('no_contest', False),
                                f'{where}.no_contest'),
    )


def _parse_week(raw, where):
    _check_keys(raw, where,
                required=('week_number', 'deadline_at',
                          'tiebreaker_event_id', 'games'))
    return WeekSnapshot(
        week_number=_strict_int(raw['week_number'], f'{where}.week_number'),
        deadline_at=_naive_datetime(raw['deadline_at'],
                                    f'{where}.deadline_at'),
        games=tuple(_parse_game(g, f'{where}.games[{i}]')
                    for i, g in enumerate(raw['games'])),
        tiebreaker_event_id=raw['tiebreaker_event_id'],
    )


def _parse_pick(raw, where):
    _check_keys(raw, where,
                required=('slot', 'event', 'market', 'side'),
                optional=('best', 'autopick'))
    return PickSnapshot(
        slot=_strict_int(raw['slot'], f'{where}.slot'),
        api_event_id=raw['event'],
        market=raw['market'],
        side=raw['side'],
        is_best=_strict_bool(raw.get('best', False), f'{where}.best'),
        is_autopick=_strict_bool(raw.get('autopick', False),
                                 f'{where}.autopick'),
    )


def _parse_player(raw, where):
    _check_keys(raw, where, required=('player_id', 'tiebreaker', 'picks'))
    return PlayerWeekInput(
        player_id=raw['player_id'],
        picks=tuple(_parse_pick(p, f'{where}.picks[{i}]')
                    for i, p in enumerate(raw['picks'])),
        tiebreaker_tenths=_to_tenths(raw['tiebreaker'],
                                     f'{where}.tiebreaker'),
    )


def _parse_expected_slot(raw, where):
    _check_keys(raw, where,
                required=('slot', 'event', 'market', 'side', 'outcome',
                          'via', 'points'),
                optional=('best', 'autopick'))
    return ExpectedSlot(
        slot=_strict_int(raw['slot'], f'{where}.slot'),
        api_event_id=raw['event'],
        market=None if raw['market'] is None else Market(raw['market']),
        side=None if raw['side'] is None else Side(raw['side']),
        outcome=None if raw['outcome'] is None else Outcome(raw['outcome']),
        via=raw['via'],
        is_best=_strict_bool(raw.get('best', False), f'{where}.best'),
        is_autopick=_strict_bool(raw.get('autopick', False),
                                 f'{where}.autopick'),
        points=_number(raw['points'], f'{where}.points'),
    )


def _parse_expected_player(raw, where):
    _check_keys(raw, where,
                required=('points', 'wins', 'error_tenths'),
                optional=('used_default_prediction', 'slots'))
    slots = raw.get('slots')
    return ExpectedPlayer(
        points=_number(raw['points'], f'{where}.points'),
        wins=_strict_int(raw['wins'], f'{where}.wins'),
        error_tenths=_strict_int(raw['error_tenths'],
                                 f'{where}.error_tenths'),
        used_default_prediction=(
            None if 'used_default_prediction' not in raw
            else _strict_bool(raw['used_default_prediction'],
                              f'{where}.used_default_prediction')),
        slots=(None if slots is None else tuple(
            _parse_expected_slot(s, f'{where}.slots[{i}]')
            for i, s in enumerate(slots))),
    )


def _parse_week_entry(raw, where, *, expected_required):
    required = ['week', 'players']
    optional = ['description', 'rulings']
    (required if expected_required else optional).append('expected')
    _check_keys(raw, where, required=tuple(required),
                optional=tuple(optional))
    return WeekCase(
        description=raw.get('description', ''),
        rulings=tuple(raw.get('rulings', ())),
        week=_parse_week(raw['week'], f'{where}.week'),
        players=tuple(_parse_player(p, f'{where}.players[{i}]')
                      for i, p in enumerate(raw['players'])),
        expected={
            player_id: _parse_expected_player(
                exp, f'{where}.expected[{player_id}]')
            for player_id, exp in raw.get('expected', {}).items()
        },
    )


def load_week_case(path) -> WeekCase:
    raw = json.loads(Path(path).read_text())
    _check_keys(raw, 'case', required=('description', 'week', 'players',
                                       'expected'),
                optional=('rulings',))
    return _parse_week_entry(raw, 'case', expected_required=True)


def _parse_expected_standing(raw, where):
    _check_keys(raw, where,
                required=('player_id', 'rank', 'points', 'wins',
                          'error_tenths', 'dropped_week', 'dropped_points'))
    return ExpectedStanding(
        player_id=raw['player_id'],
        rank=_strict_int(raw['rank'], f'{where}.rank'),
        points=_number(raw['points'], f'{where}.points'),
        wins=_strict_int(raw['wins'], f'{where}.wins'),
        error_tenths=_strict_int(raw['error_tenths'],
                                 f'{where}.error_tenths'),
        dropped_week=(None if raw['dropped_week'] is None
                      else _strict_int(raw['dropped_week'],
                                       f'{where}.dropped_week')),
        dropped_points=_optional_number(raw['dropped_points'],
                                        f'{where}.dropped_points'),
    )


def load_season_case(path) -> SeasonCase:
    raw = json.loads(Path(path).read_text())
    _check_keys(raw, 'case', required=('description', 'roster', 'weeks',
                                       'expected_standings'),
                optional=('rulings',))
    return SeasonCase(
        description=raw['description'],
        rulings=tuple(raw.get('rulings', ())),
        roster=tuple(raw['roster']),
        weeks=tuple(
            _parse_week_entry(w, f'weeks[{i}]', expected_required=False)
            for i, w in enumerate(raw['weeks'])),
        expected_standings=tuple(
            _parse_expected_standing(s, f'expected_standings[{i}]')
            for i, s in enumerate(raw['expected_standings'])),
    )


# --- Dump (the bridge/export write path)


def _tenths_to_decimal(tenths):
    if tenths is None:
        return None
    whole, frac = divmod(abs(tenths), 10)
    sign = -1 if tenths < 0 else 1
    return sign * (whole + frac / 10)


def _dump_game(game):
    out = {
        'api_event_id': game.api_event_id,
        'sport': game.sport,
        'home_team': game.home_team,
        'away_team': game.away_team,
        'kickoff_at_deadline': game.kickoff_at_deadline.isoformat(),
        'home_spread': game.home_spread,
        'total': game.total,
        'home_score': game.home_score,
        'away_score': game.away_score,
    }
    if game.no_contest:
        out['no_contest'] = True
    return out


def _dump_pick(pick):
    out = {'slot': pick.slot, 'event': pick.api_event_id,
           'market': str(pick.market), 'side': str(pick.side)}
    if pick.is_best:
        out['best'] = True
    if pick.is_autopick:
        out['autopick'] = True
    return out


def _dump_expected_slot(slot):
    out = {
        'slot': slot.slot,
        'event': slot.api_event_id,
        'market': None if slot.market is None else str(slot.market),
        'side': None if slot.side is None else str(slot.side),
        'outcome': None if slot.outcome is None else str(slot.outcome),
        'via': slot.via,
        'points': slot.points,
    }
    if slot.is_best:
        out['best'] = True
    if slot.is_autopick:
        out['autopick'] = True
    return out


def _dump_expected_player(exp):
    out = {'points': exp.points, 'wins': exp.wins,
           'error_tenths': exp.error_tenths}
    if exp.used_default_prediction is not None:
        out['used_default_prediction'] = exp.used_default_prediction
    if exp.slots is not None:
        out['slots'] = [_dump_expected_slot(s) for s in exp.slots]
    return out


def dump_week_case(case: WeekCase) -> dict:
    out = {'description': case.description}
    if case.rulings:
        out['rulings'] = list(case.rulings)
    out['week'] = {
        'week_number': case.week.week_number,
        'deadline_at': case.week.deadline_at.isoformat(),
        'tiebreaker_event_id': case.week.tiebreaker_event_id,
        'games': [_dump_game(g) for g in case.week.games],
    }
    out['players'] = [
        {'player_id': p.player_id,
         'tiebreaker': _tenths_to_decimal(p.tiebreaker_tenths),
         'picks': [_dump_pick(pick) for pick in p.picks]}
        for p in case.players
    ]
    out['expected'] = {
        player_id: _dump_expected_player(exp)
        for player_id, exp in case.expected.items()
    }
    return out
