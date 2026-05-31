"""P4 S4.1.2 regression locks — pre-state desktop 2-col + ballot semantics
+ card recipe vocabulary + out-prop differentiation.

Layer A (per plan §1.3) source-pattern locks for the Priority Issues landed
in S4.1.2. The surface covers the pre-state platform home partials
(`_home_pre.html`, `_ballot_card.html`) plus the logged-out value-props
strip in `_home_out.html` and the DESIGN.md §5 vocabulary addition.

Iteration map:

- PI-1 (`$impeccable layout` — pre-state desktop 2-col reshape):
  pre-S4.1.2 `_home_pre.html` lived inside a single `.home-col`
  (`max-width: 640px`), which floored the masthead to a phone-shaped
  column at every viewport. The new `.home-pre-grid` wrapper collapses
  to a 640-floored single column below md, then becomes a 7fr/5fr grid
  at md+ with two semantic slots (`.home-pre-col--main` for masthead +
  countdown + dossier, `.home-pre-col--rail` for opening matches +
  tiles + commish + dispatches). `.home-live` and `.home-shell--out`
  are unaffected (they use `.container-fluid > .row` and a separate
  single `.home-col` + registry composition).

- PI-2 (`$impeccable adapt` — `.ballot-card` semantic split): the
  pre-S4.1.2 ballot card was wrapped in `<a href="...?edit=1">`, which
  swallowed the flag ribbon + foot copy into one screen-reader link and
  routed every flag tap to "edit pick" instead of the team-detail
  surface a sighted user would expect. The new shape is a `<section>`
  with an explicit inline `.ballot-edit-action` anchor next to the foot
  prose, plus `aria-labelledby="ballot-status"` for AT region naming.
  Flags are decorative (`aria-hidden="true"`). The hover lift moved
  from `.ballot-card` to `.ballot-edit-action`.

- PI-3 (`$impeccable distill` — gold-bordered card recipe consolidation
  + DESIGN.md §5 vocabulary): the pre-S4.1.2 home shell carried three
  gold-bordered card recipes within one viewport (`.decree`,
  `.cta-card--seal`, `.match-card`) with conflicting border-opacity and
  radius values. The new 2-tier vocabulary (documented in DESIGN.md §5
  "Card recipes inside `.home-shell`") locks Ceremonial = purple-800→
  purple-900 + 30%-gold border + 14px radius (decree + cta-card--join +
  cta-card--seal); Informational = purple-850→purple-950 + 8%-bone
  border + 12px radius (match-card + cta-card--view). `.cta-card--seal`
  normalized from the outlier gold-overlay/35%/12px recipe to the
  ceremonial recipe. Base `.cta-card` no longer sets `border-radius`
  itself — per-variant overrides carry the register-specific value.

- PI-4 (`$impeccable delight` — `.out-prop` x3 row differentiation):
  the logged-out value-props strip rendered as three identical
  icon-text rows. The S4.1.2 fix differentiated rows by gutter mark
  (icon / sparkline / monogram). Revised in design/home-out-polish
  (2026-05-13) after first-impression critique: three different gutter
  shapes at the same 36x36 footprint read as "discombobulated" rather
  than rhythmic — the variety intervention created a new noise problem.
  The current lock drops all three gutter marks and separates rows
  with a single hairline gold rule, letting the Teko all-caps titles
  carry the structural rhythm. The identical-card-grid concern is
  addressed at the page level (the value-props strip + featured card
  + coming-soon rail are still structurally distinct) so the strip
  doesn't need within-itself differentiation.
"""
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()
HOME_OUT = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_home_out.html').read_text()
HOME_PRE = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_home_pre.html').read_text()
HOME_LIVE = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_home_live.html').read_text()
BALLOT = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_ballot_card.html').read_text()
DESIGN_MD = (ROOT / 'DESIGN.md').read_text()


def _css_rule(selector: str) -> str:
    """Return the concatenated body of every CSS rule whose opening
    selector list contains the given selector. Useful for asserting on
    specific declarations regardless of which media-query branch they
    appear in. Mirrors the helper in test_design_p4_s4_2_1.py — selector
    is normalized (trailing `{` + whitespace stripped) and the regex
    anchors on `\\s*\\{` so it can't bleed across comment boundaries or
    adjacent rule blocks (PR #15 CR R1 PI-3 → R4-A parity)."""
    normalized = selector.rstrip().removesuffix('{').rstrip()
    blocks = re.findall(
        rf'{re.escape(normalized)}\s*\{{[^}}]*\}}',
        CSS,
    )
    assert blocks, f'css rule not found for {normalized!r}'
    return '\n'.join(blocks)


# ---------------------------------------------------------------------------
# PI-1: pre-state desktop 2-col reshape.
# ---------------------------------------------------------------------------

def test_pi1_home_pre_uses_home_pre_grid_wrapper():
    """The pre-state masthead now lives inside `.home-pre-grid`. The
    pre-S4.1.2 `<div class="home-col">` wrapper has been replaced; only
    the new grid is allowed. `.home-col` itself is still in use by
    `_home_out.html` so the platform-wide rule stays."""
    assert 'home-pre-grid' in HOME_PRE, (
        "PI-1: `_home_pre.html` must use the `.home-pre-grid` wrapper "
        "so the md+ 2-col reshape applies. The single `.home-col` "
        "floor wasted ~830px on a 1280-px canvas."
    )
    # PR #15 CR R6-B — match `.home-col` as a class token within any
    # class list, not just the exact `class="home-col"` form. The literal
    # check would miss `class="home-col foo"` or reordered class lists
    # like `class="bar home-col"`.
    assert not re.search(
        r'class="(?:[^"]*\s)?home-col(?:\s[^"]*)?"',
        HOME_PRE,
    ), (
        "PI-1: `_home_pre.html` re-introduced the legacy `.home-col` "
        "wrapper. The pre-state must compose under `.home-pre-grid` so "
        "the masthead and rail can sit side-by-side at md+."
    )


def test_pi1_home_pre_grid_has_two_semantic_slots():
    """The grid has two slot columns: `.home-pre-col--main` (countdown
    + dossier) and `.home-pre-col--rail` (opening matches + tiles +
    commish + dispatches). Single column below md (CSS) preserves the
    mobile reading order; the template doesn't duplicate content."""
    assert 'home-pre-col home-pre-col--main' in HOME_PRE, (
        "PI-1: `_home_pre.html` missing the main column slot "
        "(`.home-pre-col--main`). Countdown + dossier belong there."
    )
    assert 'home-pre-col home-pre-col--rail' in HOME_PRE, (
        "PI-1: `_home_pre.html` missing the rail column slot "
        "(`.home-pre-col--rail`). Opening matches + tiles + commish + "
        "dispatches belong there."
    )


def test_pi1_main_slot_carries_countdown_and_dossier():
    """The main slot must precede the rail slot in source order (so the
    mobile single-column stack reads masthead → countdown → dossier →
    rail) AND must include the countdown + ballot. The standalone join/seal
    CTA cards were consolidated into the decree, so the countdown card now
    carries the pre-state CTA itself."""
    main_match = re.search(
        r'home-pre-col--main(.*?)home-pre-col--rail',
        HOME_PRE,
        re.DOTALL,
    )
    assert main_match, (
        "PI-1: main slot must appear before rail slot in source order "
        "so the mobile single-column stack reads correctly."
    )
    main_block = main_match.group(1)
    assert '_countdown_card.html' in main_block, (
        "PI-1: countdown card belongs inside `.home-pre-col--main`."
    )
    assert '_ballot_card.html' in main_block, (
        "PI-1: ballot dossier variant belongs inside main slot."
    )


def test_pi1_rail_slot_carries_supporting_partials():
    """The rail slot carries opening matches + game tiles + commish +
    dispatches. Those partials must NOT also appear in the main slot."""
    rail_match = re.search(
        r'home-pre-col--rail(.*?)</div>\{# /\.home-pre-col--rail #\}',
        HOME_PRE,
        re.DOTALL,
    )
    assert rail_match, (
        "PI-1: rail slot opening + closing tags missing or out of "
        "shape in `_home_pre.html`."
    )
    rail_block = rail_match.group(1)
    # S6.1.5 PI-5 — the 3 `_fixture_card.html` includes collapsed into an
    # inline `<ol class="fixture-ladder">` to break the identical-card-grid
    # pattern. The rail still owns opening matches; the affordance class
    # changed.
    assert 'fixture-ladder' in rail_block, (
        "PI-1: opening matches (fixture ladder) belong in the rail slot."
    )
    assert '_game_tiles_compact.html' in rail_block, (
        "PI-1: compact game tiles belong in the rail slot."
    )
    assert '_commish_note.html' in rail_block, (
        "PI-1: commish note belongs in the rail slot."
    )
    assert '_dispatches.html' in rail_block, (
        "PI-1: dispatches belongs in the rail slot."
    )


def test_pi1_grid_css_defines_mobile_single_column_and_md_split():
    """Below md the grid is `1fr` (single column, 640px floor mirrors
    the legacy `.home-col`). At md+ it switches to 7fr/5fr with a
    wider max-width so the masthead and rail share the canvas."""
    base = _css_rule('.home-shell .home-pre-grid')
    assert 'grid-template-columns: 1fr' in base, (
        "PI-1: `.home-pre-grid` base rule must declare "
        "`grid-template-columns: 1fr` so mobile stacks single-column."
    )
    assert 'max-width: 640px' in base, (
        "PI-1: `.home-pre-grid` must floor to 640px on mobile so the "
        "single-column register matches the legacy `.home-col` width."
    )
    # md+ rule lives inside an @media block; flatten the CSS and search for
    # both the breakpoint and the 7fr/5fr template together. PR #15 CR R5-C
    # — `[^}]*` would stop at the first closing brace, breaking the lock if
    # any unrelated rule appears before `.home-pre-grid` inside the media
    # block. Use a dotall non-greedy `[\s\S]*?` so the match spans nested
    # rule blocks correctly.
    md_pattern = re.compile(
        r'@media\s*\(min-width:\s*768px\)\s*\{[\s\S]*?\.home-shell\s+\.home-pre-grid'
        r'\s*\{[\s\S]*?minmax\(0,\s*7fr\)\s+minmax\(0,\s*5fr\)',
    )
    assert md_pattern.search(CSS), (
        "PI-1: `.home-pre-grid` must declare a 7fr/5fr "
        "`grid-template-columns` inside `@media (min-width: 768px)` so "
        "the masthead and rail sit side-by-side at md+."
    )


def test_pi1_home_live_unchanged_keeps_container_fluid_row_layout():
    """The shared `.home-shell` parent risks live-state regression
    (S4.1.1 routed concern). `_home_live.html` must still use its own
    `.container-fluid.home-live` + `.row` composition — it shouldn't
    pick up `.home-pre-grid` either."""
    assert 'home-pre-grid' not in HOME_LIVE, (
        "PI-1: `_home_live.html` must NOT use `.home-pre-grid`. The "
        "live state has its own `.container-fluid > .row` composition "
        "with order-* mobile reading control; importing the pre-state "
        "grid would re-flow the live dossier."
    )
    assert 'container-fluid home-live' in HOME_LIVE, (
        "PI-1: `_home_live.html` lost its `.container-fluid.home-live` "
        "wrapper. The live-state layout must be preserved."
    )


# ---------------------------------------------------------------------------
# PI-2: `.ballot-card` semantic restructure.
# ---------------------------------------------------------------------------

def test_pi2_ballot_card_no_longer_whole_area_link():
    """The pre-S4.1.2 ballot card was an `<a href="...?edit=1">` wrapping every
    child element. The new shape is a `<section>` with `aria-labelledby` —
    the whole-area-link is gone.

    S6.1.5 PI-2 — flags are themselves anchors now (44×44 links to
    team_detail), so the previous "no `<a href` anywhere before
    `.ballot-foot`" form would false-positive. The invariant we're locking is
    that the OUTERMOST element of the partial is the `<section>`, not an
    anchor wrapper."""
    # Strip Jinja {# ... #} comments AND {% ... %} statement tags (e.g. the
    # top-of-file `{% from '_flag.html' import flag %}` import, which renders to
    # nothing) + leading whitespace, so the first *rendered* element check is
    # robust to template indentation and no-output Jinja tags.
    body = re.sub(r'\{#.*?#\}', '', BALLOT, flags=re.DOTALL)
    body = re.sub(r'\{%.*?%\}', '', body, flags=re.DOTALL).lstrip()
    assert body.startswith('<section'), (
        "PI-2: `_ballot_card.html` must open with a `<section>` element. "
        "The pre-S4.1.2 anchor wrapper conflated nine flag taps with one "
        "edit-roster route; the explicit edit action lives inside "
        "`.ballot-foot`."
    )
    assert '<section class="ballot-card"' in BALLOT, (
        "PI-2: `_ballot_card.html` must wrap as "
        "`<section class=\"ballot-card\" aria-labelledby=\"ballot-status\">` "
        "so AT users hear region structure instead of one giant link."
    )
    assert 'aria-labelledby="ballot-status"' in BALLOT, (
        "PI-2: `<section>` must reference the status element via "
        "`aria-labelledby` so the region carries a name for AT."
    )


def test_pi2_ballot_card_has_explicit_edit_action():
    """The edit affordance is now an explicit inline link inside the
    foot, not the whole card. It carries the edit URL the previous
    wrapper held, plus the canonical visual register."""
    assert 'class="ballot-edit-action"' in BALLOT, (
        "PI-2: `_ballot_card.html` missing the explicit "
        "`.ballot-edit-action` link. Without it the user can't reach "
        "the edit-picks surface from the card."
    )
    edit_pattern = re.compile(
        r'class="ballot-edit-action"\s+href="\{\{\s*url_for\(\'worldcup\.picks\'\)\s*\}\}\?edit=1"'
    )
    assert edit_pattern.search(BALLOT), (
        "PI-2: `.ballot-edit-action` must point at "
        "`url_for('worldcup.picks')?edit=1` so the edit route the old "
        "wrapper served is preserved."
    )


def test_pi2_ballot_flags_are_accessible_team_detail_links():
    """S6.1.5 PI-2 — flags promoted from decorative ribbon to a `<ul>` of
    44×44 anchors to `/worldcup/team/<id>`. Pre-S6.1.5 they were aria-hidden
    36×36 spans with a `title=` tooltip (desktop-mouse only), so on mobile a
    thumb landed on a flag and got silence. The ribbon container still has
    an accessible name; each flag link now carries its own
    `aria-label="<team>, view team detail"` so AT users get the destination,
    not the emoji."""
    # The ribbon container is now a <ul> (was <div>). Match either to keep the
    # lock resilient if the structural element ever shifts again; the
    # invariant is the accessible name on the container.
    ribbon = re.search(
        r'<(?:ul|div)(?=[^>]*class="[^"]*\bballot-flags\b[^"]*")'
        r'(?=[^>]*aria-label="Your nine selected nations")[^>]*>',
        BALLOT,
    )
    assert ribbon, (
        "PI-2: `.ballot-flags` container must carry "
        "`aria-label=\"Your nine selected nations\"` so the ribbon has "
        "an accessible name."
    )
    # Each `.ballot-flag` is now an `<a>` (not a `<span>`) routed to
    # team_detail. Verify EVERY flag carries its own aria-label so AT users
    # hear the destination team name, not the bare flag emoji.
    flag_anchors = re.findall(r'<a\s+class="ballot-flag"[^>]*>', BALLOT)
    assert flag_anchors, "PI-2: `.ballot-flag` anchors should render."
    assert all('aria-label=' in a for a in flag_anchors), (
        "PI-2: every `.ballot-flag` anchor must carry its own "
        "`aria-label` so AT users hear the team name + destination, "
        "not nine bare flag emoji."
    )
    # PR #30 CR — the prior form `all(... in BALLOT for _ in [None])` iterated
    # exactly once and reduced to a single substring check against the whole
    # file. If only one of nine flag anchors carried the route, the lock
    # would silently pass. Iterate over the captured opening tags so every
    # `.ballot-flag` anchor is verified individually.
    assert all("url_for('worldcup.team_detail'" in a for a in flag_anchors), (
        "PI-2: every `.ballot-flag` anchor must route to "
        "`url_for('worldcup.team_detail', team_id=...)`."
    )


def test_pi2_ballot_card_no_longer_lifts_on_hover_at_card_level():
    """Hover lift moved to `.ballot-edit-action`. The card itself has no
    positive translate on hover — sighted users see the action lift,
    not the whole card. (A `transform: none` reset inside the
    `@media (hover: none)` touch suppression block is fine; the ban is
    on positive `translateY(-Npx)` lifts at the card level.)

    The `.ballot-card:hover` rule may be absent entirely — that's an
    even stronger guarantee than "present without translateY", so the
    block-search-then-assert pattern below tolerates both shapes."""
    pattern = re.escape('.home-shell .ballot-card:hover') + r'\s*\{[^}]*\}'
    blocks = re.findall(pattern, CSS)
    combined = '\n'.join(blocks)
    assert 'translateY' not in combined, (
        "PI-2: `.home-shell .ballot-card:hover` must not declare a "
        "`translateY` lift. Hover lift belongs on `.ballot-edit-action`."
    )
    # And the polish lift block at the bottom of the file must no
    # longer include `.ballot-card` in its selector list.
    polish_lift_block = re.search(
        r'/\* --- Polish: card-style links use the same lift.*?\*/'
        r'\s*([^{]+\{[^}]+\})\s*([^{]+\{[^}]+\})',
        CSS,
        re.DOTALL,
    )
    assert polish_lift_block, (
        "PI-2: polish-lift block comment + rules must still exist in "
        "style.css (just without `.ballot-card`)."
    )
    combined = polish_lift_block.group(1) + polish_lift_block.group(2)
    assert '.ballot-card' not in combined, (
        "PI-2: the polish-lift block must not include `.ballot-card`. "
        "The card no longer is an anchor; its hover lift moved to "
        "`.ballot-edit-action`."
    )


def test_pi2_ballot_edit_action_meets_44px_tap_floor_and_has_focus_ring():
    """The explicit edit action must satisfy the PRODUCT.md
    Mobile-First 44x44 tap floor and carry the canonical CCC
    gold-light `:focus-visible` ring. PR #15 CR R5-D — both dimensions
    are locked; min-height alone doesn't guarantee a 44x44 contract."""
    action_block = _css_rule('.home-shell .ballot-edit-action')
    assert 'min-height: 44px' in action_block, (
        "PI-2: `.ballot-edit-action` must declare `min-height: 44px` "
        "to satisfy the 44x44 mobile tap floor."
    )
    assert 'min-width: 44px' in action_block, (
        "PI-2: `.ballot-edit-action` must declare `min-width: 44px` "
        "to satisfy the 44x44 mobile tap floor (height alone is not enough)."
    )
    focus_block = _css_rule('.home-shell .ballot-edit-action:focus-visible')
    assert 'outline: 2px solid var(--gold-light)' in focus_block, (
        "PI-2: `.ballot-edit-action:focus-visible` must carry the "
        "canonical CCC `2px solid var(--gold-light)` ring so keyboard "
        "users see the affordance."
    )
    assert 'outline-offset: 2px' in focus_block, (
        "PI-2: `:focus-visible` ring must use `outline-offset: 2px` "
        "per the S2.1.2 / S3.3.2 lock."
    )


def test_pi2_ballot_edit_action_hover_respects_reduced_motion():
    """`.ballot-edit-action:hover` adds `transform: translateY(-1px)`.
    The `prefers-reduced-motion: reduce` opt-out must reset that lift so
    users who request reduced motion don't still see it. PR #15 CR R2
    caught the missing entry; PR #15 CR R5-E decoupled this lock from
    the previous `.ballot-card:hover` sentinel (which assumed selector
    ordering AND coupled the test to a selector whose lift was
    intentionally removed). The new shape just asserts that SOME
    `prefers-reduced-motion: reduce` block declares the reset — the
    selector ordering and sibling selectors inside that block are free
    to evolve."""
    # Find every `@media (prefers-reduced-motion: reduce)` block in the CSS
    # and check at least one contains the `.ballot-edit-action:hover` reset.
    blocks = re.findall(
        r'@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{(?:[^{}]|\{[^}]*\})*\}',
        CSS,
    )
    assert blocks, (
        "Expected at least one `@media (prefers-reduced-motion: reduce)` "
        "block in style.css."
    )
    matched = any(
        '.home-shell .ballot-edit-action:hover' in block
        for block in blocks
    )
    assert matched, (
        "`.home-shell .ballot-edit-action:hover` must appear in some "
        "`@media (prefers-reduced-motion: reduce)` opt-out so the "
        "`translateY(-1px)` lift is reset for users who request "
        "reduced motion."
    )


# ---------------------------------------------------------------------------
# PI-3: card recipe vocabulary consolidation.
# ---------------------------------------------------------------------------

def test_pi3_cta_card_seal_normalized_to_ceremonial_recipe():
    """The pre-S4.1.2 `.cta-card--seal` carried the outlier recipe
    (gold-overlay gradient `rgba(201,162,39,.1)` + 35%-gold border +
    12px radius). It now mirrors the Ceremonial register: purple-800→
    purple-900 + 30%-gold border + 14px radius (same recipe as
    `.decree` and `.cta-card--join`)."""
    # The consolidated ceremonial selector group should include both
    # --seal and --join in one rule.
    pattern = re.compile(
        r'\.home-shell\s+\.cta-card--seal\s*,\s*'
        r'\.home-shell\s+\.cta-card--join\s*\{[^}]*'
        r'var\(--purple-800\)[^}]*var\(--purple-900\)[^}]*'
        r'rgba\(201,162,39,\.3\)[^}]*'
        r'border-radius:\s*14px',
        re.DOTALL,
    )
    assert pattern.search(CSS), (
        "PI-3: `.cta-card--seal` + `.cta-card--join` must share one "
        "rule declaring the Ceremonial recipe (purple-800 → purple-900 "
        "gradient + 30%-gold border + 14px radius). DESIGN.md §5 "
        "documents this register."
    )


def test_pi3_decree_normalized_to_canonical_30_percent_gold_border():
    """Pre-S4.1.2 `.decree` carried `rgba(201,162,39,.35)` — close to but
    not equal to the consolidated cta-card recipe at `.3`. The
    Ceremonial vocabulary is one recipe, so `.decree`'s border opacity
    normalizes to `.3` to match `.cta-card--seal` + `.cta-card--join`
    + the value DESIGN.md §5 names."""
    decree_block = _css_rule('.home-shell .decree')
    # Anchor on the `border` property so a `background: rgba(201,162,39,.3)`
    # elsewhere in the block can't false-pass.
    assert re.search(r'border[^:]*:\s*[^;]*rgba\(201,162,39,\.3\)', decree_block), (
        "PI-3: `.decree` must normalize its border to "
        "`1px solid rgba(201,162,39,.3)` so the Ceremonial recipe "
        "shares one canonical opacity with `.cta-card--seal/join`."
    )
    # The outlier `.35` must be gone from the decree base rule.
    base_pattern = re.compile(
        r'\.home-shell\s+\.decree\s*\{([^}]*)\}',
    )
    base = base_pattern.search(CSS)
    assert base, "PI-3: base `.decree` rule missing from style.css."
    assert 'rgba(201,162,39,.35)' not in base.group(1), (
        "PI-3: `.decree` still carries the legacy `.35` border opacity. "
        "Normalize to `.3` (matches the Ceremonial recipe in DESIGN.md "
        "§5)."
    )


def test_pi3_cta_card_seal_no_longer_uses_gold_overlay_gradient():
    """The gold-overlay gradient that distinguished the pre-S4.1.2
    seal recipe is gone. There should be no `.cta-card--seal` rule
    whose body sets a `rgba(201,162,39,.1)` background — that fingerprint
    was the outlier."""
    seal_rules = re.findall(
        r'\.home-shell[^{]*\.cta-card--seal[^{]*\{[^}]*\}',
        CSS,
    )
    combined = '\n'.join(seal_rules)
    assert 'rgba(201,162,39,.1)' not in combined, (
        "PI-3: `.cta-card--seal` still carries the gold-overlay "
        "gradient (`rgba(201,162,39,.1)`). The Ceremonial vocabulary "
        "drops it in favor of the shared purple-800 → purple-900 fill."
    )
    assert 'rgba(201,162,39,.35)' not in combined, (
        "PI-3: `.cta-card--seal` still carries the outlier 35%-gold "
        "border. Ceremonial recipe uses 30% (matches `.decree`)."
    )


def test_pi3_cta_card_view_holds_informational_recipe():
    """Informational register: purple-850 → purple-950 gradient +
    8%-bone border + 12px radius. Used for standing affordances
    (`.cta-card--view`, `.match-card`)."""
    view_block = _css_rule('.home-shell .cta-card--view')
    assert 'var(--purple-850)' in view_block, (
        "PI-3: `.cta-card--view` must declare the purple-850 → "
        "purple-950 gradient per the Informational recipe."
    )
    assert 'var(--purple-950)' in view_block, (
        "PI-3: `.cta-card--view` must reach `--purple-950` at the "
        "gradient terminus."
    )
    # Anchor on the `border` property so a `background: rgba(...)` elsewhere
    # in the block can't false-pass. S6.1.4 PI-1 hardened the canonical
    # Informational border value from literal white-8 (`rgba(255,255,255,.08)`)
    # to bone-8 (`rgba(243,239,230,.08)`) so the recipe across `.match-card`
    # / `.cta-card--view` / `.commish-note-body` shares one tinted-neutral
    # color (impeccable "no pure white" law; DESIGN.md §5).
    assert re.search(r'\bborder\s*:\s*[^;]*rgba\(243,\s*239,\s*230,\s*\.08\)', view_block), (
        "PI-3 / S6.1.4 PI-1: `.cta-card--view` must carry the bone-8 "
        "border per the Informational recipe (matches `.match-card` + "
        "`.commish-note-body`)."
    )
    assert 'border-radius: 12px' in view_block, (
        "PI-3: `.cta-card--view` must use `border-radius: 12px` per "
        "the Informational recipe."
    )


def test_pi3_cta_card_base_drops_radius_declaration():
    """Base `.cta-card` no longer sets `border-radius` — the value
    differs between Ceremonial (14px) and Informational (12px), so it
    moves to the per-variant rules."""
    # Find the .cta-card base rule (not the .cta-card-* descendants).
    base_pattern = re.compile(
        r'\.home-shell\s+\.cta-card\s*\{([^}]*)\}',
    )
    base_match = base_pattern.search(CSS)
    assert base_match, (
        "PI-3: base `.cta-card` rule missing from style.css."
    )
    base_body = base_match.group(1)
    assert 'border-radius:' not in base_body, (
        "PI-3: base `.cta-card` rule must NOT set `border-radius` — "
        "the Ceremonial variants use 14px and Informational uses 12px. "
        "Move radius declarations to the per-variant rules."
    )


def test_pi3_design_md_documents_home_shell_card_recipes():
    """DESIGN.md §5 must name the two-tier vocabulary so a future
    contributor adds a new home-shell card by picking a register, not
    inventing a third recipe."""
    assert 'Card recipes inside `.home-shell`' in DESIGN_MD, (
        "PI-3: DESIGN.md must add a new subsection in §5 named "
        "`Card recipes inside `.home-shell`` so the vocabulary is "
        "discoverable. Without the doc, the next iteration will drift "
        "back into three-recipes-in-a-viewport."
    )
    # The subsection should name both registers + at least the canonical
    # classes from each.
    assert '**Ceremonial**' in DESIGN_MD, (
        "PI-3: DESIGN.md §5 subsection must call the first register "
        "`**Ceremonial**` (bold) so the vocabulary is unambiguous."
    )
    assert '**Informational**' in DESIGN_MD, (
        "PI-3: DESIGN.md §5 subsection must call the second register "
        "`**Informational**` (bold)."
    )
    assert '.decree' in DESIGN_MD, (
        "PI-3: DESIGN.md §5 subsection must name `.decree` as a "
        "Ceremonial member."
    )
    assert '.match-card' in DESIGN_MD, (
        "PI-3: DESIGN.md §5 subsection must name `.match-card` as an "
        "Informational member."
    )


# ---------------------------------------------------------------------------
# PI-4 (revised in design/home-out-polish, 2026-05-13): drop all `.out-prop`
# gutter marks; rows are separated by a single hairline gold rule. The Teko
# all-caps titles carry the rhythm.
# ---------------------------------------------------------------------------

def test_pi4_out_props_drop_all_gutter_marks():
    """The S4.1.2 fix differentiated rows by gutter mark (icon /
    sparkline / monogram) at the same 36x36 footprint. First-impression
    critique judged the variety itself as noise; the revised pattern
    drops all three marks so the rows read as a clean three-line
    editorial list with Teko titles doing the structural work."""
    for marker in ('out-prop-icon', 'out-prop-spark', 'out-prop-monogram'):
        assert marker not in HOME_OUT, (
            f"PI-4 (revised): `_home_out.html` still carries "
            f"`.{marker}`. The design/home-out-polish revision dropped "
            f"all three gutter marks; the rows must render title + sub "
            f"only, separated by a single hairline gold rule."
        )
    # The pre-revision Bootstrap-icon trophy element must not return either.
    assert 'bi-trophy-fill' not in HOME_OUT, (
        "PI-4 (revised): the `bi-trophy-fill` icon (the S4.1.2 row-1 "
        "baseline) must not return in `_home_out.html`."
    )


def test_pi4_out_props_separated_by_hairline_gold_rule():
    """Without gutter marks, the row separator carries the visual
    rhythm. The hairline is a 1px gold rule (per DESIGN.md §3 'gold
    divider rules between sections'), tuned to a low alpha so it
    reads as a Tribune rule, not as a forced grid divider."""
    prop_block = _css_rule('.home-shell .out-prop')
    # Match either the bare `border-bottom: ...rgba(201,162,39,...)`
    # form or a `border-bottom: 1px solid rgba(201,162,39,...)` form,
    # so the alpha calibration can evolve without breaking the lock.
    rule_pattern = re.compile(
        r'border-bottom\s*:\s*1px\s+solid\s+rgba\(201,\s*162,\s*39,'
    )
    assert rule_pattern.search(prop_block), (
        "PI-4 (revised): `.home-shell .out-prop` must separate rows "
        "with `border-bottom: 1px solid rgba(201,162,39, …)` (a gold "
        "hairline rule, DESIGN.md §3). The bone hairline the S4.1.2 "
        "iteration carried no longer fits without the gutter marks."
    )
