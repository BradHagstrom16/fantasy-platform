"""The Pay Sheet's leagues (ADR-075): the seed and the reads.

A league is a row in ``golf_league``. ``seed_leagues`` creates any league in
``constants.LEAGUE_SEED`` that is missing, taking the entry fee from config
``ENTRY_FEE`` and the penalty from ``models.PENALTY_PER_INCIDENT``. A league
already on file is left as it stands: after the seed the row is the source of
truth for its name, fee and penalty.
"""
from flask import current_app
from sqlalchemy import select

from extensions import db
from games.golf.constants import LEAGUE_SEED
from games.golf.models import PENALTY_PER_INCIDENT, GolfLeague


def seed_leagues() -> list[GolfLeague]:
    """Create every seeded league not yet on file (idempotent by slug); commits."""
    on_file = set(db.session.scalars(select(GolfLeague.slug)))
    for slug, name, ordinal in LEAGUE_SEED:
        if slug not in on_file:
            db.session.add(GolfLeague(
                slug=slug, name=name, ordinal=ordinal,
                entry_fee=current_app.config['ENTRY_FEE'],
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
    """The house league (ordinal 1, Handicap)."""
    return db.session.scalar(select(GolfLeague).where(GolfLeague.ordinal == 1))
