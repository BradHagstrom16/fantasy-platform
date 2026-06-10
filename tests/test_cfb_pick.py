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
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

import pytest
from flask import template_rendered

from app import create_app
from extensions import db
import games.registry as registry
from games.cfb.models import CfbPick
from tests._cfb_fixtures import (
    make_user, make_enrollment, make_team, make_week, make_game, make_pick,
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
    week = make_week(1)  # past deadline
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
