"""CFB Survivor enrollment service — registry integration point."""

from flask import current_app

from extensions import db
from games.cfb.models import CfbEnrollment


def _season_year() -> int:
    return current_app.config.get('CFB_SEASON_YEAR', 2026)


def get_enrollment(user_id: int) -> CfbEnrollment | None:
    """Return the user's current-season CFB enrollment, or None."""
    return CfbEnrollment.query.filter_by(
        user_id=user_id, season_year=_season_year()
    ).first()


def admin_enroll(user_id: int) -> CfbEnrollment:
    """Idempotently enroll a user in the current CFB season."""
    existing = get_enrollment(user_id)
    if existing is not None:
        return existing
    enrollment = CfbEnrollment(user_id=user_id, season_year=_season_year())
    db.session.add(enrollment)
    db.session.commit()
    return enrollment
