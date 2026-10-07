"""The Pay Sheet — shared season reads.

The loaders the room's pages and the lounge share: a season's enrollees, a
season's tournaments, a tournament's picks and results, the next pick, and
whether a season is final. Pure reads over the golf tables with their
relationships loaded up front (no query per row; the route query-count locks
in ``tests/test_golf_cleanup.py`` stand on that).

Lives in a service so the lounge (``services/lounge.py``) never imports the
blueprint: ``games/registry.py`` imports the lounge at boot.
"""
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfTournament,
    GolfTournamentResult,
)


def season_enrollments(season_year):
    """A season's enrollees with their users loaded (no query per row)."""
    return db.session.scalars(
        select(GolfEnrollment)
        .options(joinedload(GolfEnrollment.user))
        .filter_by(season_year=season_year)
    ).all()


def tournament_picks(tournament_id):
    """A tournament's picks with the member and both golfers loaded."""
    return db.session.scalars(
        select(GolfPick)
        .options(
            joinedload(GolfPick.user),
            joinedload(GolfPick.primary_player),
            joinedload(GolfPick.backup_player),
        )
        .filter_by(tournament_id=tournament_id)
    ).all()


def tournament_results(tournament_id):
    return db.session.scalars(
        select(GolfTournamentResult).filter_by(tournament_id=tournament_id)
    ).all()


def season_tournaments(season_year):
    return db.session.scalars(
        select(GolfTournament)
        .filter_by(season_year=season_year)
        .order_by(GolfTournament.start_date)
    ).all()


def next_tournament(tournaments):
    """The next pick: the first tournament still before its lock.

    Status decides only for one with no deadline yet, which the lock reads as
    open forever (a field sync that never ran leaves a played week without one).
    """
    return next(
        (t for t in tournaments
         if (not t.is_deadline_passed() if t.pick_deadline else t.status == 'upcoming')),
        None,
    )


def season_final(tournaments) -> bool:
    """Whether a season is banked through: at least one tournament, every one
    with official results. A season with no schedule is not final, it is pre."""
    return bool(tournaments) and all(t.results_finalized for t in tournaments)
