"""The ledger moves (DESIGN.md §8.12): what the latest graded week did to
each line's rank, derived by running the pure season pass twice (every
graded week, then every graded week but the last). No table, no snapshot:
the drop moves the movement exactly as it moves the ledger.

Printed on the ledger (board, phone cards, the flat off-season table), in
the standing sentence, on the member page, on the lounge's season board,
and in the Docket record letter. Movement belongs to the ledger, never to
a line (the frozen-number register stands)."""
from datetime import datetime

import pytest

from extensions import db
from games.docket.models import DocketWeekResult
from games.docket.services.grading.snapshots import PlayerWeekTotal, WeekRollup
from games.docket.services.season_pass import (
    Movement,
    season_ledger,
    season_movement,
)
from tests._docket_fixtures import login, make_enrollment, make_user, make_week


def _graded_week(week_number, default_error_tenths=0):
    week = make_week(week_number)
    week.default_error_tenths = default_error_tenths
    db.session.flush()
    return week


def _result(week, user, points, wins, error_tenths=0):
    db.session.add(DocketWeekResult(
        user_id=user.id, week_id=week.id, points=points, wins=wins,
        error_tenths=error_tenths, graded_at=datetime(2026, 9, 6, 4, 0)))


def _player(username, display_name=None):
    user = make_user(username)
    make_enrollment(user, display_name=display_name)
    return user


def _rollup(week, rows):
    return WeekRollup(week_number=week, default_error_tenths=0, players=tuple(
        PlayerWeekTotal(player_id=pid, points=pts, wins=w, error_tenths=0)
        for pid, pts, w in rows))


# ---------------------------------------------------------------------------
# The pure movement
# ---------------------------------------------------------------------------

def test_movement_is_the_rank_now_against_the_rank_before_the_last_week():
    rollups = (
        _rollup(1, [('a', 9, 7), ('b', 8, 6), ('c', 5, 4)]),
        _rollup(2, [('a', 2, 2), ('b', 8, 6), ('c', 9, 7)]),
    )
    moves = season_movement(rollups, ('a', 'b', 'c'))
    # After week 1: a 1st, b 2nd, c 3rd. After both weeks the drop strikes
    # each line's worst week: a 9 points on 9 wins, b 8 on 11, c 9 on 11,
    # so c leads on wins, a second, b third.
    assert moves['a'] == Movement(rank=2, previous_rank=1, week_number=2)
    assert moves['b'] == Movement(rank=3, previous_rank=2, week_number=2)
    assert moves['c'] == Movement(rank=1, previous_rank=3, week_number=2)
    assert moves['c'].delta == 2 and moves['c'].direction == 'up'
    assert moves['b'].delta == -1 and moves['b'].label == 'down 1'
    assert moves['a'].label == 'down 1'
    held = season_movement(rollups[:1] + (_rollup(2, [('a', 9, 7), ('b', 8, 6), ('c', 5, 4)]),),
                           ('a', 'b', 'c'))
    assert held['a'].label == 'held' and held['a'].direction == 'held'


def test_no_movement_until_two_weeks_have_graded():
    assert season_movement((), ('a',)) == {}
    assert season_movement((_rollup(1, [('a', 9, 7)]),), ('a',)) == {}


def test_the_drop_moves_the_movement_as_it_moves_the_ledger():
    # Three weeks: c's week-3 collapse is struck by the drop, so c holds.
    rollups = (
        _rollup(1, [('a', 5, 4), ('c', 9, 7)]),
        _rollup(2, [('a', 5, 4), ('c', 9, 7)]),
        _rollup(3, [('a', 5, 4), ('c', 0, 0)]),
    )
    moves = season_movement(rollups, ('a', 'c'))
    assert moves['c'].previous_rank == 1 and moves['c'].rank == 1
    assert moves['c'].week_number == 3


def test_the_words():
    up = Movement(rank=3, previous_rank=9, week_number=4)
    assert up.sentence == 'up 6 in Week 4'
    assert up.spoken == 'up 6 places in Week 4'
    assert Movement(rank=2, previous_rank=1, week_number=4).spoken == 'down 1 place in Week 4'
    assert Movement(rank=2, previous_rank=2, week_number=4).spoken == 'held its place in Week 4'


# ---------------------------------------------------------------------------
# The ledger carries it
# ---------------------------------------------------------------------------

@pytest.fixture
def two_weeks(app):
    """a leads after week 1; c leaps to the top in week 2; b slips."""
    with app.app_context():
        a, b, c = _player('ann', 'Ann'), _player('bob', 'Bob'), _player('cy', 'Cy')
        w1, w2 = _graded_week(1), _graded_week(2)
        _result(w1, a, 9, 7)
        _result(w1, b, 8, 6)
        _result(w1, c, 5, 4)
        _result(w2, a, 2, 2)
        _result(w2, b, 6, 5)
        _result(w2, c, 9, 7)
        db.session.commit()
        return {'a': a.id, 'b': b.id, 'c': c.id}


def test_the_ledger_rows_carry_their_move_and_the_biggest_mover(app, two_weeks):
    with app.app_context():
        ledger = season_ledger()
        assert ledger.movement_week == 2
        by_name = {r.enrollment.get_display_name(): r for r in ledger.rows}
        assert by_name['Cy'].move.label == 'up 2'
        assert by_name['Ann'].move.label == 'down 1'
        assert by_name['Bob'].move.label == 'down 1'
        assert ledger.biggest_mover is by_name['Cy']


def test_a_late_record_letter_keeps_its_own_weeks_season(app, two_weeks):
    """Week 2's letter sent after Week 3 has graded (a mail outage held the
    latch open): the Season fact, the move and the biggest mover are the
    season as Week 2 left it, never Week 3's."""
    from games.docket.services.record import week_records
    with app.app_context():
        from models.user import User
        a, b, c = (db.session.get(User, two_weeks[k]) for k in 'abc')
        w3 = _graded_week(3)
        _result(w3, a, 9, 7)
        _result(w3, b, 9, 8)
        _result(w3, c, 1, 1)
        db.session.commit()
        latest = {r.enrollment.get_display_name(): r for r in season_ledger().rows}
        assert latest['Cy'].move.label == 'down 2'           # what Week 3 did

        from games.docket.models import DocketWeek
        w2 = db.session.scalar(db.select(DocketWeek).filter_by(week_number=2))
        fields = {user.username: f for user, f in week_records(w2, datetime(2026, 9, 20))}
    cy = fields['cy']
    assert (cy['movement'].label, cy['movement'].week_number) == ('up 2', 2)
    assert cy['season_rank'] == 1
    mover_name, mover_move = cy['biggest_mover']
    assert (mover_name, mover_move.label) == ('Cy', 'up 2')


def test_one_graded_week_has_no_movement(app):
    with app.app_context():
        a = _player('ann')
        _result(_graded_week(1), a, 9, 7)
        db.session.commit()
        ledger = season_ledger()
        assert ledger.movement_week is None
        assert all(r.move is None for r in ledger.rows)
        assert ledger.biggest_mover is None


def test_the_ledger_page_prints_the_movement(app, client, two_weeks):
    with app.app_context():
        from models.user import User
        login(client, db.session.get(User, two_weeks['c']))
    page = client.get('/docket/ledger').get_data(as_text=True)
    assert 'up 2 in Week 2' in page                      # the standing sentence
    assert 'up 2 places in Week 2' in page               # the figure's accessible name
    assert 'down 1 place in Week 2' in page
    assert 'Movement is what Week 2 did to each standing' in page


def test_the_member_page_prints_the_movement(app, client, two_weeks):
    with app.app_context():
        from games.docket.models import DocketEnrollment
        from models.user import User
        login(client, db.session.get(User, two_weeks['a']))
        cy = db.session.scalar(db.select(DocketEnrollment).filter_by(user_id=two_weeks['c']))
        cy_id = cy.id
    page = client.get(f'/docket/ledger/{cy_id}').get_data(as_text=True)
    assert 'up 2 in Week 2' in page


def test_the_lounge_season_board_carries_the_move(app, two_weeks, monkeypatch):
    from games.docket.services.lounge import _season_leaderboard
    with app.app_context():
        from models.user import User
        board = _season_leaderboard(db.session.get(User, two_weeks['c']))
    rows = {r['name']: r for r in board['rows']}
    assert rows['Cy']['move']['label'] == 'up 2'
    assert rows['Cy']['move']['direction'] == 'up'
    assert rows['Ann']['move']['label'] == 'down 1'


def test_the_record_letter_states_the_move_and_the_biggest_mover(app):
    from games.docket.services.record import (
        TopSheet,
        around_the_docket,
        record_letter,
    )
    from utils.email_layout import render_letter
    app.config['SITE_URL'] = 'https://x.test'
    from games.docket.services.sheets import Tally
    letter = record_letter(
        week_number=3, display_name='Clerk of Court', tally=Tally(6, 2, 0, 0),
        points=7.0, week_rank=4, roster_size=31, season_rank=9,
        season_points=19.5, top_sheet=TopSheet(('Dana Whitfield',), '7-1', False),
        is_winner=False, weekly_prize=20, autopicked=False,
        ledger_url='https://x.test/docket/ledger',
        movement=Movement(rank=9, previous_rank=12, week_number=3),
        biggest_mover=('Dana Whitfield', Movement(rank=3, previous_rank=9, week_number=3)))
    assert letter.facts[2] == ('Season', '9th · 19.5 points · up 3')
    plain, _html = render_letter(letter)
    assert 'Biggest mover: Dana Whitfield, up 6 to 3rd' in plain
    rows = around_the_docket(TopSheet(('Dana Whitfield',), '7-1', False), 20)
    assert not any('mover' in r[0].lower() for r in rows)     # absent when unknown
