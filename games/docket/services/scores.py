"""The Docket — Two-Sport Score Sync (D12)

One `/scores` call per sport per run through the shared platform client, which
logs `x-requests-remaining` on every response (D5-eng). **Cost: 2 credits per
sport per run** — the endpoint is billed at 2 whenever `daysFrom` is set, and
it takes one sport per request, so a run is 4 credits combined.

`daysFrom` caps at 3. That cap is the whole reason D12's cadence carries
midweek runs (Tue ~05:15 CT post-MNF, then Wed through Mon at 08:00 CT —
Fri and Sat joined 2026-09-04 so All Sheets shows Thursday's and Friday's
finals the next morning — daily through the December window): a
weekend-only schedule would silently never see the Tuesday and Wednesday
CFB games that D3 deliberately keeps pickable.

Matching is on ``api_event_id`` alone (D22 — game identity is the Odds API
event id end-to-end). CFB Survivor's team-name fallback is deliberately not
reproduced here: The Docket imports the full two-sport slate from the same
API that reports these scores, so a miss means a genuine identity problem
worth surfacing, not a name that needs mapping.

Two columns this module must never touch: ``no_contest`` is an admin ruling
(models.py), and ``is_final`` is one-way — see ``_apply_event``.
"""
import logging

from flask import current_app
from sqlalchemy import select

from extensions import db
from games.docket.models import DocketGame, DocketPick, DocketWeek
from games.docket.services.importer import SPORTS, decode_payload
from utils.odds_api import OddsApiError, odds_api_get, sport_base_url

logger = logging.getLogger(__name__)

# The Odds API refuses a larger lookback on /scores.
MAX_DAYS_FROM = 3

# Slots 1-8 score; slot 9 is the dormant reserve (D6) — never buzzed.
_SCORING_SLOT_MAX = 8


def _capture_side_results(game):
    """Snapshot each scoring side's grading result from the game's CURRENT
    (pre-overwrite) scores, so a correction can later push only the sides whose
    result actually flips. Called only for a changed, already-final game (eng
    review 9A), so an unchanged final game does no grading reads.

    Returns {pick_id: result_value_or_None}. sheets is imported lazily to keep
    the score sync's top-level import graph light.
    """
    from games.docket.services.sheets import _result, _snapshot
    snap = _snapshot(game)
    picks = db.session.scalars(
        select(DocketPick).filter_by(game_id=game.id)
        .where(DocketPick.slot <= _SCORING_SLOT_MAX)).all()
    return {p.id: _result(p, game, snap) for p in picks}


def _event_scores(event):
    """(home_score, away_score) from an event's scores array, or (None, None).

    The API reports scores as a list of {name, score} keyed by team NAME,
    which is the one place names still matter — inside an event already
    matched by id. A partial or unparseable pair yields nothing rather than
    half a score: grading reads both or neither (GameSnapshot's both-or-
    neither contract), and a phantom 0 would grade as a real result.
    """
    home = away = None
    for entry in event.get('scores') or []:
        try:
            value = int(entry.get('score'))
        except (TypeError, ValueError):
            continue
        if entry.get('name') == event.get('home_team'):
            home = value
        elif entry.get('name') == event.get('away_team'):
            away = value
    if home is None or away is None:
        return None, None
    return home, away


def _apply_event(game, event, summary, verdicts):
    """Write one event's scores onto its game.

    ``is_final`` is one-way: once a game is final it stays final even if a
    later payload reports it in progress again. An already-graded week must
    never silently fall back to ungradeable because the feed flapped, and a
    real correction still lands (the scores themselves keep updating).

    Appends a push verdict to ``verdicts`` when a completed event either flips
    the game final (all sides are new) or corrects an already-final game's
    scores (before-results captured pre-overwrite so the caller pushes only the
    sides that flip). Presentation-only; never affects the write.
    """
    home, away = _event_scores(event)
    if home is None:
        summary['no_scores'] += 1
        return
    changed = (game.home_score, game.away_score) != (home, away)
    old_final = game.is_final
    completed = bool(event.get('completed'))
    # Capture BEFORE the overwrite, only for a real correction to a final game.
    before = (_capture_side_results(game)
              if changed and old_final and completed else None)
    game.home_score = home
    game.away_score = away
    if completed:
        if not game.is_final:
            game.is_final = True
            summary['finalized'] += 1
            verdicts.append(
                {'game_id': game.id, 'kind': 'flipped', 'before': None})
        else:
            summary['already_final'] += 1
            if changed:
                verdicts.append(
                    {'game_id': game.id, 'kind': 'corrected', 'before': before})
    else:
        summary['in_progress'] += 1
    if changed:
        summary['scores_written'] += 1


def sync_scores(week_number, days_from=MAX_DAYS_FROM,
                events_by_sport=None) -> dict:
    """Fetch both sports' scores and write them onto one week's games.

    Per-sport failures are isolated exactly as in the importer: one sport's
    outage or bad body never costs the other its update. Events that match no
    game on this week's docket are ignored silently — every run returns the
    whole lookback window, most of which belongs to other weeks (or to CFB
    Survivor's slate).

    ``events_by_sport`` (ADR-063): decoded `/scores` payloads from the
    shared game-day pass, keyed by sport. When given, a sport PRESENT in
    the dict is applied without an HTTP call and a sport ABSENT from it is
    skipped outright — never fetched here, and neither an error nor a
    success. ``None`` fetches every sport as the daily pass always has.
    """
    api_key = current_app.config.get('ODDS_API_KEY', '')
    if not api_key and events_by_sport is None:
        logger.warning('ODDS_API_KEY not configured; cannot fetch scores.')
        return {'status': 'error', 'errors': ['ODDS_API_KEY not configured']}

    week = db.session.scalar(
        select(DocketWeek).filter_by(week_number=week_number))
    if week is None:
        return {'status': 'error',
                'errors': [f'no docket week {week_number}']}

    games_by_event = {
        g.api_event_id: g for g in db.session.scalars(
            select(DocketGame).filter_by(week_id=week.id))
    }
    summary = {
        'status': 'ok', 'week_number': week_number,
        'scores_written': 0, 'finalized': 0, 'already_final': 0,
        'in_progress': 0, 'no_scores': 0, 'unmatched': 0, 'errors': [],
    }
    # Games to buzz this run (flipped-final ∪ corrected-final); read by the
    # caller AFTER the commit via push_docket_verdicts. Additive to the summary.
    verdicts = []
    sports_succeeded = 0

    for sport in SPORTS:
        if events_by_sport is not None and sport not in events_by_sport:
            continue
        try:
            if events_by_sport is not None:
                events = events_by_sport[sport]
            else:
                resp = odds_api_get(f'{sport_base_url(sport)}/scores', params={
                    'apiKey': api_key,
                    'daysFrom': min(days_from, MAX_DAYS_FROM),
                })
                if resp.status_code != 200:
                    raise OddsApiError(f'/scores returned HTTP {resp.status_code}')
                events = decode_payload(resp, '/scores')
            for event in events:
                game = games_by_event.get(event.get('id'))
                if game is None:
                    summary['unmatched'] += 1
                    continue
                _apply_event(game, event, summary, verdicts)
            sports_succeeded += 1
        except (OddsApiError, ValueError) as exc:
            logger.error('Docket score sync failed for %s: %s', sport, exc)
            summary['errors'].append(f'{sport}: {exc}')

    db.session.commit()
    summary['verdict_games'] = verdicts
    if summary['errors']:
        summary['status'] = 'partial' if sports_succeeded else 'error'
    return summary
