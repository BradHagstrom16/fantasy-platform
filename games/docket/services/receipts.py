"""The Docket — the sheet receipt (Brad's ruling 2026-09-04: "Filed only").

One Club Letter the moment the eighth side is held: the sheet as it stands
(every side with its frozen number, the x2, the number, the reserve), what
is still open, the deadline, and the sheet link. A member who asked "are my
picks submitted? I can't tell" gets the answer in their inbox as well as on
the sheet.

**The trigger is stateless.** ``sheet_just_filed`` compares the scoring
count before and after the mutation and is true only for 7 -> 8, so nothing
else on the sheet ever mails: not the reserve (slot 9), not the x2, not the
number, not a move (which returns a scoring pick but leaves the count).
There is no sent flag and no new column; a member who removes a side and
holds another gets the sheet again, which is the receipt for the sheet they
now have. A post-deadline receipt was ruled out ("Filed only").

**Accepted trade: the transition is not serialized.** Two requests for the
same eighth side racing each other (a no-JS double-click; the sheet's
enhancement layer already holds a ``busy`` flag across each mutation) can
both read 7 then 8 and mail twice. Making that airtight means a
per-recipient outbox with provider idempotency keys, committed before each
send, which is the same trade the reminder passes name and decline: the
pool is roughly twenty people and the cost is one duplicate receipt. If it
is ever built, it should be built once for all games, not here.

Sending never gates the pick: ``send_platform_email`` returns False rather
than raising, and the route records the pick before it asks for the mail.
Progress comes from ``picks.sheet_state`` and the open items from
``reminders.outstanding``, so the receipt cannot contradict the sheet or
the reminder that may follow it.
"""
import logging

from sqlalchemy import func, select

from extensions import db
from games.docket.models import DocketPick
from games.docket.services.notifications import (
    deadline_line,
    letter,
    sheet_url,
)
from games.docket.services.payment import payment_nudge_for
from games.docket.services.picks import (
    BACKUP_SLOT,
    SCORING_SLOTS,
    describe_pick,
    sheet_state,
)
from games.docket.services.reminders import outstanding
from utils.email import send_platform_email
from utils.email_layout import items_block, render_letter, tab_block

logger = logging.getLogger(__name__)


def scoring_count(user_id: int, week) -> int:
    """How many scoring sides (slots 1-8) the member holds this week."""
    return db.session.scalar(
        select(func.count(DocketPick.id))
        .filter_by(user_id=user_id, week_id=week.id)
        .filter(DocketPick.slot != BACKUP_SLOT)
    )


def sheet_just_filed(before: int, after: int) -> bool:
    """The trigger: the mutation took the scoring count from 7 to 8."""
    return before == SCORING_SLOTS - 1 and after == SCORING_SLOTS


def _sheet_lines(picks) -> list[str]:
    """'1. Utah Utes -3.5 (Idaho Vandals at Utah Utes)', the reserve last."""
    lines = []
    for p in picks:
        game = p.game
        label = 'Reserve' if p.slot == BACKUP_SLOT else str(p.slot)
        mark = ' · x2' if p.is_best else ''
        lines.append(f'{label}. {describe_pick(p)}{mark} '
                     f'({game.away_team} at {game.home_team})')
    return lines


def sheet_receipt_letter(week, state, picks, nudge):
    """The receipt as a Club Letter: the sheet is the content the CTA acts on."""
    number = week.week_number
    deadline = deadline_line(week)
    best = next((p for p in picks if p.is_best), None)
    open_items = outstanding(state)
    facts = [
        ('Deadline', deadline),
        ('x2', describe_pick(best) if best else 'Not named yet'),
        ('Number', state['prediction'] if state['prediction'] is not None
         else 'Not entered'),
    ]
    extras = [items_block(_sheet_lines(picks), title='Your sheet')]
    if open_items:
        extras.append(items_block(open_items, title='Still open on your sheet'))
    return letter(
        week,
        subject=f'Sheet filed: The Docket, Week {number}',
        headline=f'Your Week {number} sheet is filed',
        preheader=f'Eight sides held. The docket closes {deadline}.',
        lede=['All eight sides are held. This is your sheet as it stands; '
              'change anything until the docket closes.'],
        facts=facts,
        extras=extras,
        cta=('Open your sheet', sheet_url()),
        supporting=['A case locks at its own kickoff, so a side on a locked '
                    'case stands. Whatever is still open when the docket '
                    'closes is filled for you from the locked lines.'],
        notes=[tab_block(nudge, 'docket')],
    )


def send_sheet_receipt(user, enrollment, week) -> bool:
    """Mail the member their sheet. Returns whether the send was accepted."""
    if not user.email:
        return False
    state = sheet_state(user.id, week)
    picks = db.session.scalars(
        select(DocketPick).filter_by(user_id=user.id, week_id=week.id)
        .order_by(DocketPick.slot)
    ).all()
    nudge = payment_nudge_for(enrollment, bool(user.is_admin))
    receipt = sheet_receipt_letter(week, state, picks, nudge)
    plain, html = render_letter(receipt)
    sent = send_platform_email(user.email, receipt.subject, plain, html)
    if sent:
        logger.info('Docket sheet receipt sent to user %s for week %s',
                    user.id, week.week_number)
    else:
        logger.warning('Docket sheet receipt to user %s was not accepted',
                       user.id)
    return sent
