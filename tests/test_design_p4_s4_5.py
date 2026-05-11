"""P4 S4.5 — cross-cluster pre-live polish locks (3 fix PIs + triage).

S4.5 is a cluster polish session (NOT cluster mop-up) — 5 PI triage
outcomes per §1.5c (decided no-ops + re-routes count toward the cap):

- PI-1 (FIX): drop outer-table Base column on picks.html + player_detail.html;
        the accordion's "Total base × multiplier" summary becomes the
        canonical Base disclosure. Closes [S4.2.1 cross-cluster] derivation
        column trio. team_detail.html already escaped via S2.3.1 hero pattern.
- PI-2 (RE-ROUTE → S6.1): tier vocabulary canonical primitive — premise
        refuted on team_detail/player_detail/stats (no tier-badge there).
        Doc PI for DESIGN.md §6 lands at S6.1.
- PI-3 (FIX): rules.html in-page navigation accelerator. Pill rail of 7
        anchors above content. Sibling primitive to .wc-group-index (S4.4.1
        PI-3) and .schedule-jump-today (S2.6 PI-4).
- PI-4 (FIX): .wc-group-index ultra-wide max-width cap on ≥xl breakpoint
        (≥1200px). Prevents 12-pill rail stretching ~540px+ on 1470 viewport.
        Same cap covers the new .wc-rules-index sibling.
- PI-5 (NO-OP + DESIGN.md route): mobile <16px caption-tier typography
        accepted as committed cross-cluster pattern; §3 dispensation doc
        lands at S6.1.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'
WC_TPL = ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup'
PICK_ROW_PATH = WC_TPL / '_pick_row.html'
PICKS_PATH = WC_TPL / 'picks.html'
PLAYER_DETAIL_PATH = WC_TPL / 'player_detail.html'
RULES_PATH = WC_TPL / 'rules.html'


@pytest.fixture(scope='module')
def css_source() -> str:
    return CSS_PATH.read_text()


@pytest.fixture(scope='module')
def pick_row_source() -> str:
    return PICK_ROW_PATH.read_text()


@pytest.fixture(scope='module')
def picks_source() -> str:
    return PICKS_PATH.read_text()


@pytest.fixture(scope='module')
def player_detail_source() -> str:
    return PLAYER_DETAIL_PATH.read_text()


@pytest.fixture(scope='module')
def rules_source() -> str:
    return RULES_PATH.read_text()


# ---------- PI-1: drop outer-table Base column ----------

def test_pi1_pick_row_outer_drops_base_td(pick_row_source: str):
    """`_pick_row.html` no longer emits the outer-row Base td.
    The line `<td class="text-end wc-numeral">{{ "%.1f"|format(pick.base_points) }}</td>`
    in the outer-row block was the 4th of 5 td's; it's removed so the
    Multiplied total now sits directly after the multiplier chip."""
    assert '<td class="text-end wc-numeral">{{ "%.1f"|format(pick.base_points) }}</td>' not in pick_row_source


def test_pi1_pick_row_accordion_colspan_dropped_to_four(pick_row_source: str):
    """Accordion row colspan tracked the outer column count. 5 → 4 after
    the Base column drop. Regression guard against a stale colspan that
    would break the accordion's full-width span."""
    assert 'colspan="4"' in pick_row_source
    assert 'colspan="5"' not in pick_row_source


def test_pi1_pick_row_accordion_keeps_total_base_disclosure(pick_row_source: str):
    """The 'Total base X × multiplier Y = multiplied Z' line inside the
    accordion is now the canonical Base disclosure. Without it the column
    drop would erase Base entirely."""
    assert 'Total base' in pick_row_source
    assert '{{ "%.1f"|format(pick.base_points) }}' in pick_row_source
    assert '{{ "%.1f"|format(pick.multiplied_points) }}' in pick_row_source


def test_pi1_picks_html_header_drops_base_th(picks_source: str):
    """Picks readonly outer-table header no longer carries `<th>Base</th>`.
    Three th's remain pre-Points: Team / Tier / Multiplier."""
    assert '<th scope="col" class="text-end">Base</th>' not in picks_source
    assert '<th scope="col" class="text-end">Points</th>' in picks_source
    assert '<th scope="col" class="text-center">Multiplier</th>' in picks_source


def test_pi1_picks_html_caption_drops_base_phrase(picks_source: str):
    """The visually-hidden table caption used to enumerate 'tier, multiplier,
    base points, and total points' — drop 'base points' and add the
    accordion-disclosure hint so screen-reader users know depth is one
    expand away."""
    assert 'base points' not in picks_source.lower() or 'Expand a row to see base points' in picks_source
    # Affirmative form: the new caption phrasing is present.
    assert 'with tier, multiplier, and total points' in picks_source
    assert 'Expand a row to see base points' in picks_source


def test_pi1_player_detail_header_drops_base_th(player_detail_source: str):
    """player_detail.html mirrors picks.html — same column drop."""
    assert '<th scope="col" class="text-end">Base</th>' not in player_detail_source
    assert '<th scope="col" class="text-end">Points</th>' in player_detail_source


def test_pi1_player_detail_tfoot_drops_total_base_cell(player_detail_source: str):
    """The tfoot total row was 'Total | base_sum | mult_sum' spanning 5
    columns (colspan=3 label + 2 numeric cells). After the column drop it
    is 'Total | mult_sum' spanning 4 columns (colspan=3 label + 1 numeric
    cell). The orphaned total_base namespace var is removed."""
    assert 'ns.total_base' not in player_detail_source
    # Only one total cell remains in the tfoot row (the multiplied sum).
    assert '{{ "%.1f"|format(ns.total_mult) }}' in player_detail_source
    assert '{{ "%.1f"|format(ns.total_base) }}' not in player_detail_source


# ---------- PI-3: rules.html in-page navigation accelerator ----------

EXPECTED_RULES_SECTIONS = [
    ('rules-overview', 'Overview'),
    ('rules-tiers', 'Tiers'),
    ('rules-group-stage', 'Group stage'),
    ('rules-knockout', 'Knockout'),
    ('rules-points-matrix', 'By tier'),
    ('rules-tiebreaker', 'Tiebreaker'),
    ('rules-edge-cases', 'Edge cases'),
]


def test_pi3_rules_index_nav_is_semantic_nav(rules_source: str):
    """The rail is a semantic <nav> with an aria-label that names its
    purpose. Screen-reader users hear 'Jump to section' as the nav
    landmark name."""
    assert '<nav class="wc-rules-index" aria-label="Jump to section">' in rules_source


def test_pi3_rules_index_carries_seven_pills_with_expected_anchors(rules_source: str):
    """Each H2 in rules.html maps to one pill; href targets match the
    section id below."""
    for anchor_id, label in EXPECTED_RULES_SECTIONS:
        pill = f'<a href="#{anchor_id}" class="wc-rules-index-pill">{label}</a>'
        assert pill in rules_source, f'missing rules-index pill for {anchor_id!r}'


def test_pi3_rules_h2s_carry_matching_ids(rules_source: str):
    """Each H2 in the document outline carries the matching id so the
    pill rail resolves. Without these ids the anchors are dead."""
    for anchor_id, _label in EXPECTED_RULES_SECTIONS:
        h2 = f'<h2 id="{anchor_id}" class="wc-section-heading">'
        assert h2 in rules_source, f'missing H2 id={anchor_id!r}'


def test_pi3_wc_rules_index_pill_carries_44px_min_height(css_source: str):
    """44px tap-target floor per PRODUCT.md mobile hard requirement."""
    rule = _extract_rule(css_source, '.wc-rules-index-pill')
    assert 'min-height: 44px' in rule


def test_pi3_wc_rules_index_pill_has_focus_visible_ring(css_source: str):
    """Canonical CCC gold-light :focus-visible ring — same primitive as
    `.wc-group-index-pill` and `.schedule-jump-today`."""
    rule = _extract_rule(css_source, '.wc-rules-index-pill:focus-visible')
    assert 'outline: 2px solid var(--gold-light)' in rule
    assert 'outline-offset: 2px' in rule


# ---------- PI-4: .wc-group-index ultra-wide max-width cap ----------

def test_pi3_rules_h2_targets_carry_scroll_margin_offset(css_source: str):
    """`.wc-rules-index` pill jumps land on id-bearing `.wc-section-heading`
    H2s; without `scroll-margin-top` matching the sticky `.navbar` +
    `.game-subnav` stack (~98px), the section title would hide under the
    chrome on jump. Mirrors the `.group-table { scroll-margin-top: 6.5rem }`
    lock from S4.4.1 PI-3. Scoped to id-bearing headings so non-anchor uses
    of the primitive don't inherit the offset."""
    expected = (
        '.wc-section-heading[id],\n'
        '.wc-subsection-heading[id] {\n'
        '  scroll-margin-top: 6.5rem;\n'
        '}'
    )
    assert expected in css_source


def test_pi4_xl_breakpoint_caps_group_and_rules_index_max_width(css_source: str):
    """`@media (min-width: 1200px)` block applies a max-width to both
    `.wc-group-index` and the new `.wc-rules-index` sibling so the rail
    stops stretching ~540px+ on a 1470 viewport. The cap is set to 720px
    (content-narrow). Single locator string keeps the lock atomic."""
    expected = (
        '@media (min-width: 1200px) {\n'
        '  .wc-group-index,\n'
        '  .wc-rules-index {\n'
        '    max-width: 720px;\n'
        '  }\n'
        '}'
    )
    assert expected in css_source


# ---------- helpers ----------

def _extract_rule(css: str, selector: str) -> str:
    """Return the body of the first CSS rule whose selector starts with
    `selector` followed by ` {`. Crude but adequate for these locks."""
    needle = selector + ' {'
    idx = css.find(needle)
    assert idx != -1, f'selector {selector!r} not found in css'
    end = css.find('}', idx)
    assert end != -1, f'no closing brace for {selector!r}'
    return css[idx:end + 1]
