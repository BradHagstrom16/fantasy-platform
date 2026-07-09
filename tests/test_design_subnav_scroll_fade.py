"""Sub-nav scroll-fade locks: the edge fades must never lie.

The mobile sub-nav scroll hint regressed once: an unconditional
`mask-image` fade on `.subnav-pills` (max-width: 768px) kept dimming the
last pill ("Rules") even when the strip had nothing to scroll -- a false
affordance -- and kept it dimmed at scroll end when it did overflow. The
fix retired the mask in favor of the JS-gated `.subnav-scroll` edge fades
(toggled via `is-overflow-left` / `is-overflow-right` by the sub-nav
script in base.html), anchored to a wrapper around only the pill scroller
so the left fade cannot overlay the game label at >=576px.

These locks keep that contract: fades hidden by default, revealed only by
the overflow classes, never via an unconditional mask.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STYLE_CSS = REPO_ROOT / 'static' / 'css' / 'style.css'
BASE_HTML = REPO_ROOT / 'templates' / 'base.html'


def _code_only_css() -> str:
    """style.css with /* ... */ comments stripped, so rationale text
    mentioning banned patterns does not false-trip the locks."""
    css = STYLE_CSS.read_text()
    return re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)


# ---------------------------------------------------------------------------
# Lock 1: no unconditional mask fade on the sub-nav scroller
# ---------------------------------------------------------------------------

def test_no_mask_image_on_subnav_rules():
    """Zero `mask-image` declarations inside any subnav-scoped rule.

    A mask fade applies whether or not the strip overflows, so it dims an
    end pill even when there is nothing to scroll to (the original bug).
    Scroll hints on the sub-nav must stay opacity-gated on the JS-toggled
    overflow classes instead. Walks every mask-image declaration and
    resolves its enclosing selector so a reintroduction anywhere in the
    sub-nav family trips immediately.
    """
    code_only = _code_only_css()
    violations = []
    for m in re.finditer(r'(?:-webkit-)?mask-image\s*:', code_only):
        open_idx = code_only.rfind('{', 0, m.start())
        sel_start = max(
            code_only.rfind('}', 0, open_idx),
            code_only.rfind('{', 0, open_idx),
            code_only.rfind(';', 0, open_idx),
        )
        selector = code_only[sel_start + 1:open_idx].strip()
        if 'subnav' in selector:
            violations.append(selector)
    assert violations == [], (
        f'Unconditional mask fade reintroduced on sub-nav rule(s): '
        f'{violations!r}. Use the `.is-overflow-*`-gated `.subnav-scroll` '
        f'edge fades instead.'
    )


# ---------------------------------------------------------------------------
# Lock 2: edge fades are hidden by default and opacity-gated
# ---------------------------------------------------------------------------

def test_edge_fades_hidden_by_default():
    """The shared `.subnav-scroll::before/::after` base rule keeps the
    fades invisible (`opacity: 0`) and untouchable (`pointer-events: none`)
    so end pills stay tappable and nothing fades when the strip fits."""
    code_only = _code_only_css()
    match = re.search(
        r'\.game-subnav\s+\.subnav-scroll::before,\s*'
        r'\.game-subnav\s+\.subnav-scroll::after\s*\{([^}]*)\}',
        code_only,
    )
    assert match is not None, (
        'Expected the shared `.game-subnav .subnav-scroll::before, ::after` '
        'edge-fade base rule in style.css.'
    )
    block = match.group(1)
    assert re.search(r'opacity:\s*0\b', block), (
        f'Edge fades must default to opacity: 0; block={block!r}.'
    )
    assert re.search(r'pointer-events:\s*none', block), (
        f'Edge fades must carry pointer-events: none; block={block!r}.'
    )


def test_edge_fades_gated_on_overflow_classes():
    """Each fade lifts to opacity: 1 only under its JS-toggled overflow
    class -- left fade on `.is-overflow-left`, right on `.is-overflow-right`."""
    code_only = _code_only_css()
    assert re.search(
        r'\.game-subnav\.is-overflow-left\s+\.subnav-scroll::before\s*\{[^}]*opacity:\s*1',
        code_only,
    ), 'Left fade must be gated on `.is-overflow-left`.'
    assert re.search(
        r'\.game-subnav\.is-overflow-right\s+\.subnav-scroll::after\s*\{[^}]*opacity:\s*1',
        code_only,
    ), 'Right fade must be gated on `.is-overflow-right`.'


def test_per_game_fade_tints_cover_both_edges():
    """Every game sub-nav tints both edge fades to its own substrate so the
    fade reads as the strip running off the edge, not a gray smudge."""
    code_only = _code_only_css()
    for game in ('worldcup', 'golf', 'cfb'):
        assert re.search(
            rf'\.subnav-{game}\s+\.subnav-scroll::before\s*\{{[^}}]*linear-gradient\(to left',
            code_only,
        ), f'`.subnav-{game}` is missing its left edge-fade tint.'
        assert re.search(
            rf'\.subnav-{game}\s+\.subnav-scroll::after\s*\{{[^}}]*linear-gradient\(to right',
            code_only,
        ), f'`.subnav-{game}` is missing its right edge-fade tint.'


# ---------------------------------------------------------------------------
# Lock 3: template structure + JS toggles
# ---------------------------------------------------------------------------

def test_every_subnav_pills_wrapped_in_subnav_scroll():
    """Each `.subnav-pills` scroller sits inside a `.subnav-scroll` wrapper.

    The wrapper is the positioning anchor for the edge fades; it wraps
    ONLY the scroller (not the game label), so the left fade lands on the
    pills' actual clip edge at every breakpoint. An unwrapped scroller
    silently loses both fades.
    """
    html = BASE_HTML.read_text()
    pills = list(re.finditer(r'<div class="subnav-pills">', html))
    assert len(pills) == 3, (
        f'Expected one `.subnav-pills` per game sub-nav (3 total), '
        f'found {len(pills)}.'
    )
    for m in pills:
        preceding = html[:m.start()].rstrip()
        assert preceding.endswith('<div class="subnav-scroll">'), (
            'Every `.subnav-pills` must be immediately wrapped by '
            '`<div class="subnav-scroll">` (edge-fade anchor).'
        )


def test_subnav_script_toggles_both_overflow_classes():
    """The sub-nav script gates both fades on real hidden content: right on
    remaining scroll width, left on scrolled-past distance."""
    html = BASE_HTML.read_text()
    assert re.search(
        r"classList\.toggle\('is-overflow-right',\s*hiddenRight\s*>\s*1\)",
        html,
    ), 'Sub-nav script must toggle `is-overflow-right` on remaining width.'
    assert re.search(
        r"classList\.toggle\('is-overflow-left',\s*scroller\.scrollLeft\s*>\s*1\)",
        html,
    ), 'Sub-nav script must toggle `is-overflow-left` on scrollLeft.'
