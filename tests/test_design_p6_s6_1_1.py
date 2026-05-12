"""S6.1.1 — Cross-phase polish (Iter 1). Layer A locks.

Three PIs in one cluster iteration; each routed in from §0.4 of the
impeccable design improvement plan (P6 §8 docket):

- PI-1 (Group A): `.card.wc-card .wc-eyebrow` contrast lift on the navy
  substrate. The default `var(--bone-mute)` reads ~4.11:1 (sub-AA) over
  the rgba(0,17,46,.8) navy; a `:not()`-scoped lift to bone @ .85 alpha
  brings it to ~7.1:1 without disturbing the `-red` / `-gold` tonal
  variants. Closes S5.1.1 + S4.2.2 + S2.3.1 cross-phase routes; pairs
  with DESIGN.md §3 + §5.5 primitive ratification.

- PI-2 (Group B): site-wide `.text-muted` retire on bone canvas.
  Bootstrap 5.3.3's `.text-muted { color: var(--bs-secondary-color) !important; }`
  resolves the variable against the cascade — redefining it at `:root`
  flips every bone-canvas `.text-muted` to `--text-secondary`. Dark
  substrates already had specific `!important` overrides at :6670 and
  :6728; those keep winning either way. Closes S3.2.1 + S4.3.1
  cross-phase routes.

- PI-3 (Group C): gradient-text retire on the three remaining rules.
  All three violated the impeccable absolute ban + DESIGN.md §6 Don't.
  Site 1 (`.home-shell .recap-rank`) + site 2
  (`.card.wc-card.wc-hero-grad .champion-name`) land on dark substrates
  → solid `var(--gold-light)`. Site 3
  (`.table-worldcup .row-champion-pick .best-finish-champion`) lands on
  cream (#f7e9c2) → solid `var(--gold-dark)` for AA-large at Teko 700 /
  1.4rem. Closes S5.2.1 cross-phase route.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STYLE_CSS = REPO_ROOT / 'static' / 'css' / 'style.css'
DESIGN_MD = REPO_ROOT / 'DESIGN.md'


# ---------------------------------------------------------------------------
# PI-1 locks: .card.wc-card .wc-eyebrow:not(...) contrast lift
# ---------------------------------------------------------------------------

def test_pi1_dark_card_eyebrow_lift_rule_exists():
    """The S6.1.1 contrast-lift rule exists with the exact scope.

    Locks the `:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)` carve-out so
    a future "tidy" pass that drops the variant exclusion can't silently
    flatten the red/gold semantic to bone on every dark-card surface.
    """
    css = STYLE_CSS.read_text()
    match = re.search(
        r'\.card\.wc-card\s+\.wc-eyebrow:not\(\.wc-eyebrow-red\):not\(\.wc-eyebrow-gold\)\s*\{([^}]+)\}',
        css,
    )
    assert match is not None, (
        'Expected `.card.wc-card .wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)` '
        'rule in style.css (S6.1.1 PI-1).'
    )
    block = match.group(1)
    # Bone @ .85 alpha = rgba(243, 239, 230, .85). Lock the exact value so a
    # future refactor that lowers alpha back into the sub-AA band trips the test.
    assert 'rgba(243, 239, 230, .85)' in block, (
        f'PI-1 must paint bone @ .85 alpha (~7.1:1 on #313D53); block={block!r}.'
    )


def test_pi1_base_wc_eyebrow_still_uses_bone_mute():
    """The base `.wc-eyebrow` rule still defaults to `--bone-mute`.

    The S6.1.1 fix is a scoped lift on dark cards only. The bone-canvas
    default (which scoped overrides in `.wc-stat-card.is-lead`,
    `.your-standing-tribune`, `.player-pick-card` re-tint) must stay.
    Lock against a "simpler" refactor that retunes the base color and
    silently breaks the as-built primitive.
    """
    css = STYLE_CSS.read_text()
    match = re.search(
        r'^\.wc-eyebrow\s*\{([^}]+)\}',
        css,
        re.MULTILINE,
    )
    assert match is not None, (
        'Expected the base `.wc-eyebrow` rule in style.css.'
    )
    block = match.group(1)
    assert re.search(r'(?<!-)color:\s*var\(--bone-mute\)', block), (
        f'Base `.wc-eyebrow` color must remain `var(--bone-mute)`; block={block!r}.'
    )


def test_pi1_variant_classes_preserved():
    """The two tonal variants (`.wc-eyebrow-red`, `.wc-eyebrow-gold`) survive.

    A `:not()` carve-out is only meaningful if the variants it excludes
    still exist as named primitives; drop either rule and the carve-out
    becomes dead syntax.
    """
    css = STYLE_CSS.read_text()
    # Property-order agnostic: `[^}]*?` + `(?<!-)color:` lets `color` sit
    # anywhere in the rule block and excludes `background-color:` /
    # `border-color:` false-positives.
    assert re.search(
        r'\.wc-eyebrow-red\s*\{[^}]*?(?<!-)color:\s*var\(--wc-red\)',
        css,
        re.DOTALL,
    ), (
        '`.wc-eyebrow-red` variant must remain a named primitive.'
    )
    assert re.search(
        r'\.wc-eyebrow-gold\s*\{[^}]*?(?<!-)color:\s*var\(--gold-light\)',
        css,
        re.DOTALL,
    ), (
        '`.wc-eyebrow-gold` variant must remain a named primitive.'
    )


def test_pi1_design_md_ratifies_two_primitive_shape():
    """DESIGN.md §3 + §5.5 document the as-built two-primitive eyebrow."""
    design = DESIGN_MD.read_text()
    # §3 Hierarchy bullet ratifies `.admin-eyebrow` and `.wc-eyebrow` distinctly.
    assert '`.admin-eyebrow`' in design and '`.wc-eyebrow`' in design, (
        'DESIGN.md must call out both eyebrow primitives by name.'
    )
    # The doc must explicitly mention the `.wc-eyebrow` variants so a future
    # editor knows they are part of the ratified primitive, not invented stragglers.
    assert '`.wc-eyebrow-red`' in design and '`.wc-eyebrow-gold`' in design, (
        'DESIGN.md must document `.wc-eyebrow-red` + `.wc-eyebrow-gold` variants.'
    )
    # The bone-mute default + dark-card lift must appear in the doc so future
    # work understands the scope rule belongs to the primitive, not to one surface.
    assert 'bone-mute' in design and '.card.wc-card' in design, (
        'DESIGN.md must mention the bone-mute default + .card.wc-card scope lift.'
    )


# ---------------------------------------------------------------------------
# PI-2 locks: site-wide .text-muted retire via --bs-secondary-color cascade
# ---------------------------------------------------------------------------

def test_pi2_root_bs_secondary_color_redirects_to_text_secondary():
    """`:root { --bs-secondary-color: var(--text-secondary); }` exists.

    This is the bone-canvas hook: Bootstrap 5.3.3's
    `.text-muted { color: var(--bs-secondary-color) !important; }` reads
    the variable from the rendering context, so redefining it at `:root`
    propagates to every bone-canvas surface without overriding the
    `!important` rule (no specificity war).
    """
    css = STYLE_CSS.read_text()
    # Search for a :root block that contains the override. Multiple :root
    # blocks may exist in the cascade; assert at least one carries the redirect.
    root_blocks = re.findall(r':root\s*\{([^}]+)\}', css)
    assert any(
        re.search(r'--bs-secondary-color:\s*var\(--text-secondary\)', block)
        for block in root_blocks
    ), (
        'Expected a `:root { --bs-secondary-color: var(--text-secondary); }` '
        'redirect in style.css (S6.1.1 PI-2).'
    )


def test_pi2_dark_surface_overrides_still_win():
    """Pre-existing `!important` rules for dark-surface `.text-muted` survive.

    The S6.1.1 PI-2 fix is bone-canvas only. Dark substrates rely on two
    long-standing `!important` rules that win the cascade regardless of
    the variable redefine. Both must stay in place; deleting either
    would re-surface the same bug class on the navy hub.
    """
    css = STYLE_CSS.read_text()
    assert re.search(
        r'\.card\.wc-card\s+\.text-muted\s*\{[^}]*rgba\(245,\s*241,\s*232,\s*\.82\)[^}]*!important',
        css,
    ), (
        'Expected the pre-existing `.card.wc-card .text-muted` `!important` '
        'lift to bone @ .82 in style.css (originally landed in Plan 3).'
    )
    assert re.search(
        r'\.page-hero\.wc-hero-grad\s+\.hero-subhead\.text-muted\s*\{[^}]*rgba\(245,\s*241,\s*232,\s*\.82\)[^}]*!important',
        css,
    ), (
        'Expected the pre-existing `.page-hero.wc-hero-grad .hero-subhead.text-muted` '
        '`!important` lift in style.css.'
    )


def test_pi2_auth_page_override_unbroken():
    """The pre-existing `body.auth-page` `.text-muted` override still exists.

    S3.2.1 PI-2 patched the auth cluster specifically (italic Newsreader
    + `--text-secondary`). The site-wide retire must not orphan it; auth
    surfaces still want the italic-serif voice that doesn't apply elsewhere.
    """
    css = STYLE_CSS.read_text()
    assert re.search(
        r'body\.auth-page\s+\.auth-subhead,\s*body\.auth-page\s+\.text-muted',
        css,
    ), (
        'The S3.2.1 `body.auth-page` `.text-muted` override must remain in '
        'style.css.'
    )


# ---------------------------------------------------------------------------
# PI-3 locks: gradient-text retire on the three remaining sites
# ---------------------------------------------------------------------------

def test_pi3_no_background_clip_text_rules_remain():
    """Zero `background-clip: text` declarations in style.css.

    Walks the file line-by-line so a stray rule in a future commit trips
    the test immediately, not in the next Layer C critique.

    Lines mentioning the pattern inside a comment block (rationale,
    docstring) don't count; only literal `background-clip: text`
    declarations are violations.
    """
    css = STYLE_CSS.read_text()
    # Strip /* ... */ comments before scanning so rationale text doesn't false-trip.
    code_only = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    violations = [
        line for line in code_only.splitlines()
        if re.search(r'background-clip:\s*text', line)
    ]
    assert violations == [], (
        f'Gradient-text ban (DESIGN.md §6) violated by {len(violations)} '
        f'rule(s): {violations!r}'
    )
    # Same check for the prefixed -webkit- form (Safari/iOS compatibility).
    webkit_violations = [
        line for line in code_only.splitlines()
        if re.search(r'-webkit-background-clip:\s*text', line)
    ]
    assert webkit_violations == [], (
        f'Prefixed `-webkit-background-clip: text` violations: {webkit_violations!r}'
    )


def test_pi3_recap_rank_uses_solid_gold_light():
    """`.home-shell .recap-rank` paints solid `var(--gold-light)`."""
    css = STYLE_CSS.read_text()
    match = re.search(
        r'\.home-shell\s+\.recap-rank\s*\{([^}]+)\}',
        css,
    )
    assert match is not None
    block = match.group(1)
    assert re.search(r'(?<!-)color:\s*var\(--gold-light\)', block), (
        f'`.home-shell .recap-rank` must paint solid gold-light; block={block!r}.'
    )
    # And no leftover transparent / gradient declarations.
    assert 'color: transparent' not in block, (
        f'`color: transparent` leftover from gradient-text recipe; block={block!r}.'
    )
    assert 'var(--metal-gold)' not in block, (
        f'`var(--metal-gold)` background leftover; block={block!r}.'
    )


def test_pi3_champion_name_dark_hero_uses_solid_gold_light():
    """`.card.wc-card.wc-hero-grad .champion-name` paints solid `--gold-light`."""
    css = STYLE_CSS.read_text()
    match = re.search(
        r'\.card\.wc-card\.wc-hero-grad\s+\.champion-name\s*\{([^}]+)\}',
        css,
    )
    assert match is not None
    block = match.group(1)
    assert re.search(r'(?<!-)color:\s*var\(--gold-light\)', block), (
        f'Champion name on dark hero must paint solid gold-light; block={block!r}.'
    )
    assert 'color: transparent' not in block
    assert 'var(--metal-gold)' not in block


def test_pi3_best_finish_champion_cream_uses_solid_gold_dark():
    """`.table-worldcup .row-champion-pick .best-finish-champion` paints gold-dark.

    The substrate here is cream (#f7e9c2 per the row's `> td` rule), not
    dark — `--gold-light` would wash out. `--gold-dark` lands ~4.2:1 and
    qualifies for AA-large at Teko 700 / 22.4px.
    """
    css = STYLE_CSS.read_text()
    match = re.search(
        r'\.table-worldcup\s+\.row-champion-pick\s+\.best-finish-champion\s*\{([^}]+)\}',
        css,
    )
    assert match is not None
    block = match.group(1)
    assert re.search(r'(?<!-)color:\s*var\(--gold-dark\)', block), (
        f'Champion-row label on cream must paint solid gold-dark; block={block!r}.'
    )
    assert 'color: transparent' not in block
    assert 'var(--metal-gold-flat)' not in block
