"""P0 S0.3 — lock: trophy CTA text on metal-gold gradient meets WCAG AA contrast.

The metal-gold gradient runs from gold-dark (#8A6A1A) through commish-gold
(#C9A227) to gold-hi (#FFF1B8). White text on the lightest stop reads
~1.5:1. The DESIGN.md trophy contract requires chamber-purple text:
`color: var(--purple-900)` (#1C0A3A) — that yields ~14:1 against the
darkest stop and ~9:1 against the lightest, comfortably above 4.5:1.

This test pins both rest and hover so a future hover-flip can't quietly
re-introduce the contrast bug.
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
    return any(token in body for token in _VALID_TROPHY_TEXT_COLORS)


def test_navbar_trophy_cta_text_color_rest():
    """Navbar `.btn-warning` rest must declare chamber-purple text on gold."""
    css = CSS_PATH.read_text()
    body = _rule_body(css, '.navbar.navbar-dark .btn-warning')
    assert body is not None, '.navbar.navbar-dark .btn-warning rule not found'
    assert _has_valid_trophy_text_color(body), (
        f'Navbar trophy CTA rest must declare chamber-purple text '
        f'(var(--purple-900) / var(--chamber) / #1C0A3A); body was: {body!r}'
    )


def test_navbar_trophy_cta_text_color_hover():
    """Navbar `.btn-warning:hover` must keep chamber-purple text — never flip
    to bone/white. The metal-gold gradient's top stop (#FFF1B8) renders
    white-on-gold at ~1.5:1; chamber-purple stays comfortably above 4.5:1."""
    css = CSS_PATH.read_text()
    body = _rule_body(css, '.navbar.navbar-dark .btn-warning:hover')
    assert body is not None, '.navbar.navbar-dark .btn-warning:hover rule not found'
    assert _has_valid_trophy_text_color(body), (
        f'Navbar trophy CTA hover must keep chamber-purple text '
        f'(no flip to bone/white); body was: {body!r}'
    )


def test_auth_trophy_cta_text_color_rest_and_hover():
    """`body.auth-page .btn-primary` (the trophy CTA on auth pages) must also
    keep chamber-purple text on rest AND hover. Same gradient, same trap."""
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
