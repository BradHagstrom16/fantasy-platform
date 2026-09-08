"""
CFB Survivor Pool -- Week State
==============================
One definition of "which week" for the room AND the lounge (DESIGN.md
§10.5: never calculate the same fact differently in lounge and room).

Three weeks matter:

- the **reveal week** -- the latest week whose deadline has passed and that
  has at least one game, complete or not (Brad's ruling 2026-09-07: the
  standings show it; 2026-09-08: the whole room and the lounge lead with it
  while it is unfinished). A 0-game orphan never leads.
- the **pick week** -- the active week while its deadline is ahead: the one
  week a member can pick in. Since ADR-062 a week is active only once its
  lines have landed, so "active" and "pickable" are the same thing.
- the **lead** -- the week the room talks about: the reveal week while it
  is unfinished, else the pick week, else the reveal week's verdict.

Imports only the models and utils, so both ``routes`` and
``services.lounge`` can use it without a cycle.
"""
from dataclasses import dataclass, field
from datetime import datetime

from games.cfb.models import CfbGame, CfbWeek
from games.cfb.utils import deadline_has_passed

OPEN = 'open'          # the pick week leads; nothing older is unfinished
LOCKED = 'locked'      # the reveal week leads, unfinished, nothing open yet
OVERLAP = 'overlap'    # the reveal week leads, unfinished, the pick week is open
VERDICT = 'verdict'    # the reveal week leads, complete, nothing open yet
NONE = 'none'          # no week to talk about


def _has_games(week) -> bool:
    return CfbGame.query.filter_by(week_id=week.id).count() > 0


def reveal_week():
    """The latest week whose deadline has passed and that has games."""
    weeks = CfbWeek.query.order_by(CfbWeek.week_number.desc()).all()
    for week in weeks:
        if deadline_has_passed(week.deadline) and _has_games(week):
            return week
    return None


def pick_week():
    """The active week while its deadline is ahead; None otherwise."""
    week = CfbWeek.query.filter_by(is_active=True).first()
    if week is None or deadline_has_passed(week.deadline):
        return None
    return week


def latest_complete_week():
    """The highest-numbered complete week (the lounge's aftermath fallback)."""
    return (CfbWeek.query.filter_by(is_complete=True)
            .order_by(CfbWeek.week_number.desc()).first())


def pending_games(week) -> list:
    """The week's unsettled games in kickoff order (DQ-4: ``is_settled``,
    never ``home_team_won is not None`` alone)."""
    games = [g for g in CfbGame.query.filter_by(week_id=week.id).all()
             if not g.is_settled]
    games.sort(key=lambda g: (g.game_time is None, g.game_time or datetime.min))
    return games


@dataclass
class RoomWeeks:
    """What the room (and the lounge) says about the week, resolved once."""
    state: str
    lead: CfbWeek | None
    pick: CfbWeek | None
    reveal: CfbWeek | None
    pending: list = field(default_factory=list)
    # The standings column names the reveal week under a different week's
    # call (both ``overlap`` and the ordinary Tue–Sat ``open``): one
    # factual note says so.
    note: bool = False


def room_weeks() -> RoomWeeks:
    """Resolve the lead, then derive the state from the lead itself."""
    reveal = reveal_week()
    pick = pick_week()
    note = bool(reveal is not None and pick is not None
                and reveal.id != pick.id)

    if reveal is not None and not reveal.is_complete:
        state = OVERLAP if pick is not None else LOCKED
        return RoomWeeks(state, reveal, pick, reveal, pending_games(reveal),
                         note)
    if pick is not None:
        return RoomWeeks(OPEN, pick, pick, reveal, [], note)
    if reveal is not None:
        return RoomWeeks(VERDICT, reveal, None, reveal, [], False)

    # Degenerate: an active week past its deadline with no games (nobody's
    # reveal week, nobody's pick week). It still has to render.
    active = CfbWeek.query.filter_by(is_active=True).first()
    if active is not None:
        state = VERDICT if active.is_complete else LOCKED
        return RoomWeeks(state, active, None, None, pending_games(active),
                         False)
    latest = latest_complete_week()
    if latest is not None:
        return RoomWeeks(VERDICT, latest, None, None, [], False)
    return RoomWeeks(NONE, None, None, None, [], False)
