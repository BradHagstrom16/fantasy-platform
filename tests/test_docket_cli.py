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


@pytest.mark.parametrize('mode',
                         ['setup', 'lines', 'scores', 'deadline', 'remind'])
def test_scheduled_stands_down_out_of_season(app, runner, monkeypatch, mode):
    """The docket season covers 19 of 52 weeks. A timer firing in the other
    33 has nothing to do, and must say so with exit 0 — otherwise a red
    docket timer is the normal state and stops carrying information."""
    monkeypatch.setenv('DOCKET_FAKE_NOW', '2026-06-01T12:00:00')
    result = _invoke(runner, 'sync', '--mode', mode, '--scheduled')
    assert result.exit_code == 0, result.output
    assert 'Standing down' in result.output


@pytest.mark.parametrize('mode', ['lines', 'scores', 'deadline', 'remind'])
def test_scheduled_stands_down_before_the_week_is_imported(app, runner,
                                                           monkeypatch, mode):
    """Production docket tables stay empty until the deliberate Week-1
    import at the line freeze, so every timer enabled before then fires
    against nothing."""
    monkeypatch.setenv('DOCKET_FAKE_NOW', BEFORE_DEADLINE)
    result = _invoke(runner, 'sync', '--mode', mode, '--scheduled')
    assert result.exit_code == 0, result.output
    assert 'Standing down' in result.output


def test_scheduled_does_not_soften_a_real_failure(app, runner, monkeypatch):
    """--scheduled reclassifies exactly two benign states. A week that
    reached its deadline with no sound designation is not one of them: that
    is the alert the Saturday timer exists to raise."""
    _seed(designate=False)
    make_enrollment(make_user('player'))
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)

    result = _invoke(runner, 'sync', '--mode', 'deadline', '--scheduled')

    assert result.exit_code == 1
    assert 'AUTOPICK WAS SKIPPED' in result.output


def test_scheduled_does_not_soften_a_bad_week_number(app, runner, monkeypatch):
    """An out-of-range --week is a typo, not a benign state."""
    monkeypatch.setenv('DOCKET_FAKE_NOW', BEFORE_DEADLINE)
    result = _invoke(runner, 'sync', '--mode', 'lines', '--week', '99',
                     '--scheduled')
    assert result.exit_code == 1
    assert 'week must be 1-' in result.output


def test_remind_mode_mails_an_unfinished_sheet(app, runner, monkeypatch):
    _seed(final=False)
    make_enrollment(make_user('player'))
    db.session.commit()
    # Thursday morning, inside the 48h tier before the Sat 11:00 CT close.
    monkeypatch.setenv('DOCKET_FAKE_NOW', '2026-09-03T16:00:00')

    with patch('games.docket.services.notifications.send_platform_email',
               return_value=True) as send:
        result = _invoke(runner, 'sync', '--mode', 'remind')

    assert result.exit_code == 0, result.output
    assert '48h sent to 1/1' in result.output
    assert send.call_count == 1


def test_remind_mode_is_quiet_outside_a_tier(app, runner, monkeypatch):
    """Hourly firings mostly land between tiers. That is not a failure."""
    _seed(final=False)
    make_enrollment(make_user('player'))
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', '2026-09-04T04:00:00')

    with patch('games.docket.services.notifications.send_platform_email',
               return_value=True) as send:
        result = _invoke(runner, 'sync', '--mode', 'remind')

    assert result.exit_code == 0, result.output
    assert 'no tier is due' in result.output
    assert send.call_count == 0


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


def test_recalc_does_not_back_grade_a_late_joiner(app, runner, monkeypatch):
    """A full recalc grades each week against the roster AS OF ITS DEADLINE.

    Grading a closed week against the LIVE roster hands a later joiner an
    empty input, which the engine completes into a full 8-slot autopick
    package worth real points. That would make a player's season total depend
    on whether an operator ever typed `flask docket recalc`.
    """
    week, _games = _seed()
    early = make_user('early')
    make_enrollment(early, created_at=datetime.fromisoformat(BEFORE_DEADLINE))
    late = make_user('late')
    make_enrollment(late,
                    created_at=datetime(2026, 9, 20, 12, 0))
    db.session.commit()
    monkeypatch.setenv('DOCKET_FAKE_NOW', AFTER_DEADLINE)
    _invoke(runner, 'sync', '--mode', 'deadline')

    _invoke(runner, 'recalc')

    graded = {r.user_id: r for r in db.session.scalars(
        select(DocketWeekResult).filter_by(week_id=week.id))}
    assert early.id in graded, 'a member enrolled before the deadline grades'
    assert graded[early.id].points > 0, 'the autopick package scored'
    assert late.id not in graded, (
        'a member who joined after the deadline must not be back-graded into '
        'a week they never played')


def test_roster_as_of_counts_a_null_created_at_as_enrolled(app):
    """A NULL created_at cannot prove a late join, and wrongly excluding a
    real member from a graded week is the worse error."""
    from games.docket.services.enrollment import roster_user_ids_as_of

    unknown = make_user('unknown')
    make_enrollment(unknown, created_at=None)
    db.session.commit()

    assert unknown.id in roster_user_ids_as_of(
        datetime.fromisoformat(BEFORE_DEADLINE))
