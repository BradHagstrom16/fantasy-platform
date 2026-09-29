"""
CFB Survivor Pool — Season-scoped week and team reads (ADR-069)
=================================================================
A season is a column: ``CfbWeek.season_year`` and ``CfbTeam.season_year``.
Week numbers restart every season and the same school is a new team row
each season, so a read over the whole table spans every season ever
played. Every week and team read in games/cfb goes through this module
(the only file ``tests/test_season_scoping.py``'s source lock allows to
touch ``CfbWeek.query`` / ``CfbTeam.query``); picks and outcomes are scoped
by joining their week.

Each helper takes ``season_year``; None means the configured season
(``CFB_SEASON_YEAR``).
"""
from flask import current_app

from games.cfb.models import CfbTeam, CfbWeek


def current_season() -> int:
    """The season the pool is playing (``CFB_SEASON_YEAR``)."""
    return current_app.config['CFB_SEASON_YEAR']


def _season(season_year):
    return current_season() if season_year is None else season_year


# ---------------------------------------------------------------------------
# Weeks
# ---------------------------------------------------------------------------

def week_query(season_year=None):
    """The season's weeks as a query, for callers that filter or count."""
    return CfbWeek.query.filter_by(season_year=_season(season_year))


def season_weeks(season_year=None):
    """Every week of the season, by number."""
    return week_query(season_year).order_by(CfbWeek.week_number).all()


def week_by_number(number, season_year=None):
    """The season's week ``number``, or None."""
    return week_query(season_year).filter_by(week_number=number).first()


def active_week(season_year=None):
    """The season's active week, or None."""
    return week_query(season_year).filter_by(is_active=True).first()


def complete_weeks(season_year=None):
    """The season's complete weeks, by number."""
    return (week_query(season_year).filter_by(is_complete=True)
            .order_by(CfbWeek.week_number).all())


def incomplete_weeks(season_year=None):
    """The season's weeks not yet complete, by number."""
    return (week_query(season_year).filter_by(is_complete=False)
            .order_by(CfbWeek.week_number).all())


def latest_week(season_year=None):
    """The season's highest-numbered week, or None (setup numbers the next
    week from it)."""
    return week_query(season_year).order_by(CfbWeek.week_number.desc()).first()


def deactivate_all():
    """Clear ``is_active`` on every week of every season: only one week is
    active at a time, and a past season's week never is."""
    CfbWeek.query.update({'is_active': False})


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

def team_query(season_year=None):
    """The season's pool as a query."""
    return CfbTeam.query.filter_by(season_year=_season(season_year))


def season_teams(season_year=None):
    """The season's pool, by name."""
    return team_query(season_year).order_by(CfbTeam.name).all()
