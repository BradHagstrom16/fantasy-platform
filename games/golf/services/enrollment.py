"""Golf Pick 'Em enrollment service — registry integration point."""
from typing import Optional

from flask import current_app

from extensions import db
from games.golf.models import GolfEnrollment


def _season_year() -> int:
    return current_app.config['SEASON_YEAR']


def get_enrollment(user_id: int) -> Optional[GolfEnrollment]:
    """Return the user's current-season Golf enrollment, or None."""
    return GolfEnrollment.query.filter_by(
        user_id=user_id, season_year=_season_year()
    ).first()


def admin_enroll(user_id: int) -> GolfEnrollment:
    """Idempotently enroll a user in the current Golf season."""
    existing = get_enrollment(user_id)
    if existing is not None:
        return existing
    enrollment = GolfEnrollment(user_id=user_id, season_year=_season_year())
    db.session.add(enrollment)
    db.session.commit()
    return enrollment
