"""The Wire's live preview for Survivor (ADR-074, PR B).

The one push this member would get next, as `/app` paints it on a
lock-screen banner before they turn The Wire on. Every word comes from the
sender's own copy functions in ``services/reminders.py`` (``nag_push_copy``,
``verdict_push_copy``), so the preview can never drift from what lands.
Nothing is invented: a member who owes a pick sees the reminder they would
get, a member holding a pick sees the verdict shape over their own team,
and everyone else (not enrolled, eliminated, no open week, pick already
graded) gets None so `/app` falls to the real test dispatch.

Reached only through ``games.registry.GameRegistryEntry.wire_preview``;
``core/push`` never imports this module.
"""
from sqlalchemy import or_

from games.cfb.models import CfbGame, CfbPick
from games.cfb.services import weeks as week_reads
from games.cfb.services.enrollment import get_enrollment
from games.cfb.services.reminders import (
    REMINDER_WINDOWS,
    _picked_team_display,
    nag_push_copy,
    verdict_push_copy,
)
from games.cfb.utils import format_deadline_short, make_aware


def _next_nag(week, deadline, now):
    """The nag still ahead of ``now`` (aware), with the clock it would be
    sent on: the warning while its window is still ahead, else the final,
    read at the final window's open unless ``now`` is already inside it, so
    the title's "locks in" says what the phone will say."""
    warning, final = (next(w for w in REMINDER_WINDOWS if w['type'] == t)
                      for t in ('warning', 'final'))
    if now < deadline - warning['end']:
        return nag_push_copy(week, 'warning', deadline, now)
    send_at = max(now, deadline - final['start'])
    return nag_push_copy(week, 'final', deadline, send_at)


def wire_preview(user_id, now):
    """``{title, body, when}`` of this member's next Survivor push, or None.
    ``now`` is an aware UTC instant (the route's clock)."""
    enrollment = get_enrollment(user_id)
    if enrollment is None or enrollment.is_eliminated:
        return None
    week = week_reads.active_week()
    if week is None:
        return None
    pick = CfbPick.query.filter_by(user_id=user_id, week_id=week.id).first()
    deadline = make_aware(week.deadline)
    if pick is None:
        if now >= deadline:
            return None
        title, body = _next_nag(week, deadline, now)
        return {'title': title, 'body': body,
                'when': format_deadline_short(week.deadline)}
    if pick.is_correct is not None:
        return None  # graded: the promise is spent
    game = CfbGame.query.filter(
        CfbGame.week_id == week.id,
        or_(CfbGame.home_team_id == pick.team_id,
            CfbGame.away_team_id == pick.team_id)).first()
    team = _picked_team_display(game, pick.team_id)
    title, body = verdict_push_copy(team, True)
    return {'title': title, 'body': body, 'when': f'When {team} goes final'}
