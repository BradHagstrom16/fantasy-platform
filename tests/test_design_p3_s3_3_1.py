"""P3 S3.3.1 regression locks — platform home dispatcher + non-state partials.

Layer A (per plan §1.3) source-pattern locks for the Priority Issues landed
in S3.3.1. The surface covers three files: the 25-line `index.html`
dispatcher and two non-state partials (`_game_card.html`,
`_game_tiles_compact.html`). State partials (`_home_pre/live/post/out.html`)
are out of scope — they're covered by S2.1 / S4.1 / S5.1.

Iteration map:

- PI-A (`$impeccable shape` — silhouette differentiation): the `_game_card.html`
  `coming_soon` state used the same `<a class="card">` → body → `.card-footer`
  structure as `logged_out`/`available`/`joined`. When `_home_out.html`
  rendered three of these in a row (one `logged_out` + two `coming_soon`),
  the eye saw three twins where only one was playable. DESIGN.md §6 Don'ts:
  *"Don't introduce repeating identical card grids."* PRODUCT.md AI Guidance:
  *"If your first instinct on a CCC surface is a clean three-column dashboard
  with even card grids, it's wrong."* Fix: dropped the `.card-footer` from
  `coming_soon`, lifted the "Coming Soon" status into an eyebrow position
  above the icon, and softened the muted opacity (.55→.78) and grayscale
  filter (35%→18%) so the card reads "not-yet-open" rather than "broken".
  The footer-bearing CTA silhouette stays exclusive to the playable states.

- PI-B (`$impeccable polish` — DESIGN.md compliance retune on
  `.game-card--featured`): the dormant `featured` variant declared in
  `_game_card.html:9-23` (no caller invokes it today) carried multiple
  DESIGN.md violations in `style.css:4319-4394` — literal `#FFFFFF` on
  `.featured-title` (No-Pure-White Rule), `rgba(255,255,255,.55)` on
  `.featured-desc`, neutral-black `drop-shadow` on `.featured-icon`
  (Press-Room Shadow Rule), and a hardcoded WC navy + red palette
  (`#00122e`/`#002868`/`#001a44` gradient + `#BF0A30` badge) outside any
  `body.game-worldcup` scope (Two-Color Rule). When S4.1 wires this state
  up for `_home_out.html`, it must ship brand-compliant. Fix:
  • `.featured-game-inner` background swapped to CCC purple + gold radials
    over a `var(--purple-950)` → `var(--purple-800)` → `var(--purple-950)`
    linear gradient.
  • `.featured-game-inner::before` halftone-dot pattern swapped from
    `rgba(255,255,255,.03)` to `rgba(201,162,39,.06)` (Commish Gold,
    matching the platform `.page-hero` halftone per DESIGN.md §5).
  • `.featured-badge` color/background/border swapped from hardcoded WC
    red (`#BF0A30`) to `var(--live-red)` (`#E63946`) — DESIGN.md §2 reserves
    live-red for "live indicators, momentum arrows, deadline urgency",
    which "Live Now" qualifies as.
  • `.featured-icon` drop-shadow swapped from `rgba(0,0,0,.3)` to
    `rgba(28,10,58,.45)` (Chamber Purple) per Press-Room Shadow Rule.
  • `.featured-title` color `#FFFFFF` → `var(--bone)` per No-Pure-White.
  • `.featured-desc` color `rgba(255,255,255,.55)` → `rgba(243,239,230,.78)`
    (bone alpha .78, ≥AA on `var(--purple-950)` substrate).
  • `.game-card--featured:hover` box-shadow swapped from `rgba(0,40,104,.35)`
    (WC navy) to `rgba(58,29,114,.35)` (Council Purple).

- PI-C (`$impeccable polish` — DESIGN.md §2 Tinted-Neutral Rule):
  `.status-badge--muted` at `style.css:5121-5125` used `rgba(120,120,120,.1)`
  background + `rgba(120,120,120,.2)` border — neutral gray, the only
  un-tinted utility on the home surface. The sibling `.status-badge--joined`
  was already brand-tinted (gold). Fix: swap to Council Purple tint
  (`rgba(58,29,114,.07)` background, `rgba(58,29,114,.20)` border); keep
  the `--text-secondary` foreground (already purple-tinted per DESIGN.md).

Freebies batched at end-of-iteration:
- F1: `_game_card.html` `joined` state — drop the trailing `✓` from
  "Joined ✓". The gold pill carries the state; the checkmark is a
  redundant markup-as-icon. (DESIGN.md §6 Live Indicators: state colors
  are paired with text, not the inverse.)
- F2: `_game_card.html` `featured` state — drop the `<i class="bi bi-globe2
  me-2">` glyph from the "Enter the Pool" CTA. With PI-B's CCC purple +
  gold retune the variant no longer reads as WC-specific; Teko +
  "Enter the Pool" carries the weight without a generic Bootstrap globe.
- F3 (axe-discovered): `_game_card.html` `.game-title` was `<h5>` on the
  4 non-featured states while the featured state was already `<h3>`. Axe
  flagged the page-level `<h1>` → card-level `<h5>` jump as a
  heading-order violation (moderate). Aligned all card-title states to
  `<h3>` per DESIGN.md §3 *"Title (Teko 600, 1.5rem, line-height 1.1):
  card-header level h3, table sub-heads."* The remaining `<h1>` →
  `<h3>` jump in `_home_out.html` (no intermediate `<h2>` section
  heading above the grid) is out of scope for S3.3.1 and routes to S4.1.

Routed forward per §0.4 (locked in §9 rollup):
- [S3.3.1 cross-cluster] `_home_out.html:75-88` 3-up `col-md-4` grid
  composition (identical-card-grid hard hit) → S4.1 in-surface. The partial
  side now differentiates `coming_soon`; the composition reshape (1
  featured WC card + paired coming-soon strips) belongs to S4.1 when it
  reshapes `_home_out.html`.
- [S3.3.1 in-surface] `_game_tiles_compact.html:28-29` slug-branched
  display copy (`game.display_name.split()[0] if game.slug == 'cfb' else
  'Golf'`, hardcoded `Sep 3` / `2027` launch dates) → S3.3.2. Hoist into
  `home_context.py` as pre-resolved `tile_meta` dicts, or add optional
  `short_name` / `launch_label` fields to `GameRegistryEntry`.
- [S3.3.1 ship-as-is] `_game_card.html` `featured` state declared but not
  wired by any caller. Kept dormant; PI-B made the dormant variant
  brand-compliant so it's safe to wire when S4.1 reshapes `_home_out.html`.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()
INDEX = (ROOT / 'core' / 'main' / 'templates' / 'main' / 'index.html').read_text()
GAME_CARD = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_game_card.html').read_text()
TILES_COMPACT = (
    ROOT / 'core' / 'main' / 'templates' / 'main' / '_game_tiles_compact.html'
).read_text()


def _state_block(state: str) -> str:
    """Return the `_game_card.html` markup for a single Jinja state branch.

    The partial is one `{% if %}` / `{% elif %}` chain; this slices the block
    between `state == 'X'` and the next `{% elif %}` / `{% endif %}` so each
    test can assert on the right state in isolation.
    """
    pattern = re.compile(
        rf"state\s*==\s*'{state}'\s*%\}}(.*?)(?=\{{%\s*(?:elif|endif))",
        re.DOTALL,
    )
    match = pattern.search(GAME_CARD)
    assert match, f"_game_card.html missing `state == '{state}'` branch"
    return match.group(1)


def _css_block(selector: str) -> str:
    """Return all CSS declarations matching a selector across the stylesheet.

    Concatenated so any rule-set targeting the selector contributes to the
    assertion. Useful for catching duplicated/overlapping declarations.
    """
    blocks = re.findall(
        rf'{re.escape(selector)}[^{{]*\{{[^}}]*\}}',
        CSS,
    )
    return '\n'.join(blocks)


# ---------------------------------------------------------------------------
# PI-A: silhouette differentiation between `coming_soon` and the playable
# states (`joined` / `available` / `logged_out`).
# ---------------------------------------------------------------------------

def test_game_card_pia_coming_soon_drops_card_footer():
    """`coming_soon` must NOT carry the `.card-footer` block. The footer was
    the silhouette that twinned this state with `logged_out`/`available`."""
    coming_soon = _state_block('coming_soon')
    assert 'card-footer' not in coming_soon, (
        "PI-A: `coming_soon` still renders a `.card-footer` — restore "
        "silhouette differentiation by lifting the status into the card body."
    )


def test_game_card_pia_coming_soon_carries_muted_status_eyebrow():
    """`coming_soon` lifts the status badge into the card body (eyebrow
    position above the icon). The `mb-3` utility separates it from the
    icon so it reads as a contextual eyebrow, not a misplaced footer."""
    coming_soon = _state_block('coming_soon')
    pattern = re.compile(
        r'<span\s+class="status-badge\s+status-badge--muted\s+mb-3">Coming Soon</span>'
    )
    assert pattern.search(coming_soon), (
        "PI-A: `coming_soon` must contain the eyebrow-positioned "
        "`.status-badge--muted.mb-3` 'Coming Soon' span. Without it the "
        "card has no contextual signal of its inert state."
    )


def test_game_card_pia_playable_states_keep_card_footer():
    """The footer-bearing CTA silhouette stays the marker of a playable
    state. `joined` / `available` / `logged_out` all preserve their
    `.card-footer` so PI-A's differentiation work isn't accidentally
    undone by a future "clean up footers" sweep."""
    for state in ('joined', 'available', 'logged_out'):
        block = _state_block(state)
        assert 'card-footer' in block, (
            f"PI-A: playable state `{state}` lost its `.card-footer` — "
            f"the gold-CTA silhouette is what distinguishes it from "
            f"`coming_soon`. Restore the footer block."
        )


def test_game_card_pia_coming_soon_softer_grayscale_floor():
    """The pre-S3.3.1 muted variant clamped at `opacity: .55` +
    `filter: grayscale(35%)` — aggressive enough that the card read as
    "broken" rather than "not yet". Softened to .78 + 18%."""
    block = _css_block('.game-card--coming-soon')
    assert 'opacity: .78' in block, (
        "PI-A: `.game-card--coming-soon { opacity }` must be .78 (was .55) "
        "so the card reads as not-yet-open rather than broken."
    )
    assert 'grayscale(18%)' in block, (
        "PI-A: `.game-card--coming-soon { filter: grayscale }` must be "
        "18% (was 35%) — same reason as opacity."
    )


# ---------------------------------------------------------------------------
# PI-B: DESIGN.md compliance retune of `.game-card--featured`.
# ---------------------------------------------------------------------------

def _featured_css() -> str:
    """Slice the `.game-card--featured` CSS region for targeted assertions."""
    pattern = re.compile(
        r'/\* Featured game card[^*]*\*/.*?(?=/\* Coming-soon game card|/\* === )',
        re.DOTALL,
    )
    match = pattern.search(CSS)
    assert match, "PI-B: cannot locate `.game-card--featured` CSS region"
    return match.group(0)


def test_game_card_pib_featured_no_pure_white():
    """DESIGN.md §2 No-Pure-White Rule: *"The literal white (`#FFFFFF`) is
    reserved for `.card` interiors nested on bone."* `.featured-title` and
    `.featured-desc` paint on the dark featured-game-inner gradient — neither
    is a `.card` interior. Lift to `var(--bone)` / `rgba(243,239,230,...)`."""
    region = _featured_css()
    forbidden = re.findall(r'#FFFFFF|#FFF\b', region, re.IGNORECASE)
    assert not forbidden, (
        f"PI-B: `.game-card--featured` CSS region still contains literal "
        f"white hex ({forbidden}). Replace with `var(--bone)` per the "
        f"No-Pure-White Rule."
    )
    white_alpha = re.findall(r'rgba\(\s*255\s*,\s*255\s*,\s*255', region)
    assert not white_alpha, (
        "PI-B: `.game-card--featured` CSS region still contains literal "
        "white-alpha `rgba(255,255,255,...)`. Replace with bone-alpha "
        "`rgba(243,239,230,...)` per the No-Pure-White Rule."
    )


def test_game_card_pib_featured_no_neutral_black_shadow():
    """DESIGN.md §4 Press-Room Shadow Rule: *"All shadows tint with brand
    purple (or gold on CTA-hover). Neutral-gray shadows are slop and break
    the press-room atmosphere. Never use `rgba(0, 0, 0, ...)` directly."*"""
    region = _featured_css()
    black_shadow = re.findall(r'rgba\(\s*0\s*,\s*0\s*,\s*0', region)
    assert not black_shadow, (
        "PI-B: `.game-card--featured` CSS region still contains neutral-"
        "black `rgba(0,0,0,...)` shadow. Replace with chamber-purple "
        "`rgba(28,10,58,...)` per the Press-Room Shadow Rule."
    )


def test_game_card_pib_featured_drops_hardcoded_wc_palette():
    """DESIGN.md §2 Two-Color Rule: *"Game tertiaries (Golf green, CFB
    crimson, WC navy/red) layer ONLY when the surface is scoped under a
    `body.game-<slug>` class."* `.game-card--featured` is consumed by the
    platform home (`/`), which has no `body.game-worldcup` scope. Drop the
    WC navy gradient (`#00122e`, `#002868`, `#001a44`) and the hardcoded WC
    red (`#BF0A30`) badge palette."""
    region = _featured_css()
    wc_hexes = re.findall(
        r'#(?:00122[eE]|002868|001[Aa]44|BF0A30)', region,
    )
    assert not wc_hexes, (
        f"PI-B: `.game-card--featured` CSS region still hardcodes WC "
        f"palette outside a `body.game-worldcup` scope ({wc_hexes}). "
        f"Use CCC purple+gold + `var(--live-red)` instead."
    )


def test_game_card_pib_featured_uses_brand_tokens():
    """The retune must reference the canonical CCC tokens so future palette
    edits propagate. Locked tokens: `var(--bone)` for the title, the
    purple-950 + purple-800 gradient anchors for the inner background, and
    `var(--live-red)` for the "Live Now" badge."""
    region = _featured_css()
    assert 'color: var(--bone)' in region, (
        "PI-B: `.featured-title` must paint `var(--bone)`, not a literal "
        "or alpha-white color."
    )
    assert 'var(--purple-950)' in region and 'var(--purple-800)' in region, (
        "PI-B: `.featured-game-inner` background must use the "
        "`var(--purple-950)` / `var(--purple-800)` brand gradient anchors."
    )
    assert 'color: var(--live-red)' in region, (
        "PI-B: `.featured-badge` must use `var(--live-red)` for the "
        "'Live Now' indicator (DESIGN.md §2 Live and State semantics)."
    )


# ---------------------------------------------------------------------------
# PI-C: `.status-badge--muted` Tinted-Neutral Rule fix.
# ---------------------------------------------------------------------------

def test_status_badge_muted_pic_no_neutral_gray():
    """DESIGN.md §2 Tinted-Neutral Rule: *"All text colors and all gray-
    feeling utility colors carry a subtle purple cast... Don't introduce
    neutrally-gray text or neutrally-gray dividers; pull them toward the
    purple family."* The pre-S3.3.1 declaration used `rgba(120,120,120,...)`
    for background AND border — pure neutral, no tint."""
    block = _css_block('.status-badge--muted')
    neutral = re.findall(r'rgba\(\s*120\s*,\s*120\s*,\s*120', block)
    assert not neutral, (
        f"PI-C: `.status-badge--muted` still uses neutral-gray "
        f"`rgba(120,120,120,...)` ({neutral}). Re-tint with council-purple "
        f"`rgba(58,29,114,...)` per Tinted-Neutral Rule."
    )


def test_status_badge_muted_pic_uses_council_purple_tint():
    """The replacement must reference Council Purple (`#3A1D72` =
    `rgb(58, 29, 114)`) at low alpha for the background AND border, matching
    the sibling `.status-badge--joined`'s gold-tinted pattern."""
    block = _css_block('.status-badge--muted')
    assert 'rgba(58,29,114,.07)' in block, (
        "PI-C: `.status-badge--muted` background must be "
        "`rgba(58,29,114,.07)` — council-purple at 7% opacity."
    )
    assert 'rgba(58,29,114,.20)' in block, (
        "PI-C: `.status-badge--muted` border must be `rgba(58,29,114,.20)` "
        "— council-purple at 20% opacity."
    )


# ---------------------------------------------------------------------------
# Freebies: F1 + F2 source-pattern locks.
# ---------------------------------------------------------------------------

def test_game_card_f1_joined_drops_redundant_checkmark():
    """F1: the gold `.status-badge--joined` pill is self-evident as a
    state marker; the trailing `✓` was redundant markup-as-icon (cf. the
    cross-phase S6.1 routing on similar `✓` / `←` patterns from S2.4.1)."""
    joined = _state_block('joined')
    assert 'Joined ✓' not in joined and 'Joined&nbsp;✓' not in joined, (
        "F1: `Joined ✓` must collapse to `Joined`. The gold pill carries "
        "the state; the checkmark is redundant markup-as-icon."
    )
    assert '>Joined<' in joined, (
        "F1: the `.status-badge--joined` span must still read 'Joined' "
        "(without the trailing checkmark)."
    )


def test_game_card_f2_featured_cta_drops_bi_globe2():
    """F2: with PI-B's CCC purple + gold retune, the `featured` variant no
    longer reads as WC-specific. The generic Bootstrap `bi-globe2` glyph
    was the only icon tying the CTA to "world"; Teko + "Enter the Pool"
    carries the editorial weight without it."""
    featured = _state_block('featured')
    assert 'bi-globe2' not in featured, (
        "F2: `bi bi-globe2` must be removed from the featured CTA — "
        "the brand-retuned variant no longer ties to a WC-globe semantic."
    )
    assert 'Enter the Pool' in featured, (
        "F2: the featured CTA copy 'Enter the Pool' must still be present "
        "(only the icon glyph is dropped)."
    )


# ---------------------------------------------------------------------------
# F3: axe-discovered heading-order alignment.
# ---------------------------------------------------------------------------

def test_game_card_f3_card_titles_use_h3():
    """Card titles must be `<h3>` (DESIGN.md §3 *"card-header level h3"*).
    Before S3.3.1 the partial mixed `<h3>` (featured) with `<h5>` (4 other
    states); axe flagged the page-level `<h1>` → `<h5>` jump as a moderate
    `heading-order` violation. F3 unifies to `<h3>`; the remaining `<h1>`
    → `<h3>` gap routes to S4.1 (S4.1 will add an `<h2>` section heading
    in `_home_out.html` when it reshapes the out-state composition)."""
    # No `<h5 class="game-title">` may remain in the partial.
    assert '<h5 class="game-title"' not in GAME_CARD, (
        "F3: `<h5 class=\"game-title\">` still present in `_game_card.html`. "
        "All card titles must be `<h3>` per DESIGN.md §3."
    )
    # All 4 non-featured states should now render `<h3 class="game-title">`.
    # (The featured state uses `<h3 class="featured-title">`, a different class.)
    h3_count = len(re.findall(r'<h3\s+class="game-title"', GAME_CARD))
    assert h3_count == 4, (
        f"F3: expected 4 `<h3 class=\"game-title\">` occurrences (one per "
        f"non-featured state); found {h3_count}."
    )


# ---------------------------------------------------------------------------
# Dispatcher (index.html) — locked but minimal: 25-line state switch.
# ---------------------------------------------------------------------------

def test_index_dispatcher_routes_all_four_states():
    """`index.html` dispatches to one of four state partials; locking that
    the dispatch logic still references all four states keeps the dispatcher
    honest if a future cleanup ever drops a branch."""
    for state in ('out', 'pre', 'live', 'post'):
        assert (
            f"state == '{state}'" in INDEX
        ), f"index.html dispatcher missing branch for state='{state}'."


def test_index_dispatcher_loads_countdown_only_in_pre():
    """`countdown.js` is only meaningful pre-tournament; loading it in other
    states is wasted bytes. Locked here so a refactor doesn't accidentally
    promote the script tag to the always-on `super()` block."""
    pre_block = re.search(
        r"\{%\s*if\s+state\s*==\s*'pre'\s*%\}(.*?)\{%\s*endif\s*%\}",
        INDEX,
        re.DOTALL,
    )
    assert pre_block, "index.html missing the pre-state script gate."
    assert 'countdown.js' in pre_block.group(1), (
        "index.html `countdown.js` must load only inside the "
        "`state == 'pre'` script gate."
    )
    outside_pre = INDEX.replace(pre_block.group(0), '')
    assert 'countdown.js' not in outside_pre, (
        "index.html must not load `countdown.js` outside the "
        "`state == 'pre'` script gate."
    )


# ---------------------------------------------------------------------------
# _game_tiles_compact.html — routed forward to S3.3.2 for the slug-branch
# hoist; here we lock that the partial still references the registry-
# resolved entries so the S3.3.2 fix can hoist meta without re-finding the
# loop.
# ---------------------------------------------------------------------------

def test_tiles_compact_iterates_coming_soon_games():
    """`_game_tiles_compact.html` must iterate `coming_soon_games` from the
    registry, not a hardcoded list. The slug-branched display copy is
    routed to S3.3.2; the iteration source is not."""
    assert 'for game in coming_soon_games' in TILES_COMPACT, (
        "_game_tiles_compact.html must drive its coming-soon tiles from "
        "the registry's `coming_soon_games`, not a hardcoded list."
    )
