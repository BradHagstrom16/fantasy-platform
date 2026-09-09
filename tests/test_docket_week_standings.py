"""week_standings: one graded week ranked on its own three keys.

The single-week sibling of the season pass, feeding All Sheets' finished-week
standings (7.13, Brad 2026-09-09). Points (desc), wins (desc), that week's
tiebreaker error (asc), competition rank; the roster is the one All Sheets
reveals for a closed week, so an absent member is charged the week's default
error at 0 points, 0 wins. Ungraded and missing weeks return None.
"""
from datetime import datetime

from extensions import db
from games.docket.models import DocketWeekResult
from games.docket.services.season_pass import week_standings
from tests._docket_fixtures import make_enrollment, make_user, make_week

GRADED_AT = datetime(2026, 9, 6, 4, 0)


def _member(name):
    user = make_user(name)
    make_enrollment(user)
    return user


def _week(week_number, default_error_tenths=0):
    week = make_week(week_number)
    week.default_error_tenths = default_error_tenths
    db.session.flush()
    return week


def _result(week, user, points, wins, error_tenths=0):
    db.session.add(DocketWeekResult(
        user_id=user.id, week_id=week.id, points=points, wins=wins,
        error_tenths=error_tenths, graded_at=GRADED_AT))


def test_ungraded_week_has_no_standings(app):
    make_week(1)                                 # no default error, no results
    db.session.commit()
    assert week_standings(1) is None


def test_missing_week_has_no_standings(app):
    assert week_standings(99) is None


def test_rank_falls_through_the_three_keys(app):
    week = _week(1)
    a, b, c = _member('a'), _member('b'), _member('c')
    _result(week, a, 9.0, 9, error_tenths=10)    # most points
    _result(week, b, 7.0, 7, error_tenths=5)     # fewer points
    _result(week, c, 7.0, 7, error_tenths=30)    # same pts/wins, more error
    db.session.commit()
    order = [(r.rank, r.enrollment.get_display_name())
             for r in week_standings(1).rows]
    assert order == [(1, 'a'), (2, 'b'), (3, 'c')]


def test_shared_rank_shares_and_gaps(app):
    week = _week(1)
    a, b, c = _member('a'), _member('b'), _member('c')
    _result(week, a, 9.0, 9, error_tenths=10)
    _result(week, b, 9.0, 9, error_tenths=10)    # identical → tie
    _result(week, c, 4.0, 4, error_tenths=50)
    db.session.commit()
    assert [r.rank for r in week_standings(1).rows] == [1, 1, 3]


def test_absent_member_is_charged_the_default_error(app):
    week = _week(1, default_error_tenths=180)
    a = _member('a')
    _member('absent')                            # on roster, files no sheet
    _result(week, a, 9.0, 9, error_tenths=10)
    db.session.commit()
    by_name = {r.enrollment.get_display_name(): r
               for r in week_standings(1).rows}
    charged = by_name['absent']
    assert charged.points == 0.0 and charged.wins == 0
    assert charged.error_tenths == 180 and charged.submitted is False
    assert charged.rank == 2
