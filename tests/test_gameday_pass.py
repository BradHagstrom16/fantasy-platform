"""The shared game-day scores pass (games/gameday.py, ADR-063).

Same-evening finals for CFB Survivor and The Docket on one `/scores` call
per sport. Locks the seam's contract (wanted sports, the credit floor, the
one-fetch-per-sport rule, per-consumer isolation with a rollback between
consumers), each game's "could a tracked game have ended?" guard, and the
two prefetched-events paths that keep the daily passes untouched: CFB's
`run_scores(prefetched=…, notify=False, retry_open=False)` and the
Docket's `sync_scores(…, events_by_sport=…)`.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from extensions import db
from games import gameday
from games.cfb.services import automation as cfb_automation
from games.cfb.services.score_fetcher import ScoreFetcher
from games.docket.services import gameday as docket_gameday
from games.docket.services import scores as docket_scores
from tests import _cfb_fixtures as cfb
from tests import _docket_fixtures as docket
from utils.odds_api import OddsApiError

NCAAF = 'americanfootball_ncaaf'
NFL = 'americanfootball_nfl'

# CFB fixture week: deadline Sat Jan 3 2026 11:00 CT (naive pool wall clock,
# tests/_cfb_fixtures.PAST_DEADLINE). Kickoff at noon CT; "now" values are
# CFB_FAKE_NOW (UTC) — 16:30 CT is 4.5 h after kickoff.
CFB_KICK = datetime(2026, 1, 3, 12, 0)
CFB_NOW_4H = '2026-01-03T22:30:00'
CFB_NOW_2H = '2026-01-03T20:00:00'
CFB_NOW_13H = '2026-01-04T07:00:00'

# Docket: every column is naive UTC. Kickoff Sat Sep 5 noon CT.
DK_KICK = datetime(2026, 9, 5, 17, 0)
DK_NOW_4H = '2026-09-05T21:30:00'
DK_NOW_2H = '2026-09-05T19:00:00'
DK_NOW_13H = '2026-09-06T06:00:00'


def _cfb_now(monkeypatch, iso):
    monkeypatch.setenv('ENVIRONMENT', 'testing')
    monkeypatch.setenv('CFB_FAKE_NOW', iso)


def _seed_cfb(*, kick=CFB_KICK, winner=None, no_contest=False, scored=False,
              deadline=None, complete=False):
    week = cfb.make_week(1, deadline=deadline, is_complete=complete)
    t1, t2 = cfb.make_team('T1'), cfb.make_team('T2')
    game = cfb.make_game(week, t1, t2, winner=winner, no_contest=no_contest)
    game.game_time = kick
    if scored:
        game.home_score, game.away_score = 20, 20
    db.session.commit()
    return week, game


def _seed_docket(*, kickoff=DK_KICK, sport=NCAAF, final=False,
                 no_contest=False, graded=False, eid='e-1'):
    week = docket.make_week(1)
    game = docket.make_game(week, kickoff=kickoff, sport=sport,
                            home='Notre Dame', away='Wisconsin')
    game.api_event_id = eid
    game.is_final = final
    game.no_contest = no_contest
    if graded:
        week.default_error_tenths = 0
    db.session.commit()
    return week, game


def _event(eid, home, away, home_score, away_score, completed=True):
    return {'id': eid, 'home_team': home, 'away_team': away,
            'completed': completed,
            'scores': [{'name': home, 'score': str(home_score)},
                       {'name': away, 'score': str(away_score)}]}


def _resp(payload):
    class _R:
        status_code = 200
        headers = {'x-requests-remaining': '400', 'x-requests-used': '100'}  # noqa: RUF012

        def json(self):
            return payload

    return _R()


def _fake(slug, sports, calls):
    """A consumer that wants ``sports`` and records what it is handed."""
    def apply(events_by_sport):
        calls.append((slug, events_by_sport))
        return {'slug': slug}
    return gameday.GameDayConsumer(
        slug=slug, wants=lambda s: s in sports, apply=apply)


# ── the CFB guard ─────────────────────────────────────────────────────────

@pytest.mark.parametrize('now, expected', [
    (CFB_NOW_4H, True),
    (CFB_NOW_2H, False),    # kicked off 2 h ago: cannot have ended
    (CFB_NOW_13H, False),   # 13 h: past the game-day window, daily pass's job
])
def test_cfb_wants_ncaaf_only_inside_the_game_day_window(app, monkeypatch,
                                                         now, expected):
    _seed_cfb()
    _cfb_now(monkeypatch, now)
    from games.cfb.services.gameday import CONSUMER
    assert CONSUMER.wants(NCAAF) is expected


@pytest.mark.parametrize('seed', [
    {'winner': 'home'},        # settled
    {'no_contest': True},      # ruled
    {'scored': True},          # a tie awaiting a hand ruling — stop polling
    {'complete': True},        # the week is done
    {'deadline': datetime(2026, 1, 3, 18, 0)},   # pre-deadline: never graded early
])
def test_cfb_never_wants_a_game_it_would_not_grade(app, monkeypatch, seed):
    _seed_cfb(**seed)
    _cfb_now(monkeypatch, CFB_NOW_4H)
    from games.cfb.services.gameday import CONSUMER
    assert CONSUMER.wants(NCAAF) is False


def test_cfb_ignores_a_game_with_no_kickoff_and_never_wants_nfl(app, monkeypatch):
    _seed_cfb(kick=None)
    _cfb_now(monkeypatch, CFB_NOW_4H)
    from games.cfb.services.gameday import CONSUMER
    assert CONSUMER.wants(NCAAF) is False
    _seed_cfb.__wrapped__ = None  # no-op; keeps the helper reusable below
    assert CONSUMER.wants(NFL) is False


# ── the Docket guard ──────────────────────────────────────────────────────

@pytest.mark.parametrize('now, expected', [
    (DK_NOW_4H, True),
    (DK_NOW_2H, False),
    (DK_NOW_13H, False),
])
def test_docket_wants_a_sport_only_inside_the_game_day_window(app, monkeypatch,
                                                              now, expected):
    _seed_docket()
    docket.at(monkeypatch, now)
    assert docket_gameday.CONSUMER.wants(NCAAF) is expected


@pytest.mark.parametrize('seed', [
    {'final': True},
    {'no_contest': True},
    {'graded': True},
    {'sport': NFL},   # the question is per sport
])
def test_docket_never_wants_a_game_it_would_not_grade(app, monkeypatch, seed):
    _seed_docket(**seed)
    docket.at(monkeypatch, DK_NOW_4H)
    assert docket_gameday.CONSUMER.wants(NCAAF) is False


# ── the seam ──────────────────────────────────────────────────────────────

def test_idle_run_makes_no_http_call(app):
    calls = []
    with patch.object(gameday, '_consumers',
                      return_value=(_fake('a', (), calls),)), \
         patch.object(gameday, 'odds_api_get') as http, \
         patch.object(gameday, 'odds_credits_remaining') as probe:
        summary = gameday.run_game_day()
    assert summary['status'] == 'idle'
    assert not http.called and not probe.called
    assert calls == []


def test_credit_floor_stops_the_run_before_any_scores_call(app):
    app.config['ODDS_API_KEY'] = 'k'
    calls = []
    with patch.object(gameday, '_consumers',
                      return_value=(_fake('a', (NCAAF,), calls),)), \
         patch.object(gameday, 'odds_api_get') as http, \
         patch.object(gameday, 'odds_credits_remaining', return_value=90):
        summary = gameday.run_game_day()
    assert summary['status'] == 'floor'
    assert summary['remaining'] == 90
    assert not http.called
    assert calls == []


def test_a_failed_probe_never_blocks_the_run(app):
    app.config['ODDS_API_KEY'] = 'k'
    calls = []
    with patch.object(gameday, '_consumers',
                      return_value=(_fake('a', (NCAAF,), calls),)), \
         patch.object(gameday, 'odds_api_get', return_value=_resp([])) as http, \
         patch.object(gameday, 'odds_credits_remaining', return_value=None):
        summary = gameday.run_game_day()
    assert summary['status'] == 'ok'
    assert http.call_count == 1
    assert calls == [('a', {NCAAF: []})]


def test_one_call_per_wanted_sport_and_each_consumer_gets_only_its_sports(app):
    app.config['ODDS_API_KEY'] = 'k'
    calls = []
    consumers = (_fake('cfb', (NCAAF,), calls),
                 _fake('docket', (NCAAF, NFL), calls),
                 _fake('bystander', (), calls))
    payloads = {NCAAF: [{'id': 'c'}], NFL: [{'id': 'n'}]}

    def fetch(url, params=None, **_kw):
        sport = url.split('/sports/')[1].split('/')[0]
        assert params['daysFrom'] == 3, 'any daysFrom costs 2; use the widest'
        return _resp(payloads[sport])

    with patch.object(gameday, '_consumers', return_value=consumers), \
         patch.object(gameday, 'odds_api_get', side_effect=fetch) as http, \
         patch.object(gameday, 'odds_credits_remaining', return_value=400):
        summary = gameday.run_game_day()

    assert summary['status'] == 'ok'
    assert http.call_count == 2, 'one /scores call per sport, never per game'
    assert sorted(summary['fetched']) == [NCAAF, NFL]
    assert calls == [
        ('cfb', {NCAAF: [{'id': 'c'}]}),
        ('docket', {NCAAF: [{'id': 'c'}], NFL: [{'id': 'n'}]}),
    ], 'the bystander wanted nothing and must never be called'


def test_a_failed_sport_is_absent_and_the_other_still_lands(app):
    app.config['ODDS_API_KEY'] = 'k'
    calls = []
    consumers = (_fake('docket', (NCAAF, NFL), calls),)

    def fetch(url, params=None, **_kw):
        if NFL in url:
            raise OddsApiError('nfl down')
        return _resp([{'id': 'c'}])

    with patch.object(gameday, '_consumers', return_value=consumers), \
         patch.object(gameday, 'odds_api_get', side_effect=fetch), \
         patch.object(gameday, 'odds_credits_remaining', return_value=400):
        summary = gameday.run_game_day()

    assert summary['status'] == 'error'
    assert any('nfl down' in e for e in summary['errors'])
    assert calls == [('docket', {NCAAF: [{'id': 'c'}]})], \
        'a sport whose fetch failed is ABSENT, never None or []'


def test_a_failing_consumer_is_rolled_back_and_the_next_one_still_runs(app):
    app.config['ODDS_API_KEY'] = 'k'
    calls = []

    def boom(_events):
        raise RuntimeError('cfb blew up')

    consumers = (
        gameday.GameDayConsumer(slug='cfb', wants=lambda s: s == NCAAF,
                                apply=boom),
        _fake('docket', (NCAAF,), calls),
    )
    with patch.object(gameday, '_consumers', return_value=consumers), \
         patch.object(gameday, 'odds_api_get', return_value=_resp([])), \
         patch.object(gameday, 'odds_credits_remaining', return_value=400), \
         patch.object(gameday.db.session, 'rollback',
                      wraps=gameday.db.session.rollback) as rollback:
        summary = gameday.run_game_day()

    assert summary['status'] == 'error'
    assert any('cfb blew up' in e for e in summary['errors'])
    assert calls == [('docket', {NCAAF: []})]
    assert rollback.called, 'a dirty session must not reach the next consumer'


# ── the CLI ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize('args', [['scores', 'game-day'],
                                  ['scores', 'game-day', '--scheduled']])
def test_cli_exits_zero_on_idle_with_or_without_scheduled(app, args):
    runner = app.test_cli_runner()
    with patch.object(gameday, '_consumers', return_value=()):
        result = runner.invoke(args=args)
    assert result.exit_code == 0, result.output
    assert 'idle' in result.output


def test_cli_exits_one_when_the_pass_reports_an_error(app):
    runner = app.test_cli_runner()
    with patch.object(gameday, 'run_game_day',
                      return_value={'status': 'error', 'errors': ['x'],
                                    'wanted': [], 'fetched': [],
                                    'applied': {}, 'remaining': None}):
        result = runner.invoke(args=['scores', 'game-day', '--scheduled'])
    assert result.exit_code == 1


# ── CFB: the prefetched path ──────────────────────────────────────────────

def _seed_cfb_split_week():
    """One game the events will decide (T2 wins 10-20), one unplayed, three
    members: a loser on T1, a winner on T2, one waiting on T3."""
    week = cfb.make_week(1)
    t1, t2, t3, t4 = (cfb.make_team(n) for n in ('T1', 'T2', 'T3', 'T4'))
    # Lines on file: a week whose games never got a line is "never opened"
    # and run_scores refuses to grade it (ADR-062).
    decided = cfb.make_game(week, t1, t2, spread=-3.5)
    cfb.make_game(week, t3, t4, spread=2.5)
    members = {}
    for name, team in (('loser', t1), ('winner', t2), ('waiting', t3)):
        user = cfb.make_user(name)
        members[name] = (cfb.make_enrollment(user, lives=2),
                         cfb.make_pick(user, week, team))
    db.session.commit()
    return week, decided, members


def test_cfb_prefetched_events_grade_per_game_without_http_or_mail(app):
    week, _decided, members = _seed_cfb_split_week()
    events = [_event('evt1', 'T1', 'T2', 10, 20)]

    with patch('games.cfb.services.score_fetcher.odds_api_get') as http, \
         patch.object(cfb_automation, '_send_admin_email') as mail, \
         patch.object(cfb_automation, 'run_spread_update') as opener:
        outcome = cfb_automation.run_scores(prefetched=events, notify=False,
                                            retry_open=False)

    assert not http.called
    assert not mail.called
    assert not opener.called
    assert outcome['week_results'][0]['status'] == 'partial'
    assert members['loser'][0].lives_remaining == 1
    assert members['loser'][1].is_correct is False
    assert members['winner'][1].is_correct is True
    assert members['waiting'][1].is_correct is None
    assert week.is_complete is False


def test_cfb_daily_path_is_unchanged_it_still_mails_and_retries_the_open(app):
    week, decided, _members = _seed_cfb_split_week()
    fake_fetch = {
        'matched_completed': [{'game_id': decided.id, 'home_team': 'T1',
                               'away_team': 'T2', 'home_score': 10,
                               'away_score': 20, 'match_method': 'event_id',
                               'api_event_id': 'evt1'}],
        'matched_in_progress': [], 'unmatched': [],
        'api_credits_remaining': None, 'error': None,
    }
    candidate = type('W', (), {'is_active': False,
                               'picks_open_notified': False,
                               'week_number': 2})()

    with patch.object(ScoreFetcher, 'fetch_scores_for_week',
                      return_value=fake_fetch) as fetch, \
         patch.object(cfb_automation, '_send_admin_email') as mail, \
         patch.object(cfb_automation, '_week_to_open', return_value=candidate), \
         patch.object(cfb_automation, 'run_spread_update',
                      return_value={'opened': True}) as opener:
        cfb_automation.run_scores()

    fetch.assert_called_once_with(week.id, events=None)
    assert mail.called
    assert opener.called


def test_cfb_fetch_with_events_skips_http_but_keeps_its_refusals(app, monkeypatch):
    """The pre-deadline refusal stays in front of the prefetched path: a
    Thursday game is not graded before Saturday 11:00."""
    _cfb_now(monkeypatch, CFB_NOW_4H)
    week, _game = _seed_cfb(deadline=datetime(2026, 1, 3, 18, 0))
    with patch('games.cfb.services.score_fetcher.odds_api_get') as http:
        result = ScoreFetcher().fetch_scores_for_week(week.id, events=[])
    assert 'deadline has not passed' in result['error']
    assert not http.called


def test_cfb_consumer_raises_when_a_week_errors(app):
    from games.cfb.services.gameday import CONSUMER
    outcome = {'week_results': [{'week_number': 1, 'status': 'error',
                                 'details': 'boom'}]}
    with patch.object(cfb_automation, 'run_scores', return_value=outcome), \
         pytest.raises(RuntimeError, match='boom'):
        CONSUMER.apply({NCAAF: []})


def test_cfb_consumer_treats_partial_as_success(app):
    from games.cfb.services.gameday import CONSUMER
    outcome = {'week_results': [{'week_number': 1, 'status': 'partial',
                                 'details': 'No completed games found.'}]}
    with patch.object(cfb_automation, 'run_scores',
                      return_value=outcome) as run:
        assert CONSUMER.apply({NCAAF: [{'id': 'x'}]}) is outcome
    run.assert_called_once_with(prefetched=[{'id': 'x'}], notify=False,
                                retry_open=False)


# ── Docket: the prefetched path ───────────────────────────────────────────

def test_docket_prefetched_events_finalize_without_http(app, monkeypatch):
    _week, game = _seed_docket()
    docket.at(monkeypatch, DK_NOW_4H)
    events = {NCAAF: [_event('e-1', 'Notre Dame', 'Wisconsin', 27, 17)]}

    with patch.object(docket_scores, 'odds_api_get') as http:
        result = docket_gameday.CONSUMER.apply(events)

    assert not http.called
    assert game.is_final is True
    assert (game.home_score, game.away_score) == (27, 17)
    assert result[1]['grade']['status'] == 'not_ready', \
        'a Saturday grade attempt is the ordinary WeekNotReady no-op'


def test_docket_sync_never_fetches_a_sport_absent_from_the_dict(app):
    week = docket.make_week(1)
    ncaaf = docket.make_game(week, kickoff=DK_KICK, home='A', away='B')
    ncaaf.api_event_id = 'c-1'
    nfl = docket.make_game(week, kickoff=DK_KICK, sport=NFL, home='C', away='D')
    nfl.api_event_id = 'n-1'
    db.session.commit()
    app.config['ODDS_API_KEY'] = 'k'

    with patch.object(docket_scores, 'odds_api_get') as http:
        summary = docket_scores.sync_scores(
            1, events_by_sport={NCAAF: [_event('c-1', 'A', 'B', 3, 0)]})

    assert not http.called
    assert summary['status'] == 'ok'
    assert ncaaf.is_final is True
    assert nfl.is_final is False and nfl.home_score is None


def test_docket_sync_with_no_dict_still_fetches_both_sports(app):
    docket.make_week(1)
    db.session.commit()
    app.config['ODDS_API_KEY'] = 'k'
    with patch.object(docket_scores, 'odds_api_get',
                      side_effect=[_resp([]), _resp([])]) as http:
        summary = docket_scores.sync_scores(1)
    assert http.call_count == 2
    assert summary['status'] == 'ok'


def test_docket_applies_to_the_week_that_owns_the_game_not_the_clock(app, monkeypatch):
    """Monday-night final delivered after the Tue 06:00 CT boundary: the
    clock says week 2 (no row yet), the game belongs to week 1."""
    week, game = _seed_docket(kickoff=datetime(2026, 9, 8, 0, 30))  # Mon 19:30 CT
    docket.at(monkeypatch, '2026-09-08T11:30:00')                    # Tue 06:30 CT
    assert docket_gameday.CONSUMER.wants(NCAAF) is True

    with patch.object(docket_scores, 'odds_api_get') as http:
        result = docket_gameday.CONSUMER.apply(
            {NCAAF: [_event('e-1', 'Notre Dame', 'Wisconsin', 21, 14)]})

    assert not http.called
    assert game.is_final is True
    assert list(result) == [week.week_number]
