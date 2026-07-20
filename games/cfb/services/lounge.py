"""CFB lounge state resolver + context builders (C2 slice 3+, Phase 4).

The CFB half of the registry's lounge seam (transition plan section 5):

- ``cfb_lounge_state()`` -- the ``GameRegistryEntry.lounge_state`` resolver,
  implementing the C1 design spec's state table (spec section 2.1).
- ``build_lounge_context(user, state)`` -- the ``lounge_context`` builder,
  assembling per-state data for the partials in
  games/cfb/templates/cfb/lounge/ (spec section 9 data contract).

Everything here is dead on prod until the Phase 5 changeover flip: CFB
stays coming_soon/unfeatured, so ``lounge_game()`` never selects it. The
live and post contexts raise until their Phase 4 slices ship -- failing
visibly beats rendering a half-built lounge if the flip ever outran them.

Not to be confused with the CFB *room* (games/cfb/routes.py and its
templates) -- the lounge summarizes, the room completes (DESIGN.md
section 3.6). The WC imports below are the ruled C1 design: the farewell
strip (spec 3.5) and the archived WC tile (spec 3.4) read frozen 2026
archive facts through the WC lounge module's helpers.
"""
from datetime import date
from typing import Any, Literal

from flask import current_app

from extensions import db
from games.cfb.constants import SEASON_SCHEDULE
from games.cfb.models import CfbEnrollment, CfbWeek
from games.cfb.utils import get_current_time, make_aware
from games.worldcup.services import lounge as worldcup_lounge

CfbLoungeState = Literal['pre', 'live', 'post']

# The championship week -- the highest special week in the locked schedule
# (week 19, CFP National Championship). Its completion with >1 active
# player is the tiebreak-conclusion trigger for 'post'.
FINAL_WEEK_NUMBER = max(SEASON_SCHEDULE['special_weeks'])


def _season_year() -> int:
    return current_app.config.get('CFB_SEASON_YEAR', 2026)


def _week_1_kickoff() -> date:
    return date.fromisoformat(SEASON_SCHEDULE['week_1_start'])


def cfb_lounge_state() -> CfbLoungeState:
    """Resolve the CFB lounge state for an authenticated viewer.

    C1 spec section 2.1:

    pre  -- season not started: no week has been activated or completed
    live -- any week active or completed, season not concluded
    post -- a sole survivor exists (the room's championship gate: one
            active enrollment with at least one eliminated), OR the final
            playoff week is complete with more than one active player
            (season concluded by cumulative-spread tiebreak)

    'post' is checked first: a sole survivor in week 9 ends the season
    then, even while a week is nominally active.
    """
    season_year = _season_year()
    active = CfbEnrollment.query.filter_by(
        season_year=season_year, is_eliminated=False
    ).count()
    eliminated = CfbEnrollment.query.filter_by(
        season_year=season_year, is_eliminated=True
    ).count()
    if active == 1 and eliminated > 0:
        return 'post'
    final_week_complete = CfbWeek.query.filter(
        CfbWeek.week_number >= FINAL_WEEK_NUMBER,
        CfbWeek.is_complete.is_(True),
    ).first() is not None
    if final_week_complete and active > 1:
        return 'post'
    season_started = CfbWeek.query.filter(
        db.or_(CfbWeek.is_active.is_(True), CfbWeek.is_complete.is_(True))
    ).first() is not None
    return 'live' if season_started else 'pre'


def build_lounge_context(user: Any, state: CfbLoungeState | None) -> dict:
    """Assemble the CFB contribution to the lounge context for the state.

    state=None for unauthenticated users (logged-out marketing surface).
    For authenticated users, state comes from cfb_lounge_state().
    """
    if state is None:
        return _context_out()
    enrollment = CfbEnrollment.query.filter_by(
        user_id=user.id, season_year=_season_year()
    ).first()
    if state == 'pre':
        return _context_pre(user, enrollment)
    if state == 'live':
        return _context_live(user, enrollment)
    return _context_post(user, enrollment)


def _context_out() -> dict:
    """Logged-out marketing surface -- CFB's contribution is the enrolled
    count (the registry tiles come from the core dispatcher's base)."""
    return {
        'total_enrolled': CfbEnrollment.query.filter_by(
            season_year=_season_year()
        ).count(),
    }


def _context_pre(user, enrollment) -> dict:
    """The handoff composition (C1 spec section 4.2): greet court line,
    preseason decree, WC farewell strip, tiles."""
    is_enrolled = enrollment is not None
    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )
    total_enrolled = CfbEnrollment.query.filter_by(
        season_year=_season_year()
    ).count()

    now = get_current_time()
    kickoff = _week_1_kickoff()
    days_to_kickoff = max(0, (kickoff - now.date()).days)

    # Decree countdown target: week 1's DB deadline when the row exists,
    # else the WEEK_1_START constant with first-kickoff copy (C1 3.6).
    week1 = CfbWeek.query.filter_by(week_number=1).first()
    if week1 is not None:
        deadline = make_aware(week1.deadline)
        decree_days = max(0, (deadline - now).days)
        decree_deadline_line = (
            f"Week 1 locks {deadline.strftime('%A, %b %-d, %-I:%M %p')} CT."
        )
    else:
        decree_days = days_to_kickoff
        decree_deadline_line = (
            f"First kickoff {kickoff.strftime('%A, %b %-d')}."
        )

    if days_to_kickoff == 0:
        proximity = 'first kickoff today'
    elif days_to_kickoff == 1:
        proximity = 'first kickoff in 1 day'
    else:
        proximity = f'first kickoff in {days_to_kickoff} days'
    court_line = (
        f"{now.strftime('%A')} · {total_enrolled} enrolled · {proximity}"
    )

    # WC farewell strip (C1 3.5, pre-state only per ruling 4). Frozen
    # archive facts via the WC lounge helper; an incomplete archive omits
    # the strip rather than rendering a broken line.
    farewell = None
    archive = worldcup_lounge.archive_summary(user)
    if archive is not None:
        finish = None
        if archive['viewer_finish_label'] is not None:
            finish = (
                f"You finished {archive['viewer_finish_label']} "
                f"· {archive['viewer_points']:.1f} pts"
            )
        farewell = {
            'season_year': archive['season_year'],
            'line': (
                f"{archive['champion_name']} took the Cup. "
                f"{archive['winner_name']} took the pool."
            ),
            'finish': finish,
        }

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'display_name': display_name,
        'total_enrolled': total_enrolled,
        'court_line': court_line,
        'decree_days': decree_days,
        'decree_deadline_line': decree_deadline_line,
        'farewell': farewell,
        'game_tile_label': (
            f"PRESEASON · {kickoff.strftime('%b %-d').upper()}"
        ),
        'archived_tiles': _archived_tiles(user),
    }


def _archived_tiles(user) -> list[dict]:
    """Archived-game tiles for the compact strip (C1 3.4). The WC tile is
    the permanent archive presence from season start onward (ruling 4)."""
    tile = worldcup_lounge.archived_tile(user)
    return [tile] if tile is not None else []


def _context_live(user, enrollment) -> dict:
    """Live-season lounge data (the four-beat Summons) -- next Phase 4
    slice. Raising keeps a premature changeover flip loudly broken
    instead of quietly rendering a half-built lounge."""
    raise NotImplementedError(
        'CFB live lounge context ships in a later Phase 4 slice '
        '(transition plan section 8); the changeover flip must not land '
        'before it does.'
    )


def _context_post(user, enrollment) -> dict:
    """Terminal lounge data (champion / tiebreak) -- final Phase 4 slice."""
    raise NotImplementedError(
        'CFB post lounge context ships in a later Phase 4 slice '
        '(transition plan section 8); the changeover flip must not land '
        'before it does.'
    )
