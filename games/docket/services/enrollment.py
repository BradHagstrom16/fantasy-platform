"""The Docket enrollment service — registry integration point.

Season identity comes from ``games.docket.services.weeks.SEASON_YEAR`` (the
week-math SSoT), not a config key: the docket season is defined by its
week boundaries, and a second knob could silently disagree with them.
"""

from sqlalchemy import select

from extensions import db
from games.docket.models import DocketEnrollment
from games.docket.services.weeks import SEASON_YEAR


def get_enrollment(user_id: int) -> DocketEnrollment | None:
    """Return the user's current-season Docket enrollment, or None."""
    return DocketEnrollment.query.filter_by(
        user_id=user_id, season_year=SEASON_YEAR
    ).first()


def roster_user_ids(season_year: int = SEASON_YEAR) -> list[int]:
    """Every enrolled user id for the season, ascending.

    THE population for the season's write passes: the deadline pass gives
    each of these players the D5 autopick package, and the grading pass
    grades all of them so a no-input week costs 0 points and the week's
    default tiebreaker error rather than being skipped (a late joiner buys
    no advantage on key 3 — Grading Clarifications).
    """
    return sorted(db.session.scalars(
        select(DocketEnrollment.user_id).filter_by(season_year=season_year)))


def admin_enroll(user_id: int) -> DocketEnrollment:
    """Idempotently enroll a user in the current Docket season."""
    existing = get_enrollment(user_id)
    if existing is not None:
        return existing
    enrollment = DocketEnrollment(user_id=user_id, season_year=SEASON_YEAR)
    db.session.add(enrollment)
    db.session.commit()
    return enrollment
