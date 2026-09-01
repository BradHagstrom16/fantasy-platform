"""The Docket — deadline reminders (D24).

Three tiers before a week's Saturday 11:00 AM CT deadline (48h Thursday
morning, 24h Friday morning, 2h Saturday morning), sent only to roster
members whose sheet is still short of its obligations.

**De-dup is the sent flag, never the cadence** (D24). ``DocketWeek
.last_reminder_tier`` records the closest tier already mailed for the week;
a run whose active tier is at or behind it sends nothing. That is why
``docket-remind.timer`` can fire hourly and why the tolerance window below is
allowed to be wide: correctness does not depend on the timer landing in any
particular minute. Every game now shares this shape — CFB
(``CfbWeek.last_reminder_type``, retrofitted from backlog 2.7) and Golf
(``GolfTournament.last_reminder_type``) — with the order-gate math in
``utils.reminders.tier_already_sent``.

The 48h tier lands Thursday morning, ahead of the Thursday-night kickoffs
that lock their own cases hours before the week's deadline (D3 keeps early
games pickable, DESIGN.md 1.4 makes the wave visible). A player who is going
to act on a Thursday case has to hear about it on Thursday.

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
import logging
from datetime import timedelta

from extensions import db
from games.docket.services.enrollment import roster_user_ids
from games.docket.services.notifications import (
    deadline_line,
    letter,
    send_each,
    sheet_url,
)
from games.docket.services.picks import sheet_state
from games.docket.utils import now_utc, to_naive_utc
from models.user import User
from utils.email_layout import items_block, render_letter
from utils.reminders import tier_already_sent

logger = logging.getLogger(__name__)

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


def _build_body(week, tier, subject, deadline, link):
    """Per-recipient (plain, html) builder for send_each: the tier's letter,
    with the sheet's outstanding items (``outstanding()``'s prose, verbatim)
    as the list the CTA acts on. The lede counts down; the fact block states
    the literal time."""
    filed = ('Whatever is still open when the docket closes will be filled '
             'for you from the locked lines, and a side filed for you scores '
             'exactly like one you filed yourself. It is a safety net, not a '
             'plan.')
    reserve = ('You may also hold one side in reserve. It stays dormant '
               'unless a case is thrown out.')

    def build(_user, items):
        return render_letter(letter(
            week,
            subject=subject,
            headline=f'Your Week {week.week_number} sheet is not finished',
            preheader=f'The docket closes {deadline}.',
            lede=[COUNTDOWNS[tier]],
            facts=[('Deadline', deadline)],
            extras=[items_block(items, title='Still open on your sheet')],
            cta=('Open your sheet', link),
            supporting=[filed, reserve],
        ))
    return build


def run_reminder_pass(week, now=None, user_ids=None) -> dict:
    """Mail the week's due reminder tier. Idempotent within a tier.

    Reports a status rather than raising for every "no mail today" case: this
    runs hourly, so quiet is the normal outcome and a timer must not read it
    as a failure.
    """
    now_naive = to_naive_utc(now or now_utc())
    if now_naive >= week.deadline_at:
        return {'status': 'closed', 'week_number': week.week_number}

    window = active_window(week.deadline_at, now_naive)
    if window is None:
        return {'status': 'no_window', 'week_number': week.week_number}

    tier = window['tier']
    if tier_already_sent(week.last_reminder_tier, tier, REMINDER_ORDER):
        return {'status': 'already_sent', 'week_number': week.week_number,
                'tier': tier, 'last_tier': week.last_reminder_tier}

    if user_ids is None:
        user_ids = roster_user_ids()
    recipients = []
    for user_id in user_ids:
        items = outstanding(sheet_state(user_id, week))
        if not items:
            continue
        user = db.session.get(User, user_id)
        if user is None:  # pragma: no cover - roster ids come from FK rows
            continue
        recipients.append((user, items))

    if not recipients:
        # Deliberately NOT recorded: nothing was mailed, so this tier stays
        # open. A player who withdraws a side later in the same window is
        # still reachable, and the flag keeps meaning "this tier went out".
        return {'status': 'all_complete', 'week_number': week.week_number,
                'tier': tier}

    subject = SUBJECTS[tier].format(n=week.week_number)
    sent = send_each(recipients, subject,
                     _build_body(week, tier, subject, deadline_line(week),
                                 sheet_url()))

    if sent == 0:
        # Every send failed, so the tier is left open for the next hourly run
        # to retry. Recording it here would swallow a full mail outage.
        logger.error('Week %s: %s reminder reached nobody (%s recipients)',
                     week.week_number, tier, len(recipients))
        return {'status': 'send_failed', 'week_number': week.week_number,
                'tier': tier, 'recipients': len(recipients), 'sent': 0}

    # Recorded once ANY send succeeds, matching Golf's reasoning: gating on
    # all-recipient success would let one permanently bad address hold the
    # tier open and re-mail every good recipient on the next hourly firing,
    # which is the exact duplicate storm the flag exists to prevent.
    week.last_reminder_tier = tier
    db.session.commit()
    return {'status': 'sent', 'week_number': week.week_number, 'tier': tier,
            'recipients': len(recipients), 'sent': sent}
