"""The Wire's live preview for The Docket (ADR-074, PR B).

The one push this member would get next, as `/app` paints it on a
lock-screen banner before they turn The Wire on. Every word comes from the
sender's own copy functions (``reminders.nag_push_copy``,
``notifications.verdict_push_title`` and ``shared_side_phrase``), so the
preview can never drift from what lands. Nothing is invented: a short sheet
sees the reminder it would get; a filed sheet sees the verdict shape over
its next unsettled side, with the real count of sheets sharing it (the
stamp word is the one thing a preview cannot know, so it shows the WIN
stamp as the sample, the way Survivor's shows "won"); no roster seat, no
week, no unsettled side gets None so `/app` falls to the test dispatch.

Reached only through ``games.registry.GameRegistryEntry.wire_preview``;
``core/push`` never imports this module.
"""
from datetime import timedelta

from sqlalchemy import func, select

from extensions import db
from games.docket.models import DocketGame, DocketPick
from games.docket.services import week_reads
from games.docket.services.enrollment import get_enrollment
from games.docket.services.notifications import (
    deadline_line,
    shared_side_phrase,
    verdict_push_title,
)
from games.docket.services.picks import sheet_state
from games.docket.services.reminders import (
    REMINDER_WINDOWS,
    nag_push_copy,
    outstanding,
)
from games.docket.services.sheets import _snapshot
from games.docket.services.weeks import week_number_for
from games.docket.utils import to_naive_utc

_SCORING_SLOT_MAX = 8


def _next_nag(week, state, now_naive):
    """The tier still ahead of ``now`` with the clock it would be sent on
    (the tier's own instant, unless ``now`` is already past it), so a last
    call's "closes in" says what the phone will say."""
    for window in REMINDER_WINDOWS:
        send_at = week.deadline_at - timedelta(hours=window['hours'])
        if now_naive < send_at:
            return nag_push_copy(week, window['tier'], state, send_at)
    return nag_push_copy(week, REMINDER_WINDOWS[-1]['tier'], state, now_naive)


def _next_unsettled_side(user_id, week):
    """This sheet's earliest-kicking scoring side whose case is not final,
    with the count of scoring sheets on that side, or None."""
    rows = db.session.execute(
        select(DocketPick, DocketGame)
        .join(DocketGame, DocketPick.game_id == DocketGame.id)
        .where(DocketPick.user_id == user_id, DocketPick.week_id == week.id,
               DocketPick.slot <= _SCORING_SLOT_MAX)
        .order_by(DocketGame.kickoff, DocketPick.slot)).all()
    for pick, game in rows:
        if game.no_contest or _snapshot(game) is not None:
            continue
        n = db.session.scalar(
            select(func.count()).select_from(DocketPick).where(
                DocketPick.game_id == game.id, DocketPick.market == pick.market,
                DocketPick.side == pick.side,
                DocketPick.slot <= _SCORING_SLOT_MAX))
        return pick, game, n
    return None


def wire_preview(user_id, now):
    """``{title, body, when}`` of this member's next Docket push, or None.
    ``now`` is an aware UTC instant (the route's clock)."""
    if get_enrollment(user_id) is None:
        return None
    number = week_number_for(now)
    if number is None:
        return None
    week = week_reads.week_by_number(number)
    if week is None:
        return None
    now_naive = to_naive_utc(now)
    if now_naive < week.deadline_at:
        state = sheet_state(user_id, week, now=now_naive)
        if outstanding(state):
            title, body = _next_nag(week, state, now_naive)
            return {'title': title, 'body': body, 'when': deadline_line(week)}
    side = _next_unsettled_side(user_id, week)
    if side is None:
        return None
    pick, game, n = side
    case = f'{game.away_team} at {game.home_team}'
    return {'title': verdict_push_title('WIN', pick, game),
            'body': f'{case}. {shared_side_phrase(pick, n)}',
            'when': f'When {case} goes final'}
