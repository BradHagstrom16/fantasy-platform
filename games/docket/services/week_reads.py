"""
The Docket — Season-scoped week reads (ADR-069)
===============================================
A season is a column: ``DocketWeek.season_year``. Week numbers restart every
season, so a read by number, or over every week, spans every season ever
played. Every such read in games/docket goes through this module (the only
file ``tests/test_season_scoping.py``'s source lock allows to touch
``DocketWeek.query`` / ``select(DocketWeek)`` / ``filter_by(week_number=)``);
picks, games, predictions and results are scoped by their week.

Every helper takes ``season_year`` (default ``SEASON_YEAR``, the season being
played). The time-window reads (``week_containing`` / ``next_week_after``)
need no season: weeks of different seasons cover disjoint instants.
"""
from sqlalchemy import select

from extensions import db
from games.docket.models import DocketGame, DocketWeek
from games.docket.services.weeks import SEASON_YEAR


def week_query(season_year=SEASON_YEAR):
    """The season's weeks as a select, for callers that filter further."""
    return select(DocketWeek).filter_by(season_year=season_year)


def season_weeks(season_year=SEASON_YEAR):
    """Every week of the season, by number."""
    return db.session.scalars(
        week_query(season_year).order_by(DocketWeek.week_number)).all()


def week_by_number(week_number, season_year=SEASON_YEAR):
    """The season's week ``week_number``, or None."""
    return db.session.scalar(week_query(season_year).filter_by(week_number=week_number))


def weeks_by_numbers(week_numbers, season_year=SEASON_YEAR):
    """The season's weeks with these numbers, by number."""
    return db.session.scalars(
        week_query(season_year)
        .filter(DocketWeek.week_number.in_(list(week_numbers)))
        .order_by(DocketWeek.week_number)).all()


def posted_week_numbers(season_year=SEASON_YEAR):
    """The season's week numbers that hold at least one game, ascending."""
    return db.session.scalars(
        select(DocketWeek.week_number)
        .join(DocketGame, DocketGame.week_id == DocketWeek.id)
        .filter(DocketWeek.season_year == season_year)
        .distinct().order_by(DocketWeek.week_number)).all()


def week_containing(now):
    """The week whose half-open [start_at, end_at) holds naive-UTC ``now``."""
    return db.session.scalar(
        select(DocketWeek).filter(DocketWeek.start_at <= now, DocketWeek.end_at > now))


def next_week_after(now):
    """The first week starting after naive-UTC ``now``, or None."""
    return db.session.scalars(
        select(DocketWeek).filter(DocketWeek.start_at > now)
        .order_by(DocketWeek.start_at)).first()
