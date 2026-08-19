"""Undercard layout invariants (P0 fixes, 2026-08-19).

Two homepage requirements Brad set as P0 for the co-headlined lounge, both
CSS-only and both easy to regress with a one-line edit:

1. The two headliner cards must be EXACTLY the same size in every state —
   neither the larger bill. Equal width already came from the paired grid's
   `minmax(0, 1fr)` columns; equal height comes from `align-items: stretch`
   on `.hl-duo--paired`. `align-items: start` (the pre-fix value) let each
   card size to its own content and is what these locks forbid.
2. The "Your Games" tile strip must sit on one line, whatever the bill's
   size — a count-agnostic auto-flow row on desktop/tablet, a 2-up grid on
   phones. The old fixed `1fr 1fr 1fr` dropped the 4th tile to a 2nd line.

The scans read the compiled HOME region of style.css, so they bind the real
shipped rules rather than a template's class list.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _home_region():
    src = (REPO / 'static/css/style.css').read_text()
    start = src.index('/* === HOME (CCC)')
    end = src.index('/* === HOME — END')
    return src[start:end]


def _rule_body(region, selector):
    """The declaration block for the first `selector {` in `region`."""
    idx = region.index(selector + ' {')
    open_brace = region.index('{', idx)
    close_brace = region.index('}', open_brace)
    return region[open_brace + 1:close_brace]


def test_paired_headliners_are_equal_height():
    """`.hl-duo--paired` stretches both cards to the taller card's height."""
    region = _home_region()
    body = _rule_body(region, '.home-shell .hl-duo--paired')
    assert re.search(r'align-items:\s*stretch', body), (
        "`.home-shell .hl-duo--paired` must set `align-items: stretch` so the "
        "two headliner cards render at equal height (Brad P0: neither the "
        "larger bill). `align-items: start` lets each card size to its own "
        "content and reintroduces the mismatch."
    )
    # The paired grid must keep its equal-width columns too.
    assert 'minmax(0, 1fr) minmax(0, 1fr)' in body, (
        "`.home-shell .hl-duo--paired` must keep two equal `minmax(0, 1fr)` "
        "columns so the cards are equal WIDTH as well as height."
    )


def test_game_tiles_stay_on_one_row():
    """`.court-games` lays every tile on one line, count-agnostically."""
    region = _home_region()
    body = _rule_body(region, '.home-shell .court-games')
    assert re.search(r'grid-auto-flow:\s*column', body), (
        "`.home-shell .court-games` must use `grid-auto-flow: column` so the "
        "game tiles stay on one row regardless of how many games are billed "
        "(Brad P0: the 4 tiles must not wrap). A fixed `grid-template-columns` "
        "count wraps the tile beyond that count to a second line."
    )
    assert re.search(r'grid-auto-columns:\s*minmax\(0,\s*1fr\)', body), (
        "`.home-shell .court-games` must size auto columns as `minmax(0, 1fr)` "
        "so every tile shares equal width on the single row."
    )


def test_game_tiles_wrap_two_up_on_phones():
    """Phones fall back to a 2-up grid rather than a cramped single row."""
    region = _home_region()
    # The small-screen override lives in a `max-width: 559.98px` media block.
    m = re.search(
        r'@media\s*\(max-width:\s*559\.98px\)\s*\{.*?\.home-shell\s+\.court-games\s*\{'
        r'(?P<body>.*?)\}',
        region,
        re.DOTALL,
    )
    assert m, (
        "Expected a `@media (max-width: 559.98px)` rule for "
        "`.home-shell .court-games` so phones get a 2-up grid instead of a "
        "cramped one-line row of tiles."
    )
    body = m.group('body')
    assert 'grid-auto-flow: row' in body, (
        "The phone `.court-games` override must reset `grid-auto-flow: row` — "
        "without it the desktop `grid-auto-flow: column` stays in effect and "
        "the explicit 2-column template does not lay the tiles out 2-up."
    )
    assert 'grid-template-columns: 1fr 1fr' in body, (
        "The phone `.court-games` override must set "
        "`grid-template-columns: 1fr 1fr` (a clean 2×2 for four tiles)."
    )
