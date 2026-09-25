"""Unit tests for the NFL key-number margin model (games/docket/services/
nfl_margin.py): the distribution's shape, the cover arithmetic, the readings
of a book's point, and that the fitted model lands near the observed cover
rates at the spots the edge tool exists for (nflverse closing lines
2010-2025, reprinted by scripts/fit_nfl_margin.py). Pure, no DB."""
import pytest

from games.docket.services import nfl_margin as nm


def test_pmf_is_a_distribution_mirrored_in_c():
    p = nm.pmf(-3.0)
    assert abs(sum(p.values()) - 1.0) < 1e-12
    q = nm.pmf(3.0)
    assert all(abs(p[m] - q[-m]) < 1e-12 for m in p)


def test_three_and_seven_carry_the_lumps():
    p = nm.pmf(-3.0)
    assert p[3] > p[2] and p[3] > p[4]
    assert p[7] > p[6] and p[7] > p[8]
    assert p[0] < p[1] / 3   # ties are rare


def test_cover_ev_splits_a_push_and_sides_sum_to_one():
    c = nm.implied_c(-3.0)
    assert abs(nm.cover_ev(-3.0, c) - 0.5) < 1e-9   # the line itself, push halved
    win, push, loss = nm._split(-3.0, c)
    assert push > 0.08 and abs(win - loss) < 1e-9
    assert abs(nm.cover_ev(-2.5, c) + (1 - nm.cover_ev(-2.5, c)) - 1.0) < 1e-12


@pytest.mark.parametrize('point', [-10.0, -7.0, -3.5, -3.0, -2.5, -1.0, 0.0, 4.5])
def test_a_half_point_book_line_is_an_even_coin(point):
    c = nm.implied_c(point)
    win, _, loss = nm._split(point, c)
    assert abs(win - loss) < 1e-9


def test_fair_spread_round_trips():
    for spread in (-10.7, -4.5, -3.1, 0.0, 2.2, 7.0):
        assert abs(nm.fair_spread(nm.c_for_fair_spread(spread)) - spread) < 1e-6


def test_fair_spread_of_a_book_line_tracks_the_observed_mean_margin():
    # games that closed at -3.5 won by 4.8 on average, at -7 by 8.7
    assert -5.0 < nm.fair_spread(nm.implied_c(-3.5)) < -4.2
    assert -9.2 < nm.fair_spread(nm.implied_c(-7.0)) < -8.2


@pytest.mark.parametrize('frozen,close,observed', [
    (-2.5, -3.5, 0.611),   # buy the favorite through 3
    (-3.0, -3.5, 0.568),
    (-3.5, -2.5, 0.404),   # the favorite laid through 3: the dog is the value
    (-6.5, -7.0, 0.530),
    (-7.5, -7.0, 0.466),
])
def test_key_spots_land_near_the_observed_cover_rate(frozen, close, observed):
    # the favorite's expected points at the frozen number when the market
    # closed at ``close``; within 3.5 points (n 281-635 games per spot)
    assert abs(nm.cover_ev(frozen, nm.implied_c(close)) - observed) < 0.035


def test_half_a_point_across_three_beats_half_a_point_elsewhere():
    across = nm.cover_ev(-2.5, nm.implied_c(-3.0))
    elsewhere = nm.cover_ev(-4.5, nm.implied_c(-5.0))
    assert across - 0.5 > 2 * (elsewhere - 0.5)
