"""Fit the NFL key-number margin model in games/docket/services/nfl_margin.py.

Run from the repo root:  venv/bin/python scripts/fit_nfl_margin.py

Data: nflverse's public games file (every NFL game since 1999 with its final
score and closing spread). The model is a normal curve around the closing line
reweighted per absolute margin, so the lumps at 3, 7, 10, ... come back:

    P(home margin = m | expected home spread c) ~ phi((m + c) / sigma) * W[|m|]

W is fitted by iterative proportional fitting (the model's pooled |margin|
frequencies must match the observed ones), sigma by likelihood. Each game's c
is the location at which its closing point is an even 50/50 under the model
(the fit alternates between the two until c settles), exactly how the edge
tool reads a live book, so fit and use agree.

The closing PRICE is deliberately not used: the price check below shows it
predicts no better than the point alone, and worse when a favorite is juiced
on 3 (those favorites cover LESS than the price implies). The script
validates on seasons held out of the fit, against the plain normal curve the
edge tool used before, then refits on every season and prints the constants
block to paste into nfl_margin.py. Pure standard library.
"""
import csv
import io
import math
import sys
import urllib.request
from collections import Counter
from statistics import NormalDist, pstdev

URL = 'https://github.com/nflverse/nfldata/raw/master/data/games.csv'
FIRST_SEASON, HOLDOUT_FROM, LAST_SEASON = 2010, 2022, 2025
K_MAX = 24          # margins above this share one weight of 1.0 (sparse, noisy)
M_MAX = 80
SIGMAS = [s / 10 for s in range(115, 156, 2)]
IPF_ROUNDS = 30
OUTER_ROUNDS = 4


def load():
    raw = urllib.request.urlopen(URL, timeout=60).read().decode()
    games = []
    for r in csv.DictReader(io.StringIO(raw)):
        if not (r['result'] and r['spread_line']):
            continue
        season = int(r['season'])
        if FIRST_SEASON <= season <= LAST_SEASON:
            # nflverse spread_line is "home favored by"; the Docket's home
            # spread is its negative. result = home - away.
            ph, pa = r['home_spread_odds'], r['away_spread_odds']
            p = _devig(float(ph), float(pa)) if ph and pa else 0.5
            games.append((season, int(float(r['result'])),
                          -float(r['spread_line']), p))
    return games


def _devig(home_price, away_price):
    def imp(x):
        return 100 / (x + 100) if x > 0 else -x / (-x + 100)
    rh, ra = imp(home_price), imp(away_price)
    return rh / (rh + ra)


def pmf(c, sigma, w):
    ms = range(-M_MAX, M_MAX + 1)
    raw = [math.exp(-0.5 * ((m + c) / sigma) ** 2) * w[min(abs(m), K_MAX + 1)]
           for m in ms]
    z = sum(raw)
    return dict(zip(ms, (x / z for x in raw), strict=True))


def fit(games, sigma):
    """IPF weights for one sigma over (margin, c) pairs; returns (weights,
    log-likelihood)."""
    by_c = Counter(round(c, 2) for _, c in games)
    emp = Counter(min(abs(m), K_MAX + 1) for m, _ in games)
    w = [1.0] * (K_MAX + 2)
    for _ in range(IPF_ROUNDS):
        model = Counter()
        for c, cnt in by_c.items():
            for m, p in pmf(c, sigma, w).items():
                model[min(abs(m), K_MAX + 1)] += cnt * p
        for k in range(K_MAX + 1):     # the tail bucket stays the reference
            if model[k] > 0 and emp[k] > 0:
                w[k] *= emp[k] / model[k]
            elif emp[k] == 0:
                w[k] = 1e-6
    cache = {c: pmf(c, sigma, w) for c in by_c}
    ll = sum(math.log(max(cache[round(c, 2)].get(m, 0.0), 1e-12))
             for m, c in games)
    return w, ll


def implied_c(point, p, sigma, w):
    """The c at which home's cover probability at ``point`` (push excluded)
    is p. Bisection; home covers more as c falls."""
    lo, hi = -40.0, 40.0
    for _ in range(40):
        mid = (lo + hi) / 2
        pm = pmf(mid, sigma, w)
        win = sum(v for m, v in pm.items() if m + point > 0)
        loss = sum(v for m, v in pm.items() if m + point < 0)
        if win / (win + loss) > p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def best_fit(games):
    """Alternate: fit (sigma, W) given each game's c, then re-derive every c
    as the location where its closing point is 50/50 under the new model."""
    cs = {pt: pt for _, _, pt, _ in games}
    for _ in range(OUTER_ROUNDS):
        pairs = [(m, cs[pt]) for _, m, pt, _ in games]
        best = None
        for sigma in SIGMAS:
            w, ll = fit(pairs, sigma)
            if best is None or ll > best[2]:
                best = (sigma, w, ll)
        sigma, w, _ = best
        cs = {pt: implied_c(pt, 0.5, sigma, w) for pt in cs}
    return sigma, w, cs


def cover_ev(frozen, c, sigma, w):
    """Expected slot points for home at frozen F (win 1 / push 0.5)."""
    p = pmf(c, sigma, w)
    return (sum(v for m, v in p.items() if m + frozen > 0)
            + 0.5 * sum(v for m, v in p.items() if m + frozen == 0))


def validate(train, test):
    """Score frozen lines half a point to a point and a half off each held-out
    game's close: key-number model vs the plain normal curve
    on the closing point. All offsets, then only lines within a point of 3
    or 7, where the two models disagree."""
    sigma, w, cs = best_fit(train)
    sd = pstdev([m + pt for _, m, pt, _ in train])
    norm = NormalDist()
    tot = {'all': [0, 0, 0], 'key': [0, 0, 0]}
    for _, m, pt, _ in test:
        c = cs[pt] if pt in cs else implied_c(pt, 0.5, sigma, w)
        for d in (-1.5, -1.0, -0.5, 0.5, 1.0, 1.5):
            f = pt + d
            outcome = 1.0 if m + f > 0 else 0.5 if m + f == 0 else 0.0
            ek = (cover_ev(f, c, sigma, w) - outcome) ** 2
            en = (norm.cdf((f - pt) / sd) - outcome) ** 2
            buckets = ['all'] + (['key'] if any(abs(abs(f) - k) <= 1 or
                                                abs(abs(pt) - k) <= 1
                                                for k in (3, 7)) else [])
            for b in buckets:
                tot[b][0] += ek
                tot[b][1] += en
                tot[b][2] += 1
    print(f'holdout {HOLDOUT_FROM}-{LAST_SEASON}: {len(test)} games, '
          f'fit on {len(train)} (sigma {sigma}, normal sd {sd:.2f})')
    for b, (ek, en, n) in tot.items():
        print(f'  {b:>3} lines (n {n}): mean squared error key-number '
              f'{ek / n:.5f}  normal {en / n:.5f}  (lower is better)')


def spot_table(games, sigma, w, cs):
    """Favorite at frozen F against games that CLOSED at point c (away
    favorites folded in by sign): observed vs the model's mean prediction
    vs the normal curve on the point."""
    norm = NormalDist()
    sd = pstdev([m + pt for _, m, pt, _ in games])
    print('\nfavorite at frozen F, market closed favorite at c: '
          'observed vs model vs normal')
    for f, c in [(-2.5, -3.5), (-3.0, -3.5), (-3.5, -3.0), (-3.5, -2.5),
                 (-3.0, -3.0), (-2.5, -3.0), (-6.5, -7.0), (-7.5, -7.0),
                 (-7.0, -7.0), (-3.0, -5.0)]:
        obs, mod = [], []
        for _, m, pt, _ in games:
            if pt == c:
                mm, cc = m, cs[pt]
            elif pt == -c:
                mm, cc = -m, -cs[pt]
            else:
                continue
            obs.append(1.0 if mm + f > 0 else 0.5 if mm + f == 0 else 0.0)
            mod.append(cover_ev(f, cc, sigma, w))
        if not obs:
            continue
        print(f'  F {f:+5.1f} c {c:+5.1f}  n {len(obs):4d}  observed '
              f'{sum(obs) / len(obs):.3f}  model {sum(mod) / len(mod):.3f}  '
              f'normal {norm.cdf((f - c) / sd):.3f}')


def price_check(games, sigma, w, cs):
    """Does the closing price add anything to the closing point? Same scoring
    as validate, point-only c vs the c the no-vig price implies. In-sample,
    which if anything flatters the price."""
    tot = {}
    for _, m, pt, p in games:
        c_pt, c_px = cs[pt], implied_c(pt, p, sigma, w)
        skewed = abs(p - 0.5) > 0.02
        for d in (-1.0, -0.5, 0.5, 1.0):
            f = pt + d
            outcome = 1.0 if m + f > 0 else 0.5 if m + f == 0 else 0.0
            for b in ['all'] + (['skewed price'] if skewed else []):
                a = tot.setdefault(b, [0, 0, 0])
                a[0] += (cover_ev(f, c_pt, sigma, w) - outcome) ** 2
                a[1] += (cover_ev(f, c_px, sigma, w) - outcome) ** 2
                a[2] += 1
    print('\nprice check (mean squared error, lower is better):')
    for b, (ept, epx, n) in tot.items():
        print(f'  {b:>12} (n {n}): point only {ept / n:.5f}  '
              f'point + price {epx / n:.5f}')


def main():
    games = load()
    if not games:
        sys.exit('no games loaded')
    validate([g for g in games if g[0] < HOLDOUT_FROM],
             [g for g in games if g[0] >= HOLDOUT_FROM])
    sigma, w, cs = best_fit(games)
    spot_table(games, sigma, w, cs)
    price_check(games, sigma, w, cs)
    print('\n# --- paste into games/docket/services/nfl_margin.py ---')
    print(f'# nflverse games.csv, seasons {FIRST_SEASON}-{LAST_SEASON}, '
          f'{len(games)} games with a closing line.')
    print(f'SIGMA = {sigma}')
    print('WEIGHTS = (  # index = |home margin|; the last entry covers '
          f'every margin above {K_MAX}')
    vals = [f'{x:.3f}' for x in w]
    for i in range(0, len(vals), 8):
        print('    ' + ', '.join(vals[i:i + 8]) + ',')
    print(')')


if __name__ == '__main__':
    main()
