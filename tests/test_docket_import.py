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
    from sqlalchemy import select

    from extensions import db
    from games.docket.models import DocketGame

    return db.session.scalars(
        select(DocketGame).filter_by(api_event_id=eid)).one()


def _count(eid):
    from sqlalchemy import func, select

    from extensions import db
    from games.docket.models import DocketGame

    return db.session.scalar(
        select(func.count()).select_from(DocketGame)
        .where(DocketGame.api_event_id == eid))


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


def test_a_replayed_lines_run_cannot_move_an_already_frozen_kickoff(app):
    """docket-lines.timer carries Persistent=true, so a firing missed to an
    outage replays later — possibly after the deadline pass has already run.

    That is safe, and this is the reason: stamp_kickoffs writes
    kickoff_at_deadline only where it is NULL, so the D7 ordering input is
    immutable once frozen. The live kickoff column keeps tracking reality
    (D19); the frozen one keeps describing the docket the players saw. The
    two are allowed to disagree, and grading reads only the frozen one.
    """
    from games.docket.services.deadline_pass import stamp_kickoffs
    from games.docket.services.weeks import deadline_utc
    from games.docket.utils import to_naive_utc

    _run(app, [W1],
         [_odds('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                '2026-09-06T00:30:00Z',
                [_bm('draftkings', home='Notre Dame Fighting Irish',
                     home_spread=-6.5, away='Wisconsin Badgers', total=51.5)])])
    game = _get('e-wnd')
    week = game.week
    week.deadline_at = to_naive_utc(deadline_utc(1))
    stamp_kickoffs(week)
    frozen = game.kickoff_at_deadline
    assert frozen == datetime(2026, 9, 6, 0, 30)

    # The catch-up run, with a kickoff that moved three hours later.
    _run(app, [_event('e-wnd', 'Notre Dame Fighting Irish',
                      'Wisconsin Badgers', '2026-09-06T03:30:00Z')], [])

    game = _get('e-wnd')
    assert game.kickoff == datetime(2026, 9, 6, 3, 30), 'D19 refresh still runs'
    assert game.kickoff_at_deadline == frozen, (
        'a replayed lines run must never move an already-frozen kickoff')


def test_exact_end_boundary_kickoff_belongs_to_the_next_week(app):
    """Half-open window: a kickoff exactly at end_at is NOT this week's game."""
    boundary_kick = _event('e-boundary', 'Texas Longhorns',
                           'Ohio State Buckeyes', '2026-09-08T11:00:00Z')
    inside_kick = _event('e-inside', 'Texas Longhorns',
                         'Ohio State Buckeyes', '2026-09-08T10:59:59Z')
    # Different event ids, same teams — identity is api_event_id (D22).
    inside_kick['id'] = 'e-inside'
    _run(app, [boundary_kick, inside_kick], [])
    assert _count('e-boundary') == 0
    assert _count('e-inside') == 1


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


def test_malformed_200_payload_fails_that_sport_only(app):
    """CR round 2: a 200 whose body is not an array of objects (an error
    envelope, a stray scalar) must become a per-sport failure — never an
    AttributeError that aborts the other sport's import."""
    from games.docket.services.importer import import_week

    app.config['ODDS_API_KEY'] = 'test-key'
    nfl_game = _event('e-nfl', 'Green Bay Packers', 'Chicago Bears',
                      '2026-09-07T00:20:00Z')
    # ncaaf /events: 200 with an object body -> that sport fails, no /odds
    # call for it; nfl proceeds normally.
    responses = [_resp({'message': 'quota note, not a list'}),
                 _resp([nfl_game]), _resp([])]
    with patch('games.docket.services.importer.odds_api_get',
               side_effect=responses):
        summary = import_week(1)
    assert summary['status'] == 'partial'
    assert len(summary['errors']) == 1
    assert 'americanfootball_ncaaf' in summary['errors'][0]
    assert _count('e-nfl') == 1, 'the healthy sport must still import'

    # Same guard for an array of non-objects.
    responses = [_resp(['not-an-object']), _resp([]), _resp([])]
    with patch('games.docket.services.importer.odds_api_get',
               side_effect=responses):
        summary = import_week(1)
    assert 'americanfootball_ncaaf' in summary['errors'][0]


def test_one_failed_sport_reports_partial_even_with_zero_creates(app):
    """A sport that completed keeps 'partial' status even when it created no
    new rows (a re-run) — completed work must never be reported as 'error'."""
    from games.docket.services.importer import import_week

    app.config['ODDS_API_KEY'] = 'test-key'
    # First run: create the game normally.
    _run(app, [W1], [])

    def _fail_nfl(url, params=None):
        if 'americanfootball_nfl' in url:
            from utils.odds_api import OddsApiError
            raise OddsApiError('sustained outage')
        return _resp([W1] if url.endswith('/events') else [])

    with patch('games.docket.services.importer.odds_api_get',
               side_effect=_fail_nfl):
        summary = import_week(1)
    assert summary['created'] == 0
    assert summary['status'] == 'partial'
    assert summary['errors'] and 'americanfootball_nfl' in summary['errors'][0]


def _urls(mock):
    return [call.args[0] for call in mock.call_args_list]


def test_a_fully_locked_sport_skips_its_odds_call(app):
    """The /odds fetch costs 2 credits per sport per run against a 500/month
    budget, and a docket with no empty market has nothing left to gap-fill.
    The FREE /events kickoff refresh (D19) still runs."""
    from games.docket.services.importer import import_week

    app.config['ODDS_API_KEY'] = 'test-key'
    _run(app, [W1],
         [_odds('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                '2026-09-06T00:30:00Z',
                [_bm('draftkings', home='Notre Dame Fighting Irish',
                     home_spread=-6.5, away='Wisconsin Badgers', total=51.5)])])

    moved = _event('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                   '2026-09-06T01:00:00Z')
    with patch('games.docket.services.importer.odds_api_get',
               side_effect=[_resp([moved]), _resp([])]) as mock:
        summary = import_week(1)

    assert [u.rsplit('/', 1)[-1] for u in _urls(mock)] == ['events', 'events']
    assert summary['odds_skipped'] == ['americanfootball_ncaaf',
                                       'americanfootball_nfl']
    assert summary['kickoff_moved'] == 1
    assert _get('e-wnd').kickoff == datetime(2026, 9, 6, 1, 0)


def test_a_sport_with_an_open_market_still_fetches_odds(app):
    """The skip is per sport and computed AFTER the events sync, so a game
    created by this very run still gets the fetch it needs."""
    from games.docket.services.importer import import_week

    app.config['ODDS_API_KEY'] = 'test-key'
    # Locked spread, no total anywhere: the total market stays open.
    _run(app, [W1],
         [_odds('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                '2026-09-06T00:30:00Z',
                [_bm('draftkings', home='Notre Dame Fighting Irish',
                     home_spread=-6.5, away='Wisconsin Badgers')])])

    with patch('games.docket.services.importer.odds_api_get',
               side_effect=[_resp([W1]), _resp([]), _resp([]),
                            _resp([])]) as mock:
        summary = import_week(1)

    assert [u.rsplit('/', 1)[-1] for u in _urls(mock)] == [
        'events', 'odds', 'events']
    # NFL has no games on this week's docket at all — same answer, same
    # saving, which is exactly the CFB Week 1 shape (NFL opens in week 2).
    assert summary['odds_skipped'] == ['americanfootball_nfl']


def test_force_odds_overrides_the_skip(app):
    from games.docket.services.importer import import_week

    app.config['ODDS_API_KEY'] = 'test-key'
    _run(app, [W1],
         [_odds('e-wnd', 'Notre Dame Fighting Irish', 'Wisconsin Badgers',
                '2026-09-06T00:30:00Z',
                [_bm('draftkings', home='Notre Dame Fighting Irish',
                     home_spread=-6.5, away='Wisconsin Badgers', total=51.5)])])

    with patch('games.docket.services.importer.odds_api_get',
               side_effect=[_resp([W1]), _resp([]), _resp([]),
                            _resp([])]) as mock:
        summary = import_week(1, force_odds=True)

    assert [u.rsplit('/', 1)[-1] for u in _urls(mock)] == [
        'events', 'odds', 'events', 'odds']
    assert summary['odds_skipped'] == []
