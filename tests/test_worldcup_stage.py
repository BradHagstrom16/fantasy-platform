"""Tests for games.worldcup.services.stage.stage_label.

Single SSoT for mapping WorldCupMatch.stage codes to display labels.
NOT to be confused with tournament-level phase ('pre_tournament' /
'group_stage' / 'knockout' / 'completed') — that's _derive_tournament_phase
in routes.py, a different value space per CLAUDE.md.
"""
import pytest

from games.worldcup.services.stage import stage_label


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
