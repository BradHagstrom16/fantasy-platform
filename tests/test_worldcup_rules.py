"""World Cup rules page — data-integrity locks (impeccable critique 2026-05-25).

The harden pass moved the rules reference page off hardcoded literals: the
tier team rosters now derive from canonical TEAMS data, and the Points-by-Tier
matrix derives every value from constants.py x the tier multipliers. These
tests lock that single-source-of-truth so the page can never silently drift
from the scoring engine, and guard against a regression that re-hardcodes the
template.
"""
from pathlib import Path

import pytest
from markupsafe import escape

from games.worldcup.constants import (
    ADVANCE_BEST_THIRD,
    ADVANCE_GROUP_WINNER,
    ADVANCE_RUNNER_UP,
    GROUP_DRAW,
    GROUP_WIN,
    KNOCKOUT_POINTS,
)
from games.worldcup.world_cup_countries import TEAMS, TIERS, teams_by_tier

ROOT = Path(__file__).parent.parent
RULES_TPL = ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'rules.html'


@pytest.fixture(scope='module')
def rules_source() -> str:
    """Raw rules.html template source for static-content assertions."""
    return RULES_TPL.read_text()


# ---------- teams_by_tier derives from canonical data ----------

def test_teams_by_tier_covers_every_team_once():
    """Every team appears exactly once across the tier grouping."""
    grouped = teams_by_tier()
    flat = [name for names in grouped.values() for name in names]
    assert len(flat) == len(TEAMS)
    assert sorted(flat) == sorted(t['display_name'] for t in TEAMS.values())


def test_teams_by_tier_membership_matches_team_records():
    """Each tier's members match the tier recorded on the team data."""
    grouped = teams_by_tier()
    for tier_num in TIERS:
        expected = {t['display_name'] for t in TEAMS.values() if t['tier'] == tier_num}
        assert set(grouped[tier_num]) == expected


# ---------- matrix + tier rosters render from source, not literals ----------

def test_rules_matrix_values_match_constants(client):
    """Every Points-by-Tier cell must equal base x tier-multiplier where base
    comes from constants.py. Computing expected from constants here means a
    drift between the engine and the page (or a re-hardcoded template) fails."""
    html = client.get('/worldcup/rules').get_data(as_text=True)

    base_by_label = {
        'Win a match': GROUP_WIN,
        'Draw a match': GROUP_DRAW,
        'Group winner': ADVANCE_GROUP_WINNER,
        'Runner-up': ADVANCE_RUNNER_UP,
        'Best 3rd': ADVANCE_BEST_THIRD,
        'Win Round of 32': KNOCKOUT_POINTS['R32'],
        'Win Round of 16': KNOCKOUT_POINTS['R16'],
        'Win Quarterfinal': KNOCKOUT_POINTS['QF'],
        'Win Semifinal': KNOCKOUT_POINTS['SF'],
        'Win 3rd-place match': KNOCKOUT_POINTS['third_place'],
        'Runner-up (lost final)': KNOCKOUT_POINTS['runner_up'],
        'Champion': KNOCKOUT_POINTS['champion'],
    }
    multipliers = [TIERS[n]['multiplier'] for n in range(1, 6)]

    # The headline ceremonial value: a Tier-5 (x7) champion banks 350.
    assert KNOCKOUT_POINTS['champion'] * 7 == 350
    assert '350' in html

    for label, base in base_by_label.items():
        assert label in html, f'matrix row label missing: {label}'
        for mult in multipliers:
            cell = ('%g' % (base * mult))
            assert cell in html, f'missing matrix cell {cell} for {label} x{mult}'


def test_rules_renders_tier_rosters_from_data(client):
    """Each tier's canonical team names appear on the rendered page (both the
    desktop table and the mobile cards consume the passed-in mapping)."""
    html = client.get('/worldcup/rules').get_data(as_text=True)
    grouped = teams_by_tier()
    for tier_num in TIERS:
        for name in grouped[tier_num]:
            # Jinja HTML-escapes names (e.g. "Bosnia & Herzegovina").
            assert str(escape(name)) in html, f'tier {tier_num} team missing from page: {name}'


def test_rules_template_has_no_hardcoded_team_or_matrix_literals(rules_source: str):
    """Guard against re-hardcoding: the template must not reinline the team
    rosters or the matrix base values. It should consume tier_teams /
    scoring_matrix / tier_multipliers from the route instead."""
    # The old duplicated team-list literals are gone.
    assert "Spain, France, England" not in rules_source
    assert "Iran, Australia, Tunisia" not in rules_source
    # The old hardcoded matrix literal block is gone.
    assert "{% set matrix = [" not in rules_source
    assert "{% set multipliers = [1.0, 1.5, 2.5, 4.0, 7.0] %}" not in rules_source
    # The route-provided structures are consumed.
    assert "tier_teams[tier_num]" in rules_source
    assert "scoring_matrix" in rules_source
    assert "tier_multipliers" in rules_source


def test_rules_disambiguates_match_win_from_group_win(client):
    """The confusable 'Group Win' (3) vs 'Win Group' (4) pair from the prior
    matrix is renamed to unambiguous phrasing and grouped by family. The
    advancement labels match across the prose table and the matrix."""
    html = client.get('/worldcup/rules').get_data(as_text=True)
    assert 'Win a match' in html       # per-match win (3 base)
    assert 'Group winner' in html      # group-stage advancement (4 base)
    # Old ambiguous capitalized label retired everywhere.
    assert 'Group Win' not in html
