"""CFB CFP date-math + phase locks (pre-launch audit §3 — test hardening).

This file locks the parts of the CFP/date-math surface the audit verified but
that had no direct test, and *characterizes* the one deferred decision so a
future change to it is deliberate:

  - ``_calculate_week_dates`` regular-season cadence (Saturday 11am Central,
    weekly), anchored on ``SEASON_SCHEDULE['week_1_start']``.
  - The §3 deferral: weeks 16-19 (CFP) currently get the SAME rigid Saturday
    cadence even though the real playoff is Thu/Fri quarterfinals and a Monday
    National Championship. Postseason automation is deferred for season one
    (manual weekly setup per the runbook); this lock makes any future
    real-CFP-schedule fix update the test on purpose rather than by surprise.
  - ``get_cfp_eliminated_teams`` (a playoff-week loser is out) and the
    ``make_pick`` route guard that bars picking a CFP-eliminated team.

Phase-scoping itself (DQ-3 week-15 regular pool, the week-16 reset, DQ-7
lifetime cumulative spread) is already locked in tests/test_cfb_used_teams.py —
not duplicated here.

Datetime column contract (see tests/_cfb_fixtures.py): CfbWeek deadline /
CfbGame game_time hold naive pool-tz wall clock; a far-future deadline keeps a
week pickable, a past game_time marks an individual game started.
"""
import dataclasses
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

import pytest
from flask import template_rendered

import games.registry as registry
from extensions import db
from games.cfb.constants import SEASON_SCHEDULE
from games.cfb.models import CfbPick
from games.cfb.services.automation import CHICAGO_TZ, _calculate_week_dates
from games.cfb.utils import get_cfp_eliminated_teams
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_team,
    make_user,
    make_week,
)

# Naive pool-tz wall clock — a far-future deadline keeps the playoff week
# pickable for the route-level CFP-eliminated guard test.
FUTURE_DEADLINE = datetime(2099, 1, 1, 11, 0)


def _open_cfb_games():
    """Registry list with CFB flipped to 'open' (entries are frozen)."""
    return [
        dataclasses.replace(e, status='open') if e.slug == 'cfb' else e
        for e in registry.GAMES
    ]


@pytest.fixture(autouse=True)
def cfb_open():
    """Flip CFB to 'open' so an enrolled non-admin can reach /cfb/pick."""
    with patch.object(registry, 'GAMES', _open_cfb_games()):
        yield


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


@contextmanager
def captured_templates(app):
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)


def _eligible_names(templates):
    ctx = next(c for t, c in templates if t.name == 'cfb/pick.html')
    return {team.name for team in ctx['eligible_teams']}


# ── _calculate_week_dates — regular-season cadence ────────────────────────

def test_week_1_dates_are_thursday_start_saturday_11am_deadline(app):
    """Week 1 anchors on week_1_start (Thu 2026-09-03); the deadline is that
    week's Saturday at 11:00 Central — the cadence every later week inherits."""
    anchor = datetime.strptime(SEASON_SCHEDULE['week_1_start'], '%Y-%m-%d')
    start, deadline = _calculate_week_dates(1)

    assert start.replace(tzinfo=None) == anchor          # Thu 2026-09-03
    assert start.weekday() == 3                           # Thursday
    assert (deadline.replace(tzinfo=None)
            == datetime(2026, 9, 5, 11, 0))               # Sat 11:00
    assert deadline.weekday() == 5                        # Saturday
    assert deadline.tzinfo == CHICAGO_TZ                  # pool-tz aware


def test_regular_season_weeks_are_weekly_saturday_11am(app):
    """Every regular-season week's deadline is a Saturday at 11:00, spaced
    exactly 7 wall-clock days apart. Compared as naive wall clock so the
    America/Chicago DST fall-back (early November) doesn't read as a drift."""
    from datetime import timedelta

    last = SEASON_SCHEDULE['regular_season_weeks']  # 14
    prev = None
    for n in range(1, last + 1):
        _, deadline = _calculate_week_dates(n)
        assert deadline.weekday() == 5 and deadline.hour == 11
        if prev is not None:
            assert (deadline.replace(tzinfo=None)
                    - prev.replace(tzinfo=None)) == timedelta(days=7)
        prev = deadline


def test_cfp_weeks_use_the_same_rigid_saturday_cadence_audit_s3_deferral(app):
    """Audit §3 deferral, characterized.

    CFP postseason automation is DEFERRED for season one: real CFP rounds are
    Thu/Fri quarterfinals around Jan 1 and a Monday National Championship, but
    _calculate_week_dates still hands weeks 16-19 the rigid Saturday-11am weekly
    cadence. That mismatch is why those weeks are set up MANUALLY per the
    runbook. This test pins the current (deferred) behavior on purpose — if a
    future change teaches the schedule the real CFP dates, update this lock
    deliberately rather than discovering the break in production.
    """
    from datetime import timedelta

    prev = None
    for n in (16, 17, 18, 19):
        _, deadline = _calculate_week_dates(n)
        assert deadline.weekday() == 5 and deadline.hour == 11  # rigid Saturday
        if prev is not None:
            assert (deadline.replace(tzinfo=None)
                    - prev.replace(tzinfo=None)) == timedelta(days=7)
        prev = deadline


# ── get_cfp_eliminated_teams — a playoff loser is out ─────────────────────

def test_cfp_eliminated_collects_playoff_losers_only(app):
    """A team that lost a decided playoff game is eliminated; the winner and
    a decided *regular-season* loser are not."""
    cfp = make_week(16, is_playoff=True)
    reg = make_week(3, is_playoff=False)
    winner, cfp_loser = make_team('Winner'), make_team('CfpLoser')
    reg_w, reg_l = make_team('RegWin'), make_team('RegLoss')
    make_game(cfp, winner, cfp_loser, winner='home')   # away (CfpLoser) out
    make_game(reg, reg_w, reg_l, winner='home')        # regular game: ignored
    db.session.commit()

    eliminated = get_cfp_eliminated_teams()

    assert 'CfpLoser' in eliminated
    assert 'Winner' not in eliminated
    assert 'RegLoss' not in eliminated   # regular-season result is not a CFP exit


def test_cfp_eliminated_ignores_undecided_playoff_games(app):
    """An undecided playoff game (home_team_won is None) eliminates nobody."""
    cfp = make_week(16, is_playoff=True)
    a, b = make_team('A'), make_team('B')
    make_game(cfp, a, b, winner=None)   # not yet played
    db.session.commit()

    assert get_cfp_eliminated_teams() == set()


# ── make_pick route guard — can't pick a CFP-eliminated team ──────────────

def test_make_pick_rejects_cfp_eliminated_team_in_playoff_week(app, client):
    """routes.py:479-481 — in a playoff week, a team eliminated in an earlier
    playoff round is barred from selection (no pick stored)."""
    r16 = make_week(16, is_playoff=True)       # past deadline (default)
    winner, gone = make_team('Advancer'), make_team('Bounced')
    make_game(r16, winner, gone, winner='home')   # 'Bounced' lost in R16
    r17 = make_week(17, is_playoff=True, deadline=FUTURE_DEADLINE)
    opp = make_team('NextOpp')
    make_game(r17, gone, opp, spread=-3.0)     # 'Bounced' plays again in R17
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    resp = client.post('/cfb/pick/17',
                       data={'team_id': str(gone.id), 'csrf_token': 'x'},
                       follow_redirects=False)

    assert resp.status_code == 302
    assert '/cfb/pick/17' in resp.headers['Location']    # bounced back
    assert CfbPick.query.filter_by(user_id=user.id, week_id=r17.id).first() is None


def test_cfp_eliminated_team_absent_from_playoff_eligible_list(app, client):
    """GET parity: the eliminated team never appears in eligible_teams for the
    playoff week, so the picker and the POST guard agree.

    The eliminated team is the *away* side so the filter under test is the one
    that skips it directly — the home-team branch's ``continue`` also drops a
    shared game's away team, which is a separate route quirk, not this lock."""
    r16 = make_week(16, is_playoff=True)
    winner, gone = make_team('Advancer'), make_team('Bounced')
    make_game(r16, winner, gone, winner='home')      # 'Bounced' out in R16
    r17 = make_week(17, is_playoff=True, deadline=FUTURE_DEADLINE)
    still_in = make_team('StillIn')
    make_game(r17, still_in, gone, spread=-3.0)      # live home vs eliminated away
    user = make_user('p1')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    with captured_templates(app) as templates:
        client.get('/cfb/pick/17')
    eligible = _eligible_names(templates)

    assert 'Bounced' not in eligible       # eliminated away team filtered out
    assert 'StillIn' in eligible           # its still-alive opponent stays pickable
