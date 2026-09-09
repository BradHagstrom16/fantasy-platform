"""The ledger's weekly entries open onto the sheet behind each week.

Brad's ask (2026-09-07 handoff, Phase 3): each player's line collapses to
its summary and expands to the week-by-week eight-slot pick history. The
read is `services/history.py::pick_history`, a separate module so the
season pass keeps its D14-eng invariant (it reads `docket_week` and
`docket_week_result` and nothing else); the lines use All Sheets' own
wording helpers so the two surfaces never disagree about a pick.
"""
from datetime import datetime

import pytest
from sqlalchemy import event

from extensions import db
from games.docket.models import DocketPick, DocketWeekResult
from games.docket.services.history import pick_history
from tests._docket_fixtures import (
    at,
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

GRADED_AT = datetime(2026, 9, 6, 4, 0)
KICK_THU = datetime(2026, 9, 4, 0, 15)
KICK_SAT = datetime(2026, 9, 5, 18, 0)
KICK_SUN = datetime(2026, 9, 6, 17, 0)


def _graded_week(week_number, *, default_error_tenths=0):
    week = make_week(week_number)
    week.default_error_tenths = default_error_tenths
    db.session.flush()
    return week


def _result(week, user, points, wins, error_tenths=0):
    db.session.add(DocketWeekResult(
        user_id=user.id, week_id=week.id, points=points, wins=wins,
        error_tenths=error_tenths, graded_at=GRADED_AT))


def _final(game, home, away):
    game.home_score, game.away_score, game.is_final = home, away, True


def _pick(user, week, game, slot, *, market='spread', side='home',
          line=-3.5, best=False, auto=False, auto_best=False):
    pick = DocketPick(user_id=user.id, week_id=week.id, game_id=game.id,
                      market=market, side=side, slot=slot, is_best=best,
                      is_autopick=auto, is_auto_best=auto_best,
                      line_value=line, book='draftkings')
    db.session.add(pick)
    db.session.flush()
    return pick


def _full_sheet(user, week):
    """Nine games, a full eight-slot sheet plus the reserve; kickoffs out of
    slot order so kickoff ordering is observable. Slot 1 loses, slot 2 wins,
    slot 3 pushes, the rest win; slot 4 is the x2, slot 8 auto-filed."""
    games = []
    for i in range(9):
        kickoff = (KICK_SUN, KICK_THU, KICK_SAT)[i % 3]
        game = make_game(week, kickoff=kickoff, home=f'Home {i}',
                         away=f'Away {i}', home_spread=-3.5)
        if i == 0:
            _final(game, 20, 24)          # slot 1: the home side loses outright
        elif i == 2:
            game.home_spread = -3.0
            _final(game, 20, 17)          # slot 3: covers by exactly the line
        else:
            _final(game, 24, 17)          # covers -3.5
        games.append(game)
    picks = [
        _pick(user, week, games[i], i + 1,
              best=(i == 3), auto=(i == 7), auto_best=False)
        for i in range(8)
    ]
    picks.append(_pick(user, week, games[8], 9))         # the reserve
    db.session.flush()
    return games, picks


def test_pick_history_reads_a_graded_week_in_kickoff_order_reserve_last(app):
    user = make_user('player')
    make_enrollment(user)
    week = _graded_week(1)
    _full_sheet(user, week)
    _result(week, user, 7.0, 6)
    db.session.commit()

    history = pick_history((1,), [user.id])

    lines = history[user.id][1]
    assert len(lines) == 9
    assert [line.is_reserve for line in lines] == [False] * 8 + [True]
    scoring = lines[:8]
    assert [line.slot for line in scoring] != list(range(1, 9)), 'slot order'
    kicks = [line.kickoff for line in scoring]
    assert kicks == sorted(kicks), 'kickoff order'
    by_slot = {line.slot: line for line in lines}
    assert by_slot[1].result == 'loss'
    assert by_slot[2].result == 'win'
    assert by_slot[3].result == 'push'
    assert by_slot[4].is_best is True
    assert by_slot[8].is_autopick is True
    assert by_slot[1].pick == 'Home 0 -3.5'
    assert by_slot[1].caption == 'Away 0 at Home 0'
    assert by_slot[1].final_score == '24-20'


def test_pick_history_ignores_weeks_that_are_not_graded(app):
    """Only graded weeks are asked for; an open week's picks never leak
    through the ledger (the sheet reveals on its own lock, 7.13)."""
    user = make_user('player')
    make_enrollment(user)
    week1 = _graded_week(1)
    _full_sheet(user, week1)
    _result(week1, user, 7.0, 6)
    week2 = make_week(2)
    game = make_game(week2, kickoff=datetime(2026, 9, 12, 18, 0))
    _pick(user, week2, game, 1)
    db.session.commit()

    history = pick_history((1,), [user.id])

    assert set(history[user.id]) == {1}


def _enroll_with_sheets(weeks, names):
    """Enrol each name with a full graded sheet on every week."""
    users = []
    for i, name in enumerate(names):
        user = make_user(name)
        make_enrollment(user)
        for week in weeks:
            _full_sheet(user, week)
            _result(week, user, float(i), i)
        users.append(user)
    db.session.commit()
    return users


def _ledger_statement_count(client):
    statements = []

    def before(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(db.engine, 'before_cursor_execute', before)
    try:
        assert client.get('/docket/ledger').status_code == 200
    finally:
        event.remove(db.engine, 'before_cursor_execute', before)
    return len(statements)


def test_ledger_query_count_stays_flat(app, client):
    """The season board never reads per member or per week: the count for two
    members is the count for ten, on the same two graded weeks (no open week,
    so no current-week read)."""
    weeks = (_graded_week(1), _graded_week(2))
    users = _enroll_with_sheets(weeks, ['p00', 'p01'])
    login(client, users[0])
    two_members = _ledger_statement_count(client)

    _enroll_with_sheets(weeks, [f'p{i:02d}' for i in range(2, 10)])
    ten_members = _ledger_statement_count(client)

    assert ten_members == two_members, (
        f'{two_members} queries for 2 members, {ten_members} for 10 — '
        'a per-member read crept into the ledger')
    assert two_members < 18, f'{two_members} queries for 2 members x 2 weeks'


def test_ledger_query_count_flat_with_a_live_week(app, client, monkeypatch):
    """The current-week column and expand open from one all_sheets read
    (flat, whatever the roster); a per-member current-week read must never
    creep in (Brad, 2026-09-09)."""
    graded = _graded_week(1)
    live = make_week(2)                          # ungraded, current
    game = make_game(live, kickoff=datetime(2026, 9, 10, 0, 15))
    _final(game, 31, 17)
    at(monkeypatch, '2026-09-10T12:00:00')       # in Week 2, after kickoff

    def add_live_picks(users):
        for slot_user in users:
            _pick(slot_user, live, game, 1)
        db.session.commit()

    two = _enroll_with_sheets([graded], ['p00', 'p01'])
    add_live_picks(two)
    login(client, two[0])
    two_members = _ledger_statement_count(client)

    ten = _enroll_with_sheets([graded], [f'p{i:02d}' for i in range(2, 10)])
    add_live_picks(ten)
    ten_members = _ledger_statement_count(client)

    assert ten_members == two_members, (
        f'{two_members} queries for 2 members, {ten_members} for 10 with a '
        'live week — a per-member current-week read crept in')


@pytest.mark.parametrize('path', ['/docket/ledger'])
def test_ledger_still_rejects_post(app, client, path):
    user = make_user('player')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    assert client.post(path, data={'q': 'x'}).status_code == 405
