"""The Docket enrollment service — registry integration point.

Season identity comes from ``games.docket.services.weeks.SEASON_YEAR`` (the
week-math SSoT), not a config key: the docket season is defined by its
week boundaries, and a second knob could silently disagree with them.
"""

from sqlalchemy import or_, select

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


def roster_user_ids_as_of(instant, season_year: int = SEASON_YEAR) -> list[int]:
    """Every user enrolled at or before ``instant`` (naive UTC), ascending.

    THE population for grading a week that has already closed. Grading a past
    week against the LIVE roster hands a later joiner an empty input, which
    the engine completes into a full 8-slot autopick package that scores real
    points — so a Week-5 joiner would collect points for Weeks 1-4, but only
    if an operator happened to run `flask docket recalc` with no argument.
    That makes a player's season total depend on ops timing, and contradicts
    the season pass's own rule: a member absent from a week takes 0 points, 0
    wins, and that week's default error.

    Pass the week's ``deadline_at``. Both it and ``created_at`` are naive UTC
    (D6), so they compare directly. The CURRENT week keeps the live roster
    (roster_user_ids): everyone enrolled by its deadline is exactly everyone
    enrolled, and the deadline pass has already dealt them their picks.

    A NULL ``created_at`` counts as enrolled: it cannot prove a late join, and
    wrongly excluding a real member from a graded week is the worse error.
    """
    return sorted(db.session.scalars(
        select(DocketEnrollment.user_id)
        .filter(DocketEnrollment.season_year == season_year,
                or_(DocketEnrollment.created_at.is_(None),
                    DocketEnrollment.created_at <= instant))))


def admin_enroll(user_id: int) -> DocketEnrollment:
    """Idempotently enroll a user in the current Docket season."""
    existing = get_enrollment(user_id)
    if existing is not None:
        return existing
    enrollment = DocketEnrollment(user_id=user_id, season_year=SEASON_YEAR)
    db.session.add(enrollment)
    db.session.commit()
    return enrollment
