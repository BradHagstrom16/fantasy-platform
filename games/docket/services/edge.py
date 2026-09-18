"""The Docket — Frozen-Line Value Analysis (read-only)

The Docket grades every pick against a line frozen on Tuesday (the first-posted
number, snapshotted onto DocketPick.line_value). As the week goes on the real
market moves. Where today's consensus market line has drifted away from a frozen
line, the side the market moved *toward* is now a stale number that covers more
than half the time — the edge this module surfaces.

For each game we treat the CURRENT consensus market line (the median across US
books) as the sharp estimate of the true outcome distribution: the final margin
is ~Normal(mean = -current_home_spread, sigma) and the combined total is
~Normal(mean = current_total, sigma_total). The frozen line is the number the
pool actually grades, so a side's implied cover probability is the normal mass
on the covering side of the frozen number. That probability equals the expected
points the slot earns (win 1.0 / push 0.5 / loss 0.0, since the continuous
normal splits an integer-line push symmetrically).

Everything here is read-only — no DB writes, no line mutation. It powers
`flask docket edge`. Spends Odds API credits only in fetch_current_lines
(spreads,totals,h2h across us = 3 credits/sport/run).
"""
from datetime import UTC
from statistics import NormalDist, median

from games.docket.services.importer import SPORTS, decode_payload
from games.docket.utils import now_utc
from utils.odds_api import odds_api_get, sport_base_url

_Z = NormalDist()

# Sport-specific standard deviations (points). Margin sigma drives spread cover
# probability; total sigma drives over/under. These scale the absolute numbers;
# the ranking is driven by the frozen-vs-current movement magnitude. Published
# football values: NFL margin ~13.5 / total ~10; CFB is higher-variance.
SIGMA = {
    'americanfootball_nfl':   {'margin': 13.5, 'total': 10.0},
    'americanfootball_ncaaf': {'margin': 16.0, 'total': 13.0},
}
SPORT_LABEL = {'americanfootball_ncaaf': 'CFB', 'americanfootball_nfl': 'NFL'}
# NFL spreads cluster on these; a move that crosses one is worth more than the
# raw points (flagged for the reader, not modelled).
NFL_KEY_NUMBERS = (3, 6, 7, 10, 14)


def _as_utc(dt):
    """Coerce a naive (stored naive-UTC) or aware datetime to aware UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _american_to_prob(price):
    """Vig-inclusive implied probability of an American-odds price."""
    price = float(price)
    return 100.0 / (price + 100.0) if price > 0 else (-price) / (-price + 100.0)


def consensus_from_event(event):
    """Median-across-books consensus for one Odds API event payload.

    Spread is home-perspective (the frozen convention); total is the Over
    point; the de-vigged home win probability is a moneyline cross-check.
    Returns None for any market no book carried.
    """
    home, away = event.get('home_team'), event.get('away_team')
    spread_by_book, total_by_book, home_probs = {}, {}, []
    for bm in event.get('bookmakers', []):
        key = bm.get('key')
        for mk in bm.get('markets', []):
            outcomes = mk.get('outcomes', [])
            if mk.get('key') == 'spreads':
                pt = next((o['point'] for o in outcomes
                           if o.get('name') == home and o.get('point') is not None), None)
                if pt is not None:
                    spread_by_book[key] = float(pt)
            elif mk.get('key') == 'totals':
                pt = next((o['point'] for o in outcomes
                           if o.get('name') == 'Over' and o.get('point') is not None), None)
                if pt is not None:
                    total_by_book[key] = float(pt)
            elif mk.get('key') == 'h2h':
                ph = next((o['price'] for o in outcomes if o.get('name') == home), None)
                pa = next((o['price'] for o in outcomes if o.get('name') == away), None)
                if ph is not None and pa is not None:
                    rh, ra = _american_to_prob(ph), _american_to_prob(pa)
                    if rh + ra > 0:
                        home_probs.append(rh / (rh + ra))
    spreads, totals = list(spread_by_book.values()), list(total_by_book.values())
    return {
        'home_team': home, 'away_team': away,
        'commence_time': event.get('commence_time'),
        'spread_by_book': spread_by_book, 'total_by_book': total_by_book,
        'cons_spread': median(spreads) if spreads else None,
        'cons_total': median(totals) if totals else None,
        'cons_home_winprob': median(home_probs) if home_probs else None,
        'n_books': len(spread_by_book),
    }


def _crosses_key_numbers(frozen, current):
    lo, hi = sorted((abs(frozen), abs(current)))
    return [k for k in NFL_KEY_NUMBERS if lo < k < hi]


def _spread_side(game, cons_spread):
    """Score the frozen spread against the consensus. Home covers the frozen
    number F iff the final margin exceeds -F; with margin ~ N(-C, sigma) that
    probability is Phi((F - C)/sigma). Pick whichever side clears 50%."""
    frozen = game.home_spread
    if frozen is None or cons_spread is None:
        return None
    sigma = SIGMA[game.sport]['margin']
    p_home = _Z.cdf((frozen - cons_spread) / sigma)
    if p_home >= 0.5:
        side, prob = f'{game.home_team} {frozen:+g}', p_home
    else:
        side, prob = f'{game.away_team} {-frozen:+g}', 1.0 - p_home
    keys = (_crosses_key_numbers(frozen, cons_spread)
            if game.sport == 'americanfootball_nfl' else [])
    return _side_row(game, 'spread', side, prob, frozen, cons_spread, keys)


def _total_side(game, cons_total):
    """Score the frozen total. Over the frozen number Ft hits iff the combined
    score exceeds Ft; with combined ~ N(Ct, sigma_t) that is Phi((Ct - Ft)/s)."""
    frozen = game.total_points
    if frozen is None or cons_total is None:
        return None
    sigma = SIGMA[game.sport]['total']
    p_over = _Z.cdf((cons_total - frozen) / sigma)
    side, prob = ((f'Over {frozen:g}', p_over) if p_over >= 0.5
                  else (f'Under {frozen:g}', 1.0 - p_over))
    return _side_row(game, 'total', side, prob, frozen, cons_total, [])


def _side_row(game, market, side, prob, frozen, current, key_cross):
    book = game.spread_book if market == 'spread' else game.total_book
    return {
        'sport': SPORT_LABEL[game.sport], 'sport_key': game.sport,
        'game_id': game.id, 'matchup': f'{game.away_team} @ {game.home_team}',
        'market': market, 'side': side, 'prob': prob,
        'frozen': frozen, 'current': current, 'move': current - frozen,
        'book': book, 'key_cross': key_cross,
        'kickoff': _as_utc(game.kickoff),
    }


def is_pickable(game, submit_time):
    """A side is pickable when its game has not started by submit_time and is
    not already final or ruled No Contest."""
    kickoff = _as_utc(game.kickoff)
    return (not game.is_final and not game.no_contest
            and kickoff is not None and kickoff > submit_time)


def analyze(games, consensus_by_event, submit_time):
    """Score every side of every game, ranked by cover probability desc.

    Returns (rows, unmatched): rows carry a ``pickable`` flag (games that have
    started or lack a current line are marked, not dropped, so the caller can
    report coverage); unmatched is the games with no current Odds API event.
    """
    rows, unmatched = [], []
    for game in games:
        cons = consensus_by_event.get(game.api_event_id)
        if cons is None:
            unmatched.append(game)
            continue
        pickable = is_pickable(game, submit_time)
        for row in (_spread_side(game, cons['cons_spread']),
                    _total_side(game, cons['cons_total'])):
            if row is None:
                continue
            row['pickable'] = pickable
            row['winprob'] = cons['cons_home_winprob']
            row['n_books'] = cons['n_books']
            rows.append(row)
    rows.sort(key=lambda r: r['prob'], reverse=True)
    return rows, unmatched


def fetch_current_lines(api_key, sports=SPORTS):
    """{event_id: consensus} for the given sports (impure — spends credits).

    A sport whose /odds call fails or returns a bad body is skipped with its
    error recorded, so one dark sport never blanks the other. Returns
    (consensus_by_event, errors)."""
    consensus, errors = {}, []
    for sport in sports:
        try:
            resp = odds_api_get(
                f'{sport_base_url(sport)}/odds',
                params={'apiKey': api_key, 'regions': 'us',
                        'markets': 'spreads,totals,h2h', 'oddsFormat': 'american'})
            if resp.status_code != 200:
                errors.append(f'{sport} /odds HTTP {resp.status_code}')
                continue
            for event in decode_payload(resp, f'{sport} /odds'):
                consensus[event['id']] = consensus_from_event(event)
        except Exception as exc:  # noqa: BLE001 — one sport must not abort the other
            errors.append(f'{sport}: {exc}')
    return consensus, errors


def expected_points(sheet):
    """Expected sheet score: each of the 8 scoring slots earns its cover
    probability, and the headliner (the top side) doubles. Slot 9 is the
    dormant reserve and does not score. Max 9.0."""
    scoring = sheet[:8]
    base = sum(r['prob'] for r in scoring)
    headliner = scoring[0]['prob'] if scoring else 0.0
    return base + headliner


def tiebreaker_total(week, games, consensus_by_event):
    """Sharpest predicted combined score for the designated tiebreaker game:
    its current consensus total, falling back to the frozen O/U total."""
    if week.tiebreaker_game_id is None:
        return None, None
    game = next((g for g in games if g.id == week.tiebreaker_game_id), None)
    if game is None:
        return None, None
    cons = consensus_by_event.get(game.api_event_id)
    total = (cons.get('cons_total') if cons else None) or game.total_points
    return game, total


def default_submit_time():
    """Now, honoring the DOCKET_FAKE_NOW seam in dev/testing (real time in
    prod) — the same clock the rest of the docket reads."""
    return now_utc()
