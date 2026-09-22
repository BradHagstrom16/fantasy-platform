"""The Docket — opening a week (Club Desk step 3, eng review 2A).

The Tuesday open used to live inside ``games/docket/cli.py::_run_import``:
import the slates, apply the default-tiebreaker rule, check the designation,
announce "picks are open". That is the one job no other path recovers
(``docket-lines --scheduled`` soft-exits on week-not-imported), so the desk's
Tuesday Paper (``docs/designs/unified-email.md`` step 5) needs to run it
without the CLI and, crucially, without the announcement: the Paper carries
the announcement itself and latches ``picks_open_notified`` after its own
send. ``announce=`` is that seam. With the default ``True`` this is exactly
the legacy behavior, byte for byte (``tests/test_club_desk_step3_regression
.py``); the CLI wrapper prints the same lines it always printed.

No ``click`` here and no ``SystemExit``: the service reports, the CLI
disposes (the partial-import exit stays in ``_check_sync_status``).
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from games.docket.models import DocketEnrollment, DocketGame, DocketWeek
from games.docket.services.deadline_pass import check_designation
from games.docket.services.importer import import_week
from games.docket.services.notifications import notify_picks_open
from games.docket.services.tiebreaker_rule import apply_default_tiebreaker
from games.docket.services.weeks import SEASON_YEAR


@dataclass(frozen=True, slots=True)
class OpenResult:
    """What one open run did.

    ``summary`` is the importer's dict (its ``status`` drives the CLI exit
    code). ``week`` is None when the row still does not exist after the
    import (a hard failure before the week was created). ``rule_outcome``
    is ``apply_default_tiebreaker``'s dict, ``problems`` are
    ``check_designation``'s lines, ``announced`` is how many picks-open
    letters were accepted (0 when ``announce=False``, when the week was
    already announced, or when nothing qualified).
    """
    summary: dict
    week: DocketWeek | None
    rule_outcome: dict | None
    problems: tuple[str, ...]
    announced: int


def announce_picks_open(week, summary) -> int:
    """Mail the roster the "Picks Are Open" announcement — once, when the week
    first has games. Latched on the week so a later gap-fill import stays
    silent; the latch is consumed only on a successful send, so a mail outage
    retries on the next run. Skipped on a hard/partial import failure and on an
    empty week (has-games gates it), so a launch email never fires on nothing.
    Returns how many letters were accepted.
    """
    if (week.picks_open_notified
            or summary.get('status') in ('error', 'partial')):
        return 0
    has_games = db.session.scalar(
        select(DocketGame.id).filter_by(week_id=week.id).limit(1)) is not None
    if not has_games:
        return 0
    # (user, enrollment) pairs: the enrollment is what lets the announcement
    # carry the "Settle the tab" paragraph to unpaid members only.
    enrollments = db.session.scalars(
        select(DocketEnrollment)
        .filter_by(season_year=SEASON_YEAR)
        .options(joinedload(DocketEnrollment.user))
        .order_by(DocketEnrollment.user_id)).all()
    recipients = [(e.user, e) for e in enrollments if e.user is not None]
    sent = notify_picks_open(week, recipients)
    if sent > 0:
        week.picks_open_notified = True
        db.session.commit()
    return sent


def open_week(week_number, *, force_odds=False, announce=True,
              importer=import_week) -> OpenResult:
    """Import the week's slates, designate the tiebreaker by rule, and
    (unless ``announce=False``) mail the roster that picks are open.

    ``importer`` is the slate importer, injected so the CLI can pass its own
    module-level ``import_week`` name: the existing tests patch
    ``games.docket.cli.import_week``, and keeping that seam where they patch
    it is what lets this extraction ship with every test unchanged.
    """
    summary = importer(week_number, force_odds=force_odds)
    week = db.session.scalar(
        select(DocketWeek).filter_by(week_number=week_number))
    if week is None:
        return OpenResult(summary=summary, week=None, rule_outcome=None,
                          problems=(), announced=0)
    # The rule runs before the CLI's partial/error exit so a failed CFB half
    # on an NFL week still leaves the tiebreaker designated; the exit code
    # stays the import's (a missing designation is a WARNING here and exit 1
    # only at the deadline pass).
    rule_outcome = apply_default_tiebreaker(week)
    problems = tuple(check_designation(week))
    announced = announce_picks_open(week, summary) if announce else 0
    return OpenResult(summary=summary, week=week, rule_outcome=rule_outcome,
                      problems=problems, announced=announced)
