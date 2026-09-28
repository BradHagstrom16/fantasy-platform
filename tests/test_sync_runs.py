"""Every scheduled job records its runs in sync_runs (open-items §H).

utils/sync_runs.record_run wraps each scheduled CLI command; the admin
dashboard reads the rows (core/admin/health.py). The lock at the bottom
invokes every scheduled unit's real ExecStart and proves it records under
the unit's own name before doing any work, so a new timer whose command
does not record fails here.
"""
import shlex
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import select

from extensions import db
from models.sync_run import SyncRun
from utils import odds_api, sync_runs
from utils.sync_runs import JOBS, mark_run, record_run

DEPLOY = Path(__file__).resolve().parent.parent / 'deploy'
# Same selection as tests/test_job_alerts.py: the World Cup is off for good.
SCHEDULED = sorted(
    timer.with_suffix('.service') for timer in DEPLOY.glob('*.timer')
    if not timer.name.startswith('worldcup-'))


def _runs():
    db.session.expire_all()
    return db.session.scalars(select(SyncRun).order_by(SyncRun.id)).all()


def _only_run():
    runs = _runs()
    assert len(runs) == 1, runs
    return runs[0]


@pytest.fixture(autouse=True)
def _typed_at_a_shell(monkeypatch):
    monkeypatch.delenv('INVOCATION_ID', raising=False)


# ---- the recorder ------------------------------------------------------------

def test_a_clean_run_records_ok(app):
    with record_run('cfb-scores'):
        pass
    run = _only_run()
    assert (run.job, run.outcome, run.exit_code, run.via) == (
        'cfb-scores', 'ok', 0, 'shell')
    assert run.finished_at is not None


def test_the_command_says_how_it_went(app):
    with record_run('docket-lines'):
        mark_run('stood_down', 'no docket week 5 yet\nsecond line')
    run = _only_run()
    assert (run.outcome, run.summary, run.exit_code) == (
        'stood_down', 'no docket week 5 yet', 0)


def test_the_row_is_running_while_the_job_runs(app):
    with record_run('club-remind'):
        assert _only_run().outcome == 'running'
        assert _only_run().finished_at is None


def test_an_exception_is_an_error_and_still_raises(app):
    with pytest.raises(RuntimeError), record_run('cfb-setup'):
        raise RuntimeError('odds feed down')
    run = _only_run()
    assert (run.outcome, run.exit_code, run.summary) == (
        'error', 1, 'RuntimeError: odds feed down')


def test_a_nonzero_exit_is_an_error_whatever_was_marked(app):
    with pytest.raises(SystemExit), record_run('club-paper'):
        mark_run('ok', 'opened docket week 4')
        raise SystemExit(1)
    run = _only_run()
    assert (run.outcome, run.exit_code) == ('error', 1)


def test_a_zero_exit_keeps_the_marked_outcome(app):
    with pytest.raises(SystemExit), record_run('docket-scores'):
        mark_run('stood_down', 'out of season')
        raise SystemExit(0)
    run = _only_run()
    assert (run.outcome, run.exit_code) == ('stood_down', 0)


def test_the_jobs_rollback_never_takes_the_row(app):
    from models.user import User
    with record_run('cfb-autopick'):
        db.session.add(User(username='ghost', email='ghost@example.com',
                            password_hash='x'))
        db.session.flush()
        db.session.rollback()
    assert _only_run().outcome == 'ok'


def test_systemd_runs_say_so(app, monkeypatch):
    monkeypatch.setenv('INVOCATION_ID', 'abc123')
    with record_run('scores-gameday'):
        pass
    assert _only_run().via == 'systemd'


def test_none_records_nothing_and_mark_is_a_noop(app):
    with record_run(None) as run:
        mark_run('error', 'ignored')
    assert run is None
    assert _runs() == []


def test_a_broken_table_never_fails_the_job(app):
    SyncRun.__table__.drop(db.engine)
    ran = []
    with record_run('cfb-scores'):
        ran.append(True)
    assert ran == [True]


# ---- the credit balance ------------------------------------------------------

def _resp(remaining):
    return SimpleNamespace(headers={'x-requests-remaining': remaining,
                                    'x-requests-used': '1'})


def test_the_run_keeps_the_lowest_balance_it_saw(app):
    with record_run('docket-scores'):
        odds_api._log_credits(_resp('412'), 'u')
        odds_api._log_credits(_resp('410'), 'u')
        odds_api._log_credits(_resp('unknown'), 'u')
    assert _only_run().odds_credits_remaining == 410


def test_a_call_outside_a_run_records_nothing(app):
    odds_api._log_credits(_resp('400'), 'u')
    with record_run('cfb-autopick'):
        pass
    assert _only_run().odds_credits_remaining is None


# ---- each CLI's outcome ------------------------------------------------------

def _cli(app, *args):
    return app.test_cli_runner().invoke(args=list(args))


def test_cfb_skipped_is_idle_and_error_is_recorded_though_exit_0(app):
    with patch('games.cfb.services.automation.run_scores', return_value={
            'status': 'skipped', 'details': 'No incomplete weeks past deadline'}):
        assert _cli(app, 'cfb', 'sync', '--mode', 'scores').exit_code == 0
    with patch('games.cfb.services.automation.run_setup', return_value={
            'status': 'error', 'details': 'Odds API unreachable'}):
        assert _cli(app, 'cfb', 'sync', '--mode', 'setup').exit_code == 0
    scores, setup = _runs()
    assert (scores.job, scores.outcome, scores.summary) == (
        'cfb-scores', 'idle', 'No incomplete weeks past deadline')
    assert (setup.job, setup.outcome, setup.exit_code) == (
        'cfb-setup', 'error', 0)


def test_cfb_status_records_nothing(app):
    with patch('games.cfb.services.automation.run_status',
               return_value={'status': 'ok', 'details': 'season'}):
        _cli(app, 'cfb', 'sync', '--mode', 'status')
    assert _runs() == []


def test_docket_scheduled_with_no_week_stands_down(app):
    result = _cli(app, 'docket', 'sync', '--mode', 'scores', '--scheduled')
    assert result.exit_code == 0, result.output
    run = _only_run()
    assert (run.job, run.outcome) == ('docket-scores', 'stood_down')


def test_docket_by_hand_with_no_week_is_an_error(app):
    result = _cli(app, 'docket', 'sync', '--mode', 'lines')
    assert result.exit_code == 1
    run = _only_run()
    assert (run.job, run.outcome, run.exit_code) == ('docket-lines', 'error', 1)
    assert run.summary


def test_gameday_floor_stands_down(app):
    summary = {'status': 'floor', 'wanted': ['cfb'], 'fetched': [],
               'remaining': 50, 'applied': {}, 'errors': []}
    with patch('games.gameday.run_game_day', return_value=summary):
        assert _cli(app, 'scores', 'game-day', '--scheduled').exit_code == 0
    run = _only_run()
    assert (run.job, run.outcome, run.summary) == (
        'scores-gameday', 'stood_down', 'credit floor: 50 left')


def test_club_dry_runs_record_nothing(app):
    _cli(app, 'club', 'desk', '--dry-run')
    _cli(app, 'club', 'paper', '--dry-run')
    assert _runs() == []


def test_club_desk_out_of_season_stands_down(app):
    result = _cli(app, 'club', 'desk', '--scheduled', '--anchor', 'cfb,docket')
    assert result.exit_code == 0, result.output
    run = _only_run()
    assert (run.job, run.outcome) == ('club-remind', 'stood_down')


def test_golf_remind_records_under_its_unit(app):
    with patch('games.golf.services.reminders.run_reminder_check'):
        _cli(app, 'golf', 'sync-run', '--mode', 'remind')
    run = _only_run()
    assert (run.job, run.outcome) == ('golf-remind', 'ok')


# ---- the lock: every scheduled unit records under its own name ---------------

class _Recorded(BaseException):
    """Raised in place of the first insert: stops the command before it does
    any work. BaseException, so neither the recorder nor click swallows it."""


def _flask_args(service):
    (line,) = [ln.strip() for ln in service.read_text().splitlines()
               if ln.strip().startswith('ExecStart=')]
    argv = shlex.split(line.split('=', 1)[1])
    return argv[next(i for i, a in enumerate(argv) if a.endswith('/flask')) + 1:]


def _raise_recorded(job, started_at):
    raise _Recorded(job)


@pytest.mark.parametrize('service', SCHEDULED, ids=lambda p: p.stem)
def test_every_scheduled_unit_records_under_its_own_name(app, service):
    with patch.object(sync_runs, '_insert', _raise_recorded), \
            pytest.raises(_Recorded) as recorded:
        app.test_cli_runner().invoke(args=_flask_args(service),
                                     catch_exceptions=False)
    assert recorded.value.args[0] == service.stem


def test_jobs_names_exactly_the_scheduled_units():
    # docket-setup lost its unit at ADR-065 step 9; a hand run still records.
    assert set(JOBS) - {'docket-setup'} == {p.stem for p in SCHEDULED}
