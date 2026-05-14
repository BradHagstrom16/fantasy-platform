"""WC Tab Unification - Phase 5 (final `.card.wc-card` retirement) regression locks.

P5 closes the WC tab unification project by retiring the `.card.wc-card`
substrate primitive and re-homing the post-tournament champion banner onto a
dedicated `.wc-champion-banner` primitive. Every WC tab body now sits on the
Casual-Light pattern (white `.card` / `.wc-stat-card` on bone); the navy
substrate survives only on the ceremonial champion banner.

What ships:

- Every `.card.wc-card`-scoped rule retires from `static/css/style.css` along
  with the substrate primitive itself. The independent zero-padding utility
  `.card.wc-card-flush` is preserved (consumed standalone by `team_detail.html`
  post-P3.5).
- A new `.wc-champion-banner` primitive bakes in the navy substrate that the
  retired `.card.wc-card` used to provide. The three champion-* descendants
  (`.champion-flag`, `.champion-name`, `.champion-retrospect`) re-scope onto
  it, as do the two contrast lifts the banner actually consumed
  (`.text-muted` and `.wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)`).
- `_home_post.html` flips its class string from `card wc-card wc-hero-grad
  mb-4 animate-in` to `wc-champion-banner mb-4 animate-in`.

These tests pin the retirement. Regex idioms inherit the P3 / P3.5 / P4
hardening: `^...` + `re.MULTILINE` start-of-line anchoring on CSS scans;
property-anchored `(?<![-\\w])` lookbehinds; forbidden-list `\\s*[,{]`
terminators so a selector listed in a comma group still trips the assertion.
"""
from pathlib import Path
import re


ROOT = Path(__file__).parent.parent
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'
TEMPLATE_PATH = (
    ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / '_home_post.html'
)

CSS = CSS_PATH.read_text()
TEMPLATE = TEMPLATE_PATH.read_text()


# ---------------------------------------------------------------------------
# PI-1: zero `.card.wc-card` rule heads in style.css.
# ---------------------------------------------------------------------------
# Broad project-closing lock. Walks every line in style.css; any rule head
# starting with `.card.wc-card` (NOT `.card.wc-card-flush`, which is the
# preserved zero-padding utility) means the substrate primitive re-appeared.
# The negative lookahead `(?![-\\w])` after `wc-card` distinguishes the bare
# `.card.wc-card` family from the `.card.wc-card-flush` independent utility.

def test_pi1_zero_card_wc_card_rule_heads_in_style_css():
    """`static/css/style.css` carries zero `.card.wc-card`-scoped rule heads.

    The `.card.wc-card-flush` zero-padding utility is the only allowed
    exception; it survives P5 as an independent Bootstrap `.card` modifier
    used standalone by `team_detail.html` (no longer compounded with
    `.wc-card`).
    """
    rule_heads = re.findall(
        r'^\.card\.wc-card(?![-\w])[^{]*\{',
        CSS,
        re.MULTILINE,
    )
    assert rule_heads == [], (
        f'Expected zero `.card.wc-card`-scoped rule heads in style.css '
        f'post-P5 retirement; found {len(rule_heads)}: {rule_heads!r}. '
        f'The substrate primitive was retired; any re-introduction must '
        f'go through DESIGN.md and the WC tab unification doctrine.'
    )


# ---------------------------------------------------------------------------
# PI-2: `.wc-champion-banner` base rule exists with substrate properties.
# ---------------------------------------------------------------------------

def test_pi2_wc_champion_banner_substrate_rule_exists():
    """The new dedicated primitive carries the navy substrate the banner needs.

    Baked-in declarations that mirror the retired `.card.wc-card` recipe:
    navy `.8 alpha` background, bone-alpha hairline border, 8px radius,
    1rem padding. The gradient (the `.wc-hero-grad` half of the old
    compound) is not load-bearing on the banner — verified during P5
    planning: the prior `.card.wc-card.wc-hero-grad` compound only scoped
    the champion-* descendants, never the substrate itself.
    """
    match = re.search(
        r'^\.wc-champion-banner\s*\{([^}]+)\}',
        CSS,
        re.MULTILINE,
    )
    assert match is not None, (
        'Expected `.wc-champion-banner` rule in style.css (P5 primitive).'
    )
    block = match.group(1)
    assert 'background: rgba(0, 17, 46, .8)' in block, (
        f'Banner substrate must paint the navy `.8 alpha` background that '
        f'the retired `.card.wc-card` provided; block={block!r}.'
    )
    assert 'border-radius: 8px' in block, (
        f'8px radius expected; block={block!r}.'
    )
    assert 'padding: 1rem' in block, (
        f'1rem padding expected; block={block!r}.'
    )


# ---------------------------------------------------------------------------
# PI-3: `_home_post.html` carries `wc-champion-banner` and zero `wc-card`.
# ---------------------------------------------------------------------------

def test_pi3_home_post_carries_wc_champion_banner_class():
    """The champion banner div uses the new primitive class.

    Template grep: the only `<div class="..."` wrapper at the top of
    `_home_post.html` should use `wc-champion-banner`, not the legacy
    `card wc-card wc-hero-grad` compound.
    """
    assert 'wc-champion-banner' in TEMPLATE, (
        '`_home_post.html` must carry the `wc-champion-banner` primitive '
        'on the champion banner div (P5 migration).'
    )


def test_pi3_home_post_carries_no_wc_card_token():
    """`_home_post.html` markup contains zero `wc-card` class tokens.

    Distinct from `wc-card-flush` (zero-padding utility — also not used in
    this template) and from the legacy `wc-card` token P5 retired.
    Negative lock against a partial-revert that flips back to `card
    wc-card ...` somewhere in the file.
    """
    # `\bwc-card\b` matches the bare token; lookahead excludes -flush /
    # -<anything-else> compound suffixes.
    occurrences = re.findall(r'\bwc-card(?![-\w])', TEMPLATE)
    assert occurrences == [], (
        f'`_home_post.html` must carry zero bare `wc-card` tokens post-P5; '
        f'found {len(occurrences)}: {occurrences!r}.'
    )


# ---------------------------------------------------------------------------
# PI-4 + PI-5: champion-banner-scoped consumer rules re-homed onto primitive.
# ---------------------------------------------------------------------------

def test_pi4_wc_champion_banner_eyebrow_lift_rule_exists():
    """`.wc-champion-banner .wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)`
    paints bone @ .85 alpha for AA contrast on the navy substrate.

    Re-homed from `.card.wc-card .wc-eyebrow:not(...)` in P5. The S6.1.1
    PI-1 invariant (bone @ .85 on dark surfaces, with red/gold variants
    preserving their semantic) still holds; only the parent selector
    changed.
    """
    match = re.search(
        r'^\.wc-champion-banner\s+\.wc-eyebrow:not\(\.wc-eyebrow-red\):not\(\.wc-eyebrow-gold\)\s*\{([^}]+)\}',
        CSS,
        re.MULTILINE,
    )
    assert match is not None, (
        'Expected `.wc-champion-banner .wc-eyebrow:not(.wc-eyebrow-red)'
        ':not(.wc-eyebrow-gold)` rule in style.css (P5 re-home of '
        'S6.1.1 PI-1).'
    )
    block = match.group(1)
    assert re.search(
        r'(?<![-\w])color:\s*rgba\(243,\s*239,\s*230,\s*\.85\)',
        block,
    ), (
        f'Eyebrow lift must paint bone @ .85 alpha (~7.1:1 on the navy '
        f'substrate); block={block!r}.'
    )


def test_pi5_wc_champion_banner_text_muted_lift_rule_exists():
    """`.wc-champion-banner .text-muted` paints bone @ .82 alpha `!important`.

    Re-homed from `.card.wc-card .text-muted`. Bootstrap's `.text-muted`
    ships `!important`, so the override needs the same modifier. Covers
    both the `{% if champion_team %}` summary line and the defensive
    `{% else %}` "Champion not yet declared" fallback.
    """
    match = re.search(
        r'^\.wc-champion-banner\s+\.text-muted\s*\{([^}]+)\}',
        CSS,
        re.MULTILINE,
    )
    assert match is not None, (
        'Expected `.wc-champion-banner .text-muted` rule in style.css '
        '(P5 re-home of Plan 3 dark-surface lift).'
    )
    block = match.group(1)
    assert re.search(
        r'(?<![-\w])color:\s*rgba\(245,\s*241,\s*232,\s*\.82\)\s*!important',
        block,
    ), (
        f'Banner `.text-muted` must paint bone @ .82 alpha with `!important` '
        f'so Bootstrap`s !important override loses cleanly; block={block!r}.'
    )


# ---------------------------------------------------------------------------
# PI-6: Negative lock - retired `.card.wc-card` rules must not re-appear.
# ---------------------------------------------------------------------------
# Forbidden-rule pattern with `\\s*[,{]` terminator so a selector listed
# in a comma group still trips the assertion. Mirrors the P3 / P3.5 / P4
# forbidden-list idiom.

def test_pi6_forbidden_card_wc_card_rules_remain_retired():
    """Specific `.card.wc-card`-scoped rules retired in P5 must not re-appear.

    The broad PI-1 lock covers any new `.card.wc-card`-rooted rule head;
    this narrower negative lock names the specific selectors P5 retired
    so a future "tidy" pass that recreates them under a different rule-
    head shape (e.g., comma-grouped) still trips.
    """
    forbidden_patterns = [
        # Substrate primitive + hover.
        r'^\.card\.wc-card\s*[,{]',
        r'^\.card\.wc-card:hover\s*[,{]',
        # Bone-on-navy contrast lifts re-homed onto `.wc-champion-banner`.
        r'^\.card\.wc-card\s+\.text-muted\s*[,{]',
        r'^\.card\.wc-card\s+\.wc-eyebrow:not\(',
        # Champion-* descendants re-scoped onto `.wc-champion-banner`.
        r'^\.card\.wc-card\.wc-hero-grad\s+\.champion-flag\s*[,{]',
        r'^\.card\.wc-card\.wc-hero-grad\s+\.champion-name\s*[,{]',
        r'^\.card\.wc-card\.wc-hero-grad\s+\.champion-retrospect\s*[,{]',
        # Orphan rules from prior phases retired in P5.
        r'^\.card\.wc-card\s+\.wc-numeral\s*[,{]',
        r'^\.card\.wc-card:not\(\.player-picks-desktop\)\s+\.table',
        r'^\.card\.wc-card\s+\.btn-outline-secondary\s*[,{]',
        r'^\.card\.wc-card\s+\.tier-mobile-card\s+\.text-muted\s*[,{]',
        r'^\.card\.wc-card\s+\.table-worldcup\s+\.row-current-user\s*>\s*td\s+a\s*[,{]',
        r'^\.card\.wc-card\.player-picks-desktop\s+\.table-worldcup',
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*\.row\s+\.text-success\s*[,{]',
        r'^\.card\.wc-card\s+\.fixture-pts\.text-success\s*[,{]',
        r'^\.card\.wc-card\s*>\s*\.card-body\s*>\s*\.row\s+\.text-danger\s*[,{]',
        r'^\.card\.wc-card\s+\.fixture-pts\.text-danger\s*[,{]',
    ]
    violations = []
    for pattern in forbidden_patterns:
        if re.search(pattern, CSS, re.MULTILINE):
            violations.append(pattern)
    assert violations == [], (
        f'Forbidden `.card.wc-card` rules re-appeared in style.css: '
        f'{violations!r}. P5 retired these along with the substrate '
        f'primitive; restore via DESIGN.md doctrine update if intentional.'
    )


# ---------------------------------------------------------------------------
# PI-7: champion-* descendants re-homed onto `.wc-champion-banner`.
# ---------------------------------------------------------------------------

def test_pi7_wc_champion_banner_champion_flag_rule_exists():
    """`.wc-champion-banner .champion-flag` re-homed from the dark-card compound."""
    assert '.wc-champion-banner .champion-flag {' in CSS, (
        'Expected `.wc-champion-banner .champion-flag` rule (P5 re-home).'
    )


def test_pi7_wc_champion_banner_champion_name_rule_exists():
    """`.wc-champion-banner .champion-name` paints solid `--gold-light`."""
    match = re.search(
        r'^\.wc-champion-banner\s+\.champion-name\s*\{([^}]+)\}',
        CSS,
        re.MULTILINE,
    )
    assert match is not None, (
        'Expected `.wc-champion-banner .champion-name` rule (P5 re-home).'
    )
    block = match.group(1)
    assert re.search(r'(?<![-\w])color:\s*var\(--gold-light\)', block), (
        f'Champion name must paint solid `--gold-light` (P6 S6.1.1 PI-3 '
        f'gradient-text retire); block={block!r}.'
    )


def test_pi7_wc_champion_banner_champion_retrospect_rule_exists():
    """`.wc-champion-banner .champion-retrospect` carries Newsreader italic."""
    match = re.search(
        r'^\.wc-champion-banner\s+\.champion-retrospect\s*\{([^}]+)\}',
        CSS,
        re.MULTILINE,
    )
    assert match is not None, (
        'Expected `.wc-champion-banner .champion-retrospect` rule (P5 re-home).'
    )
    block = match.group(1)
    assert 'var(--font-news)' in block, (
        f'Newsreader family required for the Tribune editorial register; '
        f'block={block!r}.'
    )
    assert 'italic' in block, (
        f'Italic required; block={block!r}.'
    )
