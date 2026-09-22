"""The Docket's half of the Club Desk (ADR-065, `games/club_desk.py`).

The reminder consumer answers "whose sheet is short right now" through the
same shared builders the legacy pass calls (``reminder_recipients``,
``reminder_context``, ``reminder_letter``), so a desk letter is
byte-identical to today's; ``covers`` names the tier a ride on Survivor's
slot satisfies (48h on F, 24h on S) only when that tier's target is within
six hours. The Paper consumer opens the week without announcing
(``opener.open_week(announce=False)``) and says, per member, last week's
record and when this week closes, from the SAME reader the record letter
uses (``record.week_records``), so the two can never disagree. Nothing
here reads a clock: every callable takes the desk's ``now``.
"""
from datetime import UTC, timedelta

from markupsafe import Markup
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from games.club_desk import PaperConsumer, ReminderConsumer, Say
from games.docket.models import DocketEnrollment, DocketGame, DocketWeek
from games.docket.services.notifications import sheet_url
from games.docket.services.opener import open_week as _open_by_number
from games.docket.services.payment import payment_nudge_for
from games.docket.services.picks import sheet_state
from games.docket.services.record import (
    ordinal,
    points_text,
    record_text,
    week_records,
)
from games.docket.services.reminders import (
    REMINDER_ORDER,
    SCORING_SLOTS,
    _push_deadline_nag,
    active_window,
    reminder_context,
    reminder_letter,
    reminder_recipients,
)
from games.docket.services.weeks import SEASON_YEAR, week_number_for
from games.docket.utils import to_naive_utc
from utils.email_layout import Section
from utils.reminders import tier_already_sent

SLUG = 'docket'
DEADLINE_LABEL = 'The docket closes'
BUTTON = 'Open your sheet'
# The tier a ride on Survivor's slot satisfies, and how near its target
# must be (eng review 1A: a rider covers only a tier that is about due).
COVERS = {'F': '48h', 'S': '24h'}
TIER_HOURS = {'48h': 48, '24h': 24, '2h': 2}
COVER_REACH = timedelta(hours=6)


# ---------------------------------------------------------------------------
# Reminder consumer
# ---------------------------------------------------------------------------

def _week(now):
    """The week containing ``now``: None out of season or before its
    import (both quiet skips for the desk)."""
    number = week_number_for(now)
    if number is None:
        return None
    return db.session.scalar(select(DocketWeek).filter_by(week_number=number))


def _deadline(week):
    return week.deadline_at.replace(tzinfo=UTC)


def _anchor_tier(week, now):
    now_naive = to_naive_utc(now)
    if now_naive >= week.deadline_at:
        return None
    window = active_window(week.deadline_at, now_naive)
    if window is None:
        return None
    tier = window['tier']
    if tier_already_sent(week.last_reminder_tier, tier, REMINDER_ORDER):
        return None
    return tier


def _covers(slot, week, now):
    tier = COVERS.get(slot)
    if tier is None:
        return None
    now_naive = to_naive_utc(now)
    if now_naive >= week.deadline_at:
        return None
    target = week.deadline_at - timedelta(hours=TIER_HOURS[tier])
    if abs(target - now_naive) > COVER_REACH:
        return None
    return tier


def _user(recipient):
    return recipient[0]


def _owed_sentence(state) -> str:
    """``3 sides still to file, no headliner named.`` from the sheet's
    own state (the rail's facts, never re-derived)."""
    parts = []
    short = SCORING_SLOTS - state['scoring_count']
    if short > 0:
        parts.append(f'{short} side{"s" if short != 1 else ""} still to file')
    if state['best'] is None:
        parts.append('no headliner named')
    if state['prediction'] is None:
        parts.append('no number recorded')
    return ', '.join(parts) + '.'


def _section(recipient, week, now):
    user, _items = recipient
    state = sheet_state(user.id, week, now=to_naive_utc(now))
    return Section(
        slug=SLUG,
        title=f'The Docket · Week {week.week_number}',
        lines=[_owed_sentence(state)],
        deadline=_deadline(week),
        deadline_label=DEADLINE_LABEL,
        button=BUTTON,
        url=sheet_url(),
    )


def _context(week, now):
    return reminder_context(week)


def _tier_sent(week, tier):
    return tier_already_sent(week.last_reminder_tier, tier, REMINDER_ORDER)


def _mark_sent(week, tier):
    """Monotonic: a later tier never regresses to an earlier one."""
    if not _tier_sent(week, tier):
        week.last_reminder_tier = tier


def _push(week, tier, now, user_ids):
    _push_deadline_nag(week, tier, to_naive_utc(now), user_ids)


REMINDER = ReminderConsumer(
    slug=SLUG,
    week=_week,
    deadline=_deadline,
    anchor_tier=_anchor_tier,
    covers=_covers,
    recipients=reminder_recipients,
    user=_user,
    section=_section,
    context=_context,
    letter=reminder_letter,
    tier_sent=_tier_sent,
    mark_sent=_mark_sent,
    push=_push,
)


# ---------------------------------------------------------------------------
# Paper consumer
# ---------------------------------------------------------------------------

def _has_games(week):
    return db.session.scalar(
        select(DocketGame.id).filter_by(week_id=week.id).limit(1)) is not None


def _candidate(now):
    """The week containing ``now`` with games, announced or not."""
    week = _week(now)
    if week is None or not _has_games(week):
        return None
    return week


def _open_week(now):
    """Create and import the week silently; the week to announce is the
    one just opened, with games, from a whole import, not yet announced. A
    half slate (``partial``) or a failed import is never announced: the
    07:00 ``docket-lines`` run announces standalone once it is whole."""
    number = week_number_for(now)
    if number is None:
        return None
    result = _open_by_number(number, announce=False)
    week = result.week
    if week is None or result.summary.get('status') in ('error', 'partial'):
        return None
    if week.picks_open_notified or not _has_games(week):
        return None
    return week


def _record_week(week):
    """The previous week, whose record this Paper carries (None in Week 1
    or when it was never imported)."""
    if week.week_number <= 1:
        return None
    return db.session.scalar(
        select(DocketWeek).filter_by(week_number=week.week_number - 1))


def _graded(week):
    return week is not None and week.default_error_tenths is not None


def _record_line(fields):
    """``Last week: <strong>6 wins, 2 losses, 7 points.</strong> 4th of 31
    sheets. Dana Whitfield went 7-1 and takes the $20 weekly purse.`` from
    the record letter's own fields."""
    tally = fields['tally']
    top = fields['top_sheet']
    prize = fields['weekly_prize']
    wins = f'{tally.wins} win{"s" if tally.wins != 1 else ""}'
    losses = f'{tally.losses} loss{"es" if tally.losses != 1 else ""}'
    pushes = (f', {tally.pushes} push{"es" if tally.pushes != 1 else ""}'
              if tally.pushes else '')
    if top.split:
        verdict = (f'{len(top.names)} sheets at {top.record}; the purse is '
                   f'split.')
    elif fields['is_winner']:
        verdict = f'You went {top.record} and take the ${prize} weekly purse.'
    else:
        verdict = (f'{top.names[0]} went {top.record} and takes the ${prize} '
                   f'weekly purse.')
    line = Markup(
        'Last week: <strong>{}, {}{}, {}.</strong> {} of {} sheets. {}'
    ).format(wins, losses, pushes, points_text(fields['points']),
             ordinal(fields['week_rank']), fields['roster_size'], verdict)
    return line, f'went {record_text(tally)}'


FILING = ('File eight sides, name your x2 (it scores double), and enter '
          'your number before the docket closes.')


def _sections(week, record_week, now):
    enrollments = db.session.scalars(
        select(DocketEnrollment).filter_by(season_year=SEASON_YEAR)
        .options(joinedload(DocketEnrollment.user))
        .order_by(DocketEnrollment.user_id)).all()
    records = {}
    graded = _graded(record_week)
    if graded:
        records = {user.id: fields
                   for user, fields in week_records(record_week,
                                                    to_naive_utc(now))}
    title = f'The Docket · Week {week.week_number}'
    says = {}
    for enrollment in enrollments:
        user = enrollment.user
        if user is None:
            continue
        hook, on_record = None, False
        if record_week is None:
            lines = [FILING]
        elif not graded:
            lines = ['Last week is still being graded.']
        elif user.id in records:
            line, hook = _record_line(records[user.id])
            lines = [line]
            on_record = True
        else:
            lines = [FILING]           # joined after last week's deadline
        says[user.id] = Say(
            user=user, hook=hook, record=on_record,
            section=Section(
                slug=SLUG, title=title, lines=lines,
                deadline=_deadline(week), deadline_label=DEADLINE_LABEL,
                button=BUTTON, url=sheet_url(),
                nudge=payment_nudge_for(enrollment, bool(user.is_admin))))
    return says


def _mark_announced(week, record_week, announced, record):
    if announced:
        week.picks_open_notified = True
    if record and record_week is not None:
        record_week.record_notified = True


PAPER = PaperConsumer(
    slug=SLUG,
    open_week=_open_week,
    candidate=_candidate,
    record_week=_record_week,
    sections=_sections,
    mark_announced=_mark_announced,
)
