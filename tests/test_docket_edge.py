"""Unit tests for the Docket frozen-line value analyzer.

Pure-function coverage of games/docket/services/edge.py: the normal
cover-probability model, side selection/labelling, pickable filtering, ranking,
consensus extraction, and the expected-points / tiebreaker helpers. No DB or
network — games are lightweight stubs and events are dict payloads shaped like
The Odds API.
"""
from datetime import UTC, datetime
from types import SimpleNamespace

from games.docket.services import edge

NFL = 'americanfootball_nfl'
CFB = 'americanfootball_ncaaf'


def _game(**kw):
    base = {
        'id': 1, 'sport': NFL, 'api_event_id': 'evt1',
        'home_team': 'Home', 'away_team': 'Away',
        'home_spread': -3.0, 'spread_book': 'draftkings',
        'total_points': 45.0, 'total_book': 'draftkings',
        'kickoff': datetime(2026, 9, 20, 17, 0, tzinfo=UTC),
        'is_final': False, 'no_contest': False,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_american_to_prob_both_signs():
    assert abs(edge._american_to_prob(-150) - 0.6) < 1e-9
    assert abs(edge._american_to_prob(150) - 0.4) < 1e-9


def test_no_movement_is_a_coin_flip():
    row = edge._spread_side(_game(home_spread=-3.0), cons_spread=-3.0)
    assert abs(row['prob'] - 0.5) < 1e-9


def test_market_moved_toward_home_makes_home_the_value_side():
    # frozen home -3, market now home -7 -> holding the cheaper -3 is ~62%
    row = edge._spread_side(_game(home_spread=-3.0), cons_spread=-7.0)
    assert row['side'] == 'Home -3'
    assert row['market'] == 'spread'
    assert 0.60 < row['prob'] < 0.63  # Phi(4/13.5) = 0.616


def test_market_moved_toward_away_selects_and_labels_away():
    # frozen home -1.5 (home favored) -> market home +0.5 (home now a dog)
    row = edge._spread_side(_game(home_spread=-1.5), cons_spread=0.5)
    assert row['side'] == 'Away +1.5'
    assert row['prob'] > 0.5


def test_total_over_is_value_when_market_rose():
    row = edge._total_side(_game(total_points=45.0, sport=NFL), cons_total=49.0)
    assert row['side'] == 'Over 45'
    assert 0.63 < row['prob'] < 0.68  # Phi(4/10) = 0.655


def test_total_under_is_value_when_market_fell():
    row = edge._total_side(_game(total_points=45.0), cons_total=41.0)
    assert row['side'] == 'Under 45'
    assert row['prob'] > 0.5


def test_missing_line_or_consensus_scores_nothing():
    assert edge._spread_side(_game(home_spread=None), -7.0) is None
    assert edge._spread_side(_game(home_spread=-3.0), None) is None
    assert edge._total_side(_game(total_points=None), 50.0) is None
    assert edge._total_side(_game(total_points=45.0), None) is None


def test_cfb_uses_wider_sigma_than_nfl():
    # the same 4-pt move is less certain in CFB (sigma 16) than NFL (13.5)
    nfl = edge._spread_side(_game(sport=NFL, home_spread=-3.0), -7.0)
    cfb = edge._spread_side(_game(sport=CFB, home_spread=-3.0), -7.0)
    assert nfl['prob'] > cfb['prob']


def test_key_number_flag_only_for_nfl_crossings():
    nfl = edge._spread_side(_game(sport=NFL, home_spread=-2.5), -4.0)  # crosses 3
    cfb = edge._spread_side(_game(sport=CFB, home_spread=-2.5), -4.0)
    assert 3 in nfl['key_cross']
    assert cfb['key_cross'] == []


def test_key_number_flag_survives_a_favorite_flip():
    # -4 -> +4 crosses 3 (and 0); taking abs() first would collapse both
    # endpoints to 4 and report nothing.
    assert edge._crosses_key_numbers(-4.0, 4.0) == [3]
    # a bigger swing crosses several magnitudes
    assert edge._crosses_key_numbers(-8.0, 8.0) == [3, 6, 7]
    # same-signed move still reads the magnitude it passed
    assert edge._crosses_key_numbers(-6.0, -2.0) == [3]


def test_pickable_filters_started_final_and_nc():
    submit = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    deadline = datetime(2027, 1, 1, tzinfo=UTC)  # far off — isolates the other checks
    future = _game(kickoff=datetime(2026, 9, 20, 17, 0, tzinfo=UTC))
    past = _game(kickoff=datetime(2026, 9, 17, 17, 0, tzinfo=UTC))
    assert edge.is_pickable(future, submit, deadline) is True
    assert edge.is_pickable(past, submit, deadline) is False
    assert edge.is_pickable(_game(is_final=True), submit, deadline) is False
    assert edge.is_pickable(_game(no_contest=True), submit, deadline) is False


def test_pickable_requires_picks_still_open_at_the_deadline():
    # a game kicking after the deadline (MNF) is pickable before the deadline
    # and unpickable once submit_time reaches it.
    deadline = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
    mnf = _game(kickoff=datetime(2026, 9, 22, 0, 15, tzinfo=UTC))
    assert edge.is_pickable(mnf, datetime(2026, 9, 20, 16, 0, tzinfo=UTC), deadline) is True
    assert edge.is_pickable(mnf, deadline, deadline) is False  # exactly at close
    assert edge.is_pickable(mnf, datetime(2026, 9, 21, 12, 0, tzinfo=UTC), deadline) is False


def test_pickable_accepts_naive_utc_kickoff():
    # stored kickoff is naive UTC; the filter must coerce, not crash
    submit = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    deadline = datetime(2027, 1, 1, tzinfo=UTC)
    naive = _game(kickoff=datetime(2026, 9, 20, 17, 0))
    assert edge.is_pickable(naive, submit, deadline) is True


def test_analyze_ranks_by_probability_and_reports_unmatched():
    submit = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    deadline = datetime(2027, 1, 1, tzinfo=UTC)
    matched = _game(id=1, api_event_id='a')
    missing = _game(id=2, api_event_id='no-event')
    consensus = {'a': {'cons_spread': -9.0, 'cons_total': 52.0,
                       'cons_home_winprob': 0.7, 'n_books': 6}}
    rows, unmatched = edge.analyze([matched, missing], consensus, submit, deadline)
    assert unmatched == [missing]
    assert rows == sorted(rows, key=lambda r: r['prob'], reverse=True)
    assert all(r['game_id'] == 1 for r in rows)  # only the matched game scored
    assert len(rows) == 2  # a spread side and a total side
    assert all(r['pickable'] is True for r in rows)


def test_expected_points_doubles_the_headliner():
    sheet = [{'prob': 0.6}] + [{'prob': 0.5}] * 8  # 9 sides (8 scoring + reserve)
    # 8 scoring: 0.6 + 7*0.5 = 4.1; headliner doubles: +0.6 -> 4.7; reserve idle
    assert abs(edge.expected_points(sheet) - 4.7) < 1e-9


def test_consensus_from_event_medians_and_devigs():
    event = {
        'home_team': 'Home', 'away_team': 'Away', 'commence_time': 'x',
        'bookmakers': [
            {'key': 'draftkings', 'markets': [
                {'key': 'spreads', 'outcomes': [
                    {'name': 'Home', 'point': -3.0}, {'name': 'Away', 'point': 3.0}]},
                {'key': 'totals', 'outcomes': [
                    {'name': 'Over', 'point': 44.0}, {'name': 'Under', 'point': 44.0}]},
                {'key': 'h2h', 'outcomes': [
                    {'name': 'Home', 'price': -150}, {'name': 'Away', 'price': 130}]},
            ]},
            {'key': 'fanduel', 'markets': [
                {'key': 'spreads', 'outcomes': [
                    {'name': 'Home', 'point': -3.5}, {'name': 'Away', 'point': 3.5}]},
                {'key': 'totals', 'outcomes': [
                    {'name': 'Over', 'point': 46.0}, {'name': 'Under', 'point': 46.0}]},
            ]},
        ],
    }
    cons = edge.consensus_from_event(event)
    assert cons['cons_spread'] == -3.25   # median(-3.0, -3.5)
    assert cons['cons_total'] == 45.0     # median(44, 46)
    assert cons['n_books'] == 2
    assert 0.55 < cons['cons_home_winprob'] < 0.62  # -150 de-vigged ~= 0.58


def test_tiebreaker_prefers_current_total_then_falls_back():
    week = SimpleNamespace(tiebreaker_game_id=7)
    game = _game(id=7, api_event_id='mnf', total_points=48.5)
    with_cur = {'mnf': {'cons_total': 47.0}}
    g, total = edge.tiebreaker_total(week, [game], with_cur)
    assert g is game and total == 47.0
    # no current line -> frozen O/U
    g2, total2 = edge.tiebreaker_total(week, [game], {})
    assert total2 == 48.5
    # no designation
    assert edge.tiebreaker_total(SimpleNamespace(tiebreaker_game_id=None),
                                 [game], with_cur) == (None, None)
