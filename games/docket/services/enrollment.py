"""The Docket enrollment service — registry integration point.

Season identity comes from ``games.docket.services.weeks.SEASON_YEAR`` (the
week-math SSoT), not a config key: the docket season is defined by its
week boundaries, and a second knob could silently disagree with them.
"""

from extensions import db
from games.docket.models import DocketEnrollment
from games.docket.services.weeks import SEASON_YEAR


def get_enrollment(user_id: int) -> DocketEnrollment | None:
    """Return the user's current-season Docket enrollment, or None."""
    return DocketEnrollment.query.filter_by(
        user_id=user_id, season_year=SEASON_YEAR
    ).first()


def admin_enroll(user_id: int) -> DocketEnrollment:
    """Idempotently enroll a user in the current Docket season."""
    existing = get_enrollment(user_id)
    if existing is not None:
        return existing
    enrollment = DocketEnrollment(user_id=user_id, season_year=SEASON_YEAR)
    db.session.add(enrollment)
    db.session.commit()
    return enrollment
