"""The Docket — the sheet receipt (Brad, 2026-10-02: one per sitting,
through the hourly desk; amends the 2026-09-04 "Filed only" ruling).

The first receipt fired the moment the eighth side was held. The sheet's
ask ladder then asks for the x2, the number and (optionally) the reserve,
so in the normal flow the letter was stale on all three by the time it was
read ("Still open on your sheet: No headliner named."), and a member who
removed and re-held a side got the sheet again each time (three to ten
receipts a week for the tinkerers; prod journal, 2026-10-02).

Now every member mutation of the current week's sheet STAMPS the member's
``DocketSheetReceipt`` row (``touch``, called by the four routes; nothing
mails from a route), and the Club Desk's hourly firing (``club-remind``,
games/club_desk.py) mails each OWED, FILED sheet as it stands, once, and
stamps ``sent_at``:

- owed: ``sent_at`` is null or behind ``touched_at``;
- filed: eight sides the member held (``slot != 9 and not is_autopick``),
  the ruling's definition. A short sheet stays owed and is read again next
  hour; an autopicked sheet is short by construction, so the deadline pass
  never produces a receipt;
- the sitting is over: at least ``RECEIPT_QUIET`` since the last edit, so a
  firing that lands mid-sitting waits an hour rather than mailing half a
  sheet. The noon firing (``now >= deadline_at``) waives it: no edit can
  follow the close, and it runs two minutes before the autopick pass, so
  those members get the sheet they themselves filed, worded as closed
  (Brad, 2026-10-02).

A change after a sent receipt resends once, as "Sheet updated" (CFB's "a
change says so" rule). A reminder letter in the same firing satisfies the
receipt (the desk marks it sent). A refused send leaves the row owed for
the next firing, which the old stateless trigger could never do.

Accepted trades: up to an hour's delay (the sheet page answers "did it go
through" at once); a stale row from a past week is dormant (the drain
reads the week containing ``now`` only); a failed stamp is a log line,
never a refused pick (the route commits the pick before it stamps).
"""
import logging
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from extensions import db
from games.docket.models import DocketPick, DocketSheetReceipt
from games.docket.services.enrollment import get_enrollment
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
    now_naive,
    sheet_state,
)
from games.docket.services.reminders import outstanding
from models.user import User
from utils.email_layout import items_block, tab_block

logger = logging.getLogger(__name__)

# How long a sheet must sit untouched before a firing mails it: a member
# still filling the sheet at the top of the hour gets one letter next hour,
# not half a sheet now and the rest later.
RECEIPT_QUIET = timedelta(minutes=10)


# ---------------------------------------------------------------------------
# The touch (the routes)
# ---------------------------------------------------------------------------

def _receipt_row(user_id, week):
    return db.session.scalar(
        select(DocketSheetReceipt)
        .filter_by(user_id=user_id, week_id=week.id))


def _stamp(user_id, week, now):
    row = _receipt_row(user_id, week)
    if row is not None:
        row.touched_at = now
        db.session.commit()
        return
    db.session.add(DocketSheetReceipt(
        user_id=user_id, week_id=week.id, touched_at=now))
    try:
        db.session.commit()
    except IntegrityError:
        # Two requests raced to insert the member's row; the other one won.
        db.session.rollback()
        _receipt_row(user_id, week).touched_at = now
        db.session.commit()


def touch(user_id, week, now=None):
    """Stamp the member's last edit of ``week``'s sheet (naive UTC; the
    routes leave ``now`` None and read the seam-aware clock). Never gates
    the pick the route just committed: a failed stamp is logged and rolled
    back, and the member's success response goes out as usual."""
    if now is None:
        now = now_naive()
    try:
        _stamp(user_id, week, now)
    except Exception:
        db.session.rollback()
        logger.exception('Docket sheet stamp failed for user %s, week %s',
                         user_id, week.week_number)


# ---------------------------------------------------------------------------
# The drain (the Club Desk)
# ---------------------------------------------------------------------------

def _picks(user_id, week):
    return db.session.scalars(
        select(DocketPick).filter_by(user_id=user_id, week_id=week.id)
        .order_by(DocketPick.slot)
    ).all()


def _member_held(picks) -> int:
    """Scoring sides the member held: the reserve and the deadline pass's
    autopicks never count toward a filed sheet."""
    return sum(1 for p in picks
               if p.slot != BACKUP_SLOT and not p.is_autopick)


def _owed_rows(week):
    return db.session.scalars(
        select(DocketSheetReceipt)
        .filter_by(week_id=week.id)
        .filter(or_(DocketSheetReceipt.sent_at.is_(None),
                    DocketSheetReceipt.touched_at > DocketSheetReceipt.sent_at))
        .order_by(DocketSheetReceipt.user_id)
    ).all()


def owed_receipts(week, now):
    """The week's owed rows whose sheet is filed and whose sitting is over
    at ``now`` (naive UTC); the noon firing waives the quiet period."""
    closed = now >= week.deadline_at
    rows = []
    for row in _owed_rows(week):
        if not closed and now - row.touched_at < RECEIPT_QUIET:
            continue
        if _member_held(_picks(row.user_id, week)) != SCORING_SLOTS:
            continue
        rows.append(row)
    return rows


def compose_receipts(week, now):
    """``[(user, letter, row)]`` for every owed, filed sheet of ``week`` at
    ``now``: the desk sends each and, on acceptance, marks its row."""
    closed = now >= week.deadline_at
    composed = []
    for row in owed_receipts(week, now):
        user = db.session.get(User, row.user_id)
        nudge = payment_nudge_for(get_enrollment(user.id), bool(user.is_admin))
        receipt = sheet_receipt_letter(
            week, sheet_state(user.id, week, now=now), _picks(user.id, week),
            nudge, closed=closed, changed=row.sent_at is not None)
        composed.append((user, receipt, row))
    return composed


def mark_receipt_sent(row, now):
    """Stage ``sent_at`` (no commit: the desk commits once per firing)."""
    row.sent_at = now


# ---------------------------------------------------------------------------
# The letter
# ---------------------------------------------------------------------------

def _own_x2(pick) -> bool:
    """The member's own headliner; the deadline pass's auto-designation is
    never shown as theirs."""
    return pick.is_best and not pick.is_auto_best


def _sheet_lines(picks) -> list[str]:
    """'1. Utah Utes -3.5 (Idaho Vandals at Utah Utes)', the reserve last."""
    lines = []
    for p in picks:
        game = p.game
        label = 'Reserve' if p.slot == BACKUP_SLOT else str(p.slot)
        mark = ' · x2' if _own_x2(p) else ''
        lines.append(f'{label}. {describe_pick(p)}{mark} '
                     f'({game.away_team} at {game.home_team})')
    return lines


OPEN_SUPPORT = ['A case locks at its own kickoff, so a side on a locked '
                'case stands. Whatever is still open when the docket '
                'closes is filled for you from the locked lines.']
CLOSED_SUPPORT = ['A side on a locked case stands. Whatever was still open '
                  'when the docket closed is filled for you from the '
                  'locked lines.']


def sheet_receipt_letter(week, state, picks, nudge, *, closed=False,
                         changed=False):
    """The receipt as a Club Letter: the sheet is the content the CTA acts
    on. ``changed`` says a receipt went before (the subject says so);
    ``closed`` words the letter for the noon firing."""
    number = week.week_number
    deadline = deadline_line(week)
    best = next((p for p in picks if _own_x2(p)), None)
    open_items = outstanding(state)
    facts = [
        ('Closed' if closed else 'Deadline', deadline),
        ('x2', describe_pick(best) if best
         else ('Not named' if closed else 'Not named yet')),
        ('Number', state['prediction'] if state['prediction'] is not None
         else 'Not entered'),
    ]
    extras = [items_block(_sheet_lines(picks), title='Your sheet')]
    if open_items:
        extras.append(items_block(
            open_items,
            title=('Still open when the docket closed' if closed
                   else 'Still open on your sheet')))
    what = 'Sheet updated' if changed else 'Sheet filed'
    if closed:
        headline = 'your sheet is filed'
        preheader = f'Eight sides held. The docket closed {deadline}.'
        lede = ['The docket has closed. This is the sheet you filed.']
        supporting = CLOSED_SUPPORT
    elif changed:
        headline = 'your sheet is updated'
        preheader = f'Eight sides held. The docket closes {deadline}.'
        lede = ['This is your sheet as it stands after your latest change; '
                'change anything until the docket closes.']
        supporting = OPEN_SUPPORT
    else:
        headline = 'your sheet is filed'
        preheader = f'Eight sides held. The docket closes {deadline}.'
        lede = ['All eight sides are held. This is your sheet as it stands; '
                'change anything until the docket closes.']
        supporting = OPEN_SUPPORT
    return letter(
        week,
        subject=f'{what}: The Docket, Week {number}',
        headline=headline,
        preheader=preheader,
        lede=lede,
        facts=facts,
        extras=extras,
        cta=('Open your sheet', sheet_url()),
        supporting=supporting,
        notes=[tab_block(nudge, 'docket')],
    )
