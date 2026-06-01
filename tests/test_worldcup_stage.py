"""Tests for games.worldcup.services.stage.stage_label.

Single SSoT for mapping WorldCupMatch.stage codes to display labels.
NOT to be confused with tournament-level phase ('pre_tournament' /
'group_stage' / 'knockout' / 'completed') — that's _derive_tournament_phase
in routes.py, a different value space per CLAUDE.md.
"""
import pytest

from games.worldcup.services.stage import stage_label, best_finish_label


@pytest.mark.parametrize('code,expected', [
    ('group', 'Group Stage'),
    ('R32', 'Round of 32'),
    ('R16', 'Round of 16'),
    ('QF', 'Quarterfinals'),
    ('SF', 'Semifinals'),
    ('third_place', 'Third-Place Match'),
    ('final', 'The Final'),
])
def test_stage_label_known_codes(code, expected):
    assert stage_label(code) == expected


def test_stage_label_unknown_code_falls_back_to_group_stage():
    """Defensive default — matches the pre-lift behavior."""
    assert stage_label('mystery') == 'Group Stage'


def test_stage_label_does_not_mangle_all_caps():
    """Regression: Jinja's |title filter mangles 'SF' -> 'Sf'.
    stage_label() must preserve the canonical display form."""
    assert stage_label('SF') == 'Semifinals'
    assert stage_label('QF') == 'Quarterfinals'
    assert stage_label('R32') == 'Round of 32'


def test_stage_label_does_not_mangle_underscores():
    """Regression: Jinja's |title filter renders 'third_place' -> 'Third_Place'."""
    assert stage_label('third_place') == 'Third-Place Match'


# ---------------------------------------------------------------------------
# best_finish_label — SSoT for WorldCupTeam.best_finish codes (a DIFFERENT
# value space from stage codes: adds 'champion'/'runner_up'/'3rd', and an
# empty/None value means "advanced but eliminated in the Round of 32").
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('code,expected', [
    ('group', 'Group Stage'),
    ('R32', 'Round of 32'),
    ('R16', 'Round of 16'),
    ('QF', 'Quarterfinals'),
    ('SF', 'Semifinals'),
    ('3rd', '3rd Place'),
    ('runner_up', 'Runner-up'),
    ('champion', 'Champion'),
])
def test_best_finish_label_known_codes(code, expected):
    """B1 regression: codes must render as display labels, never raw."""
    assert best_finish_label(code) == expected


@pytest.mark.parametrize('empty', ['', None])
def test_best_finish_label_empty_means_reached_round_of_32(empty):
    """F1: a team that advanced from its group but won no knockout match has an
    empty best_finish — it reached the Round of 32 and lost. This is DISTINCT
    from 'group' (eliminated in the group stage), so it must NOT collapse to
    'Group Stage'."""
    assert best_finish_label(empty) == 'Round of 32'


def test_best_finish_label_unknown_code_falls_back_to_raw():
    """CLAUDE.md: surface an unmapped code as itself, never silently 'Group'."""
    assert best_finish_label('mystery') == 'mystery'
