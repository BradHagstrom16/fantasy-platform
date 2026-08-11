"""Two-sport import spine (games/docket/services/importer.py).

Locks the D3/DQ-6 analog (first fetch locks what's posted, later runs fill
gaps only, locked lines NEVER move), the D17 bookmaker-provenance policy
(DraftKings preferred, fixed fallback order, each market independent, book
recorded), the D19 kickoff refresh, the half-open week window, and the D6
naive-UTC storage contract at the functional level. All API traffic is
mocked at the importer's odds_api_get import site.
"""
from datetime import datetime
from typing import ClassVar
from unittest.mock import patch

NCAAF = 'americanfootball_ncaaf'
NFL = 'americanfootball_nfl'


def _resp(payload):
    class _R:
        status_code = 200
        headers: ClassVar[dict] = {'x-requests-remaining': '447',
                                   'x-requests-used': '53'}

        def json(self):
            return payload

    return _R()


def _event(eid, home, away, commence):
    return {'id': eid, 'home_team': home, 'away_team': away,
            'commence_time': commence}


def _bm(key, home=None, home_spread=None, away=None, total=None):
    markets = []
    if home_spread is not None:
        markets.append({'key': 'spreads', 'outcomes': [
            {'name': home, 'point': home_spread},
            {'name': away, 'point': -home_spread},
        ]})
    if total is not None:
        markets.append({'key': 'totals', 'outcomes': [
            {'name': 'Over', 'point': total},
            {'name': 'Under', 'point': total},
        ]})
    return {'key': key, 'markets': markets}


def _odds(eid, home, away, commence, bookmakers):
    return {'id': eid, 'home_team': home, 'away_team': away,
            'commence_time': commence, 'bookmakers': bookmakers}


def _run(app, ncaaf_events, ncaaf_odds, nfl_events=(), nfl_odds=()):
    from games.docket.services.importer import import_week

    app.config['ODDS_API_KEY'] = 'test-key'
    responses = [_resp(list(ncaaf_events)), _resp(list(ncaaf_odds)),
                 _resp(list(nfl_events)), _resp(list(nfl_odds))]
    with patch('games.docket.services.importer.odds_api_get',
               side_effect=responses):
        return import_week(1)


def _get(eid):
    from games.docket.models import DocketGame

    return DocketGame.query.filter_by(api_event_id=eid).one()


W1 = _event('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
            '2026-09-06T00:30:00Z')


def test_first_run_creates_games_and_locks_posted_lines(app):
    _run(app,
         [W1],
         [_odds('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                '2026-09-06T00:30:00Z',
                [_bm('draftkings', home='Notre Dame Fighting Irish',
                     home_spread=-6.5, away='Wisconsin Badgers', total=51.5)])])
    game = _get('e-wnd')
    assert game.sport == NCAAF
    assert game.week.week_number == 1
    # D6 functional lock: stored naive UTC, exactly the API's Z instant.
    assert game.kickoff == datetime(2026, 9, 6, 0, 30)
    assert game.kickoff.tzinfo is None
    assert (game.home_spread, game.spread_book) == (-6.5, 'draftkings')
    assert game.spread_locked_at is not None
    assert (game.total_points, game.total_book) == (51.5, 'draftkings')
    assert game.total_locked_at is not None
    assert game.kickoff_at_deadline is None


def test_locked_lines_never_move_and_later_runs_fill_gaps_only(app):
    """The DQ-6 analog in one scenario: a moved spread must NOT re-lock, and
    a market that was missing on the first run locks on the second."""
    # First run: spread posted, no total anywhere.
    _run(app, [W1],
         [_odds('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                '2026-09-06T00:30:00Z',
                [_bm('draftkings', home='Notre Dame Fighting Irish',
                     home_spread=-6.5, away='Wisconsin Badgers')])])
    game = _get('e-wnd')
    first_locked_at = game.spread_locked_at
    assert game.total_points is None

    # Second run: the market moved to -9.5 AND a total appeared.
    _run(app, [W1],
         [_odds('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                '2026-09-06T00:30:00Z',
                [_bm('draftkings', home='Notre Dame Fighting Irish',
                     home_spread=-9.5, away='Wisconsin Badgers', total=49.5)])])
    game = _get('e-wnd')
    assert game.home_spread == -6.5, 'a locked line may never be overwritten'
    assert game.spread_locked_at == first_locked_at
    assert (game.total_points, game.total_book) == (49.5, 'draftkings')
    assert game.total_locked_at is not None


def test_provenance_prefers_draftkings_each_market_independently(app):
    """D17: a game's spread and total may come from different books; each
    market independently walks the priority order, book recorded."""
    _run(app, [W1],
         [_odds('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                '2026-09-06T00:30:00Z',
                [_bm('fanduel', home='Notre Dame Fighting Irish',
                     home_spread=-7.0, away='Wisconsin Badgers', total=52.5),
                 _bm('draftkings', home='Notre Dame Fighting Irish',
                     away='Wisconsin Badgers', total=51.5)])])
    game = _get('e-wnd')
    assert (game.home_spread, game.spread_book) == (-7.0, 'fanduel')
    assert (game.total_points, game.total_book) == (51.5, 'draftkings')


def test_provenance_tail_is_deterministic_beyond_the_priority_list(app):
    """Books outside the fixed priority list fall back alphabetically —
    deterministic, never response-order-dependent."""
    _run(app, [W1],
         [_odds('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                '2026-09-06T00:30:00Z',
                [_bm('unibet_us', home='Notre Dame Fighting Irish',
                     home_spread=-3.0, away='Wisconsin Badgers'),
                 _bm('betsson', home='Notre Dame Fighting Irish',
                     home_spread=-3.5, away='Wisconsin Badgers')])])
    game = _get('e-wnd')
    assert (game.home_spread, game.spread_book) == (-3.5, 'betsson')


def test_kickoff_refresh_updates_live_kickoff_without_touching_locks(app):
    """D19: every run refreshes commence times from /events; the frozen
    column and locked lines stay put."""
    _run(app, [W1],
         [_odds('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                '2026-09-06T00:30:00Z',
                [_bm('draftkings', home='Notre Dame Fighting Irish',
                     home_spread=-6.5, away='Wisconsin Badgers', total=51.5)])])
    moved = _event('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                   '2026-09-06T03:30:00Z')
    _run(app, [moved], [])
    game = _get('e-wnd')
    assert game.kickoff == datetime(2026, 9, 6, 3, 30)
    assert game.home_spread == -6.5
    assert game.kickoff_at_deadline is None


def test_exact_end_boundary_kickoff_belongs_to_the_next_week(app):
    """Half-open window: a kickoff exactly at end_at is NOT this week's game."""
    from games.docket.models import DocketGame

    boundary_kick = _event('e-boundary', 'Texas Longhorns',
                           'Ohio State Buckeyes', '2026-09-08T11:00:00Z')
    inside_kick = _event('e-inside', 'Texas Longhorns',
                         'Ohio State Buckeyes', '2026-09-08T10:59:59Z')
    # Different event ids, same teams — identity is api_event_id (D22).
    inside_kick['id'] = 'e-inside'
    _run(app, [boundary_kick, inside_kick], [])
    assert DocketGame.query.filter_by(api_event_id='e-boundary').count() == 0
    assert DocketGame.query.filter_by(api_event_id='e-inside').count() == 1


def test_import_spans_both_sports(app):
    nfl_game = _event('e-nfl', 'Green Bay Packers', 'Chicago Bears',
                      '2026-09-07T00:20:00Z')
    _run(app, [W1], [], [nfl_game], [])
    assert _get('e-wnd').sport == NCAAF
    assert _get('e-nfl').sport == NFL


def test_summary_reports_created_locked_and_skipped(app):
    summary = _run(app,
                   [W1, _event('e-out', 'Texas Longhorns',
                               'Ohio State Buckeyes', '2026-09-08T11:00:00Z')],
                   [_odds('e-wnd', 'Notre Dame Fighting Irish',
                          'Wisconsin Badgers', '2026-09-06T00:30:00Z',
                          [_bm('draftkings', home='Notre Dame Fighting Irish',
                               home_spread=-6.5, away='Wisconsin Badgers',
                               total=51.5)])])
    assert summary['created'] == 1
    assert summary['spreads_locked'] == 1
    assert summary['totals_locked'] == 1
    assert summary['skipped_out_of_window'] == 1
