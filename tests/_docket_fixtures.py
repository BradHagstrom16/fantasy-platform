"""Shared Docket test fixtures (tests/_cfb_fixtures.py pattern).

Builders flush (not commit) so tests control transaction boundaries.
Week rows are built through games/docket/services/weeks.py so every test
exercises the real CT→UTC boundary math. Time is driven via the
DOCKET_FAKE_NOW seam (naive ISO ⇒ UTC); the canonical conftest app fixture
pins ENVIRONMENT=testing so the seam is always live.
"""
import itertools
from datetime import datetime

from extensions import db
from games.docket.models import DocketEnrollment, DocketGame, DocketWeek
from games.docket.services.weeks import (
    SEASON_YEAR,
    deadline_utc,
    week_bounds_utc,
)
from games.docket.utils import to_naive_utc
from models.user import User

_event_ids = itertools.count(1)

# Week 1 anchors (naive UTC): boundary Tue Sep 1 06:00 CT, deadline
# Sat Sep 5 11:00 CT.
WEEK1_DEADLINE_UTC = datetime(2026, 9, 5, 16, 0)
IN_WEEK1 = '2026-09-02T12:00:00'


def make_user(username='player', is_admin=False):
    user = User(username=username, email=f'{username}@test.com',
                is_admin=is_admin)
    user.set_password('pw')
    db.session.add(user)
    db.session.flush()
    return user


def make_enrollment(user, **kwargs):
    # ``display_name`` is the member's one platform name (ADR-057); the
    # enrollment no longer carries its own, so it lands on the user.
    display_name = kwargs.pop('display_name', None)
    if display_name is not None:
        user.display_name = display_name
    enrollment = DocketEnrollment(
        user_id=user.id, season_year=SEASON_YEAR, **kwargs)
    db.session.add(enrollment)
    db.session.flush()
    return enrollment


def make_week(week_number=1):
    start, end = week_bounds_utc(week_number)
    week = DocketWeek(
        week_number=week_number,
        start_at=to_naive_utc(start),
        end_at=to_naive_utc(end),
        deadline_at=to_naive_utc(deadline_utc(week_number)),
    )
    db.session.add(week)
    db.session.flush()
    return week


def make_game(week, *, kickoff, home='Home Team', away='Away Team',
              sport='americanfootball_ncaaf',
              home_spread=-3.5, spread_book='draftkings',
              total=51.5, total_book='draftkings', created_at=None):
    """A game with both markets locked by default; pass None to unpost one.

    ``kickoff`` is naive UTC (the D6 column contract). ``created_at`` is
    pinned to the Tuesday line freeze rather than left to the model's
    real-wall-clock default: the deadline pass compares it against the
    week deadline to spot a late arrival, so a real ``now()`` would silently
    reclassify every seeded game once the calendar passes Sep 5 2026.
    """
    locked_at = datetime(2026, 9, 1, 11, 0)
    game = DocketGame(
        created_at=created_at if created_at is not None else locked_at,
        week_id=week.id,
        sport=sport,
        api_event_id=f'test-ev-{next(_event_ids)}',
        home_team=home,
        away_team=away,
        kickoff=kickoff,
        home_spread=home_spread,
        spread_book=spread_book if home_spread is not None else None,
        spread_locked_at=locked_at if home_spread is not None else None,
        total_points=total,
        total_book=total_book if total is not None else None,
        total_locked_at=locked_at if total is not None else None,
    )
    db.session.add(game)
    db.session.flush()
    return game


def login(client, user):
    """Seed the session with the user's auth_id (never str(user.id))."""
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def at(monkeypatch, iso):
    """Drive the docket clock: naive ISO ⇒ UTC via DOCKET_FAKE_NOW.

    ENVIRONMENT=testing rides along (the time-seam convention): the fake-now
    seam only activates in dev/testing, and the outside-process env var does
    not propagate when a test file runs without the ENVIRONMENT prefix."""
    monkeypatch.setenv('ENVIRONMENT', 'testing')
    monkeypatch.setenv('DOCKET_FAKE_NOW', iso)
