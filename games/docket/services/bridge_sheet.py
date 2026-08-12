"""
The Docket — Bridge Sheet Generator (D22)
=========================================
Emits one docket week as sheet-ready rows: the generated output goes into
the bridge Google Sheet verbatim, the Apps Script grader works off these
numbers, and the eventual bridge importer joins back on ``api_event_id``.
Rendering is the ONE sanctioned place (besides week creation) where the D6
naive-UTC columns meet America/Chicago.

Row contract is snapshot-locked by tests/test_docket_bridge_sheet.py —
change it deliberately, with the sheet, or not at all.
"""
import csv
import io
from datetime import UTC

from sqlalchemy import select

from extensions import db
from games.docket.models import DocketGame
from games.docket.services.weeks import CT

SPORT_LABELS = {
    'americanfootball_ncaaf': 'CFB',
    'americanfootball_nfl': 'NFL',
}

SHEET_COLUMNS = (
    'api_event_id', 'sport', 'away_team', 'home_team', 'kickoff_ct',
    'home_spread', 'spread_book', 'total', 'total_book', 'tiebreaker',
)


def _format_ct(kickoff_naive_utc):
    """'Sat Sep 5, 7:30 PM CT' — human kickoff for the sheet."""
    local = kickoff_naive_utc.replace(tzinfo=UTC).astimezone(CT)
    hour12 = local.hour % 12 or 12
    ampm = 'AM' if local.hour < 12 else 'PM'
    return f'{local:%a %b} {local.day}, {hour12}:{local.minute:02d} {ampm} CT'


def build_sheet_rows(week):
    """Sheet rows for one week, kickoff-ordered, every value a string.

    Unlocked markets render as empty strings — the sheet shows exactly what
    is locked, nothing provisional.
    """
    games = db.session.scalars(
        select(DocketGame).filter_by(week_id=week.id)
        .order_by(DocketGame.kickoff, DocketGame.api_event_id)).all()
    rows = []
    for game in games:
        rows.append({
            'api_event_id': game.api_event_id,
            'sport': SPORT_LABELS.get(game.sport, game.sport),
            'away_team': game.away_team,
            'home_team': game.home_team,
            'kickoff_ct': _format_ct(game.kickoff),
            'home_spread': ('' if game.home_spread is None
                            else f'{game.home_spread:+g}'),
            'spread_book': game.spread_book or '',
            'total': ('' if game.total_points is None
                      else f'{game.total_points:g}'),
            'total_book': game.total_book or '',
            'tiebreaker': 'TRUE' if game.id == week.tiebreaker_game_id else '',
        })
    return rows


def rows_to_csv(rows):
    """Rows → CSV text (header + rows), ready to paste into the sheet."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=SHEET_COLUMNS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def set_tiebreaker(week, matchup):
    """Designate the week's tiebreaker game from an 'Away @ Home' string.

    Case-insensitive substring match on both team names; exactly one game
    must match (Week 1 hand-set: 'Wisconsin @ Notre Dame'). Raises
    ValueError on no match, an ambiguous match, or a malformed matchup.

    Only the matchup-string resolution lives here. The write itself
    delegates to ``admin_ops.designate_tiebreaker``, so this CLI fallback and
    T9's admin UI share one contract: the same designation validation, the
    same prediction-clearing on a re-designation, the same notification. An
    unsound designation now rolls back instead of committing and then being
    reported, which is why the refusal arrives as a ValueError carrying the
    contract's own problem strings.
    """
    if ' @ ' not in matchup:
        raise ValueError(f"Tiebreaker must be 'Away @ Home', got {matchup!r}")
    away_q, home_q = (part.strip().lower() for part in matchup.split(' @ ', 1))
    if not away_q or not home_q:
        # A blank side substring-matches every name — on a one-game week
        # that would silently designate the wrong game.
        raise ValueError(
            f"Tiebreaker must name both teams ('Away @ Home'), got {matchup!r}")
    games = db.session.scalars(
        select(DocketGame).filter_by(week_id=week.id)).all()
    matches = [g for g in games
               if away_q in g.away_team.lower() and home_q in g.home_team.lower()]
    if len(matches) != 1:
        raise ValueError(
            f'Tiebreaker {matchup!r} matched {len(matches)} games in week '
            f'{week.week_number}; need exactly 1')
    # Imported here, not at module scope: routes.py imports this module for
    # SPORT_LABELS while the blueprint is still assembling, and admin_ops
    # reaches the grading and deadline services.
    from games.docket.services.admin_ops import (
        AdminOpError,
        designate_tiebreaker,
    )
    try:
        return designate_tiebreaker(week, matches[0].id)['game']
    except AdminOpError as exc:
        raise ValueError('; '.join([exc.message, *exc.problems])) from exc
