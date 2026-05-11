"""P3 S3.3.2 regression locks — second iteration on the platform home
dispatcher + non-state partials.

Layer A (per plan §1.3) source-pattern locks for the three Priority Issues
landed in S3.3.2. The surface still covers `_game_card.html`,
`_game_tiles_compact.html`, the `games/registry.py` GameRegistryEntry shape,
and `static/css/style.css` for the focus-ring + microcopy rules.

Iteration map:

- PI-1 (registry-driven tile copy): the S3.3.1 §0.4 entry on
  `_game_tiles_compact.html:28-29` flagged the slug-branched ternaries
  (`game.display_name.split()[0] if game.slug == 'cfb' else 'Golf'` and
  `Sep 3 / 2027`) as brittle: a future registry rename like
  `"College Football Survivor"` would make the first word render
  `"College"`, and the launch-date strings lived invisible to anyone editing
  `games/registry.py`. DESIGN.md §1 *"Each game provides its own room: its
  own palette, sub-nav, and interaction emphasis. Game blueprints inject
  their identity"*; PRODUCT.md Design Principle 5 *"Custom Games Earn
  Custom Layers"* — per-game identity flows from the registry/blueprint,
  not from ternaries in a shared partial. S3.3.2 implemented option (a):
  added optional `short_name` (default `''`) and `launch_label` (default
  `''`) fields to `GameRegistryEntry`, populated them on all three entries
  (WC: `"World Cup"` / `"Jun 11"`; CFB: `"CFB"` / `"Sep 3"`; Golf:
  `"Golf"` / `"2027"`), and rewrote the partial to read
  `{{ game.short_name or game.display_name }}` and
  `{{ game.launch_label or 'TBA' }}` so it carries no slug knowledge.

- PI-2 (`$impeccable clarify` — coming-soon temporal anchor): the
  `_game_card.html` `coming_soon` variant displayed `"Coming Soon"` with no
  date anchor, leaving casual users with an open-ended promise. Heuristic
  10 (Help/Documentation) graded 2 at S3.3.1; adding the launch-label
  surfaces an inline date hint without requiring a separate countdown.
  Reads as `"Opens Sep 3"` / `"Opens 2027"` / `"Opens TBA"` depending on
  the registry value. Styled via `.game-launch-meta` (Teko 500, .9rem,
  .14em letter-spacing, uppercase, `var(--text-secondary)`) — sits on the
  bone surface so we use `--text-secondary` (~6.9:1) not Bootstrap
  `--text-muted` (~3.7:1, AA-fail on bone per the
  `project_text_muted_aa_on_bone` memory established in S2.2.1 + S2.6 PI-3
  + S3.2.1 PI-2). The `.game-card--coming-soon .game-desc` margin-bottom
  was tightened to .85rem so the new line reads as a tightly-paired
  temporal anchor rather than a stranded footer.

- PI-3 (`$impeccable polish` — keyboard focus ring): the S3.3.1 §0.4 entry
  flagged that `.game-card--live` inherited the browser-default focus
  outline (inconsistent across Chrome/Safari/Firefox), parallel to the
  S3.1.1 routed finding on `.nav-link` / `.subnav-pill`. Heuristic 7
  (Flexibility/Efficiency) graded 2 at S3.3.1; an explicit gold-light ring
  closes the keyboard-first gap. Pattern matches the canonical
  `.home-shell .sec-head .more:focus-visible` rule established in S2.1.2:
  `outline: 2px solid var(--gold-light); outline-offset: 2px;
  border-radius: var(--radius);` — the radius traces the card silhouette.

The combined heuristic lift (Heuristic 7: 2→3, Heuristic 10: 2→3) clears
the §1.5b gate (b) baseline+6 floor (24 → ≥26) that S3.3.1 fell short of.
"""
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()
GAME_CARD = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_game_card.html').read_text()
TILES_COMPACT = (
    ROOT / 'core' / 'main' / 'templates' / 'main' / '_game_tiles_compact.html'
).read_text()
REGISTRY = (ROOT / 'games' / 'registry.py').read_text()


def _state_block(state: str) -> str:
    """Slice `_game_card.html` between `state == 'X'` and the next branch."""
    pattern = re.compile(
        rf"state\s*==\s*'{state}'\s*%\}}(.*?)(?=\{{%\s*(?:elif|endif))",
        re.DOTALL,
    )
    match = pattern.search(GAME_CARD)
    assert match, f"_game_card.html missing `state == '{state}'` branch"
    return match.group(1)


def _css_block(selector: str) -> str:
    """Return all CSS declarations matching a selector across the stylesheet."""
    blocks = re.findall(
        rf'{re.escape(selector)}[^{{]*\{{[^}}]*\}}',
        CSS,
    )
    return '\n'.join(blocks)


# ---------------------------------------------------------------------------
# PI-1: registry-driven tile copy — slug knowledge leaves the partial.
# ---------------------------------------------------------------------------

def test_pi1_registry_entry_carries_short_name_field():
    """`GameRegistryEntry` must declare a `short_name` field with an empty-
    string default so legacy callers (test mocks in `test_registry.py` /
    `test_enrollment_gating.py`) keep working without modification."""
    assert re.search(r"short_name\s*:\s*str\s*=\s*''", REGISTRY), (
        "PI-1: `GameRegistryEntry` must declare `short_name: str = ''` so "
        "the partial can read `game.short_name` slug-agnostically. Default "
        "empty so legacy mock factories don't break."
    )


def test_pi1_registry_entry_carries_launch_label_field():
    """Same shape as `short_name` — empty-string default keeps backward
    compatibility with the two existing mock-factory test files."""
    assert re.search(r"launch_label\s*:\s*str\s*=\s*''", REGISTRY), (
        "PI-1: `GameRegistryEntry` must declare `launch_label: str = ''` so "
        "the partial can read `game.launch_label` slug-agnostically."
    )


def test_pi1_registry_populates_cfb_and_golf_metadata():
    """The three production entries must set `short_name` + `launch_label`
    so the registry, not the partial, owns the display copy. WC is set for
    consistency (the WC tile in the compact partial uses its own stateful
    label, but populating WC keeps every entry uniform)."""
    # CFB — replaces `display_name.split()[0]` ternary + `Sep 3` literal.
    assert "short_name='CFB'" in REGISTRY, "PI-1: CFB entry must set short_name='CFB'."
    assert "launch_label='Sep 3'" in REGISTRY, "PI-1: CFB entry must set launch_label='Sep 3'."
    # Golf — replaces the `'Golf'` fallback + `2027` literal.
    assert "short_name='Golf'" in REGISTRY, "PI-1: Golf entry must set short_name='Golf'."
    assert "launch_label='2027'" in REGISTRY, "PI-1: Golf entry must set launch_label='2027'."
    # WC — uniform population, surfaces in the compact partial's hardcoded
    # WC tile only as wc_label which still derives from state, but the
    # registry-side metadata exists for any future caller.
    assert "short_name='World Cup'" in REGISTRY, "PI-1: WC entry must set short_name='World Cup'."


def test_pi1_tiles_compact_drops_slug_ternaries():
    """The partial must NOT branch on `game.slug`. The whole point of PI-1
    is to push slug knowledge out of presentation."""
    assert "game.slug == 'cfb'" not in TILES_COMPACT, (
        "PI-1: `_game_tiles_compact.html` still branches on "
        "`game.slug == 'cfb'`. Read `game.short_name` / `game.launch_label` "
        "from the registry instead."
    )
    # The old literal launch dates must also be gone — the registry owns them now.
    # 'Sep 3' and '2027' as bare strings inside the partial.
    assert 'Sep 3' not in TILES_COMPACT, (
        "PI-1: hardcoded `Sep 3` must move to `games/registry.py` as the "
        "CFB entry's `launch_label`."
    )
    assert '2027' not in TILES_COMPACT, (
        "PI-1: hardcoded `2027` must move to `games/registry.py` as the "
        "Golf entry's `launch_label`."
    )


def test_pi1_tiles_compact_reads_registry_fields():
    """The partial must read the new registry fields with sensible fallbacks
    so an entry that omits them still renders something meaningful."""
    assert 'game.short_name or game.display_name' in TILES_COMPACT, (
        "PI-1: partial must read `{{ game.short_name or game.display_name }}` "
        "so entries that omit `short_name` fall back to the full display_name."
    )
    assert "game.launch_label or 'TBA'" in TILES_COMPACT, (
        "PI-1: partial must read `{{ game.launch_label or 'TBA' }}` so "
        "entries that omit `launch_label` render `TBA` instead of empty."
    )


# ---------------------------------------------------------------------------
# PI-2: "Opens [season]" microcopy on the coming_soon variant.
# ---------------------------------------------------------------------------

def test_pi2_coming_soon_renders_launch_microcopy():
    """The `coming_soon` branch of `_game_card.html` must render a
    `.game-launch-meta` paragraph using the registry's `launch_label`."""
    coming_soon = _state_block('coming_soon')
    assert 'game-launch-meta' in coming_soon, (
        "PI-2: `coming_soon` must include a `.game-launch-meta` line. "
        "This is the inline date anchor that turns 'Coming Soon' into "
        "'Coming Soon · Opens Sep 3' (Heuristic 10: Help/Documentation)."
    )
    # The copy reads "Opens {launch_label}" — `Opens` is the literal lead-in.
    assert re.search(r"Opens\s+\{\{\s*game\.launch_label", coming_soon), (
        "PI-2: the microcopy must read `Opens {{ game.launch_label ... }}` "
        "so registry metadata drives the date."
    )
    assert "game.launch_label or 'TBA'" in coming_soon, (
        "PI-2: the microcopy must fall back to `TBA` when the registry "
        "entry omits `launch_label`, matching the compact tile partial."
    )


def test_pi2_game_launch_meta_uses_text_secondary_not_text_muted():
    """`.game-launch-meta` paints on the bone card body. Per the
    `project_text_muted_aa_on_bone` memory (3.7:1 fail at body sizes),
    microcopy on bone must use `--text-secondary` (#5A5470, ~6.9:1)."""
    block = _css_block('.game-card--coming-soon .game-launch-meta')
    assert 'color: var(--text-secondary)' in block, (
        "PI-2: `.game-card--coming-soon .game-launch-meta` must paint "
        "`var(--text-secondary)` — `--text-muted` fails AA on bone."
    )
    # Negative lock: must NOT use --text-muted.
    assert 'color: var(--text-muted)' not in block, (
        "PI-2: `.game-launch-meta` must NOT use `var(--text-muted)` "
        "(3.7:1 on bone, AA-fail per project_text_muted_aa_on_bone)."
    )


def test_pi2_game_launch_meta_uses_teko():
    """Microcopy is Teko 500 uppercase per DESIGN.md §3's eyebrow primitive
    — matches sibling `.status-badge` / `.wc-eyebrow` typography so the
    coming-soon card reads in one editorial voice."""
    block = _css_block('.game-card--coming-soon .game-launch-meta')
    assert "font-family: 'Teko'" in block, (
        "PI-2: `.game-launch-meta` must use Teko (matches DESIGN.md §3 "
        "eyebrow primitive register)."
    )
    assert 'text-transform: uppercase' in block, (
        "PI-2: `.game-launch-meta` must be uppercase per the eyebrow primitive."
    )


# ---------------------------------------------------------------------------
# PI-3: keyboard focus ring on `.game-card--live`.
# ---------------------------------------------------------------------------

def test_pi3_game_card_live_has_focus_visible_ring():
    """`.game-card--live` must declare a `:focus-visible` outline so
    keyboard users get a consistent arrival indicator across browsers
    (heuristic 7: Flexibility/Efficiency). Pattern matches the canonical
    `.home-shell .sec-head .more:focus-visible` rule (S2.1.2 locked)."""
    block = _css_block('.game-card--live:focus-visible')
    assert block, (
        "PI-3: `.game-card--live:focus-visible` rule missing. Keyboard "
        "users currently inherit the browser-default outline, which is "
        "inconsistent across Chrome/Safari/Firefox."
    )
    # The canonical pattern: 2px gold-light outline, 2px offset, radius-traced.
    assert 'outline: 2px solid var(--gold-light)' in block, (
        "PI-3: focus ring must use `outline: 2px solid var(--gold-light)` "
        "matching the canonical `.home-shell .sec-head .more` pattern."
    )
    assert 'outline-offset: 2px' in block, (
        "PI-3: focus ring must use `outline-offset: 2px` for visual breathing."
    )
    assert 'border-radius: var(--radius)' in block, (
        "PI-3: focus ring must trace the card silhouette via "
        "`border-radius: var(--radius)`."
    )


def test_pi3_focus_ring_only_on_live_card_not_coming_soon():
    """The focus ring is for playable cards. `.game-card--coming-soon` is
    `pointer-events: none` + non-anchor in the partial, so a focus-visible
    rule there would be misleading (the card isn't focusable). Lock that
    we didn't accidentally broadcast the rule."""
    coming_soon_focus = _css_block('.game-card--coming-soon:focus-visible')
    assert not coming_soon_focus, (
        "PI-3: `.game-card--coming-soon:focus-visible` should NOT exist. "
        "The coming-soon variant is non-interactive; adding a focus ring "
        "would imply keyboard reachability that the markup denies."
    )
