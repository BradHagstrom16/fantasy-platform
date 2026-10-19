"""The Pay Sheet enrollment service — registry integration point."""

from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import contains_eager

from extensions import db
from games.golf.models import GolfEnrollment, GolfLeague
from games.golf.services.leagues import house_league


def _season_year() -> int:
    return current_app.config['SEASON_YEAR']


def enrollments_for(user_id: int) -> list[GolfEnrollment]:
    """The user's current-season lines, house league first, each with its
    league loaded (one query)."""
    return list(db.session.scalars(
        select(GolfEnrollment)
        .join(GolfLeague, GolfEnrollment.league_id == GolfLeague.id)
        .options(contains_eager(GolfEnrollment.league))
        .where(GolfEnrollment.user_id == user_id,
               GolfEnrollment.season_year == _season_year())
        .order_by(GolfLeague.ordinal)
    ))


def get_enrollment(user_id: int, league: GolfLeague | None = None) -> GolfEnrollment | None:
    """The user's current-season line in ``league``, or None.

    No league is the registry's one-argument call: the member's
    lowest-ordinal line this season.
    """
    if league is None:
        lines = enrollments_for(user_id)
        return lines[0] if lines else None
    return db.session.scalar(select(GolfEnrollment).where(
        GolfEnrollment.user_id == user_id,
        GolfEnrollment.league_id == league.id,
        GolfEnrollment.season_year == _season_year(),
    ))


def house_enrollment(user_id: int) -> GolfEnrollment | None:
    """The user's current-season line in the house league, or None: the
    already-seated check that pairs with ``admin_enroll`` on the platform's
    enrollments page (a member of the other league alone is not seated)."""
    return get_enrollment(user_id, house_league())


def admin_enroll(user_id: int, league: GolfLeague | None = None) -> GolfEnrollment:
    """Idempotently enroll a user in a league for the current season
    (no league seats the house league)."""
    league = league or house_league()
    existing = get_enrollment(user_id, league)
    if existing is not None:
        return existing
    enrollment = GolfEnrollment(user_id=user_id, league_id=league.id,
                                season_year=_season_year())
    db.session.add(enrollment)
    db.session.commit()
    return enrollment
