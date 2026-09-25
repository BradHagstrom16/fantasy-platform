"""The Docket — Frozen-Line Value Analysis (read-only)

The Docket grades every pick against a line frozen on Tuesday (the first-posted
number, snapshotted onto DocketPick.line_value). As the week goes on the real
market moves. Where today's consensus market line has drifted away from a frozen
line, the side the market moved *toward* is now a stale number that covers more
than half the time — the edge this module surfaces.

For each game the CURRENT market (the median point across ten books, Pinnacle
among them) is the sharp estimate of the outcome, optionally blended with a
projection model's line for NFL games (Subvertadown's team scores, see
parse_projections). The frozen line is the number the pool actually grades, so
a side's cover probability at the frozen number is the expected points the
slot earns (win 1.0 / push 0.5 / loss 0.0):

- NFL spreads use the key-number margin model (services/nfl_margin.py), so
  half a point across 3 or 7 is priced at what it is worth.
- CFB spreads and every total use a normal curve around the line.

Prices (the juice) are deliberately ignored: on nflverse's 4,363 closing lines
the no-vig price predicts no better than the point alone, and worse when a
favorite is juiced on 3 (scripts/fit_nfl_margin.py prints the check).

Everything here is read-only — no DB writes, no line mutation. It powers
`flask docket edge`. Spends Odds API credits only in fetch_current_lines
(spreads,totals across the ten named BOOKS = 2 credits/sport/run).
"""
from datetime import UTC
from math import isfinite
from statistics import NormalDist, median

from games.docket.services import nfl_margin
from games.docket.services.importer import SPORTS, decode_payload
from games.docket.utils import now_utc
from utils.odds_api import odds_api_get, sport_base_url

_Z = NormalDist()
NFL = 'americanfootball_nfl'

# Normal-curve standard deviations (points) of the final margin / combined
# score around the line, for every market but NFL spreads. Measured on the
# graded 2026 Docket slates (Weeks 1-3, actual minus frozen line): NFL margin
# 13.8 / total 15.4 (n=33), CFB margin 14.7 / total 14.8 (n=253); nflverse's
# 2010-2025 NFL closing totals give 13.2 (n=4,362). A total is no less
# variable than a margin, so each sport carries one sigma for both markets.
SIGMA = {
    NFL:                      {'margin': 13.5, 'total': 13.5},
    'americanfootball_ncaaf': {'margin': 15.0, 'total': 15.0},
}
SPORT_LABEL = {'americanfootball_ncaaf': 'CFB', NFL: 'NFL'}
# NFL spreads cluster on these; a move across one is flagged for the reader
# (the key-number model already prices it).
NFL_KEY_NUMBERS = (3, 6, 7, 10, 14)
# The /odds book set: ten named books bill as one region (the same credits as
# regions=us) and let Pinnacle, the sharpest number, into the median.
BOOKS = ('pinnacle,draftkings,fanduel,betmgm,williamhill_us,betonlineag,'
         'lowvig,betrivers,espnbet,hardrockbet')
# Weight of the projection model against the market in an NFL game's line
# (Brad, 2026-09-25: 75% market / 25% Subvertadown until enough saved weekly
# captures exist to fit it). Overridable per run with --sva-weight.
SVA_WEIGHT = 0.25


def _as_utc(dt):
    """Coerce a naive (stored naive-UTC) or aware datetime to aware UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def consensus_from_event(event):
    """Median-point consensus for one Odds API event payload.

    ``spreads`` holds each book's home spread (the frozen convention),
    ``totals`` each book's Over point; ``cons_spread`` / ``cons_total`` are
    their medians, None for a market no book carried.
    """
    home = event.get('home_team')
    spreads, totals = [], []
    for bm in event.get('bookmakers', []):
        for mk in bm.get('markets', []):
            outcomes = mk.get('outcomes', [])
            if mk.get('key') == 'spreads':
                pt = next((o['point'] for o in outcomes
                           if o.get('name') == home and o.get('point') is not None), None)
                if pt is not None:
                    spreads.append(float(pt))
            elif mk.get('key') == 'totals':
                pt = next((o['point'] for o in outcomes
                           if o.get('name') == 'Over' and o.get('point') is not None), None)
                if pt is not None:
                    totals.append(float(pt))
    return {
        'home_team': home, 'away_team': event.get('away_team'),
        'commence_time': event.get('commence_time'),
        'spreads': spreads, 'totals': totals,
        'cons_spread': median(spreads) if spreads else None,
        'cons_total': median(totals) if totals else None,
    }


def parse_projections(data, nfl_week):
    """{team nickname: projected points} from a projection capture.

    The capture is ``{"nfl_week": N, "team_points": {"Bills": 30.4, ...}}``
    (a team on bye carries null). A capture for any other NFL week is stale —
    the source has not rolled over — and raises ValueError rather than
    blending last week's numbers into this week's lines.
    """
    if not isinstance(data, dict) or not isinstance(data.get('team_points'), dict):
        raise ValueError('projections file needs a "team_points" object')
    if data.get('nfl_week') != nfl_week:
        raise ValueError(f'projections are for NFL week {data.get("nfl_week")}, '
                         f'not {nfl_week}: the source has not rolled over')
    points = {}
    for name, pts in data['team_points'].items():
        if pts is None:
            continue
        bad = ValueError(f'team_points[{name!r}] must be a finite number or null')
        if isinstance(pts, bool) or not isinstance(pts, int | float):
            raise bad
        try:
            value = float(pts)   # a huge JSON integer overflows
        except OverflowError:
            raise bad from None
        if not isfinite(value):  # json.load accepts 1e400 (inf) and NaN
            raise bad
        points[name] = value
    return points


def _team_points(full_name, projections):
    """A projection keyed by nickname, for the DB's full team name
    ("49ers" -> "San Francisco 49ers"); None when the team is not listed."""
    for nick, pts in projections.items():
        if full_name == nick or full_name.endswith(' ' + nick):
            return pts
    return None


def model_lines(game, projections):
    """(home spread, total) the projections imply for an NFL game, or None
    when there are no projections, the game is not NFL, or a team is
    missing."""
    if not projections or game.sport != NFL:
        return None
    home = _team_points(game.home_team, projections)
    away = _team_points(game.away_team, projections)
    if home is None or away is None:
        return None
    return -(home - away), home + away


def _blend(market, model, weight):
    return market if model is None else (1 - weight) * market + weight * model


def _crosses_key_numbers(frozen, current):
    """NFL key magnitudes strictly between the frozen and current home spread.

    Works in signed space and reports the magnitude, so a move that flips the
    favorite (e.g. -4 to +4, crossing 3) is not hidden by taking absolute
    values first — which would collapse equal-magnitude endpoints to an empty
    range."""
    lo, hi = sorted((frozen, current))
    return [k for k in NFL_KEY_NUMBERS if lo < k < hi or lo < -k < hi]


def _home_cover(game, frozen, market, model, weight):
    """Probability (expected points) that home covers the frozen spread.

    NFL: the market's median point is read as an even 50/50 line under the
    key-number model, turned into a fair spread, blended with the model's
    spread, and priced at the frozen number. Elsewhere: a normal curve around
    the line."""
    if game.sport == NFL:
        c = nfl_margin.implied_c(market)
        if model is not None:
            fair = _blend(nfl_margin.fair_spread(c), model, weight)
            c = nfl_margin.c_for_fair_spread(fair)
        return nfl_margin.cover_ev(frozen, c)
    return _Z.cdf((frozen - market) / SIGMA[game.sport]['margin'])


def _spread_side(game, cons, model=None, weight=SVA_WEIGHT):
    """Score the frozen spread; pick whichever side clears 50%."""
    frozen, market = game.home_spread, cons['cons_spread']
    if frozen is None or market is None:
        return None
    p_home = _home_cover(game, frozen, market, model, weight)
    if p_home >= 0.5:
        side, prob = f'{game.home_team} {frozen:+g}', p_home
    else:
        side, prob = f'{game.away_team} {-frozen:+g}', 1.0 - p_home
    keys = _crosses_key_numbers(frozen, market) if game.sport == NFL else []
    return _side_row(game, 'spread', side, prob, frozen, market, keys,
                     cons['spreads'], model)


def _total_side(game, cons, model=None, weight=SVA_WEIGHT):
    """Score the frozen total. The Over hits iff the combined score exceeds
    the frozen number; combined ~ Normal(blended total, sigma)."""
    frozen, market = game.total_points, cons['cons_total']
    if frozen is None or market is None:
        return None
    mean = _blend(market, model, weight)
    p_over = _Z.cdf((mean - frozen) / SIGMA[game.sport]['total'])
    side, prob = ((f'Over {frozen:g}', p_over) if p_over >= 0.5
                  else (f'Under {frozen:g}', 1.0 - p_over))
    return _side_row(game, 'total', side, prob, frozen, market, [],
                     cons['totals'], model)


def _side_row(game, market, side, prob, frozen, current, key_cross, points,
              model):
    book = game.spread_book if market == 'spread' else game.total_book
    return {
        'sport': SPORT_LABEL[game.sport], 'sport_key': game.sport,
        'game_id': game.id, 'matchup': f'{game.away_team} @ {game.home_team}',
        'market': market, 'side': side, 'prob': prob,
        'frozen': frozen, 'current': current, 'move': current - frozen,
        'model': model, 'book': book, 'key_cross': key_cross,
        'n_books': len(points), 'range': (min(points), max(points)),
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


def analyze(games, consensus_by_event, submit_time, deadline,
            projections=None, weight=SVA_WEIGHT):
    """Score every side of every game, ranked by cover probability desc.

    Returns (rows, unmatched): rows carry a ``pickable`` flag (games past their
    kickoff, or past the week ``deadline``, or lacking a current line, are
    marked not-pickable rather than dropped, so the caller can report
    coverage); unmatched is the games with no current Odds API event. NFL
    games blend ``projections`` in at ``weight`` when both teams are listed.
    """
    rows, unmatched = [], []
    for game in games:
        cons = consensus_by_event.get(game.api_event_id)
        if cons is None:
            unmatched.append(game)
            continue
        pickable = is_pickable(game, submit_time, deadline)
        lines = model_lines(game, projections)
        spread_model, total_model = lines if lines else (None, None)
        for row in (_spread_side(game, cons, spread_model, weight),
                    _total_side(game, cons, total_model, weight)):
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
                consensus[event['id']] = consensus_from_event(event)
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


def tiebreaker_total(week, games, consensus_by_event, projections=None,
                     weight=SVA_WEIGHT):
    """Sharpest predicted combined score for the designated tiebreaker game:
    its current consensus total (blended with the projections for an NFL
    game), falling back to the frozen O/U total."""
    if week.tiebreaker_game_id is None:
        return None, None
    game = next((g for g in games if g.id == week.tiebreaker_game_id), None)
    if game is None:
        return None, None
    cons = consensus_by_event.get(game.api_event_id)
    market = cons.get('cons_total') if cons else None
    if market is None:
        return game, game.total_points
    lines = model_lines(game, projections)
    return game, _blend(market, lines[1] if lines else None, weight)


def default_submit_time():
    """Now, honoring the DOCKET_FAKE_NOW seam in dev/testing (real time in
    prod) — the same clock the rest of the docket reads."""
    return now_utc()
