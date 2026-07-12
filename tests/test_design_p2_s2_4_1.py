"""P2 S2.4.1 regression locks — first iteration of the stats.html surface.

Layer A (per plan §1.3) source-pattern locks for the four Priority Issues
landed in S2.4.1. Each test pins a structural decision the impeccable
critique surfaced as P0/P1 and that S2.4.1 closed.

Iteration map:
- PI-1 (`$impeccable polish stats.html`): WCAG 2.1 AA contrast sweep.
  `--text-muted` (#8A849B, 3.59:1 on white card) replaced with
  `--text-secondary` (#5A5470, ~7.15:1) on every card-interior microcopy
  slot — KPI label/sub CSS rules + ~12 inline `style="...color:..."`
  strings across the template + JS render functions. One legitimate use
  remains (the progress-bar idle phase label sits on `--bg-muted`, not
  white) and is permitted by an explicit count cap.
- PI-2 (`$impeccable distill stats.html`): both KPI bands collapsed.
  Board's 4-tile `.wc-kpi-block` band → `.wc-stats-masthead`: one dominant
  Teko numeral (Total Pts Awarded) + Newsreader derivation prose carrying
  the four prior data points. Tiers' 5-tile band → `.wc-stats-ledger`:
  horizontal ledger strip with gold-rule top, per-cell border, dot+name+
  value. Honors the §1.5b "hero-metric ban applies to adjacency" lesson
  from S2.3.1.
- PI-3 (`$impeccable layout stats.html`): introduces `.wc-stat-card.is-lead`
  variant — gold-rule top, no body border — to break the 15-card identical
  silhouette. Marked on Top Scorers (Board), Popularity vs. Score (Field),
  Pick Distribution (Tiers). Each lead card carries a `.wc-eyebrow`
  ("The lead", "The map", "The cross-section") in its head.
- PI-4 (`$impeccable clarify stats.html`): row scan paths use `tbl()`
  (`T# · Name`) instead of bare `tb()` (`T#`). Recognition over recall
  per Nielsen #6 — Top Scorers, Carrying the Field, Dead Weight rows
  have no nearby legend, casual readers couldn't decode bare T#. tb() is
  preserved for `pbarHtml` only (where the surrounding `tierHeader` names
  the tier) and gets an aria-label so SR users still hear "Tier N · name".

Freebies (per §1.5b polish-freebie cap of 3):
- F-1: HTML-entity sweep — `&middot;` → literal middle dot.
- F-2: "Pts" → "Points" on Board card heads (editorial register).
- F-3: ★ glyph wrapped `aria-hidden="true"` plus `.visually-hidden`
  "your pick" / "your picks" SR text in row labels and combo highlights.

Pattern matches CLAUDE.md "CSS specificity for utility classes" — new
`.wc-stat-card.is-lead` is a compound selector winning over later base
rules of equal specificity, parallel to S2.3.1's surface-scoped class
migration pattern.
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = (
    ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'stats.html'
)
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'

TPL = TEMPLATE_PATH.read_text()
CSS = CSS_PATH.read_text()


# ---------------------------------------------------------------------------
# PI-1: WCAG 2.1 AA contrast sweep — `--text-muted` → `--text-secondary`.
# ---------------------------------------------------------------------------

def test_kpi_label_css_uses_text_secondary_not_text_muted():
    """`.wc-kpi-label` is no longer in the rendered DOM after PI-2 (the
    band collapsed), but the rule may still cascade to other surfaces.
    Pin the rule's color to `--text-secondary` to lock the AA fix."""
    label_rule = CSS.split('.wc-kpi-label')[1].split('}')[0]
    assert 'var(--text-secondary)' in label_rule, (
        "`.wc-kpi-label` must use --text-secondary (~7.15:1 on white). "
        "--text-muted (#8A849B) on white = 3.59:1, sub-AA at 12-13px body."
    )
    assert 'var(--text-muted)' not in label_rule, (
        "`.wc-kpi-label` should not reference --text-muted after PI-1"
    )


def test_kpi_sub_css_uses_text_secondary_not_text_muted():
    """Same fix on `.wc-kpi-sub`."""
    # The .wc-kpi-sub rule is single-line; grep for it precisely.
    sub_rules = [line for line in CSS.split('\n') if line.strip().startswith('.wc-kpi-sub ')]
    assert sub_rules, "Expected `.wc-kpi-sub` rule to still be defined"
    assert all('var(--text-secondary)' in r for r in sub_rules)
    assert all('var(--text-muted)' not in r for r in sub_rules)


def test_chart_tick_color_uses_text_secondary():
    """Chart axis ticks (`TICK_COLOR`) are 11-12px text on the bone canvas;
    --text-muted is sub-AA there too. Lock to --text-secondary."""
    assert "_tok('--text-secondary')" in TPL, (
        "Chart TICK_COLOR must read --text-secondary token (#5A5470)"
    )
    # `_tok('--text-muted')` should be gone from the chart-color block; it
    # may still appear in a stray comment, so look for the assignment shape.
    assert "TICK_COLOR = _tok('--text-muted')" not in TPL


def test_stats_template_has_at_most_one_text_muted_inline_use():
    """Sweep card-interior microcopy off --text-muted. One legitimate use
    remains: the progress-bar idle phase label sits on --bg-muted (not
    white card), and the dim register is intentional 'this is upcoming'.
    Anything beyond that one is a regression."""
    count = TPL.count('var(--text-muted)')
    assert count <= 1, (
        f"Expected at most 1 inline `var(--text-muted)` (the progress-bar "
        f"idle phase label on --bg-muted); found {count}. PI-1's contrast "
        f"sweep should have replaced the rest with --text-secondary."
    )


# ---------------------------------------------------------------------------
# PI-2: KPI bands collapsed. Board → masthead. Tiers → ledger strip.
# ---------------------------------------------------------------------------

def test_legacy_kpi_block_band_is_gone_from_stats_template():
    """The 4-tile Board KPI band and the 5-tile Tiers KPI band both
    rendered as `.wc-kpi-block` instances inside Bootstrap col grids.
    PI-2 collapses both. The template should declare zero `.wc-kpi-block`
    classes on stats.html (the CSS rule is preserved, just unused on
    this surface — Jinja explanatory comments referencing the prior
    pattern are allowed)."""
    # The JS render string `class="wc-kpi-block"` is the load-bearing
    # marker — comments using the literal name `.wc-kpi-block` are fine.
    assert 'class="wc-kpi-block"' not in TPL, (
        "stats.html should no longer render `.wc-kpi-block` after PI-2"
    )
    # Also: the JS `renderTierKPIs` function is gone from the call site.
    assert "'wc-kpi-block'" not in TPL  # JS template-string variant
    assert "`wc-kpi-block`" not in TPL  # JS template-literal variant


def test_board_renders_editorial_masthead():
    """PI-2: one dominant Teko numeral (Total Pts Awarded) + Newsreader
    derivation prose replacing the 4-tile band."""
    assert 'wc-stats-masthead' in TPL
    assert 'wc-stats-masthead-numeral' in TPL
    assert 'wc-stats-masthead-derivation' in TPL


def test_masthead_css_uses_gold_rule_top_and_newsreader():
    """The masthead is editorial register: gold-rule top, Newsreader
    serif for the derivation prose, max-width capped at 60ch per the
    DESIGN.md / impeccable typography heuristic."""
    masthead_block = CSS.split('.wc-stats-masthead {')[1].split('}')[0]
    assert '2px solid var(--gold)' in masthead_block, (
        "Masthead must lead with a 2px gold rule"
    )
    derivation_block = CSS.split('.wc-stats-masthead-derivation {')[1].split('}')[0]
    assert "Newsreader" in derivation_block, (
        "Derivation prose must use Newsreader (Newsroom Rule)"
    )
    assert 'max-width: 60ch' in derivation_block


def test_tiers_renders_ledger_strip_not_kpi_grid():
    """PI-2: 5-cell horizontal ledger replacing the 5-tile KPI grid.
    Driven by renderTierLedger() (replacing renderTierKPIs)."""
    assert 'wc-stats-ledger' in TPL
    assert 'wc-stats-ledger-row' in TPL
    assert 'tier-ledger-row' in TPL
    # The function name swap. Look for the call site (with parens) so
    # explanatory Jinja comments mentioning the old name are allowed.
    assert 'renderTierLedger();' in TPL
    assert 'renderTierKPIs();' not in TPL, (
        "Old per-tier KPI render fn must no longer be called"
    )
    assert 'function renderTierKPIs(' not in TPL, (
        "Old per-tier KPI render fn must no longer be defined"
    )


def test_ledger_css_has_per_cell_border_and_mobile_breakpoint():
    """Ledger reads as horizontal divider rule, not card grid: per-cell
    border-right at desktop, 50% reflow at mobile."""
    assert '.wc-stats-ledger-cell {' in CSS
    cell_block = CSS.split('.wc-stats-ledger-cell {')[1].split('}')[0]
    assert '1px solid var(--border)' in cell_block
    # The mobile breakpoint reflows cells 50% wide.
    ledger_section = CSS.split('/* S2.4.1 PI-2: By-Tier ledger')[1].split('/* S2.4.1 PI-3:')[0]
    assert '@media (max-width: 767px)' in ledger_section
    assert '50%' in ledger_section


# ---------------------------------------------------------------------------
# PI-3: lead-card variant breaks the identical-card silhouette.
# ---------------------------------------------------------------------------

def test_three_lead_cards_one_per_tab():
    """PI-3 marks the dominant card on each tab with `.is-lead` so the
    tab has a recognizable visual lead, breaking the 15-identical-card
    silhouette flagged by the critique. The Paths to Glory tab (added later)
    carries the same doctrine: its picker card is that tab's lead."""
    lead_count = TPL.count('wc-stat-card is-lead')
    assert lead_count == 4, (
        f"Expected exactly 4 `.wc-stat-card.is-lead` (Top Scorers / "
        f"Popularity vs. Score / Pick Distribution / Call Every Game); "
        f"found {lead_count}"
    )


def test_lead_cards_carry_eyebrow_primitive():
    """Each lead card head opens with a `.wc-eyebrow` ('The lead' /
    'The map' / 'The cross-section') so the surface gets editorial-
    masthead voice instead of dashboard-card-grid voice."""
    assert 'class="wc-eyebrow">The lead<' in TPL
    assert 'class="wc-eyebrow">The map<' in TPL
    assert 'class="wc-eyebrow">The cross-section<' in TPL


def test_is_lead_css_uses_red_rule_top_no_border():
    """The lead variant strips the body border and leads with a red-
    rule top — the editorial-register signature that distinguishes it
    from `.wc-stat-card`'s default 1px ring.

    WC Tab Unification Phase 0 — flipped from gold to `var(--wc-red)`
    to codify the new accent rank order (red → white → blue → gold
    quaternary) across the WC tab system. The lead-card mark is the
    canonical "dominant editorial register" signal across every tab;
    anchoring it on red sets the doctrine downstream phases inherit.
    """
    lead_block = CSS.split('.wc-stat-card.is-lead {')[1].split('}')[0]
    assert 'border: 0' in lead_block
    assert 'border-top: 2px solid var(--wc-red)' in lead_block


# ---------------------------------------------------------------------------
# PI-4: recognition over recall — `tbl()` on row scan paths.
# ---------------------------------------------------------------------------

def test_score_list_uses_tbl_not_tb():
    """Top Scorers row label uses `tbl(c.tier)` (T# · Name), not bare
    `tb(c.tier)`. The row has no nearby legend; the tier name must be
    inline so casual readers don't have to remember the T#→name map."""
    score_block = TPL.split('function renderScoring()')[1].split('function ')[0]
    assert '${tbl(c.tier)}' in score_block, (
        "renderScoring must use tbl() on the row label"
    )
    assert '${tb(c.tier)}' not in score_block, (
        "renderScoring should not use bare tb() — recognition over recall"
    )


def test_impact_lists_use_tbl_not_tb():
    """Carrying the Field + Dead Weight rows: same fix as Top Scorers."""
    impact_block = TPL.split('function renderImpact()')[1].split('function ')[0]
    assert impact_block.count('${tbl(c.tier)}') == 2, (
        "Both impact lists (help-list + hurt-list) must use tbl()"
    )
    assert '${tb(c.tier)}' not in impact_block


def test_tb_helper_carries_aria_label_for_sr_recognition():
    """`tb()` is preserved for `pbarHtml` only (the surrounding tierHeader
    names the tier). Add aria-label so SR users still hear the full
    'Tier N · name' even though sighted users see compact T#."""
    tb_def_line = [
        line for line in TPL.split('\n')
        if line.strip().startswith('function tb(t)')
    ]
    assert tb_def_line, "tb() helper must still be defined"
    assert 'aria-label="Tier ${t} · ${TN[t]}"' in tb_def_line[0]


# ---------------------------------------------------------------------------
# Freebies.
# ---------------------------------------------------------------------------

def test_html_entity_middot_swept():
    """F-1: stats.html uses literal middle dot, not `&middot;` entity."""
    assert '&middot;' not in TPL, (
        "Replace `&middot;` with literal ' · ' per the entity-sweep "
        "pattern established in S0.3 / S2.2.1."
    )


def test_card_heads_use_full_word_points():
    """F-2: editorial register doesn't abbreviate. 'Pts' → 'Points'."""
    assert '<span>Points Breakdown</span>' in TPL, (
        "Board card head: 'Pts Breakdown' → 'Points Breakdown'"
    )
    assert '<span>Pts Breakdown</span>' not in TPL


def test_star_glyphs_have_aria_hidden_and_sr_text():
    """F-3: ★ is decorative; SR users get a `.visually-hidden` text
    label ('your pick' / 'your picks') so the row's category-of-self
    is announced explicitly."""
    # The constant carries both pieces.
    assert "STAR_HL = '<span aria-hidden=\"true\"" in TPL
    assert 'visually-hidden">your pick</span>' in TPL
    # Combo-row highlight has the same shape.
    assert 'visually-hidden">your picks</span>' in TPL


# ---------------------------------------------------------------------------
# Rendered-HTML smoke test (Layer A flavor 2 per plan §1.3).
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from app import create_app
    from extensions import db

    app = create_app('testing')
    with app.app_context():
        db.create_all()
        # Stats route runs WorldCupTeam.query.all() unconditionally. With
        # an empty table the route still renders (kpis dict short-circuits
        # on empty country_stats), so no seed is required for the smoke
        # test — we only assert the new structural classes are present.
        yield app
        db.drop_all()


def test_stats_route_renders_new_structure(app):
    """Confirms the route emits the new shape — masthead, ledger,
    is-lead. Catches any Jinja-side break that the source-grep tests
    miss (e.g., a context-processor rename)."""
    client = app.test_client()
    # Stats is gated until kickoff (admins-only preview); render the unlocked
    # state so the structural assertions exercise the real data surface.
    with patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T12:00:00+00:00',
                                 'ENVIRONMENT': 'testing'}):
        resp = client.get('/worldcup/stats')
    assert resp.status_code == 200
    body = resp.data.decode('utf-8')
    assert 'wc-stats-masthead' in body
    assert 'wc-stats-masthead-numeral' in body
    assert 'wc-stats-ledger' in body
    assert 'tier-ledger-row' in body
    assert body.count('wc-stat-card is-lead') == 4
    # The load-bearing marker is the rendered class attribute itself —
    # JS-source comments inlined into the response body are permitted.
    assert 'class="wc-kpi-block"' not in body, (
        "Rendered HTML must not contain the legacy KPI band"
    )
