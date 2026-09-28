"""Failed jobs email someone; every job checks in with a dead-man (ADR-067).

Before this, no deploy/*.service set OnFailure=, so a docket, game-day or club
unit that exited 1 told nobody. Every unit a timer fires now names the two
templates: job-alert@ (mail the admin inbox + ping healthchecks /fail) and
job-ping@ (ping healthchecks on success). The templates run utils/job_alert.py.

`systemd-analyze verify`, which deploy.sh gates every install on, does NOT
notice an OnFailure= naming a template that does not exist (checked on the
droplet 2026-09-28), so the name coupling is locked here.
"""
import subprocess
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import job_alert

DEPLOY = Path(__file__).resolve().parent.parent / 'deploy'
ALERT = DEPLOY / 'job-alert@.service'
PING = DEPLOY / 'job-ping@.service'

# The World Cup is archived and its timers are off for good (frozen surface).
SCHEDULED = sorted(
    timer.with_suffix('.service') for timer in DEPLOY.glob('*.timer')
    if not timer.name.startswith('worldcup-'))


def _directives(path):
    """Non-comment, non-blank lines: the part systemd reads."""
    return [line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def _section(path, name):
    lines, inside = [], False
    for line in _directives(path):
        if line.startswith('['):
            inside = line == f'[{name}]'
        elif inside:
            lines.append(line)
    return lines


# ---- the units -------------------------------------------------------------

def test_the_scheduled_set_is_what_we_think():
    names = {p.stem for p in SCHEDULED}
    assert {'club-remind', 'club-paper', 'docket-scores', 'cfb-scores',
            'scores-gameday'} <= names
    assert not any(n.startswith('worldcup-') for n in names)


@pytest.mark.parametrize('service', SCHEDULED, ids=lambda p: p.name)
def test_every_scheduled_job_alerts_on_failure_and_pings_on_success(service):
    unit = _section(service, 'Unit')
    assert 'OnFailure=job-alert@%N.service' in unit
    assert 'OnSuccess=job-ping@%N.service' in unit


def test_the_named_templates_exist():
    assert ALERT.is_file()
    assert PING.is_file()


@pytest.mark.parametrize('template', [ALERT, PING], ids=lambda p: p.name)
def test_a_template_never_triggers_another_alert(template):
    text = '\n'.join(_directives(template))
    assert 'OnFailure=' not in text
    assert 'OnSuccess=' not in text


@pytest.mark.parametrize('template, mode', [(ALERT, 'fail'), (PING, 'ok')],
                         ids=['alert', 'ping'])
def test_template_runs_the_right_mode_in_production(template, mode):
    service = _section(template, 'Service')
    assert 'Type=oneshot' in service
    assert 'User=deploy' in service
    assert 'Environment=ENVIRONMENT=production' in service
    assert 'EnvironmentFile=/home/deploy/fantasy-platform/.env' in service
    exec_starts = [d for d in service if d.startswith('ExecStart=')]
    assert exec_starts == [
        'ExecStart=/home/deploy/fantasy-platform/venv/bin/python '
        f'-m utils.job_alert {mode} %i']


def test_the_alert_can_read_the_journal():
    assert 'SupplementaryGroups=systemd-journal' in _section(ALERT, 'Service')


# ---- utils/job_alert.py ----------------------------------------------------

def _ok_response():
    resp = MagicMock(status=200)
    resp.__enter__.return_value = resp
    return resp


def test_blank_ping_key_makes_no_request():
    with patch('utils.job_alert.urllib.request.urlopen') as urlopen:
        assert job_alert.ping('', 'club-remind') is False
    urlopen.assert_not_called()


@pytest.mark.parametrize('fail, suffix', [(False, ''), (True, '/fail')])
def test_ping_url(fail, suffix):
    with patch('utils.job_alert.urllib.request.urlopen',
               return_value=_ok_response()) as urlopen:
        assert job_alert.ping('KEY', 'club-remind', fail=fail) is True
    url = urlopen.call_args.args[0]
    assert url == f'https://hc-ping.com/KEY/club-remind{suffix}?create=1'


def test_the_ping_that_creates_a_check_counts_as_delivered(caplog):
    """healthchecks.io answers 201 Created when ?create=1 makes a new check
    (seen on the droplet's first ping, 2026-09-28); no retry, no warning."""
    created = _ok_response()
    created.status = 201
    with patch('utils.job_alert.urllib.request.urlopen', return_value=created) as urlopen, \
            patch('utils.job_alert.time.sleep') as sleep:
        assert job_alert.ping('KEY', 'club-remind') is True
    assert urlopen.call_count == 1
    sleep.assert_not_called()
    assert 'failed' not in caplog.text


def test_a_ping_that_cannot_connect_retries_then_gives_up_quietly(caplog):
    with patch('utils.job_alert.urllib.request.urlopen',
               side_effect=urllib.error.URLError('down')) as urlopen, \
            patch('utils.job_alert.time.sleep') as sleep:
        assert job_alert.ping('SECRETKEY', 'club-remind') is False
    assert urlopen.call_count == 3
    assert [c.args[0] for c in sleep.call_args_list] == [2, 4]
    assert 'SECRETKEY' not in caplog.text


def test_a_transient_failure_is_recovered_by_a_retry():
    with patch('utils.job_alert.urllib.request.urlopen',
               side_effect=[urllib.error.URLError('blip'), _ok_response()]) as urlopen, \
            patch('utils.job_alert.time.sleep'):
        assert job_alert.ping('KEY', 'club-paper') is True
    assert urlopen.call_count == 2


def test_the_retries_fit_inside_the_ping_units_timeout():
    """Every attempt's 10 s timeout plus the pauses between them must finish
    before job-ping@'s 1-minute TimeoutStartSec kills the run."""
    import inspect
    params = inspect.signature(job_alert.ping).parameters
    attempts, backoff = params['attempts'].default, params['backoff'].default
    worst = attempts * 10 + sum(backoff * n for n in range(1, attempts))
    assert 'TimeoutStartSec=1m' in _section(PING, 'Service')
    assert worst < 60


def test_journal_tail_reads_the_units_last_lines():
    done = subprocess.CompletedProcess([], 0, stdout='line one\nline two\n', stderr='')
    with patch('utils.job_alert.subprocess.run', return_value=done) as run:
        assert job_alert.journal_tail('docket-scores') == 'line one\nline two'
    argv = run.call_args.args[0]
    assert argv[:3] == ['journalctl', '-u', 'docket-scores.service']


def test_journal_tail_explains_an_unreadable_journal():
    with patch('utils.job_alert.subprocess.run', side_effect=OSError('nope')):
        assert 'could not read the journal' in job_alert.journal_tail('x')


def test_failure_letter_names_the_unit_and_carries_the_journal():
    subject, body = job_alert.failure_letter('docket-scores', 'Traceback: boom')
    assert subject == '[CCC ops] docket-scores failed'
    assert 'Traceback: boom' in body
    assert 'sudo systemctl start docket-scores.service' in body


def _run(argv, *, admin='admin@example.com', key='KEY', sent=True):
    env = {'ENVIRONMENT': 'testing'}
    with patch.dict('os.environ', env), \
            patch.object(job_alert.config['testing'], 'ADMIN_EMAIL', admin), \
            patch.object(job_alert.config['testing'], 'EMAIL_ADDRESS', ''), \
            patch.object(job_alert.config['testing'], 'HEALTHCHECKS_PING_KEY', key), \
            patch('utils.job_alert.ping') as ping, \
            patch('utils.job_alert.journal_tail', return_value='the log'), \
            patch('utils.job_alert.send_platform_email', return_value=sent) as send:
        rc = job_alert.main(argv)
    return rc, ping, send


def test_fail_pings_then_mails_the_admin():
    rc, ping, send = _run(['job_alert', 'fail', 'club-remind'])
    assert rc == 0
    ping.assert_called_once_with('KEY', 'club-remind', fail=True)
    to_addr, subject, body = send.call_args.args
    assert to_addr == 'admin@example.com'
    assert subject == '[CCC ops] club-remind failed'
    assert 'the log' in body


def test_fail_exits_1_when_the_mail_did_not_go():
    rc, _, _ = _run(['job_alert', 'fail', 'club-remind'], sent=False)
    assert rc == 1


def test_fail_with_no_recipient_still_pings():
    rc, ping, send = _run(['job_alert', 'fail', 'club-remind'], admin='')
    assert rc == 1
    ping.assert_called_once()
    send.assert_not_called()


def test_ok_only_pings():
    rc, ping, send = _run(['job_alert', 'ok', 'club-remind'])
    assert rc == 0
    ping.assert_called_once_with('KEY', 'club-remind')
    send.assert_not_called()


@pytest.mark.parametrize('argv', [['job_alert'], ['job_alert', 'boom', 'x'],
                                  ['job_alert', 'ok']])
def test_bad_arguments_exit_2(argv):
    assert job_alert.main(argv) == 2


def test_the_alert_never_imports_the_app_or_a_game():
    """A deploy that breaks the app's import must still produce an alert."""
    code = ('import sys, utils.job_alert; '
            'bad = [m for m in sys.modules if m == "app" or m.startswith("games")]; '
            'print(bad)')
    out = subprocess.run(
        [sys.executable, '-c', code], capture_output=True, text=True,
        cwd=DEPLOY.parent, env={'ENVIRONMENT': 'testing', 'PATH': '/usr/bin:/bin'},
        check=True)
    assert out.stdout.strip() == '[]'
