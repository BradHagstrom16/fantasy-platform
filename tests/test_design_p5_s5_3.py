"""S5.3 — Cross-cluster post-live polish. Layer A locks.

Four Priority Issues, each backed by a source-pattern regression test:

- PI-1: Selector-scope ``.card.wc-card .wc-numeral`` bone override so it
  skips Bootstrap-table substrates. S2.6 PI-1's ``--bs-table-bg`` lock
  (style.css :6691) made every .wc-numeral inside a tbody cell paint
  bone-on-white (~1.1:1, axe-confirmed 8 hits on _home_post tables). The
  new rule restores platform ink for in-cell numerals; the
  ``:not(.player-picks-desktop)`` carve-out mirrors PR #15 CR R2's
  .wc-multiplier-chip pattern so the navy-bleed-through surface keeps its
  bone numerals. Routed from S5.1.1 §0.4; taken in S5.3 as §1.8 deviation.

- PI-2: Lift ``.card.wc-card .btn-outline-secondary`` quicklinks from
  3.04:1 (axe-confirmed) to AA. The home_shell.html quicklink trio
  (Schedule / Groups / Rules) is universal to every state partial, so
  the cluster-wide lift lands all four states at once.

- PI-3: Cross-cluster Tribune voice alignment on the WC _home_post.html
  champion banner eyebrow. ``World Cup Winner`` (wire-service) → ``Final
  Decree`` (Council Tribune), mirroring the platform _champion_banner.html
  eyebrow set by S5.2.1 PI-3.

- PI-4: Add a Tribune retrospection line to the platform _champion_banner
  .html. The cluster's primary full-bleed champion moment carried only
  wire-service voice (eyebrow + name + summary + venue/date); the WC
  variant had a retrospection line since S5.1.1 PI-2. The Tribune voice
  should land hardest on the cluster's biggest moment, not its secondary
  banner. The new platform line ("The Club records the night.") is
  intentionally distinct from the WC line ("A final the club will
  remember.") so the cluster reads as one Tribune voice with two
  sentences, not a repeated line.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import create_app
from extensions import db
from flask import render_template


REPO_ROOT = Path(__file__).resolve().parents[1]
STYLE_CSS = REPO_ROOT / 'static' / 'css' / 'style.css'
WC_HOME_POST = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / '_home_post.html'
HOME_SHELL = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'home_shell.html'
PLATFORM_CHAMPION_BANNER = REPO_ROOT / 'core' / 'main' / 'templates' / 'main' / '_champion_banner.html'


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _champion_branches(src: str) -> tuple[str, str]:
    """Slice the ``{% if champion_team %} … {% else %} … {% endif %}`` block.

    Returns ``(success_branch, fallback_branch)`` substrings so eyebrow / glyph
    assertions can scope to the correct branch instead of grepping the whole
    template (which would silently match the wrong branch if source order ever
    changed, or if a second ``.wc-eyebrow`` div is added above).
    """
    match = re.search(
        r'\{%\s*if\s+champion_team\s*%\}(.*?)\{%\s*else\s*%\}(.*?)\{%\s*endif\s*%\}',
        src,
        re.DOTALL,
    )
    assert match is not None, (
        'Expected an {% if champion_team %} / {% else %} / {% endif %} block.'
    )
    return match.group(1), match.group(2)


# ---------------------------------------------------------------------------
# PI-1 locks: .card.wc-card:not(.player-picks-desktop) .table .wc-numeral
# ---------------------------------------------------------------------------

def test_pi1_in_cell_wc_numeral_restores_platform_ink():
    """Selector-scoped rule retints in-cell .wc-numeral to --text-primary.

    Locks the existence + exact selector shape. A future "tidy this up"
    pass that broadens the selector to ``.card.wc-card .table .wc-numeral``
    (no :not) would silently break the .player-picks-desktop bleed-through
    case where bone-on-navy is correct.
    """
    css = STYLE_CSS.read_text()
    match = re.search(
        r'\.card\.wc-card:not\(\.player-picks-desktop\)\s+\.table\s+\.wc-numeral\s*\{([^}]+)\}',
        css,
    )
    assert match is not None, (
        'Expected `.card.wc-card:not(.player-picks-desktop) .table .wc-numeral` '
        'rule in style.css (S5.3 PI-1).'
    )
    block = match.group(1)
    # Negative-lookbehind so the assertion can't false-pass against a future
    # `background-color: …` or `border-color: …` edit using the same token.
    assert re.search(r'(?<!-)color:\s*var\(--text-primary\)', block), (
        f'Rule must paint --text-primary so default body color reads on '
        f'the white-masked td; block={block!r}.'
    )


def test_pi1_parent_bone_override_still_exists():
    """The canonical ``.card.wc-card .wc-numeral`` bone override is preserved.

    The S4.2.2 PI-5 bone override (style.css :2850) is still required for
    .wc-numeral spans in .card-header and direct .card-body content on the
    navy substrate (e.g., the tiebreaker numeral, the "Total: 125.0 pts"
    desktop header). The S5.3 fix only adds a more-specific child rule;
    deleting the parent would break those non-table call sites.
    """
    css = STYLE_CSS.read_text()
    match = re.search(
        r'\.card\.wc-card\s+\.wc-numeral\s*\{([^}]+)\}',
        css,
    )
    assert match is not None
    block = match.group(1)
    assert re.search(r'(?<!-)color:\s*var\(--text-on-dark\)', block), (
        f'The canonical bone override on non-table .wc-numeral spans '
        f'must persist; block={block!r}.'
    )


def test_pi1_in_cell_rule_lives_after_parent_in_cascade():
    """The :not()-scoped rule appears AFTER the parent in source order.

    Specificity (0,0,4,0) wins over (0,0,2,0) regardless of order, so this
    is documentation of intent more than enforcement. But if a future
    refactor reorders blocks and accidentally moves the parent rule below
    the child, the parent's lower specificity still loses cleanly — locking
    the existing source order against silent rearrangement.
    """
    css = STYLE_CSS.read_text()
    parent_idx = css.find('.card.wc-card .wc-numeral {')
    child_idx = css.find(
        '.card.wc-card:not(.player-picks-desktop) .table .wc-numeral {'
    )
    assert parent_idx != -1 and child_idx != -1, (
        'Both .card.wc-card .wc-numeral rules must exist in style.css.'
    )
    assert child_idx > parent_idx, (
        'The PI-1 child rule should appear after the parent rule in source '
        'order so the cascade lock and intent comment read together.'
    )


# ---------------------------------------------------------------------------
# PI-2 locks: .card.wc-card .btn-outline-secondary quicklink lift
# ---------------------------------------------------------------------------

def test_pi2_quicklink_rest_state_lifts_to_bone_on_navy():
    """``.card.wc-card .btn-outline-secondary`` lifts to bone at rest.

    Bootstrap's default --bs-secondary-color (#8a849b) reads 3.04:1 on
    the .card.wc-card navy substrate. The lift to var(--text-on-dark)
    (full bone) reads ~13:1, well past AA.
    """
    css = STYLE_CSS.read_text()
    match = re.search(
        r'\.card\.wc-card\s+\.btn-outline-secondary\s*\{([^}]+)\}',
        css,
    )
    assert match is not None, (
        'Expected `.card.wc-card .btn-outline-secondary` rule (S5.3 PI-2).'
    )
    block = match.group(1)
    assert re.search(r'(?<!-)color:\s*var\(--text-on-dark\)', block), (
        f'Rest-state color must lift to --text-on-dark; block={block!r}.'
    )
    assert 'border-color: rgba(245, 241, 232, .35)' in block, (
        f'Border lift to bone-alpha .35 missing; block={block!r}.'
    )


def test_pi2_quicklink_hover_focus_invert_to_ink_on_bone():
    """Hover + focus-visible invert to ink-on-bone (Bootstrap-parallel).

    Mirrors Bootstrap's btn-outline-secondary hover inversion (white on
    gray-600) but in CCC tokens: --text-primary on --bone. Both pseudo-
    classes share the same block so keyboard focus reads identically.
    """
    css = STYLE_CSS.read_text()
    match = re.search(
        r'\.card\.wc-card\s+\.btn-outline-secondary:hover,\s*\n\s*'
        r'\.card\.wc-card\s+\.btn-outline-secondary:focus-visible\s*\{([^}]+)\}',
        css,
    )
    assert match is not None, (
        'Hover + focus-visible combined block missing.'
    )
    block = match.group(1)
    assert re.search(r'(?<!-)color:\s*var\(--text-primary\)', block)
    assert 'background-color: var(--bone)' in block
    assert 'border-color: var(--bone)' in block


def test_pi2_home_shell_quicklinks_still_use_btn_outline_secondary():
    """The home_shell.html quicklink trio still carries the targeted class.

    The CSS lift only takes effect when the markup keeps
    btn-outline-secondary. Lock against a future template refactor that
    swaps to a different button variant and silently re-fails the contrast.
    """
    src = HOME_SHELL.read_text()
    count = src.count('btn-outline-secondary')
    assert count >= 3, (
        f'Expected at least 3 .btn-outline-secondary anchors in '
        f'home_shell.html (Schedule / Groups / Rules); found {count}.'
    )


# ---------------------------------------------------------------------------
# PI-3 locks: WC banner eyebrow Tribune voice
# ---------------------------------------------------------------------------

def test_pi3_wc_banner_eyebrow_carries_final_decree_voice():
    """The WC banner eyebrow says ``Final Decree``, not ``World Cup Winner``.

    Cross-cluster Tribune voice consistency with the platform
    _champion_banner.html eyebrow set by S5.2.1 PI-3.
    """
    src = WC_HOME_POST.read_text()
    success, _ = _champion_branches(src)
    # Scope to the champion_team success branch so a future second
    # .wc-eyebrow div above (or branch reorder) can't false-pass.
    match = re.search(
        r'<div class="wc-eyebrow mb-1">([^<]+)</div>',
        success,
    )
    assert match is not None, (
        'wc-eyebrow div missing from the champion_team success branch.'
    )
    text = match.group(1).strip()
    assert text == 'Final Decree', (
        f'Expected "Final Decree" eyebrow; got {text!r}.'
    )


def test_pi3_wc_banner_eyebrow_does_not_carry_platform_glyphs():
    """WC chrome convention omits the platform's ◈ ornament glyphs.

    The wc-eyebrow primitive renders without ornament glyphs everywhere
    else in the WC surface set; voice alignment with the platform should
    not borrow chrome.
    """
    src = WC_HOME_POST.read_text()
    success, _ = _champion_branches(src)
    match = re.search(
        r'<div class="wc-eyebrow mb-1">([^<]+)</div>',
        success,
    )
    assert match is not None
    text = match.group(1).strip()
    assert '◈' not in text, (
        f'wc-eyebrow should not carry platform ◈ glyphs; text={text!r}.'
    )


def test_pi3_wc_banner_eyebrow_no_longer_says_world_cup_winner():
    """The wire-service "World Cup Winner" label is retired.

    Anchored by template grep — a future revert that reintroduces the
    descriptive label trips this. Strips Jinja comments first so the
    rationale comment block (which historically quotes the retired label)
    doesn't trigger the test.
    """
    src = WC_HOME_POST.read_text()
    # Strip Jinja {# ... #} comment blocks (non-greedy across lines).
    src_no_comments = re.sub(r'\{#.*?#\}', '', src, flags=re.DOTALL)
    assert 'World Cup Winner' not in src_no_comments, (
        '"World Cup Winner" wire-service label was retired in S5.3 PI-3 '
        'for Tribune voice consistency.'
    )


def test_pi3_defensive_eyebrow_kept_for_admin_error_branch():
    """The defensive "Tournament Complete" eyebrow for the no-champion
    fallback branch persists. The Tribune-voice rewrite is gated to the
    success branch; admin-error state stays factual.
    """
    src = WC_HOME_POST.read_text()
    _, fallback = _champion_branches(src)
    # Anchor to the {% else %} branch so a future edit can't move
    # "Tournament Complete" into the success branch and silently still pass.
    match = re.search(
        r'<div class="wc-eyebrow mb-1">([^<]+)</div>',
        fallback,
    )
    assert match is not None, (
        'wc-eyebrow div missing from the no-champion fallback branch.'
    )
    text = match.group(1).strip()
    assert text == 'Tournament Complete', (
        f'Defensive fallback eyebrow expected "Tournament Complete"; '
        f'got {text!r}.'
    )


# ---------------------------------------------------------------------------
# PI-4 locks: Platform _champion_banner.html Tribune retrospection
# ---------------------------------------------------------------------------

def test_pi4_platform_banner_has_champion_retrospect_div():
    """Platform `_champion_banner.html` renders a ``.champion-retrospect`` div.

    Lock against a future revert that strips the Tribune retrospection line.
    """
    src = PLATFORM_CHAMPION_BANNER.read_text()
    match = re.search(
        r'<div class="champion-retrospect">([^<]+)</div>',
        src,
    )
    assert match is not None, (
        'champion-retrospect div missing from platform _champion_banner.html.'
    )


def test_pi4_platform_retrospect_distinct_from_wc_variant():
    """Platform line is intentionally distinct from the WC variant's line.

    Two Tribune sentences across the cluster, not a repeated line. If a
    future pass moves the WC line up to platform (or vice versa) and
    creates cross-cluster duplication, this test catches it.
    """
    platform_src = PLATFORM_CHAMPION_BANNER.read_text()
    wc_src = WC_HOME_POST.read_text()

    platform_match = re.search(
        r'<div class="champion-retrospect">([^<]+)</div>',
        platform_src,
    )
    wc_match = re.search(
        r'<p class="champion-retrospect">([^<]+)</p>',
        wc_src,
    )
    assert platform_match is not None and wc_match is not None, (
        'Both clusters must carry a champion-retrospect line.'
    )
    platform_line = platform_match.group(1).strip()
    wc_line = wc_match.group(1).strip()
    assert platform_line != wc_line, (
        f'Cross-cluster Tribune lines must be distinct; both clusters say '
        f'{platform_line!r}.'
    )


def test_pi4_platform_retrospect_lands_council_voice():
    """The platform retrospect carries a Council/Tribune phrase.

    Loose lock — "Club" anchors the Council voice without pinning the
    exact wording so a future tune can revise prose without breaking the
    test. The wire-service words "score", "venue", "stadium" must NOT
    appear inside this div.
    """
    src = PLATFORM_CHAMPION_BANNER.read_text()
    match = re.search(
        r'<div class="champion-retrospect">([^<]+)</div>',
        src,
    )
    assert match is not None
    text = match.group(1).strip()
    assert 'Club' in text, (
        f'Expected Council-voice "Club" anchor; text={text!r}.'
    )
    for wire in ('score', 'venue', 'stadium', 'goals'):
        assert wire.lower() not in text.lower(), (
            f'Retrospect should carry editorial voice, not wire-service '
            f'token {wire!r}; text={text!r}.'
        )


def test_pi4_platform_retrospect_only_in_champion_success_branch():
    """The retrospect div sits inside ``{% if champion_team %}`` only.

    The admin-error fallback branch (champion_pending state) must NOT
    render the Tribune retrospection — that voice is reserved for the
    actual champion-crowned moment. Locking via positional check.
    """
    src = PLATFORM_CHAMPION_BANNER.read_text()
    # Walk: the {% if champion_team %} branch ends at {% else %}.
    success_start = src.find('{% if champion_team %}')
    else_branch = src.find('{% else %}', success_start)
    retrospect_idx = src.find('class="champion-retrospect"')
    assert success_start != -1 and else_branch != -1 and retrospect_idx != -1
    assert success_start < retrospect_idx < else_branch, (
        'champion-retrospect must live inside the champion_team success '
        'branch, before the {% else %} fallback.'
    )


def test_pi4_platform_retrospect_css_rule_exists():
    """The CSS rule `.home-shell .champion-retrospect` is styled.

    The PI-4 markup change is paired with a CSS recipe mirroring the WC
    variant at style.css :7009 (Newsreader italic, bone .82). A markup-
    only PI without the style would render default browser ink.
    """
    css = STYLE_CSS.read_text()
    match = re.search(
        r'\.home-shell\s+\.champion-retrospect\s*\{([^}]+)\}',
        css,
    )
    assert match is not None, (
        '.home-shell .champion-retrospect CSS rule missing (PI-4 paired '
        'CSS recipe).'
    )
    block = match.group(1)
    assert 'font-family: var(--font-news)' in block, (
        f'Newsreader family expected; block={block!r}.'
    )
    assert 'font-style: italic' in block, (
        f'Italic expected to match WC variant; block={block!r}.'
    )
    assert 'rgba(245, 241, 232, 0.82)' in block, (
        f'Bone .82 alpha expected to match WC variant tone; block={block!r}.'
    )
