"""The Docket lounge module — the clerk's presence on the club's home surface.

Registry-bound pair (multi-featured seam):

- ``docket_lounge_state()`` resolves the season-level shell state from PURE
  time math (games/docket/services/weeks.py), never the database. Every
  foreign test that renders ``/`` runs against empty docket tables, and prod
  tables are empty until the deliberate Week-1 import — "week not imported
  yet" is therefore a *beat inside live* (§4.1 "Awaiting docket"), not a
  state of its own.
- ``build_lounge_context(user, state)`` assembles the per-state panel data.
  The lounge summarizes and orients (DESIGN.md §3); it never offers per-case
  controls, so nothing here loads the week's games — the sheet's
  ``locked_game_ids`` scan stays in the room. Standings gravity stays on
  the ledger page: no ``season_ledger()`` call belongs in a lounge builder.

Read-only by contract: this module must never import the writer services
(deadline_pass, grading_pass, importer, scores) — it is imported by
``games/registry.py`` at boot and runs on every lounge render.

Datetimes handed to templates are naive UTC (the D6 column form); the Jinja
``ct`` filter is the render boundary, exactly as the room's templates do it.
"""
from typing import Any, Literal

from sqlalchemy import func, select

from extensions import db
from games.docket.models import (
    DocketEnrollment,
    DocketPick,
    DocketTiebreakerPrediction,
    DocketWeekResult,
)
from games.docket.services import picks as picks_service
from games.docket.services import weeks
from games.docket.services.enrollment import get_enrollment
from games.docket.services.grading.snapshots import BACKUP_SLOT
from games.docket.services.reminders import outstanding
from games.docket.utils import now_utc, to_naive_utc

DocketLoungeState = Literal['pre', 'live', 'post']


def docket_lounge_state() -> DocketLoungeState:
    """Season-level lounge state, resolved from the week-boundary math alone."""
    now = now_utc()
    if now < weeks.boundary_utc(1):
        return 'pre'
    if weeks.week_number_for(now) is not None:
        return 'live'
    return 'post'


def join_window_open() -> bool:
    """Whether self-serve enrollment is still open (Brad's ruling, 2026-08-18):
    the Week 1 deadline (Sat Sep 5, 11:00 AM CT) closes joining for the
    season. Late membership is granted by the Commish through admin
    enrollment, never through /docket/join."""
    return now_utc() < weeks.deadline_utc(1)


def build_lounge_context(user: Any, state: DocketLoungeState | None) -> dict:
    """Per-state lounge panel data. state=None is the logged-out surface."""
    if state is None:
        return {'total_enrolled': _total_enrolled()}

    enrollment = get_enrollment(user.id)
    is_enrolled = enrollment is not None
    ctx = {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'viewer_mode': 'member' if is_enrolled else 'view',
        'display_name': (
            enrollment.get_display_name() if is_enrolled
            else user.get_display_name()
        ),
        'total_enrolled': _total_enrolled(),
        'archived_tiles': [],
    }
    if state == 'pre':
        ctx.update(_context_pre())
    elif state == 'live':
        ctx.update(_context_live(user, is_enrolled))
    else:
        ctx.update(_context_post())
    return ctx


def _total_enrolled() -> int:
    return db.session.scalar(
        select(func.count(DocketEnrollment.id))
        .filter_by(season_year=weeks.SEASON_YEAR)
    )


def _context_pre() -> dict:
    """Before the Week 1 boundary: the docket has not convened yet."""
    return {
        'court_line': 'The court convenes Tuesday, September 1',
        'game_tile_label': 'OPENS · SEP 1',
        # Naive UTC; templates render it through the ct filter.
        'first_deadline_at': to_naive_utc(weeks.deadline_utc(1)),
    }


def _context_live(user, is_enrolled: bool) -> dict:
    """In season. The weekly rhythm lives in ``beat``:

    awaiting → open → closed → adjourned  (§4.1 projected onto one week)

    ``week_no`` comes from the pure math so it is right even before the
    week row is imported (the Week-1 CFB-only window, or an import lag).
    """
    now = picks_service.now_naive()
    week_no = weeks.week_number_for(now_utc())
    week = picks_service.current_week(now)

    if week is None:
        beat = 'awaiting'
    elif now < week.deadline_at:
        beat = 'open'
    elif week.default_error_tenths is None:
        beat = 'closed'
    else:
        beat = 'adjourned'

    beat_word = {
        'awaiting': 'awaiting the docket',
        'open': 'docket open',
        'closed': 'docket closed',
        'adjourned': 'week adjourned',
    }[beat]
    ctx = {
        'beat': beat,
        'week_number': week_no,
        'court_line': f'Week {week_no} · {beat_word}',
        'game_tile_label': f'WEEK {week_no} · {beat.upper()}',
        'week_deadline_at': week.deadline_at if week is not None else None,
    }

    if is_enrolled and week is not None:
        if beat == 'open':
            ctx['progress'] = _sheet_progress(user.id, week.id)
        elif beat == 'adjourned':
            ctx['result'] = _week_result(user.id, week.id)
    return ctx


def _context_post() -> dict:
    """After Week 19: the season is a record."""
    return {
        'season_complete': True,
        'court_line': 'The season ledger is closed',
        'game_tile_label': 'SEASON CLOSED',
    }


def _sheet_progress(user_id: int, week_id: int) -> dict:
    """The Clerk's-Ledger facts for the lounge card, from two cheap queries.

    Deliberately NOT ``picks.sheet_state``: its third query loads every game
    of the week purely to compute ``locked_game_ids``, which a summary card
    never renders. The ≤9 pick rows and the prediction row are the whole
    read. ``outstanding`` is the room's own phrasing (one prose SSoT with
    the reminder emails); it only inspects ``is None`` on best/prediction.
    """
    pick_rows = db.session.execute(
        select(DocketPick.slot, DocketPick.is_best)
        .filter_by(user_id=user_id, week_id=week_id)
    ).all()
    scoring_count = sum(1 for slot, _ in pick_rows if slot != BACKUP_SLOT)
    best_named = any(is_best for _, is_best in pick_rows)
    backup_held = any(slot == BACKUP_SLOT for slot, _ in pick_rows)
    prediction = db.session.scalar(
        select(DocketTiebreakerPrediction.prediction_tenths)
        .filter_by(user_id=user_id, week_id=week_id)
    )
    return {
        'scoring_count': scoring_count,
        'best_named': best_named,
        'backup_held': backup_held,
        'prediction_recorded': prediction is not None,
        'outstanding': outstanding({
            'scoring_count': scoring_count,
            'best': True if best_named else None,
            'prediction': (picks_service.format_tenths(prediction)
                           if prediction is not None else None),
        }),
    }


def _week_result(user_id: int, week_id: int) -> dict | None:
    """The viewer's graded line for the week, or None when absent."""
    result = db.session.scalar(
        select(DocketWeekResult).filter_by(user_id=user_id, week_id=week_id)
    )
    if result is None:
        return None
    return {
        'points_label': f'{result.points:.1f}',
        'wins': result.wins,
    }
