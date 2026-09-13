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
  controls. For the viewer's OWN card it reads their at-most-nine picks
  (``sheets.viewer_marks``) — the sheet's week-wide ``locked_game_ids`` scan
  stays in the room.

The leaderboard (Brad, 2026-09-12): the panel now carries a standings board,
like the survivor section. The earlier doctrine kept "standings gravity on the
ledger page" and barred ``season_ledger()`` here; Brad overruled it — a member
who lands on the club door wants to see where the field stands. The board reads
the weekly live record (``sheets.all_sheets``) once >=3 members have a final,
and otherwise the season ledger (``season_pass.season_ledger``); both are
read-only, top-3 + a you-row, so the lounge summarizes the ledger without
becoming it. The "Full standings" link is always one tap to the room.

Read-only by contract: this module must never import the writer services
(deadline_pass, grading_pass, importer, scores) — it is imported by
``games/registry.py`` at boot and runs on every lounge render.
``all_sheets`` and ``season_ledger`` are pure reads and are permitted.

Datetimes handed to templates are naive UTC (the D6 column form); the Jinja
``ct`` filter is the render boundary, exactly as the room's templates do it.
"""
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import func, select

from extensions import db
from games.docket.models import (
    DocketEnrollment,
    DocketGame,
    DocketTiebreakerPrediction,
    DocketWeekResult,
)
from games.docket.services import picks as picks_service
from games.docket.services import weeks
from games.docket.services.enrollment import get_enrollment
from games.docket.services.grading.snapshots import SCORING_SLOTS
from games.docket.services.reminders import outstanding
from games.docket.services.season_pass import season_ledger
from games.docket.services.sheets import (
    all_sheets,
    marks_tally,
    record_label,
    viewer_marks,
)
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


# The season's enrollment deadline: self-serve joining closes Sat Sep 5 2026
# 11:00 AM CT (16:00 UTC; CDT is UTC-5) — the shared club cutoff (ADR-050),
# the same instant as CFB's ENROLLMENT_DEADLINE_UTC. Pinned as a season
# constant, NOT derived from deadline_utc(1): when the weekly pick deadline
# moved to Sunday 12:00 PM CT (Brad, 2026-09-09) the join cutoff deliberately
# stayed Saturday, so the two are no longer the same instant. Equality with
# the CFB constant is locked in tests. A literal, so the window resolves
# identically against empty tables.
ENROLLMENT_DEADLINE_UTC = datetime(2026, 9, 5, 16, 0, tzinfo=UTC)


def join_window_open() -> bool:
    """Whether self-serve enrollment is still open (Brad's ruling, 2026-08-18):
    the shared enrollment deadline (Sat Sep 5, 11:00 AM CT) closes joining for
    the season. Late membership is granted by the Commish through admin
    enrollment, never through /docket/join."""
    return now_utc() < ENROLLMENT_DEADLINE_UTC


# Roster-count display floor (design review 2026-08-18) — mirrored in the
# CFB lounge service; a shared-value test locks the two floors together.
ROSTER_COUNT_FLOOR = 6


def build_lounge_context(user: Any, state: DocketLoungeState | None) -> dict:
    """Per-state lounge panel data. state=None is the logged-out surface."""
    if state is None:
        total_enrolled = _total_enrolled()
        return {
            'total_enrolled': total_enrolled,
            'roster_count': (total_enrolled
                             if total_enrolled >= ROSTER_COUNT_FLOOR else 0),
        }

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
        ctx.update(_context_post(user, is_enrolled))
    return ctx


def _total_enrolled() -> int:
    return db.session.scalar(
        select(func.count(DocketEnrollment.id))
        .filter_by(season_year=weeks.SEASON_YEAR)
    )


def _context_pre() -> dict:
    """Before the Week 1 boundary: the docket has not convened yet. The
    court line carries the weekly cadence (dateless); the panel body owns
    the convening date, once.

    The posted branch (design review 2026-08-19): once a future week is
    imported with games, the room shows it read-only (the pre-season
    preview), so the panel must say posted-for-reading instead of promising
    a post that already happened. Count-only existence read — the games
    themselves stay in the room, per the module contract above."""
    posted_week_number = None
    upcoming = picks_service.upcoming_week()
    if upcoming is not None and db.session.scalar(
        select(func.count(DocketGame.id)).filter_by(week_id=upcoming.id)
    ):
        posted_week_number = upcoming.week_number
    return {
        'court_line': 'Sheets due Sundays · 12:00 PM CT',
        'game_tile_label': 'OPENS · SEP 1',
        # Naive UTC; templates render these through the ct filter.
        'first_deadline_at': to_naive_utc(weeks.deadline_utc(1)),
        'court_convenes_at': to_naive_utc(weeks.boundary_utc(1)),
        'posted_week_number': posted_week_number,
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

    if is_enrolled:
        if week is not None and beat in ('open', 'closed'):
            # Closed carries the same facts as open (bolder pass 2026-09-12):
            # the board and the record keep painting while verdicts land.
            ctx['progress'] = _sheet_progress(user.id, week, now)
        elif week is not None and beat == 'adjourned':
            ctx['result'] = _week_result(user.id, week, now)
        # The standings board (Brad, 2026-09-12): weekly while the week is
        # live and >=3 members have a final; the season ledger otherwise
        # (including between weeks). None when neither can be ranked yet.
        ctx['leaderboard'] = _leaderboard(user, beat, week, now)
    return ctx


def _context_post(user, is_enrolled: bool) -> dict:
    """After Week 19: the season is a record. The board shows the final
    season standings for a member."""
    return {
        'season_complete': True,
        'court_line': 'The season ledger is closed',
        'game_tile_label': 'SEASON CLOSED',
        'leaderboard': _season_leaderboard(user) if is_enrolled else None,
    }


def _sheet_progress(user_id: int, week, now) -> dict:
    """The Clerk's-Ledger facts for the lounge card, from two cheap queries.

    Deliberately NOT ``picks.sheet_state``: its third query loads every game
    of the week purely to compute ``locked_game_ids``, which a summary card
    never renders. The viewer's ≤9 picks joined to their own games
    (``viewer_marks``) and the prediction row are the whole read; the board
    paints each slot's state and the record is the tally of its finals.
    ``outstanding`` is the room's own phrasing (one prose SSoT with the
    reminder emails); it only inspects ``is None`` on best/prediction.
    """
    marks = viewer_marks(user_id, week, now)
    scoring_count = sum(1 for m in marks if m.held and not m.is_reserve)
    best_named = any(m.is_best for m in marks if m.held)
    backup_held = any(m.held and m.is_reserve for m in marks)
    prediction = db.session.scalar(
        select(DocketTiebreakerPrediction.prediction_tenths)
        .filter_by(user_id=user_id, week_id=week.id)
    )
    tally = marks_tally(marks)
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
        'marks': marks,
        'tally': tally,
        'record': record_label(tally) if tally is not None else None,
        'board_label': _board_label(marks, tally),
    }


def _board_label(marks, tally) -> str:
    """The board's text equivalent (role="img"): the record once a case is
    final, the held count before; then the x2 slot and the reserve."""
    held = sum(1 for m in marks if m.held and not m.is_reserve)
    if tally is None:
        parts = [f'{held} of {SCORING_SLOTS} sides held']
    else:
        parts = [f'{tally.wins} win{"" if tally.wins == 1 else "s"}, '
                 f'{tally.losses} loss{"" if tally.losses == 1 else "es"}']
        if tally.pushes:
            parts[0] += f', {tally.pushes} mistrial{"" if tally.pushes == 1 else "s"}'
        if tally.pending:
            parts.append(f'{tally.pending} to play')
    in_play = sum(1 for m in marks if m.in_play and not m.is_reserve)
    if in_play:
        parts.append(f'{in_play} in play')
    best = next((m for m in marks if m.held and m.is_best), None)
    if best is not None:
        parts.append(f'x2 on slot {best.slot}')
    if any(m.held and m.is_reserve for m in marks):
        parts.append('reserve held')
    return '; '.join(parts)


def _week_result(user_id: int, week, now) -> dict | None:
    """The viewer's graded line for the week, or None when absent, with
    the final board and its record so the adjourned card keeps the shape."""
    result = db.session.scalar(
        select(DocketWeekResult).filter_by(user_id=user_id, week_id=week.id)
    )
    if result is None:
        return None
    marks = viewer_marks(user_id, week, now)
    tally = marks_tally(marks)
    return {
        'points_label': f'{result.points:.1f}',
        'wins': result.wins,
        'marks': marks,
        'tally': tally,
        'record': record_label(tally) if tally is not None else None,
        'board_label': _board_label(marks, tally),
    }


# The standings board (Brad, 2026-09-12). The lounge shows the field, like the
# survivor section: top-3 plus a you-row when the viewer ranks below it.
LEADERBOARD_TOP = 3
# The weekly board needs enough of the field to have played to be worth showing;
# under this many finals it defers to the season ledger.
WEEKLY_MIN_SCORED = 3


def _leaderboard(user, beat, week, now) -> dict | None:
    """The panel's standings board: the weekly live record once the week is
    in play and >=3 members have a final, else the season ledger. None when
    neither can be ranked (early Week 1, nothing final and nothing graded)."""
    if week is not None and beat in ('open', 'closed'):
        weekly = _weekly_leaderboard(user, week, now)
        if weekly is not None:
            return weekly
    return _season_leaderboard(user)


def _weekly_leaderboard(user, week, now) -> dict | None:
    """This week's live record board, or None until >=3 members have a final.

    Ranked by live record (wins, then fewer losses, then more sides held),
    stable over the all_sheets name order so equal records read alphabetically
    — the same key the room's All Sheets record sort uses. Marks only, never a
    point: no points post before the week grades (§7.13)."""
    board = all_sheets(week, now)
    if sum(1 for m in board.members if m.tally is not None) < WEEKLY_MIN_SCORED:
        return None

    def key(m):
        t = m.tally
        return (-(t.wins if t else 0), t.losses if t else 0, -m.held_count)

    ordered = sorted(board.members, key=key)
    entries = []
    prev_key = None
    rank = 0
    for i, m in enumerate(ordered):
        this_key = key(m)
        if this_key != prev_key:
            rank = i + 1
            prev_key = this_key
        t = m.tally
        entries.append({
            'rank': rank,
            'user_id': m.user_id,
            'name': m.enrollment.get_display_name(),
            'avatar': m.enrollment.user.get_avatar(),
            'record': record_label(t) if t is not None else None,
            'wins': t.wins if t is not None else 0,
            'losses': t.losses if t is not None else 0,
            'pushes': t.pushes if t is not None else 0,
            'pending': t.pending if t is not None else m.held_count,
            # Distinguishes a member holding nothing yet (tagline "Nothing held
            # yet") from one whose sides are all final ("All played") — both
            # read pending 0.
            'held': m.held_count,
        })
    return {
        'mode': 'weekly',
        'title': 'This week',
        'rows': _top_and_you(entries, user.id),
    }


def _season_leaderboard(user) -> dict | None:
    """The season ledger board, or None before any week grades."""
    ledger = season_ledger()
    if not ledger.is_graded:
        return None
    entries = [
        {
            'rank': row.standing.rank,
            'user_id': row.enrollment.user_id,
            'name': row.enrollment.get_display_name(),
            'avatar': row.enrollment.user.get_avatar(),
            'points': row.standing.total_points,
            'wins': row.standing.wins,
        }
        for row in ledger.rows          # already (rank, name)-ordered
    ]
    return {
        'mode': 'season',
        'title': 'The season, so far',
        'rows': _top_and_you(entries, user.id),
    }


def _top_and_you(entries: list[dict], viewer_user_id: int) -> list[dict]:
    """Top-N rows plus the viewer's own row (with a separator) when it ranks
    below the cut — the survivor standings shape (`_standings_rows`)."""
    top = entries[:LEADERBOARD_TOP]
    rows = [{**e, 'is_you': e['user_id'] == viewer_user_id,
             'separator_above': False} for e in top]
    if all(e['user_id'] != viewer_user_id for e in top):
        you = next((e for e in entries
                    if e['user_id'] == viewer_user_id), None)
        if you is not None:
            rows.append({**you, 'is_you': True, 'separator_above': True})
    return rows
