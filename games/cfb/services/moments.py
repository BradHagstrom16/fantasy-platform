"""
CFB Survivor Pool — the room's terminal moments (ADR-078)
=========================================================
A terminal moment (games/cfb/DESIGN.md §6.14) plays once per member: the
first room view after the state it marks is final, never again. The first
is the member's own elimination, the Observer's Seat: the card their run
ended on steps down to the observer's register. Its record is
``CfbEnrollment.elimination_seen_week``, scoped to the season by the
enrollment, written only by the POST the page sends when the moment starts.
The routes and that POST all read the one rule here.
"""
from sqlalchemy import select

from extensions import db
from games.cfb.models import CfbEnrollment, CfbGame, CfbPick
from games.cfb.services import weeks as week_reads
from games.cfb.services.game_logic import get_elimination_weeks
from games.cfb.utils import deadline_has_passed, make_aware


def run_end_week(enrollment):
    """The week this member's run ended, once that is final; else None.

    Final means the DQ-1 revival can no longer undo it: the week's outcome
    snapshot records the elimination, or, while that week is the only one
    in play, another member is sure to still be standing when it completes
    (a revival needs a whole-pool wipe). Per-game grading puts a member out
    the hour their game goes final, days before a midweek game completes
    the week.
    """
    if enrollment is None or not enrollment.is_eliminated:
        return None
    snapshot = get_elimination_weeks(
        [enrollment.user_id], None, enrollment.season_year)
    if enrollment.user_id in snapshot:
        return snapshot[enrollment.user_id]
    in_play = _weeks_in_play(enrollment.season_year)
    if len(in_play) != 1:
        return None
    week = in_play[0]
    lost = db.session.scalar(select(CfbPick.id).where(
        CfbPick.user_id == enrollment.user_id,
        CfbPick.week_id == week.id,
        CfbPick.is_correct.is_(False),
    ))
    if lost is None or not _someone_stands(week, enrollment):
        return None
    return week


def _weeks_in_play(season_year):
    """The season's incomplete weeks that can take a life before they
    complete: past the deadline with games on it (a 0-game week never
    completes, so it never takes one), or already holding a graded pick (a
    Thursday kickoff grades before Saturday's deadline). With two in play
    (an earlier week stalled on a postponed or unscored game), a later
    week's loss can still empty the pool and revive the earlier week's
    cut, so nothing is final until the snapshot."""
    weeks = []
    for week in week_reads.incomplete_weeks(season_year):
        graded = db.session.scalar(select(CfbPick.id).where(
            CfbPick.week_id == week.id, CfbPick.is_correct.is_not(None)).limit(1))
        played = db.session.scalar(select(CfbGame.id).where(
            CfbGame.week_id == week.id).limit(1))
        if graded is not None or (
                played is not None and deadline_has_passed(make_aware(week.deadline))):
            weeks.append(week)
    return weeks


def _someone_stands(week, out):
    """Whether another member is sure to be standing when ``week`` completes:
    two lives (a loss or a missed pick still leaves one), or a pick this
    week already graded (a loser with a life to spare survives it) or ruled
    a No Contest."""
    others = db.session.scalars(select(CfbEnrollment).where(
        CfbEnrollment.season_year == out.season_year,
        CfbEnrollment.is_eliminated.is_(False),
        CfbEnrollment.id != out.id,
    )).all()
    if any(e.lives_remaining >= 2 for e in others):
        return True
    picks = {p.user_id: p for p in db.session.scalars(
        select(CfbPick).where(CfbPick.week_id == week.id))}
    no_contest = set()
    for game in db.session.scalars(select(CfbGame).where(
            CfbGame.week_id == week.id, CfbGame.is_no_contest.is_(True))):
        no_contest.update((game.home_team_id, game.away_team_id))
    for enrollment in others:
        pick = picks.get(enrollment.user_id)
        if pick is not None and (pick.is_correct is not None or pick.team_id in no_contest):
            return True
    return False


_UNREAD = object()


def elimination_moment_due(enrollment, run_end=_UNREAD):
    """The week whose end this member has yet to watch, or None. A caller
    that already holds ``run_end_week(enrollment)`` passes it as ``run_end``."""
    week = run_end_week(enrollment) if run_end is _UNREAD else run_end
    if week is None or enrollment.elimination_seen_week == week.week_number:
        return None
    return week


def mark_elimination_seen(enrollment, week_number):
    """Record that the moment played on the card for ``week_number``, the
    week the page showed. Only while that is still the week due: a page left
    open across a re-grade that moved the run's end never files the new
    week as seen. Idempotent."""
    week = elimination_moment_due(enrollment)
    if week is not None and week.week_number == week_number:
        enrollment.elimination_seen_week = week_number
        db.session.commit()


def run_end_line(week_number):
    """The card's closing line, which opens with the elimination push's own
    title (``reminders.elimination_push_copy``) so the push and the room say
    one thing."""
    return f'Your run ends at Week {week_number}. The pool plays on.'
