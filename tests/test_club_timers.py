"""The Club Desk's systemd units (deploy/club-*, ADR-065).

Same rationale as tests/test_docket_timers.py: `systemd-analyze verify` on
the droplet checks syntax, not whether an ExecStart names a real command,
whether the timer fires at an hour the pass can use, or whether the After=
edges that stand in for a lock are present. Those are repo-side facts.

The After= edges are the real concurrency guard (docs/designs/unified-email.md):
there is deliberately no lock in code, so while an old opener and a Club
Desk unit coexist on the box, unit ordering plus the latches are what keep a
week from being opened or announced twice.

Step 5 ships club-paper; club-remind (step 9) joins EXPECTED_UNITS then.
"""
import re
from pathlib import Path

import pytest

DEPLOY = Path(__file__).parent.parent / 'deploy'
PRESET = DEPLOY / '10-fantasy-platform.preset'

# Spelled out, not globbed: a unit pair that goes missing in a rename should
# fail this file, not quietly shrink the covered set.
EXPECTED_UNITS = ('paper',)

TIMERS = [DEPLOY / f'club-{unit}.timer' for unit in EXPECTED_UNITS]
SERVICES = [DEPLOY / f'club-{unit}.service' for unit in EXPECTED_UNITS]
PAPER_TIMER = DEPLOY / 'club-paper.timer'
PAPER_SERVICE = DEPLOY / 'club-paper.service'

_ONCALENDAR = re.compile(r'^OnCalendar=(.+)$', re.MULTILINE)
_EXECSTART = re.compile(r'^ExecStart=(.+)$', re.MULTILINE)


def _directives(path):
    """Non-comment, non-blank lines — the part systemd actually reads."""
    return [line for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def _after(path):
    """Every unit named on an After= line (several lines, several per line)."""
    return {unit for d in _directives(path) if d.startswith('After=')
            for unit in d.split('=', 1)[1].split()}


def _pulls(path, unit):
    """True when the unit would START ``unit``, not just order after it."""
    return any(d.startswith(('Wants=', 'Requires='))
               and unit in d.split('=', 1)[1].split()
               for d in _directives(path))


def test_pulls_sees_a_pull_dependency():
    """The guard for the ordering-only assertions below: a `Wants=` line
    with the key still attached to the unit name must register."""
    assert 'network-online.target' in _after(PAPER_SERVICE)
    assert _pulls(PAPER_SERVICE, 'network-online.target')
    assert not _pulls(PAPER_SERVICE, 'cfb-spreads.service')


def _clock(rule):
    return rule.split()[-2]


@pytest.mark.parametrize('path', TIMERS + SERVICES, ids=lambda p: p.name)
def test_unit_exists(path):
    assert path.is_file(), f'{path.name} is missing from deploy/'


@pytest.mark.parametrize('timer', TIMERS, ids=lambda p: p.name)
def test_every_timer_has_its_service(timer):
    """A timer whose .service is absent installs fine and then fails at its
    first firing."""
    assert timer.with_suffix('.service').is_file()


def test_paper_service_runs_the_paper_in_scheduled_form():
    """`--scheduled` is the TIMER-ONLY flag (out of season and nothing-open
    become a logged exit 0). Never `--dry-run`: the unit is the real send."""
    exec_starts = _EXECSTART.findall(PAPER_SERVICE.read_text())
    assert len(exec_starts) == 1, 'club-paper.service needs exactly one ExecStart'
    command = exec_starts[0]
    assert command.endswith('flask club paper --scheduled'), command
    assert re.search(r'(?<!\S)--scheduled(?!\S)', command)
    assert '--dry-run' not in command


def test_paper_service_pins_the_production_environment():
    directives = _directives(PAPER_SERVICE)
    assert 'Environment=ENVIRONMENT=production' in directives
    assert 'Environment=FLASK_APP=app.py' in directives
    assert 'Type=oneshot' in directives


def test_paper_service_allows_two_openers():
    """Each opener had 5m on its own unit; the Paper runs both, then sends."""
    assert 'TimeoutStartSec=10m' in _directives(PAPER_SERVICE)


def test_paper_fires_tuesday_after_the_boundary_and_the_grading_run():
    """06:15 CT, exactly: after the Tue 06:00 week boundary the Paper
    resolves the Docket week from (firing AT it would race the
    arithmetic), and after the 05:15 docket-scores run that grades Monday
    night, so the record the Paper carries is the graded one. Before the
    07:00 standalone record handoff (RECORD_HANDOFF) and the 07:00
    docket-lines announcer."""
    rules = [r.strip() for r in _ONCALENDAR.findall(PAPER_TIMER.read_text())]
    assert rules == ['Tue *-*-* 06:15:00 America/Chicago'], rules
    docket_scores = _ONCALENDAR.findall((DEPLOY / 'docket-scores.timer').read_text())
    tuesday_grade = [_clock(r) for r in docket_scores if r.startswith('Tue ')]
    assert tuesday_grade and all(c < '06:00:00' for c in tuesday_grade)
    assert '06:00:00' < _clock(rules[0]) < '07:00:00'


def test_paper_timer_is_persistent():
    """A Tuesday missed to downtime must still open both games when the box
    comes back: the latches make the replay safe, the After= edges make it
    ordered."""
    assert 'Persistent=true' in _directives(PAPER_TIMER)


def test_timer_is_enableable():
    directives = _directives(PAPER_TIMER)
    assert '[Install]' in directives
    assert 'WantedBy=timers.target' in directives


def test_preset_ignores_the_club_prefix():
    """Cut over by name at each step; preset-all must touch neither the old
    unit nor the new one (tests/test_systemd_preset.py covers the prefix
    bijection; this pins the verb)."""
    rules = [tuple(line.split()) for line in _directives(PRESET)]
    assert ('ignore', 'club-*.timer') in rules


# ── the After= edges: the concurrency guard while old and new coexist ─────

def test_paper_runs_after_the_legacy_tuesday_openers():
    """During the cutover window (or a Persistent boot replay that fires
    every missed Tuesday unit at once) the legacy openers go first and
    their picks_open_notified latch makes the Paper's matching section a
    no-op. Ordering only — a Wants= would start docket-setup on every
    Paper, re-announcing standalone the week the Paper is about to carry."""
    after = _after(PAPER_SERVICE)
    assert {'cfb-spreads.service', 'docket-setup.service'} <= after, after
    for unit in ('cfb-spreads.service', 'docket-setup.service'):
        assert not _pulls(PAPER_SERVICE, unit), f'{unit} must be ordering only'


def test_survivor_open_retry_runs_after_the_paper():
    """cfb-scores ends with the ADR-062 open retry, the same opener the
    Paper runs. A boot replay spanning 06:15 and 08:00 CT fires both; only a
    unit-level After= keeps the opener from running twice (two odds calls,
    two letters)."""
    service = DEPLOY / 'cfb-scores.service'
    assert 'club-paper.service' in _after(service)
    assert not _pulls(service, 'club-paper.service')


def test_docket_gap_fill_runs_after_the_paper():
    """docket-lines at 07:00 is the standalone announcer for a week the Paper
    imported partial or failed to open; replayed together it must not
    announce standalone a week the Paper was about to carry."""
    service = DEPLOY / 'docket-lines.service'
    assert 'club-paper.service' in _after(service)
    assert not _pulls(service, 'club-paper.service')


def test_paper_and_docket_setup_share_the_tuesday_instant():
    """Both fire Tue 06:15; while both are enabled (the cutover window) the
    After= edge above is what sequences them. A drift in either clock would
    silently turn that guard into a race."""
    setup = [r.strip() for r in
             _ONCALENDAR.findall((DEPLOY / 'docket-setup.timer').read_text())]
    paper = [r.strip() for r in _ONCALENDAR.findall(PAPER_TIMER.read_text())]
    assert setup == paper, (setup, paper)


# ── step 7: the Survivor desk carries a Docket rider; the Docket pass follows ─

def test_docket_remind_runs_after_the_survivor_desk():
    """Since step 7 cfb-remind IS the desk (`--anchor cfb --ride F`): the
    Docket rides Friday's warning and its 48h tier is pre-marked. Both timers
    fire on the hour and a Persistent replay queues them together; only this
    After= lands the mark before docket-remind reads last_reminder_tier.
    Ordering only — a Wants= would run the desk on every Docket firing."""
    service = DEPLOY / 'docket-remind.service'
    assert 'cfb-remind.service' in _after(service)
    assert not _pulls(service, 'cfb-remind.service')


def test_both_remind_timers_share_the_hourly_instant():
    """The After= edge sequences co-queued firings only. If the two clocks
    ever drifted apart the edge would stop applying and the guard would
    silently become a race."""
    cfb = [r.strip() for r in
           _ONCALENDAR.findall((DEPLOY / 'cfb-remind.timer').read_text())]
    docket = [r.strip() for r in
              _ONCALENDAR.findall((DEPLOY / 'docket-remind.timer').read_text())]
    assert cfb == docket == ['*-*-* *:00:00 America/Chicago'], (cfb, docket)
