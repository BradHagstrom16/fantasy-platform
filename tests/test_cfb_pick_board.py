"""CFB pick board: the filtered slate, the sticky commit bar, the status strip
(impeccable critique 2026-09-01, live Week 1 at 375px).

Locks the contracts of the 2026-09-01 pick-page pass:

  - the room's short deadline + relative countdown helpers
  - the board partition: a game shows by default iff it has at least one
    pickable team (or holds the member's existing pick); the rest stay in the
    DOM behind a disclosure, never omitted
  - the commit bar is sticky and names the team it locks in
  - the legend is a census of the states actually on the board
"""
import dataclasses
import re
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import games.registry as registry
from extensions import db
from games.cfb.models import CfbGame
from games.cfb.services import board
from games.cfb.utils import format_deadline_short, format_relative
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)

FUTURE_DEADLINE = datetime(2099, 1, 1, 11, 0)


@pytest.fixture(autouse=True)
def cfb_open():
    """Flip CFB to 'open' so an enrolled non-admin can reach /cfb/pick."""
    flipped = [
        dataclasses.replace(e, status='open') if e.slug == 'cfb' else e
        for e in registry.GAMES
    ]
    with patch.object(registry, 'GAMES', flipped):
        yield


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _chip_reason(data, name):
    """The out-reason chip on a team's own board row (same shape as
    tests/test_cfb_pick.py so the two files lock the same markup)."""
    m = re.search(
        r'cfb-team-name">' + re.escape(name) + r'</span>'
        r'(?:\s*<span class="cfb-home-tag">Home</span>)?'
        r'\s*<span class="cfb-out-reason">([^<]+)</span>',
        data)
    return m.group(1) if m else None


def _untracked_game(week, pool_team, *, spread):
    """A pool team hosting a non-pool (untracked) opponent."""
    g = CfbGame(week_id=week.id, home_team_id=pool_team.id, away_team_id=None,
                away_team_name='Arkansas Pine Bluff Golden Lions',
                home_team_spread=spread, game_time=week.deadline)
    db.session.add(g)
    db.session.flush()
    return g


# ── Time helpers ───────────────────────────────────────────────────────────

def test_format_relative_days_and_hours():
    assert format_relative(timedelta(days=2, hours=14, minutes=9)) == '2d 14h'


def test_format_relative_hours_and_minutes():
    assert format_relative(timedelta(hours=3, minutes=18)) == '3h 18m'


def test_format_relative_minutes_only():
    assert format_relative(timedelta(minutes=42)) == '42m'


def test_format_relative_never_negative():
    assert format_relative(timedelta(minutes=-5)) == '0m'


def test_format_deadline_short_reads_weekday_date_and_ct(app):
    # Naive pool-tz wall clock, the CfbWeek.deadline column contract.
    with app.app_context():
        assert format_deadline_short(datetime(2026, 9, 5, 11, 0)) == \
            'Saturday, Sep 5 · 11:00 AM CT'


def test_format_deadline_short_tbd_when_missing(app):
    with app.app_context():
        assert format_deadline_short(None) == 'TBD'


# ── board.side_state: the one precedence for a team row's state ───────────

def _team(tid, name='T'):
    return SimpleNamespace(id=tid, name=name)


def _state(team, spread, **kw):
    opts = {'preview': False, 'used_ids': set(), 'eligible_ids': set(),
            'cfp_out_names': set(), 'started': False}
    opts.update(kw)
    return board.side_state(team, spread, **opts)


def test_non_pool_opponent_is_never_pickable():
    assert _state(None, -3.0, eligible_ids={1}) == 'not_in_pool'


def test_eligible_team_reads_open():
    assert _state(_team(1), -3.0, eligible_ids={1}) == 'open'


def test_used_beats_every_other_out_reason():
    assert _state(_team(1), -20.5, used_ids={1}, started=True) == 'used'


def test_cfp_out_beats_started_and_spread():
    assert _state(_team(1, 'Elim'), -20.5, cfp_out_names={'Elim'},
                  started=True) == 'cfp_out'


def test_started_beats_the_spread_cap():
    assert _state(_team(1), -20.5, started=True) == 'started'


def test_spread_cap_is_inclusive_at_16_5():
    assert _state(_team(1), -16.5) == 'too_favored'
    assert _state(_team(1), -16.0) == 'out'      # eligible_ids decides open


def test_missing_line_reads_no_line():
    assert _state(_team(1), None) == 'no_line'


def test_preview_marks_only_used_and_on_slate():
    assert _state(_team(1), None, preview=True, used_ids={1}) == 'used'
    assert _state(_team(2), None, preview=True) == 'on_slate'
    assert _state(None, None, preview=True) == 'not_in_pool'


# ── board.partition_board: open iff a side is open, or it holds the pick ──

def _game(gid, home_id, away_id):
    return SimpleNamespace(id=gid, home_team_id=home_id, away_team_id=away_id)


def test_partition_hides_games_with_no_open_side():
    games = [_game(1, 10, 11), _game(2, 20, 21)]
    states = {1: {'home': 'open', 'away': 'not_in_pool'},
              2: {'home': 'too_favored', 'away': 'not_in_pool'}}
    open_games, hidden = board.partition_board(games, states)
    assert [g.id for g in open_games] == [1]
    assert [g.id for g in hidden] == [2]


def test_partition_keeps_kickoff_order_within_each_half():
    games = [_game(1, 10, 11), _game(2, 20, 21), _game(3, 30, 31)]
    states = {1: {'home': 'used', 'away': 'used'},
              2: {'home': 'open', 'away': 'open'},
              3: {'home': 'open', 'away': 'used'}}
    open_games, hidden = board.partition_board(games, states)
    assert [g.id for g in open_games] == [2, 3]
    assert [g.id for g in hidden] == [1]


def test_partition_always_shows_the_card_holding_the_members_pick():
    games = [_game(1, 10, 11)]
    states = {1: {'home': 'started', 'away': 'started'}}
    open_games, hidden = board.partition_board(games, states, held_team_id=11)
    assert [g.id for g in open_games] == [1]
    assert hidden == []


# ── board.legend_census: only states actually on the page, canonical order ─

def test_legend_census_lists_board_and_ledger_states_in_canonical_order():
    states = {1: {'home': 'not_in_pool', 'away': 'open'},
              2: {'home': 'too_favored', 'away': 'open'}}
    assert board.legend_census(states, ledger_reasons={'not_playing'}) == \
        ['open', 'too_favored', 'not_playing', 'not_in_pool']


def test_legend_census_drops_states_nobody_can_see():
    states = {1: {'home': 'open', 'away': 'open'}}
    assert board.legend_census(states, ledger_reasons=set()) == ['open']


# ── board.hidden_games_sentence: the absence, explained ───────────────────

def test_hidden_sentence_names_the_reasons_present():
    games = [_game(2, 20, None)]
    states = {2: {'home': 'too_favored', 'away': 'not_in_pool'}}
    assert board.hidden_games_sentence(games, states) == (
        '1 game has no open team this week: favorites of 16.5 or more, '
        'opponents outside the pool.')


def test_hidden_sentence_pluralizes():
    games = [_game(1, 1, 2), _game(2, 3, 4)]
    states = {1: {'home': 'used', 'away': 'used'},
              2: {'home': 'used', 'away': 'started'}}
    assert board.hidden_games_sentence(games, states) == (
        '2 games have no open team this week: teams you have used, '
        'games already kicked off.')


# ── The rendered board ────────────────────────────────────────────────────

def test_game_with_no_open_team_collapses_behind_the_disclosure(app, client):
    week = make_week(1, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('Open A'), make_team('Open B'), spread=-3.0)
    _untracked_game(week, make_team('BigFav'), spread=-24.5)  # nothing pickable
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/1').data.decode()

    rest = data.index('<details class="cfb-board-rest">')     # closed by default
    assert data.index('cfb-team-name">Open A<') < rest        # open card first
    assert data.index('cfb-team-name">BigFav<') > rest        # hidden card inside
    assert _chip_reason(data, 'BigFav') == 'Favored 16.5+'        # chips intact
    assert 'Show all 2 games' in data
    assert '1 game with an open team' in data
    assert '2 open teams' in data
    assert ('1 game has no open team this week: favorites of 16.5 or more, '
            'opponents outside the pool.') in data


def test_disclosure_opens_when_nothing_is_pickable(app, client):
    user = make_user('p1')
    make_enrollment(user)
    prior = make_week(1)                                      # past deadline
    used = make_team('Wisconsin')
    make_pick(user, prior, used)
    week = make_week(2, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('Notre Dame'), used, spread=-20.5)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/2').data.decode()

    assert 'No Open Teams' in data
    assert '<details class="cfb-board-rest" open>' in data
    assert _chip_reason(data, 'Notre Dame') == 'Favored 16.5+'


def test_board_without_hidden_games_renders_no_disclosure(app, client):
    week = make_week(1, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('Open A'), make_team('Open B'), spread=-3.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/1').data.decode()

    assert 'cfb-board-rest' not in data
    assert '1 game with an open team' in data


# ── Member language: labels are sentences a first-timer reads, not rule IDs ─

def test_state_labels_speak_member_language():
    assert board.STATE_LABELS['too_favored'] == 'Favored 16.5+'
    assert board.STATE_LABELS['not_in_pool'] == 'Not a Pool Team'
    assert board.STATE_LABELS['used'] == 'Already Used'
    assert board.STATE_LABELS['started'] == 'Kicked Off'
    assert board.STATE_LABELS['not_playing'] == 'No Game This Week'


def test_board_states_the_binding_rules_once(app, client):
    week = make_week(1, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('Open A'), make_team('Open B'), spread=-3.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/1').data.decode()

    assert 'Pick one team to win outright.' in data
    assert 'A team is yours for the season once you use it.' in data
    assert 'Teams favored by 16.5 or more are off the board.' in data
    assert 'Only the 2 pool teams can be picked' in data
    assert 'Minus means favored' in data


def test_ledger_notes_use_the_shared_labels(app, client):
    week = make_week(1, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('Open A'), make_team('Open B'), spread=-3.0)
    make_team('Bye Team')
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/1').data.decode()

    assert ('cfb-team-chip is-out">Bye Team<span class="cfb-team-chip-note">'
            'No Game This Week</span>') in data


# ── The commit bar: sticky, names the team, offers a real Clear ────────────

CSS = None


def _css():
    global CSS
    if CSS is None:
        from pathlib import Path
        CSS = (Path(__file__).resolve().parent.parent / 'static' / 'css'
               / 'style.css').read_text()
    return CSS


def _rule(anchored_selector):
    m = re.search(anchored_selector + r'\s*\{([^}]*)\}', _css(), re.M)
    assert m, f'CSS rule not found: {anchored_selector}'
    return m.group(1)


def test_confirm_bar_is_sticky_at_the_viewport_bottom():
    block = _rule(r'^#pickConfirmBar')
    assert re.search(r'position:\s*sticky', block)
    assert re.search(r'(?<![-\w])bottom:\s*0', block)
    assert 'z-index' in block
    # The platform .card:hover lift would make a pinned bar jump.
    assert re.search(r'transform:\s*none', _rule(r'^#pickConfirmBar:hover'))


def test_confirm_bar_names_the_team_and_offers_clear(app, client):
    week = make_week(1, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('Open A'), make_team('Open B'), spread=-3.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/1').data.decode()

    assert 'id="confirmBtnTeam"' in data
    assert 'Lock In <span id="confirmBtnTeam">' in data
    assert 'Not Locked Yet' in data
    assert 'id="clearSelection"' in data
    assert 'aria-live="polite"' in data
    assert '>Cancel<' not in data


def test_confirm_bar_keeps_the_held_pick_by_name(app, client):
    user = make_user('p1')
    make_enrollment(user)
    week = make_week(1, deadline=FUTURE_DEADLINE)
    held = make_team('Held Team')
    make_game(week, held, make_team('Other'), spread=-3.0)
    make_pick(user, week, held)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/1').data.decode()

    # Held: the bar shows the pick on file and the button keeps it by name;
    # the JS switches the verb to "Change To" the moment another row is tapped.
    assert 'Keep <span id="confirmBtnTeam">Held Team</span>' in data
    assert 'Your Standing Pick' in data


# ── The status strip: lives, the clock, the consequence ───────────────────

def test_status_strip_states_the_unmade_pick_and_its_consequence(app, client):
    week = make_week(1, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('Open A'), make_team('Open B'), spread=-3.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/1').data.decode()

    assert 'You have not made a pick.' in data
    assert 'Miss the deadline and you get the biggest available favorite.' in data
    assert data.count('<span class="life"></span>') == 2       # two lives, pips
    assert 'Picks Lock' in data                                  # literal eyebrow
    assert re.search(r'in \d+d \d+h', data)                     # relative
    assert '11:00 AM CT' in data                                 # short absolute
    assert 'at 11:00 AM' not in data                             # long form gone


def test_status_strip_holds_the_pick_without_the_unmade_line(app, client):
    user = make_user('p1')
    make_enrollment(user, lives=1)
    week = make_week(1, deadline=FUTURE_DEADLINE)
    held = make_team('Held Team')
    make_game(week, held, make_team('Other'), spread=-3.0)
    make_pick(user, week, held)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/1').data.decode()

    assert 'You have not made a pick.' not in data
    assert 'Change it any time before picks lock.' in data
    assert data.count('<span class="life"></span>') == 1
    assert data.count('<span class="life lost"></span>') == 1


# ── Format polish ─────────────────────────────────────────────────────────

def test_kickoff_reads_like_the_deadline(app, client):
    week = make_week(1, deadline=datetime(2026, 9, 5, 11, 0))
    make_game(week, make_team('Open A'), make_team('Open B'), spread=-3.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)
    import os
    from unittest.mock import patch as _patch
    with _patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                  'CFB_FAKE_NOW': '2026-09-01T13:00:00'}):
        data = client.get('/cfb/pick/1').data.decode()

    assert 'Sat, Sep 5 · 11:00 AM' in data      # kickoff = fixture deadline
    assert '09/05' not in data


def test_out_reason_chip_clears_the_caption_floor():
    block = _rule(r'^\.cfb-out-reason')
    m = re.search(r'font-size:\s*([\d.]+)rem', block)
    assert m and float(m.group(1)) >= 0.75


def test_open_rows_carry_a_visible_edge_and_opponents_demote():
    assert 'inset' in _rule(r'^body\.game-cfb \.team-option\[role="button"\]')
    assert _rule(r'^body\.game-cfb \.team-option\.team-option-out\.is-opponent')
    assert re.search(r'min-height:\s*44px',
                     _rule(r'^\.cfb-board-toggle'))
