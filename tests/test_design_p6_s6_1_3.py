"""S6.1.3 — Cross-phase polish (Iter 3). Layer A locks.

Four PIs in one cluster iteration; each routed in from §0.4 of the
impeccable design improvement plan (P6 §8 docket):

- PI-1 (Group J — 3 routes closed in one atomic edit): leaderboard
  polish triple. (a) Tiebreaker cell fallback voiced as "No guess"
  (not literal lowercase 'none' breaking the editorial register).
  (b) Move column header gains `title="Change since yesterday's
  snapshot"` for analyst context. (c) Gold-divider rule threads the
  Your Position tribune block to the standings cards. Closes
  S1.1 x 3 routes.

- PI-2 (Group I): `--metal-gold-flat`'s 100% stop retuned from
  `#8A6A1A` → `#A88420` so chamber-purple text on the navbar
  `.btn-warning` clears WCAG AA 4.5:1 at the bottom-right pixel
  corner where the 135° gradient terminates. `--gold-dark` token
  itself is unchanged (still `#8A6A1A`); only the gradient stop
  is lifted. DESIGN.md §2 ratifies the new dark anchor.
  Closes S0.3 route.

- PI-3 (Group E PI-A): voice repetition stack on read-only picks
  collapses. Card-header eyebrows ("Sealed · still amendable" /
  "The Oath is sealed") no longer echo the H1 — both branches now
  read the invariant Tribune section anchor "The Ballot". Closes
  S4.2.1 cross-phase route.

- PI-4 (Group E PI-B): success flash banners auto-fade after ~4s so
  they don't compete with the page masthead on every navigation.
  Pure-CSS opacity animation (no layout reflow per the impeccable
  ban on animating layout properties); `prefers-reduced-motion`
  bypass disables the auto-fade. Errors/warnings stay loud until
  dismissed. Closes S4.1.1 cross-phase route.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN_MD = REPO_ROOT / 'DESIGN.md'
STYLE_CSS = REPO_ROOT / 'static' / 'css' / 'style.css'
TOKENS_CSS = REPO_ROOT / 'static' / 'css' / 'tokens.css'
LEADERBOARD_HTML = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'leaderboard.html'
PICKS_HTML = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'picks.html'


# ---------------------------------------------------------------------------
# PI-1 locks (Group J): leaderboard tiebreaker / Move tooltip / visual thread.
# ---------------------------------------------------------------------------

def test_pi1_tiebreaker_fallback_uses_voiced_string():
    """The tiebreaker cell fallback reads "No guess", not literal 'none'.

    The pre-S6.1.3 source rendered `'none'` (lowercase) when an enrollment
    had no `usa_goals_guess` — a SaaS dump that broke the editorial
    register. The voiced fallback "No guess" matches the Tribune voice
    and keeps the cell present without faking a numeric value.
    """
    html = LEADERBOARD_HTML.read_text()
    assert "is not none else 'No guess'" in html, (
        'Tiebreaker cell must fall back to "No guess" voiced string '
        '(S6.1.3 PI-1, Group J).'
    )
    assert "is not none else 'none'" not in html, (
        "Old literal 'none' fallback must not re-appear — it breaks the "
        "editorial register."
    )


def test_pi1_move_column_has_tooltip():
    """`Move` column header carries a `title=` tooltip naming the window.

    Analyst-register progressive disclosure: the column is a daily-snapshot
    rank delta but the header alone doesn't say *since when*. The title=
    attribute surfaces "Change since yesterday's snapshot" on hover.
    """
    html = LEADERBOARD_HTML.read_text()
    assert re.search(
        r'<th[^>]*title="Change since yesterday\'s snapshot"[^>]*>Move</th>',
        html,
    ), (
        '`Move` column header must carry a `title="Change since yesterday\'s '
        'snapshot"` attribute (S6.1.3 PI-1, Group J).'
    )


def test_pi1_red_divider_rule_threads_tribune_to_standings():
    """A red-divider rule sits between Your Position tribune and standings.

    Lock the canonical adjacent-sibling selector pattern in `style.css` so
    a future cleanup can't accidentally split the tribune block away from
    the standings table without re-establishing the visual thread. Targets
    both the desktop card and the mobile cards wrapper.

    WC Tab Unification P2 flip: selector dropped `.wc-card` from the
    compound when leaderboard.html migrated off `.card.wc-card`. The
    tribune is leaderboard-only, so the broadened `+ .card` adjacent-
    sibling selector still scopes correctly. Color flipped gold→red per
    the new accent doctrine (red as primary on light WC substrates; gold
    demoted to quaternary). DESIGN.md §6 Do major-section separator
    pattern unchanged.
    """
    css = STYLE_CSS.read_text()
    # Adjacent-sibling rule must name both desktop and mobile receivers.
    assert '.your-standing-tribune + .card,' in css, (
        'Red-divider rule must target `.your-standing-tribune + .card` '
        '(desktop standings card; S6.1.3 PI-1, Group J — P2 flipped).'
    )
    assert '.your-standing-tribune + .card + .d-md-none' in css, (
        'Red-divider rule must also target the mobile cards wrapper via '
        '`.your-standing-tribune + .card + .d-md-none` so mobile gets the '
        'same thread.'
    )
    # Regression lock: the pre-P2 `.your-standing-tribune + .card.wc-card`
    # form must not re-appear in a live CSS rule. (`.card.wc-card` may still
    # show up in unrelated rules — this assertion is specific to the
    # adjacent-sibling tribune divider.)
    assert '.your-standing-tribune + .card.wc-card' not in css, (
        'Pre-P2 selector `.your-standing-tribune + .card.wc-card` must not '
        're-appear — P2 flipped to `.your-standing-tribune + .card` in '
        'lockstep with the BOARD migration.'
    )
    # And the rule must actually carry `border-top: 2px solid var(--wc-red)
    # !important` (the DESIGN.md §6 Do major-section separator pattern). The
    # `!important` is required to defeat Bootstrap's `.border-0` utility,
    # which the desktop standings card carries; a non-important declaration
    # would paint only on mobile.
    assert re.search(
        r'\.your-standing-tribune \+ \.card,\s*'
        r'\.your-standing-tribune \+ \.card \+ \.d-md-none\s*\{'
        r'\s*border-top:\s*2px solid var\(--wc-red\)\s*!important\s*;',
        css,
    ), (
        'Red-divider rule must carry '
        '`border-top: 2px solid var(--wc-red) !important;` per DESIGN.md §6 '
        'Do canonical pattern; the !important defeats Bootstrap `.border-0`.'
    )


# ---------------------------------------------------------------------------
# PI-2 locks (Group I): --metal-gold-flat 100% stop retune.
# ---------------------------------------------------------------------------

def test_pi2_metal_gold_flat_dark_stop_is_lifted():
    """`--metal-gold-flat`'s 100% stop is `#A88420`, not `#8A6A1A`.

    Locks the AA-clearing dark anchor on the diagonal trophy gradient.
    Chamber-purple text on the bottom-right pixel-corner used to read
    3.6:1 (sub-AA); the lifted stop clears 4.5:1 with margin.
    """
    css = TOKENS_CSS.read_text()
    assert re.search(
        r'--metal-gold-flat:\s*linear-gradient\(135deg,\s*'
        r'#F2D36B\s+0%,\s*#C9A227\s+45%,\s*#A88420\s+100%\)',
        css,
    ), (
        '`--metal-gold-flat` must terminate at `#A88420` (S6.1.3 PI-2, Group I).'
    )
    # Regression lock: the prior `#8A6A1A 100%` stop must not re-appear in
    # `--metal-gold-flat`. Scoped to the `--metal-gold-flat: linear-gradient(...)`
    # declaration so a future token that legitimately uses `#8A6A1A 100%`
    # elsewhere doesn't false-trip this lock. (`#8A6A1A` still appears as the
    # `--gold-dark` token and at the 78% stop of `--metal-gold`; both intentional.)
    assert re.search(
        r'--metal-gold-flat:\s*linear-gradient\([^;]*#8A6A1A\s+100%',
        css,
    ) is None, (
        'Old `#8A6A1A 100%` stop must not re-appear in `--metal-gold-flat` '
        '— retuned to clear AA at the worst-corner.'
    )


def test_pi2_gold_dark_token_unchanged():
    """`--gold-dark` token itself stays at `#8A6A1A` (only the gradient changed).

    The token is reused as the link-hover color on auth pages where it
    paints on bone at ~5.07:1 (AA-passing). Changing it would ripple
    into a different audit; the gradient fix is surgical.
    """
    css = TOKENS_CSS.read_text()
    # Whitespace-agnostic so a future formatter pass that normalizes the
    # column alignment between `:` and the value doesn't trip the lock.
    assert re.search(r'--gold-dark:\s*#8A6A1A\s*;', css), (
        '`--gold-dark` token must remain `#8A6A1A` — the retune is gradient-only.'
    )


def test_pi2_design_md_documents_diagonal_dark_anchor():
    """DESIGN.md §2 ratifies the new `--metal-gold-flat` dark anchor `#A88420`.

    Without this doc entry, a future contributor reading DESIGN.md alone
    would see `Gold Dark (#8A6A1A): Anchor stop in the metal-gold
    gradient` and assume both gradients terminate at the same value.
    """
    design = DESIGN_MD.read_text()
    assert '#A88420' in design, (
        'DESIGN.md must name the diagonal gradient dark anchor `#A88420` '
        '(S6.1.3 PI-2, Group I).'
    )
    # And the doc must call out *why* the diagonal carries a lifted dark
    # anchor (the bottom-right corner is exactly where text descenders
    # land on a diagonal gradient terminus).
    assert 'worst-corner' in design.lower() or 'bottom-right' in design.lower(), (
        'DESIGN.md must name the worst-corner rationale on the diagonal '
        'dark anchor so future editors can\'t silently roll it back.'
    )


# ---------------------------------------------------------------------------
# PI-3 locks (Group E PI-A): picks card-header eyebrow voice collapse.
# ---------------------------------------------------------------------------

def test_pi3_picks_card_header_eyebrow_collapses_to_the_ballot():
    """Read-only picks card-header eyebrow no longer echoes the H1 state.

    Pre-S6.1.3: both desktop and mobile card-headers carried the same
    {% if deadline_passed %}The Oath is sealed{% else %}Sealed · still
    amendable{% endif %} text — restating the H1 verbatim. The invariant
    "The Ballot" eyebrow now sits as a section anchor; the H1 carries
    the state info.
    """
    html = PICKS_HTML.read_text()
    # The two echoing strings must not appear anywhere in the template.
    assert 'Sealed · still amendable' not in html, (
        'Card-header eyebrow text "Sealed · still amendable" must not '
        're-appear — it echoed the H1 (S6.1.3 PI-3, Group E PI-A).'
    )
    # The other half of the legacy eyebrow ternary ("The Oath is sealed")
    # must also stay out of eyebrow contexts. Scoped to the eyebrow span
    # because the same phrase is the legitimate post-deadline H1 (line 9
    # of picks.html) — a blanket `not in html` would false-positive.
    assert re.search(
        r'<span class="wc-eyebrow">\s*The Oath is sealed\s*</span>',
        html,
    ) is None, (
        'Eyebrow span "The Oath is sealed" must not re-appear in a card-'
        'header context — it echoed the H1 (S6.1.3 PI-3, Group E PI-A). '
        'The H1 itself retains the phrase as the post-deadline title.'
    )
    # The new section anchor must appear at least twice (desktop card-header
    # + mobile card-header) inside `wc-eyebrow` spans.
    matches = re.findall(
        r'<span class="wc-eyebrow">\s*The Ballot\s*</span>',
        html,
    )
    assert len(matches) >= 2, (
        'Both desktop and mobile read-only card-headers must carry '
        '`<span class="wc-eyebrow">The Ballot</span>` (S6.1.3 PI-3, Group E PI-A); '
        f'found {len(matches)}.'
    )


# ---------------------------------------------------------------------------
# PI-4 locks (Group E PI-B): success flash auto-fade animation.
# ---------------------------------------------------------------------------

def test_pi4_success_flash_carries_auto_fade_animation():
    """`.alert.alert-success.alert-dismissible` carries the auto-fade animation.

    Scoped to `.alert-dismissible` so only chrome flash messages decay —
    static page alerts (rare in this codebase) keep their visibility.
    The animation composes with the existing `slideDown` entrance.
    """
    css = STYLE_CSS.read_text()
    assert re.search(
        r'\.alert\.alert-success\.alert-dismissible\s*\{\s*'
        r'animation:\s*slideDown[^,]+,\s*ccc-flash-success-fade',
        css,
    ), (
        '`.alert.alert-success.alert-dismissible` must run the '
        '`ccc-flash-success-fade` animation alongside the existing '
        '`slideDown` entrance (S6.1.3 PI-4, Group E PI-B).'
    )


def test_pi4_flash_fade_keyframes_only_animate_opacity():
    """`@keyframes ccc-flash-success-fade` only animates opacity (and pointer-events).

    The impeccable shared design law bans animating CSS layout properties.
    A keyframes block that touches `max-height` / `padding` / `margin`
    would violate the ban; lock the opacity-only contract.
    """
    css = STYLE_CSS.read_text()
    # Pull the keyframes body and verify only opacity (and pointer-events,
    # which isn't a layout property) get mutated.
    match = re.search(
        r'@keyframes ccc-flash-success-fade\s*\{([^}]*\{[^}]*\}[^}]*\{[^}]*\})',
        css,
        re.DOTALL,
    )
    assert match, (
        '`@keyframes ccc-flash-success-fade` block must exist '
        '(S6.1.3 PI-4, Group E PI-B).'
    )
    body = match.group(1)
    # Positively require `opacity` so an empty/non-fading keyframe block
    # can't false-pass the banned-property check below.
    assert re.search(r'\bopacity\s*:', body), (
        '`@keyframes ccc-flash-success-fade` must animate `opacity` to '
        'implement the intended auto-fade (S6.1.3 PI-4, Group E PI-B).'
    )
    # Allowed properties only: opacity, pointer-events, visibility.
    # Anything else is a layout-animation regression risk.
    # Property-scoped regex: `(?<![a-zA-Z-])` ensures the property name
    # isn't part of a longer identifier — `top:` must not match `stop:`,
    # `height:` must not match `line-height:`, etc. (`max-height` has its
    # own entry in the banned tuple so it's still caught directly.)
    banned = ('max-height', 'height', 'padding', 'margin', 'transform', 'top', 'left')
    for prop in banned:
        assert re.search(rf'(?<![a-zA-Z-]){prop}\s*:', body) is None, (
            f'`@keyframes ccc-flash-success-fade` must not animate `{prop}` '
            '— the impeccable shared design law bans animating CSS layout '
            'properties.'
        )


def test_pi4_reduced_motion_disables_auto_fade():
    """`prefers-reduced-motion` users get the entrance only — no auto-fade.

    The auto-fade is a courtesy for users who don't want flashes hovering;
    users with motion sensitivity disabled get a stable, persistent alert
    they can dismiss manually.
    """
    css = STYLE_CSS.read_text()
    # The reduced-motion block must override `.alert-success.alert-dismissible`
    # specifically (not the broader `.alert` selector) so we don't drop the
    # entrance animation for everyone.
    assert re.search(
        r'@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{\s*'
        r'\.alert\.alert-success\.alert-dismissible\s*\{\s*'
        r'animation:\s*slideDown[^;]+;',
        css,
    ), (
        '`@media (prefers-reduced-motion: reduce)` must reset the success '
        'flash animation to the entrance-only `slideDown` (S6.1.3 PI-4, '
        'Group E PI-B).'
    )
    # And the auto-fade must NOT leak into the reduced-motion override —
    # `[^;]+` in the regex above traverses commas, so a hypothetical
    # `animation: slideDown ..., ccc-flash-success-fade ...;` would
    # false-pass the positive assertion. Extract the specific reduced-
    # motion rule body for `.alert.alert-success.alert-dismissible` and
    # assert the fade keyframe name isn't inside it. (`[^}]+` keeps the
    # capture bounded to the inner rule — the outer media block may
    # contain unrelated selectors, but the inner `{ ... }` is exact.)
    reduced_motion_alert = re.search(
        r'@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{[^{}]*'
        r'\.alert\.alert-success\.alert-dismissible\s*\{([^}]+)\}',
        css,
    )
    assert reduced_motion_alert is not None, (
        'Could not locate the reduced-motion `.alert.alert-success.alert-'
        'dismissible` rule body to verify fade absence.'
    )
    assert 'ccc-flash-success-fade' not in reduced_motion_alert.group(1), (
        '`prefers-reduced-motion` override must not include '
        '`ccc-flash-success-fade`; reduced-motion is entrance-only.'
    )
