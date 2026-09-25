"""The Docket — Frozen-Line Value Analysis (read-only)

The Docket grades every pick against a line frozen on Tuesday (the first-posted
number, snapshotted onto DocketPick.line_value). As the week goes on the real
market moves. Where today's consensus market line has drifted away from a frozen
line, the side the market moved *toward* is now a stale number that covers more
than half the time — the edge this module surfaces.

For each game we treat the CURRENT consensus market as the sharp estimate of
the true outcome distribution: the final margin is ~Normal(mean = -C, sigma)
and the combined total is ~Normal(mean = Ct, sigma_total), where C and Ct are
the median across books of each book's PRICE-AWARE implied mean (a book at
-3 -125 is pricing the favorite past 3, so its implied mean is -3.4, not -3).
The frozen line is the number the pool actually grades, so a side's implied
cover probability is the normal mass on the covering side of the frozen number.
That probability equals the expected points the slot earns (win 1.0 / push 0.5
/ loss 0.0, since the continuous normal splits an integer-line push
symmetrically).

Everything here is read-only — no DB writes, no line mutation. It powers
`flask docket edge`. Spends Odds API credits only in fetch_current_lines
(spreads,totals across the ten named BOOKS = 2 credits/sport/run).
"""
from datetime import UTC
from statistics import NormalDist, median

from games.docket.services.importer import SPORTS, decode_payload
from games.docket.utils import now_utc
from utils.odds_api import odds_api_get, sport_base_url

_Z = NormalDist()

# Sport-specific standard deviations (points) of the final margin / combined
# score around the line. Measured on the graded 2026 Docket slates (Weeks 1-3,
# actual minus frozen line): NFL margin 13.8 / total 15.4 (n=33), CFB margin
# 14.7 / total 14.8 (n=253). A total is no less variable than a margin (the two
# teams' scores correlate positively), so each sport carries one sigma for both
# markets; a smaller totals sigma would inflate every totals edge against the
# spreads it competes with for the same eight slots.
SIGMA = {
    'americanfootball_nfl':   {'margin': 13.5, 'total': 13.5},
    'americanfootball_ncaaf': {'margin': 15.0, 'total': 15.0},
}
SPORT_LABEL = {'americanfootball_ncaaf': 'CFB', 'americanfootball_nfl': 'NFL'}
# NFL spreads cluster on these; a move that crosses one is worth more than the
# raw points (flagged for the reader, not modelled).
NFL_KEY_NUMBERS = (3, 6, 7, 10, 14)
# A book hanging -3 -125 is paying for the push on 3, not moving its mean, so
# on these numbers its juice is not converted into points (see _book_prob).
NFL_JUICE_KEYS = (3.0, 7.0)
# The /odds book set: ten named books bill as one region (the same credits as
# regions=us) and let Pinnacle, the sharpest number, into the median.
BOOKS = ('pinnacle,draftkings,fanduel,betmgm,williamhill_us,betonlineag,'
         'lowvig,betrivers,espnbet,hardrockbet')


def _as_utc(dt):
    """Coerce a naive (stored naive-UTC) or aware datetime to aware UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _american_to_prob(price):
    """Vig-inclusive implied probability of an American-odds price."""
    price = float(price)
    return 100.0 / (price + 100.0) if price > 0 else (-price) / (-price + 100.0)


def _devig(price_a, price_b):
    """No-vig probability of side a from a two-sided pair, or None when a
    price is missing."""
    if price_a is None or price_b is None:
        return None
    ra, rb = _american_to_prob(price_a), _american_to_prob(price_b)
    return ra / (ra + rb)


def _implied_mean(point, p, sigma, juice_keys=()):
    """The mean a book's (point, no-vig probability) implies, in the point's
    own sign convention: a side priced over 50% at its point is pricing a
    mean past that point. Point-only when there is no price, and on a juice
    key (the price is buying the push there, not moving the mean)."""
    if p is None or abs(point) in juice_keys:
        return point
    return point - sigma * _Z.inv_cdf(p)


def consensus_from_event(event, sport):
    """Price-aware consensus for one Odds API event payload.

    Each book contributes a quote per market: its point and the de-vigged
    probability that the home side covers it (spreads, home perspective, the
    frozen convention) or that the Over hits (totals). ``cons_spread`` /
    ``cons_total`` are the median implied means, for display, the move and
    the tiebreaker; the cover probabilities are priced per book at the frozen
    number in _market_prob. Returns None for any market no book carried.
    """
    home = event.get('home_team')
    sigma = SIGMA[sport]
    juice_keys = NFL_JUICE_KEYS if sport == 'americanfootball_nfl' else ()
    spread_quotes, total_quotes = [], []
    for bm in event.get('bookmakers', []):
        for mk in bm.get('markets', []):
            outcomes = mk.get('outcomes', [])
            if mk.get('key') == 'spreads':
                h = next((o for o in outcomes if o.get('name') == home
                          and o.get('point') is not None), None)
                a = next((o for o in outcomes if o.get('name') != home), None)
                if h is not None:
                    spread_quotes.append((float(h['point']), _devig(
                        h.get('price'), a.get('price') if a else None)))
            elif mk.get('key') == 'totals':
                o = next((x for x in outcomes if x.get('name') == 'Over'
                          and x.get('point') is not None), None)
                u = next((x for x in outcomes if x.get('name') == 'Under'), None)
                if o is not None:
                    total_quotes.append((float(o['point']), _devig(
                        o.get('price'), u.get('price') if u else None)))
    # The home spread's mean moves opposite to a home cover probability; the
    # total's moves with the Over's, hence the flipped sign on its inversion.
    spread_means = [_implied_mean(pt, p, sigma['margin'], juice_keys)
                    for pt, p in spread_quotes]
    total_means = [-_implied_mean(-pt, p, sigma['total'])
                   for pt, p in total_quotes]
    return {
        'home_team': home, 'away_team': event.get('away_team'),
        'commence_time': event.get('commence_time'),
        'spread_quotes': spread_quotes, 'total_quotes': total_quotes,
        'cons_spread': median(spread_means) if spread_means else None,
        'cons_total': median(total_means) if total_means else None,
    }


def _book_prob(frozen, point, p, sigma, juice_keys=()):
    """One book's probability that the home side covers (or the Over clears)
    the FROZEN number, in home-spread orientation: covering means the mean
    sits below the frozen number. A book hanging the frozen number itself is
    read straight off its no-vig price."""
    if p is not None and point == frozen:
        return p
    return _Z.cdf((frozen - _implied_mean(point, p, sigma, juice_keys)) / sigma)


def _market_prob(frozen, quotes, sigma, juice_keys=(), total=False):
    """Median across books of the home-cover (or Over) probability at the
    frozen number. A total is priced in the spread's orientation by negating
    its numbers (the Over clears F iff -total < -F)."""
    if total:
        return median(_book_prob(-frozen, -pt, p, sigma) for pt, p in quotes)
    return median(_book_prob(frozen, pt, p, sigma, juice_keys)
                  for pt, p in quotes)


def _crosses_key_numbers(frozen, current):
    """NFL key magnitudes strictly between the frozen and current home spread.

    Works in signed space and reports the magnitude, so a move that flips the
    favorite (e.g. -4 to +4, crossing 3) is not hidden by taking absolute
    values first — which would collapse equal-magnitude endpoints to an empty
    range."""
    lo, hi = sorted((frozen, current))
    return [k for k in NFL_KEY_NUMBERS if lo < k < hi or lo < -k < hi]


def _spread_side(game, cons):
    """Score the frozen spread against the market. Home covers the frozen
    number F iff the final margin exceeds -F; each book prices that at F and
    the median across books decides. Pick whichever side clears 50%."""
    frozen, quotes = game.home_spread, cons['spread_quotes']
    if frozen is None or not quotes:
        return None
    nfl = game.sport == 'americanfootball_nfl'
    p_home = _market_prob(frozen, quotes, SIGMA[game.sport]['margin'],
                          NFL_JUICE_KEYS if nfl else ())
    if p_home >= 0.5:
        side, prob = f'{game.home_team} {frozen:+g}', p_home
    else:
        side, prob = f'{game.away_team} {-frozen:+g}', 1.0 - p_home
    keys = _crosses_key_numbers(frozen, cons['cons_spread']) if nfl else []
    return _side_row(game, 'spread', side, prob, frozen, cons['cons_spread'],
                     keys, quotes)


def _total_side(game, cons):
    """Score the frozen total. Over the frozen number Ft hits iff the combined
    score exceeds Ft; each book prices that at Ft, the median decides."""
    frozen, quotes = game.total_points, cons['total_quotes']
    if frozen is None or not quotes:
        return None
    p_over = _market_prob(frozen, quotes, SIGMA[game.sport]['total'], total=True)
    side, prob = ((f'Over {frozen:g}', p_over) if p_over >= 0.5
                  else (f'Under {frozen:g}', 1.0 - p_over))
    return _side_row(game, 'total', side, prob, frozen, cons['cons_total'], [],
                     quotes)


def _side_row(game, market, side, prob, frozen, current, key_cross, quotes):
    book = game.spread_book if market == 'spread' else game.total_book
    points = [pt for pt, _ in quotes]
    return {
        'sport': SPORT_LABEL[game.sport], 'sport_key': game.sport,
        'game_id': game.id, 'matchup': f'{game.away_team} @ {game.home_team}',
        'market': market, 'side': side, 'prob': prob,
        'frozen': frozen, 'current': current, 'move': current - frozen,
        'book': book, 'key_cross': key_cross,
        'n_books': len(quotes), 'range': (min(points), max(points)),
        'kickoff': _as_utc(game.kickoff),
    }


def is_pickable(game, submit_time, deadline):
    """A side is pickable when picks are still open at submit_time — the week
    deadline has not passed (the whole-sheet cutoff, so a game kicking after it
    like MNF is unpickable once it does) and the game has not started — and it
    is not already final or ruled No Contest."""
    if deadline is not None and submit_time >= deadline:
        return False
    kickoff = _as_utc(game.kickoff)
    return (not game.is_final and not game.no_contest
            and kickoff is not None and kickoff > submit_time)


def analyze(games, consensus_by_event, submit_time, deadline):
    """Score every side of every game, ranked by cover probability desc.

    Returns (rows, unmatched): rows carry a ``pickable`` flag (games past their
    kickoff, or past the week ``deadline``, or lacking a current line, are
    marked not-pickable rather than dropped, so the caller can report
    coverage); unmatched is the games with no current Odds API event.
    """
    rows, unmatched = [], []
    for game in games:
        cons = consensus_by_event.get(game.api_event_id)
        if cons is None:
            unmatched.append(game)
            continue
        pickable = is_pickable(game, submit_time, deadline)
        for row in (_spread_side(game, cons), _total_side(game, cons)):
            if row is None:
                continue
            row['pickable'] = pickable
            rows.append(row)
    rows.sort(key=lambda r: r['prob'], reverse=True)
    return rows, unmatched


def fetch_current_lines(api_key, sports=SPORTS):
    """{event_id: consensus} for the given sports (impure — spends credits).

    A sport whose /odds call fails or returns a bad body is skipped with its
    error recorded, so one dark sport never blanks the other. Returns
    (consensus_by_event, errors, remaining), remaining being the key's
    credits left as of the last response (None when no call answered)."""
    consensus, errors, remaining = {}, [], None
    for sport in sports:
        try:
            resp = odds_api_get(
                f'{sport_base_url(sport)}/odds',
                params={'apiKey': api_key, 'bookmakers': BOOKS,
                        'markets': 'spreads,totals', 'oddsFormat': 'american'})
            remaining = resp.headers.get('x-requests-remaining', remaining)
            if resp.status_code != 200:
                errors.append(f'{sport} /odds HTTP {resp.status_code}')
                continue
            for event in decode_payload(resp, f'{sport} /odds'):
                consensus[event['id']] = consensus_from_event(event, sport)
        except Exception as exc:  # noqa: BLE001 — one sport must not abort the other
            errors.append(f'{sport}: {exc}')
    return consensus, errors, remaining


def expected_points(sheet):
    """Expected sheet score: each of the 8 scoring slots earns its cover
    probability, and the headliner (the top side) doubles. Slot 9 is the
    dormant reserve and does not score. Max 9.0."""
    scoring = sheet[:8]
    base = sum(r['prob'] for r in scoring)
    headliner = scoring[0]['prob'] if scoring else 0.0
    return base + headliner


def build_sheet(pickable, top=9):
    """The recommended sheet from pickable rows ranked best-first: the top
    scoring sides (at most 8), then, when ``top`` reaches 9, the reserve — the
    best remaining side on a game no scoring side is on. The sheet refuses a
    reserve on a held case (DESIGN.md §1.5: it would die on the same No
    Contest it is meant to cover), so a bare ninth-best side can be illegal."""
    scoring = pickable[:min(top, 8)]
    if top < 9:
        return scoring
    held = {r['game_id'] for r in scoring}
    reserve = next((r for r in pickable[len(scoring):]
                    if r['game_id'] not in held), None)
    return scoring + ([reserve] if reserve else [])


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
