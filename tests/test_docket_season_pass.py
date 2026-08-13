"""The season ledger's ORM→pure adapter (D14-eng).

Locks the read path: standings come from the persisted rollup, the drop is
derived rather than stored, and every absent-member charge follows the
Grading Clarifications. The engine itself is covered by the fixture
catalog; these tests are about the seam.
"""
from datetime import datetime

import pytest
from sqlalchemy import select

from extensions import db
from games.docket.models import DocketWeekResult
from tests._docket_fixtures import make_enrollment, make_user, make_week


def _graded_week(week_number, default_error_tenths=0):
    week = make_week(week_number)
    week.default_error_tenths = default_error_tenths
    db.session.flush()
    return week


def _result(week, user, points, wins, error_tenths=0):
    row = DocketWeekResult(
        user_id=user.id, week_id=week.id, points=points, wins=wins,
        error_tenths=error_tenths, graded_at=datetime(2026, 9, 6, 4, 0))
    db.session.add(row)
    return row


def _player(username):
    user = make_user(username)
    make_enrollment(user)
    return user


# ---------------------------------------------------------------------------
# D14-eng: the ledger reads the rollup
# ---------------------------------------------------------------------------

def test_ledger_reads_only_the_rollup_tables(app):
    """The sharpest D14-eng lock: seed real picks and predictions that
    disagree with the rollup, delete them, and the standings must not move.
    Standings read the rollup, never pick history."""
    from games.docket.models import (
        DocketPick,
        DocketTiebreakerPrediction,
        DocketWeek,
    )
    from games.docket.services.season_pass import season_ledger
    from tests._docket_fixtures import make_game

    week = _graded_week(1)
    alice, bob = _player('alice'), _player('bob')
    _result(week, alice, 7.5, 7)
    _result(week, bob, 4.0, 4)

    # Pick history that would grade to something else entirely: eight losing
    # sides for alice, plus a wild prediction. The ledger must ignore it.
    games = [make_game(week, kickoff=datetime(2026, 9, 5, 18, 0),
                       home=f'H{i}', away=f'A{i}',
                       home_spread=-7.0, total=50.0) for i in range(8)]
    for game in games:
        game.home_score, game.away_score, game.is_final = 0, 40, True
    week.tiebreaker_game_id = games[0].id
    for slot, game in enumerate(games, start=1):
        db.session.add(DocketPick(
            user_id=alice.id, week_id=week.id, game_id=game.id,
            market='spread', side='home', slot=slot,
            line_value=-7.0, book='draftkings'))
    db.session.add(DocketTiebreakerPrediction(
        user_id=alice.id, week_id=week.id, prediction_tenths=9999))
    db.session.commit()

    before = [(r.enrollment.user_id, r.standing.rank, r.standing.total_points,
               r.standing.error_tenths) for r in season_ledger().rows]
    assert before[0][2] == 7.5, 'the rollup wins over pick history'

    db.session.query(DocketPick).delete()
    db.session.query(DocketTiebreakerPrediction).delete()
    db.session.query(DocketWeek).filter_by(id=week.id).update(
        {'tiebreaker_game_id': None})
    db.session.commit()

    after = [(r.enrollment.user_id, r.standing.rank, r.standing.total_points,
              r.standing.error_tenths) for r in season_ledger().rows]
    assert before == after


def test_ungraded_weeks_are_absent_and_charge_nobody(app):
    """A week with no result rows is not graded: it charges no default error
    and does not count toward the drop."""
    from games.docket.services.season_pass import week_rollups_from_db

    graded = _graded_week(1)
    _graded_week(2, default_error_tenths=250)  # exists, never graded
    alice = _player('alice')
    _result(graded, alice, 6.0, 6)
    db.session.commit()

    rollups = week_rollups_from_db()
    assert [r.week_number for r in rollups] == [1]


def test_week_with_results_but_no_default_error_is_refused(app):
    """Refuse loudly rather than silently dropping the week: an absent week
    changes everyone's totals and therefore everyone's rank."""
    from games.docket.services.season_pass import week_rollups_from_db

    week = _graded_week(1)
    week.default_error_tenths = None
    alice = _player('alice')
    _result(week, alice, 6.0, 6)
    db.session.commit()

    with pytest.raises(ValueError, match='flask docket recalc'):
        week_rollups_from_db()


# ---------------------------------------------------------------------------
# D20-eng: integer tenths through the DB path
# ---------------------------------------------------------------------------

def test_no_float_enters_key_three_through_the_db_path(app):
    from games.docket.services.season_pass import season_ledger

    week = _graded_week(1, default_error_tenths=125)
    alice = _player('alice')
    _result(week, alice, 6.0, 6, error_tenths=515)
    db.session.commit()

    error = season_ledger().rows[0].standing.error_tenths
    assert isinstance(error, int) and not isinstance(error, bool)
    assert error == 515


def test_a_float_error_is_refused_at_the_seam(app):
    """SQLite is dynamically typed and will store 4.5 in an Integer column,
    so the snapshot guard is the real gate, not the schema."""
    from games.docket.services.season_pass import week_rollups_from_db

    week = _graded_week(1)
    alice = _player('alice')
    row = _result(week, alice, 6.0, 6)
    db.session.commit()
    row.error_tenths = 51.5
    db.session.commit()

    with pytest.raises(ValueError, match='integer tenths'):
        week_rollups_from_db()


# ---------------------------------------------------------------------------
# The drop
# ---------------------------------------------------------------------------

def test_drop_removes_points_only(app):
    """Wins and cumulative error survive a dropped week: the liability
    account never forgives."""
    from games.docket.services.season_pass import season_ledger

    w1, w2 = _graded_week(1), _graded_week(2)
    alice = _player('alice')
    _result(w1, alice, 2.0, 2, error_tenths=30)   # the worst week
    _result(w2, alice, 8.0, 8, error_tenths=45)
    db.session.commit()

    standing = season_ledger().rows[0].standing
    assert standing.total_points == 8.0      # 10.0 - the dropped 2.0
    assert standing.wins == 10               # never dropped
    assert standing.error_tenths == 75       # never dropped
    assert standing.dropped_week == 1


def test_drop_does_not_apply_to_a_single_graded_week(app):
    from games.docket.services.season_pass import season_ledger

    week = _graded_week(1)
    alice = _player('alice')
    _result(week, alice, 3.0, 3)
    db.session.commit()

    ledger = season_ledger()
    assert ledger.drop_active is False
    assert ledger.rows[0].standing.total_points == 3.0
    assert ledger.rows[0].standing.dropped_week is None


def test_drop_takes_the_earliest_week_on_an_equal_lowest_tie(app):
    from games.docket.services.season_pass import season_ledger

    w1, w2, w3 = _graded_week(1), _graded_week(2), _graded_week(3)
    alice = _player('alice')
    _result(w1, alice, 2.0, 2)
    _result(w2, alice, 2.0, 2)   # equal-lowest, but later
    _result(w3, alice, 9.0, 9)
    db.session.commit()

    assert season_ledger().rows[0].standing.dropped_week == 1


def test_the_drop_is_derived_and_is_dropped_is_never_written(app):
    """DocketWeekResult.is_dropped is deliberately unwritten: the drop moves
    every time any week grades, so a persisted copy would be a second source
    of truth for a fact nothing reads."""
    from games.docket.services.season_pass import season_ledger

    w1, w2 = _graded_week(1), _graded_week(2)
    alice = _player('alice')
    _result(w1, alice, 1.0, 1)
    _result(w2, alice, 8.0, 8)
    db.session.commit()

    assert season_ledger().rows[0].standing.dropped_week == 1
    rows = db.session.scalars(select(DocketWeekResult)).all()
    assert rows and all(r.is_dropped is False for r in rows)


# ---------------------------------------------------------------------------
# Absent members (the Grading Clarifications)
# ---------------------------------------------------------------------------

def test_absent_member_is_charged_the_weeks_default_error(app):
    """Late joiners buy no advantage on key 3: a member with no result row
    takes 0 points, 0 wins, and that week's default error."""
    from games.docket.services.season_pass import season_ledger

    week = _graded_week(1, default_error_tenths=180)
    alice, ghost = _player('alice'), _player('ghost')
    _result(week, alice, 6.0, 6, error_tenths=20)
    db.session.commit()

    rows = {r.enrollment.user_id: r for r in season_ledger().rows}
    ghost_standing = rows[ghost.id].standing
    assert ghost_standing.total_points == 0.0
    assert ghost_standing.wins == 0
    assert ghost_standing.error_tenths == 180
    assert rows[ghost.id].weeks[0].submitted is False


def test_designation_death_week_charges_zero_error_to_everyone(app):
    """Post-deadline designation death is a zero-error week for everyone,
    absent members included."""
    from games.docket.services.season_pass import season_ledger

    week = _graded_week(1, default_error_tenths=0)
    alice, ghost = _player('alice'), _player('ghost')
    _result(week, alice, 6.0, 6, error_tenths=0)
    db.session.commit()

    rows = {r.enrollment.user_id: r for r in season_ledger().rows}
    assert rows[ghost.id].standing.error_tenths == 0
    assert rows[alice.id].standing.error_tenths == 0


# ---------------------------------------------------------------------------
# Ranking and display
# ---------------------------------------------------------------------------

def test_competition_rank_shares_and_gaps(app):
    """The platform convention: 1, 1, 3, 4 — ties share and gap."""
    from games.docket.services.season_pass import season_ledger

    week = _graded_week(1)
    for name, points, wins in [('alice', 9.0, 9), ('bob', 9.0, 9),
                               ('carol', 5.0, 5), ('dave', 1.0, 1)]:
        _result(week, _player(name), points, wins)
    db.session.commit()

    assert [r.standing.rank for r in season_ledger().rows] == [1, 1, 3, 4]


def test_within_rank_display_order_is_by_name_not_user_id_string(app):
    """The engine ties on player_id (str(user_id)) to stay deterministic,
    which sorts '10' above '2'. Inside a shared rank the ledger orders by
    name; the rank itself is never re-derived."""
    from games.docket.services.season_pass import season_ledger

    week = _graded_week(1)
    zoe, adam = _player('zoe'), _player('adam')   # zoe has the lower user id
    _result(week, zoe, 5.0, 5)
    _result(week, adam, 5.0, 5)
    db.session.commit()

    rows = season_ledger().rows
    assert [r.standing.rank for r in rows] == [1, 1]
    assert [r.enrollment.get_display_name() for r in rows] == ['adam', 'zoe']


def test_ledger_is_empty_but_valid_before_any_week_grades(app):
    """The state the ledger ships in: prod docket tables stay empty until the
    Week-1 import."""
    from games.docket.services.season_pass import season_ledger

    _player('alice')
    db.session.commit()

    ledger = season_ledger()
    assert ledger.is_graded is False
    assert ledger.week_numbers == ()
    assert ledger.season_complete is False
    assert len(ledger.rows) == 1
    assert ledger.rows[0].standing.total_points == 0.0
    assert ledger.rows[0].weeks == ()


def test_ledger_with_no_enrollments_at_all(app):
    from games.docket.services.season_pass import season_ledger

    ledger = season_ledger()
    assert ledger.rows == ()
    assert ledger.leader is None


def test_season_complete_only_when_every_week_is_graded(app):
    from games.docket.services.season_pass import season_ledger
    from games.docket.services.weeks import TOTAL_WEEKS

    alice = _player('alice')
    for n in range(1, TOTAL_WEEKS + 1):
        _result(_graded_week(n), alice, 5.0, 5)
    db.session.commit()

    ledger = season_ledger()
    assert ledger.total_weeks == TOTAL_WEEKS
    assert ledger.season_complete is True
