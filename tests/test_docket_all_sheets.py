"""All Sheets: everyone's picks, revealed case by case at kickoff.

Brad's ruling 2026-09-04 (a member asked to see the master sheet on
Thursday): once a pick locks it releases visibility for everyone. The page
is by member; unrevealed picks show as a sealed count in words, never a
side; the tiebreaker number shows at its own lock; a closed week reads the
as-of-deadline roster (ADR-048); result marks come from the grading engine
behind the same final gate the week grade uses, and no points are shown
before the week grades.
"""
import re
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from extensions import db
from games.docket.services import picks as picks_service
from games.docket.services import sheets as sheets_service
from games.docket.services.grading.engine import grade_pick_outcome
from games.docket.services.grading.snapshots import GameSnapshot, Market, Side
from tests._docket_fixtures import (
    IN_WEEK1,
    at,
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

KICK_THU = datetime(2026, 9, 4, 0, 15)      # Thu 7:15 PM CT
KICK_SAT = datetime(2026, 9, 5, 23, 30)     # Sat 6:30 PM CT
KICK_SUN = datetime(2026, 9, 6, 17, 0)      # Sun noon CT
DEADLINE = datetime(2026, 9, 5, 16, 0)      # Sat 11:00 AM CT
FRIDAY = datetime(2026, 9, 4, 12, 0)        # Thursday's cases locked
JSON = {'Accept': 'application/json'}


def _member(name, **kwargs):
    user = make_user(name)
    make_enrollment(user, **kwargs)
    return user


def _hold(user, week, game, market='spread', side='home', backup=False):
    return picks_service.set_pick(user.id, week, game.id, market, side,
                                  backup=backup)


def _final(game, home, away):
    game.home_score, game.away_score, game.is_final = home, away, True


def _board(week, now):
    db.session.commit()
    return sheets_service.all_sheets(week, now)


def _sheet(board, user):
    return next(m for m in board.members if m.user_id == user.id)


# ── the reveal rule ───────────────────────────────────────────────────────

def test_pick_seals_before_kickoff_and_reveals_at_it(app, monkeypatch):
    week = make_week(1)
    thu = make_game(week, kickoff=KICK_THU, home='Utah Utes',
                    away='Idaho Vandals')
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    _hold(user, week, thu)
    sealed = _sheet(_board(week, KICK_THU - timedelta(seconds=1)), user)
    assert sealed.lines == () and sealed.sealed_count == 1
    shown = _sheet(_board(week, KICK_THU), user)
    assert [line.pick for line in shown.lines] == ['Utah Utes -3.5']
    assert shown.lines[0].caption == 'Idaho Vandals at Utah Utes'
    assert shown.sealed_count == 0


def test_sealed_facts_are_words_never_sides(app, monkeypatch):
    week = make_week(1)
    games = [make_game(week, kickoff=KICK_SAT, home=f'Home {i}',
                       away=f'Away {i}') for i in range(3)]
    sun = make_game(week, kickoff=KICK_SUN, home='Chiefs', away='Browns')
    week.tiebreaker_game_id = sun.id
    db.session.flush()
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    for g in games[:2]:
        _hold(user, week, g)
    picks_service.set_best(user.id, week, games[0].id, 'spread')
    _hold(user, week, games[2], backup=True)
    picks_service.set_tiebreaker(user.id, week, '53.7')
    sheet = _sheet(_board(week, FRIDAY), user)
    assert sheet.lines == ()
    assert sheet.sealed_count == 2
    assert sheet.x2_sealed and sheet.sealed_reserve and sheet.number_in
    assert sheet.number is None
    assert sheet.sealed_sentence == ('2 sides sealed until kickoff · x2 named '
                                     '· reserve held · number in.')
    assert 'Home' not in sheet.sealed_sentence


def test_deadline_reveals_every_pick(app, monkeypatch):
    week = make_week(1)
    sun = make_game(week, kickoff=KICK_SUN, home='Chiefs', away='Browns')
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    _hold(user, week, sun, 'total', 'over')
    assert _sheet(_board(week, DEADLINE - timedelta(seconds=1)), user).lines == ()
    shown = _sheet(_board(week, DEADLINE), user)
    assert [line.pick for line in shown.lines] == ['Over 51.5']
    assert _board(week, DEADLINE).deadline_passed is True


def test_lines_are_in_kickoff_order(app, monkeypatch):
    week = make_week(1)
    sat = make_game(week, kickoff=KICK_SAT, home='Sat Home', away='Sat Away')
    thu = make_game(week, kickoff=KICK_THU, home='Thu Home', away='Thu Away')
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    _hold(user, week, sat)          # slot 1, but kicks off later
    _hold(user, week, thu)          # slot 2
    shown = _sheet(_board(week, DEADLINE), user)
    assert [line.caption for line in shown.lines] == [
        'Thu Away at Thu Home', 'Sat Away at Sat Home']


def test_autopick_and_auto_best_marks_carry_through(app, monkeypatch):
    week = make_week(1)
    sat = make_game(week, kickoff=KICK_SAT)
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    pick = _hold(user, week, sat)
    pick.is_autopick, pick.is_best, pick.is_auto_best = True, True, True
    shown = _sheet(_board(week, DEADLINE), user)
    line = shown.lines[0]
    assert line.is_autopick and line.is_best and line.is_auto_best


def test_reserve_line_is_marked_and_last(app, monkeypatch):
    week = make_week(1)
    a = make_game(week, kickoff=KICK_SAT, home='A Home', away='A Away')
    b = make_game(week, kickoff=KICK_THU, home='B Home', away='B Away')
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    _hold(user, week, a)
    _hold(user, week, b, backup=True)          # earlier kickoff, still last
    shown = _sheet(_board(week, DEADLINE), user)
    assert [line.is_reserve for line in shown.lines] == [False, True]


# ── result marks: the engine's rule, behind the week grade's final gate ──

@pytest.mark.parametrize('market,side,home,away,expected', [
    ('spread', 'home', 31, 17, 'win'),       # home -3.5, covers by 14
    ('spread', 'home', 20, 17, 'loss'),      # home -3.5, wins by 3
    ('spread', 'away', 20, 17, 'win'),
    ('total', 'over', 28, 27, 'win'),        # 55 > 51.5
    ('total', 'under', 28, 27, 'loss'),
    ('total', 'over', 24, 24, 'loss'),       # 48 < 51.5
])
def test_result_marks_equal_the_engine_rule(app, monkeypatch, market, side,
                                            home, away, expected):
    week = make_week(1)
    thu = make_game(week, kickoff=KICK_THU)
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    _hold(user, week, thu, market, side)
    _final(thu, home, away)
    line = _sheet(_board(week, FRIDAY), user).lines[0]
    assert line.result == expected
    snap = GameSnapshot(api_event_id=thu.api_event_id, sport=thu.sport,
                        home_team=thu.home_team, away_team=thu.away_team,
                        kickoff_at_deadline=thu.kickoff,
                        home_spread=thu.home_spread, total=thu.total_points,
                        home_score=home, away_score=away)
    assert line.result == grade_pick_outcome(snap, Market(market),
                                             Side(side)).value
    assert line.final_score == f'{away}-{home}'


def test_a_push_is_a_mistrial_mark(app, monkeypatch):
    week = make_week(1)
    thu = make_game(week, kickoff=KICK_THU, home_spread=-4.0)
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    _hold(user, week, thu)
    _final(thu, 24, 20)
    assert _sheet(_board(week, FRIDAY), user).lines[0].result == 'push'


def test_no_contest_marks_and_stays_out_of_the_tally(app, monkeypatch):
    week = make_week(1)
    thu = make_game(week, kickoff=KICK_THU)
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    _hold(user, week, thu)
    _final(thu, 31, 17)
    thu.no_contest = True
    sheet = _sheet(_board(week, FRIDAY), user)
    assert sheet.lines[0].result == 'no_contest'
    assert sheet.lines[0].final_score is None
    assert sheet.tally is None


def test_unfinal_scores_show_no_result(app, monkeypatch):
    week = make_week(1)
    thu = make_game(week, kickoff=KICK_THU)
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    _hold(user, week, thu)
    thu.home_score, thu.away_score = 14, 7       # in progress, not final
    line = _sheet(_board(week, FRIDAY), user).lines[0]
    assert line.result is None and line.final_score is None


def test_tally_counts_final_scoring_lines_only(app, monkeypatch):
    week = make_week(1)
    thu = [make_game(week, kickoff=KICK_THU) for _ in range(4)]
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    for g in thu[:3]:
        _hold(user, week, g)
    _hold(user, week, thu[3], backup=True)
    _final(thu[0], 31, 17)                       # win
    _final(thu[1], 20, 17)                       # loss
    _final(thu[3], 31, 17)                       # the reserve: not counted
    sheet = _sheet(_board(week, FRIDAY), user)
    assert sheet.tally.wins == 1 and sheet.tally.losses == 1
    assert sheet.tally.pushes == 0 and sheet.tally.pending == 1
    assert sheet.summary == '1-1 · 1 to play'


# ── the number, the roster, the empty member ─────────────────────────────

def test_number_reveals_at_its_own_lock(app, monkeypatch):
    week = make_week(1)
    thu = make_game(week, kickoff=KICK_THU, home='Chiefs', away='Browns')
    week.tiebreaker_game_id = thu.id            # designated early, by hand
    db.session.flush()
    user = _member('ann')
    at(monkeypatch, IN_WEEK1)
    picks_service.set_tiebreaker(user.id, week, '53.7')
    before = _board(week, KICK_THU - timedelta(seconds=1))
    assert before.number_revealed is False
    assert _sheet(before, user).number is None
    after = _board(week, KICK_THU)
    assert after.number_revealed is True
    assert after.number_lock_at == KICK_THU
    assert _sheet(after, user).number == '53.7'


def test_roster_is_live_before_the_deadline_and_as_of_after(app, monkeypatch):
    week = make_week(1)
    make_game(week, kickoff=KICK_SAT)
    _member('early')
    late = _member('late', created_at=DEADLINE + timedelta(hours=1))
    db.session.commit()
    before = _board(week, DEADLINE - timedelta(hours=1))
    assert {m.user_id for m in before.members} >= {late.id}
    after = _board(week, DEADLINE + timedelta(hours=2))
    assert late.id not in {m.user_id for m in after.members}


def test_member_with_nothing_held_still_appears(app, monkeypatch):
    week = make_week(1)
    thu = make_game(week, kickoff=KICK_THU)
    ann = _member('ann')
    _member('bob')
    at(monkeypatch, IN_WEEK1)
    _hold(ann, week, thu)
    board = _board(week, FRIDAY)
    names = [m.enrollment.get_display_name() for m in board.members]
    assert names == ['ann', 'bob']
    bob = board.members[1]
    assert bob.lines == () and bob.sealed_count == 0
    assert bob.sealed_sentence == 'Nothing held yet.'
    assert bob.summary == '0 of 8 held'


def test_board_facts(app, monkeypatch):
    week = make_week(1)
    make_game(week, kickoff=KICK_THU)
    make_game(week, kickoff=KICK_SAT)
    _member('ann')
    board = _board(week, KICK_THU - timedelta(hours=1))
    assert board.week_number == 1
    assert board.any_revealed is False
    assert board.first_kickoff == KICK_THU and board.next_lock == KICK_THU
    later = _board(week, FRIDAY)
    assert later.any_revealed is True and later.next_lock == KICK_SAT
    assert later.locked_cases == 1 and later.total_cases == 2


def test_no_n_plus_one(app, monkeypatch):
    week = make_week(1)
    games = [make_game(week, kickoff=KICK_THU) for _ in range(4)]
    members = [_member(f'm{i}') for i in range(3)]
    at(monkeypatch, IN_WEEK1)
    for user in members:
        for g in games:
            _hold(user, week, g)
    db.session.commit()
    db.session.expire_all()
    # The week is the caller's: its fields are read before the listener so
    # the count below is the service's own five statements (the roster ids,
    # enrollments with their users, games, picks, predictions), no more.
    _ = (week.id, week.deadline_at, week.tiebreaker_game_id, week.week_number)
    statements = []

    def count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.engine, 'before_cursor_execute', count)
    try:
        board = sheets_service.all_sheets(week, FRIDAY)
        # Touch everything the template will read.
        touched = []
        for m in board.members:
            touched.append(m.enrollment.get_display_name())
            touched.append(m.enrollment.user.get_avatar())
            touched.extend((line.pick, line.caption, line.result)
                           for line in m.lines)
    finally:
        event.remove(db.engine, 'before_cursor_execute', count)
    assert len(board.members) == 3
    assert len(statements) == 5, statements


# ── the page ──────────────────────────────────────────────────────────────

@pytest.fixture()
def member(app, client):
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    return user


def _page(client):
    resp = client.get('/docket/sheets')
    assert resp.status_code == 200
    return resp.data.decode()


def test_sheets_requires_enrollment(app, client):
    user = make_user('wanderer')
    db.session.commit()
    login(client, user)
    resp = client.get('/docket/sheets')
    assert resp.status_code == 302
    assert '/docket/join' in resp.headers['Location']


def test_sheets_carries_no_forms(monkeypatch, client, member):
    week = make_week(1)
    thu = make_game(week, kickoff=KICK_THU)
    at(monkeypatch, IN_WEEK1)
    _hold(member, week, thu)
    db.session.commit()
    at(monkeypatch, '2026-09-05T17:00:00')      # closed
    html = _page(client)
    assert '<form' not in html
    assert 'data-docket-action="' not in html
    assert 'csrf_token' not in html


def test_sheets_marks_you_once_and_lists_every_member(
        monkeypatch, client, member):
    week = make_week(1)
    make_game(week, kickoff=KICK_THU)
    _member('zed', display_name='Zed')
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    html = _page(client)
    assert html.count('docket-you-tag') == 1
    assert 'is-you' in html
    assert html.index('member') < html.index('Zed')


def test_sheets_pre_first_lock_states_the_reason(monkeypatch, client, member):
    week = make_week(1)
    make_game(week, kickoff=KICK_THU)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    html = _page(client)
    assert 'Nothing has locked yet.' in html
    assert 'Sheets open here case by case at kickoff' in html
    assert 'Thursday 7:15 PM CT' in html          # the first case
    assert 'The Week 1 Sheets' in html


def test_sheets_seals_sides_in_words(monkeypatch, client, member):
    week = make_week(1)
    sat = make_game(week, kickoff=KICK_SAT, home='Utah Utes',
                    away='Idaho Vandals')
    at(monkeypatch, IN_WEEK1)
    _hold(member, week, sat)
    db.session.commit()
    html = _page(client)
    assert 'Utah Utes' not in html
    assert '1 side sealed until kickoff.' in html
    assert '1 of 8 held' in html


def test_sheets_reveals_at_kickoff_with_the_result(
        monkeypatch, client, member):
    week = make_week(1)
    thu = make_game(week, kickoff=KICK_THU, home='Utah Utes',
                    away='Idaho Vandals')
    sat = make_game(week, kickoff=KICK_SAT, home='Sat Home', away='Sat Away')
    at(monkeypatch, IN_WEEK1)
    _hold(member, week, thu)
    _hold(member, week, sat)
    _final(thu, 31, 17)
    db.session.commit()
    at(monkeypatch, '2026-09-04T12:00:00')      # Friday morning
    html = _page(client)
    assert 'Utah Utes -3.5' in html
    assert 'Idaho Vandals at Utah Utes' in html
    assert 'docket-sheet-result is-win' in html and '>Win<' in html
    assert 'Final 17-31' in html
    assert 'Sat Home' not in html
    assert '1 side sealed until kickoff.' in html
    assert '1 of 2 cases locked' in html
    assert 'Next to open' in html


def test_sheets_closed_shows_the_clerks_marks(monkeypatch, client, member):
    week = make_week(1)
    sat = make_game(week, kickoff=KICK_SAT)
    at(monkeypatch, IN_WEEK1)
    pick = _hold(member, week, sat)
    pick.is_autopick, pick.is_best, pick.is_auto_best = True, True, True
    db.session.commit()
    at(monkeypatch, '2026-09-05T17:00:00')
    html = _page(client)
    assert 'docket-sheet-line is-autopick' in html
    assert 'docket-auto-tag' in html
    assert 'docket-headliner-chip is-auto' in html
    assert 'Every sheet is on the record.' in html
    assert 'Points post to the ledger with the week' in html


def test_sheets_empty_states(monkeypatch, client, member):
    at(monkeypatch, IN_WEEK1)
    html = _page(client)
    assert 'Court convenes' in html
    week = make_week(1)
    db.session.commit()
    at(monkeypatch, '2026-08-30T12:00:00')      # posted, court not convened
    html = _page(client)
    assert 'not been posted yet' in html
    # The hero agrees with the body: no "sheets open at kickoff" promise
    # above a docket that has no cases yet.
    lead = re.search(r'<p class="lead mb-0">(.*?)</p>', html, re.S).group(1)
    assert 'case by case' not in lead
    assert 'has not been posted yet' in lead
    assert html.count('has not been posted yet') == 2      # hero + body
    make_game(week, kickoff=KICK_THU)
    db.session.commit()
    html = _page(client)
    assert 'The docket is posted for reading.' in html
    assert 'Sheets open here case by case at kickoff' in html


def test_rules_and_join_state_the_visibility_rule(app, client):
    user = make_user('newcomer')                 # not yet enrolled
    db.session.commit()
    login(client, user)
    rules = client.get('/docket/rules').data.decode()
    assert 'All Sheets' in rules and 'sealed until' in rules
    join = client.get('/docket/join').data.decode()
    assert 'All Sheets' in join


def test_subnav_carries_all_sheets_after_my_sheet(
        monkeypatch, client, member):
    at(monkeypatch, IN_WEEK1)
    html = client.get('/docket/').data.decode()
    assert html.index('My Sheet') < html.index('All Sheets') < html.index('Ledger')
    sheets = _page(client)
    assert 'subnav-pill active' in sheets
