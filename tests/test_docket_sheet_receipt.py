"""The Docket sheet receipt (Brad, 2026-09-04: "Filed only").

One Club Letter the moment the eighth side is held: the sheet as it stands,
what is still open, and the deadline. The trigger is stateless: the mutation
that takes the scoring count from 7 to 8. Nothing else on the sheet mails
(the reserve, the x2, the number, a move), a member who removes a side and
holds another gets the sheet again, and a refused send never gates the pick.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from extensions import db
from tests._docket_fixtures import (
    IN_WEEK1,
    at,
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

KICK_SAT = datetime(2026, 9, 5, 23, 30)
JSON = {'Accept': 'application/json'}
SEND = 'games.docket.services.receipts.send_platform_email'


@pytest.fixture()
def member(app, client):
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    return user


def _week_with_games(n=10):
    week = make_week(1)
    games = [make_game(week, kickoff=KICK_SAT, home=f'Home {i}',
                       away=f'Away {i}') for i in range(n)]
    week.tiebreaker_game_id = games[-1].id
    db.session.commit()
    return week, games


def _file(client, game, market='spread', side='home', **extra):
    data = {'game_id': game.id, 'market': market, 'side': side,
            'csrf_token': 'x', **extra}
    return client.post('/docket/picks/set', data=data, headers=JSON)


def _plain(send):
    return send.call_args[0][2]


def test_eighth_side_sends_the_sheet_receipt_once(monkeypatch, client, member):
    week, games = _week_with_games()
    at(monkeypatch, IN_WEEK1)
    with patch(SEND, return_value=True) as send:
        for g in games[:7]:
            _file(client, g)
        assert send.call_count == 0
        resp = _file(client, games[7])
    assert resp.get_json()['ok'] is True
    assert send.call_count == 1
    to_addr, subject, plain, html = send.call_args[0]
    assert to_addr == member.email
    assert subject == 'Sheet filed: The Docket, Week 1'
    assert 'Your Week 1 sheet is filed' in plain
    for i in range(8):
        assert f'Home {i} -3.5' in plain
    assert 'Still open on your sheet' in plain
    assert 'No headliner named.' in plain
    assert 'No combined-score number recorded.' in plain
    assert 'Saturday, Sep 5' in plain           # the deadline, literal
    assert '/docket/' in plain                  # the sheet link
    assert 'Home 0 -3.5' in html


def test_nothing_else_on_the_sheet_mails(monkeypatch, client, member):
    week, games = _week_with_games()
    at(monkeypatch, IN_WEEK1)
    with patch(SEND, return_value=True) as send:
        for g in games[:8]:
            _file(client, g)
        assert send.call_count == 1
        _file(client, games[8], backup='1')                     # the reserve
        client.post('/docket/best', data={'game_id': games[0].id,
                                          'market': 'spread',
                                          'csrf_token': 'x'}, headers=JSON)
        client.post('/docket/tiebreaker',
                    data={'prediction': '53.7', 'csrf_token': 'x'},
                    headers=JSON)
        _file(client, games[7], side='away')                    # a move
    assert send.call_count == 1


def test_holding_again_after_a_removal_sends_the_sheet_again(
        monkeypatch, client, member):
    week, games = _week_with_games()
    at(monkeypatch, IN_WEEK1)
    with patch(SEND, return_value=True) as send:
        for g in games[:8]:
            _file(client, g)
        client.post('/docket/picks/remove',
                    data={'game_id': games[3].id, 'market': 'spread',
                          'csrf_token': 'x'}, headers=JSON)
        _file(client, games[8])
    assert send.call_count == 2


def test_a_finished_sheet_receipt_has_no_open_items(
        monkeypatch, client, member):
    week, games = _week_with_games()
    at(monkeypatch, IN_WEEK1)
    with patch(SEND, return_value=True) as send:
        for g in games[:7]:
            _file(client, g)
        client.post('/docket/best', data={'game_id': games[2].id,
                                          'market': 'spread',
                                          'csrf_token': 'x'}, headers=JSON)
        client.post('/docket/tiebreaker',
                    data={'prediction': '53.7', 'csrf_token': 'x'},
                    headers=JSON)
        _file(client, games[7])
    plain = _plain(send)
    assert 'Still open on your sheet' not in plain
    assert 'Home 2 -3.5' in plain
    assert '53.7' in plain


def test_a_refused_send_never_gates_the_pick(monkeypatch, client, member):
    week, games = _week_with_games()
    at(monkeypatch, IN_WEEK1)
    with patch(SEND, return_value=False) as send:
        for g in games[:7]:
            _file(client, g)
        resp = _file(client, games[7])
    assert send.call_count == 1
    payload = resp.get_json()
    assert payload['ok'] is True
    assert payload['sheet']['scoring_count'] == 8
