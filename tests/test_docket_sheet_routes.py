"""Docket pick-sheet route locks: rendering states, the dual-mode mutation
seam (form PRG vs sheet-state JSON), and the client-input tamper lock."""
from datetime import datetime

import pytest
from sqlalchemy import select

from extensions import db
from games.docket.models import DocketPick
from tests._docket_fixtures import (
    IN_WEEK1,
    at,
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

KICK_THU = datetime(2026, 9, 4, 0, 15)
KICK_SAT = datetime(2026, 9, 5, 23, 30)

JSON = {'Accept': 'application/json'}


@pytest.fixture()
def member(app, client):
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    return user


def test_pre_season_empty_state(monkeypatch, client, member):
    at(monkeypatch, '2026-08-15T12:00:00')  # before the Week 1 boundary
    resp = client.get('/docket/')
    assert resp.status_code == 200
    assert b'Court convenes September 1' in resp.data
    assert b'docket-day-tab' not in resp.data


def test_week_without_games_empty_state(monkeypatch, client, member):
    make_week(1)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    resp = client.get('/docket/')
    assert resp.status_code == 200
    assert b'has not been posted yet' in resp.data


def test_sheet_renders_calendar_rail_and_tiebreaker(
        monkeypatch, client, member):
    week = make_week(1)
    make_game(week, kickoff=KICK_THU, home='Green Bay Packers',
              away='Chicago Bears', sport='americanfootball_nfl')
    sat = make_game(week, kickoff=KICK_SAT, home='Notre Dame Fighting Irish',
                    away='Wisconsin Badgers')
    week.tiebreaker_game_id = sat.id
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    resp = client.get('/docket/')
    html = resp.data.decode()
    assert resp.status_code == 200
    assert html.count('docket-day-tab-label') == 2  # Thu + Sat CT days
    assert 'Chicago Bears' in html          # first unlocked day is active
    assert 'id="docket-rail"' in html
    assert 'id="docket-rail-mobile"' in html
    assert 'The number' in html
    assert 'Tiebreaker case' not in html    # designated game is on Sat tab


def test_day_tab_switches_active_day(monkeypatch, client, member):
    week = make_week(1)
    make_game(week, kickoff=KICK_THU, away='Chicago Bears',
              home='Green Bay Packers', sport='americanfootball_nfl')
    make_game(week, kickoff=KICK_SAT, away='Wisconsin Badgers',
              home='Notre Dame Fighting Irish')
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    resp = client.get('/docket/?day=2026-09-05')
    html = resp.data.decode()
    assert 'Wisconsin Badgers' in html
    # The Thursday case belongs to the other tab; day tabs carry dates only.
    assert 'Chicago Bears' not in html


def test_mutation_without_active_week_is_refused_not_500(
        monkeypatch, client, member):
    """A POST outside any week window: the service's _require_open_week
    guard refuses with no_active_week; it never dereferences week=None."""
    at(monkeypatch, '2026-08-15T12:00:00')  # before the Week 1 boundary
    resp = client.post(
        '/docket/picks/set',
        data={'game_id': 1, 'market': 'spread', 'side': 'home',
              'csrf_token': 'x'},
        headers=JSON,
    )
    assert resp.status_code == 409
    assert resp.get_json()['error'] == 'no_active_week'


def test_set_pick_json_returns_sheet_state(monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    resp = client.post(
        '/docket/picks/set',
        data={'game_id': game.id, 'market': 'spread', 'side': 'home',
              'csrf_token': 'x'},
        headers=JSON,
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['ok'] is True
    assert payload['sheet']['scoring_count'] == 1
    assert payload['sheet']['picks'][0]['slot'] == 1


def test_locked_game_json_conflict(monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_THU)
    db.session.commit()
    at(monkeypatch, '2026-09-04T01:00:00')  # kicked off between load and save
    resp = client.post(
        '/docket/picks/set',
        data={'game_id': game.id, 'market': 'spread', 'side': 'home',
              'csrf_token': 'x'},
        headers=JSON,
    )
    assert resp.status_code == 409
    payload = resp.get_json()
    assert payload['ok'] is False
    assert payload['error'] == 'game_locked'
    assert payload['message']


def test_form_post_redirects_back_to_day_tab(monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    resp = client.post(
        '/docket/picks/set',
        data={'game_id': game.id, 'market': 'spread', 'side': 'home',
              'day': '2026-09-05', 'csrf_token': 'x'},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/docket/?day=2026-09-05')


def test_route_ignores_client_supplied_line_and_slot(
        monkeypatch, client, member):
    """Tamper lock: the endpoints accept no line/slot input — parity is by
    construction (the models.py write-path contract)."""
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT, home_spread=-3.5)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    resp = client.post(
        '/docket/picks/set',
        data={'game_id': game.id, 'market': 'spread', 'side': 'home',
              'line_value': '99.5', 'book': 'forged', 'slot': '7',
              'is_best': '1', 'csrf_token': 'x'},
        headers=JSON,
    )
    assert resp.status_code == 200
    pick = DocketPick.query.one()
    assert pick.line_value == -3.5
    assert pick.book == 'draftkings'
    assert pick.slot == 1
    assert pick.is_best is False


def test_locked_case_renders_static_with_reason(monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_THU)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    client.post('/docket/picks/set',
                data={'game_id': game.id, 'market': 'spread',
                      'side': 'home', 'csrf_token': 'x'})
    at(monkeypatch, '2026-09-04T01:00:00')
    resp = client.get('/docket/?day=2026-09-03')
    html = resp.data.decode()
    assert 'Locked at kickoff' in html
    assert 'is-picked is-locked' in html      # the held side keeps its stamp
    assert 'data-docket-action="set-pick"' not in html


def test_closed_docket_renders_read_only(monkeypatch, client, member):
    week = make_week(1)
    make_game(week, kickoff=KICK_SAT)
    db.session.commit()
    at(monkeypatch, '2026-09-05T16:30:00')  # past the deadline
    resp = client.get('/docket/')
    html = resp.data.decode()
    assert 'The docket is closed' in html
    # No mutation forms anywhere (the enhancement script's selector string
    # legitimately contains the attribute name, so match the form syntax).
    assert 'data-docket-action="' not in html


def test_auto_filed_sides_are_marked_and_the_sheet_says_why(
        monkeypatch, client, member):
    """After the deadline pass a player sees sides they never chose. Each is
    marked, an assigned double is marked, and the reason is stated once."""
    week = make_week(1)
    mine = make_game(week, kickoff=KICK_SAT, home='Mine H', away='Mine A')
    filed = make_game(week, kickoff=KICK_SAT, home='Filed H', away='Filed A')
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    client.post('/docket/picks/set',
                data={'game_id': mine.id, 'market': 'spread',
                      'side': 'home', 'csrf_token': 'x'})
    # Stand in for the deadline pass: one filed side, and the double
    # assigned onto the side the player picked themselves.
    db.session.add(DocketPick(
        user_id=member.id, week_id=week.id, game_id=filed.id,
        market='total', side='over', slot=2, is_autopick=True,
        line_value=filed.total_points, book=filed.total_book))
    own = db.session.scalars(
        select(DocketPick).filter_by(game_id=mine.id)).one()
    own.is_best = True
    own.is_auto_best = True
    db.session.commit()

    at(monkeypatch, '2026-09-05T16:30:00')
    html = client.get('/docket/').data.decode()

    assert 'is-picked is-locked is-autopick' in html
    assert 'docket-auto-tag' in html
    assert '· auto-filed' in html                     # the rail slot caption
    assert 'docket-headliner-chip is-auto' in html    # the assigned double
    assert 'Headliner x2 · assigned' in html
    assert 'filed for you when the docket closed' in html
    assert 'Your headliner was assigned for you.' in html
    # The player's own side keeps the plain stamp, unmarked.
    assert 'is-picked is-locked is-best' in html


def test_a_sheet_the_player_filled_carries_no_auto_marks(
        monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    client.post('/docket/picks/set',
                data={'game_id': game.id, 'market': 'spread',
                      'side': 'home', 'csrf_token': 'x'})
    at(monkeypatch, '2026-09-05T16:30:00')
    html = client.get('/docket/').data.decode()

    assert 'is-autopick' not in html
    assert 'docket-auto-tag' not in html
    assert 'docket-auto-note' not in html


def test_best_and_tiebreaker_json_flow(monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    week.tiebreaker_game_id = game.id
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    client.post('/docket/picks/set',
                data={'game_id': game.id, 'market': 'spread',
                      'side': 'home', 'csrf_token': 'x'})
    resp = client.post(
        '/docket/best',
        data={'game_id': game.id, 'market': 'spread', 'csrf_token': 'x'},
        headers=JSON,
    )
    assert resp.get_json()['sheet']['best']['game_id'] == game.id
    resp = client.post(
        '/docket/tiebreaker',
        data={'prediction': '51.5', 'csrf_token': 'x'},
        headers=JSON,
    )
    assert resp.get_json()['sheet']['prediction'] == '51.5'
    resp = client.post(
        '/docket/tiebreaker',
        data={'prediction': '51.55', 'csrf_token': 'x'},
        headers=JSON,
    )
    assert resp.status_code == 400
    assert resp.get_json()['error'] == 'invalid'


def test_remove_pick_form_flow_leaves_gap(monkeypatch, client, member):
    week = make_week(1)
    g1 = make_game(week, kickoff=KICK_SAT)
    g2 = make_game(week, kickoff=KICK_SAT)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    for g in (g1, g2):
        client.post('/docket/picks/set',
                    data={'game_id': g.id, 'market': 'spread',
                          'side': 'home', 'csrf_token': 'x'})
    resp = client.post(
        '/docket/picks/remove',
        data={'game_id': g1.id, 'market': 'spread', 'csrf_token': 'x'},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert {p.slot for p in DocketPick.query.all()} == {2}
