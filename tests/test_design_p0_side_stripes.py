"""P0 S0.2 — lock: no `border-left/right: Npx` colored side-stripe accent on
CCC platform/WC components, and no `box-shadow: inset Npx 0 0` /
`inset -Npx 0 0` declarations that draw a leading-edge stripe by other
means. Side-stripe accents are an impeccable absolute ban (DESIGN.md,
§6 Don'ts), and the ban applies to the visual effect, not just the CSS
property.

Scope: walks `static/css/style.css` and flags any single-class rule that
declares either form of leading-stripe. Game-specific selectors (Golf
and CFB) are explicitly out of scope for the impeccable design improvement
project (see `docs/superpowers/plans/2026-05-08-...`, §1.6) and are
skipped here.
"""

import re
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'

# Selectors that are out of scope for this project (Golf and CFB blueprints
# are explicitly excluded; their existing patterns stay). Word-boundary
# matches catch every class containing the game name as a word — so
# `.cfb-foo`, `.game-cfb`, `.table-cfb`, `.cfb-card`, etc. all exempt
# without a per-pattern entry.
GAME_SCOPED_PATTERNS = [
    r'\.lives-indicator',
    r'\bcfb\b',              # CFB blueprint (any class containing the cfb word)
    r'\bgolf\b',             # Golf blueprint (any class containing the golf word)
    r'\.col-divider',        # Golf-only column divider between season/tournament data
    r'\.elimination-alert',  # CFB Survivor "you're out" callout
]


def _strip_comments(src: str) -> str:
    """Remove /* ... */ blocks so commented-out examples don't trip the regex."""
    return re.sub(r'/\*.*?\*/', '', src, flags=re.DOTALL)


# Match any flat CSS rule (selector + body). Both groups exclude braces so the
# regex doesn't try to span nested @media/@keyframes blocks; the inner rules
# inside those blocks are matched independently. Selectors can be contextual
# (descendant, child, sibling, comma-separated) — `[^{}]+?` captures the full
# selector string, which the GAME_SCOPED_PATTERNS check then runs over.
_RULE_RE = re.compile(r'([^{}]+?)\s*\{([^{}]*)\}', re.DOTALL)


def _is_game_scoped(selector: str) -> bool:
    return any(re.search(p, selector) for p in GAME_SCOPED_PATTERNS)


def test_no_colored_side_stripes_on_platform_components():
    """Walk style.css. Any rule with `border-left/right: Npx` (N >= 2) outside
    Golf/CFB-scoped blocks is a side-stripe ban violation. The selector match
    is permissive — contextual selectors (e.g. `.table-worldcup .row-current-user > td`)
    and comma-separated selectors are scanned, with the GAME_SCOPED_PATTERNS
    list filtering out the explicit out-of-scope game blocks.
    """
    src = _strip_comments(CSS_PATH.read_text())
    offenders = []
    for rule_match in _RULE_RE.finditer(src):
        selector = rule_match.group(1).strip()
        body = rule_match.group(2)
        if _is_game_scoped(selector):
            continue
        for stripe in re.finditer(r'border-(left|right):\s*([2-9]|[1-9]\d+)px', body):
            offenders.append((selector[:120], stripe.group(1), stripe.group(2)))
    assert not offenders, (
        'Side-stripe ban violations on platform/WC components: '
        f'{offenders}. Replace with full borders, leading icons/numerals, '
        'or background tints.'
    )


def test_no_inset_box_shadow_side_stripes_on_platform_components():
    """The side-stripe ban applies to the visual effect, not just to
    `border-left`/`border-right` declarations. A `box-shadow: ... inset Npx 0 0`
    (N >= 2) draws a left-edge stripe; `... inset -Npx 0 0` draws a right-edge
    stripe. Both are banned on platform/WC components.

    Discovered post-S0.2: `.fixture-row-next` used `box-shadow: inset 3px 0 0`
    to render a 3px red leading accent, slipping the original border-left
    regex. This test closes that loophole — and matches `inset` anywhere
    inside a multi-part `box-shadow` value, not just at the start, so a
    declaration like `box-shadow: 0 2px 8px ..., inset 3px 0 0 ...` is also
    caught.
    """
    src = _strip_comments(CSS_PATH.read_text())
    offenders = []
    for rule_match in _RULE_RE.finditer(src):
        selector = rule_match.group(1).strip()
        body = rule_match.group(2)
        if _is_game_scoped(selector):
            continue
        for shadow_decl in re.finditer(r'box-shadow\s*:\s*([^;]+);', body):
            value = shadow_decl.group(1)
            for stripe in re.finditer(
                r'\binset\s+(-?)([2-9]|[1-9]\d+)px\s+0\s+0', value
            ):
                sign, width = stripe.group(1), stripe.group(2)
                edge = 'right' if sign == '-' else 'left'
                offenders.append((
                    selector[:120],
                    f'inset {sign}{width}px 0 0',
                    edge,
                ))
    assert not offenders, (
        'Inset-box-shadow side-stripe violations on platform/WC components: '
        f'{offenders}. The 3px-leading-accent visual is banned regardless of '
        'whether it is drawn via border-left or box-shadow. Replace with full '
        'borders, leading icons/numerals, or background tints.'
    )


def test_card_border_state_classes_use_full_border_not_side_stripe():
    """`.card.border-{success,danger,warning,primary}` must use a full border
    (`border:` shorthand or all four edges of equal width), not a heavy
    `border-left` accent."""
    src = _strip_comments(CSS_PATH.read_text())
    for class_name in ['border-success', 'border-danger', 'border-warning', 'border-primary']:
        rule_match = re.search(
            rf'\.card\.{class_name}\s*\{{([^}}]+)\}}', src, re.MULTILINE
        )
        if rule_match is None:
            continue  # rule may have been removed entirely
        body = rule_match.group(1)
        bad = re.search(r'border-left:\s*([2-9]|[1-9]\d+)px\b', body)
        assert bad is None, (
            f'.card.{class_name} still uses a heavy border-left side-stripe: '
            f'{body[:200]}'
        )


def test_alert_uses_full_border_not_side_stripe():
    """`.alert` must use a full border, not a `border-left: Npx` (N>=2) accent.
    Bootstrap-style 4px left-stripe alerts violate the impeccable absolute ban."""
    src = _strip_comments(CSS_PATH.read_text())
    rule_match = re.search(r'(?<!\w)\.alert\s*\{([^}]+)\}', src, re.MULTILINE)
    assert rule_match is not None, '.alert rule not found in style.css'
    body = rule_match.group(1)
    bad = re.search(r'border-left:\s*([2-9]|[1-9]\d+)px', body)
    assert bad is None, f'.alert still uses border-left {bad.group(0)}: {body[:200]}'


def test_your_standing_tribune_has_no_side_stripe():
    """`.your-standing-tribune` must not carry a `border-left: Npx` accent.
    P1 S1.1 reshaped the block from .your-standing to .your-standing-tribune;
    the side-stripe ban carries forward."""
    src = _strip_comments(CSS_PATH.read_text())
    rule_match = re.search(
        r'(?<!\w)\.your-standing-tribune\s*\{([^}]+)\}', src, re.MULTILINE
    )
    assert rule_match is not None, \
        '.your-standing-tribune rule not found in style.css'
    body = rule_match.group(1)
    bad = re.search(r'border-left:\s*([2-9]|[1-9]\d+)px', body)
    assert bad is None, \
        f'.your-standing-tribune still has a side-stripe: {bad.group(0)}'
