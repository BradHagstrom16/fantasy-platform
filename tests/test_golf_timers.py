"""Golf Pick 'Em's systemd units (deploy/golf-*).

Same rationale as tests/test_cfb_timers.py: `systemd-analyze verify` on the
droplet checks syntax, not whether an ExecStart names a real mode or a timer
fires at an hour the game can use. Those are repo-side facts, asserted here.

Golf runs SlashGolf on the FREE RapidAPI tier (250 calls/month). Nothing in
`flask golf sync-run` enforces that budget (`free_tier_blocked` is empty), so
the timer cadence IS the budget gate. The cadence locked below mirrors what the
retired PythonAnywhere app actually ran for the 2026 season — three live reads
a day during play (noon / 4 PM / 8 PM CT, the last one with the withdrawal
check) — about 115 calls a month. The original 30-minute live timer (~600
calls/month) would have blown the budget in week two.
"""
import re
from pathlib import Path

import pytest

DEPLOY = Path(__file__).parent.parent / 'deploy'

# Deliberately spelled out rather than globbed: a unit pair that goes missing
# in a rename should fail this file, not quietly shrink the covered set.
EXPECTED_UNITS = ('schedule', 'field', 'live', 'live-wd', 'results', 'remind')

# Modes `flask golf sync-run --mode` accepts (games/golf/cli.py defines the
# Choice inline, so the list is mirrored here). 'all' has no unit on purpose —
# it is refused under ENVIRONMENT=production.
CLI_MODES = ('schedule', 'field', 'live', 'live-with-wd', 'withdrawals',
             'results', 'earnings', 'remind', 'all')

TIMERS = [DEPLOY / f'golf-{unit}.timer' for unit in EXPECTED_UNITS]
SERVICES = [DEPLOY / f'golf-{unit}.service' for unit in EXPECTED_UNITS]

_ONCALENDAR = re.compile(r'^OnCalendar=(.+)$', re.MULTILINE)
_EXECSTART = re.compile(r'^ExecStart=(.+)$', re.MULTILINE)


def _directives(path):
    """Non-comment, non-blank lines — the part systemd actually reads."""
    return [line for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def _rules(name):
    return _ONCALENDAR.findall((DEPLOY / name).read_text())


def _mode(service):
    exec_starts = _EXECSTART.findall(service.read_text())
    assert len(exec_starts) == 1, f'{service.name} needs exactly one ExecStart'
    command = exec_starts[0]
    assert 'flask golf sync-run --mode ' in command
    return command.split('--mode ')[1].split()[0]


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
    mode = _mode(service)
    assert mode in CLI_MODES, f'{service.name} runs unknown mode {mode!r}'
    assert mode != 'all', 'sync-run --mode all is dev-only and refused in prod'


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
    inline in OnCalendar. Omitting it silently schedules in UTC — which is
    exactly the DST drift the PythonAnywhere task list suffered from."""
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


# ── The free-tier cadence (the API budget gate) ───────────────────────────

def test_schedule_syncs_monday_morning_only():
    """The schedule/purse sync is Monday-gated in cli.py; one 07:00 CT firing
    is all it needs. Pinned exactly so an added firing (another API call)
    fails here."""
    assert _rules('golf-schedule.timer') == ['Mon *-*-* 07:00:00 America/Chicago']


def test_live_reads_twice_a_day_during_play():
    """Noon + 4 PM CT, Thu–Sun. Each firing is one leaderboard call for the
    active tournament (off-week firings make no call)."""
    assert _rules('golf-live.timer') == ['Thu..Sun *-*-* 12,16:00:00 America/Chicago']
    assert _mode(DEPLOY / 'golf-live.service') == 'live'


def test_live_wd_is_the_8pm_read_with_the_withdrawal_check():
    """The third daily read is the one users know as "leaderboard updates at
    8 PM Central", and it carries the withdrawal check — Friday's run is the
    one that catches a pre-Round-2 WD and activates the backup."""
    assert _rules('golf-live-wd.timer') == ['Thu..Sun *-*-* 20:00:00 America/Chicago']
    assert _mode(DEPLOY / 'golf-live-wd.service') == 'live-with-wd'


def test_results_land_sunday_night_after_the_last_live_read():
    """The Sunday recap email rides the results run, so it fires after the
    20:00 live read; the two Monday firings catch late official postings."""
    assert _rules('golf-results.timer') == [
        'Sun *-*-* 20:30:00 America/Chicago',
        'Mon *-*-* 08:00:00 America/Chicago',
        'Mon *-*-* 18:00:00 America/Chicago',
    ]


def test_field_syncs_tuesday_and_wednesday_only():
    """Field syncs are the calls that fire "Picks Are Open"; keeping them to
    Tue/Wed (08:00 + 18:00 CT) matches both the free-tier gate in cli.py and
    the legacy cadence. Pinned exactly so a third firing or a weekday slip
    fails here, not just a non-Tue/Wed prefix."""
    assert _rules('golf-field.timer') == [
        'Tue,Wed *-*-* 08:00:00 America/Chicago',
        'Tue,Wed *-*-* 18:00:00 America/Chicago',
    ]


def test_field_timer_is_not_persistent():
    """A downtime replay of the field sync could fire "Picks Are Open" after
    the deadline — deliberately unlike every other golf timer (PR #106)."""
    assert 'Persistent=false' in _directives(DEPLOY / 'golf-field.timer')


def test_remind_fires_hourly_with_no_weekday_restriction():
    """De-dup lives in GolfTournament.last_reminder_type, so hourly is what
    lets every 24h/12h/1h window land regardless of the deadline's weekday."""
    assert _rules('golf-remind.timer') == ['*-*-* *:00:00 America/Chicago']
    assert 'Persistent=true' in _directives(DEPLOY / 'golf-remind.timer')


def test_no_timer_polls_more_than_hourly():
    """A sub-hourly OnCalendar (the old `06..23:0/30:00`) is how the budget
    gets blown. Hourly is the finest cadence any golf timer may use."""
    for timer in TIMERS:
        for rule in _ONCALENDAR.findall(timer.read_text()):
            assert '/' not in rule.split(' ')[-2], (
                f'{timer.name}: {rule!r} repeats inside the hour')
