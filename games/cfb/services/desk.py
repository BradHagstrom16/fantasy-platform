"""CFB Survivor's half of the Club Desk (ADR-065, `games/club_desk.py`).

The reminder consumer answers "who owes a pick right now" through the same
shared builders the legacy pass calls (``reminder_recipients``,
``reminder_context``, ``reminder_letter``), so a desk letter is
byte-identical to today's. The Paper consumer opens the week without
announcing (``run_spread_update(announce=False)``) and says, per member,
what last week did and when this week locks, from facts the room already
persists: the ``CfbWeekOutcome`` snapshot, lives, and ``N of M still
alive``. Nothing here reads a clock: every callable takes the desk's
``now``.
"""
from markupsafe import Markup
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from games.cfb.models import CfbEnrollment, CfbPick, CfbWeek, CfbWeekOutcome
from games.cfb.services.payment import payment_nudge_for
from games.cfb.services.reminders import (
    REMINDER_ORDER,
    REMINDER_WINDOWS,
    _push_pick_nag,
    active_reminder_window_at,
    reminder_context,
    reminder_letter,
    reminder_recipients,
)
from games.cfb.utils import get_week_display_name, make_aware
from games.club_desk import PaperConsumer, ReminderConsumer, Say
from utils.email_layout import Section, site_url
from utils.reminders import tier_already_sent

SLUG = 'cfb'
DEADLINE_LABEL = 'Survivor locks'
BUTTON = 'Make your pick'
LIVES_WORDS = {2: 'Two lives in hand.', 1: 'One life in hand.'}


def _season():
    from flask import current_app
    return current_app.config.get('CFB_SEASON_YEAR', 2026)


def _pick_url(week):
    return f'{site_url()}/cfb/pick/{week.week_number}'


# ---------------------------------------------------------------------------
# Reminder consumer
# ---------------------------------------------------------------------------

def _week(now):
    """The active week, the one the legacy pass reminds for."""
    return db.session.scalar(select(CfbWeek).filter_by(is_active=True))


def _deadline(week):
    return make_aware(week.deadline)


def _anchor_tier(week, now):
    window = active_reminder_window_at(_deadline(week), now)
    if window is None:
        return None
    tier = window['type']
    if tier_already_sent(week.last_reminder_type, tier, REMINDER_ORDER):
        return None
    return tier


def _covers(slot, week, now):
    """Survivor never rides: its final tier is the last letter before its
    Saturday lock, and the Docket's Sunday slot has nothing of Survivor's
    left to carry."""
    return None


def _user(recipient):
    return recipient[1]


def _section(recipient, week, now):
    week_name = get_week_display_name(week)
    return Section(
        slug=SLUG,
        title=f'CFB Survivor · {week_name}',
        lines=[f'Your {week_name} pick is not in.'],
        deadline=_deadline(week),
        deadline_label=DEADLINE_LABEL,
        button=BUTTON,
        url=_pick_url(week),
    )


def _tier_sent(week, tier):
    return tier_already_sent(week.last_reminder_type, tier, REMINDER_ORDER)


def _mark_sent(week, tier):
    """Monotonic: a later tier never regresses to an earlier one."""
    if not _tier_sent(week, tier):
        week.last_reminder_type = tier


def _push(week, tier, now, user_ids):
    window = next(w for w in REMINDER_WINDOWS if w['type'] == tier)
    _push_pick_nag(week, window, _deadline(week), now, user_ids)


REMINDER = ReminderConsumer(
    slug=SLUG,
    week=_week,
    deadline=_deadline,
    anchor_tier=_anchor_tier,
    covers=_covers,
    recipients=reminder_recipients,
    user=_user,
    section=_section,
    context=reminder_context,
    letter=reminder_letter,
    tier_sent=_tier_sent,
    mark_sent=_mark_sent,
    push=_push,
)


# ---------------------------------------------------------------------------
# Paper consumer
# ---------------------------------------------------------------------------

def _has_lines(week):
    return any(g.home_team_spread is not None for g in week.games)


def _candidate(now):
    """The open week (active, with lines), announced or not."""
    week = db.session.scalar(select(CfbWeek).filter_by(is_active=True))
    if week is None or not _has_lines(week):
        return None
    return week


def _open_week(now):
    """Open the week with its lines, silently; the week to announce is the
    active week with lines whose letter has not gone out."""
    from games.cfb.services.automation import run_spread_update
    run_spread_update(announce=False)
    db.session.expire_all()
    week = _candidate(now)
    if week is None or week.picks_open_notified:
        return None
    return week


def _record_week(week):
    """Survivor's "last week" is the latest complete week before this one."""
    return db.session.scalar(
        select(CfbWeek)
        .filter(CfbWeek.is_complete.is_(True),
                CfbWeek.week_number < week.week_number)
        .order_by(CfbWeek.week_number.desc()))


def _last_week_line(outcome, pick):
    """``Last week: <strong>Survived</strong> with Oregon.`` from the
    outcome snapshot and the pick; None without a snapshot."""
    if outcome is None:
        return None, None
    team = pick.team.name if pick is not None and pick.team else None
    if outcome.no_pick:
        verdict, hook = 'No pick, lost a life', 'lost a life'
        with_team = ''
    elif outcome.lost_life:
        verdict, hook = 'Lost a life', f'lost a life with {team}'
        with_team = f' with {team}' if team else ''
    else:
        verdict, hook = 'Survived', f'survived with {team}'
        with_team = f' with {team}' if team else ''
    if team is None:
        hook = hook.split(' with ')[0]
    line = Markup('Last week: <strong>{}</strong>{}.').format(verdict, with_team)
    return line, hook


def _sections(week, record_week, now):
    season = _season()
    enrollments = db.session.scalars(
        select(CfbEnrollment).filter_by(season_year=season)
        .options(joinedload(CfbEnrollment.user))
        .order_by(CfbEnrollment.user_id)).all()
    alive = sum(1 for e in enrollments if not e.is_eliminated)
    total = len(enrollments)
    still = f'{alive} of {total} still alive.'
    outcomes, picks = {}, {}
    if record_week is not None:
        outcomes = {o.user_id: o for o in db.session.scalars(
            select(CfbWeekOutcome).filter_by(week_id=record_week.id))}
        picks = {p.user_id: p for p in db.session.scalars(
            select(CfbPick).filter_by(week_id=record_week.id))}
    week_name = get_week_display_name(week)
    title = f'CFB Survivor · {week_name}'
    says = {}
    for enrollment in enrollments:
        user = enrollment.user
        if user is None:
            continue
        if enrollment.is_eliminated:
            out_week = db.session.scalar(
                select(CfbWeek.week_number).join(CfbWeekOutcome)
                .filter(CfbWeekOutcome.user_id == enrollment.user_id,
                        CfbWeekOutcome.is_eliminated.is_(True))
                .order_by(CfbWeek.week_number))
            out = (f'Out after Week {out_week}.' if out_week
                   else 'Out of the running.')
            says[user.id] = Say(user=user, section=Section(
                slug=SLUG, title=title, lines=[f'{out} {still}']))
            continue
        line, hook = _last_week_line(outcomes.get(enrollment.user_id),
                                     picks.get(enrollment.user_id))
        lives = LIVES_WORDS.get(enrollment.lives_remaining,
                                f'{enrollment.lives_remaining} lives in hand.')
        text = f'{lives} {still}'
        lines = ([Markup('{} {}').format(line, text)] if line is not None
                 else [text])
        says[user.id] = Say(
            user=user, hook=hook,
            section=Section(
                slug=SLUG, title=title, lines=lines,
                deadline=_deadline(week), deadline_label=DEADLINE_LABEL,
                button=BUTTON, url=_pick_url(week),
                nudge=payment_nudge_for(enrollment, bool(user.is_admin))))
    return says


def _mark_announced(week, record_week, announced, record):
    if announced:
        week.picks_open_notified = True


PAPER = PaperConsumer(
    slug=SLUG,
    open_week=_open_week,
    candidate=_candidate,
    record_week=_record_week,
    sections=_sections,
    mark_announced=_mark_announced,
)
