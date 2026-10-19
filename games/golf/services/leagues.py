"""The Pay Sheet's leagues (ADR-075): the seed and the reads.

A league is a row in ``golf_league``. Production's rows were written by
migration 32cd68a3e8ea. ``seed_leagues`` creates any league in
``constants.LEAGUE_SEED`` that is missing (a ``create_all`` database: the
tests), the penalty from ``models.PENALTY_PER_INCIDENT``. A league already on
file is left as it stands: the row is the source of truth for its name, fee
and penalty.
"""
from sqlalchemy import select

from extensions import db
from games.golf.constants import LEAGUE_SEED
from games.golf.models import PENALTY_PER_INCIDENT, GolfLeague


def seed_leagues() -> list[GolfLeague]:
    """Create every seeded league not yet on file (idempotent by slug); commits."""
    on_file = set(db.session.scalars(select(GolfLeague.slug)))
    for slug, name, ordinal, entry_fee in LEAGUE_SEED:
        if slug not in on_file:
            db.session.add(GolfLeague(
                slug=slug, name=name, ordinal=ordinal, entry_fee=entry_fee,
                penalty_per_incident=PENALTY_PER_INCIDENT,
            ))
    db.session.commit()
    return leagues()


def leagues() -> list[GolfLeague]:
    """Every league, house league first."""
    return list(db.session.scalars(select(GolfLeague).order_by(GolfLeague.ordinal)))


def league_by_slug(slug: str) -> GolfLeague | None:
    return db.session.scalar(select(GolfLeague).where(GolfLeague.slug == slug))


def house_league() -> GolfLeague:
    """The house league (ordinal 1, Handicap); its absence is a loud error."""
    return db.session.execute(select(GolfLeague).where(GolfLeague.ordinal == 1)).scalar_one()
