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
from games.docket.models import DocketGame, DocketWeek
from games.docket.services.importer import SPORTS, decode_payload
from utils.odds_api import OddsApiError, odds_api_get, sport_base_url

logger = logging.getLogger(__name__)

# The Odds API refuses a larger lookback on /scores.
MAX_DAYS_FROM = 3


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


def _apply_event(game, event, summary):
    """Write one event's scores onto its game.

    ``is_final`` is one-way: once a game is final it stays final even if a
    later payload reports it in progress again. An already-graded week must
    never silently fall back to ungradeable because the feed flapped, and a
    real correction still lands (the scores themselves keep updating).
    """
    home, away = _event_scores(event)
    if home is None:
        summary['no_scores'] += 1
        return
    changed = (game.home_score, game.away_score) != (home, away)
    game.home_score = home
    game.away_score = away
    if event.get('completed'):
        if not game.is_final:
            game.is_final = True
            summary['finalized'] += 1
        else:
            summary['already_final'] += 1
    else:
        summary['in_progress'] += 1
    if changed:
        summary['scores_written'] += 1


def sync_scores(week_number, days_from=MAX_DAYS_FROM) -> dict:
    """Fetch both sports' scores and write them onto one week's games.

    Per-sport failures are isolated exactly as in the importer: one sport's
    outage or bad body never costs the other its update. Events that match no
    game on this week's docket are ignored silently — every run returns the
    whole lookback window, most of which belongs to other weeks (or to CFB
    Survivor's slate).
    """
    api_key = current_app.config.get('ODDS_API_KEY', '')
    if not api_key:
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
    sports_succeeded = 0

    for sport in SPORTS:
        try:
            resp = odds_api_get(f'{sport_base_url(sport)}/scores', params={
                'apiKey': api_key,
                'daysFrom': min(days_from, MAX_DAYS_FROM),
            })
            if resp.status_code != 200:
                raise OddsApiError(f'/scores returned HTTP {resp.status_code}')
            for event in decode_payload(resp, '/scores'):
                game = games_by_event.get(event.get('id'))
                if game is None:
                    summary['unmatched'] += 1
                    continue
                _apply_event(game, event, summary)
            sports_succeeded += 1
        except (OddsApiError, ValueError) as exc:
            logger.error('Docket score sync failed for %s: %s', sport, exc)
            summary['errors'].append(f'{sport}: {exc}')

    db.session.commit()
    if summary['errors']:
        summary['status'] = 'partial' if sports_succeeded else 'error'
    return summary
