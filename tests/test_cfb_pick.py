"""CFB make_pick eligibility + create/update locks (pre-launch audit §8.8-10).

Regression locks for behavior the audit verified correct (no ⚠ items):
the 16.5 spread-cap sign convention, GET ``eligible_teams`` parity with
the POST guards, used-team / deadline / started-game rejections, the
eliminated-user redirect, and pick create-vs-update semantics.

CFB launches ``coming_soon``; an autouse fixture flips the registry entry
to ``open`` so an enrolled non-admin can reach ``/cfb/pick`` the way a real
player will at launch. Session identity is auth_id, never str(user.id).

Datetime column contract (see tests/_cfb_fixtures.py): CfbWeek deadline /
CfbGame game_time hold naive pool-tz wall clock; a far-future deadline keeps
a week pickable, a past game_time marks an individual game started.
"""
import dataclasses
import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from flask import template_rendered
from sqlalchemy.exc import IntegrityError

import games.registry as registry
from app import create_app
from extensions import db
from games.cfb.models import CfbPick
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)

# Naive pool-tz wall clock. FUTURE keeps a week pickable; STARTED is a
# game_time safely in the past so that one game reads as kicked off.
FUTURE_DEADLINE = datetime(2099, 1, 1, 11, 0)
STARTED = datetime(2020, 1, 1, 11, 0)


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _open_cfb_games():
    """Registry list with CFB flipped to 'open' (entries are frozen)."""
    return [
        dataclasses.replace(e, status='open') if e.slug == 'cfb' else e
        for e in registry.GAMES
    ]


@pytest.fixture(autouse=True)
def cfb_open():
    """Flip CFB to 'open' for the whole test so enrolled non-admins can pick."""
    with patch.object(registry, 'GAMES', _open_cfb_games()):
        yield


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


@contextmanager
def captured_templates(app):
    """Record (template, context) pairs so a test can read the route's
    computed context (e.g. eligible_teams) rather than guessing from HTML."""
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)


def _eligible_names(templates):
    """Names in the pick.html render's eligible_teams context list."""
    ctx = next(c for t, c in templates if t.name == 'cfb/pick.html')
    return {team.name for team in ctx['eligible_teams']}


def _post_pick(client, week_number, team_id):
    return client.post(
        f'/cfb/pick/{week_number}',
        data={'team_id': str(team_id), 'csrf_token': 'x'},
        follow_redirects=False,
    )


# ── §8.8 — spread-cap sign convention (16.5+ favorites ineligible) ────────

def test_post_rejects_home_favorite_at_exactly_16_5(app, client):
    """A home team favored by exactly 16.5 is ineligible (<= -16.5)."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Bama'), make_team('Vandy')
    make_game(week, home, away, spread=-16.5)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    resp = _post_pick(client, 1, home.id)

    assert resp.status_code == 302
    assert '/cfb/pick/1' in resp.headers['Location']  # bounced back, not index
    assert CfbPick.query.filter_by(user_id=user.id, week_id=week.id).first() is None


def test_post_allows_home_favorite_at_16_0(app, client):
    """16.0 is under the cap — pickable; lands on the index after success."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Bama'), make_team('Vandy')
    make_game(week, home, away, spread=-16.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    resp = _post_pick(client, 1, home.id)

    assert resp.status_code == 302
    assert resp.headers['Location'] in ('/cfb/', 'http://localhost/cfb/')
    pick = CfbPick.query.filter_by(user_id=user.id, week_id=week.id).first()
    assert pick is not None and pick.team_id == home.id


def test_post_rejects_away_team_when_home_is_plus_16_5(app, client):
    """Home +16.5 ⇒ away favored by 16.5 ⇒ away ineligible (sign flip)."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Vandy'), make_team('Bama')
    make_game(week, home, away, spread=16.5)  # away (Bama) favored by 16.5
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    resp = _post_pick(client, 1, away.id)

    assert resp.status_code == 302
    assert '/cfb/pick/1' in resp.headers['Location']
    assert CfbPick.query.filter_by(user_id=user.id, week_id=week.id).first() is None


def test_post_rejects_team_with_no_spread(app, client):
    """A game with no posted spread locks both teams out."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Home'), make_team('Away')
    make_game(week, home, away, spread=None)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    resp = _post_pick(client, 1, home.id)

    assert resp.status_code == 302
    assert '/cfb/pick/1' in resp.headers['Location']
    assert CfbPick.query.filter_by(user_id=user.id, week_id=week.id).first() is None


def test_get_eligible_teams_parity_with_post_rules(app, client):
    """GET eligible_teams mirrors POST acceptance: the 16.5 favorite and the
    no-spread teams are absent; the 16.0 favorite and its underdog are present."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    # Game A: home favored by 16.5 → home out, away (dog +16.5) in.
    a_home, a_away = make_team('BigFav'), make_team('BigDog')
    make_game(week, a_home, a_away, spread=-16.5)
    # Game B: home favored by 16.0 → both in.
    b_home, b_away = make_team('OkFav'), make_team('OkDog')
    make_game(week, b_home, b_away, spread=-16.0)
    # Game C: no spread → both out.
    c_home, c_away = make_team('NoSpreadH'), make_team('NoSpreadA')
    make_game(week, c_home, c_away, spread=None)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    with captured_templates(app) as templates:
        client.get('/cfb/pick/1')
    eligible = _eligible_names(templates)

    assert 'OkFav' in eligible and 'OkDog' in eligible  # 16.0 favorite + its dog
    assert 'BigDog' in eligible                          # +16.5 underdog eligible
    assert 'BigFav' not in eligible                      # 16.5 favorite excluded
    assert 'NoSpreadH' not in eligible and 'NoSpreadA' not in eligible


# ── §8.9 — used-team / deadline / started-game / eliminated rejections ────

def test_post_rejects_team_used_in_same_phase(app, client):
    """A team picked in a prior regular-season week can't be reused."""
    w1 = make_week(1, deadline=FUTURE_DEADLINE)
    w2 = make_week(2, deadline=FUTURE_DEADLINE)
    team = make_team('Repeat')
    other = make_team('Other')
    make_game(w1, team, other, spread=-3.0)
    make_game(w2, team, other, spread=-3.0)
    user = make_user('p1')
    make_enrollment(user)
    make_pick(user, w1, team)
    db.session.commit()
    _login(client, user)

    resp = _post_pick(client, 2, team.id)

    assert resp.status_code == 302
    assert '/cfb/pick/2' in resp.headers['Location']
    # Only the week-1 pick exists; week 2 got none.
    assert CfbPick.query.filter_by(user_id=user.id, week_id=w2.id).first() is None


def test_post_rejected_after_deadline(app, client):
    """A past deadline bounces the POST to the index with no pick stored."""
    week = make_week(1)  # default PAST_DEADLINE
    home, away = make_team('Home'), make_team('Away')
    make_game(week, home, away, spread=-3.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    resp = _post_pick(client, 1, home.id)

    assert resp.status_code == 302
    assert resp.headers['Location'] in ('/cfb/', 'http://localhost/cfb/')
    assert CfbPick.query.filter_by(user_id=user.id, week_id=week.id).first() is None


def test_get_after_deadline_redirects_to_index(app, client):
    """GET on a locked week redirects rather than rendering the picker."""
    make_week(1)  # past deadline
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    resp = client.get('/cfb/pick/1')

    assert resp.status_code == 302
    assert resp.headers['Location'] in ('/cfb/', 'http://localhost/cfb/')


def test_existing_pick_locks_when_its_game_started(app, client):
    """Once the picked team's game kicks off, the pick can't be changed."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    locked_home, locked_away = make_team('Started'), make_team('StartedOpp')
    g = make_game(week, locked_home, locked_away, spread=-3.0)
    g.game_time = STARTED  # already kicked off
    open_home, open_away = make_team('Open'), make_team('OpenOpp')
    make_game(week, open_home, open_away, spread=-3.0)
    user = make_user('p1')
    make_enrollment(user)
    make_pick(user, week, locked_home)
    db.session.commit()
    _login(client, user)

    resp = _post_pick(client, 1, open_home.id)

    # A locked pick re-renders the page with the lock flash (not a redirect);
    # the invariant under test is that the stored pick is untouched.
    assert resp.status_code == 200
    assert b'locked' in resp.data.lower()
    pick = CfbPick.query.filter_by(user_id=user.id, week_id=week.id).first()
    assert pick.team_id == locked_home.id  # unchanged — switch was blocked


def test_post_rejects_pick_onto_a_started_game(app, client):
    """Can't pick a team whose game has already started."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    open_home, open_away = make_team('Open'), make_team('OpenOpp')
    make_game(week, open_home, open_away, spread=-3.0)
    started_home, started_away = make_team('Gone'), make_team('GoneOpp')
    g = make_game(week, started_home, started_away, spread=-3.0)
    g.game_time = STARTED
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    resp = _post_pick(client, 1, started_home.id)

    assert resp.status_code == 302
    assert '/cfb/pick/1' in resp.headers['Location']
    assert CfbPick.query.filter_by(user_id=user.id, week_id=week.id).first() is None


def test_eliminated_user_redirected_from_pick(app, client):
    """An eliminated enrollment is bounced to the index on GET and POST."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Home'), make_team('Away')
    make_game(week, home, away, spread=-3.0)
    user = make_user('p1')
    make_enrollment(user, lives=0, eliminated=True)
    db.session.commit()
    _login(client, user)

    get_resp = client.get('/cfb/pick/1')
    post_resp = _post_pick(client, 1, home.id)

    assert get_resp.status_code == 302
    assert get_resp.headers['Location'] in ('/cfb/', 'http://localhost/cfb/')
    assert post_resp.status_code == 302
    assert CfbPick.query.filter_by(user_id=user.id, week_id=week.id).first() is None


# ── §8.10 — pick create vs. update (created_at refresh) ───────────────────

def test_pick_created_when_none_exists(app, client):
    """First submission creates exactly one pick row."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Home'), make_team('Away')
    make_game(week, home, away, spread=-7.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    _post_pick(client, 1, home.id)

    picks = CfbPick.query.filter_by(user_id=user.id, week_id=week.id).all()
    assert len(picks) == 1 and picks[0].team_id == home.id


def test_pick_updated_in_place_not_duplicated(app, client):
    """Changing the pick mutates the existing row — no second pick appears."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Home'), make_team('Away')
    make_game(week, home, away, spread=-7.0)
    user = make_user('p1')
    make_enrollment(user)
    make_pick(user, week, home)
    db.session.commit()
    _login(client, user)

    _post_pick(client, 1, away.id)

    picks = CfbPick.query.filter_by(user_id=user.id, week_id=week.id).all()
    assert len(picks) == 1 and picks[0].team_id == away.id


def test_no_eligible_alert_uses_accurate_cap_copy(app, client):
    """The empty-state alert says 'favored by 16.5 or more' — exactly 16.5 is
    already ineligible, so the old 'more than 16.5' was wrong (audit §1 LOW).

    Exhaustion needs a posted spread since the 2026-08-19 lines-pending
    slate: an all-lineless week previews the board instead. Here the home
    side is capped and the away side is already used."""
    user = make_user('p1')
    make_enrollment(user)
    prior = make_week(1)                               # past deadline
    away = make_team('UsedAway')
    make_pick(user, prior, away)
    week = make_week(2, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('CappedHome'), away, spread=-20.5)
    db.session.commit()
    _login(client, user)

    text = client.get('/cfb/pick/2').get_data(as_text=True)

    assert '16.5 or more' in text
    assert 'more than 16.5' not in text


def test_pick_page_survives_null_game_time(app, client):
    """A game with a NULL game_time (import parse failure) must not 500 the
    pick page — the game_time sort has to be None-safe (audit §9 HIGH)."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    h1, a1 = make_team('H1'), make_team('A1')
    h2, a2 = make_team('H2'), make_team('A2')
    make_game(week, h1, a1, spread=-7.0)         # game_time = deadline (set)
    g2 = make_game(week, h2, a2, spread=-3.0)
    g2.game_time = None                           # parse failure left it NULL
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    resp = client.get('/cfb/pick/1')

    assert resp.status_code == 200


def test_created_at_refreshes_on_update(app, client):
    """An update stamps a fresh created_at (the recap deadline clock resets)."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Home'), make_team('Away')
    make_game(week, home, away, spread=-7.0)
    user = make_user('p1')
    make_enrollment(user)
    stale = datetime(2026, 1, 1, 0, 0)  # naive UTC per the column contract
    make_pick(user, week, home, created_at=stale)
    db.session.commit()
    _login(client, user)

    _post_pick(client, 1, away.id)

    pick = CfbPick.query.filter_by(user_id=user.id, week_id=week.id).first()
    assert pick.created_at > stale


# ── concurrent-pick race — unique-constraint protection ───────────────────
#
# One pick per (user, week) is enforced by the unique_cfb_user_week_pick
# constraint. A concurrent double-submit (both requests read "no pick", both
# INSERT) makes the loser's commit raise IntegrityError. True concurrency
# isn't observable under single-threaded in-memory SQLite, so we inject the
# IntegrityError the race would raise and assert graceful recovery — never a
# 500. (Cumulative-spread and is_eliminated-toggle races have no 500-class
# failure mode and aren't testable here; see the PR notes.)


def test_pick_unique_constraint_present():
    """Lock the (user_id, week_id) unique constraint so the race protection
    can't be silently dropped from the model. (Pure model introspection — no
    app context needed.)"""
    names = {c.name for c in CfbPick.__table_args__}
    assert 'unique_cfb_user_week_pick' in names


def test_double_submit_integrity_error_recovers_gracefully(app, client):
    """When the unique constraint rejects a racing duplicate INSERT at commit,
    the route rolls back and redirects gracefully instead of 500ing."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Home'), make_team('Away')
    make_game(week, home, away, spread=-7.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    err = IntegrityError('INSERT', {}, Exception('UNIQUE constraint failed'))
    with patch.object(db.session, 'commit', side_effect=err):
        resp = _post_pick(client, 1, home.id)

    assert resp.status_code == 302
    assert resp.headers['Location'] in ('/cfb/', 'http://localhost/cfb/')


def test_autoflush_integrity_error_recovers_gracefully(app, client):
    """The racing duplicate can also surface during autoflush — the SELECT in
    calculate_cumulative_spread flushes the pending INSERT before commit() is
    reached. That earlier path must recover identically (redirect, no 500), so
    the guard has to wrap the recalculation too, not just the commit."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Home'), make_team('Away')
    make_game(week, home, away, spread=-7.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    err = IntegrityError('INSERT', {}, Exception('UNIQUE constraint failed'))
    with patch('games.cfb.routes.calculate_cumulative_spread', side_effect=err):
        resp = _post_pick(client, 1, home.id)

    assert resp.status_code == 302
    assert resp.headers['Location'] in ('/cfb/', 'http://localhost/cfb/')


def test_pick_rejected_when_deadline_slips_past(app, client):
    """Deadline-slip race: the deadline lapses between the GET and the POST.
    With now (CFB_FAKE_NOW) a minute past the week deadline, the POST is
    rejected and no pick is stored — the started-game lock alone isn't relied
    on for the week-level cutoff."""
    deadline = datetime(2026, 9, 5, 11, 0)            # naive pool-tz wall clock
    week = make_week(1, deadline=deadline)
    home, away = make_team('Home'), make_team('Away')
    make_game(week, home, away, spread=-7.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    # ENVIRONMENT must ride in the same patch.dict or the CFB seam stays off.
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'CFB_FAKE_NOW': '2026-09-05T16:01:00+00:00'}):
        # 11:01 America/Chicago (CDT, UTC-5) == 16:01 UTC — one minute past.
        resp = _post_pick(client, 1, home.id)

    assert resp.status_code == 302
    assert resp.headers['Location'] in ('/cfb/', 'http://localhost/cfb/')
    assert CfbPick.query.filter_by(user_id=user.id, week_id=week.id).first() is None


# ── Lines-pending slate (pre-spread-lock board, 2026-08-19 ruling) ────────

def test_lines_pending_shows_the_slate_without_controls(app, client):
    """Games imported before the Tuesday spread lock render the full board
    read-only, not the misleading exhausted-state copy."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Notre Dame'), make_team('Wisconsin')
    make_game(week, home, away)                        # no spread yet
    user = make_user('previewer')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)
    data = client.get('/cfb/pick/1').data.decode()
    assert 'Notre Dame' in data
    assert 'Wisconsin' in data
    assert 'Lines and eligibility post' in data
    # The notice carries the computed lock date: the week's Tuesday, which
    # the fixture geometry puts at deadline - 4 days (start = deadline - 2,
    # lock = start - 2) — the same math the route runs.
    expected_lock = (FUTURE_DEADLINE - timedelta(days=4)).strftime('%A, %B %-d')
    assert f'spreads lock {expected_lock}.' in data
    # Attribute form: the picker JS's selector string mentions the name.
    assert 'data-team-id="' not in data
    assert 'No Open Teams' not in data
    assert 'Lock It In' not in data


def test_one_posted_spread_ends_lines_pending(app, client):
    week = make_week(1, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('Notre Dame'), make_team('Wisconsin'),
              spread=-3.5)
    make_game(week, make_team('Texas'), make_team('Ohio State'))
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)
    data = client.get('/cfb/pick/1').data.decode()
    assert 'Lines and eligibility post' not in data
    assert 'data-team-id="' in data


def test_exhausted_board_keeps_the_no_open_teams_copy(app, client):
    """Spreads posted but nothing pickable stays the real empty state."""
    user = make_user('p1')
    make_enrollment(user)
    prior = make_week(1)                               # past deadline
    away_used = make_team('Wisconsin')
    make_pick(user, prior, away_used)
    week = make_week(2, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('Notre Dame'), away_used,
              spread=-20.5)                            # home 16.5+, away used
    db.session.commit()
    _login(client, user)
    data = client.get('/cfb/pick/2').data.decode()
    assert 'No Open Teams' in data
    assert 'Lines and eligibility post' not in data


# ── Full-pool accounting: board + ledger cover all 49 (the state work) ─────

def _ledger_names(templates):
    """(name -> reason) for every team in the pool_ledger context list."""
    ctx = next(c for t, c in templates if t.name == 'cfb/pick.html')
    return {e['team'].name: e['reason'] for e in ctx['pool_ledger']}


def _chip_reason(data, name):
    """The out-reason chip text rendered on a specific team's board row, or
    None. Targets that team's own markup so a legend label can't satisfy the
    assertion by accident (CR #161)."""
    m = re.search(
        r'cfb-team-name">' + re.escape(name) + r'</span>'
        r'(?:\s*<span class="cfb-home-tag">Home</span>)?'
        r'\s*<span class="cfb-out-reason">([^<]+)</span>',
        data)
    return m.group(1) if m else None


def test_not_playing_team_lands_in_the_ledger(app, client):
    """A pool team with no game this week is not on the board — it shows in the
    ledger tagged 'not_playing', so 'not playing this week' is a visible state."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    home, away = make_team('Playing A'), make_team('Playing B')
    make_game(week, home, away, spread=-3.0)
    make_team('Bye Team')                              # rostered, no game
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    with captured_templates(app) as templates:
        data = client.get('/cfb/pick/1').data.decode()

    ledger = _ledger_names(templates)
    assert ledger == {'Bye Team': 'not_playing'}       # only the bye team
    assert 'Not On The Board This Week' in data
    assert 'Not Playing' in data


def test_used_team_off_the_slate_shows_used_in_ledger(app, client):
    """A team already used AND not playing this week shows in the ledger tagged
    'used' — otherwise a used team on a bye would be invisible."""
    user = make_user('p1')
    make_enrollment(user)
    prior = make_week(1)                               # past deadline
    burned = make_team('Burned')
    make_pick(user, prior, burned)                     # used in week 1
    week = make_week(2, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('OnBoard A'), make_team('OnBoard B'), spread=-3.0)
    db.session.commit()                                # Burned has no week-2 game
    _login(client, user)

    with captured_templates(app) as templates:
        client.get('/cfb/pick/2')

    assert _ledger_names(templates)['Burned'] == 'used'


def test_board_plus_ledger_account_for_every_pool_team(app, client):
    """Board teams + ledger teams == the whole roster, with no overlap."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    a, b = make_team('A'), make_team('B')
    make_game(week, a, b, spread=-7.0)
    make_team('C')                                     # not playing
    make_team('D')                                     # not playing
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    with captured_templates(app) as templates:
        client.get('/cfb/pick/1')
    ctx = next(c for t, c in templates if t.name == 'cfb/pick.html')

    from games.cfb.models import CfbTeam
    on_board = {g.home_team_id for g in ctx['games']} | {
        g.away_team_id for g in ctx['games']}
    ledger_ids = {e['team'].id for e in ctx['pool_ledger']}
    all_ids = {t.id for t in CfbTeam.query.all()}
    assert on_board.isdisjoint(ledger_ids)             # no team counted twice
    assert on_board | ledger_ids == all_ids            # everyone accounted for
    assert {e['team'].name for e in ctx['pool_ledger']} == {'C', 'D'}


# ── State legend: phase-aware key, no favorite split before lines lock ─────

def test_legend_omits_favorite_split_in_preview(app, client):
    """Before lines lock there is no spread, so the legend must not claim a
    16.5+ split it cannot compute — it shows On The Slate / Used / Not Playing."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('Notre Dame'), make_team('Wisconsin'))  # no line
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/1').data.decode()

    assert 'cfb-pick-legend' in data
    assert 'cfb-legend-label">On The Slate</span>' in data
    assert '16.5+ Fav' not in data                     # no favorite split yet


def test_legend_shows_live_states_once_lines_post(app, client):
    """A posted spread lights up the full legend, including the Open swatch."""
    week = make_week(1, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('Open A'), make_team('Open B'), spread=-3.0)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/1').data.decode()

    assert 'cfb-legend-label">Open</span>' in data
    assert 'cfb-legend-label">16.5+ Fav</span>' in data


def test_out_reason_labels_render_for_each_state(app, client):
    """The reason taxonomy stays distinct on the board: each team's OWN chip
    carries its reason (Used / 16.5+ Fav / No Line), never a bare 'Unavailable'.
    Asserting per team-chip (not page-wide) so a legend label can't pass it."""
    user = make_user('p1')
    make_enrollment(user)
    prior = make_week(1)                               # past deadline
    used = make_team('UsedTeam')
    make_pick(user, prior, used)
    week = make_week(2, deadline=FUTURE_DEADLINE)
    make_game(week, make_team('BigFav'), make_team('OkDog'), spread=-20.5)  # 16.5+
    make_game(week, used, make_team('UsedOpp'), spread=-3.0)                # Used
    make_game(week, make_team('NoLineH'), make_team('NoLineA'))             # No Line
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/pick/2').data.decode()

    assert _chip_reason(data, 'BigFav') == '16.5+ Fav'
    assert _chip_reason(data, 'UsedTeam') == 'Used'
    assert _chip_reason(data, 'NoLineH') == 'No Line'


def test_cfp_eliminated_team_shows_cfp_out_on_board_and_ledger(app, client):
    """In a playoff week, a CFP-eliminated team reads 'CFP Out' both on the
    board (when it has a game) and in the ledger (when it doesn't) — not the
    generic 'Not Playing' the ledger would otherwise give an off-slate team."""
    user = make_user('p1')
    make_enrollment(user)
    # A completed prior playoff week where two teams lose -> CFP-eliminated.
    pw1 = make_week(16, is_playoff=True)               # past deadline, decided
    elim_board = make_team('Elim On Board')
    elim_ledger = make_team('Elim Off Board')
    make_game(pw1, make_team('Winner A'), elim_board, spread=-3.0, winner='home')
    make_game(pw1, make_team('Winner B'), elim_ledger, spread=-3.0, winner='home')
    # Active playoff week: elim_board has a game, elim_ledger does not.
    pw2 = make_week(17, deadline=FUTURE_DEADLINE, is_playoff=True, is_active=True)
    make_game(pw2, make_team('Still Alive'), elim_board, spread=-3.0)
    db.session.commit()
    _login(client, user)

    with captured_templates(app) as templates:
        data = client.get('/cfb/pick/17').data.decode()

    assert _chip_reason(data, 'Elim On Board') == 'CFP Out'         # board row
    assert _ledger_names(templates)['Elim Off Board'] == 'cfp_out'  # ledger tag
    assert 'CFP Out' in data                                        # ledger group renders


# ── Sub-nav "Pick" pill: reachable only when a pick is actually possible ───

def test_pick_pill_shows_for_active_pickable_week(app, client):
    """An enrolled, non-eliminated member with an active, still-open week gets a
    Pick pill in the CFB sub-nav pointing at that week's board."""
    make_week(1, deadline=FUTURE_DEADLINE, is_active=True)
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/').data.decode()

    assert 'href="/cfb/pick/1">Pick</a>' in data


def test_pick_pill_hidden_for_eliminated_member(app, client):
    """An eliminated member can't pick, so the pill is absent."""
    make_week(1, deadline=FUTURE_DEADLINE, is_active=True)
    user = make_user('p1')
    make_enrollment(user, lives=0, eliminated=True)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/').data.decode()

    assert '>Pick</a>' not in data


def test_pick_pill_hidden_when_active_week_deadline_passed(app, client):
    """A past-deadline active week is not pickable, so the pill is absent
    (it would only bounce back to the index)."""
    make_week(1, is_active=True)                        # default PAST_DEADLINE
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    data = client.get('/cfb/').data.decode()

    assert '>Pick</a>' not in data
