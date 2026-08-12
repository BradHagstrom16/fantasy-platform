"""The parametrized fixture runner (D10-eng): one runner, every case.

Week cases: grade_week(case.week, case.players) must reproduce the
hand-graded expectations exactly — points, wins, error (integer tenths),
and, where the fixture asserts it, the full per-slot trace. Season cases:
each week grades through grade_week, then season_standings must reproduce
the expected table exactly (rank, drop, cumulative error).

A failure names its fixture file (param id = filename stem).
"""
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / 'fixtures' / 'docket'
WEEK_CASES = sorted(FIXTURE_DIR.glob('week_*.json'))
SEASON_CASES = sorted(FIXTURE_DIR.glob('season_*.json'))


def _ids(paths):
    return [p.stem for p in paths]


def test_catalog_is_not_empty():
    """A glob typo or a moved directory must fail loudly, never collect
    zero cases and pass green."""
    assert WEEK_CASES, f'no week fixtures found under {FIXTURE_DIR}'


def _assert_player_grade(got, exp, where):
    assert isinstance(got.error_tenths, int) and \
        not isinstance(got.error_tenths, bool), (
            f'{where}: error_tenths must be a true int (D20-eng)')
    assert got.points == exp.points, (
        f'{where}: points {got.points} != expected {exp.points}')
    assert got.wins == exp.wins, (
        f'{where}: wins {got.wins} != expected {exp.wins}')
    assert got.error_tenths == exp.error_tenths, (
        f'{where}: error_tenths {got.error_tenths} != '
        f'expected {exp.error_tenths}')
    if exp.used_default_prediction is not None:
        assert got.used_default_prediction == exp.used_default_prediction, (
            f'{where}: used_default_prediction '
            f'{got.used_default_prediction} != '
            f'expected {exp.used_default_prediction}')
    if exp.slots is not None:
        by_slot = {s.slot: s for s in got.slots}
        for exp_slot in exp.slots:
            got_slot = by_slot[exp_slot.slot]
            for attr in ('api_event_id', 'market', 'side', 'outcome',
                         'via', 'is_best', 'is_autopick', 'points'):
                assert getattr(got_slot, attr) == getattr(exp_slot, attr), (
                    f'{where} slot {exp_slot.slot}: {attr} '
                    f'{getattr(got_slot, attr)!r} != '
                    f'expected {getattr(exp_slot, attr)!r}')


def _grade_and_check_week(case, where):
    from games.docket.services.grading.engine import grade_week

    grade = grade_week(case.week, case.players)
    graded = {g.player_id: g for g in grade.players}
    assert set(graded) == {p.player_id for p in case.players}, (
        f'{where}: every submitted player gets exactly one grade')
    for player_id, exp in case.expected.items():
        _assert_player_grade(graded[player_id], exp,
                             f'{where}/{player_id}')
    return grade


@pytest.mark.parametrize('path', WEEK_CASES, ids=_ids(WEEK_CASES))
def test_week_cases(path):
    from games.docket.services.grading.codec import load_week_case

    case = load_week_case(path)
    _grade_and_check_week(case, path.stem)


@pytest.mark.parametrize('path', SEASON_CASES, ids=_ids(SEASON_CASES))
def test_season_cases(path):
    from games.docket.services.grading.codec import load_season_case
    from games.docket.services.grading.season import season_standings

    case = load_season_case(path)
    week_grades = [
        _grade_and_check_week(wk, f'{path.stem}/week{wk.week.week_number}')
        for wk in case.weeks
    ]
    standings = season_standings(week_grades, case.roster)
    assert len(standings) == len(case.expected_standings), (
        f'{path.stem}: standings row count')
    for got, exp in zip(standings, case.expected_standings, strict=True):
        where = f'{path.stem}/standings/{exp.player_id}'
        assert got.player_id == exp.player_id, (
            f'{where}: order — got {got.player_id}')
        assert got.rank == exp.rank, f'{where}: rank {got.rank}'
        assert got.total_points == exp.points, (
            f'{where}: points {got.total_points}')
        assert got.wins == exp.wins, f'{where}: wins {got.wins}'
        assert isinstance(got.error_tenths, int) and \
            not isinstance(got.error_tenths, bool)
        assert got.error_tenths == exp.error_tenths, (
            f'{where}: error_tenths {got.error_tenths}')
        assert got.dropped_week == exp.dropped_week, (
            f'{where}: dropped_week {got.dropped_week}')
        assert got.dropped_points == exp.dropped_points, (
            f'{where}: dropped_points {got.dropped_points}')
