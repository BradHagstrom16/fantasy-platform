"""World Cup enrollment service — registry integration point."""
from typing import Optional

from extensions import db
from games.worldcup.models import WorldCupEnrollment
from games.worldcup.constants import SEASON_YEAR


def get_enrollment(user_id: int) -> Optional[WorldCupEnrollment]:
    """Return the user's current-season World Cup enrollment, or None."""
    return WorldCupEnrollment.query.filter_by(
        user_id=user_id, season_year=SEASON_YEAR
    ).first()


def admin_enroll(user_id: int) -> WorldCupEnrollment:
    """Idempotently enroll a user in the current World Cup season."""
    existing = get_enrollment(user_id)
    if existing is not None:
        return existing
    enrollment = WorldCupEnrollment(user_id=user_id, season_year=SEASON_YEAR)
    db.session.add(enrollment)
    db.session.commit()
    return enrollment
