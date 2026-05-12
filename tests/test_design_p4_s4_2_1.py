"""P4 S4.2.1 regression locks — picks.html + _pick_row.html first iteration.

Layer A (per plan §1.3) source-pattern locks for the four Priority Issues
and three freebies that landed in S4.2.1. The surface covers the World Cup
pick UI (form + read-only roster shells).

Iteration map:

- PI-1 (`$impeccable harden` — keyboard / AT primitive). Pre-S4.2.1 the
  team-card was `<div onclick>` wrapping a Bootstrap `.d-none` checkbox —
  not focusable, not space-toggleable, fully invisible to assistive tech.
  Sam (NVDA + keyboard) could not make picks. The new shape is the same
  `<div>` with `role="checkbox" tabindex="0" aria-checked` + an inline
  `onkeydown` handler that intercepts Space/Enter, plus a canonical 2px
  gold-light `:focus-visible` ring matching the S2.1.2 / S3.4 lock. The
  underlying `<input>` stays as the form-submission carrier but moves
  from `.d-none` (display:none — removed from AT tree) to
  `.visually-hidden` with `aria-hidden="true" tabindex="-1"`.

- PI-2 (`$impeccable optimize` — pick-accordion motion-law fix). Pre
  -S4.2.1 the accordion transitioned `max-height: 0 → 600px`, a layout
  property animation (DESIGN.md absolute ban + impeccable shared design
  law: "Don't animate CSS layout properties"). The 600px ceiling also
  clipped any team that accrued 10+ score events (Champion-tier with
  group + KO bonuses). The new pattern uses CSS Grid `grid-template-
  rows: 0fr ↔ 1fr` on the `.pick-accordion` outer with a single
  `.pick-accordion-inner` wrapper carrying overflow/min-height. No
  ceiling, no layout-property animation, no clip risk.

- PI-3 (`$impeccable adapt` — 44×44 tap-target floor). Two surface
  affordances failed the PRODUCT.md mobile-first floor: the hero
  "View Scoring Rules" link (137×23) and the `.team-group-pill` inside
  each team-card (42×21). The hero link is now `.picks-rules-link`, an
  inline-flex chip with `min-height: 44px` + `min-width: 44px` + the
  S2.1.2-locked negative-margin recipe. The pill gets `min-height/min-
  width: 44px` + padding + canonical focus ring. Per §1.5b atomic-edit
  rule, both close one priority issue (44×44 floor recurrence).

- PI-4 (`$impeccable colorize` — CCC tinted-neutrals replace literal
  WC navy + `#fff`). Three platform-component declarations carried
  literal `rgba(0, 40, 104, ...)` (WC navy hex inlined) instead of
  CCC tinted neutrals: `.tier-card-header` background gradient,
  `.wc-team-card.selected` background tint, `.wc-team-card.selected`
  ring (box-shadow). On the bone page, the selected affordance should
  read CCC purple (Council Purple, `rgba(58, 29, 114, ...)`) — not the
  game tertiary. `.tier-badge` color was literal `#fff`, which violates
  the No-Pure-White Rule; lifted to `var(--text-on-dark)` (= pressroom
  -bone). `.wc-team-card.selected::after` checkmark recolored from
  `var(--game-primary)` to `var(--platform-primary)` so the affordance
  stays in the brand register.

- F1 (`aria-live` on counters). `#counter-{N}` and `#mobilePickCount`
  now carry `aria-live="polite" aria-atomic="true"` so Sam hears the
  "3/3 selected" / "9/9 picks" updates as they happen.

- F2 (heading-order fix). Pre-S4.2.1 the read-only "Your 9 Picks"
  card-header was an `<h4>` (×2 — desktop + mobile) — directly under
  the hero `<h1>`, skipping H2 + H3 (axe heading-order moderate).
  Promoted to `<h2 class="pick-card-head">` with a surface class that
  preserves the prior Teko 1.35rem visual (and `--mobile` modifier
  for the mobile card-header's 1.1rem variant).

- F3 (mobile readonly Grp letter AA fix). `.player-pick-card .pick-
  team small` was `--text-muted` (#8A849B) on the white card surface
  (~3.7:1 — AA fail per `project_text_muted_aa_on_bone` memory).
  Lifted to `--text-secondary` (#5A5470, ~6.9:1) matching the S2.5.1
  PI-5 lock on `.wc-eyebrow` on the same surface.
"""
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()
PICKS = (ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'picks.html').read_text()
PICK_ROW = (ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / '_pick_row.html').read_text()


def _css_rule(selector: str) -> str:
    """Concatenate the bodies of every CSS rule whose opening selector
    list contains the given selector. Used to assert on specific
    declarations regardless of media-query branch."""
    normalized = selector.rstrip().removesuffix('{').rstrip()
    blocks = re.findall(
        rf'{re.escape(normalized)}\s*\{{[^}}]*\}}',
        CSS,
    )
    assert blocks, f'css rule not found for {normalized!r}'
    return '\n'.join(blocks)


# ----- PI-1: keyboard / AT primitive on .wc-team-card -----

def test_pi1_team_card_carries_role_checkbox_and_tabindex():
    """`.wc-team-card` must declare `role="checkbox"` + `tabindex="0"` so
    keyboard users can land focus on the primitive and AT announces the
    selectable role. PR #15 CR R5-F — bind both attributes to the
    `.wc-team-card` element itself via lookahead regex; an unrelated
    element elsewhere in `picks.html` carrying either attribute must not
    satisfy the lock."""
    card = re.search(
        r'<div(?=[^>]*class="[^"]*\bwc-team-card\b[^"]*")'
        r'(?=[^>]*role="checkbox")'
        r'(?=[^>]*tabindex="0")[^>]*>',
        PICKS,
    )
    assert card, (
        '.wc-team-card must carry both role="checkbox" AND tabindex="0" '
        'on the same element (keyboard focus + AT-announced selectable role).'
    )


def test_pi1_team_card_carries_aria_checked_with_initial_state():
    """`aria-checked` must reflect the server-rendered selection state so
    a logged-in user with `picks_submitted=True` opens the edit form with
    AT correctly announcing which 9 teams are already selected."""
    # Jinja-templated initial state: `aria-checked="{% if ... %}true{% else %}false{% endif %}"`
    assert re.search(
        r'aria-checked="\{%\s*if\s+team\.id\s+in\s+selected_team_ids\s*%\}true\{%\s*else\s*%\}false\{%\s*endif\s*%\}"',
        PICKS,
    ), 'aria-checked Jinja branch missing or shape changed'


def test_pi1_team_card_keyboard_handler_intercepts_space_and_enter():
    """The inline `onkeydown` must intercept Space + Enter and call
    `toggleTeam(this)` after `event.preventDefault()` so Space doesn't
    scroll the page out from under the user."""
    # Match the exact handler shape, allowing whitespace tolerance
    handler = re.search(r'onkeydown="([^"]*toggleTeam\(this\)[^"]*)"', PICKS)
    assert handler, 'onkeydown handler missing on team card'
    body = handler.group(1)
    assert "event.key === ' '" in body, 'space key not handled'
    assert "event.key === 'Enter'" in body, 'enter key not handled'
    assert 'event.preventDefault()' in body, 'preventDefault missing (Space would scroll page)'


def test_pi1_team_card_input_uses_visually_hidden_not_d_none():
    """The form-submission checkbox should move from Bootstrap `.d-none`
    (display:none — drops it from the AT tree) to `.visually-hidden`
    (positions off-screen, kept in DOM + form data) and carry
    `aria-hidden="true"` + `tabindex="-1"` so AT doesn't double-announce
    it alongside the role=checkbox div."""
    cb_pattern = re.search(
        r'<input[^>]*name="tier_\{\{\s*tier_num\s*\}\}"[^>]*>',
        PICKS,
    )
    assert cb_pattern, 'tier checkbox input missing'
    cb = cb_pattern.group(0)
    assert 'd-none' not in cb, 'team-checkbox still carries .d-none — AT cannot see it'
    assert 'visually-hidden' in cb, 'team-checkbox missing .visually-hidden'
    assert 'aria-hidden="true"' in cb, 'team-checkbox missing aria-hidden="true"'
    assert 'tabindex="-1"' in cb, 'team-checkbox missing tabindex="-1"'


def test_pi1_team_card_focus_visible_ring_locked():
    """Canonical 2px gold-light focus ring with 2px offset per S2.1.2
    lock — keyboard users need a visible focus indicator on the
    role=checkbox primitive."""
    rule = _css_rule('.wc-team-card:focus-visible')
    assert 'outline: 2px solid var(--gold-light)' in rule, \
        f'.wc-team-card:focus-visible missing canonical gold-light outline: {rule}'
    assert 'outline-offset: 2px' in rule, \
        f'.wc-team-card:focus-visible missing 2px offset: {rule}'


def test_pi1_toggle_team_js_keeps_aria_checked_in_sync():
    """`toggleTeam()` must call `setAttribute('aria-checked', ...)` so
    the AT-visible state and the underlying selection stay in lockstep
    on every click/keypress."""
    assert "card.setAttribute('aria-checked'" in PICKS, \
        'toggleTeam() does not update aria-checked on the card'


# ----- PI-2: pick-accordion motion-law fix (max-height → grid-template-rows) -----

def test_pi2_pick_accordion_no_longer_animates_max_height():
    """`max-height` animation is an impeccable absolute ban (layout-
    property motion). The `.pick-accordion` rule must not declare any
    `max-height` or transition it."""
    rule = _css_rule('.pick-accordion {')
    assert 'max-height' not in rule, \
        f'.pick-accordion still references max-height: {rule}'


def test_pi2_pick_accordion_uses_grid_template_rows_transition():
    """The accordion transitions `grid-template-rows: 0fr ↔ 1fr` via
    CSS Grid, with overflow on the `.pick-accordion-inner` wrapper.
    Lock the pattern so a future refactor doesn't quietly regress to
    `max-height`."""
    closed = _css_rule('.pick-accordion {')
    assert 'display: grid' in closed, '.pick-accordion missing display: grid'
    assert 'grid-template-rows: 0fr' in closed, '.pick-accordion missing 0fr resting state'
    assert 'transition: grid-template-rows' in closed, \
        '.pick-accordion transition does not include grid-template-rows'

    open_rule = _css_rule('.pick-accordion.open')
    assert 'grid-template-rows: 1fr' in open_rule, \
        '.pick-accordion.open missing 1fr expanded state'


def test_pi2_pick_accordion_inner_wrapper_carries_overflow_and_min_height():
    """The grid technique requires a single wrapper child with
    `overflow: hidden; min-height: 0;` so the row collapses cleanly.
    Without this, animation either jumps or fails to clip."""
    rule = _css_rule('.pick-accordion-inner')
    assert 'overflow: hidden' in rule, '.pick-accordion-inner missing overflow: hidden'
    assert 'min-height: 0' in rule, '.pick-accordion-inner missing min-height: 0'


def test_pi2_pick_row_wraps_content_in_pick_accordion_inner():
    """The `_pick_row.html` partial must wrap its accordion body in a
    single `.pick-accordion-inner` div so the grid technique works
    (multiple direct children would each get their own grid row, only
    one of which would animate). PR #15 CR R6-D — lock the direct-child
    shape (`.pick-accordion` > `.pick-accordion-inner`), not just
    presence anywhere in the partial."""
    # The outer `.pick-accordion` carries other attributes (e.g., id), so
    # the lookahead matches the opening tag regardless of attribute set;
    # the `\s*<div class="pick-accordion-inner">` then locks the direct-
    # child relationship (no intervening element).
    assert re.search(
        r'<div\b(?=[^>]*class="pick-accordion")[^>]*>\s*'
        r'<div\s+class="pick-accordion-inner">',
        PICK_ROW,
    ), '_pick_row.html missing direct `.pick-accordion > .pick-accordion-inner` structure'


def test_pi2_no_fixed_600px_max_height_ceiling_anywhere():
    """The 600px max-height ceiling clipped deep-run teams. No CSS rule
    targeting `.pick-accordion` may declare a max-height anywhere
    (including `.pick-accordion.open`). PR #15 CR R6-E — narrowed from
    a global `not in CSS` ban (which would fail on any unrelated 600px
    usage) to a scoped scan of `.pick-accordion(.open)?` rule blocks."""
    accordion_blocks = re.findall(
        r'\.pick-accordion(?:\.open)?\s*\{[^}]*\}',
        CSS,
    )
    assert accordion_blocks, '.pick-accordion rules must still exist in style.css'
    # PR #15 CR R8-B — whitespace-tolerant regex so `max-height:600px` (no
    # space) or `max-height :  600px` variants can't false-pass.
    assert all(not re.search(r'max-height\s*:\s*600px\b', block) for block in accordion_blocks), (
        'style.css still carries a 600px max-height on a `.pick-accordion` rule '
        '(the deep-run-clipping ceiling)'
    )


# ----- PI-3: 44×44 tap-target floor (hero rules link + .team-group-pill) -----

def test_pi3_picks_rules_link_replaces_bootstrap_text_white_50():
    """The hero "View Scoring Rules" link is no longer a raw Bootstrap
    `.text-white-50 small` inline anchor (137×23 — tap-floor fail). It's
    now a `.picks-rules-link` with the surface-scoped 44×44 + bone-alpha
    color pattern."""
    assert 'class="picks-rules-link"' in PICKS, \
        'picks.html missing .picks-rules-link wrapper on rules anchor'
    assert 'text-white-50' not in PICKS, \
        'picks.html still uses Bootstrap .text-white-50 on rules link'


def test_pi3_picks_rules_link_meets_44px_floor():
    """`.picks-rules-link` carries `min-height: 44px` + `min-width: 44px`
    so the rules anchor meets the PRODUCT.md mobile-first floor."""
    rule = _css_rule('.picks-rules-link {')
    assert 'min-height: 44px' in rule, '.picks-rules-link missing min-height: 44px'
    assert 'min-width: 44px' in rule, '.picks-rules-link missing min-width: 44px'


def test_pi3_picks_rules_link_carries_focus_visible_ring():
    """Canonical 2px gold-light focus ring on the keyboard-focused
    rules link."""
    rule = _css_rule('.picks-rules-link:focus-visible')
    assert 'outline: 2px solid var(--gold-light)' in rule
    assert 'outline-offset: 2px' in rule


def test_pi3_team_group_pill_meets_44px_floor():
    """`.team-group-pill` inside `.wc-team-card` must clear the 44×44
    floor — it's an interactive anchor route to the groups page."""
    rule = _css_rule('.wc-team-card .team-group-pill {')
    assert 'min-height: 44px' in rule, '.team-group-pill missing min-height: 44px'
    assert 'min-width: 44px' in rule, '.team-group-pill missing min-width: 44px'


def test_pi3_team_group_pill_carries_focus_visible_ring():
    """Keyboard-focused group pill carries the canonical focus ring."""
    rule = _css_rule('.wc-team-card .team-group-pill:focus-visible')
    assert 'outline: 2px solid var(--gold-light)' in rule
    assert 'outline-offset: 2px' in rule


# ----- PI-4: CCC tinted-neutrals replace literal WC navy + #fff -----

def test_pi4_tier_card_header_uses_ccc_purple_not_wc_navy():
    """`.tier-card-header` background gradient resolves to Council Purple
    (`rgba(58, 29, 114, ...)`) on the platform tier-card primitive — not
    the literal WC navy hex (`rgba(0, 40, 104, ...)`) that previously
    bound a platform component to one game's tertiary."""
    rule = _css_rule('.tier-card-header {')
    # Strip CSS block comments so the assertion checks declarations only.
    rule_body = re.sub(r'/\*.*?\*/', '', rule, flags=re.DOTALL)
    # PR #15 CR R7-C — split the compound `assert X and Y` so failure
    # diagnostics point at the specific spacing variant (Ruff PT018).
    assert 'rgba(0,40,104' not in rule_body, \
        f'.tier-card-header still uses WC navy literal (no-space form): {rule_body}'
    assert 'rgba(0, 40, 104' not in rule_body, \
        f'.tier-card-header still uses WC navy literal (spaced form): {rule_body}'
    assert 'rgba(58, 29, 114' in rule_body, \
        f'.tier-card-header missing CCC purple (Council Purple): {rule_body}'


def test_pi4_wc_team_card_selected_uses_ccc_purple_for_tint_and_ring():
    """`.wc-team-card.selected` background tint + box-shadow ring lift to
    Council Purple (`rgba(58, 29, 114, ...)`) so the selected affordance
    reads in the CCC brand register on the bone canvas. The border keeps
    `var(--game-primary)` so cross-game scoping still works."""
    rule = _css_rule('.wc-team-card.selected {')
    rule_body = re.sub(r'/\*.*?\*/', '', rule, flags=re.DOTALL)
    # PR #15 CR R7-C — split the compound `assert X and Y` (Ruff PT018).
    assert 'rgba(0,40,104' not in rule_body, \
        f'.wc-team-card.selected still references WC navy literal (no-space form): {rule_body}'
    assert 'rgba(0, 40, 104' not in rule_body, \
        f'.wc-team-card.selected still references WC navy literal (spaced form): {rule_body}'
    assert 'rgba(58, 29, 114, .05)' in rule_body, \
        f'.wc-team-card.selected background tint not Council Purple at .05: {rule_body}'
    assert 'rgba(58, 29, 114, .18)' in rule_body, \
        f'.wc-team-card.selected ring not Council Purple at .18: {rule_body}'


def test_pi4_wc_team_card_selected_checkmark_recolored_to_platform_primary():
    """The pseudo-element checkmark recolors from `var(--game-primary)`
    (WC navy) to `var(--platform-primary)` (Council Purple) so it
    matches the new tint + ring register. S4.2.2 F1 swapped the Unicode
    glyph for a CSS-mask SVG, so the color contract is now expressed via
    `background-color` (the mask paints whatever fill the box carries),
    NOT via `color`. Asserting `color:` would pass on substring match
    against `background-color:` and silently mask a regression — lock
    the actual property the implementation uses."""
    rule = _css_rule('.wc-team-card.selected::after')
    assert 'background-color: var(--platform-primary)' in rule, \
        f'.wc-team-card.selected::after mask not painted with platform-primary: {rule}'


def test_pi4_tier_badge_color_lifts_off_pure_white():
    """`.tier-badge { color: #fff; }` violates DESIGN.md No-Pure-White
    Rule. Lift to `var(--text-on-dark)` (= pressroom bone) so the badge
    text tints toward the brand neutral."""
    rule = _css_rule('.tier-badge {')
    # The badge background is colored (per-tier), and the foreground must
    # be a CCC bone token, not the literal `#fff` or `white` keyword.
    # Anchor each assertion on the `color` property via a negative-lookbehind
    # so a `background-color: ...` or `border-color: ...` value substring can't
    # false-pass (PR #15 CR R3, same hygiene as R2-D's checkmark contract).
    assert not re.search(r'(?<!-)color:\s*#fff\b', rule, flags=re.IGNORECASE), \
        '.tier-badge still uses literal #fff color'
    assert not re.search(r'(?<!-)color:\s*white\b', rule, flags=re.IGNORECASE), \
        '.tier-badge still uses literal white color'
    assert re.search(r'(?<!-)color:\s*var\(--text-on-dark\)', rule), \
        f'.tier-badge color must reference --text-on-dark token: {rule}'


# ----- F1: aria-live on counters -----

def test_f1_tier_counter_carries_aria_live_polite_and_atomic():
    """`#counter-{N}` announces "{m}/{n} selected" updates politely
    so AT users hear progress as they pick. PR #15 CR R5-G — use
    lookahead assertions so HTML attribute order can shift without
    breaking the lock; presence of each attribute on the same span
    is what we care about."""
    # PR #15 CR R8-C — scope `wc-numeral` to the `class` attribute so an
    # unrelated attribute carrying the token can't false-satisfy the lookahead.
    assert re.search(
        r'<span'
        r'(?=[^>]*class="[^"]*\btier-counter\b[^"]*")'
        r'(?=[^>]*class="[^"]*\bwc-numeral\b[^"]*")'
        r'(?=[^>]*id="counter-\{\{\s*tier_num\s*\}\}")'
        r'(?=[^>]*aria-live="polite")'
        r'(?=[^>]*aria-atomic="true")[^>]*>',
        PICKS,
    ), 'tier counter missing aria-live="polite" aria-atomic="true" on the .tier-counter.wc-numeral span'


def test_f1_mobile_pick_count_carries_aria_live_polite_and_atomic():
    """`#mobilePickCount` in the sticky bar also announces updates.
    PR #15 CR R5-G — lookahead assertions decouple from attribute order."""
    # PR #15 CR R8-C — same class-attribute scoping as the tier counter above.
    assert re.search(
        r'<span'
        r'(?=[^>]*class="[^"]*\bcount-num\b[^"]*")'
        r'(?=[^>]*class="[^"]*\bwc-numeral\b[^"]*")'
        r'(?=[^>]*id="mobilePickCount")'
        r'(?=[^>]*aria-live="polite")'
        r'(?=[^>]*aria-atomic="true")[^>]*>',
        PICKS,
    ), 'mobilePickCount missing aria-live="polite" aria-atomic="true" on the .count-num.wc-numeral span'


# ----- F2: heading-order H1 → H4 → H2 -----

def test_f2_readonly_card_headers_promoted_from_h4_to_h2():
    """Both readonly "Your 9 Picks" card headers (desktop + mobile) must
    use `<h2 class="pick-card-head">`, not `<h4>`. The hero `<h1>` is
    "Sealed. Still amendable." / "The Oath is sealed" / "Amend the Oath";
    H2 is the correct next step in the outline."""
    # No h4 should remain on this specific copy
    assert not re.search(r'<h4[^>]*>\s*<i[^>]*bi-check2-square[^>]*></i>\s*Your\s+9\s+Picks\s*</h4>', PICKS, re.IGNORECASE), \
        'readonly "Your 9 Picks" card-header still uses <h4>'
    # The h2 promotions must be present (×2 — desktop card-header + mobile card-header)
    h2_promotions = re.findall(
        r'<h2[^>]*class="[^"]*pick-card-head[^"]*"[^>]*>',
        PICKS,
    )
    assert len(h2_promotions) >= 2, \
        f'expected ≥2 <h2 class="pick-card-head"> instances (desktop + mobile), found {len(h2_promotions)}'


def test_f2_pick_card_head_css_preserves_prior_teko_visual():
    """The `.pick-card-head` surface class carries the Teko 1.35rem
    uppercase visual that the prior `<h4>` rendered, so the H4 → H2
    promotion doesn't shift the rendered hierarchy on the page."""
    rule = _css_rule('.pick-card-head {')
    assert "font-family: 'Teko', sans-serif" in rule, \
        '.pick-card-head missing Teko font-family'
    assert 'font-size: 1.35rem' in rule, '.pick-card-head font-size not 1.35rem'
    assert 'text-transform: uppercase' in rule, '.pick-card-head missing uppercase'

    mobile = _css_rule('.pick-card-head--mobile')
    assert 'font-size: 1.1rem' in mobile, '.pick-card-head--mobile font-size not 1.1rem'


# ----- F3: mobile readonly Grp letter AA fix -----

def test_f3_player_pick_card_grp_small_uses_text_secondary_not_text_muted():
    """`.player-pick-card .pick-team small` (the Grp-letter Newsreader
    italic) must paint `var(--text-secondary)` (~6.9:1 on bone, AA pass)
    not `var(--text-muted)` (~3.7:1 on bone, AA fail) per the
    `project_text_muted_aa_on_bone` memory + S2.5.1 PI-5 lock on the
    same surface."""
    rule = _css_rule('.player-pick-card .pick-team small')
    # Anchor on the `color` property via negative-lookbehind so a
    # `background-color: var(--text-secondary)` or `border-color: ...`
    # value can't false-pass either check (same hygiene as R3-E).
    assert re.search(r'(?<!-)color:\s*var\(--text-secondary\)', rule), \
        f'.player-pick-card .pick-team small not on --text-secondary: {rule}'
    assert not re.search(r'(?<!-)color:\s*var\(--text-muted\)', rule), \
        f'.player-pick-card .pick-team small still uses --text-muted: {rule}'
