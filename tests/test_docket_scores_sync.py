"""Two-sport score sync (games/docket/services/scores.py).

Locks D22 identity (matching is api_event_id only — no team-name fallback),
the both-or-neither score contract the engine depends on, the one-way
is_final latch, the admin-only no_contest column, per-sport failure
isolation, and the daysFrom cap that D12's midweek cadence exists to serve.
All API traffic is mocked at the module's odds_api_get import site.
"""
from datetime import datetime
from typing import ClassVar
from unittest.mock import patch

from extensions import db
from tests._docket_fixtures import make_game, make_week

KICK = datetime(2026, 9, 5, 18, 0)


def _resp(payload, status=200):
    class _R:
        status_code = status
        headers: ClassVar[dict] = {'x-requests-remaining': '441',
                                   'x-requests-used': '59'}

        def json(self):
            return payload

    return _R()


def _event(eid, home, away, home_score=None, away_score=None,
           completed=False):
    scores = None
    if home_score is not None or away_score is not None:
        scores = []
        if home_score is not None:
            scores.append({'name': home, 'score': str(home_score)})
        if away_score is not None:
            scores.append({'name': away, 'score': str(away_score)})
    return {'id': eid, 'home_team': home, 'away_team': away,
            'completed': completed, 'scores': scores}


def _run(app, ncaaf, nfl=(), **kwargs):
    from games.docket.services.scores import sync_scores

    app.config['ODDS_API_KEY'] = 'test-key'
    with patch('games.docket.services.scores.odds_api_get',
               side_effect=[_resp(list(ncaaf)), _resp(list(nfl))]) as mock:
        summary = sync_scores(1, **kwargs)
    return summary, mock


def _seed_game(week, eid, **kwargs):
    game = make_game(week, kickoff=KICK, **kwargs)
    game.api_event_id = eid
    db.session.flush()
    return game


def test_completed_event_writes_scores_and_finalizes(app):
    week = make_week(1)
    game = _seed_game(week, 'e-1', home='Notre Dame', away='Wisconsin')
    db.session.commit()

    summary, _mock = _run(app, [_event('e-1', 'Notre Dame', 'Wisconsin',
                                       home_score=27, away_score=17,
                                       completed=True)])

    assert (game.home_score, game.away_score) == (27, 17)
    assert game.is_final is True
    assert game.no_contest is False, 'no_contest is an admin ruling only'
    assert summary['finalized'] == 1
    assert summary['scores_written'] == 1


def test_in_progress_event_records_the_score_without_finalizing(app):
    week = make_week(1)
    game = _seed_game(week, 'e-1', home='Notre Dame', away='Wisconsin')
    db.session.commit()

    summary, _mock = _run(app, [_event('e-1', 'Notre Dame', 'Wisconsin',
                                       home_score=14, away_score=7)])

    assert (game.home_score, game.away_score) == (14, 7)
    assert game.is_final is False, 'grading must never see a live score'
    assert summary['in_progress'] == 1


def test_is_final_is_one_way(app):
    """A feed that flaps back to in-progress must not un-grade a week."""
    week = make_week(1)
    game = _seed_game(week, 'e-1', home='Notre Dame', away='Wisconsin')
    db.session.commit()

    _run(app, [_event('e-1', 'Notre Dame', 'Wisconsin', home_score=27,
                      away_score=17, completed=True)])
    assert game.is_final is True

    # Same game, now reported live again with a corrected score.
    summary, _mock = _run(app, [_event('e-1', 'Notre Dame', 'Wisconsin',
                                       home_score=28, away_score=17)])
    assert game.is_final is True
    assert (game.home_score, game.away_score) == (28, 17), \
        'a real correction still lands'
    assert summary['scores_written'] == 1


def test_a_live_score_can_never_reach_the_engine(app):
    """The finality contract lives in the ADAPTER, not the snapshot type.

    GameSnapshot.is_final is score-presence, so writing a live score here
    would be dangerous if build_week_snapshot passed it through — it doesn't:
    it gates on the persisted is_final column. This locks that gate, since
    the CLI grades immediately after a scores run.
    """
    from games.docket.services.grading_pass import build_week_snapshot

    week = make_week(1)
    game = _seed_game(week, 'e-1', home='Notre Dame', away='Wisconsin')
    game.kickoff_at_deadline = KICK
    week.tiebreaker_game_id = game.id
    db.session.commit()

    _run(app, [_event('e-1', 'Notre Dame', 'Wisconsin', home_score=14,
                      away_score=7)])

    assert (game.home_score, game.away_score) == (14, 7)
    snapshot = build_week_snapshot(week)
    assert snapshot.games[0].home_score is None
    assert snapshot.games[0].is_final is False, \
        'a live score must not satisfy the engine\'s final-score contract'


def test_a_partial_score_pair_is_refused(app):
    """GameSnapshot's both-or-neither contract: half a score would grade as
    a real result with a phantom zero."""
    week = make_week(1)
    game = _seed_game(week, 'e-1', home='Notre Dame', away='Wisconsin')
    db.session.commit()

    summary, _mock = _run(app, [_event('e-1', 'Notre Dame', 'Wisconsin',
                                       home_score=27, completed=True)])

    assert (game.home_score, game.away_score) == (None, None)
    assert game.is_final is False
    assert summary['no_scores'] == 1


def test_matching_is_by_event_id_only(app):
    """D22: identity is the API event id end-to-end. A right-named event
    with the wrong id is NOT this game."""
    week = make_week(1)
    game = _seed_game(week, 'e-1', home='Notre Dame', away='Wisconsin')
    db.session.commit()

    summary, _mock = _run(app, [_event('e-OTHER', 'Notre Dame', 'Wisconsin',
                                       home_score=27, away_score=17,
                                       completed=True)])

    assert game.home_score is None
    assert summary['unmatched'] == 1


def test_one_sport_failing_never_costs_the_other_its_update(app):
    from games.docket.services.scores import sync_scores

    week = make_week(1)
    game = _seed_game(week, 'e-nfl', home='Chiefs', away='Ravens',
                      sport='americanfootball_nfl')
    db.session.commit()
    app.config['ODDS_API_KEY'] = 'test-key'

    # NCAAF 500s; NFL succeeds. (SPORTS order is ncaaf, nfl.)
    with patch('games.docket.services.scores.odds_api_get',
               side_effect=[_resp([], status=500),
                            _resp([_event('e-nfl', 'Chiefs', 'Ravens',
                                          home_score=24, away_score=20,
                                          completed=True)])]):
        summary = sync_scores(1)

    assert summary['status'] == 'partial'
    assert len(summary['errors']) == 1
    assert (game.home_score, game.away_score) == (24, 20)
    assert game.is_final is True


def test_days_from_is_capped_at_the_api_maximum(app):
    week = make_week(1)
    _seed_game(week, 'e-1')
    db.session.commit()

    _summary, mock = _run(app, [], days_from=30)

    for call in mock.call_args_list:
        assert call.kwargs['params']['daysFrom'] == 3


def test_a_missing_key_or_week_reports_instead_of_raising(app):
    from games.docket.services.scores import sync_scores

    app.config['ODDS_API_KEY'] = ''
    assert sync_scores(1)['status'] == 'error'

    app.config['ODDS_API_KEY'] = 'test-key'
    with patch('games.docket.services.scores.odds_api_get') as mock:
        result = sync_scores(1)
    assert result['status'] == 'error'
    assert 'no docket week 1' in result['errors'][0]
    # A missing week must not spend credits.
    mock.assert_not_called()


# --- Captured live payload -------------------------------------------------
# Verbatim from The Odds API, 2026-08-12: GET /v4/sports/baseball_mlb/scores/
# ?daysFrom=1 (HTTP 200, x-requests-last: 2). MLB rather than football because
# the probe needed a sport with games ALREADY COMPLETE — every fixture above
# is hand-built, so until this ran nothing had confirmed that the shapes they
# assume are the shapes the API actually sends.
#
# What it settles, all three verified across the 30 events in that response:
#   * scores[].name repeats home_team/away_team VERBATIM — the one place D22's
#     id-only matching still leans on a name. An abbreviation here would make
#     _event_scores return (None, None) for every game and no week would grade.
#   * score is a STRING ("3"), never a number, so the int() cast is load-
#     bearing rather than defensive.
#   * a game that has not started carries scores: null — the key is present
#     with a null value, which is why the reader coalesces rather than .get()s
#     a default.
LIVE_COMPLETED = {
    'id': 'bbf1e6cb506f7bad49e73490f15d2a14',
    'sport_key': 'baseball_mlb',
    'sport_title': 'MLB',
    'commence_time': '2026-08-12T01:39:00Z',
    'completed': True,
    'home_team': 'Los Angeles Angels',
    'away_team': 'Texas Rangers',
    'scores': [
        {'name': 'Los Angeles Angels', 'score': '3'},
        {'name': 'Texas Rangers', 'score': '2'},
    ],
    'last_update': '2026-08-12T17:36:22Z',
}

LIVE_IN_PROGRESS = {
    'id': 'f6f17db1f13670f04ec571027601d33c',
    'sport_key': 'baseball_mlb',
    'sport_title': 'MLB',
    'commence_time': '2026-08-12T22:41:00Z',
    'completed': False,
    'home_team': 'Miami Marlins',
    'away_team': 'Pittsburgh Pirates',
    'scores': [
        {'name': 'Miami Marlins', 'score': '8'},
        {'name': 'Pittsburgh Pirates', 'score': '2'},
    ],
    'last_update': '2026-08-13T00:58:21Z',
}

LIVE_NOT_STARTED = {
    'id': 'b0c3869f276e1d63fbbce0cfdcbf8f1c',
    'sport_key': 'baseball_mlb',
    'sport_title': 'MLB',
    'commence_time': '2026-08-13T02:10:00Z',
    'completed': False,
    'home_team': 'Los Angeles Dodgers',
    'away_team': 'Kansas City Royals',
    'scores': None,
    'last_update': '2026-08-13T00:58:21Z',
}


def test_live_completed_payload_parses():
    """The branch no mocked test could prove: a real populated scores array."""
    from games.docket.services.scores import _event_scores

    assert _event_scores(LIVE_COMPLETED) == (3, 2)


def test_live_in_progress_payload_parses_but_is_not_final():
    """Scores arrive before `completed` flips. sync_scores writes them and
    leaves is_final alone, which is what keeps a live score out of grading."""
    from games.docket.services.scores import _event_scores

    assert _event_scores(LIVE_IN_PROGRESS) == (8, 2)
    assert LIVE_IN_PROGRESS['completed'] is False


def test_live_not_started_payload_yields_no_scores():
    """scores is null, not absent and not []."""
    from games.docket.services.scores import _event_scores

    assert _event_scores(LIVE_NOT_STARTED) == (None, None)


def test_live_payload_sport_agnostic_shape_matches_the_hand_built_fixtures():
    """The football fixtures above are trusted only because this holds: the
    captured payload's shape is exactly what _event() constructs."""
    built = _event('x', 'Los Angeles Angels', 'Texas Rangers',
                   home_score=3, away_score=2, completed=True)
    assert built['scores'] == LIVE_COMPLETED['scores']
    assert set(built) <= set(LIVE_COMPLETED)
