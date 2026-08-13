"""The systemd preset policy (deploy/10-fantasy-platform.preset).

`deploy.sh` lints this file's *shape* before installing it, and
tests/test-deploy-guards.sh proves that lint rejects a dangerous one. Neither
can see the repo's actual timer set, which is what the interesting facts are
about: whether every game's timers have a policy at all, and whether the
archived game's rule still says what it is supposed to say.

Those are repo-side facts, so they are asserted here — the
tests/test_docket_timers.py pattern of locking a deploy/ file from the suite.
"""
from pathlib import Path

import pytest

DEPLOY = Path(__file__).parent.parent / 'deploy'
PRESET = DEPLOY / '10-fantasy-platform.preset'

VALID_DIRECTIVES = ('enable', 'disable', 'ignore')

# The archived game. `preset-all` must actively switch these off, not merely
# leave them alone: the 2026 tournament concluded 2026-07-19, worldcup-digest*
# mail real players, and all four timers set Persistent=true so an accidental
# enable fires immediately rather than at the next scheduled tick.
ARCHIVED_PREFIX = 'worldcup'


def _rules():
    """(directive, pattern) for every line systemd would actually read."""
    rules = []
    for line in PRESET.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in '#;':
            continue
        rules.append(tuple(stripped.split()))
    return rules


def _timer_prefixes():
    """The game prefix of every timer in deploy/, e.g. 'worldcup'.

    Split on the FIRST hyphen, not the last: worldcup-digest-player.timer
    belongs to 'worldcup', and a naive rsplit would invent a 'worldcup-digest'
    game that no preset line covers.
    """
    return {p.name.split('-', 1)[0] for p in DEPLOY.glob('*.timer')}


def test_preset_exists():
    assert PRESET.is_file(), f'{PRESET.name} is missing from deploy/'


def test_filename_sorts_before_the_vendor_preset():
    """The numeric prefix is load-bearing, not decoration.

    systemd.preset(5): preset files are sorted by filename lexicographically
    across every preset directory, and the first matching line wins. The box
    carries /usr/lib/systemd/system-preset/90-systemd.preset, so this file only
    outranks it while its prefix sorts lower. Dropping the prefix would put
    'f' after '9' and silently demote the whole policy.
    """
    prefix = PRESET.name.split('-', 1)[0]
    assert prefix.isdigit(), f'{PRESET.name} must start with a numeric prefix'
    assert int(prefix) < 90, (
        f'{PRESET.name} must sort before 90-systemd.preset; got prefix {prefix}'
    )


def test_every_line_is_a_directive_and_a_pattern():
    for rule in _rules():
        assert len(rule) == 2, (
            f'{rule!r} is not exactly "<directive> <pattern>". Preset files have '
            'no trailing-comment syntax — extra words are read as template '
            'instance names.'
        )
        assert rule[0] in VALID_DIRECTIVES, (
            f'{rule[0]!r} is not one of {VALID_DIRECTIVES}'
        )


@pytest.mark.parametrize('rule', _rules(), ids=lambda r: ' '.join(r))
def test_pattern_cannot_reach_beyond_this_platform(rule):
    """No rule here may match a unit this platform does not own.

    A preset file in /etc outranks the vendor policy for every unit it matches,
    so an over-broad pattern is not a bad deploy but a bad box: `disable *`
    would take getty@.service and systemd-resolved.service down at the next
    preset-all. `disable *.timer` is the one that looks safe and is not — it
    ends in .timer while still matching every timer on the machine.
    """
    pattern = rule[1]
    assert pattern.endswith('.timer'), (
        f'{pattern!r} does not end in .timer; this file governs game timers only'
    )
    assert pattern[0].isalnum(), (
        f'{pattern!r} starts with a wildcard and would match timers this '
        'platform does not own'
    )


@pytest.mark.parametrize('prefix', sorted(_timer_prefixes()))
def test_every_game_has_a_preset_policy(prefix):
    """A new game's timers must not inherit systemd's *enable* default.

    This is the drift that took the exposure from 4 to 14 to 19 timers with
    nobody widening it on purpose: each game's units landed in deploy/, got
    installed by the ADR-041 sync, and silently picked up PRESET=enabled. This
    test makes that choice deliberate — a new prefix fails CI until someone
    writes a rule for it.
    """
    covered = {rule[1].split('-', 1)[0] for rule in _rules()}
    assert prefix in covered, (
        f"deploy/{prefix}-*.timer has no rule in {PRESET.name}, so "
        f"`systemctl preset-all` would ENABLE those timers. Add an explicit "
        f"'disable {prefix}-*.timer' or 'ignore {prefix}-*.timer' line."
    )


def test_archived_game_is_disabled_not_ignored():
    """`ignore` would be a shrug where an assertion is required.

    The active games are `ignore` on purpose — their enablement is hand-managed
    ops state and preset-all should not touch it. World Cup is the opposite
    case: it is archived indefinitely, so preset-all is entitled to switch its
    timers back off if one is ever enabled by accident.
    """
    rules = {pattern: directive for directive, pattern in _rules()}
    pattern = f'{ARCHIVED_PREFIX}-*.timer'
    assert rules.get(pattern) == 'disable', (
        f'{pattern} must be "disable", not {rules.get(pattern)!r}'
    )


def test_no_catch_all_rule():
    """Belt and braces over the per-pattern checks: no rule may be a bare glob."""
    for _, pattern in _rules():
        assert pattern.strip('*?[]') != '', f'{pattern!r} is a catch-all'
