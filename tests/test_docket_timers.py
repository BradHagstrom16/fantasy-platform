"""The Docket's systemd units (deploy/docket-*).

Unit files are shipped config that no other test touches: `deploy.sh` runs
`systemd-analyze verify` on the droplet before installing them, but that
checks systemd syntax, not whether the ExecStart names a real mode or whether
a timer fires at an hour this game can actually use. Those are repo-side
facts, so they are asserted here — the tests/test_client_ip_keying.py pattern
of locking a deploy/ file from the suite.
"""
import re
from pathlib import Path

import pytest

from games.docket.cli import SYNC_MODES

DEPLOY = Path(__file__).parent.parent / 'deploy'

# Every mode the units are expected to run. Deliberately spelled out rather
# than globbed from the directory: a unit pair that goes missing in a rename
# should fail this file, not quietly shrink the covered set.
EXPECTED_MODES = ('setup', 'lines', 'deadline', 'scores', 'remind')

TIMERS = [DEPLOY / f'docket-{mode}.timer' for mode in EXPECTED_MODES]
SERVICES = [DEPLOY / f'docket-{mode}.service' for mode in EXPECTED_MODES]

_ONCALENDAR = re.compile(r'^OnCalendar=(.+)$', re.MULTILINE)
_EXECSTART = re.compile(r'^ExecStart=(.+)$', re.MULTILINE)


def _directives(path):
    """Non-comment, non-blank lines — the part systemd actually reads."""
    return [line for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


@pytest.mark.parametrize('path', TIMERS + SERVICES,
                         ids=lambda p: p.name)
def test_unit_exists(path):
    assert path.is_file(), f'{path.name} is missing from deploy/'


@pytest.mark.parametrize('timer', TIMERS, ids=lambda p: p.name)
def test_every_timer_has_its_service(timer):
    """A timer whose .service is absent installs fine and then fails at its
    first firing."""
    assert timer.with_suffix('.service').is_file()


@pytest.mark.parametrize('service', SERVICES, ids=lambda p: p.name)
def test_service_runs_a_real_mode_in_scheduled_form(service):
    """ExecStart must name a mode the CLI accepts AND pass --scheduled.

    Without the flag the two benign states (out of season, week not imported)
    exit 1, so four of these five units would report failure on every firing
    for most of the year and a red docket timer would stop meaning anything.
    """
    exec_starts = _EXECSTART.findall(service.read_text())
    assert len(exec_starts) == 1, f'{service.name} needs exactly one ExecStart'
    command = exec_starts[0]
    assert 'flask docket sync --mode ' in command
    mode = command.split('--mode ')[1].split()[0]
    assert mode in SYNC_MODES, f'{service.name} runs unknown mode {mode!r}'
    assert '--scheduled' in command, (
        f'{service.name} must pass --scheduled: a timer that exits 1 for '
        f'"nothing to do yet" trains the operator to ignore it')


@pytest.mark.parametrize('service', SERVICES, ids=lambda p: p.name)
def test_service_pins_the_production_environment(service):
    """ENVIRONMENT=production is set in three places as defense in depth
    (CLAUDE.md); the unit's Environment= is the one that lives in this repo.
    Without it, migrations/env.py resolves the SQLite dev engine."""
    directives = _directives(service)
    assert 'Environment=ENVIRONMENT=production' in directives
    assert 'Environment=FLASK_APP=app.py' in directives


@pytest.mark.parametrize('timer', TIMERS, ids=lambda p: p.name)
def test_oncalendar_carries_an_inline_timezone(timer):
    """There is no TimeZone= directive for timer units, so the zone has to be
    inline in OnCalendar. Omitting it silently schedules in UTC, which in CT
    is five or six hours wrong depending on the season."""
    rules = _ONCALENDAR.findall(timer.read_text())
    assert rules, f'{timer.name} defines no OnCalendar'
    for rule in rules:
        assert rule.strip().endswith('America/Chicago'), (
            f'{timer.name}: {rule!r} has no inline timezone')


@pytest.mark.parametrize('timer', TIMERS, ids=lambda p: p.name)
def test_timer_is_enableable(timer):
    """A timer with no [Install] section cannot be enabled — `systemctl
    enable` reports success and schedules nothing."""
    directives = _directives(timer)
    assert '[Install]' in directives
    assert 'WantedBy=timers.target' in directives


def test_deadline_never_fires_at_the_deadline_instant():
    """run_deadline_pass refuses while now < deadline_at, so a firing at
    Saturday 11:00:00 races its own precondition. Running late is free (the
    freeze is only-if-null and the autopick pool is deadline-relative), so
    the fix is to fire after the hour, never on it."""
    rules = _ONCALENDAR.findall((DEPLOY / 'docket-deadline.timer').read_text())
    assert rules, 'the deadline pass has no schedule'
    for rule in rules:
        assert 'Sat ' in rule, f'the deadline pass must be Saturday: {rule!r}'
        clock = rule.split()[-2]
        assert clock > '11:00:00', (
            f'{rule!r} fires at or before the 11:00 CT deadline; '
            f'run_deadline_pass would refuse it')


def test_tuesday_scores_run_stays_before_the_week_boundary():
    """D12: the Tuesday scores run is pre-boundary on purpose. Docket weeks
    turn over at Tuesday 06:00 CT, and this mode resolves its week from the
    clock — after the boundary it would target the fresh week and leave the
    finished one ungraded."""
    rules = _ONCALENDAR.findall((DEPLOY / 'docket-scores.timer').read_text())
    tuesday = [rule for rule in rules if rule.startswith('Tue ')]
    assert tuesday, 'D12 requires a Tuesday scores run'
    for rule in tuesday:
        assert rule.split()[-2] < '06:00:00', (
            f'{rule!r} fires after the Tue 06:00 CT week boundary')


def test_december_window_ends_inside_the_docket_season():
    """CFB's daily window runs to Jan 25; the Docket's 19th week ends Tue
    Jan 12 2027, and the Tue 05:15 rule covers that last day. A January rule
    reaching past the season would fire into the out-of-season branch daily."""
    rules = _ONCALENDAR.findall((DEPLOY / 'docket-scores.timer').read_text())
    january = [rule for rule in rules if rule.startswith('*-01-')]
    assert january, 'the December window needs its January half'
    for rule in january:
        last_day = int(rule.split()[0].rsplit('..', 1)[1])
        assert last_day <= 12, (
            f'{rule!r} runs past the end of the docket season')
