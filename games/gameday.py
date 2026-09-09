"""
The game-day scores pass (ADR-063)
==================================
Same-evening finals for CFB Survivor and The Docket on ONE `/scores` call
per sport. The daily passes (`cfb-scores`, `docket-scores`) are untouched:
they remain the safety net, the only source of admin mail, and the only
place the ADR-062 open retry runs. This pass exists so a Saturday noon
verdict lands Saturday afternoon instead of Sunday 08:00.

Cross-game on purpose (the games/registry.py precedent): each game exposes a
``GameDayConsumer`` — a ``wants(sport)`` guard and an ``apply(events)``
writer — and this module owns the fetch. That reverses D5-eng's "share the
client, not the fetch runs" for this pass only; the credit arithmetic that
justified it is in docs/designs/same-evening-finals.md.

Spend discipline, in order:

1. **Nothing to do is free.** A sport is fetched only when a consumer says a
   tracked game of that sport kicked off between GAME_COULD_HAVE_ENDED and
   GAME_DAY_WINDOW ago and is not yet settled. An hourly timer over a quiet
   Tuesday costs zero credits.
2. **The floor protects grading.** A free ``/sports`` probe reads the
   account's remaining credits; below GAME_DAY_CREDIT_FLOOR the pass stands
   down so the daily passes can never be starved late in a heavy month.
3. **One call per sport, any ``daysFrom``.** The endpoint bills 2 credits
   for any lookback, so the widest (3) is used: the same call also catches
   anything the morning pass missed.

Consumers are isolated: one game's failure rolls the session back and the
next consumer still writes. Any fetch or consumer error makes the pass
report ``error`` (the CLI exits 1) only after every consumer has had its
turn.
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from flask import current_app

from extensions import db
from games.docket.services.importer import decode_payload
from utils.odds_api import (
    OddsApiError,
    odds_api_get,
    odds_credits_remaining,
    sport_base_url,
)

logger = logging.getLogger(__name__)

SPORTS = ('americanfootball_ncaaf', 'americanfootball_nfl')

# A game that kicked off less than this long ago cannot have ended; one that
# kicked off more than GAME_DAY_WINDOW ago is the daily pass's problem (a
# postponed, cancelled or unmatched game must not be polled hourly forever).
GAME_COULD_HAVE_ENDED = timedelta(hours=3)
GAME_DAY_WINDOW = timedelta(hours=12)

# Below this many remaining credits the game-day pass stands down for the
# month. The daily passes need roughly 6 credits a day.
GAME_DAY_CREDIT_FLOOR = 100

# Any value costs 2 credits; the widest window is free insurance.
DAYS_FROM = 3


@dataclass(frozen=True)
class GameDayConsumer:
    """One game's half of the seam.

    ``wants(sport_key)``: could a tracked game of this sport have ended and
    not yet be settled? Decides whether the sport is fetched at all.

    ``apply({sport_key: decoded events})``: write the finals through the
    game's own scores path. Receives only the sports it wanted that were
    actually fetched; raises on failure.
    """
    slug: str
    wants: Callable[[str], bool]
    apply: Callable[[dict[str, list]], dict]


def _consumers():
    """Imported lazily: each consumer module imports this one for the
    dataclass and the window constants."""
    from games.cfb.services.gameday import CONSUMER as cfb
    from games.docket.services.gameday import CONSUMER as docket
    return (cfb, docket)


def fetch_scores(sport, api_key):
    """One `/scores` call for ``sport`` (2 credits), decoded and shape-checked."""
    resp = odds_api_get(f'{sport_base_url(sport)}/scores', params={
        'apiKey': api_key,
        'daysFrom': DAYS_FROM,
    })
    if resp.status_code != 200:
        raise OddsApiError(f'/scores returned HTTP {resp.status_code}')
    return decode_payload(resp, '/scores')


def run_game_day() -> dict:
    """Run one game-day tick. Returns a summary; never raises for a game's
    failure (those are collected into ``errors``)."""
    consumers = _consumers()
    summary = {'status': 'idle', 'wanted': [], 'fetched': [], 'errors': [],
               'applied': {}, 'remaining': None}

    wanted = {}
    for sport in SPORTS:
        takers = [c for c in consumers if c.wants(sport)]
        if takers:
            wanted[sport] = takers
    summary['wanted'] = sorted(wanted)
    if not wanted:
        return summary

    api_key = current_app.config.get('ODDS_API_KEY', '')
    if not api_key:
        summary['status'] = 'error'
        summary['errors'].append('ODDS_API_KEY not configured')
        return summary

    remaining = odds_credits_remaining(api_key)
    summary['remaining'] = remaining
    if remaining is not None and remaining < GAME_DAY_CREDIT_FLOOR:
        logger.warning('Game-day pass standing down: %s credits remaining '
                       '(floor %s); the daily passes keep grading',
                       remaining, GAME_DAY_CREDIT_FLOOR)
        summary['status'] = 'floor'
        return summary

    events = {}
    for sport in wanted:
        try:
            events[sport] = fetch_scores(sport, api_key)
            summary['fetched'].append(sport)
        except (OddsApiError, ValueError) as exc:
            logger.error('Game-day fetch failed for %s: %s', sport, exc)
            summary['errors'].append(f'{sport}: {exc}')

    for consumer in consumers:
        mine = {sport: payload for sport, payload in events.items()
                if any(c is consumer for c in wanted[sport])}
        if not mine:
            continue
        try:
            summary['applied'][consumer.slug] = consumer.apply(mine)
        # Deliberately broad: one game's failure must never keep the other
        # game's finals from landing, and the session must be clean before
        # the next consumer commits.
        except Exception as exc:
            db.session.rollback()
            logger.exception('Game-day apply failed for %s', consumer.slug)
            summary['errors'].append(f'{consumer.slug}: {exc}')

    summary['status'] = 'error' if summary['errors'] else 'ok'
    return summary
