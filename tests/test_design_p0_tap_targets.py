"""P0 S0.3 — lock: mobile tap-target floor 44x44.
WCAG 2.5.5 / 2.5.8 + DESIGN.md mobile-first floor.

These tests are source-pattern locks. Layer A — they don't replace the
Playwright MCP rendered-rect probe used during the session, but they keep
the CSS from regressing in source.
"""
import re
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'


def _rule_min_height(css: str, selector: str) -> str | None:
    """Return the `min-height` value declared on a standalone selector rule,
    or None if not declared.

    Anchors at line-start to avoid matching `.descendant .selector { ... }`
    rules (e.g., `.wc-stats-pills .subnav-pill`) — those are separate rules
    that don't constitute a base declaration of the selector.
    """
    pattern = rf'(?m)^{re.escape(selector)}\s*\{{([^}}]+)\}}'
    match = re.search(pattern, css)
    if not match:
        return None
    body = match.group(1)
    mh = re.search(r'min-height:\s*([^;]+);', body)
    return mh.group(1).strip() if mh else None


def _accepts_44px(value: str) -> bool:
    """A min-height value satisfies the 44px floor if it declares 44px / 2.75rem
    or anything visibly larger (48px, 3rem, ...)."""
    if value is None:
        return False
    v = value.strip()
    if v in ('44px', '2.75rem', '48px', '3rem', '52px', '3.25rem'):
        return True
    return any(token in v for token in ('44px', '2.75rem', '48px', '3rem'))


def _rule_value(css: str, selector: str, prop: str) -> str | None:
    """Read a single property's value from the standalone selector rule."""
    pattern = rf'(?m)^{re.escape(selector)}\s*\{{([^}}]+)\}}'
    match = re.search(pattern, css)
    if not match:
        return None
    body = match.group(1)
    decl = re.search(rf'{re.escape(prop)}:\s*([^;]+);', body)
    return decl.group(1).strip() if decl else None


def test_subnav_pill_min_height_44px():
    """`.subnav-pill` (the per-game sub-nav pill bar) must declare a 44px floor.

    Six pills sit in a horizontally-scrolling band under the navbar on every
    WC page; pre-fix they rendered ~30px tall at 375 viewport, well below
    the WCAG 2.5.8 24x24 SC and below the DESIGN.md 44x44 mobile-first floor.
    """
    css = CSS_PATH.read_text()
    mh = _rule_min_height(css, '.subnav-pill')
    assert mh is not None, '.subnav-pill must declare min-height (44px floor)'
    assert _accepts_44px(mh), f'.subnav-pill min-height must be ≥ 44px / 2.75rem; found: {mh!r}'


def test_subnav_pill_min_width_44px():
    """`.subnav-pill` must declare a 44px min-width as well.

    The shortest label ("Hub") rendered 36px wide pre-min-width, failing the
    WCAG 2.5.5 (AAA) target-size spec. min-width: 44px keeps every pill
    square-or-wider regardless of label length.
    """
    css = CSS_PATH.read_text()
    mw = _rule_value(css, '.subnav-pill', 'min-width')
    assert mw is not None, '.subnav-pill must declare min-width (44px floor)'
    assert _accepts_44px(mw), f'.subnav-pill min-width must be ≥ 44px / 2.75rem; found: {mw!r}'


def test_subnav_pill_mobile_override_keeps_44px_floor():
    """The `@media (max-width: 575.98px)` override of `.subnav-pill` must NOT
    drop the min-height back below the 44px floor.

    The mobile override compacts font-size + padding to fit 6 pills on 375px
    without scroll; it must keep the touch floor.
    """
    css = CSS_PATH.read_text()
    # Find the mobile-scoped subnav-pill rule body
    pattern = r'@media\s*\([^)]*max-width:\s*575\.98px[^)]*\)\s*\{[^@]*?\.subnav-pill\s*\{([^}]+)\}'
    match = re.search(pattern, css, re.DOTALL)
    if match is None:
        # If the override block doesn't redeclare min-height, the outer
        # rule's min-height carries through — which is acceptable.
        return
    body = match.group(1)
    mh_decl = re.search(r'min-height:\s*([^;]+);', body)
    if mh_decl is None:
        # Override doesn't touch min-height; outer rule carries through.
        return
    assert _accepts_44px(mh_decl.group(1).strip()), (
        f'.subnav-pill mobile override must not drop min-height below 44px; '
        f'found: {mh_decl.group(1)!r}'
    )


def test_leaderboard_card_link_uses_whole_card_pattern():
    """Mobile leaderboard cards must use whole-card-as-link, not a nested
    name-string anchor (which rendered 26px tall pre-fix).

    Heuristic: the mobile section is wrapped in `<a class="... leaderboard-card ...">`
    rather than `<div class="card ... leaderboard-card">` containing a small
    inline `<a>`.
    """
    template = (
        Path(__file__).parent.parent
        / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'leaderboard.html'
    )
    src = template.read_text()
    # Find the mobile cards marker and scope the assertions to the source AFTER
    # it, so an unrelated `leaderboard-card-link` anchor elsewhere in the file
    # cannot satisfy this lock if the mobile section regresses.
    mobile_marker = re.search(
        r'<!--\s*Mobile cards.*?-->|{#\s*Mobile cards.*?#}',
        src,
        re.DOTALL | re.IGNORECASE,
    )
    assert mobile_marker is not None, (
        'Mobile cards marker not found in leaderboard.html — the test cannot '
        'verify that the whole-card-as-link pattern lives in the mobile section.'
    )
    mobile_src = src[mobile_marker.end():]
    assert 'leaderboard-card-link' in mobile_src, (
        'Expected `.leaderboard-card-link` class used to indicate whole-card-as-link '
        'pattern in leaderboard.html mobile section.'
    )
    # And the wrapping element of the per-row mobile card must be an anchor.
    anchor_pattern = r'<a[^>]+class="[^"]*\bleaderboard-card-link\b'
    assert re.search(anchor_pattern, mobile_src), (
        'Mobile leaderboard card must be wrapped in <a class="... leaderboard-card-link ...">; '
        'the inner-name-only <a> pattern fails the 44x44 tap-target floor.'
    )


def test_leaderboard_card_link_neutralizes_default_link_style():
    """`.leaderboard-card-link` must declare color: inherit + text-decoration: none
    so the navy WC card surface keeps its tribune typography rather than
    flipping to default-blue + underline."""
    css = CSS_PATH.read_text()
    pattern = r'\.leaderboard-card-link\s*\{([^}]+)\}'
    match = re.search(pattern, css)
    assert match is not None, '.leaderboard-card-link rule must exist in style.css'
    body = match.group(1)
    assert 'color: inherit' in body, '.leaderboard-card-link must declare color: inherit'
    assert 'text-decoration: none' in body, '.leaderboard-card-link must declare text-decoration: none'


def test_leaderboard_card_link_has_focus_visible_outline():
    """`.leaderboard-card-link:focus-visible` must declare a brand-tinted outline.
    Whole-card-as-link removes the inner-anchor focus ring; we must put one back."""
    css = CSS_PATH.read_text()
    pattern = r'\.leaderboard-card-link:focus-visible\s*\{([^}]+)\}'
    match = re.search(pattern, css)
    assert match is not None, (
        '.leaderboard-card-link:focus-visible rule must exist (keyboard focus '
        'must remain visible after the anchor moves to the card root).'
    )
    body = match.group(1)
    assert 'outline' in body, '.leaderboard-card-link:focus-visible must declare an outline'
