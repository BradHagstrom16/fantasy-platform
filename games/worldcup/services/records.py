"""The World Cup's board for the club's permanent record (ADR-068).

One read-only function, the registry's ``season_finishes`` seam. Reuses the
frozen archive's query shape (services/lounge.py::archive_summary: every
enrollment of the season by total_score, then id) and the platform's
competition rank. Nothing here writes, and no existing WC module changes;
this file is the second sanctioned post-archive addition
(docs/worldcup-archive-invariants.md).
"""
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment
from games.worldcup.services.state import worldcup_state
from models.records import FinishDraft, SeasonNotClosed


def season_finishes(season_year: int) -> list[FinishDraft]:
    """Every enrolled member's finish, place 1 first, once the Final is decided."""
    if season_year != SEASON_YEAR or worldcup_state() != 'post':
        raise SeasonNotClosed(f'World Cup {season_year} is not a decided tournament')
    enrollments = db.session.scalars(
        select(WorldCupEnrollment)
        .filter_by(season_year=season_year)
        .options(joinedload(WorldCupEnrollment.user))
        .order_by(WorldCupEnrollment.total_score.desc(), WorldCupEnrollment.id.asc())
    ).all()
    return [
        FinishDraft(
            user_id=e.user_id,
            name=e.get_display_name(),
            place=1 + sum(1 for o in enrollments if o.total_score > e.total_score),
            outcome=None,
            detail=f'{e.total_score:.1f} pts',
        )
        for e in enrollments
    ]
