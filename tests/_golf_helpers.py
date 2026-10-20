"""Shared helpers for the golf two-league tests (ADR-075): a member with a
line per league, a per-viewer client, a platform admin, a line lookup and a
season event. Imported by tests/test_golf_leagues.py and
tests/test_golf_payment_nudge.py (the repo's shape beside _registry_helpers.py).
"""
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import select

from extensions import db
from games.golf.models import GolfEnrollment, GolfTournament
from models.user import User


def _user(username):
    user = User(username=username, email=f'{username}@example.com')
    user.set_password('x')
    db.session.add(user)
    db.session.commit()
    return user


def _member(username, *lines, app, admin_in=None, display_name=None):
    """A user with a line in each of ``lines`` this season (``admin_in`` is
    the league whose line carries the commissioner flag); returns the id."""
    user = User(username=username, email=f'{username}@example.com',
                display_name=display_name or username)
    user.set_password('x')
    db.session.add(user)
    db.session.flush()
    for league in lines:
        db.session.add(GolfEnrollment(
            user_id=user.id, league_id=league.id, season_year=app.config['SEASON_YEAR'],
            is_admin=league is admin_in))
    db.session.commit()
    return user.id


@contextmanager
def _viewer(app, user_id=None):
    """A fresh client for one viewer, inside its own app context.

    Flask-Login caches the loaded user on ``g``, and every request under the
    fixture's app context shares that ``g``, so a test that reads as several
    viewers gives each its own context (tests/test_cfb_player_card.py::_page).
    The nested teardown removes its session, which is why callers pass ids.
    """
    client = app.test_client()
    with app.app_context():
        if user_id is not None:
            with client.session_transaction() as sess:
                sess['_user_id'] = db.session.get(User, user_id).auth_id
                sess['_fresh'] = True
        yield client


def _platform_admin(username):
    user = _user(username)
    user.is_admin = True
    db.session.commit()
    return user.id


def _line_of(user_id, league):
    return db.session.scalar(select(GolfEnrollment).where(
        GolfEnrollment.user_id == user_id, GolfEnrollment.league_id == league.id))


def _season_event(app, name, *, status='complete', deadline_in=None):
    """An event in the configured season; ``deadline_in`` puts its lock that far
    ahead in league wall clock (the reminder pass reads it as CT)."""
    from games.golf.utils import GOLF_LEAGUE_TZ
    now = datetime.now(GOLF_LEAGUE_TZ).replace(tzinfo=None)
    deadline = now + deadline_in if deadline_in is not None else now - timedelta(days=4)
    event = GolfTournament(
        api_tourn_id=f'A4-{name}'[:20], name=name, season_year=app.config['SEASON_YEAR'],
        start_date=deadline, end_date=deadline + timedelta(days=3),
        pick_deadline=deadline, purse=10_000_000, status=status,
    )
    db.session.add(event)
    db.session.commit()
    return event
