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

REPO_ROOT = Path(__file__).resolve().parents[1]
STYLE_CSS = REPO_ROOT / 'static' / 'css' / 'style.css'
WC_HOME_POST = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / '_home_post.html'
HOME_SHELL = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'home_shell.html'
PLATFORM_CHAMPION_BANNER = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'lounge' / '_champion_banner.html'


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
# PI-1 + PI-2 locks retired in WC tab unification P5
# ---------------------------------------------------------------------------
# The S5.3 PI-1 (`.card.wc-card .wc-numeral` family) and PI-2
# (`.card.wc-card .btn-outline-secondary` family) rules both retired in P5
# along with the entire `.card.wc-card` substrate. Their bone-on-navy
# overrides are no longer needed because no WC tab body sits on a dark
# substrate anymore — every consumer now reads Bootstrap default ink on
# the Casual-Light card. Broad retirement is locked in
# `tests/test_design_wc_tab_unification_p5.py::test_pi1_zero_card_wc_card_rule_heads`.
# The PI-2 home_shell quicklink template assertion below stays — the
# `.btn-outline-secondary` class still ships in the markup, it just reads
# against the platform `--bs-secondary-color` redirect now (S6.1.1 PI-2)
# instead of a scoped lift.


def test_pi2_home_shell_around_the_pool_footer_retired():
    """The home_shell.html "Around the Pool" quicklink footer is gone.

    Hub coherence pass 2026-05 retired the Schedule / Groups / Rules
    outline-button footer — the game sub-nav at the top of every WC tab
    already routes to those destinations, and the footer duplicated them
    below scroll on a long pre-state where users had most likely already
    used the sub-nav. Aesthetic-and-minimalist under WC §6: every element
    earns its pixel. This test locks the retirement so a future "let's
    add a footer" reflex re-trips the contract.

    The `--bs-secondary-color` redirect at style.css :7183 still ships
    (it's load-bearing for any other consumer of `.text-muted` /
    `.btn-outline-secondary` on bone). What changed is just the call
    site count in home_shell.html.
    """
    src = HOME_SHELL.read_text()
    assert 'Around the Pool' not in src, (
        '"Around the Pool" footer was retired — restoring it duplicates '
        'the game sub-nav and re-introduces an unused below-scroll row.'
    )
    assert 'btn-outline-secondary' not in src, (
        'No outline-secondary footer buttons should ship in '
        'home_shell.html post-coherence-pass; found at least one.'
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
