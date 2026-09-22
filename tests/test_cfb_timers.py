"""CFB Survivor's systemd units (deploy/cfb-*).

Same rationale as tests/test_docket_timers.py: `systemd-analyze verify` on the
droplet checks syntax, not whether an ExecStart names a real mode or a timer
fires at an hour the game can use. Those are repo-side facts, asserted here.

Pick reminders are the Club Desk's since ADR-065 step 9 (deploy/club-remind.*,
tests/test_club_timers.py); the cfb-remind pair is gone, and a unit named
cfb-remind reappearing here would put two units on one sent flag.
"""
import re
from pathlib import Path

import pytest

DEPLOY = Path(__file__).parent.parent / 'deploy'

# Deliberately spelled out rather than globbed: a unit pair that goes missing
# in a rename should fail this file, not quietly shrink the covered set.
EXPECTED_MODES = ('setup', 'spreads', 'scores', 'autopick')

# The exact command each unit runs, after the venv's `flask`. Locked as
# values, not just a shape: a unit that quietly started running a different
# mode is a production change. (The reminder desk's --anchor/--ride rollout
# state is locked the same way on club-remind, tests/test_club_timers.py.)
EXPECTED_EXECSTART = {
    'setup': 'flask cfb sync --mode setup',
    'spreads': 'flask cfb sync --mode spreads',
    'scores': 'flask cfb sync --mode scores',
    'autopick': 'flask cfb sync --mode autopick',
}

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


@pytest.mark.parametrize('mode', EXPECTED_MODES)
def test_service_runs_the_expected_command(mode):
    """Exact match on the command after the venv's `flask`."""
    service = DEPLOY / f'cfb-{mode}.service'
    exec_starts = _EXECSTART.findall(service.read_text())
    assert len(exec_starts) == 1, f'{service.name} needs exactly one ExecStart'
    prefix = '/home/deploy/fantasy-platform/venv/bin/'
    assert exec_starts[0].startswith(prefix), exec_starts[0]
    assert exec_starts[0][len(prefix):] == EXPECTED_EXECSTART[mode]


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


# ── no cfb-remind pair: the reminder desk owns it (ADR-065 step 9) ───────

def test_no_cfb_remind_unit_reappears():
    """club-remind.timer sends every Survivor tier and there is no lock in
    code: a cfb-remind unit landing back in deploy/ would be installed by
    the next deploy and, if enabled, race the desk on last_reminder_type."""
    assert not (DEPLOY / 'cfb-remind.service').exists()
    assert not (DEPLOY / 'cfb-remind.timer').exists()


# ── cfb-spreads: Friday only since the Paper took Tuesday (ADR-065 step 5) ─

def test_spreads_timer_is_friday_only():
    """Tuesday's OPEN — the first fetch, which locks the lines (DQ-6) and
    announces the week — runs inside the Paper (deploy/club-paper.*, Tue
    06:15 CT), which calls this same opener. A Tuesday rule here would open
    and announce the week fifteen minutes before the Paper and turn its
    Survivor section into a no-op every week. Friday stays: the gap-fill
    that makes no odds call once every line is locked."""
    rules = [r.strip() for r in
             _ONCALENDAR.findall((DEPLOY / 'cfb-spreads.timer').read_text())]
    assert rules == ['Fri *-*-* 06:00:00 America/Chicago'], rules


# ── cfb-scores / cfb-setup: the Monday-game week (2026-09-07 incident) ───

def _weekday_rules(timer_name, clock):
    """Weekday-restricted OnCalendar rules firing at ``clock`` (HH:MM:SS)."""
    rules = _ONCALENDAR.findall((DEPLOY / timer_name).read_text())
    return [rule for rule in rules
            if rule.split()[-2] == clock and rule[0].isalpha()]


def test_scores_run_covers_every_day_cfb_plays():
    """/scores looks back at most daysFrom=3, and a CFB week runs Thu→Wed
    with its deadline on Saturday: Labor-Day Monday and November MACtion
    (Tue/Wed) games finish AFTER the old Sun/Mon cadence and BEFORE the next
    Sunday run could see them, so the week could never auto-complete (Week 1
    2026: SMU @ Florida State on Mon Sep 7 sat unscored). Sun through Thu at
    08:00 CT scores every post-deadline game inside the window; Fri/Sat runs
    would only see pre-deadline games, which the fetcher refuses anyway."""
    days = set()
    for rule in _weekday_rules('cfb-scores.timer', '08:00:00'):
        days.update(rule.split()[0].split(','))
    # Equality, not subset: every extra weekday is one more /scores call
    # (2 credits) that can only see pre-deadline games.
    assert days == {'Sun', 'Mon', 'Tue', 'Wed', 'Thu'}, days


def test_monday_setup_fires_after_the_scores_run():
    """Setup no longer flips is_active (ADR-062: a week opens on the spreads
    run that lands its first line), so this ordering is no longer
    load-bearing for the room. It stays: on a Monday the scores run grades
    the old week's last game before setup writes the next week, keeping the
    admin's two emails in causal order and the orphan-retry query
    (is_complete=False) reading a settled state — and moving OnCalendar on
    a Persistent timer fires a catch-up run at deploy (2026-09-07)."""
    scores = _weekday_rules('cfb-scores.timer', '08:00:00')
    assert any('Mon' in rule.split()[0].split(',') for rule in scores), (
        'cfb-scores.timer must fire on Monday')
    setup = [rule for rule in
             _ONCALENDAR.findall((DEPLOY / 'cfb-setup.timer').read_text())
             if rule.startswith('Mon ')]
    assert setup, 'cfb-setup.timer must fire on Monday'
    for rule in setup:
        assert rule.split()[-2] > '08:00:00', (
            f'{rule!r} fires before or with the 08:00 CT scores run')


def test_scores_service_is_ordered_after_the_spreads_service():
    """The scores run ends with the open retry (ADR-062): if the spreads run
    has not opened the next week, the scores run calls the opener itself.
    Two hours apart on an ordinary day; a Persistent boot replay after
    downtime spanning 06:00 and 08:00 CT fires both at once, and only a
    unit-level After= keeps the opener from running twice (two odds calls,
    two letters). Ordering only — a Wants= would fire a spreads run on
    every scores run."""
    directives = _directives(DEPLOY / 'cfb-scores.service')
    assert 'After=cfb-spreads.service' in directives
    assert not any(d.startswith('Wants=cfb-spreads') or
                   d.startswith('Requires=cfb-spreads') for d in directives)


def test_setup_service_is_ordered_after_the_scores_service():
    """The clock ordering above covers an ordinary Monday; a boot that
    missed BOTH firings replays them together (Persistent=true), and only
    a unit-level After= keeps the old week's scores run ahead of setup's
    write of the next week. Ordering only — a Wants= would fire a second
    /scores call (2 credits) on every setup."""
    directives = _directives(DEPLOY / 'cfb-setup.service')
    assert 'After=cfb-scores.service' in directives
    assert not any(d.startswith('Wants=cfb-scores') or
                   d.startswith('Requires=cfb-scores') for d in directives)
