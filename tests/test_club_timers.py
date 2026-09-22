"""The Club Desk's systemd units (deploy/club-*, ADR-065).

Same rationale as tests/test_docket_timers.py: `systemd-analyze verify` on
the droplet checks syntax, not whether an ExecStart names a real command,
whether the timer fires at an hour the pass can use, or whether the After=
edges that stand in for a lock are present. Those are repo-side facts.

The After= edges are the real concurrency guard (docs/designs/unified-email.md):
there is deliberately no lock in code, so wherever two units can touch one
latch, unit ordering plus the latches are what keep a week from being opened
or announced twice.

Step 5 shipped club-paper (the Tuesday open of both games); step 9 shipped
club-remind (every reminder tier of both games) and retired cfb-remind,
docket-remind and docket-setup. The desk's rollout state (--anchor, --ride)
lives on club-remind's ExecStart line and is locked here as exact values.
"""
import re
from pathlib import Path

import pytest

DEPLOY = Path(__file__).parent.parent / 'deploy'
PRESET = DEPLOY / '10-fantasy-platform.preset'

# Spelled out, not globbed: a unit pair that goes missing in a rename should
# fail this file, not quietly shrink the covered set.
EXPECTED_UNITS = ('paper', 'remind')

TIMERS = [DEPLOY / f'club-{unit}.timer' for unit in EXPECTED_UNITS]
SERVICES = [DEPLOY / f'club-{unit}.service' for unit in EXPECTED_UNITS]
PAPER_TIMER = DEPLOY / 'club-paper.timer'
PAPER_SERVICE = DEPLOY / 'club-paper.service'
REMIND_TIMER = DEPLOY / 'club-remind.timer'
REMIND_SERVICE = DEPLOY / 'club-remind.service'

# The reminder desk's rollout state, exactly. --anchor names the games the
# desk leads for, --ride the slots that may carry a rider (F = Survivor's
# Friday warning, S = its Saturday final). Step 9's end state: every game
# anchors and both Survivor slots carry the Docket. A value drifting here is
# a production cutover and must change this line too.
REMIND_COMMAND = 'flask club desk --scheduled --anchor cfb,docket --ride F,S'
HOURLY = '*-*-* *:00:00 America/Chicago'

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


def _rules(timer):
    return [r.strip() for r in _ONCALENDAR.findall(timer.read_text())]


@pytest.mark.parametrize('path', TIMERS + SERVICES, ids=lambda p: p.name)
def test_unit_exists(path):
    assert path.is_file(), f'{path.name} is missing from deploy/'


@pytest.mark.parametrize('timer', TIMERS, ids=lambda p: p.name)
def test_every_timer_has_its_service(timer):
    """A timer whose .service is absent installs fine and then fails at its
    first firing."""
    assert timer.with_suffix('.service').is_file()


@pytest.mark.parametrize('service', SERVICES, ids=lambda p: p.name)
def test_service_pins_the_production_environment(service):
    directives = _directives(service)
    assert 'Environment=ENVIRONMENT=production' in directives
    assert 'Environment=FLASK_APP=app.py' in directives
    assert 'Type=oneshot' in directives


@pytest.mark.parametrize('timer', TIMERS, ids=lambda p: p.name)
def test_timer_is_enableable(timer):
    directives = _directives(timer)
    assert '[Install]' in directives
    assert 'WantedBy=timers.target' in directives


@pytest.mark.parametrize('timer', TIMERS, ids=lambda p: p.name)
def test_timer_is_persistent(timer):
    """A firing missed to downtime must still run when the box comes back:
    the latches and sent flags make the replay safe, the After= edges make
    it ordered."""
    assert 'Persistent=true' in _directives(timer)


@pytest.mark.parametrize('timer', TIMERS, ids=lambda p: p.name)
def test_oncalendar_carries_an_inline_timezone(timer):
    """There is no TimeZone= directive for timer units, so the zone has to be
    inline in OnCalendar. Omitting it silently schedules in UTC."""
    rules = _rules(timer)
    assert rules, f'{timer.name} defines no OnCalendar'
    for rule in rules:
        assert rule.endswith('America/Chicago'), rule


def test_preset_ignores_the_club_prefix():
    """Cut over by name at each step; preset-all must touch neither the old
    unit nor the new one (tests/test_systemd_preset.py covers the prefix
    bijection; this pins the verb)."""
    rules = [tuple(line.split()) for line in _directives(PRESET)]
    assert ('ignore', 'club-*.timer') in rules


# ── the Paper ─────────────────────────────────────────────────────────────

def test_paper_service_runs_the_paper_in_scheduled_form():
    """`--scheduled` is the TIMER-ONLY flag (out of season and nothing-open
    become a logged exit 0). Never `--dry-run`: the unit is the real send."""
    exec_starts = _EXECSTART.findall(PAPER_SERVICE.read_text())
    assert len(exec_starts) == 1, 'club-paper.service needs exactly one ExecStart'
    command = exec_starts[0]
    assert command.endswith('flask club paper --scheduled'), command
    assert re.search(r'(?<!\S)--scheduled(?!\S)', command)
    assert '--dry-run' not in command


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
    rules = _rules(PAPER_TIMER)
    assert rules == ['Tue *-*-* 06:15:00 America/Chicago'], rules
    docket_scores = _ONCALENDAR.findall((DEPLOY / 'docket-scores.timer').read_text())
    tuesday_grade = [_clock(r) for r in docket_scores if r.startswith('Tue ')]
    assert tuesday_grade and all(c < '06:00:00' for c in tuesday_grade)
    assert '06:00:00' < _clock(rules[0]) < '07:00:00'


def test_paper_is_the_only_tuesday_docket_open():
    """docket-setup's unit was retired at step 9 (its Tuesday open runs
    inside the Paper). deploy.sh installs every unit in deploy/, so a
    docket-setup pair reappearing here would open the week twice."""
    assert not (DEPLOY / 'docket-setup.service').exists()
    assert not (DEPLOY / 'docket-setup.timer').exists()
    assert 'docket-setup.service' not in _after(PAPER_SERVICE)


# ── the After= edges around the Paper ─────────────────────────────────────

def test_paper_runs_after_the_friday_spreads_opener():
    """cfb-spreads is Friday-only, so the two never share a scheduled
    instant — but a Persistent boot replay after downtime spanning both
    queues them together, and then the opener goes first and its
    picks_open_notified latch makes the Paper's Survivor section a no-op.
    Ordering only — a Wants= would start the opener on every Paper."""
    assert 'cfb-spreads.service' in _after(PAPER_SERVICE)
    assert not _pulls(PAPER_SERVICE, 'cfb-spreads.service')


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


# ── the reminder desk (step 9) ────────────────────────────────────────────

def test_remind_service_runs_the_desk_for_every_game_with_both_rides():
    """The exact rollout state, whole-token: `--anchor cfb,docket` (every
    game's tiers anchor; 1A: a Docket-only week sends its own three) and
    `--ride F,S` (the Docket rides both Survivor letters). `--scheduled` is
    the timer-only flag; never `--dry-run`."""
    exec_starts = _EXECSTART.findall(REMIND_SERVICE.read_text())
    assert len(exec_starts) == 1, 'club-remind.service needs exactly one ExecStart'
    command = exec_starts[0]
    prefix = '/home/deploy/fantasy-platform/venv/bin/'
    assert command.startswith(prefix), command
    assert command[len(prefix):] == REMIND_COMMAND
    assert re.search(r'(?<!\S)--scheduled(?!\S)', command)
    assert '--dry-run' not in command


def test_remind_fires_hourly_with_no_weekday_restriction():
    """The de-dup guarantee lives in each game's sent flag, so the cadence
    only has to land inside every window at least once: Survivor's span
    130 minutes (two landings, the second an outage retry), the Docket's
    70. Hourly does that for ANY deadline time; a weekday-restricted rule
    would silently send ZERO reminders for a hand-scheduled CFP week."""
    assert _rules(REMIND_TIMER) == [HOURLY], _rules(REMIND_TIMER)


def test_remind_never_shares_the_papers_instant():
    """Tue 06:15 is the Paper's; the desk fires on the hour. Both write the
    Docket week (the Paper creates it, the desk reads it), and there is no
    lock in code, so the two clocks must stay off each other."""
    def minute(rule):
        return _clock(rule).split(':')[1]
    assert all(minute(r) == '00' for r in _rules(REMIND_TIMER))
    assert all(minute(r) != '00' for r in _rules(PAPER_TIMER))


def test_remind_keeps_the_single_pass_timeout():
    """Two games' tiers in one firing still finish inside the 5 minutes
    each legacy pass had: no odds call, mail only."""
    assert 'TimeoutStartSec=5m' in _directives(REMIND_SERVICE)


@pytest.mark.parametrize('retired', ['cfb-remind', 'docket-remind'])
def test_retired_remind_units_stay_retired(retired):
    """club-remind owns every tier and there is no lock in code. deploy.sh
    installs every unit in deploy/, so a retired pair reappearing here is
    one `systemctl enable` from two units racing one sent flag (deploy.sh
    warns on that state; this keeps the file from existing at all)."""
    assert not (DEPLOY / f'{retired}.service').exists()
    assert not (DEPLOY / f'{retired}.timer').exists()
