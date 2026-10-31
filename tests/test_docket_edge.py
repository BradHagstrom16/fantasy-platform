"""Unit tests for the Docket frozen-line value analyzer.

Pure-function coverage of games/docket/services/edge.py: cover probabilities
(the NFL key-number model and the normal curve), side selection/labelling,
the projection blend, pickable filtering, ranking, consensus extraction, the
legal reserve, and the expected-points / tiebreaker helpers. No DB or
network — games are lightweight stubs and events are dict payloads shaped like
The Odds API.
"""
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

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


def _cons(spread=None, total=None, spreads=None, totals=None):
    """A consensus dict as consensus_from_event builds it."""
    spreads = spreads if spreads is not None else ([] if spread is None else [spread])
    totals = totals if totals is not None else ([] if total is None else [total])
    return {'spreads': spreads, 'totals': totals,
            'cons_spread': edge.median(spreads) if spreads else None,
            'cons_total': edge.median(totals) if totals else None}


def test_no_movement_is_a_coin_flip():
    row = edge._spread_side(_game(home_spread=-3.0), _cons(spread=-3.0))
    assert abs(row['prob'] - 0.5) < 1e-9


def test_market_moved_toward_home_makes_home_the_value_side():
    # frozen home -3, market now home -7: holding the cheaper -3 wins by 4+
    # and pushes on 3, the key-number model's ~66% (a normal curve says 62%)
    row = edge._spread_side(_game(home_spread=-3.0), _cons(spread=-7.0))
    assert row['side'] == 'Home -3'
    assert row['market'] == 'spread'
    assert 0.63 < row['prob'] < 0.69


def test_market_moved_toward_away_selects_and_labels_away():
    # frozen home -1.5 (home favored) -> market home +0.5 (home now a dog)
    row = edge._spread_side(_game(home_spread=-1.5), _cons(spread=0.5))
    assert row['side'] == 'Away +1.5'
    assert row['prob'] > 0.5


def test_total_over_is_value_when_market_rose():
    row = edge._total_side(_game(total_points=45.0, sport=NFL), _cons(total=49.0))
    assert row['side'] == 'Over 45'
    assert 0.60 < row['prob'] < 0.63  # Phi(4/13.5) = 0.616


def test_total_under_is_value_when_market_fell():
    row = edge._total_side(_game(total_points=45.0), _cons(total=41.0))
    assert row['side'] == 'Under 45'
    assert row['prob'] > 0.5


def test_missing_line_or_consensus_scores_nothing():
    assert edge._spread_side(_game(home_spread=None), _cons(spread=-7.0)) is None
    assert edge._spread_side(_game(home_spread=-3.0), _cons(spread=None)) is None
    assert edge._total_side(_game(total_points=None), _cons(total=50.0)) is None
    assert edge._total_side(_game(total_points=45.0), _cons(total=None)) is None


def test_the_same_move_is_worth_less_in_cfb():
    # CFB: a normal curve with sigma 15; NFL: the key-number model, which
    # also credits the push on 3
    nfl = edge._spread_side(_game(sport=NFL, home_spread=-3.0), _cons(spread=-7.0))
    cfb = edge._spread_side(_game(sport=CFB, home_spread=-3.0), _cons(spread=-7.0))
    assert nfl['prob'] > cfb['prob']


def test_key_number_flag_only_for_nfl_crossings():
    nfl = edge._spread_side(_game(sport=NFL, home_spread=-2.5), _cons(spread=-4.0))  # crosses 3
    cfb = edge._spread_side(_game(sport=CFB, home_spread=-2.5), _cons(spread=-4.0))
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
    consensus = {'a': _cons(spread=-9.0, total=52.0)}
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


def test_consensus_from_event_medians_the_points():
    event = {
        'home_team': 'Home', 'away_team': 'Away', 'commence_time': 'x',
        'bookmakers': [
            {'key': 'draftkings', 'markets': [
                {'key': 'spreads', 'outcomes': [
                    {'name': 'Home', 'point': -3.0}, {'name': 'Away', 'point': 3.0}]},
                {'key': 'totals', 'outcomes': [
                    {'name': 'Over', 'point': 44.0}, {'name': 'Under', 'point': 44.0}]},
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
    assert cons['spreads'] == [-3.0, -3.5]
    assert cons['totals'] == [44.0, 46.0]


def test_nfl_spread_is_priced_on_the_key_number_model():
    # half a point across 3 is worth far more than half a point elsewhere
    across = edge._spread_side(_game(home_spread=-2.5), _cons(spread=-3.5))
    elsewhere = edge._spread_side(_game(home_spread=-5.0), _cons(spread=-6.0))
    assert across['side'] == 'Home -2.5' and elsewhere['side'] == 'Home -5'
    assert across['prob'] > 0.57 > elsewhere['prob']
    assert abs(across['prob'] - edge.nfl_margin.cover_ev(
        -2.5, edge.nfl_margin.implied_c(-3.5))) < 1e-12


def test_cfb_spread_stays_on_the_normal_curve():
    row = edge._spread_side(_game(sport=CFB, home_spread=-3.0), _cons(spread=-7.0))
    assert abs(row['prob'] - edge._Z.cdf(4 / 15.0)) < 1e-12


def test_consensus_is_the_median_point():
    row = edge._spread_side(_game(sport=CFB, home_spread=-3.0),
                            _cons(spreads=[-3.0, -7.0, -7.0]))
    assert abs(row['prob'] - edge._Z.cdf(4 / 15.0)) < 1e-12
    assert row['n_books'] == 3 and row['range'] == (-7.0, -3.0)


def test_projection_blends_into_an_nfl_total():
    # market 45, model 49, weight 0.25 -> mean 46 against a frozen 45
    row = edge._total_side(_game(total_points=45.0), _cons(total=45.0),
                           model=49.0, weight=0.25)
    assert row['side'] == 'Over 45' and row['model'] == 49.0
    assert abs(row['prob'] - edge._Z.cdf(1 / 13.5)) < 1e-12


def test_projection_blends_into_an_nfl_spread_as_a_fair_spread():
    nm = edge.nfl_margin
    row = edge._spread_side(_game(home_spread=-3.0), _cons(spread=-3.0),
                            model=-7.0, weight=0.25)
    fair = 0.75 * nm.fair_spread(nm.implied_c(-3.0)) + 0.25 * -7.0
    assert row['side'] == 'Home -3'
    assert abs(row['prob'] - nm.cover_ev(-3.0, nm.c_for_fair_spread(fair))) < 1e-9
    # weight 0 is the market alone
    alone = edge._spread_side(_game(home_spread=-3.0), _cons(spread=-3.0),
                              model=-7.0, weight=0.0)
    assert abs(alone['prob'] - 0.5) < 1e-6


def test_parse_projections_checks_the_week_and_skips_byes():
    data = {'nfl_week': 3, 'team_points': {'Bills': 30.4, 'Chiefs': None}}
    assert edge.parse_projections(data, 3) == {'Bills': 30.4}
    with pytest.raises(ValueError, match='NFL week 3, not 4'):
        edge.parse_projections(data, 4)
    with pytest.raises(ValueError, match='team_points'):
        edge.parse_projections({'nfl_week': 3}, 3)


@pytest.mark.parametrize('raw', ['[30.4]', '{"pts": 30.4}', '"30.4"', 'true',
                                 '1e400', 'NaN', '1' + '0' * 400])
def test_parse_projections_refuses_a_non_finite_number(raw):
    # a bad capture must be the CLI's clean refusal, never a TypeError or
    # OverflowError traceback, and a boolean, inf or NaN never blends in
    data = json.loads(f'{{"nfl_week": 3, "team_points": {{"Bills": {raw}}}}}')
    with pytest.raises(ValueError,
                       match=r"team_points\['Bills'\] must be a finite number"):
        edge.parse_projections(data, 3)


def test_model_lines_match_nicknames_and_skip_cfb_and_missing_teams():
    proj = {'49ers': 27.4, 'Cardinals': 18.7, 'Bills': 30.4}
    game = _game(home_team='San Francisco 49ers', away_team='Arizona Cardinals')
    spread, total = edge.model_lines(game, proj)
    assert abs(spread - -8.7) < 1e-9 and abs(total - 46.1) < 1e-9
    assert edge.model_lines(_game(sport=CFB, home_team='San Francisco 49ers',
                                  away_team='Arizona Cardinals'), proj) is None
    assert edge.model_lines(_game(home_team='Buffalo Bills',
                                  away_team='Miami Dolphins'), proj) is None
    assert edge.model_lines(game, None) is None


def test_analyze_blends_only_projected_nfl_games():
    submit = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    deadline = datetime(2027, 1, 1, tzinfo=UTC)
    nfl = _game(id=1, api_event_id='a', home_team='Buffalo Bills',
                away_team='Los Angeles Chargers', home_spread=-7.0, total_points=50.0)
    cfb = _game(id=2, api_event_id='b', sport=CFB, home_team='Buffalo Bulls',
                away_team='Kent State Golden Flashes')
    consensus = {'a': _cons(spread=-7.0, total=50.0), 'b': _cons(spread=-3.0, total=45.0)}
    proj = {'Bills': 30.4, 'Chargers': 19.7}
    rows, _ = edge.analyze([nfl, cfb], consensus, submit, deadline, proj, 0.25)
    by = {(r['game_id'], r['market']): r for r in rows}
    assert by[(1, 'spread')]['model'] is not None
    assert by[(1, 'spread')]['side'] == 'Buffalo Bills -7'  # model says -10.7
    assert by[(2, 'spread')]['model'] is None               # "Bulls" never matches


def test_build_sheet_reserve_skips_a_game_already_held():
    rows = [{'game_id': g, 'prob': p} for g, p in
            [(1, .7), (2, .69), (3, .68), (4, .67), (5, .66), (6, .65),
             (7, .64), (8, .63), (8, .62), (9, .61)]]
    sheet = edge.build_sheet(rows, 9)
    assert [r['game_id'] for r in sheet[:8]] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert sheet[8]['game_id'] == 9  # game 8's other market is refused
    assert len(edge.build_sheet(rows, 5)) == 5
    assert len(edge.build_sheet(rows[:9], 9)) == 8  # no legal reserve left


def test_fetch_names_ten_books_and_skips_h2h(monkeypatch):
    calls = []

    def fake_get(url, params=None):
        calls.append(params)
        return SimpleNamespace(status_code=200, json=list,
                               headers={'x-requests-remaining': '480'})

    monkeypatch.setattr(edge, 'odds_api_get', fake_get)
    consensus, errors, remaining = edge.fetch_current_lines('k', [NFL, CFB])
    assert consensus == {} and errors == [] and remaining == '480'
    for params in calls:
        assert params['markets'] == 'spreads,totals'
        assert 'regions' not in params
        books = params['bookmakers'].split(',')
        assert 'pinnacle' in books and len(books) == 10  # 10 books = 1 region


def test_tiebreaker_blends_the_projection_into_the_total():
    week = SimpleNamespace(tiebreaker_game_id=7)
    game = _game(id=7, api_event_id='mnf', home_team='Chicago Bears',
                 away_team='Philadelphia Eagles')
    proj = {'Bears': 18.7, 'Eagles': 21.7}   # 40.4
    _, total = edge.tiebreaker_total(week, [game], {'mnf': {'cons_total': 41.6}},
                                     proj, 0.25)
    assert abs(total - (0.75 * 41.6 + 0.25 * 40.4)) < 1e-9


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


# ── planning around a member's held picks ──────────────────────────────────

KO = datetime(2026, 10, 31, 17, 0, tzinfo=UTC)


def _row(gid, prob, *, market='spread', side_key='home', minutes=0):
    return {'game_id': gid, 'market': market, 'side_key': side_key,
            'side': f'G{gid} {market} {side_key}', 'prob': prob,
            'matchup': f'A{gid} @ H{gid}',
            'kickoff': KO.replace(minute=minutes)}


def _pick(gid, slot, *, market='spread', side='home', is_best=False,
          points=None, prob=None, minutes=0):
    return {'game_id': gid, 'market': market, 'side': side, 'slot': slot,
            'is_best': is_best, 'label': f'P{gid} {market} {side}',
            'matchup': f'A{gid} @ H{gid}',
            'kickoff': KO.replace(minute=minutes), 'prob': prob,
            'points': points}


def _ranked(n=12):
    return [_row(g, 0.70 - g * 0.01) for g in range(1, n + 1)]


def test_rows_carry_the_pick_side_they_stand_for():
    home = edge._spread_side(_game(home_spread=-3.0), _cons(spread=-7.0))
    away = edge._spread_side(_game(home_spread=-1.5), _cons(spread=0.5))
    over = edge._total_side(_game(total_points=45.0), _cons(total=49.0))
    under = edge._total_side(_game(total_points=45.0), _cons(total=41.0))
    assert [r['side_key'] for r in (home, away, over, under)] == [
        'home', 'away', 'over', 'under']


def test_plan_with_nothing_held_is_the_blank_sheet():
    rows = _ranked()
    rows.insert(8, _row(3, 0.615, market='total', side_key='over'))
    plan = edge.plan_sheet(rows)
    assert plan['open'] == rows[:8]
    assert plan['headliner'] is rows[0] and not plan['headliner_locked']
    assert plan['reserve']['game_id'] == 9      # skips game 3's total
    assert edge.build_sheet(rows) == plan['open'] + [plan['reserve']]
    outlook = edge.sheet_outlook(plan)
    assert abs(outlook['projected']
               - edge.expected_points(edge.build_sheet(rows))) < 1e-9


def test_a_held_headliner_stays_and_six_slots_open():
    rows = _ranked()
    held = [_pick(100, 1, is_best=True, points=2.0), _pick(101, 2, points=0.0)]
    plan = edge.plan_sheet(rows, held)
    assert plan['open'] == rows[:6]
    assert plan['headliner'] is held[0] and plan['headliner_locked']
    assert plan['reserve'] is rows[6]
    outlook = edge.sheet_outlook(plan)
    assert outlook['banked'] == 2.0 and outlook['graded'] == 2
    assert outlook['pending'] == 0
    # no doubling on the open side: the headliner is already spent
    assert abs(outlook['open_ev'] - sum(r['prob'] for r in rows[:6])) < 1e-9


def test_a_held_plain_pick_sends_the_headliner_to_the_top_open_row():
    rows = _ranked()
    held = [_pick(100, 1, points=1.0), _pick(101, 2)]       # 101 still live
    plan = edge.plan_sheet(rows, held)
    assert plan['headliner'] is rows[0] and not plan['headliner_locked']
    outlook = edge.sheet_outlook(plan)
    assert outlook['banked'] == 1.0 and outlook['pending'] == 1
    expected = sum(r['prob'] for r in rows[:6]) + rows[0]['prob']
    assert abs(outlook['open_ev'] - expected) < 1e-9
    assert abs(outlook['projected'] - (1.0 + expected)) < 1e-9


def test_a_held_reserve_is_kept():
    rows = _ranked()
    held = [_pick(100, 9)]
    plan = edge.plan_sheet(rows, held)
    assert plan['reserve'] is held[0] and plan['reserve_locked']
    assert plan['open'] == rows[:8]


def test_the_reserve_skips_a_game_a_held_pick_is_on():
    # a held spread on game 100 whose total is still on the board
    rows = _ranked(7) + [_row(100, 0.55, market='total', side_key='under'),
                         _row(8, 0.54)]
    plan = edge.plan_sheet(rows, [_pick(100, 3)])
    assert plan['open'] == rows[:7]
    assert plan['reserve']['game_id'] == 8


def test_top_below_nine_plans_no_reserve():
    plan = edge.plan_sheet(_ranked(), [_pick(100, 1)], top=5)
    assert len(plan['open']) == 4 and plan['reserve'] is None


def test_sheet_changes_lists_the_edits_in_sheet_order():
    rows = [_row(1, 0.66, minutes=30), _row(2, 0.64, minutes=10),
            _row(3, 0.62, minutes=50), _row(4, 0.60, minutes=20),
            _row(5, 0.58), _row(6, 0.57), _row(7, 0.56), _row(8, 0.55),
            _row(9, 0.54)]
    held = [_pick(100, 1, points=1.0), _pick(101, 2, points=0.0)]
    plan = edge.plan_sheet(rows, held)          # opens 1-6, reserve 7
    current = [
        _pick(1, 3, prob=0.66, minutes=30),                   # keep
        _pick(2, 4, side='away', prob=0.36, minutes=10),      # flip
        _pick(50, 5, market='total', side='over', is_best=True,
              prob=0.45),                                     # remove
        _pick(60, 9, prob=0.5),                               # reserve moves
    ]
    changes = edge.sheet_changes(current, plan)
    assert [(c['action'], c['label']) for c in changes] == [
        ('remove', 'P50 total over'),
        ('flip', 'G2 spread home'),
        ('reserve', 'G7 spread home'),
        ('add', 'G5 spread home'),          # earliest kickoff first
        ('add', 'G6 spread home'),
        ('add', 'G4 spread home'),
        ('add', 'G3 spread home'),
        ('headliner', 'G1 spread home'),
        ('keep', 'P1 spread home'),
    ]
    by_action = {c['action']: c for c in changes}
    assert by_action['flip']['was'] == 'P2 spread away'
    assert by_action['reserve']['was'] == 'P60 spread home'
    assert by_action['headliner']['was'] == 'P50 total over'


def test_sheet_changes_quiet_when_the_sheet_already_matches():
    rows = _ranked()
    plan = edge.plan_sheet(rows)
    current = [_pick(r['game_id'], i, is_best=i == 1, prob=r['prob'])
               for i, r in enumerate(plan['open'], 1)]
    current.append(_pick(plan['reserve']['game_id'], 9, prob=0.5))
    changes = edge.sheet_changes(current, plan)
    assert {c['action'] for c in changes} == {'keep'}


def test_a_held_headliner_needs_no_headliner_change():
    rows = _ranked()
    plan = edge.plan_sheet(rows, [_pick(100, 1, is_best=True, points=0.0)])
    changes = edge.sheet_changes([], plan)
    assert 'headliner' not in {c['action'] for c in changes}
    assert sum(c['action'] == 'add' for c in changes) == 7


def test_a_reserve_on_a_planned_game_goes_when_no_reserve_is_left():
    rows = _ranked(6)                       # all six fill the open slots
    held = [_pick(100, 1, points=1.0), _pick(101, 2, points=0.0)]
    plan = edge.plan_sheet(rows, held)
    assert plan['reserve'] is None
    current = [_pick(3, 9, prob=rows[2]['prob'])]   # reserve on planned game 3
    changes = edge.sheet_changes(current, plan)
    assert changes[0]['action'] == 'remove'
    assert changes[0]['label'] == 'P3 spread home'
    assert ('add', 'G3 spread home') in [(c['action'], c['label'])
                                         for c in changes]


def test_a_reserve_off_the_plan_stays_when_no_reserve_is_left():
    plan = edge.plan_sheet(_ranked(6), [_pick(100, 1), _pick(101, 2)])
    changes = edge.sheet_changes([_pick(77, 9, prob=0.5)], plan)
    assert 'remove' not in {c['action'] for c in changes}
