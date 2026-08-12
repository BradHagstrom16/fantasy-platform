"""
The Docket — Two-Sport Line Import (D22 import spine)
=====================================================
One import pass over both sports (NCAAF + NFL) for one docket week:

- ``/events`` (FREE) supplies schedule + kickoff identity: games are created
  keyed on ``api_event_id`` end-to-end (D22 — no curated team table, no name
  matching), and every run refreshes the LIVE kickoff column from it (D19);
  a moved kickoff logs a visible change line.
- ``/odds`` with ``markets='spreads,totals'`` (2 credits/sport/run) supplies
  lines under the D3/DQ-6 analog: the first fetch that finds a posted market
  locks it, later runs fill still-empty markets only, and a locked line is
  NEVER overwritten. A sport whose every market is already locked has
  nothing left to fill, so its /odds call is skipped outright — the free
  /events kickoff refresh still runs (``force_odds`` overrides).
- Bookmaker provenance (D17): DraftKings preferred, then the fixed fallback
  order below, then any other book alphabetically (a deterministic tail —
  never response-order-dependent). Each market walks the policy
  independently, and the winning book is recorded next to its line.

Week membership is authoritative client-side: a game belongs to the week
whose half-open [start_at, end_at) window contains its kickoff, so an event
kicking off exactly at ``end_at`` is skipped here and imported by next
week's run. Credit burn is logged by the shared client wrapper on every
call (utils/odds_api.py, D5).
"""
import logging
from datetime import datetime

from flask import current_app
from sqlalchemy import or_, select

from extensions import db
from games.docket.models import DocketGame, DocketWeek
from games.docket.services.weeks import deadline_utc, week_bounds_utc
from games.docket.utils import now_utc, to_naive_utc
from utils.odds_api import OddsApiError, odds_api_get, sport_base_url

logger = logging.getLogger(__name__)

SPORTS = ('americanfootball_ncaaf', 'americanfootball_nfl')

# D17 fixed fallback order. Books absent from this list are considered
# after it, alphabetically by key.
BOOKMAKER_PRIORITY = (
    'draftkings',
    'fanduel',
    'betmgm',
    'espnbet',
    'williamhill_us',
    'betrivers',
    'bovada',
)

_TIME_FMT = '%Y-%m-%dT%H:%M:%SZ'


def ensure_week(week_number):
    """Get or create the DocketWeek row, bounds/deadline stored naive UTC."""
    week = db.session.scalar(
        select(DocketWeek).filter_by(week_number=week_number))
    if week:
        return week
    start_aware, end_aware = week_bounds_utc(week_number)
    week = DocketWeek(
        week_number=week_number,
        start_at=to_naive_utc(start_aware),
        end_at=to_naive_utc(end_aware),
        deadline_at=to_naive_utc(deadline_utc(week_number)),
    )
    db.session.add(week)
    db.session.flush()
    return week


def decode_payload(resp, endpoint):
    """Decode + shape-check a 200 response body.

    The Odds API's list endpoints return a JSON array of objects; anything
    else (an error envelope under HTTP 200, a stray scalar) becomes a
    per-sport OddsApiError so one sport's bad body can never abort the
    other sport's import mid-loop.
    """
    try:
        payload = resp.json()
    except ValueError as exc:
        raise OddsApiError(
            f'{endpoint} returned undecodable JSON: {exc}') from exc
    if not isinstance(payload, list) \
            or any(not isinstance(entry, dict) for entry in payload):
        raise OddsApiError(f'{endpoint} returned an unexpected payload shape '
                           f'({type(payload).__name__})')
    return payload


def _parse_kickoff(commence_time):
    """API commence_time (ISO, Z suffix) → naive UTC, or None if unusable."""
    if not commence_time:
        return None
    try:
        aware = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
    except ValueError:
        logger.warning('Unparseable commence_time: %r', commence_time)
        return None
    return to_naive_utc(aware)


def _provenance_order(bookmakers):
    prio = {key: i for i, key in enumerate(BOOKMAKER_PRIORITY)}
    return sorted(bookmakers, key=lambda bm: (
        prio.get(bm.get('key'), len(BOOKMAKER_PRIORITY)), bm.get('key') or ''))


def _select_market(event, market_key, outcome_name):
    """First usable (point, bookmaker_key) for one market per the D17 policy.

    A book missing the market — or carrying it without a usable point for
    the wanted outcome — is passed over; the walk continues down the policy
    order. Returns (None, None) when no book carries the market.
    """
    for bm in _provenance_order(event.get('bookmakers', [])):
        for market in bm.get('markets', []):
            if market.get('key') != market_key:
                continue
            for outcome in market.get('outcomes', []):
                if outcome.get('name') == outcome_name \
                        and outcome.get('point') is not None:
                    return float(outcome['point']), bm.get('key')
    return None, None


def _sync_events(week, sport, events, summary):
    """Create missing games; refresh live kickoffs on existing ones (D19)."""
    for event in events:
        event_id = event.get('id')
        kickoff = _parse_kickoff(event.get('commence_time'))
        if not event_id or kickoff is None:
            summary['skipped_malformed'] += 1
            continue
        in_window = week.start_at <= kickoff < week.end_at

        game = db.session.scalar(
            select(DocketGame).filter_by(api_event_id=event_id))
        if game is None:
            if not in_window:
                summary['skipped_out_of_window'] += 1
                continue
            db.session.add(DocketGame(
                week_id=week.id,
                sport=sport,
                api_event_id=event_id,
                home_team=event.get('home_team', ''),
                away_team=event.get('away_team', ''),
                kickoff=kickoff,
            ))
            summary['created'] += 1
            continue

        if game.kickoff != kickoff:
            # D19 change row: the live kickoff moved. A move out of the
            # week window is a No Contest candidate for the admin — the
            # game keeps its docket week either way (postponed beyond the
            # week ⇒ NC by ruling, not reassignment).
            level = logger.warning if not in_window else logger.info
            level('Kickoff moved for %s @ %s (%s): %s -> %s%s',
                  game.away_team, game.home_team, event_id,
                  game.kickoff, kickoff,
                  '' if in_window else ' — NOW OUTSIDE ITS WEEK WINDOW')
            game.kickoff = kickoff
            summary['kickoff_moved'] += 1


def _has_open_market(week, sport):
    """Does this sport still have an unlocked market on this week's docket?

    The /odds call costs 2 credits per sport per run against a 500/month
    budget, and once every market of a sport is locked the D3 gap-fill has
    nothing left to do — a locked line is never overwritten. A sport with no
    games on this week's docket answers False for the same reason, which is
    what keeps the empty NFL slate from taxing every CFB Week 1 run. Called
    AFTER the events sync so a game created by this very run still triggers
    the fetch it needs.
    """
    return db.session.scalar(
        select(DocketGame.id)
        .filter_by(week_id=week.id, sport=sport)
        .filter(or_(DocketGame.spread_locked_at.is_(None),
                    DocketGame.total_locked_at.is_(None)))
        .limit(1)) is not None


def _apply_odds(events, now_naive, summary):
    """Lock still-open markets per DQ-6 + D17; never touch a locked one."""
    for event in events:
        game = db.session.scalar(
            select(DocketGame).filter_by(api_event_id=event.get('id')))
        if game is None:
            summary['unmatched_odds'] += 1
            continue
        if game.spread_locked_at is None:
            point, book = _select_market(event, 'spreads',
                                         event.get('home_team'))
            if point is not None:
                game.home_spread = point
                game.spread_book = book
                game.spread_locked_at = now_naive
                summary['spreads_locked'] += 1
        if game.total_locked_at is None:
            point, book = _select_market(event, 'totals', 'Over')
            if point is not None:
                game.total_points = point
                game.total_book = book
                game.total_locked_at = now_naive
                summary['totals_locked'] += 1


def import_week(week_number, force_odds=False):
    """Run the two-sport /events + /odds import for one docket week.

    Per-sport failures are isolated: one sport erroring never blocks the
    other's import. Returns a summary dict; ``errors`` lists any sport-level
    failures.

    ``force_odds`` re-fetches /odds even for a sport whose markets are all
    locked — the escape hatch for the skip that keeps late-week gap-fill
    runs from spending credits on a docket with nothing left to fill.
    """
    api_key = current_app.config.get('ODDS_API_KEY', '')
    if not api_key:
        logger.warning('ODDS_API_KEY not configured; cannot import games.')
        return {'status': 'error', 'errors': ['ODDS_API_KEY not configured']}

    week = ensure_week(week_number)
    start_aware, end_aware = week_bounds_utc(week_number)
    window = {
        'commenceTimeFrom': start_aware.strftime(_TIME_FMT),
        'commenceTimeTo': end_aware.strftime(_TIME_FMT),
    }
    summary = {
        'status': 'ok', 'week_number': week_number,
        'created': 0, 'kickoff_moved': 0,
        'spreads_locked': 0, 'totals_locked': 0,
        'skipped_out_of_window': 0, 'skipped_malformed': 0,
        'unmatched_odds': 0, 'odds_skipped': [], 'errors': [],
    }
    now_naive = to_naive_utc(now_utc())
    sports_succeeded = 0

    for sport in SPORTS:
        base = sport_base_url(sport)
        try:
            resp = odds_api_get(f'{base}/events',
                                params={'apiKey': api_key, **window})
            if resp.status_code != 200:
                raise OddsApiError(f'/events returned HTTP {resp.status_code}')
            _sync_events(week, sport, decode_payload(resp, '/events'),
                         summary)
            # Flush so games created moments ago are visible to the
            # open-market check below (autoflush would cover it; being
            # explicit keeps the credit decision from riding on a default).
            db.session.flush()

            if not force_odds and not _has_open_market(week, sport):
                logger.info('All %s markets are locked for week %s — '
                            'skipping the /odds fetch (2 credits saved).',
                            sport, week_number)
                summary['odds_skipped'].append(sport)
                sports_succeeded += 1
                continue

            resp = odds_api_get(f'{base}/odds', params={
                'apiKey': api_key,
                'regions': 'us',
                'markets': 'spreads,totals',
                'oddsFormat': 'american',
                **window,
            })
            if resp.status_code != 200:
                raise OddsApiError(f'/odds returned HTTP {resp.status_code}')
            _apply_odds(decode_payload(resp, '/odds'), now_naive, summary)
            sports_succeeded += 1
        except (OddsApiError, ValueError) as exc:
            logger.error('Docket import failed for %s: %s', sport, exc)
            summary['errors'].append(f'{sport}: {exc}')

    db.session.commit()
    if summary['errors']:
        # A sport that completed keeps its work regardless of the created
        # count (a re-run that creates 0 new games still succeeded).
        summary['status'] = 'partial' if sports_succeeded else 'error'
    return summary
