"""P2 S2.1.2 regression locks — second iteration of the home-live cluster.

Layer A (per plan §1.3) source-pattern locks for the four Priority Issues
landed in S2.1.2. Each test pins a structural decision the impeccable
critique surfaced as P1/P2 and that S2.1.2 closed.

Iteration map:
- PI-1 (`$impeccable adapt`): `.sec-head .more` links pad to a 44x44 hit area.
- PI-2 (`$impeccable clarify` + CSS): dossier-stamp moves out of absolute
  positioning (was overlapping rank-meta on narrow viewports) and drops the
  spy-register "Classified" framing for "Council Filings" — Tribune voice.
- PI-3 (`$impeccable layout`): SUPERSEDED. S2.1.2 pushed Recent Results
  full-width below the dossier/leaderboard pair to stop the *right* rail
  starving under a 4-line Commish note. PR #79 added the nine-nation roster
  to the dossier, so the *left* column now runs long and the right rail
  starved instead. The live state moved to a `.home-live-grid` (parallel to
  `.home-pre-grid`) whose right rail carries the leaderboard THEN Recent
  Results, rebalancing the columns. The Commish note still stays OUT of the
  rail (S2.1.2's actual lesson). Mobile collapses to source order
  (dossier → leaderboard → results → narrative → tiles).
- PI-4 (`$impeccable clarify`): the "Also Today" eyebrow over neutral
  results promised a temporal anchor the rows never delivered; renamed to
  "Around the Tournament" so the editorial register stays honest.
"""
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()
HOME_LIVE = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_home_live.html').read_text()
DOSSIER = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_dossier_card.html').read_text()
RECENT = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_recent_results.html').read_text()


# ---------------------------------------------------------------------------
# PI-1: section "more" links satisfy the 44x44 tap-target floor.
# ---------------------------------------------------------------------------

def test_sec_head_more_link_meets_44x44_tap_floor():
    """`.home-shell .sec-head .more` must declare a 44x44 minimum hit area
    (PRODUCT.md mobile-first floor). The negative-margin trick keeps the
    visual baseline aligned with the section title at the original 22px
    rendered size."""
    block = _css_block(CSS, '.home-shell .sec-head .more')
    assert block, '.home-shell .sec-head .more rule missing'
    assert 'min-height: 44px' in block, (
        '.home-shell .sec-head .more dropped the 44px height floor; mobile '
        'tap-targets regressed below WCAG 2.5.5.'
    )
    assert 'min-width: 44px' in block, (
        '.home-shell .sec-head .more dropped the 44px width floor.'
    )
    assert 'display: inline-flex' in block, (
        '.home-shell .sec-head .more must use inline-flex so padding centers '
        'the text vertically inside the 44px hit area.'
    )


def test_sec_head_more_link_has_focus_visible_ring():
    """Keyboard users need a visible focus ring on the only nav-out anchor
    in each home section. Heuristic 7 (Flexibility/Efficiency) flagged this."""
    assert '.home-shell .sec-head .more:focus-visible' in CSS


# ---------------------------------------------------------------------------
# PI-2: dossier-stamp register + mobile collision.
# ---------------------------------------------------------------------------

def test_dossier_stamp_drops_classified_register():
    """"Classified" is intelligence-file metaphor on a Tribune surface — the
    register-shift the S2.1.1 critique flagged and S2.1.2 closes. The new
    eyebrow stays tribune voice ("Council Filings") rather than spy voice."""
    assert 'Classified' not in DOSSIER, (
        'dossier-stamp re-introduced "Classified" — register-shift away from '
        'the Tribune North Star (DESIGN.md). Use Council/Tribune/Filings voice.'
    )
    assert 'Council Filings' in DOSSIER


def test_dossier_stamp_no_longer_position_absolute():
    """The stamp was `position: absolute; top: 0.85rem; right: 1rem;` and
    overlapped rank-meta when "Holding rank over 7 days" wrapped on narrow
    viewports. S2.1.2 makes it a flow eyebrow that can't collide."""
    block = _css_block(CSS, '.home-shell .dossier-stamp')
    assert block, '.home-shell .dossier-stamp rule missing'
    assert 'position: absolute' not in block, (
        'dossier-stamp re-introduced absolute positioning; the prior version '
        'overlapped rank-meta on narrow viewports.'
    )


# ---------------------------------------------------------------------------
# PI-3: right-rail layout balance.
# ---------------------------------------------------------------------------

def test_home_live_recent_results_lives_in_the_rail():
    """Post-PR-79 the dossier (now carrying the nine-nation roster) runs long,
    so Recent Results moves INTO the supporting rail beneath the leaderboard
    to fill the right-hand void. It must sit in `.home-live-col--rail`, never
    in the masthead/dossier column."""
    rail_section = _section_between(HOME_LIVE, 'home-live-col--rail', '')
    assert rail_section, '.home-live-col--rail wrapper missing.'
    assert 'main/_recent_results.html' in rail_section, (
        '_recent_results.html must sit in .home-live-col--rail (beneath the '
        'leaderboard) so the rail balances the tall dossier.'
    )
    main_section = _section_between(HOME_LIVE, 'home-live-col--main', '')
    if main_section:
        assert 'main/_recent_results.html' not in main_section, (
            "_recent_results.html leaked into .home-live-col--main; Recent "
            "Results belongs in the rail, not the masthead column."
        )


def test_home_live_commish_lives_outside_the_rail():
    """The Commish note is long-form Newsreader editorial and must stay in the
    full-width `.home-live-narrative` band, never the thin rail (S2.1.2's
    rail-starvation lesson + the 65-75ch line-length register)."""
    assert 'home-live-narrative' in HOME_LIVE
    rail_section = _section_between(HOME_LIVE, 'home-live-col--rail', '')
    if rail_section:
        assert '_commish_note.html' not in rail_section, (
            '_commish_note.html leaked into the rail; it must stay in the '
            'full-width .home-live-narrative band.'
        )


def test_home_live_uses_grid_and_collapses_to_source_order():
    """The live state uses `.home-live-grid` (parallel to `.home-pre-grid`),
    not the retired Bootstrap `.row` + `order-*` utilities. Mobile reading
    order is the DOM source order: dossier (main) → leaderboard → results
    (rail) → narrative → tiles, so no `order-*` reordering is needed."""
    assert 'home-live-grid' in HOME_LIVE
    assert 'home-live-col--main' in HOME_LIVE
    assert 'home-live-col--rail' in HOME_LIVE
    assert 'home-live-tiles' in HOME_LIVE
    # The retired Bootstrap order-utility scaffolding must be gone.
    assert 'order-lg-0' not in HOME_LIVE, (
        'order-lg-* utilities should be gone; the grid collapses to source '
        'order on mobile without them.'
    )
    # Source order: main column precedes the rail, which precedes narrative.
    main_at = HOME_LIVE.index('home-live-col--main')
    rail_at = HOME_LIVE.index('home-live-col--rail')
    narrative_at = HOME_LIVE.index('home-live-narrative')
    assert main_at < rail_at < narrative_at, (
        'DOM order must be main → rail → narrative so the mobile single-column '
        'reading order is dossier → leaderboard/results → commish.'
    )


# ---------------------------------------------------------------------------
# PI-4: "Also Today" eyebrow rename — no false time anchor.
# ---------------------------------------------------------------------------

def test_results_also_eyebrow_does_not_promise_today_anchor():
    """Eyebrow promised a temporal anchor (date/time) the rows never
    delivered. Renamed to a register-honest editorial label."""
    # Strip Jinja comments before the assertion — the rename rationale lives
    # in a comment in the template and shouldn't trip the lock.
    src_no_comments = re.sub(r'\{#.*?#\}', '', RECENT, flags=re.S)
    assert 'Also Today' not in src_no_comments, (
        'results-also-eyebrow reverted to "Also Today"; rows still lack a '
        'time tag, so the eyebrow promises something the markup never delivers.'
    )
    assert 'Around the Tournament' in src_no_comments


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _css_block(src: str, selector: str) -> str:
    pat = re.escape(selector) + r'\s*\{([^}]*)\}'
    m = re.search(pat, src)
    return m.group(1) if m else ''


def _section_between(src: str, opening_class: str, expected_col: str) -> str:
    """Return the inner markup of the first `<div class="... opening_class ...">`
    block, scanned to its matching closing `</div>`. Naive but adequate for
    these structural locks (Jinja braces and Bootstrap classes only).

    Returns '' if the wrapper isn't found (test still meaningful — the
    presence assertions in the calling test catch that case).
    """
    open_match = re.search(
        r'<div class="[^"]*' + re.escape(opening_class) + r'[^"]*">',
        src,
    )
    if not open_match:
        return ''
    start = open_match.end()
    depth = 1
    cursor = start
    div_re = re.compile(r'<div\b|</div>')
    for token in div_re.finditer(src, cursor):
        if token.group() == '<div':
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return src[start:token.start()]
    return src[start:]
