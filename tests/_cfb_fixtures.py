"""Shared CFB Survivor test data helpers — used by the lives-pipeline
tests (tests/test_cfb_results.py) and future CFB suites.

Naming convention matches tests/_worldcup_fixtures.py — the leading
underscore signals "test helper, not a pytest discovery file."
These are plain functions, not pytest fixtures (each test file owns
its own ``app`` fixture; helpers seed data inside it).

Datetime column contract (implicit in games/cfb): CfbWeek
``start_date``/``deadline`` and CfbGame ``game_time`` hold naive
pool-timezone wall clock; ``created_at`` columns hold naive UTC.
"""
from datetime import datetime, timedelta

from extensions import db
from games.cfb.models import CfbEnrollment, CfbGame, CfbPick, CfbTeam, CfbWeek
from models.user import User

SEASON = 2026

# Naive pool-tz wall clock, safely in the past relative to any test run.
PAST_DEADLINE = datetime(2026, 1, 3, 11, 0)


def make_user(name, *, is_admin=False):
    """Create a User with a hashed password (and optional platform admin)."""
    u = User(
        username=name,
        email=f'{name}@test.com',
        is_admin=is_admin,
    )
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    return u


def make_enrollment(user, *, lives=2, eliminated=False, season=SEASON,
                    display_name=None):
    """Create a CfbEnrollment with the given lives/elimination state."""
    e = CfbEnrollment(
        user_id=user.id,
        season_year=season,
        lives_remaining=lives,
        is_eliminated=eliminated,
        display_name=display_name,
    )
    db.session.add(e)
    db.session.flush()
    return e


def make_team(name):
    """Create a CfbTeam by name."""
    t = CfbTeam(name=name)
    db.session.add(t)
    db.session.flush()
    return t


def make_week(number=1, *, deadline=None, is_playoff=False, is_active=False,
              is_complete=False):
    """Create a CfbWeek with a past deadline by default."""
    w = CfbWeek(
        week_number=number,
        start_date=(deadline or PAST_DEADLINE) - timedelta(days=2),
        deadline=deadline or PAST_DEADLINE,
        is_active=is_active,
        is_complete=is_complete,
        is_playoff_week=is_playoff,
    )
    db.session.add(w)
    db.session.flush()
    return w


def make_game(week, home, away, *, spread=None, winner=None, no_contest=False):
    """Create a game. ``winner`` is 'home', 'away', or None (undecided)."""
    g = CfbGame(
        week_id=week.id,
        home_team_id=home.id,
        away_team_id=away.id,
        home_team_spread=spread,
        game_time=week.deadline,
        home_team_won={'home': True, 'away': False}.get(winner),
        is_no_contest=no_contest,
    )
    db.session.add(g)
    db.session.flush()
    return g


def make_pick(user, week, team, *, created_at=None, is_correct=None):
    """Create a CfbPick for the user/week/team triple.

    ``created_at`` is naive UTC per the column contract; None keeps the
    model default (real now).
    """
    p = CfbPick(user_id=user.id, week_id=week.id, team_id=team.id,
                is_correct=is_correct)
    if created_at is not None:
        p.created_at = created_at
    db.session.add(p)
    db.session.flush()
    return p
