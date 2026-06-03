"""P0 S0.3 — color-token lock: trophy CTA text declares chamber-purple in CSS.

This is a SOURCE-PATTERN lock, NOT a WCAG AA contrast guarantee. The
assertions only verify that the rule body declares chamber-purple text
(`var(--purple-900)` / `var(--chamber)` / `#1C0A3A`); they do not compute
the rendered contrast ratio against the metal-gold gradient stops.

Rendered contrast against gold-dark (#8A6A1A, the gradient's worst-stop)
is currently ~3.6:1 — below WCAG AA 4.5:1. The DESIGN.md token retune
that lifts the gold floor is tracked in plan §0.4 (P6 S6.1 backlog) and
will close that gap. Until then, the locks below freeze the text-color
half of the fix; pair them with the rendered probe in browser DevTools.

Hover is pinned alongside rest so a future hover-flip can't quietly
re-introduce the white-on-gold bug (~1.5:1 against the lightest stop).

The file has since grown a second family of source-pattern contrast locks
(the pick-summary eyebrow lift); see the dated section comments below.
"""
import re
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'

# Accept any of: var(--purple-900), var(--chamber), or the literal #1C0A3A
# (the DESIGN.md chamber-purple value).
_VALID_TROPHY_TEXT_COLORS = ('var(--purple-900)', 'var(--chamber)', '#1C0A3A', '#1c0a3a')


def _rule_body(css: str, selector: str) -> str | None:
    """Return the body of a standalone rule (line-anchored, no descendant)."""
    pattern = rf'(?m)^{re.escape(selector)}\s*\{{([^}}]+)\}}'
    match = re.search(pattern, css)
    return match.group(1) if match else None


def _has_valid_trophy_text_color(body: str) -> bool:
    """True when the body's `color:` declaration itself is chamber-purple.

    Anchored to the color: declaration (the (?<!-) lookbehind excludes the
    -color property family) so a purple border/shadow can't satisfy the lock
    while the actual text color regresses to bone/white.
    """
    return any(
        re.search(rf'(?<!-)color\s*:\s*{re.escape(token)}', body)
        for token in _VALID_TROPHY_TEXT_COLORS
    )


def test_navbar_trophy_cta_text_color_rest():
    """Navbar `.btn-warning` rest must DECLARE chamber-purple text in source.

    Token-presence check only; rendered AA contrast against the gradient's
    worst-stop is tracked separately (see module docstring).
    """
    css = CSS_PATH.read_text()
    body = _rule_body(css, '.navbar.navbar-dark .btn-warning')
    assert body is not None, '.navbar.navbar-dark .btn-warning rule not found'
    assert _has_valid_trophy_text_color(body), (
        f'Navbar trophy CTA rest must declare chamber-purple text '
        f'(var(--purple-900) / var(--chamber) / #1C0A3A); body was: {body!r}'
    )


def test_navbar_trophy_cta_text_color_hover():
    """Navbar `.btn-warning:hover` must keep the chamber-purple declaration
    in source, never flip to bone/white. White on the gradient's top stop
    (#FFF1B8) renders ~1.5:1 in the browser; this token lock prevents the
    white-on-gold regression at the source level."""
    css = CSS_PATH.read_text()
    body = _rule_body(css, '.navbar.navbar-dark .btn-warning:hover')
    assert body is not None, '.navbar.navbar-dark .btn-warning:hover rule not found'
    assert _has_valid_trophy_text_color(body), (
        f'Navbar trophy CTA hover must keep chamber-purple text '
        f'(no flip to bone/white); body was: {body!r}'
    )


def test_auth_trophy_cta_text_color_rest_and_hover():
    """`body.auth-page .btn-primary` (the trophy CTA on auth pages) must also
    declare chamber-purple text on rest AND hover. Same gradient, same trap.
    Token-presence check only; same rendered-contrast caveat as the navbar
    tests above."""
    css = CSS_PATH.read_text()
    rest = _rule_body(css, 'body.auth-page .btn-primary')
    hover = _rule_body(css, 'body.auth-page .btn-primary:hover')
    assert rest is not None, 'body.auth-page .btn-primary rule not found'
    assert hover is not None, 'body.auth-page .btn-primary:hover rule not found'
    assert _has_valid_trophy_text_color(rest), (
        f'Auth trophy CTA rest must declare chamber-purple text; body was: {rest!r}'
    )
    assert _has_valid_trophy_text_color(hover), (
        f'Auth trophy CTA hover must keep chamber-purple text; body was: {hover!r}'
    )


# --- Pick-summary eyebrow lift (2026-06-03) -------------------------------
# Separate source-pattern lock in the shared contrast-lock file. The
# "Your selections" eyebrow in picks.html sits inside .pick-summary (white
# --bg-card panel); the base .wc-eyebrow color is --bone-mute, a
# dark-substrate token that renders near-invisible on white. The fix joins
# .pick-summary to the grouped light-substrate lift (DESIGN.md §3 scoped-lift
# pattern, same as .wc-card-flush / .player-picks-mobile / -sealed).
# Deliberately NOT via _rule_body: that helper line-anchors selector-then-{,
# so it only matches the terminal selector of a grouped rule and would fail
# spuriously if the group were ever reordered. The position-independent
# substring + brace-scan below survives reordering (precedent:
# test_design_p2_s2_3_1.py's `.team-path > .wc-eyebrow` lock).

def test_pick_summary_eyebrow_light_substrate_lift():
    """`.pick-summary .wc-eyebrow:not(...)` must declare --text-secondary so
    the "Your selections" label stays AA-legible on the white summary panel.
    Guards against the lift selector being dropped from the grouped rule."""
    css = CSS_PATH.read_text()
    selector = '.pick-summary .wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)'
    idx = css.find(selector)
    assert idx != -1, (
        '.pick-summary eyebrow lift selector not found — the bare .wc-eyebrow '
        '(--bone-mute, dark-substrate token) is near-invisible on the white '
        '.pick-summary panel without it'
    )
    # Body of the rule containing the selector: the first {...} block after it
    # (selectors cannot contain braces; rule bodies in this sheet are flat).
    body = css[css.index('{', idx) + 1 : css.index('}', idx)]
    # Match the `color:` declaration specifically; the (?<!-) lookbehind keeps
    # -color variants (background-color, border-color, ...) from satisfying it.
    assert re.search(r'(?<!-)color\s*:\s*var\(--text-secondary\)', body), (
        f'.pick-summary eyebrow lift must use var(--text-secondary); body was: {body!r}'
    )
