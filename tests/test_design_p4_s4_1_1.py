"""P4 S4.1.1 regression locks — platform home pre-state + logged-out surfaces.

Layer A (per plan §1.3) source-pattern locks for the Priority Issues landed
in S4.1.1. The surface covers two state partials (`_home_out.html`,
`_home_pre.html`) plus the supporting `_countdown_card.html` partial they
compose into.

Iteration map:

- PI-1 (`$impeccable layout` — registry grid reshape, closes two routed
  items from S3.3.1 as one atomic edit per §1.5b): the `_home_out.html`
  `col-md-4` 3-up grid (1 logged-out + 2 coming-soon) rendered as three
  440×278 identical rectangles at desktop, triggering DESIGN.md §6 Don't #7
  ("Don't introduce repeating identical card grids") and PRODUCT.md "Generic
  SaaS Dashboards" anti-reference. The heading outline jumped page `<h1>` →
  card `<h3>` ×3 with no `<h2>` between (axe heading-order moderate
  violation, routed from S3.3.1 §0.4). Fix: wrapped the registry in a
  `<section>` with `<h2 id="out-registry-head">Pools in Session</h2>`, then
  composed a 1× featured card (CCC purple + gold radials over the home-shell
  backdrop) + 1× stacked coming-soon rail of horizontal strips. The featured
  card and the strip silhouettes differ structurally, so the grid no longer
  reads as identical rectangles. At desktop ≥992px the grid uses a 7fr+5fr
  template; at <992 it collapses to single column. The featured card
  preserves the logged-out auth-flow link (`auth.register?next=blueprint_join`).

  Distill 2026-06-08 (`$impeccable distill`): the featured `.out-featured`
  card was folded UP into the `.join` conversion card. The pre-merge page
  carried two co-equal gold CTAs ("Join the Club" + "Sign Up to Play") that
  both routed to `auth.register` and told the World Cup story twice, leaving a
  first-time visitor unsure which to click. The merged `.join` card is now the
  single primary CTA (registry-driven identity + `next=blueprint_join`
  routing); the `.out-registry` section keeps its `<h2 id="out-registry-head">`
  + `aria-labelledby` but carries only the coming-soon rail (a quiet,
  button-less breadth signal). The `.out-featured*` locks below were retired
  with the card and replaced by `.join`-scoped equivalents.

- PI-2 (`$impeccable distill` — countdown hero-metric adjacency collapse):
  the `_countdown_card.html` 4-cell `Days · Hours · Min · Sec` strip read
  as four equal-weight numerals in a row (each 2.8rem / 3.6rem at md+
  Teko 700, identical units), triggering DESIGN.md §6 Don't #8 (hero-metric
  template) + the S2.3.1 calibration the iterative model has locked: "the
  hero-metric-template ban applies to *adjacency*, not just presence. Four
  equal-weight numerals in a row reads as the SaaS cliché DESIGN.md §6 bans
  even when each tile carries a distinct, justified data point." Fix:
  collapsed to one dominant Days numeral (`4.5rem` mobile / `6rem` desktop)
  + a Newsreader-italic derivation prose line that carries the live tick
  (`01h · 43m · 46s ticking`). The `data-cd-days/hours/mins/secs` attributes
  are preserved so `static/js/countdown.js` keeps writing into them without
  any JS change.

- PI-3 (`$impeccable adapt` — countdown `.decree-links` tap-target floor):
  the bottom-row "House Rules" + "Scoring" links inside the countdown card
  measured 93×20 and 67×20 at the 375 viewport, both failing the PRODUCT.md
  "Mobile-First Requirements" 44×44 tap-target floor (height fails by 24px).
  Every pre-state mobile user sees these links. Fix: `min-height: 44px;
  min-width: 44px; padding: 0.65rem 0.75rem;` on `.decree-links a` (the
  S2.1.2-locked recipe), plus the canonical `:focus-visible` gold-light
  ring for keyboard users.

Freebies batched at end-of-iteration:
- F1 (inherited from S3.3.1 §0.4 — `_home_out.html:68` 44×15 tap-target):
  the "Sign in" link in `.join-alt` ("Already sworn in? Sign in") measured
  44×15 at the 375 viewport — height fails the 44×44 floor by 29px. Fix:
  inline-flex with `min-height: 44px; padding: 0.6rem 0.5rem; margin:
  -0.6rem -0.5rem;` (the same negative-margin trick S2.1.2 locked for
  `.sec-head .more`). Negative margins neutralize the visual offset so the
  link still reads inline inside the running text. Adds `:focus-visible`
  gold ring.

Routed forward per §0.4 (locked in §9 rollup of the plan):

- [S4.1.1 in-surface] pre-state desktop 2-column layout at md+ — the
  `.home-col { max-width: 640px }` floors the pre-state to a phone-shaped
  column at every viewport. A 2-col reshape at md+ would put the dossier +
  countdown on the left (7fr) and opening matches + commish + dispatches on
  the right (5fr). Substantial scope (affects 3 dossier variants + opening
  matches placement + commish/dispatches positioning + risks live-state
  regression since `.home-shell` is shared) — routed to S4.1.2.
- [S4.1.1 in-surface] `.ballot-card` whole-area-link semantic — the entire
  card is wrapped in `<a href="...?edit=1">`, swallowing the flags ribbon
  + "Edit any time before the whistle." copy into a single concatenated
  link for screen readers, and making the flag emoji clickable to "edit
  pick" rather than "show team detail". Restructure into `<section>` + an
  explicit inline `Edit roster ›` action. Routed to S4.1.2.
- [S4.1.1 in-surface] 3 different gold-bordered card recipes within one
  viewport (.decree, .cta-card--seal, .match-card) — needs a DESIGN.md §5
  vocabulary addition (Ceremonial vs Informational card register) before
  consolidation. Routed to S4.1.2.
- [S4.1.1 in-surface] out value-prop strip — 3 identical icon-text rows
  (.out-prop ×3) read as within-strip identical-grid. P3 differentiation
  candidate; routed to S4.1.2.
- [S4.1.1 cross-phase] flash banner competing with home-shell masthead —
  the "Logged in successfully!" alert lives in `base.html` chrome and
  affects every authenticated state's home + game pages. P3; routed to
  S6.1 cross-phase polish.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()
HOME_OUT = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_home_out.html').read_text()
COUNTDOWN = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_countdown_card.html').read_text()


def _css_block(selector: str) -> str:
    """Return concatenated CSS declarations whose opening selector list
    contains the given selector. Useful for asserting on `:focus-visible`
    rules or media-query variants alongside the base rule."""
    blocks = re.findall(
        rf'{re.escape(selector)}[^{{]*\{{[^}}]*\}}',
        CSS,
    )
    return '\n'.join(blocks)


# ---------------------------------------------------------------------------
# PI-1: `_home_out.html` registry grid reshape (closes 2 routed items as one
# atomic edit per §1.5b atomic-edit rule).
# ---------------------------------------------------------------------------

def test_pi1_home_out_no_longer_uses_col_md_4_registry_grid():
    """The pre-S4.1.1 registry markup wrapped each game card in
    `<div class="col-sm-6 col-md-4">` inside `<div class="row g-4
    justify-content-center">`. That 3-up `col-md-4` grid is the identical-
    card-grid anti-pattern hit. After PI-1 the registry is restructured into
    a `<section>` + 7fr/5fr grid; the `col-md-4` registry containers must
    not return."""
    assert 'col-md-4' not in HOME_OUT, (
        "PI-1: `_home_out.html` re-introduced the `col-md-4` 3-up registry "
        "grid. The composition reshape locks must keep the featured + "
        "coming-soon-rail layout, not regress to identical Bootstrap cols."
    )
    assert "g-4 justify-content-center" not in HOME_OUT, (
        "PI-1: the original `row g-4 justify-content-center` registry grid "
        "row class returned to `_home_out.html`. Use `.out-registry-grid` "
        "(the new 7fr/5fr CSS grid) instead."
    )


def test_pi1_home_out_carries_section_h2_heading():
    """The S3.3.1-routed missing-`<h2>` finding: the page jumped page `<h1>`
    → card `<h3>` ×3 with no intermediate heading. After PI-1 the registry
    section opens with an `<h2 id="out-registry-head">` so the screen-reader
    outline has a parent heading for the featured card to hang off."""
    assert 'id="out-registry-head"' in HOME_OUT, (
        "PI-1: `_home_out.html` must declare `id=\"out-registry-head\"` on "
        "the `<h2>` so the `<section aria-labelledby=...>` wrapper can "
        "name the region for assistive tech."
    )
    pattern = re.compile(
        r'<h2[^>]*id="out-registry-head"[^>]*>.*?</h2>',
        re.DOTALL,
    )
    assert pattern.search(HOME_OUT), (
        "PI-1: `<h2 id=\"out-registry-head\">` opening + closing tags "
        "missing from `_home_out.html`. Without the H2, axe still flags "
        "heading-order (page H1 → card H3)."
    )
    # Section wrapper carries the aria-labelledby tie-back.
    assert 'aria-labelledby="out-registry-head"' in HOME_OUT, (
        "PI-1: `<section>` wrapper must reference the h2's id via "
        "`aria-labelledby=\"out-registry-head\"` so the section is named "
        "for AT users."
    )


def test_pi1_home_out_merged_join_card_routes_through_auth_register_next():
    """Distill 2026-06-08: the featured pool folded into the `.join` conversion
    card. Its single gold CTA must still route through `auth.register` with
    `next=blueprint_join` so a new user lands on the join page after sign-up,
    and the card must be driven by the registry `available_games` loop so the
    pool identity + join route generalize when a second game opens."""
    assert '{% for game in available_games %}' in HOME_OUT, (
        "PI-1 (distill): the conversion card must loop over `available_games` "
        "so the open pool's identity + join route come from the registry."
    )
    pattern = re.compile(
        r'class="join-cta"\s+href="\{\{\s*url_for\(\'auth\.register\','
        r'\s*next=url_for\(game\.blueprint_join\)\)\s*\}\}"'
    )
    assert pattern.search(HOME_OUT), (
        "PI-1 (distill): the `.join-cta` must route through "
        "`auth.register?next=blueprint_join` to preserve the logged-out "
        "conversion path. Direct `blueprint_index` would bounce the user "
        "back to login."
    )


def test_pi1_home_out_renders_coming_soon_rail_with_aria_label():
    """The coming-soon rail wraps the upcoming games in a semantic `<aside>`
    with `aria-label`. The `out-coming-strip` rows differentiate the
    silhouette from the featured card (different shape + structure)."""
    assert 'out-coming-rail' in HOME_OUT, (
        "PI-1: `.out-coming-rail` wrapper missing from `_home_out.html`. "
        "Without it, the coming-soon games would still render as identical "
        "cards instead of differentiated horizontal strips."
    )
    assert '<aside class="out-coming-rail"' in HOME_OUT, (
        "PI-1: the rail should be a semantic `<aside>` so AT users hear it "
        "as a complementary region, not just another grid item."
    )
    assert 'aria-label="Pools coming soon"' in HOME_OUT, (
        "PI-1: `<aside>` must carry `aria-label=\"Pools coming soon\"` so "
        "the section announces itself to screen readers."
    )
    assert 'out-coming-strip' in HOME_OUT, (
        "PI-1: `.out-coming-strip` markup missing — the rail must render "
        "horizontal strips, not stacked cards."
    )


def test_pi1_home_out_single_primary_cta():
    """Distill 2026-06-08 core lock: the logged-out page must carry exactly one
    gold primary CTA. The pre-merge page had two (`.join-cta` "Join the Club"
    inside `.join` + `.out-featured-cta` "Sign Up to Play" inside the featured
    card), both routing to `auth.register`, which left a first-time visitor
    unsure which to click. The featured card + its CTA must not return."""
    assert HOME_OUT.count('class="join-cta"') == 1, (
        "Distill: `_home_out.html` must render exactly one `.join-cta` — the "
        "single primary conversion CTA."
    )
    assert 'class="out-featured"' not in HOME_OUT, (
        "Distill: the `.out-featured` featured card (the retired second gold "
        "CTA) must not return to `_home_out.html`."
    )
    assert 'Sign Up to Play' not in HOME_OUT, (
        "Distill: the second CTA label 'Sign Up to Play' must not return — the "
        "single conversion CTA is 'Join the Club'."
    )


def test_pi1_home_out_join_title_is_h2_pool_name():
    """The merged conversion card's pool name is its `<h2 class="join-title">`
    (the old "Join the competition." word-stamp retired). This gives AT users a
    navigable heading for the page's primary content and keeps the H1 → H2
    outline clean without the featured card's old H3."""
    assert re.search(r'<h2[^>]*class="join-title"', HOME_OUT), (
        "Distill: `.join-title` must be an `<h2>` carrying the pool name so "
        "the conversion card has a navigable heading and the outline stays "
        "H1 → H2 (no skipped level)."
    )


def test_pi1_css_defines_out_registry_grid_centered_single_column():
    """The S4.1.1 PI-1 7fr+5fr-desktop split was revised in
    design/home-out-polish (2026-05-13). First-impression critique by
    the product owner flagged the featured card as "crammed into a
    corner" at desktop: the 7fr column floated left within the home-
    shell container with no balancing centering moment. The fix stacks
    the featured card centered above the coming-soon rail at every
    viewport, capped with `max-width` so the centered column doesn't
    stretch edge-to-edge. The identical-card-grid silhouette stays
    broken because the featured card and the rail strips remain
    structurally different shapes (hero card vs horizontal strips)."""
    grid_block = _css_block('.home-shell .out-registry-grid')
    assert 'grid-template-columns: 1fr;' in grid_block, (
        "PI-1 (revised): `.out-registry-grid` must default to `1fr` so "
        "the featured card stacks above the coming-soon rail."
    )
    assert 'max-width:' in grid_block, (
        "PI-1 (revised): `.out-registry-grid` must cap its width with "
        "`max-width:` so the centered single-column layout doesn't "
        "stretch the featured card edge-to-edge inside the container."
    )
    assert 'margin: 0 auto' in grid_block or 'margin-inline: auto' in grid_block, (
        "PI-1 (revised): `.out-registry-grid` must center itself "
        "(`margin: 0 auto`) so the featured card and rail land in the "
        "visual middle of the container, not against its left edge."
    )
    # The pre-revision split must NOT come back; if a future iteration
    # wants to re-introduce side-by-side, revise this lock together with
    # the new design rationale.
    assert 'minmax(0, 7fr) minmax(0, 5fr)' not in grid_block, (
        "PI-1 (revised): the legacy 7fr+5fr split must not return. The "
        "stacked-centered layout is the locked design after the "
        "design/home-out-polish revision."
    )


def test_pi1_css_defines_join_card_purple_gradient_atmosphere():
    """Distill 2026-06-08: the merged conversion card keeps the CCC purple
    gradient + the canonical 30%-gold informational border. It earns focus as
    the page's single gold CTA, not via a louder edge — the retired featured
    card's 50% gold border must not migrate over. (Replaces the
    `.out-featured-inner` atmosphere lock.)"""
    block = _css_block('.home-shell .join')
    assert 'var(--purple-800)' in block and 'var(--purple-900)' in block, (
        "Distill: `.join` must layer the CCC purple gradient "
        "(`var(--purple-800)` → `var(--purple-900)`)."
    )
    assert 'rgba(201,162,39,.3)' in block, (
        "Distill: `.join` must keep the 30%-gold informational border; the "
        "retired featured card's louder 50% edge must not migrate onto the "
        "now-focal conversion card."
    )


def test_pi1_css_defines_focus_visible_on_join_cta():
    """The page's single primary CTA needs a keyboard focus ring (canonical
    CCC 2px gold-light outline) so tabbing users see the same affordance as
    mouse users. Replaces the lock the retired `.out-featured:focus-visible`
    carried."""
    block = _css_block('.home-shell .join-cta:focus-visible')
    assert 'outline: 2px solid var(--gold-light)' in block, (
        "Distill: `.join-cta:focus-visible` missing the 2px gold-light "
        "outline — keyboard users lose the affordance mouse hover gives."
    )


# ---------------------------------------------------------------------------
# PI-2: countdown hero-metric adjacency collapse.
# ---------------------------------------------------------------------------

def test_pi2_countdown_no_longer_uses_4_cell_decree_days_strip():
    """The pre-S4.1.1 markup rendered four `<div class="d-cell">` numerals
    in a row inside `<div class="decree-days">`. After PI-2 the structure
    is a single `.decree-hero` block + a `.decree-derivation` prose line.
    The old class names must not return."""
    assert '<div class="decree-days">' not in COUNTDOWN, (
        "PI-2: `_countdown_card.html` re-introduced `<div "
        "class=\"decree-days\">` — that's the 4-cell hero-metric strip the "
        "iteration retired. Use `.decree-hero` + `.decree-derivation` "
        "instead."
    )
    assert 'class="d-cell"' not in COUNTDOWN, (
        "PI-2: `.d-cell` markup back in `_countdown_card.html`. The cells "
        "are what carry the 4-equal-weight-numeral pattern."
    )
    assert 'class="d-sep"' not in COUNTDOWN, (
        "PI-2: `.d-sep` colon separator back in `_countdown_card.html`. "
        "It's only there to space the 4 cells; if the cells are gone, the "
        "separator must go with them."
    )


def test_pi2_countdown_renders_hero_block():
    """The hero block carries one dominant Days numeral + a unit label
    that anchors it ("Days to the Whistle"). The number itself preserves
    `data-cd-days` so `static/js/countdown.js` keeps writing into it."""
    assert 'decree-hero-num' in COUNTDOWN, (
        "PI-2: `.decree-hero-num` element missing — the iteration's central "
        "fix was collapsing 4 numerals to one dominant numeral."
    )
    # S6.1.5 PI-1 — the .decree-hero-num element gained `aria-hidden="true"`
    # alongside `data-cd-days` (the parent .decree-hero now carries the
    # accessible name as a `role="text"` aria-label). The previous strict
    # regex required `data-cd-days` to immediately follow `class=` with only
    # whitespace; the order-agnostic form below preserves the intent (the
    # attribute appears on the .decree-hero-num element) without coupling to
    # attribute ordering.
    pattern = re.compile(
        r'<div\b[^>]*\bclass="[^"]*\bdecree-hero-num\b[^"]*"[^>]*\bdata-cd-days\b'
        r'|<div\b[^>]*\bdata-cd-days\b[^>]*\bclass="[^"]*\bdecree-hero-num\b'
    )
    assert pattern.search(COUNTDOWN), (
        "PI-2: `.decree-hero-num` must carry `data-cd-days` so "
        "`static/js/countdown.js` can write the live days value. Losing "
        "the attr breaks the live tick silently."
    )
    assert 'decree-hero-unit' in COUNTDOWN, (
        "PI-2: `.decree-hero-unit` element missing — the unit label "
        "(Newsreader-italic prose 'Days to the Whistle') is what makes "
        "the hero numeral comprehensible without four side-by-side units."
    )


def test_pi2_countdown_renders_derivation_with_live_tick_attrs_preserved():
    """The Newsreader-italic derivation line carries the live HH/MM/SS
    tick, but as supporting prose rather than four equal-weight numerals.
    The `data-cd-hours/mins/secs` attributes must be preserved so the JS
    timer keeps updating them."""
    assert 'decree-derivation' in COUNTDOWN, (
        "PI-2: `.decree-derivation` missing — the prose line that demotes "
        "hours/min/sec from hero-equals to supporting derivation."
    )
    # Every tick attribute must still be present in the markup.
    for attr in ('data-cd-hours', 'data-cd-mins', 'data-cd-secs'):
        assert attr in COUNTDOWN, (
            f"PI-2: `{attr}` missing from `_countdown_card.html`. "
            f"`static/js/countdown.js` reads this attribute every second; "
            f"removing it breaks the live tick silently (the JS warns to "
            f"console then returns)."
        )


def test_pi2_css_defines_decree_hero_at_dominant_size():
    """The hero numeral must be visibly larger than supporting type. At
    mobile, ≥4rem Teko 700 is the minimum to read as the page's primary
    numeral. At desktop (≥768px), bumped via a media-query override."""
    block = _css_block('.home-shell .decree-hero-num')
    assert 'font-size: 4.5rem' in block, (
        "PI-2: `.decree-hero-num` mobile font-size must be ≥4rem so the "
        "number reads as the page's primary numeral. Anything smaller "
        "puts it in the same weight class as the derivation line and the "
        "hero-metric ban returns."
    )
    assert 'font-weight: 700' in block, (
        "PI-2: `.decree-hero-num` must be Teko 700 for masthead weight."
    )
    # Tabular-nums prevents jitter when the value ticks (e.g. 30→29).
    assert 'tabular-nums' in block, (
        "PI-2: `.decree-hero-num` should use `font-variant-numeric: "
        "tabular-nums` so the number doesn't reflow when it ticks down."
    )


def test_pi2_css_decree_hero_unit_uses_gold_light_eyebrow_register():
    """The unit label below the hero uses the CCC eyebrow register: Teko
    500, uppercase, letter-spaced, gold-light. This keeps the hero anchored
    to the Tribune voice rather than reading as plain caption text."""
    block = _css_block('.home-shell .decree-hero-unit')
    assert 'var(--gold-light)' in block, (
        "PI-2: `.decree-hero-unit` color must be `var(--gold-light)` per "
        "the eyebrow register (DESIGN.md §3 Eyebrow Rule)."
    )
    assert 'text-transform: uppercase' in block, (
        "PI-2: `.decree-hero-unit` must be uppercase per the eyebrow rule."
    )


# ---------------------------------------------------------------------------
# PI-3 retired: the `.decree-links` (House Rules + Scoring) lived inside the
# countdown card's CTA block, which the home-pre polish pass (PR following
# S6.x) removed entirely — the dossier slot now owns the single CTA surface.
# No element to protect, no tap-target floor to assert. The historical
# locks lived here; if .decree-links is ever reintroduced, the 44×44 floor
# applies (S2.1.2 recipe).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# F1: `_home_out.html` "Sign in" link 44×15 tap-target (inherited from S3.3.1).
# ---------------------------------------------------------------------------

def test_f1_join_alt_sign_in_link_meets_44px_tap_floor():
    """The `.join-alt a` link ("Already sworn in? Sign in") measured 44×15
    at the 375 viewport — height fails the 44×44 floor by 29px. Inline-
    flex with padding expands the hit area; negative margins neutralize
    the visual offset so the link still reads inline inside the running
    text."""
    block = _css_block('.home-shell .join-alt a')
    assert 'min-height: 44px' in block, (
        "F1: `.join-alt a` must declare `min-height: 44px`. Without it, "
        "the Sign-in link measures 15px tall and fails the mobile "
        "tap-target floor (PRODUCT.md Mobile-First Requirements)."
    )
    # Negative margins keep the link reading inline with the running text.
    # The padding+margin pair must come together — padding alone would push
    # the link off-baseline.
    assert 'margin: -0.6rem -0.5rem' in block, (
        "F1: `.join-alt a` must use `margin: -0.6rem -0.5rem` to "
        "neutralize the `padding: 0.6rem 0.5rem` visual offset. Without "
        "the negative-margin trick the link slips off the running-text "
        "baseline."
    )


def test_f1_join_alt_link_carries_focus_visible_ring():
    """Same focus-ring discipline as PI-3 — keyboard users see the
    canonical 2px gold-light outline."""
    block = _css_block('.home-shell .join-alt a:focus-visible')
    assert 'outline: 2px solid var(--gold-light)' in block, (
        "F1: `.join-alt a:focus-visible` must carry the canonical 2px "
        "gold-light focus ring."
    )


# ---------------------------------------------------------------------------
# Rendered-HTML assertions — full-page integration with the Flask test client.
# ---------------------------------------------------------------------------

def test_rendered_out_state_heading_outline_is_h1_then_h2_no_skips():
    """Logged-out home page (state='out') must render a clean H1 → H2 outline
    with no skipped levels. The original H1 → H3 jump was an axe heading-order
    violation. Distill 2026-06-08: the featured card's H3 retired with the
    merge — the conversion card's pool name is now an H2 (`.join-title`) and the
    breadth section keeps its H2 (`out-registry-head`), so the outline is
    H1 → H2 → H2 with no gap. Neither the old skip nor the featured H3 may
    return."""
    from app import create_app
    from extensions import db
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        with app.test_client() as c:
            resp = c.get('/')
            body = resp.data.decode('utf-8')
    h1_pos = body.find('<h1')
    join_h2_pos = body.find('<h2 class="join-title"')
    section_h2_pos = body.find('id="out-registry-head"')
    assert h1_pos > -1, "Rendered home is missing `<h1>`."
    assert join_h2_pos > -1, (
        "Rendered home is missing the `<h2 class=\"join-title\">` conversion "
        "card heading — the pool name must be an H2, not a styled div."
    )
    assert section_h2_pos > -1, (
        "Rendered home is missing `<h2 id=\"out-registry-head\">` — the "
        "breadth section heading that keeps the region named for AT."
    )
    # Page H1 precedes both H2s; no level is skipped (no H3 before an H2).
    assert h1_pos < join_h2_pos < section_h2_pos, (
        "Heading outline order regressed: H1 at "
        f"{h1_pos}, join H2 at {join_h2_pos}, section H2 at {section_h2_pos}. "
        "Must be H1 < join-card H2 < breadth-section H2."
    )
    # The retired featured card's H3 (the old H1→H3 skip) must not come back.
    assert 'out-featured-title' not in body, (
        "Rendered home re-introduced `out-featured-title` — the featured card "
        "H3 the distill merge retired. A stray H3 above the section H2 reopens "
        "the heading-order gap."
    )


def test_rendered_out_state_no_longer_carries_col_md_4_registry_grid():
    """End-to-end check: the rendered logged-out page must not contain the
    pre-S4.1.1 `col-md-4` 3-up registry grid. This catches both source-
    template regressions and any future routing-level reintroduction."""
    from app import create_app
    from extensions import db
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        with app.test_client() as c:
            resp = c.get('/')
            body = resp.data.decode('utf-8')
    # The `<div class="col-sm-6 col-md-4">` pattern was the registry grid
    # cell. It must not surround the registry section any more.
    assert 'col-sm-6 col-md-4' not in body, (
        "Rendered home re-introduced `col-sm-6 col-md-4` Bootstrap "
        "containers — the identical-card-grid pattern is back. Use "
        "`.out-registry-grid` instead."
    )
    # Positive lock: the merged conversion CTA + breadth section + rail must
    # all render.
    for marker in ('join-cta', 'out-registry', 'out-coming-rail'):
        assert marker in body, (
            f"Rendered home is missing `{marker}` — the distill merge didn't "
            f"make it to the response body."
        )
    # The second gold CTA must not return — exactly one primary CTA on the page.
    assert 'out-featured' not in body, (
        "Rendered home re-introduced `out-featured` — the second gold CTA the "
        "distill merge removed. The page must carry exactly one primary CTA."
    )
