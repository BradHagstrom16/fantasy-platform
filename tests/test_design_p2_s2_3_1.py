"""P2 S2.3.1 regression locks — first iteration of the team_detail surface.

Layer A (per plan §1.3) source-pattern locks for the four Priority Issues
landed in S2.3.1. Each test pins a structural decision the impeccable
critique surfaced as P1 and that S2.3.1 closed.

Iteration map:
- PI-1+3 (`$impeccable shape team_detail-hero`): the masthead now renders
  a single dominant Scored numeral with the multiplier chip inline and a
  Base × Multiplier derivation microline; the duplicate Tier tile moved up
  onto the eyebrow line. The owned-state hero variant (`wc-hero-grad-owned`)
  carries warmer atmosphere via Voice in Copy ("Your pick · ") rather than
  inventing new chrome.
- PI-2 (`$impeccable shape path-to-crown`): every path segment now carries
  an icon (won/current/eliminated/future), removing the color-only state
  encoding that PRODUCT.md a11y rule bans. <ol>+<li> + aria-current="step"
  for the current segment.
- PI-4 (`$impeccable adapt fixture-row-mobile`): un-played fixture rows
  collapse to 3 columns on mobile so the dead Pts column doesn't claim
  ~12% of horizontal space; the empty pts cell renders as an aria-hidden
  visibility-hidden spacer on desktop. Opponent flag + FIFA code split into
  named flex children with explicit gap so the emoji glyph never overlaps
  the code at the squeezed 1fr column.
- PI-5 (`$impeccable adapt picker-list-tap-targets`): .picker-link enforces
  the 44×44 mobile tap-target floor (P0 S0.3 globalized; surface-scoped
  utilities can still regress).
- Freebies: HTML-entity sweep on lines 125 & 134 (`&ndash;` / `&middot;` →
  real Unicode glyphs); Bootstrap `.text-muted` on the dark navy ribbon
  blurb replaced with a scoped `.ownership-ribbon-blurb` class.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = (
    ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'team_detail.html'
)
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'

TPL = TEMPLATE_PATH.read_text()
CSS = CSS_PATH.read_text()


# ---------------------------------------------------------------------------
# PI-1+3: hero stat re-shape, owned-state variant, duplicate-Tier-tile gone.
# ---------------------------------------------------------------------------

def test_hero_no_longer_renders_four_equal_weight_stat_tiles():
    """The old `.team-hero-stats` 4-tile flex (Tier · Multiplier · Base ·
    Scored at equal weight) read as a hero-metric template adjacency. The
    re-shape uses `.team-hero-line` with one dominant Scored numeral."""
    assert 'team-hero-line' in TPL, "Expected new .team-hero-line shape"
    assert 'team-hero-score-value' in TPL, "Expected dominant Scored numeral"
    # Old shape gone from the team_detail template specifically.
    assert 'class="team-hero-stats"' not in TPL, (
        "Old 4-tile .team-hero-stats grid should be replaced on team_detail"
    )


def test_hero_does_not_render_duplicate_tier_tile():
    """Tier appears in the eyebrow line; a second 'Tier' tile in the stat
    strip duplicated information and contributed to hero-metric-template
    adjacency. The re-shape promotes the tier-dot to the eyebrow line."""
    # The eyebrow line carries the tier-dot; no separate <span class="wc-eyebrow">Tier</span>
    # block remains in the stat strip.
    eyebrow_count = TPL.count('<span class="wc-eyebrow">Tier</span>')
    assert eyebrow_count == 0, (
        f"No standalone 'Tier' eyebrow tile expected; found {eyebrow_count}"
    )
    # And the tier-dot does sit on the eyebrow line.
    assert 'wc-tier-dot wc-tier-dot-' in TPL


def test_hero_carries_owned_state_voice_via_copy_not_chrome():
    """Owned state surfaces through (a) a 'Your pick · ' eyebrow prefix and
    (b) a `wc-hero-grad-owned` gradient variant — Voice in Copy + atmosphere,
    not new chrome (DESIGN.md design principle #2)."""
    assert "{% if user_owns %}Your pick · {% endif %}" in TPL
    assert 'wc-hero-grad-owned' in TPL
    assert '.page-hero.wc-hero-grad.wc-hero-grad-owned' in CSS, (
        "Owned hero variant must be defined in style.css with a warmer gradient"
    )


def test_team_hero_score_value_is_visually_dominant():
    """The Scored numeral renders at ~2.6rem so it dominates the masthead
    (the old equal-weight tiles all rendered at 1.6rem)."""
    # Match the team-hero-score-value font-size declaration.
    import re
    match = re.search(
        r'\.team-hero-score-value\s*\{[^}]*font-size:\s*([0-9.]+rem)',
        CSS,
    )
    assert match, "Expected .team-hero-score-value to declare a font-size"
    size_rem = float(match.group(1).rstrip('rem'))
    assert size_rem >= 2.2, (
        f".team-hero-score-value font-size must dominate (≥2.2rem); got {size_rem}rem"
    )


# ---------------------------------------------------------------------------
# PI-2: path-to-crown segment icons (no color-only state encoding).
# ---------------------------------------------------------------------------

def test_path_segments_render_as_ordered_list_with_aria_current():
    """The 6-segment path is a sequence; <ol>+<li> + aria-current='step'
    on the current segment is the right semantic shape for assistive tech."""
    assert '<ol class="path-segments"' in TPL
    assert 'aria-label="Path through the tournament"' in TPL
    assert "aria-current=\"{% if seg.status == 'current' %}step{% else %}false{% endif %}\"" in TPL


def test_every_path_segment_status_carries_an_icon():
    """No status reads as color-only: won → check, current → record-circle,
    eliminated → x, future → empty circle. PRODUCT.md a11y rule pairs
    state color with icons."""
    for marker in (
        "{% if is_crown %}<i class=\"bi bi-trophy-fill\"></i>",
        "{% elif seg.status == 'won' %}<i class=\"bi bi-check-lg\"></i>",
        "{% elif seg.status == 'eliminated' %}<i class=\"bi bi-x-lg\"></i>",
        "{% elif seg.status == 'current' %}<i class=\"bi bi-record-circle-fill\"></i>",
        "{% else %}<i class=\"bi bi-circle\"></i>",
    ):
        assert marker in TPL, f"Path segment icon branch missing: {marker!r}"


def test_path_segment_icon_class_styled_per_status():
    """Each status declares a color rule on `.path-segment-{status}
    .path-segment-icon` so screenshot-level legibility is locked."""
    for sel in (
        '.path-segment-future .path-segment-icon',
        '.path-segment-won .path-segment-icon',
        '.path-segment-current .path-segment-icon',
        '.path-segment-eliminated .path-segment-icon',
    ):
        assert sel in CSS, f"Missing styled selector: {sel}"


def test_current_segment_pulse_respects_reduced_motion():
    """The current-segment pulse animation must be disabled under
    prefers-reduced-motion (PRODUCT.md motion accessibility)."""
    assert '@keyframes path-current-pulse' in CSS
    # The path-current-pulse keyframes block ends right before the
    # reduced-motion guard scoped to the same animation; anchor on that
    # adjacency rather than the first reduced-motion @media in the file
    # (which scopes home-shell champion-glow, not path segments).
    pulse_idx = CSS.find('@keyframes path-current-pulse')
    assert pulse_idx != -1
    nearby = CSS[pulse_idx:pulse_idx + 600]
    assert '@media (prefers-reduced-motion: reduce)' in nearby
    assert '.path-segment-current .path-segment-icon { animation: none' in nearby


# ---------------------------------------------------------------------------
# PI-4: mobile fixture-row adapt + entity sweep freebie.
# ---------------------------------------------------------------------------

def test_un_played_fixture_row_carries_pending_modifier_class():
    """Un-played rows pick up `fixture-row-pending` so mobile CSS can
    collapse them to 3 columns (the dead Pts cell stops claiming space)."""
    assert "{% if not match.is_completed %} fixture-row-pending{% endif %}" in TPL


def test_empty_pts_cell_is_aria_hidden_visibility_spacer():
    """Desktop keeps 4-col grid alignment by rendering a visibility-hidden
    spacer instead of the '·' placeholder dot. ARIA hidden so screen
    readers don't announce a phantom cell."""
    assert 'class="fixture-pts fixture-pts-empty" aria-hidden="true"' in TPL
    assert '.fixture-pts-empty' in CSS
    assert 'visibility: hidden' in CSS


def test_mobile_pending_fixture_row_drops_pts_column():
    """At ≤575.98px, `.fixture-row-pending` re-grids to 3 columns and
    hides the empty pts spacer entirely so the opponent cell breathes."""
    import re
    block = re.search(
        r'@media \(max-width: 575\.98px\) \{(.+?)\n\}\n',
        CSS, re.DOTALL,
    )
    assert block, "Expected mobile media block for fixture-row"
    # Pending-row 3-col grid is in the same media block.
    assert '.fixture-row-pending' in block.group(1)
    assert 'grid-template-columns: 80px 1fr 60px' in block.group(1)


def test_fixture_opponent_uses_named_flag_and_code_spans():
    """The opponent cell splits flag + code into named flex children with
    an explicit gap so the emoji glyph never collides with the FIFA code
    at the squeezed 1fr column on mobile."""
    assert '<span class="fixture-flag">' in TPL
    assert '<span class="fixture-code">' in TPL
    assert '.fixture-opponent .fixture-flag' in CSS
    assert '.fixture-opponent .fixture-code' in CSS


def test_fixture_row_drops_html_entity_dashes_and_dots():
    """Freebie entity sweep: `&ndash;` (line 125) + `&middot;` (line 134)
    replaced with real Unicode glyphs / structural empties. Same pattern
    as S2.2.1's schedule sweep."""
    assert '&ndash;' not in TPL, "Use real Unicode '–' glyph, not entity"
    assert '&middot;' not in TPL, "Empty pts cell should be a spacer, not a '·' entity"
    # The Unicode dash should appear inside the score render expression.
    assert 'home_score }}–{{' in TPL or '–{{ match.home_score }}' in TPL


# ---------------------------------------------------------------------------
# PI-5: picker-link 44×44 mobile tap-target floor.
# ---------------------------------------------------------------------------

def test_picker_link_meets_44_min_height_floor():
    """P0 S0.3 globalized 44×44 across chrome; surface-scoped utilities
    can still regress. .picker-link must declare min-height:44px and
    inline-flex alignment so the tap target hits the floor at ≤375px."""
    import re
    block = re.search(
        r'\.picker-list-item \.picker-link \{(.+?)\}',
        CSS, re.DOTALL,
    )
    assert block, "Expected .picker-list-item .picker-link rule"
    rule_body = block.group(1)
    assert 'min-height: 44px' in rule_body
    assert 'display: inline-flex' in rule_body


def test_picker_link_carries_focus_visible_outline():
    """Keyboard reachability: focus-visible must produce a clearly visible
    outline (not just the border-color hover swap that mouse users see)."""
    assert '.picker-list-item .picker-link:focus-visible' in CSS
    # Outline declaration scoped to the focus-visible rule.
    fv_block_idx = CSS.find('.picker-list-item .picker-link:focus-visible')
    assert fv_block_idx != -1
    rule_window = CSS[fv_block_idx:fv_block_idx + 400]
    assert 'outline: 2px solid' in rule_window


def test_picker_grid_step_drops_to_140_so_two_pills_fit_at_375():
    """Cap the auto-fill minmax at 140px so a 375px viewport seats two
    pills per row instead of stacking single-column."""
    assert 'minmax(140px, 1fr)' in CSS


# ---------------------------------------------------------------------------
# Freebie: ribbon blurb scoped color so it holds AA on dark navy.
# ---------------------------------------------------------------------------

def test_ribbon_blurb_no_longer_uses_bootstrap_text_muted_on_dark_surface():
    """The `.ownership-ribbon` substrate is `rgba(0,17,46,.6)` (dark navy);
    Bootstrap `.text-muted` resolves to #6c757d (neutral gray) and reads
    sub-AA against it. Replaced with a scoped `.ownership-ribbon-blurb`
    that tints toward `--bone-mute`."""
    assert 'class="ownership-ribbon-blurb mt-1"' in TPL
    assert '.ownership-ribbon .ownership-ribbon-blurb' in CSS


# ---------------------------------------------------------------------------
# Bugfix 2026-06-01: the Path-to-the-Crown row was authored for the retired
# dark `.card.wc-card` and never migrated in the P5 Casual-Light unification.
# On the bone body its labels rendered bone-on-bone (~1:1) and its won-checks
# washed gold-on-bone (~1.4:1). Migrate the row to the light substrate.
# ---------------------------------------------------------------------------

def _css_rule_block(selector):
    """Return the declaration block ({...}) for the first rule whose selector
    list begins exactly with `selector` followed by ` {` (avoids matching a
    descendant/compound selector that merely contains it)."""
    import re
    m = re.search(
        r'(?<![-\w.])' + re.escape(selector) + r'\s*\{([^}]*)\}', CSS,
    )
    return m.group(1) if m else None


def test_path_segment_base_not_on_dark_navy_substrate():
    """`.path-segment` must not fill with the dark navy `rgba(0, 17, 46, …)`
    designed for the retired `.card.wc-card`; on the bone body that fill is
    near-invisible and its bone text reads ~1:1. It sits on a light surface."""
    block = _css_rule_block('.path-segment')
    assert block is not None, '.path-segment rule block not found'
    assert 'rgba(0, 17, 46' not in block, (
        '.path-segment still uses the dark-navy fill — migrate to the '
        'Casual-Light substrate so labels and checks read on the bone body'
    )


def test_path_segment_label_eyebrow_lifted_off_bone_mute():
    """The per-segment stage label (`.path-segment .wc-eyebrow`) carried the
    navy-calibrated `--bone-mute` default → invisible bone-on-bone. A scoped
    rule must lift it so GROUP/R32/…/FINAL read on the light substrate."""
    assert '.path-segment .wc-eyebrow' in CSS, (
        'missing scoped color lift for the segment stage label on light substrate'
    )


def test_path_segment_won_icon_uses_cream_safe_gold():
    """The won-check must move off `--gold-light` (#F2D36B, ~1.4:1 on bone)
    to the cream-safe `--gold-dark` (~4.6:1) so a cleared stage reads."""
    block = _css_rule_block('.path-segment-won .path-segment-icon')
    assert block is not None
    assert 'var(--gold-dark)' in block
    assert 'var(--gold-light)' not in block


def test_path_segment_champion_class_styled():
    """The champion's Final segment gets a ceremonial `.path-segment-champion`
    treatment (gold trophy) so winning it all looks distinct from a plain
    cleared stage."""
    assert '.path-segment-champion' in CSS


def test_path_section_eyebrow_legible_on_light_substrate():
    """The section's OWN eyebrow ('Path to the Crown' / 'Ran the table') sits
    on the bone body, but plain `.wc-eyebrow` is `--bone-mute` (~1:1,
    invisible) and `.wc-eyebrow-gold` is washed `--gold-light` (~1.3:1). The
    section carries a `.team-path` hook and a scoped lift: `--text-secondary`
    for the plain/alive label, cream-safe `--gold-dark` for the champion
    label. (`.wc-eyebrow-red` already reads on bone, kept as-is.)"""
    import re
    assert 'class="team-path mb-4"' in TPL, 'section needs a .team-path hook for the lift'
    assert '.team-path > .wc-eyebrow' in CSS
    gold = re.search(r'\.team-path > \.wc-eyebrow-gold\s*\{([^}]*)\}', CSS)
    assert gold and 'var(--gold-dark)' in gold.group(1), (
        'champion section eyebrow must use cream-safe --gold-dark on bone, '
        'not the washed --gold-light'
    )
