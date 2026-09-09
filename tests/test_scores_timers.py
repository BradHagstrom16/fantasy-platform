"""The shared game-day scores units (deploy/scores-gameday.*, ADR-063).

Same rationale as tests/test_docket_timers.py: `systemd-analyze verify` on
the droplet checks syntax, not whether the ExecStart names a real command or
the timer fires at hours the pass can use. Those are repo-side facts.
"""
import re
from pathlib import Path

DEPLOY = Path(__file__).parent.parent / 'deploy'
TIMER = DEPLOY / 'scores-gameday.timer'
SERVICE = DEPLOY / 'scores-gameday.service'
PRESET = DEPLOY / '10-fantasy-platform.preset'

_ONCALENDAR = re.compile(r'^OnCalendar=(.+)$', re.MULTILINE)
_EXECSTART = re.compile(r'^ExecStart=(.+)$', re.MULTILINE)

# Validated with `systemd-analyze calendar` on the droplet 2026-09-09.
EXPECTED_RULES = [
    '*-01..11-* 13..23:30:00 America/Chicago',
    '*-01..11-* 00:30:00 America/Chicago',
    '*-12-* 13..23/2:30:00 America/Chicago',
    '*-12-* 00:30:00 America/Chicago',
]


def _directives(path):
    return [line for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def test_unit_pair_exists():
    assert TIMER.is_file() and SERVICE.is_file()


def test_service_runs_the_game_day_pass_in_scheduled_form():
    exec_starts = _EXECSTART.findall(SERVICE.read_text())
    assert len(exec_starts) == 1
    command = exec_starts[0]
    assert command.endswith('flask scores game-day --scheduled'), command
    assert re.search(r'(?<!\S)--scheduled(?!\S)', command)


def test_service_pins_the_production_environment():
    directives = _directives(SERVICE)
    assert 'Environment=ENVIRONMENT=production' in directives
    assert 'Environment=FLASK_APP=app.py' in directives
    assert 'Type=oneshot' in directives


def test_timer_rules_are_exactly_the_validated_set():
    """Hourly at :30 through game hours plus 00:30 for late West Coast
    finals; December every two hours (bowls most days). The :30 offset keeps
    the pass off the :00 reminder ticks and the 08:00 daily passes."""
    rules = [r.strip() for r in _ONCALENDAR.findall(TIMER.read_text())]
    assert rules == EXPECTED_RULES


def test_timer_is_not_persistent():
    """A missed hourly tick's catch-up is worthless (the next tick is under
    an hour away) and a boot replay must not spend credits for nothing —
    the one deliberate departure from the docket set."""
    assert 'Persistent=false' in _directives(TIMER)


def test_timer_is_enableable():
    directives = _directives(TIMER)
    assert '[Install]' in directives
    assert 'WantedBy=timers.target' in directives


def test_preset_ignores_the_scores_prefix():
    rules = [tuple(line.split()) for line in _directives(PRESET)]
    assert ('ignore', 'scores-*.timer') in rules
