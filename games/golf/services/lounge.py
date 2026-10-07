"""The Pay Sheet's lounge module: the room's presence on the club's door.

Registry-bound pair (the multi-featured seam, ADR-049):

- ``golf_lounge_state()`` resolves the season-level shell state from the
  season's schedule: no events on the book is ``pre``; every event banked is
  ``post``; a lock passed is ``live``; a schedule nobody has locked on yet is
  still ``pre``. It works against empty tables (every foreign test that
  renders ``/`` runs on them, and prod's golf tables are empty until Phase L).
- ``build_lounge_context(user, state)`` assembles the per-state panel data.
  The lounge orients and summarizes (DESIGN.md §3); the room owns the pick,
  the sheet, the board. For a member the live card reads the sheet's own
  builder (``services/sheet.py``) over rows loaded once, so the lounge says
  the same money the room does.

Read-only by contract: this module must never import the writer services
(sync, cli, reminders); it is imported by ``games/registry.py`` at boot and
runs on every lounge render. A fixed number of queries, none per row.
"""
from types import SimpleNamespace
from typing import Any, Literal

from flask import current_app
from sqlalchemy import select

from extensions import db
from games.golf.models import GolfPick
from games.golf.services.enrollment import get_enrollment
from games.golf.services.reads import (
    next_tournament,
    season_enrollments,
    season_final,
    season_tournaments,
    tournament_picks,
    tournament_results,
)
from games.golf.services.sheet import build_sheet, event_clock, live_event, week_lines
from games.golf.utils import format_lock, get_current_time, the_event

GolfLoungeState = Literal['pre', 'live', 'post']

# Roster-count display floor (design review 2026-08-18): mirrored in the CFB
# and Docket lounge services; a shared-value test locks the floors together.
ROSTER_COUNT_FLOOR = 6

# The lounge's standings board: the top of the final sheet.
TOP = 3


def _season() -> int:
    return current_app.config['SEASON_YEAR']


def golf_lounge_state() -> GolfLoungeState:
    """Season-level lounge state, from the schedule and its locks."""
    tournaments = season_tournaments(_season())
    if not tournaments:
        return 'pre'
    if season_final(tournaments):
        return 'post'
    if any(t.is_deadline_passed() for t in tournaments):
        return 'live'
    return 'pre'


def _money(amount) -> str:
    return f'${amount:,.0f}'


def _first_event(tournaments) -> dict:
    """The season's opening event and its lock, for the pre panel and the
    conversion card ("The schedule posts in January" when none is seeded)."""
    first = tournaments[0] if tournaments else None
    return {
        'first_event': first.name if first else None,
        'first_lock': (format_lock(first.pick_deadline)
                       if first is not None and first.pick_deadline else None),
    }


def build_lounge_context(user: Any, state: GolfLoungeState | None) -> dict:
    """Per-state lounge panel data. state=None is the logged-out surface."""
    season_year = _season()
    tournaments = season_tournaments(season_year)
    enrollments = season_enrollments(season_year)
    total_enrolled = len(enrollments)
    if state is None:
        return {
            'season_year': season_year,
            'total_enrolled': total_enrolled,
            'roster_count': total_enrolled if total_enrolled >= ROSTER_COUNT_FLOOR else 0,
            **_first_event(tournaments),
        }

    enrollment = get_enrollment(user.id)
    is_enrolled = enrollment is not None
    ctx = {
        'season_year': season_year,
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'viewer_mode': 'member' if is_enrolled else 'view',
        'display_name': user.get_display_name(),
        'total_enrolled': total_enrolled,
        'archived_tiles': [],
    }
    if state == 'pre':
        ctx.update(_context_pre(tournaments))
    elif state == 'live':
        ctx.update(_context_live(user, is_enrolled, tournaments, enrollments))
    else:
        ctx.update(_context_post(user, tournaments, enrollments))
    return ctx


def _context_pre(tournaments) -> dict:
    """Before the first lock: the opening event and when it locks."""
    first = tournaments[0] if tournaments else None
    return {
        'court_line': 'One golfer a week · spent once',
        'game_tile_label': (f'OPENS · {first.start_date:%b %-d}'.upper()
                            if first is not None else 'PRESEASON'),
        **_first_event(tournaments),
    }


def _context_live(user, is_enrolled: bool, tournaments, enrollments) -> dict:
    """In season: the event on the course or settling (the sheet's pencilled
    week), the next lock, and for a member their line and the leader."""
    event = live_event([t for t in tournaments if t.is_deadline_passed()])
    lines = clock = None
    if event is not None:
        results = tournament_results(event.id)
        lines = week_lines(event, tournament_picks(event.id), results)
        clock = event_clock(event, results, get_current_time())
    coming = next_tournament(tournaments)
    week = event if event is not None else coming
    week_number = week.week_number if week is not None else None

    if clock is not None and clock.on_course:
        beat, word = 'live', 'LIVE'
    elif event is not None:
        beat, word = 'settling', 'SETTLING'
    else:
        beat, word = 'open', 'PICKS OPEN'
    ctx = {
        'beat': beat,
        'week_number': week_number,
        'event_name': week.name if week is not None else None,
        'event_the': the_event(week.name) if week is not None else None,
        'court_line': (f'Week {week_number} · {beat}' if week_number
                       else 'Between events'),
        'game_tile_label': (f'WEEK {week_number} · {word}' if week_number
                            else 'IN SEASON'),
        'next_event': coming.name if coming is not None else None,
        'next_id': coming.id if coming is not None else None,
        'next_lock': (format_lock(coming.pick_deadline)
                      if coming is not None and coming.pick_deadline else None),
        'field_open': bool(coming is not None and coming.has_sufficient_field()),
    }

    sheet = build_sheet(enrollments, user.id, lines)
    if sheet.rows:
        top = sheet.rows[0]
        ctx['leader'] = {
            'name': top.user.get_display_name(),
            'money': _money(top.total),
            'projected': top.projected,
            'tied': sum(1 for r in sheet.rows if r.rank == 1) > 1,
        }
    if is_enrolled and sheet.mine is not None:
        me = sheet.mine
        pick_in = coming is not None and db.session.scalar(
            select(GolfPick.id).filter_by(user_id=user.id, tournament_id=coming.id)
        ) is not None
        ctx['mine'] = {
            'money': _money(me.total),
            'word': 'projected' if me.projected else 'banked',
            'place': me.place,
            'leads': me.rank == 1,
            'this_week': (f'{me.week.golfer.last_name}'
                          + (f' · {me.week.position}' if me.week.position else '')
                          if me.week is not None else None),
            'pick_in': pick_in,
        }
        ctx['field'] = len(sheet.rows)
        # The one ask: a pick still to make on a field that is open.
        ctx['pick_wanted'] = bool(coming is not None and ctx['field_open'] and not pick_in)
    return ctx


def _context_post(user, tournaments, enrollments) -> dict:
    """After the last event banks: the champion and the top of the sheet."""
    sheet = build_sheet(enrollments, user.id, None)
    champions = [r for r in sheet.rows if r.rank == 1]
    name = ' and '.join(r.user.get_display_name() for r in champions)
    return {
        'court_line': 'The sheet is banked',
        'game_tile_label': f'CHAMPION · {name}' if champions else 'SEASON BANKED',
        'events': len(tournaments),
        'champions': [{'name': r.user.get_display_name(), 'money': _money(r.total),
                       'user_id': r.user.id} for r in champions],
        # The Commish note's champion slot reads .display_name (CFB's shim).
        'champion_team': SimpleNamespace(display_name=name) if champions else None,
        'top': [{
            'rank': r.rank, 'rank_label': r.rank_label, 'user_id': r.user.id,
            'name': r.user.get_display_name(), 'avatar': r.user.get_avatar(),
            'money': _money(r.total), 'is_you': r.is_me,
        } for r in sheet.rows[:TOP]],
    }
