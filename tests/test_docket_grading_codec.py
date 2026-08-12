"""Strict fixture codec: JSON case files <-> snapshot types (D10-eng).

The loader FAILS on unknown keys at every nesting level (naming the key), so
a typo'd fixture can never silently assert nothing. dump/load round-trips
exactly — the future bridge/export path writes fixtures through dump, so the
codec is shipped code, not test scaffolding.
"""
import copy
import json

import pytest

WEEK_CASE = {
    'description': 'two players, one graded game',
    'rulings': ['D4-session'],
    'week': {
        'week_number': 1,
        'deadline_at': '2026-09-05T16:00:00',
        'tiebreaker_event_id': 'e-1',
        'games': [
            {
                'api_event_id': 'e-1',
                'sport': 'americanfootball_ncaaf',
                'home_team': 'Notre Dame Fighting Irish',
                'away_team': 'Wisconsin Badgers',
                'kickoff_at_deadline': '2026-09-05T16:00:00',
                'home_spread': -20.5,
                'total': 47.5,
                'home_score': 27,
                'away_score': 20,
            },
            {
                'api_event_id': 'e-2',
                'sport': 'americanfootball_nfl',
                'home_team': 'Green Bay Packers',
                'away_team': 'Chicago Bears',
                'kickoff_at_deadline': '2026-09-06T17:00:00',
                'home_spread': -6.5,
                'total': 44.0,
                'home_score': None,
                'away_score': None,
                'no_contest': True,
            },
        ],
    },
    'players': [
        {
            'player_id': 'alice',
            'tiebreaker': 41.7,
            'picks': [
                {'slot': 1, 'event': 'e-1', 'market': 'spread',
                 'side': 'home', 'best': True},
                {'slot': 2, 'event': 'e-1', 'market': 'total',
                 'side': 'over'},
                {'slot': 9, 'event': 'e-2', 'market': 'total',
                 'side': 'under'},
            ],
        },
        {
            'player_id': 'bob',
            'tiebreaker': None,
            'picks': [],
        },
    ],
    'expected': {
        'alice': {
            'points': 1.5,
            'wins': 1,
            'error_tenths': 53,
            'used_default_prediction': False,
            'slots': [
                {'slot': 1, 'event': 'e-1', 'market': 'spread',
                 'side': 'home', 'outcome': 'loss', 'via': 'pick',
                 'best': True, 'points': 0.0},
            ],
        },
        'bob': {
            'points': 4.0,
            'wins': 0,
            'error_tenths': 6,
            'used_default_prediction': True,
        },
    },
}

SEASON_CASE = {
    'description': 'drop activates at two weeks',
    'roster': ['alice', 'bob'],
    'weeks': [
        {'week': WEEK_CASE['week'], 'players': WEEK_CASE['players']},
    ],
    'expected_standings': [
        {'player_id': 'alice', 'rank': 1, 'points': 6.5, 'wins': 5,
         'error_tenths': 53, 'dropped_week': None, 'dropped_points': None},
        {'player_id': 'bob', 'rank': 2, 'points': 4.0, 'wins': 0,
         'error_tenths': 6, 'dropped_week': None, 'dropped_points': None},
    ],
}


def _write(tmp_path, payload, name='case.json'):
    path = tmp_path / name
    path.write_text(json.dumps(payload))
    return path


def _load_week(tmp_path, payload):
    from games.docket.services.grading.codec import load_week_case

    return load_week_case(_write(tmp_path, payload))


# --- Happy path + round trip


def test_week_case_loads_into_snapshot_types(tmp_path):
    from games.docket.services.grading.snapshots import (
        PlayerWeekInput,
        WeekSnapshot,
    )

    case = _load_week(tmp_path, WEEK_CASE)
    assert isinstance(case.week, WeekSnapshot)
    assert case.week.game('e-2').no_contest is True
    assert all(isinstance(p, PlayerWeekInput) for p in case.players)
    alice = next(p for p in case.players if p.player_id == 'alice')
    assert alice.tiebreaker_tenths == 417  # 41.7 -> integer tenths (D20-eng)
    assert alice.picks[0].is_best is True
    bob_expected = case.expected['bob']
    assert bob_expected.error_tenths == 6
    assert bob_expected.used_default_prediction is True
    assert bob_expected.slots is None  # slots trace optional per player


def test_dump_load_round_trip_is_exact(tmp_path):
    """The bridge/export path writes through dump — a fixture must survive
    dump -> load with nothing gained or lost."""
    from games.docket.services.grading.codec import (
        dump_week_case,
        load_week_case,
    )

    case = _load_week(tmp_path, WEEK_CASE)
    dumped = dump_week_case(case)
    reloaded = load_week_case(_write(tmp_path, dumped, 'reloaded.json'))
    assert reloaded == case


def test_season_case_loads(tmp_path):
    from games.docket.services.grading.codec import load_season_case

    case = load_season_case(_write(tmp_path, SEASON_CASE))
    assert case.roster == ('alice', 'bob')
    assert len(case.weeks) == 1
    assert case.expected_standings[0].player_id == 'alice'
    assert case.expected_standings[0].dropped_week is None


# --- Strictness: unknown keys fail, naming the key


@pytest.mark.parametrize('mutate,unknown_key', [
    (lambda c: c.__setitem__('bonus_round', True), 'bonus_round'),
    (lambda c: c['week'].__setitem__('theme', 'dark'), 'theme'),
    (lambda c: c['week']['games'][0].__setitem__('venue', 'dome'), 'venue'),
    (lambda c: c['players'][0].__setitem__('mood', 'confident'), 'mood'),
    (lambda c: c['players'][0]['picks'][0].__setitem__('note', 'lock'),
     'note'),
    (lambda c: c['expected']['alice'].__setitem__('style_points', 11),
     'style_points'),
    (lambda c: c['expected']['alice']['slots'][0].__setitem__('vibe', 'w'),
     'vibe'),
])
def test_unknown_key_fails_naming_the_key(tmp_path, mutate, unknown_key):
    payload = copy.deepcopy(WEEK_CASE)
    mutate(payload)
    with pytest.raises(ValueError, match=unknown_key):
        _load_week(tmp_path, payload)


def test_missing_required_expected_key_fails(tmp_path):
    """points/wins/error_tenths are mandatory per expected player — a
    fixture that forgets one asserts less than it claims to."""
    payload = copy.deepcopy(WEEK_CASE)
    del payload['expected']['alice']['error_tenths']
    with pytest.raises(ValueError, match='error_tenths'):
        _load_week(tmp_path, payload)


# --- Value-space rejections


def test_timezone_suffixed_datetime_rejected(tmp_path):
    """Naive UTC only: a Z/offset suffix means the writer was thinking in
    aware datetimes and the whole file is suspect."""
    payload = copy.deepcopy(WEEK_CASE)
    payload['week']['deadline_at'] = '2026-09-05T16:00:00+00:00'
    with pytest.raises(ValueError, match='naive'):
        _load_week(tmp_path, payload)


def test_non_tenth_prediction_rejected(tmp_path):
    """Predictions are 0.1-step by rule; 41.75 is not a prediction, it is a
    data error — refused, never rounded (D20-eng)."""
    payload = copy.deepcopy(WEEK_CASE)
    payload['players'][0]['tiebreaker'] = 41.75
    with pytest.raises(ValueError, match='tenth'):
        _load_week(tmp_path, payload)


def test_float_error_tenths_in_expected_rejected(tmp_path):
    """Fixture expectations are IN TENTHS already — a float here means the
    author wrote 5.3 meaning 53, and the runner must refuse to guess."""
    payload = copy.deepcopy(WEEK_CASE)
    payload['expected']['alice']['error_tenths'] = 5.3
    with pytest.raises(ValueError, match='error_tenths'):
        _load_week(tmp_path, payload)


def test_bool_error_tenths_rejected(tmp_path):
    payload = copy.deepcopy(WEEK_CASE)
    payload['expected']['alice']['error_tenths'] = True
    with pytest.raises(ValueError, match='error_tenths'):
        _load_week(tmp_path, payload)
