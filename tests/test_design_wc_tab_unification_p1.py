"""WC Tab Unification — Phase 1 (HUB body migration) regression locks.

P1 migrated the World Cup hub's content cards off the dark `.card.wc-card`
surface onto the light Stats pattern `.wc-stat-card`, reconciled the
PR #21 gold accents to red, and codified a global red repaint for every
WC `.btn-game` regardless of substrate.

These tests pin the migration so it can't silently drift back:

- PI-1: `body.game-worldcup .btn-game` global red rule exists in style.css
  with `var(--wc-red)` background and border. The prior dark-card scoped
  override (`.card.wc-card .btn-game`) is removed (it lifted to
  `--game-accent` only because the navy primary collapsed into the navy
  card; on the new light cards the navy primary reads fine but the doctrine
  now wants red CTAs everywhere on WC).
- PI-2: hub partials + home_shell.html have zero `.card.wc-card` usage
  EXCEPT the deliberate ceremonial champion banner in `_home_post.html`,
  which combines `.card.wc-card` + `.wc-hero-grad` to carry the dark+gold
  "Final Decree" moment. That wrapper-class migration is deferred to P5
  cleanup.
- PI-3: the `.card.wc-card-deadline` modifier has been retired; its
  gold-top-on-dark semantic was rederived as `.wc-stat-card.is-lead`
  (red-top on light, already locked by `test_design_p2_s2_4_1`).
- PI-4: `--wc-red-dark` token exists in tokens.css to back the new
  global button hover state.
- PI-5: a `.page-hero.wc-hero-grad .phase-indicator` rule paints the
  hero phase chip with red, not gold (PR #21 hub-polish gold variant
  flipped to red+white per the new accent doctrine).
"""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).parent.parent
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'
TOKENS_PATH = ROOT / 'static' / 'css' / 'tokens.css'
TPL_DIR = ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup'

CSS = CSS_PATH.read_text()
TOKENS = TOKENS_PATH.read_text()

HUB_TEMPLATES = [
    TPL_DIR / 'home_shell.html',
    TPL_DIR / '_home_out.html',
    TPL_DIR / '_home_pre.html',
    TPL_DIR / '_home_live.html',
    TPL_DIR / '_home_post.html',
]


# ---------------------------------------------------------------------------
# PI-1: global WC button red repaint + dark-card scoped override removed.
# ---------------------------------------------------------------------------

def test_global_wc_btn_game_red_rule_exists():
    """`body.game-worldcup .btn-game { background: var(--wc-red); … }` is the
    new SSoT for WC CTA paint. Replaces the dark-card scoped lift to
    `--game-accent` from before P1."""
    match = re.search(
        r'body\.game-worldcup\s+\.btn-game\s*\{([^}]+)\}',
        CSS,
    )
    assert match is not None, (
        'Expected a `body.game-worldcup .btn-game` rule defining the global '
        'red CTA paint introduced in WC tab unification P1.'
    )
    block = match.group(1)
    assert 'var(--wc-red)' in block, (
        f'Global WC btn-game rule must paint background/border with '
        f'var(--wc-red); block={block!r}.'
    )
    assert 'background:' in block and 'border-color:' in block, (
        f'Global WC btn-game rule must set both background and border-color; '
        f'block={block!r}.'
    )


def test_global_wc_btn_game_hover_uses_red_dark():
    """Hover/focus-visible state darkens to `var(--wc-red-dark)` — the
    `#9C0826` token added in P1 (~6.94:1 white-on-red, AA-large)."""
    match = re.search(
        r'body\.game-worldcup\s+\.btn-game:hover[^{]*\{([^}]+)\}',
        CSS,
    )
    assert match is not None, (
        'Expected a `body.game-worldcup .btn-game:hover[, …:focus-visible]` '
        'rule for the global red CTA hover state.'
    )
    assert 'var(--wc-red-dark)' in match.group(1), (
        f'Hover rule must darken to var(--wc-red-dark); '
        f'block={match.group(1)!r}.'
    )


def test_old_dark_card_btn_game_override_removed():
    """The pre-P1 `.card.wc-card .btn-game` override lifted to `--game-accent`
    because the navy primary collapsed into the navy card. P1's global red
    repaint supersedes it; the scoped rule must be gone."""
    assert not re.search(
        r'\.card\.wc-card\s+\.btn-game\s*\{',
        CSS,
    ), (
        'The legacy `.card.wc-card .btn-game` dark-card scoped override should '
        'be removed in P1 — the global `body.game-worldcup .btn-game` rule '
        'now paints CTAs red on every WC substrate.'
    )


# ---------------------------------------------------------------------------
# PI-2: hub partials migrated off `.card.wc-card` except champion banner.
# ---------------------------------------------------------------------------

def test_hub_templates_have_no_card_wc_card_except_champion_banner():
    """Lock the migration end-state: 12 of 13 hub `.card.wc-card` containers
    moved to `.wc-stat-card`; the post-state champion banner keeps the dark
    ceremonial wrapper (`.card.wc-card.wc-hero-grad`) as a deliberate
    exception, scheduled for the P5 cleanup pass."""
    pattern = re.compile(r'class="[^"]*\bcard\s+wc-card\b[^"]*"')
    occurrences = []
    for tpl in HUB_TEMPLATES:
        text = tpl.read_text()
        for line_num, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                occurrences.append((tpl.name, line_num, line.strip()))

    assert len(occurrences) == 1, (
        f'Expected exactly 1 `.card.wc-card` usage across hub templates '
        f'(the post-state champion banner); found {len(occurrences)}: '
        f'{occurrences!r}.'
    )

    name, line_num, line = occurrences[0]
    assert name == '_home_post.html', (
        f'The lone remaining `.card.wc-card` should live in _home_post.html '
        f'(champion banner); found in {name} at line {line_num}: {line!r}.'
    )
    assert 'wc-hero-grad' in line, (
        f'The champion banner exception must combine `wc-card` with '
        f'`wc-hero-grad` (dark gradient) to read as the ceremonial Final '
        f'Decree surface, not a stray dark card; found: {line!r}.'
    )


# ---------------------------------------------------------------------------
# PI-3: `.card.wc-card-deadline` modifier retired.
# ---------------------------------------------------------------------------

def test_card_wc_card_deadline_modifier_retired():
    """The deadline modifier (gold-top on dark) was rederived as
    `.wc-stat-card.is-lead` (red-top on light) when the hub moved off
    `.card.wc-card`. The rule should be gone."""
    assert not re.search(
        r'\.card\.wc-card-deadline\s*\{',
        CSS,
    ), (
        'Expected `.card.wc-card-deadline` modifier to be removed in P1 — '
        'its semantic now lives on `.wc-stat-card.is-lead`.'
    )


# ---------------------------------------------------------------------------
# PI-4: --wc-red-dark token added to support the hover state.
# ---------------------------------------------------------------------------

def test_wc_red_dark_token_defined():
    """`--wc-red-dark` is the new hover-darker companion to `--wc-red`, used
    by the global WC button rule."""
    assert re.search(r'--wc-red-dark\s*:', TOKENS), (
        '`--wc-red-dark` should be defined in tokens.css to back the global '
        'WC button hover state.'
    )


# ---------------------------------------------------------------------------
# PI-5: hero phase chip flipped from gold to red+white.
# ---------------------------------------------------------------------------

def test_hero_phase_indicator_uses_red_not_gold():
    """The PR #21 hub-polish gold-on-dark phase chip flips to red+white per
    the new accent doctrine (gold demoted to quaternary, reserved for
    champion banners / podium glow / a11y focus rings)."""
    match = re.search(
        r'\.page-hero\.wc-hero-grad\s+\.phase-indicator\s*\{([^}]+)\}',
        CSS,
    )
    assert match is not None, (
        'Expected the `.page-hero.wc-hero-grad .phase-indicator` rule to '
        'still exist (the chip lives in the dark hero on every state).'
    )
    block = match.group(1)
    # Red-tinted bg + red-tinted border, no gold tokens
    assert '191, 10, 48' in block or '191,10,48' in block, (
        f'Hero phase chip background/border should reference the red triplet '
        f'(rgba 191, 10, 48, …); block={block!r}.'
    )
    assert 'gold' not in block.lower(), (
        f'Hero phase chip should no longer reference any gold token after '
        f'the P1 flip; block={block!r}.'
    )


def test_pulse_red_keyframe_defined():
    """The hero phase chip's `active` pulse switches from `pulseGold` to
    `pulseRed` so the chip's ripple matches its new red dot."""
    assert re.search(r'@keyframes\s+pulseRed\s*\{', CSS), (
        'Expected a `@keyframes pulseRed` declaration to back the hero '
        'phase chip\'s active-pulse ripple after the gold→red flip.'
    )
