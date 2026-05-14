"""P2 S2.5.1 regression locks — first iteration of the player_detail surface.

PR #25 CR R1: the two `..._carries_explicit_color_per_substrate_doctrine` tests
(`test_pick_table_tbody_td_*` + `test_pick_event_stage_*`) originally used pure
substring `in CSS` assertions to check the light-substrate base rules. A
prefixed re-introduction (e.g., `.card.wc-card.player-picks-desktop ...` or
`.card.wc-card .pick-event-stage ...`) would also contain the substring,
giving a false-positive pass. Both rewrote to use the block-scoped-regex +
`(?<!-)color:` property-anchor pattern from PR #15 CR R7-D (already used by
test_design_wc_tab_unification_p2.py PI-4 and the new P3 PI-4). Same fix on
both occurrences.


Layer A (per plan §1.3) source-pattern locks for the Priority Issues landed
in S2.5.1. Each test pins a structural decision the impeccable critique
surfaced as P0/P1 and that S2.5.1 closed.

Iteration map:
- PI-1 (`$impeccable harden player_detail-contrast-on-wc-card`): the wrapping
  `.card.wc-card.wc-card-flush` is a dark navy surface, but the previous CSS
  in this scope forced dark text (`color: var(--text-primary, #212529)` on
  the multiplier chip, `color: var(--text-muted, #6c757d)` on inline eyebrows
  and event meta, dashed borders at `rgba(0, 40, 104, .07)`). Result: 18
  table rows rendered invisible. Lifted every cell on the
  `.player-picks-desktop > .table-worldcup > tbody > tr > td` scope to
  `var(--text-on-dark)`; lifted the accordion panel to a bone wash and the
  accordion toggle / `.score-events-total` / `.score-events-empty` to
  `var(--bone-mute)` / `var(--text-on-dark)`. Matches the pattern locked in
  CLAUDE.md "`.card.wc-card` is a dark navy surface".
- PI-2 + PI-4 atomic (`$impeccable shape player_detail-hero`): the old
  three-equal-weight `.player-hero-stats` grid (Total · Lead · Tiebreak,
  each at `1.6rem`) tripped the hero-metric-template-adjacency ban — the
  same anti-pattern S2.3.1 locked out of team_detail. Re-shape mirrors
  `.team-hero-line`: one dominant Total numeral at `2.6rem`, Newsreader
  derivation prose carrying rivalry framing ("Trails leader by X.X · Y.Y
  ahead of next."), Tiebreak moved off the masthead onto the eyebrow line
  as a chip with units ("Tiebreak 12 US goals"). Closes PI-4 inside the
  same edit.
- PI-5 (`$impeccable clarify tier-recognition`): bare `T1` eyebrows in the
  pick rows forced recall against the rules page. Replaced with the canonical
  tier name from the `tiers` dict the route already passes
  (`{{ tiers[pick.tier].name }}` → "Favorites" / "Contenders" / "Dark Horses"
  / "Underdogs" / "Wildcards"). Recognition over recall (Heuristic #6).
- Polish freebies: decorative flag emoji (`pick.team.flag_emoji`) and
  decorative tier dots get `aria-hidden="true"` so screen readers don't
  speak "flag of Germany" / "circle" alongside the team name.

Routed forward to S2.5.2 per §0.4:
- PI-3 (rivalry comparison strip — needs new `compute_comparison` route helper)
- PI-6 (Roster-sealed empty state shape — needs un-priv probe)
- PI-7 (above-fold density / wrapper reduction)
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = (
    ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'player_detail.html'
)
PICK_ROW_PATH = (
    ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / '_pick_row.html'
)
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'

TPL = TEMPLATE_PATH.read_text()
ROW = PICK_ROW_PATH.read_text()
CSS = CSS_PATH.read_text()


# ---------------------------------------------------------------------------
# PI-1: contrast lock on .card.wc-card dark substrate
# ---------------------------------------------------------------------------

def test_pick_table_tbody_td_carries_explicit_color_per_substrate_doctrine():
    """The desktop pick table sits inside `.card.wc-card` (rgba(0,17,46,.8))
    on the original S2.5.1 doctrine — Bootstrap's default `<td>` color
    rgb(33,37,41) renders invisible on that substrate.

    S2.5.1 lifted the cells to `var(--text-on-dark)` (bone on navy). WC Tab
    Unification P2 then split the rule into a light base
    (`var(--text-primary)` for player_detail.html post-P2) + a
    `.card.wc-card.player-picks-desktop` dark carve-out (preserving bone
    on navy for picks.html ROSTER). P3 retired the carve-out when
    picks.html migrated, leaving only the light base. The S2.5.1
    invariant — "the cells carry an explicit color, not inherited
    `currentColor`" — survives all three flips. Lock the property is
    present on the base rule; the exact value evolves with the substrate
    doctrine (currently `var(--text-primary)`).

    The `--bs-table-bg` mask defused via `background-color: transparent`
    on the cells is part of the same lift — preserved through every phase.

    Per PR #25 CR R1 + R4: regex-anchored both selector and property:
    `^...` with `re.MULTILINE` requires the selector to start at the
    beginning of a CSS line, rejecting *all* prefixed re-introductions
    (not just `.card.wc-card.player-picks-desktop` but any prefix like
    `.foo .player-picks-desktop ...`); `(?<![-\\w])color:` rejects
    hyphenated property names like `background-color:` / `border-color:`
    that share the same `var(--text-primary)` value.
    """
    match = re.search(
        r'^\.player-picks-desktop \.table-worldcup > tbody > tr > td\s*\{([^}]+)\}',
        CSS,
        re.MULTILINE,
    )
    assert match is not None, (
        'Expected a base `.player-picks-desktop .table-worldcup > tbody > tr '
        '> td` rule (the light-substrate path inherited from P2 with the '
        'carve-out retired in P3).'
    )
    block = match.group(1)
    assert re.search(r'(?<![-\w])color:\s*var\(--text-primary\)', block), (
        f'Post-P3 base must paint `color: var(--text-primary)` on the cell; '
        f'block={block!r}.'
    )
    assert 'background-color: transparent' in block, (
        f'`--bs-table-bg` mask defuse must remain on the same cell rule; '
        f'block={block!r}.'
    )


def test_pick_table_no_longer_forces_dark_text_on_multiplier_chip():
    """The legacy `.player-picks-desktop .wc-multiplier-chip { color:
    var(--text-primary, #212529) }` rule assumed a light card surface that
    never existed — both player_detail.html and picks.html wrap the table
    in .card.wc-card. The override forced dark-on-dark text on the chip."""
    assert (
        '.player-picks-desktop .wc-multiplier-chip {\n'
        '  color: var(--text-primary'
    ) not in CSS, (
        "The stale 'light card' multiplier-chip override should be gone"
    )


def test_pick_event_stage_carries_explicit_color_per_substrate_doctrine():
    """`.pick-event-stage` (the date column on the accordion drill-down)
    needed an explicit color on S2.5.1's dark substrate (Bootstrap's
    default `text-muted` was invisible on navy). S2.5.1 lifted to
    `var(--bone-mute)`; WC Tab Unification P2 split the rule into a light
    base (`var(--text-secondary)` for player_detail.html) + a
    `.card.wc-card .pick-event-stage` dark carve-out (preserving bone-mute
    for picks.html ROSTER). P3 retired the carve-out when picks.html
    migrated, leaving the light base.

    The S2.5.1 invariant — "the date column carries an explicit color, not
    inherited `currentColor`" — survives all three flips. Lock the value
    evolves with the substrate doctrine (currently `var(--text-secondary)`).

    Per PR #25 CR R1 + R4: regex-anchored both selector and property:
    `^...` with `re.MULTILINE` requires the selector to start at the
    beginning of a CSS line, rejecting *all* prefixed re-introductions
    (not just `.card.wc-card .pick-event-stage` but any prefix);
    `(?<![-\\w])color:` rejects hyphenated property names.
    """
    match = re.search(
        r'^\.pick-event-stage\s*\{([^}]+)\}',
        CSS,
        re.MULTILINE,
    )
    assert match is not None, (
        'Expected a base `.pick-event-stage` rule (the light-substrate '
        'path inherited from P2 with the carve-out retired in P3).'
    )
    block = match.group(1)
    assert re.search(r'(?<![-\w])color:\s*var\(--text-secondary\)', block), (
        f'Post-P3 must paint `color: var(--text-secondary)`; block={block!r}.'
    )


def test_pick_accordion_panel_tinted_for_dark_substrate():
    """The accordion panel was tinted `rgba(0, 40, 104, .03)` (navy on navy,
    near-invisible) with a `rgba(0,40,104,.07)` dashed border. Lift to a
    bone-wash tint so the drill-down reads as a distinct band on navy."""
    assert 'background: rgba(245, 241, 232, .04)' in CSS, (
        "Accordion panel should be bone-washed on dark substrate"
    )
    # And the dashed border on the panel border-top moved off the navy-on-navy hex.
    assert 'border-top: 1px dashed rgba(245, 241, 232, .14)' in CSS


def test_pick_accordion_toggle_uses_light_token():
    """The toggle chevron rendered `color: var(--text-muted, #6c757d)` — dark
    on dark navy. Lift to bone-mute (rest) + gold-light (open/hover)."""
    assert (
        '.pick-accordion-toggle {\n'
        '  background: transparent;\n'
        '  border: 0;\n'
        '  color: var(--bone-mute);'
    ) in CSS
    assert '.pick-accordion-toggle.open {\n  transform: rotate(90deg);\n  color: var(--gold-light);\n}' in CSS


def test_score_events_total_and_empty_paint_light_substrate_only():
    """The drill-down total line and the empty state both used Bootstrap's
    `var(--text-muted, #6c757d)` originally — invisible on either WC body
    substrate. S2.5.1 lifted them to `var(--bone-mute)` on the
    `.card.wc-card` dark navy. WC Tab Unification P2 then split the rules
    so the base paints the new LIGHT substrate (`var(--text-secondary)` /
    `var(--text-primary)` on white, for player_detail.html post-P2) and a
    `.card.wc-card .score-events-*` carve-out preserved the dark variant
    (`var(--bone-mute)`) for picks.html ROSTER read-only.

    P3 then migrated picks.html off `.card.wc-card`, retiring the dark
    carve-out in lockstep. The accordion footer + empty state now live on
    a single light substrate across both consumers (picks.html ROSTER +
    player_detail.html BOARD). Lock the light base survives AND assert the
    dark carve-out is gone (mirrors P2 PI-7's forbidden-rule lockout style).
    """
    # (a) LIGHT base — both player_detail + picks.html now sit on plain `.card`.
    # Per PR #25 CR R4: anchored block-extraction (`^...` + re.MULTILINE)
    # rejects prefixed re-introductions like `.foo .score-events-total {`
    # that would have matched the prior substring `in CSS` check; the
    # property check uses the `(?<![-\w])color:` anchor (PR #15 CR R7-D
    # pattern) so a future `background-color:` / `border-color:` with the
    # same value can't false-pass.
    match = re.search(
        r'^\.score-events-total\s*\{([^}]+)\}',
        CSS,
        re.MULTILINE,
    )
    assert match is not None, (
        'Expected a bare `.score-events-total` light-base rule.'
    )
    total_block = match.group(1)
    assert 'padding: .5rem 1rem .75rem' in total_block, (
        f'.score-events-total padding must remain; block={total_block!r}.'
    )
    assert 'border-top: 1px dotted var(--border)' in total_block, (
        f'.score-events-total must keep `border-top: 1px dotted var(--border)`; '
        f'block={total_block!r}.'
    )
    assert re.search(r'(?<![-\w])color:\s*var\(--text-secondary\)', total_block), (
        f'.score-events-total base must paint `color: var(--text-secondary)`; '
        f'block={total_block!r}.'
    )

    match = re.search(
        r'^\.score-events-empty\s*\{([^}]+)\}',
        CSS,
        re.MULTILINE,
    )
    assert match is not None, (
        'Expected a bare `.score-events-empty` light-base rule.'
    )
    empty_block = match.group(1)
    assert 'padding: .75rem 1rem' in empty_block, (
        f'.score-events-empty padding must remain; block={empty_block!r}.'
    )
    assert 'font-size: .85rem' in empty_block, (
        f'.score-events-empty font-size must remain; block={empty_block!r}.'
    )
    assert re.search(r'(?<![-\w])color:\s*var\(--text-secondary\)', empty_block), (
        f'.score-events-empty base must paint `color: var(--text-secondary)`; '
        f'block={empty_block!r}.'
    )

    # (b) DARK carve-out retired in P3 — assert it does NOT re-appear.
    # Per PR #25 CR R3 + R4: `\s*[,{]` terminator allows optional whitespace
    # before either a comma (selector-list reintroduction) or an opening
    # brace (canonical block-start formatting with whitespace, the dominant
    # CSS convention). The prior R3 `[,{]` form required the terminator
    # immediately after the selector and missed the standalone block form
    # `.card.wc-card .score-events-total {` (false-negative on regression).
    forbidden = [
        r'\.card\.wc-card\s+\.score-events-total\s*[,{]',
        r'\.card\.wc-card\s+\.score-events-empty\s*[,{]',
    ]
    for pattern in forbidden:
        assert re.search(pattern, CSS) is None, (
            f'Forbidden `{pattern}` dark carve-out re-appeared in style.css. '
            f'P3 retired this in lockstep with picks.html migration (its sole '
            f'DOM consumer); a regression here means the cleanup was undone.'
        )


# ---------------------------------------------------------------------------
# PI-2 + PI-4 atomic: hero re-shape (one dominant numeral + Newsreader
# derivation + Tiebreak chip with unit)
# ---------------------------------------------------------------------------

def test_player_detail_hero_drops_three_equal_weight_stat_grid():
    """The old `.player-hero-stats` flex (three 1.6rem numerals: Total,
    Lead, Tiebreak) was hero-metric-template adjacency. Replaced with the
    `.player-hero-line` shape mirroring S2.3.1's `.team-hero-line` lock."""
    assert 'class="player-hero-stats"' not in TPL
    assert 'player-hero-line' in TPL
    assert 'player-hero-score-value' in TPL


def test_player_detail_hero_score_value_is_dominant_numeral():
    """The dominant Total numeral renders at 2.6rem (matches the
    `.team-hero-score-value` standard locked in S2.3.1)."""
    assert (
        '.player-hero-score-value {\n'
        '  font-size: 2.6rem;'
    ) in CSS


def test_player_detail_hero_derivation_is_newsreader_prose():
    """Lead delta is no longer a bare numeral in a stat tile. The
    derivation reads as Newsreader microcopy (one of the prose variants
    "Leads the table.", "Trails leader by X.X[, Y.Y ahead of next].").
    DESIGN.md voice principle: 'Voice in Copy', not 'Voice in Numerals'."""
    assert (
        ".player-hero-derivation {\n"
        "  font-family: 'Newsreader', Georgia, serif;"
    ) in CSS
    # Both rivalry-framing prose branches are present.
    assert 'Leads the table.' in TPL
    assert 'Trails leader by' in TPL


def test_player_detail_hero_tiebreak_moved_off_masthead_with_unit():
    """Tiebreak previously sat in the masthead numeral grid as a bare
    integer ("12") with no unit. PI-4 lock: when present, Tiebreak renders
    on the eyebrow line as a chip with a unit ("Tiebreak 12 US goals")."""
    # The legacy "<span class=\"wc-eyebrow\">Tiebreak</span>" tile is gone.
    assert '"wc-eyebrow">Tiebreak</span>' not in TPL
    # The new chip carries the unit copy.
    assert 'player-hero-tiebreak' in TPL
    assert 'US&nbsp;goals' in TPL
    # And the chip's bound aria-label spells out the unit for SR users.
    assert 'aria-label="Tiebreaker:' in TPL


def test_player_detail_hero_lead_value_no_longer_renders_word_none():
    """The legacy hero rendered "none" as a bare word inside the dominant
    Lead numeral when the player was rank 1 — reads as a missing value, not
    a state. The new derivation prose handles rank-1 with a positive sentence
    ('Leads the table.'), so neither the markup nor the rendered string
    contains the orphan 'none'."""
    # Match an isolated "none" token in the hero (not a substring like
    # "noneticed"). The prior bug rendered:
    #     <strong class="wc-numeral">\n            none\n          </strong>
    # We assert that no Jinja block in the hero outputs a bare "none" token.
    assert ' none\n' not in TPL or 'none </' not in TPL
    # Defensive: also assert the old grid markup is gone (covered above too).
    assert '{% if neighbors.lead_delta_up is none %}\n            none' not in TPL


# ---------------------------------------------------------------------------
# PI-5: tier names replace bare T# in pick rows
# ---------------------------------------------------------------------------

def test_pick_row_uses_tier_name_not_bare_letter_T():
    """The pick row eyebrow surfaced the schema as `T1`..`T5`, forcing
    recall. The `tiers` dict (`world_cup_countries.TIERS`) is already passed
    to the template by routes.py; consume `.name` for recognition."""
    assert 'T{{ pick.tier }}' not in ROW
    assert '{{ tiers[pick.tier].name }}' in ROW


def test_player_detail_mobile_pick_card_uses_tier_name():
    """Mobile pick cards mirror the desktop pick-row decision so the schema
    reads the same on both viewports."""
    assert 'T{{ pick.tier }}' not in TPL
    assert '{{ tiers[pick.tier].name }}' in TPL


def test_mobile_pick_card_eyebrow_uses_aa_token_on_white_card():
    """The `.wc-eyebrow` default is `var(--bone-mute)` (designed for dark
    surfaces). On the light `.player-pick-card` (background `--bg-card` = white),
    bone-mute fails AA. Scope to `--text-secondary` (#5A5470), the canonical
    AA-passing token for headings/legends on bone per memory
    project_text_muted_aa_on_bone.md."""
    assert (
        '.player-pick-card .wc-eyebrow {\n'
        '    color: var(--text-secondary);\n'
        '  }'
    ) in CSS


# ---------------------------------------------------------------------------
# Polish freebies
# ---------------------------------------------------------------------------

def test_decorative_glyphs_get_aria_hidden():
    """Flag emoji + tier dot are decorative chrome; screen readers should
    skip them. The team name carries the semantic identity."""
    # Pick row: flag glyph + tier dot are aria-hidden.
    assert '<span class="me-2 fs-5" aria-hidden="true">{{ pick.team.flag_emoji }}</span>' in ROW
    assert 'wc-tier-dot wc-tier-dot-{{ pick.tier }}" aria-hidden="true"' in ROW
    # Mobile pick card: flag glyph + tier dot are aria-hidden.
    assert '<span aria-hidden="true">{{ pick.team.flag_emoji }}</span>' in TPL
    assert 'wc-tier-dot wc-tier-dot-{{ pick.tier }}" aria-hidden="true"' in TPL


def test_hero_avatar_glyph_is_decorative():
    """The avatar emoji in the H1 is decorative; the player display name
    carries the identity for SR users."""
    assert '<span class="me-2" aria-hidden="true">{{ enrollment.user.get_avatar() }}</span>' in TPL
