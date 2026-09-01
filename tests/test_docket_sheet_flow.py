"""The Docket sheet's first-timer flow (impeccable critique 2026-09-01, live
Week 1 at 375px).

Locks the contracts of the 2026-09-01 sheet pass:

  - ``picks.next_step``: one ask per sheet state, by priority (sides ->
    x2 -> number -> reserve -> complete), with preview / closed / urgent
    rungs; embedded in ``sheet_state`` so template, JSON, and toast agree
  - every successful mutation returns a message (JSON) and flashes it (PRG)
  - x2 is settable on the held pill itself; never on a locked or reserve pill
  - the bar speaks in words (Reserve, x2, Number), never bare letters
  - the number card states its default and its button says "Save number"
  - the sheet_full refusal and the prediction sanity cap say what to do
  - drawer buttons clear the 44px floor
"""
import re
from datetime import datetime
from pathlib import Path

import pytest

from extensions import db
from games.docket.services import picks as picks_service
from games.docket.services.picks import PickError
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
CSS = (Path(__file__).resolve().parent.parent / 'static' / 'css'
       / 'style.css').read_text()


@pytest.fixture()
def member(app, client):
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    return user


def _state(n=0, best=None, prediction=None, backup=None):
    return {'scoring_count': n, 'best': best, 'prediction': prediction,
            'backup': backup}


def _file(client, game, market='spread', side='home', **extra):
    data = {'game_id': game.id, 'market': market, 'side': side,
            'csrf_token': 'x', **extra}
    return client.post('/docket/picks/set', data=data, headers=JSON)


def _rule(anchored_selector):
    m = re.search(anchored_selector + r'\s*\{([^}]*)\}', CSS, re.M)
    assert m, f'CSS rule not found: {anchored_selector}'
    return m.group(1)


# ── next_step: the ask ladder ──────────────────────────────────────────────

def test_blank_sheet_asks_for_eight_sides(app, monkeypatch):
    week = make_week(1)
    at(monkeypatch, IN_WEEK1)
    step = picks_service.next_step(_state(0), week)
    assert step['stage'] == 'blank'
    assert step['ask'] == 'Tap 8 sides to fill your sheet.'
    assert step['remaining'] == 8


def test_partial_sheet_counts_down(app, monkeypatch):
    week = make_week(1)
    at(monkeypatch, IN_WEEK1)
    assert picks_service.next_step(_state(3), week)['ask'] == \
        '5 more sides to file.'
    assert picks_service.next_step(_state(7), week)['ask'] == \
        '1 more side to file.'


def test_eight_filed_asks_for_the_x2_first(app, monkeypatch):
    week = make_week(1)
    at(monkeypatch, IN_WEEK1)
    step = picks_service.next_step(_state(8), week)
    assert step['stage'] == 'x2'
    assert step['ask'] == 'All 8 filed. Now pick your x2: it scores double.'


def test_then_the_number(app, monkeypatch):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    week.tiebreaker_game_id = game.id
    db.session.flush()
    at(monkeypatch, IN_WEEK1)
    step = picks_service.next_step(_state(8, best={'slot': 1}), week)
    assert step['stage'] == 'number'
    assert step['ask'] == 'Now your number: predict the tiebreaker score.'


def test_number_rung_skipped_when_no_case_is_designated(app, monkeypatch):
    week = make_week(1)
    at(monkeypatch, IN_WEEK1)
    step = picks_service.next_step(_state(8, best={'slot': 1}), week)
    assert step['stage'] == 'reserve'


def test_then_the_reserve_is_optional(app, monkeypatch):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    week.tiebreaker_game_id = game.id
    db.session.flush()
    at(monkeypatch, IN_WEEK1)
    step = picks_service.next_step(
        _state(8, best={'slot': 1}, prediction='51.5'), week)
    assert step['stage'] == 'reserve'
    assert step['ask'] == 'Optional: tap one more side as your reserve.'


def test_complete_sheet_has_a_closing_line(app, monkeypatch):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    week.tiebreaker_game_id = game.id
    db.session.flush()
    at(monkeypatch, IN_WEEK1)
    step = picks_service.next_step(
        _state(8, best={'slot': 1}, prediction='51.5', backup={'slot': 9}),
        week)
    assert step['stage'] == 'complete'
    assert step['ask'] == \
        'Sheet filed. Change anything until Saturday 11:00 AM CT.'


def test_preview_and_closed_rungs(app, monkeypatch):
    week = make_week(1)
    at(monkeypatch, '2026-08-30T12:00:00')          # before the boundary
    step = picks_service.next_step(_state(0), week)
    assert step['stage'] == 'preview'
    assert step['ask'] == 'Picks open Tuesday, September 1.'
    at(monkeypatch, '2026-09-05T16:00:00')          # 11:00 AM CT exactly
    step = picks_service.next_step(_state(3), week)
    assert step['stage'] == 'closed'
    assert step['ask'] == 'The docket is closed. Verdicts to follow.'


def test_urgent_prefix_inside_six_hours(app, monkeypatch):
    week = make_week(1)
    at(monkeypatch, '2026-09-05T13:00:00')          # 3h before 16:00 UTC
    step = picks_service.next_step(_state(6), week)
    assert step['urgent'] is True
    assert step['ask'] == 'Closes in 3h 0m. 2 more sides to file.'
    at(monkeypatch, '2026-09-04T12:00:00')
    assert picks_service.next_step(_state(6), week)['urgent'] is False


def test_sheet_state_embeds_next_step(app, monkeypatch):
    user = make_user('u')
    week = make_week(1)
    db.session.flush()
    at(monkeypatch, IN_WEEK1)
    state = picks_service.sheet_state(user.id, week)
    assert state['next_step']['stage'] == 'blank'


# ── Success is confirmed: message in the JSON and the flash ───────────────

def test_set_pick_json_carries_a_message_with_the_ask(
        monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    payload = _file(client, game).get_json()
    assert payload['ok'] is True
    assert payload['message'] == 'Filed, slot 1. 7 more sides to file.'


def test_eighth_pick_message_turns_to_the_x2(monkeypatch, client, member):
    week = make_week(1)
    games = [make_game(week, kickoff=KICK_SAT) for _ in range(8)]
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    for g in games[:7]:
        _file(client, g)
    payload = _file(client, games[7]).get_json()
    assert payload['message'] == \
        'Filed, slot 8. All 8 filed. Now pick your x2: it scores double.'


def test_reserve_message_says_what_a_reserve_is(monkeypatch, client, member):
    week = make_week(1)
    games = [make_game(week, kickoff=KICK_SAT) for _ in range(9)]
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    for g in games[:8]:
        _file(client, g)
    payload = _file(client, games[8], backup='1').get_json()
    assert payload['message'].startswith(
        'Filed as your reserve. It only plays if a case is thrown out.')


def test_x2_and_number_messages(monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT, home='Utah Utes',
                     away='Idaho Vandals')
    week.tiebreaker_game_id = game.id
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    _file(client, game, 'total', 'over')
    resp = client.post('/docket/best',
                       data={'game_id': game.id, 'market': 'total',
                             'csrf_token': 'x'}, headers=JSON)
    assert resp.get_json()['message'].startswith('x2 set: Over 51.5.')
    resp = client.post('/docket/tiebreaker',
                       data={'prediction': '53.7', 'csrf_token': 'x'},
                       headers=JSON)
    assert resp.get_json()['message'].startswith('Number saved: 53.7.')


def test_form_post_flashes_the_same_message(monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    resp = client.post('/docket/picks/set',
                       data={'game_id': game.id, 'market': 'spread',
                             'side': 'home', 'csrf_token': 'x'},
                       follow_redirects=True)
    assert 'Filed, slot 1. 7 more sides to file.' in resp.data.decode()


# ── Refusals say what to do ───────────────────────────────────────────────

def test_sheet_full_copy_names_the_way_out(monkeypatch, app):
    user = make_user('u')
    week = make_week(1)
    games = [make_game(week, kickoff=KICK_SAT) for _ in range(10)]
    db.session.flush()
    at(monkeypatch, IN_WEEK1)
    for g in games[:8]:
        picks_service.set_pick(user.id, week, g.id, 'spread', 'home')
    picks_service.set_pick(user.id, week, games[8].id, 'spread', 'home',
                           backup=True)
    with pytest.raises(PickError) as err:
        picks_service.set_pick(user.id, week, games[9].id, 'spread', 'home')
    assert err.value.message == (
        'Your sheet is full: eight sides plus a reserve. Remove a pick to '
        'swap this one in.')


def test_sheet_full_without_reserve_offers_reserve(monkeypatch, app):
    """When all 8 scoring slots are full but the reserve is empty, the error
    message mentions the reserve as an option, not as something already held."""
    user = make_user('u')
    week = make_week(1)
    games = [make_game(week, kickoff=KICK_SAT) for _ in range(10)]
    db.session.flush()
    at(monkeypatch, IN_WEEK1)
    for g in games[:8]:
        picks_service.set_pick(user.id, week, g.id, 'spread', 'home')
    with pytest.raises(PickError) as err:
        picks_service.set_pick(user.id, week, games[8].id, 'spread', 'home')
    assert err.value.message == (
        'All eight scoring slots are filled. Remove a pick, '
        'or file this one as your reserve.')
    assert 'plus a reserve' not in err.value.message


def test_prediction_cap_catches_a_dropped_decimal():
    with pytest.raises(PickError) as err:
        picks_service.parse_prediction_tenths('515')
    assert err.value.status == 400
    assert err.value.message == (
        'That looks high for a combined score. Enter it like 51.5.')


# ── The rendered sheet ────────────────────────────────────────────────────

def test_blank_sheet_renders_orientation_and_the_ask(
        monkeypatch, client, member):
    week = make_week(1)
    make_game(week, kickoff=KICK_SAT)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    html = client.get('/docket/').data.decode()
    assert 'docket-orient' in html
    assert 'How the sheet works' in html
    assert html.count('Tap 8 sides to fill your sheet.') == 3   # bar, drawer, rail
    # Before 8 scoring picks, the bar shows neutral labels (not "open")
    assert 'x2 open' not in html and 'Reserve open' not in html
    assert '>x2<' in html and '>Reserve<' in html and 'No number' in html
    assert 'R open' not in html and 'no x2' not in html
    assert 'docket-rail-bar-handle' in html


def test_orientation_leaves_after_the_first_pick(monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    _file(client, game)
    html = client.get('/docket/').data.decode()
    assert 'docket-orient' not in html
    assert '7 more sides to file.' in html


def test_held_pill_carries_the_x2_button(monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    _file(client, game)
    html = client.get('/docket/').data.decode()
    pill = re.search(r'<div class="docket-side is-picked[^"]*">.*?</div>\s*</div>',
                     html, re.S)
    assert pill, 'the held pill must be a div (it nests the x2 form)'
    assert 'data-docket-action="set-best"' in pill.group(0)
    assert 'docket-x2-btn' in pill.group(0)


def test_locked_and_reserve_pills_carry_no_x2_button(
        monkeypatch, client, member):
    week = make_week(1)
    thu = make_game(week, kickoff=KICK_THU)
    games = [make_game(week, kickoff=KICK_SAT) for _ in range(8)]
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    _file(client, thu)
    for g in games[:7]:
        _file(client, g)
    _file(client, games[7], backup='1')
    at(monkeypatch, '2026-09-04T01:00:00')          # Thursday kicked off
    html = client.get('/docket/?day=2026-09-03').data.decode()
    locked = re.search(r'<div class="docket-side is-picked is-locked[^"]*">.*?</div>\s*</div>',
                       html, re.S)
    assert locked and 'set-best' not in locked.group(0)
    html = client.get('/docket/?day=2026-09-05').data.decode()
    reserve = re.search(r'<div class="docket-side is-picked[^"]*">(?:(?!</article>).)*?Reserve</span>',
                        html, re.S)
    assert reserve and 'set-best' not in reserve.group(0)


def test_full_sheet_renders_the_prompt_card(monkeypatch, client, member):
    week = make_week(1)
    games = [make_game(week, kickoff=KICK_SAT) for _ in range(8)]
    week.tiebreaker_game_id = games[0].id
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    for g in games:
        _file(client, g)
    html = client.get('/docket/').data.decode()
    assert 'docket-prompt' in html
    assert 'Tap x2 on any filed pick' in html
    assert 'Your next tap on any open side files as your reserve' in html
    assert 'data-docket-open-sheet' in html


def test_number_card_states_its_default_and_saves(monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    week.tiebreaker_game_id = game.id
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    html = client.get('/docket/').data.decode()
    assert 'Save number' in html
    assert '>Record<' not in html
    assert 'Your prediction' in html
    assert 'Skip it and the line stands in as your number.' in html
    client.post('/docket/tiebreaker',
                data={'prediction': '53.7', 'csrf_token': 'x'})
    html = client.get('/docket/').data.decode()
    assert 'Saved: 53.7. Change it until Saturday 11:00 AM CT.' in html


def test_rail_speaks_reserve_and_remove(monkeypatch, client, member):
    week = make_week(1)
    game = make_game(week, kickoff=KICK_SAT)
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    _file(client, game)
    html = client.get('/docket/').data.decode()
    assert '>Remove<' in html and '>Withdraw<' not in html
    assert '>Make this x2<' in html
    assert 'docket-slot-num-reserve' in html
    assert 'Held in reserve.' not in html


def test_drawer_controls_clear_the_touch_floor():
    assert re.search(r'min-height:\s*44px',
                     _rule(r'^\.docket-rail-drawer \.docket-slot-btn'))
    assert re.search(r'min-height:\s*44px', _rule(r'^\.docket-x2-btn'))
    notice = _rule(r'^\.docket-notice')
    m = re.search(r'(?<![-\w])bottom:\s*(\d+)px', notice)
    assert m and int(m.group(1)) >= 84
