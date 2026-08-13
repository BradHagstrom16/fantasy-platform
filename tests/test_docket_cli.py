"""The `flask docket` CLI namespace.

Locks the operator contract rather than re-testing the services underneath:
week resolution, the non-zero exit codes T11's timers will alert on, the
recalc population (the full enrolled roster, not just submitters), and the
scores mode's grade-when-ready behavior.
"""
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select

from extensions import db
from games.docket.models import DocketPick, DocketWeekResult
from tests._docket_fixtures import (
    at,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

AFTER_DEADLINE = '2026-09-05T16:30:00'
BEFORE_DEADLINE = '2026-09-02T12:00:00'
KICK = datetime(2026, 9, 5, 18, 0)


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


def _seed(*, designate=True, final=True, games=9):
    week = make_week(1)
    rows = [
        make_game(week, kickoff=KICK, home=f'Home {i}', away=f'Away {i}',
                  home_spread=-(3.5 + i), total=40.5 + i)
        for i in range(games)
    ]
    if final:
        for game in rows:
            game.home_score, game.away_score = 31, 17
            game.is_final = True
    if designate:
        week.tiebreaker_game_id = rows[0].id
    db.session.commit()
    return week, rows


def _invoke(runner, *args):
    from games.docket.cli import docket_cli

    return runner.invoke(docket_cli, list(args))


def test_out_of_season_without_week_refuses(app, runner, monkeypatch):
    monkeypatch.setenv('DOCKET_FAKE_NOW', '2026-06-01T12:00:00')
    result = _invoke(runner, 'sync', '--mode', 'lines')
    assert result.exit_code == 1
    assert 'outside the docket season' in result.output


def test_lines_before_setup_refuses_and_names_the_fix(app, runner,
                                                      monkeypatch):
    monkeypatch.setenv('DOCKET_FAKE_NOW', '2026-09-02T12:00:00')
    result = _invoke(runner, 'sync', '--mode', 'lines')
    assert result.exit_code == 1
    assert '--mode setup' in result.output


def test_deadline_mode_reports_the_freeze_and_the_deal(app, runner,
                                                       monkeypatch):
    week, games = _seed()
    user = make_user('player')
    make_enrollment(user)
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    result = _invoke(runner, 'sync', '--mode', 'deadline')

    assert result.exit_code == 0, result.output
    assert 'stamped: 9' in result.output
    assert 'picks_added: 8' in result.output
    assert all(g.kickoff_at_deadline == KICK for g in games)


def test_deadline_mode_without_a_designation_exits_non_zero(app, runner,
                                                            monkeypatch):
    """Ruled behavior: freeze anyway, refuse the deal, and point at the fix."""
    week, games = _seed(designate=False)
    user = make_user('player')
    make_enrollment(user)
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    result = _invoke(runner, 'sync', '--mode', 'deadline')

    assert result.exit_code == 1
    assert 'AUTOPICK WAS SKIPPED' in result.output
    assert 'set-tiebreaker' in result.output
    assert all(g.kickoff_at_deadline == KICK for g in games)
    assert db.session.scalars(select(DocketPick)).all() == []


def test_recalc_grades_the_whole_roster_not_just_submitters(app, runner,
                                                             monkeypatch):
    week, _games = _seed()
    submitter = make_user('submitter')
    quiet = make_user('quiet')
    make_enrollment(submitter)
    make_enrollment(quiet)
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)
    assert _invoke(runner, 'sync', '--mode', 'deadline').exit_code == 0

    result = _invoke(runner, 'recalc', '1')

    assert result.exit_code == 0, result.output
    assert '2 players graded' in result.output
    rows = db.session.scalars(
        select(DocketWeekResult).filter_by(week_id=week.id)).all()
    assert {r.user_id for r in rows} == {submitter.id, quiet.id}


def test_recalc_is_idempotent(app, runner, monkeypatch):
    week, _games = _seed()
    make_enrollment(make_user('player'))
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)
    _invoke(runner, 'sync', '--mode', 'deadline')

    _invoke(runner, 'recalc', '1')
    first = [(r.user_id, r.points, r.wins, r.error_tenths, r.is_dropped)
             for r in db.session.scalars(select(DocketWeekResult))]
    _invoke(runner, 'recalc', '1')
    second = [(r.user_id, r.points, r.wins, r.error_tenths, r.is_dropped)
              for r in db.session.scalars(select(DocketWeekResult))]

    assert first == second
    assert all(not row[4] for row in second), \
        'is_dropped belongs to the season rollup, not the week pass'


def test_recalc_reports_a_week_that_is_not_ready_yet(app, runner,
                                                     monkeypatch):
    """No deadline pass has run, so nothing is frozen — that is a wait, not
    a crash."""
    _seed()
    make_enrollment(make_user('player'))
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    result = _invoke(runner, 'recalc', '1')

    assert result.exit_code == 0
    assert 'not ready' in result.output
    assert 'kickoff_at_deadline' in result.output


def test_recalc_with_no_argument_covers_every_past_deadline_week(app, runner,
                                                                 monkeypatch):
    _seed()
    make_enrollment(make_user('player'))
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)
    _invoke(runner, 'sync', '--mode', 'deadline')

    result = _invoke(runner, 'recalc')

    assert result.exit_code == 0
    assert 'week 1: 1 players graded' in result.output


def test_scores_mode_writes_then_grades_when_the_week_is_complete(
        app, runner, monkeypatch):
    week, games = _seed(final=False)
    make_enrollment(make_user('player'))
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)
    _invoke(runner, 'sync', '--mode', 'deadline')
    app.config['ODDS_API_KEY'] = 'test-key'

    events = [{'id': g.api_event_id, 'home_team': g.home_team,
               'away_team': g.away_team, 'completed': True,
               'scores': [{'name': g.home_team, 'score': '31'},
                          {'name': g.away_team, 'score': '17'}]}
              for g in games]

    class _R:
        status_code = 200
        headers = {}  # noqa: RUF012 - throwaway stub

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    with patch('games.docket.services.scores.odds_api_get',
               side_effect=[_R(events), _R([])]):
        result = _invoke(runner, 'sync', '--mode', 'scores')

    assert result.exit_code == 0, result.output
    assert 'finalized: 9' in result.output
    assert '1 players graded' in result.output
    assert db.session.scalars(
        select(DocketWeekResult).filter_by(week_id=week.id)).all()


def test_a_partial_sync_exits_non_zero(app, runner, monkeypatch):
    """One sport dark for a week must not read as a green timer run — the
    healthy sport's work still lands, and the command still fails."""
    week, games = _seed(final=False)
    make_enrollment(make_user('player'))
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)
    _invoke(runner, 'sync', '--mode', 'deadline')
    app.config['ODDS_API_KEY'] = 'test-key'

    class _R:
        headers = {}  # noqa: RUF012 - throwaway stub

        def __init__(self, payload, status=200):
            self._payload = payload
            self.status_code = status

        def json(self):
            return self._payload

    ok = [{'id': games[0].api_event_id, 'home_team': games[0].home_team,
           'away_team': games[0].away_team, 'completed': True,
           'scores': [{'name': games[0].home_team, 'score': '31'},
                      {'name': games[0].away_team, 'score': '17'}]}]
    # NCAAF 500s after retries; NFL succeeds. (SPORTS order is ncaaf, nfl.)
    with patch('games.docket.services.scores.odds_api_get',
               side_effect=[_R([], 500), _R(ok)]):
        result = _invoke(runner, 'sync', '--mode', 'scores')

    assert result.exit_code == 1
    assert 'partially failed' in result.output
    assert games[0].is_final is True, \
        'the sport that succeeded keeps its update'


def test_set_tiebreaker_designates_and_validates(app, runner, monkeypatch):
    week, games = _seed(designate=False)
    at(monkeypatch, BEFORE_DEADLINE)  # designation is pre-deadline only

    result = _invoke(runner, 'set-tiebreaker', '1', 'Away 3 @ Home 3')

    assert result.exit_code == 0, result.output
    assert week.tiebreaker_game_id == games[3].id


def test_set_tiebreaker_refuses_an_unsound_designation(app, runner,
                                                       monkeypatch):
    """A designated game with no locked total cannot supply key 3's default
    prediction — the command says so instead of leaving it to Saturday."""
    week, games = _seed(designate=False)
    games[3].total_points = None
    db.session.commit()
    at(monkeypatch, BEFORE_DEADLINE)

    result = _invoke(runner, 'set-tiebreaker', '1', 'Away 3 @ Home 3')

    assert result.exit_code == 1
    assert 'no locked total' in result.output
    assert week.tiebreaker_game_id is None, \
        'an unsound designation rolls back rather than sticking'


def test_status_summarizes_the_season(app, runner, monkeypatch):
    _seed()
    make_enrollment(make_user('player'))
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    result = _invoke(runner, 'sync', '--mode', 'status')

    assert result.exit_code == 0, result.output
    assert 'enrolled players: 1' in result.output
    assert 'week  1:   9 games' in result.output
    assert 'tiebreaker: Away 0 @ Home 0' in result.output
