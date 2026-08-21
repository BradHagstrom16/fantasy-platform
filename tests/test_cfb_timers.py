"""CFB Survivor's systemd units (deploy/cfb-*).

Same rationale as tests/test_docket_timers.py: `systemd-analyze verify` on the
droplet checks syntax, not whether an ExecStart names a real mode or a timer
fires at an hour the game can use. Those are repo-side facts, asserted here.

The remind pair gets its own locks: its correctness contract changed from
"fire only inside the two windows" (cadence-dependent, the pre-sent-flag
shape) to "fire hourly, de-dup via CfbWeek.last_reminder_type". A weekday
restriction reappearing on cfb-remind.timer would silently zero out reminders
for any non-Saturday deadline (manually scheduled CFP weeks).
"""
import re
from pathlib import Path

import pytest

DEPLOY = Path(__file__).parent.parent / 'deploy'

# Deliberately spelled out rather than globbed: a unit pair that goes missing
# in a rename should fail this file, not quietly shrink the covered set.
EXPECTED_MODES = ('setup', 'spreads', 'scores', 'autopick', 'remind')

# Modes `flask cfb sync --mode` accepts (games/cfb/cli.py defines the Choice
# inline, so the list is mirrored here; 'status' has no unit on purpose).
CLI_MODES = ('setup', 'spreads', 'scores', 'autopick', 'remind', 'status')

TIMERS = [DEPLOY / f'cfb-{mode}.timer' for mode in EXPECTED_MODES]
SERVICES = [DEPLOY / f'cfb-{mode}.service' for mode in EXPECTED_MODES]

_ONCALENDAR = re.compile(r'^OnCalendar=(.+)$', re.MULTILINE)
_EXECSTART = re.compile(r'^ExecStart=(.+)$', re.MULTILINE)


def _directives(path):
    """Non-comment, non-blank lines — the part systemd actually reads."""
    return [line for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


@pytest.mark.parametrize('path', TIMERS + SERVICES, ids=lambda p: p.name)
def test_unit_exists(path):
    assert path.is_file(), f'{path.name} is missing from deploy/'


@pytest.mark.parametrize('timer', TIMERS, ids=lambda p: p.name)
def test_every_timer_has_its_service(timer):
    """A timer whose .service is absent installs fine and then fails at its
    first firing."""
    assert timer.with_suffix('.service').is_file()


@pytest.mark.parametrize('service', SERVICES, ids=lambda p: p.name)
def test_service_runs_a_real_mode(service):
    exec_starts = _EXECSTART.findall(service.read_text())
    assert len(exec_starts) == 1, f'{service.name} needs exactly one ExecStart'
    command = exec_starts[0]
    assert 'flask cfb sync --mode ' in command
    mode = command.split('--mode ')[1].split()[0]
    assert mode in CLI_MODES, f'{service.name} runs unknown mode {mode!r}'


@pytest.mark.parametrize('service', SERVICES, ids=lambda p: p.name)
def test_service_pins_the_production_environment(service):
    """ENVIRONMENT=production is set in three places as defense in depth
    (CLAUDE.md); the unit's Environment= is the one that lives in this repo."""
    directives = _directives(service)
    assert 'Environment=ENVIRONMENT=production' in directives
    assert 'Environment=FLASK_APP=app.py' in directives


@pytest.mark.parametrize('timer', TIMERS, ids=lambda p: p.name)
def test_oncalendar_carries_an_inline_timezone(timer):
    """There is no TimeZone= directive for timer units, so the zone has to be
    inline in OnCalendar. Omitting it silently schedules in UTC."""
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


# ── cfb-remind: hourly + de-duped, never cadence-dependent again ──────────

def test_remind_fires_hourly_with_no_weekday_restriction():
    """The de-dup guarantee lives in CfbWeek.last_reminder_type, so the
    cadence only has to land inside every window's ±35-minute tolerance at
    least once — hourly does, for ANY deadline time. A weekday-restricted
    rule (the old `Fri,Sat 10:00`) silently sends ZERO reminders for a week
    whose deadline isn't Saturday ~11:00 CT, e.g. a hand-scheduled CFP week."""
    rules = _ONCALENDAR.findall((DEPLOY / 'cfb-remind.timer').read_text())
    assert rules == ['*-*-* *:00:00 America/Chicago'], (
        f'cfb-remind.timer must fire hourly every day, got {rules!r}')


def test_remind_is_persistent():
    """Persistent=true is what turns droplet downtime inside a window into a
    caught-up send instead of a missed reminder; the sent-flag makes the
    catch-up safe to double-fire."""
    assert 'Persistent=true' in _directives(DEPLOY / 'cfb-remind.timer')
