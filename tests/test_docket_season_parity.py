"""Parity: the persisted path and the engine path must agree.

The season fixtures (tests/fixtures/docket/season_*.json) are the binding
catalog — drop activation, equal-lowest tie, late-joiner default error,
three-key competition rank, cumulative error surviving the drop. The pure
suite runs them through grade_week; this one materializes the same grades as
docket_week_result rows and replays them through the ORM adapter.

If the two ever disagree, the ledger is lying about a ruling.
"""
from datetime import datetime
from pathlib import Path

import pytest

from extensions import db
from games.docket.models import DocketWeek, DocketWeekResult
from tests._docket_fixtures import make_enrollment, make_user

FIXTURES = Path(__file__).parent / 'fixtures' / 'docket'
SEASON_CASES = sorted(FIXTURES.glob('season_*.json'))


def _ids(paths):
    return [p.stem for p in paths]


def _materialize(case, week_grades):
    """Write the engine's grades to the DB exactly as the grading pass would.

    Only players present in a WeekGrade get a result row — which is what
    makes the late-joiner case real: an absent member has no row and must be
    charged the week's default error by the season pass, not by this seed.
    """
    users = {}
    for name in case.roster:
        user = make_user(name)
        make_enrollment(user)
        users[name] = user
    db.session.flush()

    for grade in week_grades:
        week = DocketWeek(
            week_number=grade.week_number,
            start_at=datetime(2026, 9, 1, 11, 0),
            end_at=datetime(2026, 9, 8, 11, 0),
            deadline_at=datetime(2026, 9, 5, 16, 0),
            default_error_tenths=grade.default_error_tenths,
        )
        db.session.add(week)
        db.session.flush()
        for player in grade.players:
            db.session.add(DocketWeekResult(
                user_id=users[player.player_id].id,
                week_id=week.id,
                points=player.points,
                wins=player.wins,
                error_tenths=player.error_tenths,
                graded_at=datetime(2026, 9, 6, 4, 0),
            ))
    db.session.commit()
    return users


@pytest.mark.parametrize('path', SEASON_CASES, ids=_ids(SEASON_CASES))
def test_every_season_fixture_replays_through_the_db_path(app, path):
    from games.docket.services.grading.codec import load_season_case
    from games.docket.services.grading.engine import grade_week
    from games.docket.services.season_pass import season_ledger

    case = load_season_case(path)
    week_grades = [grade_week(wk.week, wk.players) for wk in case.weeks]
    users = _materialize(case, week_grades)
    by_user_id = {user.id: name for name, user in users.items()}

    got = {
        by_user_id[row.enrollment.user_id]: row.standing
        for row in season_ledger().rows
    }
    assert set(got) == set(case.roster), f'{path.stem}: roster coverage'

    for expected in case.expected_standings:
        where = f'{path.stem}/{expected.player_id}'
        standing = got[expected.player_id]
        assert standing.rank == expected.rank, f'{where}: rank'
        assert standing.total_points == expected.points, f'{where}: points'
        assert standing.wins == expected.wins, f'{where}: wins'
        assert standing.error_tenths == expected.error_tenths, \
            f'{where}: error_tenths'
        assert isinstance(standing.error_tenths, int) and \
            not isinstance(standing.error_tenths, bool), \
            f'{where}: key 3 stayed integer tenths through the DB'
        assert standing.dropped_week == expected.dropped_week, \
            f'{where}: dropped_week'
        assert standing.dropped_points == expected.dropped_points, \
            f'{where}: dropped_points'


@pytest.mark.parametrize('path', SEASON_CASES, ids=_ids(SEASON_CASES))
def test_db_rollups_equal_engine_rollups(app, path):
    """Stronger than comparing standings: the two producers of WeekRollup
    must emit equal frozen values, so nothing downstream can diverge."""
    from games.docket.services.grading.codec import load_season_case
    from games.docket.services.grading.engine import grade_week
    from games.docket.services.grading.season import week_rollup
    from games.docket.services.season_pass import week_rollups_from_db

    case = load_season_case(path)
    week_grades = [grade_week(wk.week, wk.players) for wk in case.weeks]
    users = _materialize(case, week_grades)

    from_engine = [week_rollup(g) for g in week_grades]
    from_db = week_rollups_from_db()
    assert len(from_db) == len(from_engine), f'{path.stem}: week count'

    # player_id is the fixture name on the engine side and str(user_id) on the
    # DB side; compare on the numbers with the ids normalized.
    id_for = {name: str(user.id) for name, user in users.items()}
    for engine_rollup, db_rollup in zip(from_engine, from_db, strict=True):
        where = f'{path.stem}/week{engine_rollup.week_number}'
        assert db_rollup.week_number == engine_rollup.week_number, where
        assert db_rollup.default_error_tenths == \
            engine_rollup.default_error_tenths, f'{where}: default error'
        expected = {
            (id_for[p.player_id], p.points, p.wins, p.error_tenths)
            for p in engine_rollup.players
        }
        actual = {
            (p.player_id, p.points, p.wins, p.error_tenths)
            for p in db_rollup.players
        }
        assert actual == expected, f'{where}: player totals'
