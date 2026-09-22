"""The Docket — deadline reminders (D24).

Three tiers before a week's Sunday 12:00 PM CT deadline (48h Friday
afternoon, 24h Saturday afternoon, 2h Sunday morning), sent only to roster
members whose sheet is still short of its obligations.

**De-dup is the sent flag, never the cadence** (D24). ``DocketWeek
.last_reminder_tier`` records the closest tier already mailed for the week;
a run whose active tier is at or behind it sends nothing. That is why
``club-remind.timer`` can fire hourly and why the tolerance window below is
allowed to be wide: correctness does not depend on the timer landing in any
particular minute. Every game shares this shape — CFB
(``CfbWeek.last_reminder_type``) and Golf (``GolfTournament
.last_reminder_type``) — with the order-gate math in
``utils.reminders.tier_already_sent``.

The send loop itself is the Club Desk's (``games/club_desk.py``, ADR-065):
this module owns the Docket's tiers, recipients and letter, and
``services/desk.py`` is the consumer that hands them to the desk. A tier the
Docket rode as a footnote on a Survivor letter is pre-marked in the same
flag, so the desk's next firing never sends it standalone.

The 48h tier lands Friday afternoon. Thursday-night kickoffs still lock their
own cases hours ahead of the week's deadline (D3 keeps early games pickable,
DESIGN.md 1.4 makes the wave visible), but since the deadline moved to Sunday
12:00 PM CT (PR #203) that first reminder no longer precedes them — an accepted
gap: the reminders guard the Sunday deadline, and the Thursday wave is surfaced
on the sheet itself, not by mail.

Progress comes from ``picks.sheet_state`` and is never re-derived here: it is
the same assembly the sheet rail renders, so an email cannot contradict the
page it links to.

**Accepted trade: the flag is per-week, not per-recipient.** It is written
once, after the send loop, so a process that dies mid-loop leaves the tier
unrecorded and the next hourly run re-mails everyone — including whoever
already received it. Making that airtight means a per-recipient outbox with
provider idempotency keys, committed before each send. Deliberately not built:
the pool is roughly twenty people, the cost of the failure is one duplicate
reminder, and every other game on the platform makes the same trade (Golf's
recap and reminder paths both name it). If it is ever built, it should be
built once for all games, not here.
"""
from datetime import timedelta

from extensions import db
from games.docket.services.enrollment import roster_user_ids
from games.docket.services.notifications import (
    deadline_line,
    letter,
    sheet_url,
)
from games.docket.services.picks import sheet_state
from games.docket.utils import to_naive_utc
from models.user import User
from utils.email_layout import items_block
from utils.push import send_push

SCORING_SLOTS = 8

# One subject per tier, so Gmail never threads three reminders into one.
SUBJECTS = {
    '48h': 'Sheet not finished: The Docket, Week {n}',
    '24h': 'Closes tomorrow: The Docket, Week {n}',
    '2h': 'Two hours left: The Docket, Week {n}',
}
COUNTDOWNS = {
    '48h': 'Two days to go.',
    '24h': 'One day to go.',
    '2h': 'Two hours to go.',
}

# Hours before the deadline, farthest first. The tier tag is what lands in
# DocketWeek.last_reminder_tier.
REMINDER_WINDOWS = (
    {'hours': 48, 'tier': '48h'},
    {'hours': 24, 'tier': '24h'},
    {'hours': 2, 'tier': '2h'},
)

# Higher = closer to the deadline. A run whose active tier is <= the tier
# already recorded is a repeat and sends nothing. An unrecognised stored value
# scores -1 so an unknown flag re-sends rather than silencing the week.
REMINDER_ORDER = {window['tier']: index
                  for index, window in enumerate(REMINDER_WINDOWS)}

# Half-width of each tier's firing window. Wide on purpose: the flag above is
# what prevents a double send, so this only has to guarantee that an hourly
# timer lands inside every tier at least once.
TOLERANCE_MINUTES = 35


def active_window(deadline_naive_utc, now_naive_utc):
    """The reminder tier due at this instant, or None.

    Returns the tier CLOSEST to the deadline when more than one matches. The
    shipped spacing (48h/24h/2h against a 35-minute tolerance) cannot produce
    an overlap, but resolving deterministically means a future tier edit
    cannot silently make the choice depend on tuple order.
    """
    if now_naive_utc >= deadline_naive_utc:
        return None
    tolerance = timedelta(minutes=TOLERANCE_MINUTES)
    matches = [
        window for window in REMINDER_WINDOWS
        if abs(deadline_naive_utc - timedelta(hours=window['hours'])
               - now_naive_utc) <= tolerance
    ]
    if not matches:
        return None
    return max(matches, key=lambda window: REMINDER_ORDER[window['tier']])


def outstanding(state) -> list[str]:
    """What this sheet still owes, in the order the rail states it.

    Empty means the sheet is complete and its owner is not a recipient. The
    reserve (slot 9) is prudence rather than an obligation (DESIGN.md 1.5),
    so it is described in the body but never triggers a reminder.
    """
    items = []
    committed = state['scoring_count']
    if committed < SCORING_SLOTS:
        items.append(f'Sides committed: {committed} of {SCORING_SLOTS}.')
    if state['best'] is None:
        items.append('No headliner named.')
    if state['prediction'] is None:
        items.append('No combined-score number recorded.')
    return items


# ---------------------------------------------------------------------------
# Shared builders (Club Desk step 3, eng review 6A): the desk's Docket
# consumer (services/desk.py) composes through these; the legacy pass that
# once sat below them was retired at step 9.
# ---------------------------------------------------------------------------

FILED = ('Whatever is still open when the docket closes will be filled '
         'for you from the locked lines, and a side filed for you scores '
         'exactly like one you filed yourself. It is a safety net, not a '
         'plan.')
RESERVE = ('You may also hold one side in reserve. It stays dormant '
           'unless a case is thrown out.')


def reminder_recipients(week, tier, now, user_ids=None):
    """Who owes something on their sheet right now: ``(user, items)`` per
    roster member whose sheet is short (``outstanding()``'s prose, verbatim,
    the list the CTA acts on). ``tier`` and ``now`` are part of the
    cross-game contract; the Docket's recipients do not depend on them.
    ``user_ids`` narrows the roster (tests)."""
    if user_ids is None:
        user_ids = roster_user_ids()
    now_naive = to_naive_utc(now)
    recipients = []
    for user_id in user_ids:
        items = outstanding(sheet_state(user_id, week, now=now_naive))
        if not items:
            continue
        user = db.session.get(User, user_id)
        if user is None:  # pragma: no cover - roster ids come from FK rows
            continue
        recipients.append((user, items))
    return recipients


def reminder_context(week):
    """The per-run facts every reminder letter for ``week`` shares."""
    return {'week': week, 'deadline': deadline_line(week), 'link': sheet_url()}


def reminder_letter(recipient, context, tier):
    """One recipient's reminder as a Letter: the tier's subject and
    countdown, the literal deadline in the fact block, the sheet's
    outstanding items as the list the CTA acts on. ``recipient`` is an
    element of ``reminder_recipients``."""
    _user, items = recipient
    week, deadline = context['week'], context['deadline']
    return letter(
        week,
        subject=SUBJECTS[tier].format(n=week.week_number),
        headline=f'Your Week {week.week_number} sheet is not finished',
        preheader=f'The docket closes {deadline}.',
        lede=[COUNTDOWNS[tier]],
        facts=[('Deadline', deadline)],
        extras=[items_block(items, title='Still open on your sheet')],
        cta=('Open your sheet', context['link']),
        supporting=[FILED, RESERVE],
    )


def _push_deadline_nag(week, tier, now_naive, user_ids):
    """The deadline nag as a push (T11): the buzz twin of the reminder email.
    Never raises (send_push swallows its own errors)."""
    if not user_ids:
        return
    ttl = max(int((week.deadline_at - now_naive).total_seconds()), 0)
    title = ('Last call: your sheet.' if tier == '2h'
             else 'Your Docket sheet is due.')
    send_push(user_ids,
              title=title,
              body=f'{COUNTDOWNS[tier]} Sides still open.',
              url='/docket/',
              tag=f'docket-w{week.week_number}-nag',
              topic=f'docket-w{week.week_number}',
              ttl=ttl, urgency='normal', app_badge=1)
