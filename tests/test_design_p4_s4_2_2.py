"""P4 S4.2.2 regression locks — picks.html + _pick_row.html second iteration.

Layer A (per plan §1.3) source-pattern locks for the four Priority Issues
and two freebies that landed in S4.2.2. Iteration inherits seven routed
items from S4.2.1 §0.4; per §1.5b atomic-edit rule PI-1 (distill — tier
vocabulary collapse) and the routed mobile tap-through (originally tagged
$impeccable adapt) close in one edit (the mobile readonly card becomes an
<a> + the tier-badge swaps for wc-tier-dot + Teko tier name) and count as
ONE Priority Issue.

Iteration map:

- PI-1 (`$impeccable distill` + `$impeccable adapt`, atomic). The mobile
  readonly `.player-pick-card` was a non-interactive `<div>` carrying a
  `.tier-badge tier-badge-N` chip (one of three competing tier primitives
  in the picks surface — alongside `.wc-tier-dot` on desktop _pick_row.html
  and `.wc-multiplier-chip` for the multiplier). Casey (mobile, two-thumb)
  got a worse drill-down than the desktop user on the same data + had to
  re-learn the tier visual on each shell. Both close in one rewrite of
  the mobile readonly block: card becomes an `<a href="…team_detail">`,
  the tier badge swaps to a `.wc-tier-dot` + `.wc-eyebrow` tier name on
  a stacked `.pick-tier-line` row above the team line. `.tier-badge`
  survives only in the sidebar pick-summary JS (the demoted "one place,
  one job" home — locked in the test below). `.wc-multiplier-chip` is
  not used to encode tier on the mobile readonly card anymore.

- PI-2 (`$impeccable typeset`). Four inline `style="font-size:N.Nrem"`
  declarations on `.wc-numeral` spans (1.1 / 1.2 / 1.3 / 1.4rem) and one
  on the mobile readonly `.tier-badge` bypassed the DESIGN.md fixed type
  scale. Extracted to `.wc-numeral--xl/--lg/--md/--sm` modifier classes;
  inline declarations removed (the `.tier-badge` one is closed by PI-1's
  vocabulary collapse). Only the empty-state decorative `bi-x-circle`
  retains an inline `font-size` (out of routed PI scope — not a numeral).

- PI-3 (`$impeccable harden`). Edit-form heading outline pre-S4.2.2 was
  H1 (hero) → H3 ×5 (tier-card-header) → H4 (sidebar pick-summary) — no
  H2, tripping axe heading-order. Promoted `.tier-card-header h3` → H2
  via new `.tier-card-heading` class and `.pick-summary h4` → H2 via new
  `.pick-summary-heading` class. Each tier card is a logical section
  under the page H1; sidebar is a parallel section. Visual preserved by
  the new class selectors.

- PI-4 (`$impeccable polish`). `.pick-summary` rendered with
  `border-top: 3px solid var(--game-primary)` (= raw `rgb(0, 40, 104)`
  on the bone canvas). The impeccable absolute ban targets >1px colored
  side stripes on cards; a 3px top stripe lives in the same family.
  Dropped the stripe entirely — the Teko eyebrow + H2 carry hierarchy.

- F1 (markup-as-icon glyph). `.wc-team-card.selected::after` used
  `content: '\\2713'` (Unicode checkmark). Swapped to CSS-mask SVG so
  the affordance is a real check icon at a fixed 14px square, color-
  controlled via `background-color` — no font-cascade dependency.

- F2 (`--wc-white` token hygiene). `.wc-multiplier-chip { color:
  var(--wc-white) }` referenced a token DESIGN.md `colors:` doesn't
  define. Lifted to `var(--text-on-dark)` matching the S4.2.1 PI-4 lift
  on `.tier-badge`. No visual delta (both resolve to pressroom-bone).
"""
import re
from pathlib import Path

REPO = Path(__file__).parent.parent
CSS = REPO / 'static' / 'css' / 'style.css'
PICKS = REPO / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'picks.html'
PICK_ROW = REPO / 'games' / 'worldcup' / 'templates' / 'worldcup' / '_pick_row.html'


# ---------- PI-1: tier vocabulary collapse + mobile tap-through ----------

def test_pi1_mobile_player_pick_card_is_anchor_with_team_detail_href():
    """Mobile readonly card is now <a href="…team_detail…"> (PI-3 routed item)."""
    src = PICKS.read_text()
    # The block lives inside player-picks-mobile; check the new <a class="player-pick-card">.
    assert 'class="player-pick-card"' in src, "player-pick-card class still rendered"
    assert "url_for('worldcup.team_detail', team_id=pick.team_id)" in src, \
        "Mobile readonly card must link to team_detail"
    # The literal anchor form: <a href="…" class="player-pick-card">
    assert '<a href="{{ url_for(\'worldcup.team_detail\', team_id=pick.team_id) }}" class="player-pick-card">' in src


def test_pi1_mobile_card_uses_wc_tier_dot_not_tier_badge():
    """Mobile readonly card no longer renders .tier-badge; tier-dot + Teko name is canonical."""
    src = PICKS.read_text()
    # The mobile readonly block must not contain a tier-badge inside player-pick-card.
    # Sidebar pick-summary JS (summaryList) still uses .tier-badge — that's the demoted home.
    # Strip the script block from the search so we're only checking the HTML markup.
    markup_only = src.split('{% block scripts %}')[0]
    assert 'tier-badge-' not in markup_only, \
        "tier-badge-* must not appear in picks.html template body; only in summaryList JS"
    # Tier-dot is the canonical mobile readonly tier visual.
    assert 'wc-tier-dot-{{ pick.tier }}' in src, "wc-tier-dot must encode tier on mobile readonly card"


def test_pi1_tier_badge_survives_only_in_summaryList_js():
    """.tier-badge is now demoted to one place: the sidebar pick-summary JS builder."""
    src = PICKS.read_text()
    # Count tier-badge occurrences in the JS block specifically
    script_block = src.split('{% block scripts %}')[-1] if '{% block scripts %}' in src else ''
    assert 'tier-badge-' in script_block, \
        "summaryList JS must still build .tier-badge li chips (the one canonical home)"


def test_pi1_pick_row_desktop_keeps_wc_tier_dot_canonical():
    """_pick_row.html (desktop readonly table cell) keeps wc-tier-dot + tier name."""
    src = PICK_ROW.read_text()
    assert 'wc-tier-dot wc-tier-dot-{{ pick.tier }}' in src
    assert 'tiers[pick.tier].name' in src


# ---------- PI-2: inline font-size extraction ----------

def test_pi2_no_inline_font_size_on_wc_numeral_in_picks():
    """All .wc-numeral spans in picks.html now use modifier classes, not inline font-size."""
    src = PICKS.read_text()
    # The decorative bi-x-circle empty-state icon retains an inline font-size — that's
    # out of routed scope (not a numeral). Every numeral must be modifier-driven.
    offenders = []
    for line_no, line in enumerate(src.splitlines(), start=1):
        if 'wc-numeral' in line and 'style="font-size' in line:
            offenders.append((line_no, line.strip()[:120]))
    assert not offenders, f"Inline font-size on .wc-numeral spans remain: {offenders}"


def test_pi2_numeral_modifier_classes_defined_in_css():
    """The four numeral modifier classes must be declared in style.css."""
    css = CSS.read_text()
    assert '.wc-numeral--xl' in css
    assert '.wc-numeral--lg' in css
    assert '.wc-numeral--md' in css
    assert '.wc-numeral--sm' in css


def test_pi2_modifier_classes_carry_expected_rem_values():
    """xl=1.4rem, lg=1.3rem, md=1.2rem, sm=1.1rem so each is a discrete scale
    step. PR #15 CR R5-A — modifiers are scoped as compound utilities
    (`.wc-numeral.wc-numeral--*`) to hold (0,0,2,0) specificity against
    composed descendant rules (matches CLAUDE.md utility-scope convention)."""
    css = CSS.read_text()
    assert '.wc-numeral.wc-numeral--xl { font-size: 1.4rem; }' in css
    assert '.wc-numeral.wc-numeral--lg { font-size: 1.3rem; }' in css
    assert '.wc-numeral.wc-numeral--md { font-size: 1.2rem; }' in css
    assert '.wc-numeral.wc-numeral--sm { font-size: 1.1rem; }' in css


def test_pi2_each_modifier_is_consumed_at_least_once_in_picks():
    """Confirms the templates actually use the new scale (no dead CSS)."""
    src = PICKS.read_text()
    assert 'wc-numeral--xl' in src, "xl modifier must be consumed (Tiebreak total)"
    assert 'wc-numeral--lg' in src, "lg modifier must be consumed (desktop total)"
    assert 'wc-numeral--md' in src, "md modifier must be consumed (mobile total)"
    assert 'wc-numeral--sm' in src, "sm modifier must be consumed (sidebar count)"


# ---------- PI-3: heading outline ----------

def test_pi3_tier_card_header_uses_h2_not_h3():
    """Each of the 5 tier-card headers is an H2 (was H3 pre-S4.2.2)."""
    src = PICKS.read_text()
    assert '<h2 class="tier-card-heading">' in src, \
        "Tier card heading must be H2 with .tier-card-heading class"
    # The old H3 with d-flex inline classes must not return.
    assert '<h3 class="d-flex align-items-center gap-2 mb-0">' not in src


def test_pi3_pick_summary_uses_h2_not_h4():
    """Sidebar pick-summary heading is an H2 (was H4 pre-S4.2.2)."""
    src = PICKS.read_text()
    assert '<h2 class="pick-summary-heading">' in src, \
        "Sidebar pick-summary heading must be H2 with .pick-summary-heading class"
    # Old H4 form must not return.
    assert '<h4 class="mb-3">' not in src


def test_pi3_css_targets_tier_card_heading_class_not_h3():
    """The styling that was scoped to .tier-card-header h3 now keys off .tier-card-heading."""
    css = CSS.read_text()
    assert '.tier-card-header .tier-card-heading' in css, \
        "CSS must style .tier-card-heading via class, not element type"
    # The old element-type-keyed rule is gone.
    assert '.tier-card-header h3 {' not in css


def test_pi3_css_targets_pick_summary_heading_class_not_h4():
    """The styling that was scoped to .pick-summary h4 now keys off .pick-summary-heading."""
    css = CSS.read_text()
    assert '.pick-summary .pick-summary-heading' in css
    assert '.pick-summary h4 {' not in css


# ---------- PI-4: .pick-summary top-stripe ----------

def test_pi4_pick_summary_no_top_stripe():
    """`.pick-summary` no longer declares a border-top stripe (side-stripe-adjacent ban)."""
    css = CSS.read_text()
    # Find the .pick-summary block and assert no border-top declaration inside.
    start = css.find('.pick-summary {')
    assert start >= 0, ".pick-summary rule still exists"
    block_end = css.find('}', start)
    block = css[start:block_end]
    assert 'border-top:' not in block, \
        ".pick-summary must not declare border-top (was '3px solid var(--game-primary)' pre-S4.2.2)"


def test_pi4_pick_summary_keeps_full_border():
    """`.pick-summary` keeps the full perimeter border (border: 1px solid var(--border))."""
    css = CSS.read_text()
    start = css.find('.pick-summary {')
    block_end = css.find('}', start)
    block = css[start:block_end]
    assert 'border: 1px solid var(--border)' in block


# ---------- F1: \2713 markup-as-icon ----------

def test_f1_selected_after_no_unicode_checkmark_content():
    """`.wc-team-card.selected::after` no longer uses `content: '\\2713'` (markup-as-icon)."""
    css = CSS.read_text()
    # Find the selected::after block.
    selector = '.wc-team-card.selected::after {'
    start = css.find(selector)
    assert start >= 0
    block_end = css.find('}', start)
    block = css[start:block_end]
    assert "content: '\\2713'" not in block
    assert "content: '✓'" not in block
    assert "content: '';" in block or 'content: "";' in block, \
        "Empty content + SVG mask is the canonical replacement"


def test_f1_selected_after_uses_svg_mask():
    """`.wc-team-card.selected::after` uses a CSS-mask SVG (real icon, not a glyph)."""
    css = CSS.read_text()
    selector = '.wc-team-card.selected::after {'
    start = css.find(selector)
    block_end = css.find('}', start)
    block = css[start:block_end]
    # The SVG path is the Bootstrap Icons bi-check2 shape.
    assert "data:image/svg+xml" in block
    assert "mask:" in block or "-webkit-mask:" in block
    assert "background-color:" in block, "Color must be controllable via background-color"


# ---------- F2: --wc-white token hygiene ----------

def test_f2_multiplier_chip_paints_light_substrate_only():
    """`.wc-multiplier-chip` paints on a single light substrate, and never
    references the undefined `var(--wc-white)`. PR #15 CR R7-D originally
    locked `color: var(--text-on-dark)` on the base when the chip ALWAYS
    sat on `.card.wc-card`. WC Tab Unification P2 split that into a light
    base (`color: var(--text-primary)` for player_detail.html post-P2) and
    a `.card.wc-card .wc-multiplier-chip` carve-out preserving
    `color: var(--text-on-dark)` for picks.html ROSTER. P3 then migrated
    picks.html off `.card.wc-card`, retiring the dark carve-out in lockstep
    — the chip now consumes only the light base across both player_detail
    and picks.html.

    Anchored on the `color` property via negative-lookbehind regex so a
    future `background-color: var(--wc-white)` or `border-color: var(--wc-
    white)` can't silently slip through. The dark carve-out's removal is
    asserted in P2 PI-7 style so a regression that re-introduces it is
    caught loudly.
    """
    css = CSS.read_text()

    # (1) Base rule paints the light substrate.
    start = css.find('.wc-multiplier-chip {')
    block_end = css.find('}', start)
    base_block = css[start:block_end]
    assert re.search(r'(?<!-)color:\s*var\(--text-primary\)', base_block), (
        '.wc-multiplier-chip base must paint `color: var(--text-primary)` '
        'on light substrate (P2 flip, preserved through P3).'
    )

    # (2) `.card.wc-card .wc-multiplier-chip` carve-out retired in P3.
    assert '.card.wc-card .wc-multiplier-chip {' not in css, (
        '`.card.wc-card .wc-multiplier-chip` carve-out was retired in P3 '
        '(its sole consumer, picks.html ROSTER, migrated off `.card.wc-card`). '
        'A regression here means the cleanup was undone.'
    )

    # (3) Original CR intent: the base rule does not reference the undefined token.
    assert not re.search(r'(?<!-)color:\s*var\(--wc-white\)', base_block), (
        '.wc-multiplier-chip base must not reference the undefined '
        'var(--wc-white) token (PR #15 CR R7-D).'
    )


# ---------- PI-A1: contrast scope lock (folded in-iteration per §1.7) ----------
#
# Layer C critique caught two contrast P1s: (a) F2 above made the chip
# bone-on-white inside .tier-card-heading (white tier-card body) at
# ~1.04:1 — an in-iteration regression; (b) `.wc-numeral` inherited
# Bootstrap body color on the navy `.card.wc-card` substrate, making the
# readonly card-header Total + tiebreaker numeral near-black on near-
# black. Originally closed by two scoped CSS rules; the dark-substrate
# half (`.card.wc-card .wc-numeral`) retired in WC tab unification P5
# along with the entire `.card.wc-card` substrate. The light-substrate
# half (`.tier-card-heading .wc-multiplier-chip`) below stays.


def test_pia1_multiplier_chip_re_tinted_on_tier_card_heading():
    """`.tier-card-heading .wc-multiplier-chip` overrides the dark default
    for the white tier-card body. PR #15 CR R6-G — uses `var(--text-primary)`
    (the platform text-on-light alias declared at style.css:23); the original
    `var(--text-ink)` was an undefined token that rendered by cascade
    fallback. Matches the sibling chip retint pattern in PI-2 (R3-E /
    R5-H lock at `.card.wc-card:not(.player-picks-desktop) .table-worldcup
    .wc-multiplier-chip`)."""
    css = CSS.read_text()
    idx = css.find('.tier-card-heading .wc-multiplier-chip {')
    assert idx >= 0, "Light-surface chip override must exist"
    block_end = css.find('}', idx)
    block = css[idx:block_end]
    # PR #15 CR R7-D — anchor `color` on the property, and anchor the
    # Council Purple tint on the `background` property (not `color` or
    # `border-color`, both of which also use rgba(58, 29, 114, ...) values
    # in this rule).
    assert re.search(r'(?<!-)color:\s*var\(--text-primary\)', block), \
        '.tier-card-heading .wc-multiplier-chip must set color: var(--text-primary)'
    assert 'var(--text-ink)' not in block, \
        '.tier-card-heading .wc-multiplier-chip must not reference the undefined --text-ink token'
    assert re.search(r'background:\s*rgba\(58,\s*29,\s*114', block), \
        "Council Purple tint must drive the background (S4.2.1 PI-4 idiom)"
