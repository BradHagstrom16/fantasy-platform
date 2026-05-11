"""P4 S4.4.1 — locks for groups.html iteration 1 (5 PIs + 1 freebie).

Coverage:
- PI-1: H1 → H2×12 outline restoration via .wc-section-heading primitive;
        .group-table-header is an <h2> with the primitive class; each <table>
        carries aria-labelledby pointing at its H2 (freebie F3 folded in).
- PI-2: .group-table table th + .advancement-badge.eliminated lifted from
        --text-muted to --text-secondary (AA on white).
- PI-3: in-page .wc-group-index pill rail above the grid (anti-pattern
        identical-card-grid mitigation + mobile-scroll navigation).
- PI-4: .team-name-cell at 1rem (mobile body floor); narrow-viewport
        override no longer drops it below 16px.
- PI-5: hero voice rewrite + state chip rendered conditionally on wc_state.
- F1: numeric column widths via .group-stat-col / .group-pts-col classes,
      not inline style attributes.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'
TPL_PATH = ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'groups.html'


@pytest.fixture(scope='module')
def css_source() -> str:
    return CSS_PATH.read_text()


@pytest.fixture(scope='module')
def tpl_source() -> str:
    return TPL_PATH.read_text()


# ---------- PI-1: heading outline restoration ----------

def test_pi1_group_header_is_h2_with_section_heading_primitive(tpl_source: str):
    """The `Group {{ letter }}` masthead is rendered as <h2> carrying both
    .group-table-header (the dark-band surface scope) and .wc-section-heading
    (the S4.3.1 primitive)."""
    assert '<h2 id="group-{{ letter }}-heading" class="group-table-header wc-section-heading">Group {{ letter }}</h2>' in tpl_source


def test_pi1_no_div_group_table_header_remains(tpl_source: str):
    """Regression guard: the pre-S4.4.1 <div class="group-table-header">
    must not survive — it would break the H1→H2 outline."""
    assert '<div class="group-table-header">' not in tpl_source


def test_pi1_each_table_carries_aria_labelledby_to_its_h2(tpl_source: str):
    """F3 folded into PI-1 atomic edit: <table aria-labelledby="group-X-heading">
    pairs each data table with its visible heading. Single Jinja source line
    fans out to 12 rendered tables."""
    assert 'aria-labelledby="group-{{ letter }}-heading"' in tpl_source


def test_pi1_group_table_header_css_is_scoped_to_group_table(css_source: str):
    """Compound selector `.group-table .group-table-header` (specificity 0,0,2,0)
    is required to beat .wc-section-heading's later-in-file (0,0,1,0) cascade
    on the conflicting margin-bottom + font-size properties."""
    assert '.group-table .group-table-header {' in css_source


def test_pi1_group_table_header_no_longer_redeclares_primitive_properties(css_source: str):
    """After the dedupe, font-family, font-weight, text-transform, and
    letter-spacing live on .wc-section-heading only. The .group-table
    .group-table-header surface scope owns surface-specific properties
    (background, color, padding, font-size override, margin reset).
    Locks that the surface rule body matches the dedupe contract verbatim."""
    expected = (
        ".group-table .group-table-header {\n"
        "  background: var(--game-primary-dark);\n"
        "  color: var(--text-on-dark);\n"
        "  padding: .65rem 1rem;\n"
        "  font-size: 1.1rem;\n"
        "  margin: 0;\n"
        "}"
    )
    assert expected in css_source


# ---------- PI-2: --text-muted → --text-secondary AA lift ----------

def test_pi2_th_color_lifted_to_text_secondary(css_source: str):
    """`.group-table table th` paints --text-secondary (#5A5470, ~6.9:1 on
    white) instead of --text-muted (#8A849B, ~3.6:1, AA-fail at 12px)."""
    block = _extract_rule(css_source, '.group-table table th')
    assert 'color: var(--text-secondary);' in block
    assert 'color: var(--text-muted)' not in block


def test_pi2_eliminated_badge_color_lifted_to_text_secondary(css_source: str):
    """`.advancement-badge.eliminated` uses --text-secondary. Latent in
    dev DB but spec was AA-broken pre-S4.4.1."""
    block = _extract_rule(css_source, '.advancement-badge.eliminated')
    assert 'color: var(--text-secondary)' in block
    assert 'color: var(--text-muted)' not in block


# ---------- PI-3: group index pill rail ----------

def test_pi3_index_nav_rendered_above_grid(tpl_source: str):
    """A <nav class="wc-group-index" aria-label="Jump to group"> wrapper
    sits above the .row.g-3 grid."""
    assert '<nav class="wc-group-index" aria-label="Jump to group">' in tpl_source


def test_pi3_index_nav_renders_one_pill_per_group_letter(tpl_source: str):
    """The Jinja loop iterates groups.keys() and emits one anchor pill per
    letter. Each anchor points to the existing #group-{letter} id."""
    assert '{% for letter in groups.keys() %}' in tpl_source
    assert '<a href="#group-{{ letter }}" class="wc-group-index-pill">{{ letter }}</a>' in tpl_source


def test_pi3_index_pill_meets_44_floor_in_css(css_source: str):
    """`.wc-group-index-pill` carries min-width: 44px and min-height: 44px
    so the rail honors the WCAG 2.1 tap-target floor on mobile (probed live:
    44×44 at viewport <540px)."""
    block = _extract_rule(css_source, '.wc-group-index-pill')
    assert 'min-width: 44px;' in block
    assert 'min-height: 44px;' in block


def test_pi3_index_pill_carries_canonical_focus_visible_ring(css_source: str):
    """Canonical CCC focus-ring (2px gold-light + 2px offset), matching the
    S2.1.2 + S3.4 + S4.3.1 lock."""
    focus_block = _extract_rule(css_source, '.wc-group-index-pill:focus-visible')
    assert 'outline: 2px solid var(--gold-light);' in focus_block
    assert 'outline-offset: 2px;' in focus_block


# ---------- PI-4: mobile body floor on team-name cell ----------

def test_pi4_team_name_cell_floors_at_1rem(css_source: str):
    """The page's primary read-target cell paints 16px (1rem) at every
    viewport. PRODUCT.md mobile-first floor."""
    block = _extract_rule(css_source, '.group-table .team-name-cell')
    assert 'font-size: 1rem;' in block


def test_pi4_narrow_viewport_no_longer_overrides_team_name_size(css_source: str):
    """The `@media (max-width: 400px)` block previously dropped
    `.team-name-cell` to .82rem (~13.1px on 375 viewport) — below the floor.
    The numeric override (`.group-table table { font-size: .8rem }`) survives;
    the team-name override does not. Scopes the search to the
    `18l. WC Groups` narrow-viewport block specifically (the file contains
    multiple `@media (max-width: 400px)` blocks)."""
    anchor = css_source.find('/* --- 18l. WC Groups')
    assert anchor != -1, 'WC Groups narrow-viewport comment marker missing'
    # The actual @media rule body begins after the comment block and a `{`
    media_open = css_source.find('@media (max-width: 400px) {', anchor)
    assert media_open != -1, '18l block @media rule missing'
    # Walk braces to find the matching close
    depth = 0
    end = media_open
    for i in range(media_open, len(css_source)):
        ch = css_source[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    media_block = css_source[media_open:end]
    assert '.82rem' not in media_block, 'team-name-cell .82rem override should be gone'
    assert 'team-name-cell' not in media_block, 'team-name-cell rule should not be in this block'
    # The narrow-viewport block does still shrink the numeric table cells
    assert '.group-table table {' in media_block
    assert 'font-size: .8rem;' in media_block


# ---------- PI-5: state chip + voice copy ----------

def test_pi5_route_passes_wc_state_to_template():
    """The /worldcup/groups route imports worldcup_state and threads its
    return value into the render_template context under the name `wc_state`."""
    routes = (ROOT / 'games' / 'worldcup' / 'routes.py').read_text()
    # Find the groups() route block
    idx = routes.find("@worldcup_bp.route('/groups')")
    assert idx != -1
    block = routes[idx:idx + 800]
    assert 'from games.worldcup.services.state import worldcup_state' in block
    assert 'wc_state=worldcup_state()' in block


def test_pi5_template_renders_state_chip_branched_on_wc_state(tpl_source: str):
    """Three branches: pre, live, post. Each renders a .wc-state-chip with
    its modifier class. Lives in `.container` below the hero, not inside it."""
    for state in ('pre', 'live', 'post'):
        assert f"{{% if wc_state == '{state}' %}}" in tpl_source or f"{{% elif wc_state == '{state}' %}}" in tpl_source
        assert f'wc-state-chip--{state}' in tpl_source


def test_pi5_state_chip_css_defines_all_three_state_variants(css_source: str):
    """`.wc-state-chip--pre`, `.wc-state-chip--live`, `.wc-state-chip--post`
    each carry their own color/background/border tokens."""
    for variant in ('.wc-state-chip--pre', '.wc-state-chip--live', '.wc-state-chip--post'):
        assert variant + ' {' in css_source


def test_pi5_voice_eyebrow_tribune_register(tpl_source: str):
    """The hero eyebrow drops the literal restatement "Group standings"
    (which duplicates the H1) for a Tribune-voiced statement of fact.
    Locks the specific copy so a future commit can't quietly regress it
    to generic SaaS-utility language."""
    assert 'The pairings are drawn.' in tpl_source
    assert '<span class="wc-eyebrow">Group standings</span>' not in tpl_source


def test_pi5_lead_no_longer_restates_heading_and_drops_middot(tpl_source: str):
    """Per PRODUCT.md "every word earns its place" — the lead now describes
    advancement mechanics (the page's *purpose*), not the pre-existing
    factoid "12 groups · 48 teams · 2026 FIFA World Cup" which restated the
    H1 + chrome label. Also drops `&middot;` HTML entities (freebie F2)."""
    assert '12 groups &middot; 48 teams' not in tpl_source
    assert '&middot;' not in tpl_source
    assert 'eight best third-place finishers' in tpl_source


# ---------- F1: column-width classes ----------

def test_f1_no_inline_width_attributes_on_group_table_ths(tpl_source: str):
    """Numeric column widths moved from inline style="width:Npx" to
    .group-stat-col / .group-pts-col classes."""
    assert 'style="width:35px"' not in tpl_source
    assert 'style="width:40px"' not in tpl_source


def test_f1_group_stat_col_classes_defined_in_css(css_source: str):
    """`.group-stat-col { width: 35px }` and `.group-pts-col { width: 40px }`
    own the column widths the inline-style attrs used to carry."""
    assert '.group-table .group-stat-col { width: 35px; }' in css_source
    assert '.group-table .group-pts-col { width: 40px; }' in css_source


# ---------- helpers ----------

def _extract_rule(css: str, selector: str) -> str:
    """Return the body of the first CSS rule whose selector list starts with
    `selector` followed by ` {`. Crude but adequate for these locks."""
    needle = selector + ' {'
    idx = css.find(needle)
    assert idx != -1, f'selector {selector!r} not found in css'
    end = css.find('}', idx)
    assert end != -1, f'no closing brace for {selector!r}'
    return css[idx:end + 1]
