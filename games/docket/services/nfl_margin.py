"""The Docket — NFL key-number margin model (read-only, pure).

NFL final margins are lumpy: about one game in seven ends by exactly 3, one in
eleven by 7. A normal curve around the line spreads that mass evenly, so it
prices half a point across 3 like any other half point when it is worth
several points of cover probability. This model keeps the normal shape and
reweights each absolute margin:

    P(home margin = m | c) ~ phi((m + c) / SIGMA) * WEIGHTS[|m|]

where c is the expected home spread (negative = home favored), the Docket's
convention. The constants are fitted by scripts/fit_nfl_margin.py on
nflverse's public closing lines, each game's c read from its closing point the
same way `implied_c` reads a live book. The script reports the holdout check
against the plain normal curve, and the check that keeps prices out: the
closing juice predicts no better than the point, and worse on 3.

Used by games/docket/services/edge.py for NFL spreads only; CFB spreads and
every total stay on the normal curve (their key numbers are much weaker).
"""
from functools import lru_cache
from math import exp

# nflverse games.csv, seasons 2010-2025, 4363 games with a closing line.
# Fitted 2026-09-25 by scripts/fit_nfl_margin.py (holdout 2022-2025 beats the
# normal curve on every slice; the closing price adds nothing to the point).
SIGMA = 13.7
WEIGHTS = (  # index = |home margin|; the last entry covers every margin above 24
    0.134, 0.991, 0.997, 3.341, 1.165, 0.953, 1.593, 2.157,
    1.046, 0.387, 1.387, 0.602, 0.520, 0.734, 1.663, 0.571,
    0.907, 1.316, 1.039, 0.496, 0.981, 1.313, 0.608, 0.798,
    1.495, 1.000,
)
M_MAX = 80
_MARGINS = range(-M_MAX, M_MAX + 1)
_TAIL = len(WEIGHTS) - 1


@lru_cache(maxsize=4096)
def pmf(c):
    """{home margin: probability} given the expected home spread c."""
    raw = [exp(-0.5 * ((m + c) / SIGMA) ** 2) * WEIGHTS[min(abs(m), _TAIL)]
           for m in _MARGINS]
    z = sum(raw)
    return dict(zip(_MARGINS, (x / z for x in raw), strict=True))


def _split(frozen, c):
    """(win, push, loss) probabilities for home at the frozen home spread."""
    win = push = loss = 0.0
    for m, p in pmf(c).items():
        s = m + frozen
        if s > 0:
            win += p
        elif s < 0:
            loss += p
        else:
            push += p
    return win, push, loss


def cover_ev(frozen, c):
    """Expected slot points for the HOME side at the frozen number: win 1,
    push 0.5. The away side earns 1 minus this."""
    win, push, _ = _split(frozen, c)
    return win + 0.5 * push


def implied_c(point):
    """The location at which a book's home spread ``point`` is an even 50/50
    (push excluded, as a price is). An even -3.5 sits at about -5.1: the mass
    on 3 lands on the losing side of it."""
    lo, hi = -60.0, 60.0
    for _ in range(40):
        mid = (lo + hi) / 2
        win, _, loss = _split(point, mid)
        if win > loss:
            lo = mid   # home covers too often: move the location toward away
        else:
            hi = mid
    return (lo + hi) / 2


def fair_spread(c):
    """The expected home spread in points (minus the expected home margin)
    the model's location ``c`` stands for. It is not c itself: the reweighted
    margins pull the mean back toward the key numbers (an even-money -3.5
    has c -5.2 but a fair spread of -4.5; games that closed there won by
    4.8 on average). Fair spreads are what blend with a projection."""
    return -sum(m * p for m, p in pmf(c).items())


def c_for_fair_spread(spread):
    """Inverse of fair_spread (monotone): the location whose expected home
    spread is ``spread``."""
    lo, hi = -80.0, 80.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if fair_spread(mid) < spread:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
