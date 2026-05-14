"""WC Tab Unification — Phase 3 (ROSTER read-only migration) regression locks.

P3 migrated `picks.html`'s three `.card.wc-card.wc-card-flush` wrappers
(desktop pick-row table, post-deadline tiebreak display, pre-deadline
tiebreak sidebar) off the dark navy substrate onto the Casual-Light Stats
pattern. With the template migration, the four `.card.wc-card`-scoped dark
carve-outs P2 introduced to preserve ROSTER on navy lost their only
consumers and were retired in lockstep.

These tests pin the migration so it can't silently drift back:

- PI-1: `picks.html` has zero `.card.wc-card` usage.
- PI-2: `.card.wc-card .pick-events-list .pick-event-item` and
  `.card.wc-card .pick-event-stage` dark carve-outs are absent.
- PI-3: `.card.wc-card .score-events-total` (+ `strong`) and
  `.card.wc-card .score-events-empty` dark carve-outs are absent.
- PI-4: `.card.wc-card .wc-multiplier-chip` dark carve-out is absent; the
  light base at `.wc-multiplier-chip { color: var(--text-primary); … }`
  still survives (property-scoped regex per PR #15 CR R7-D).
- PI-5: `.card.wc-card.player-picks-desktop` table/team-link rule family
  is absent (mirrors P2 PI-7's BOARD-only dark-card rule lockout). The
  cluster-3 `.text-muted` counter-rule on the same compound is NOT in
  scope — it's preserved as an orphan awaiting P5 per the strategy doc.
"""
from pathlib import Path
import re


ROOT = Path(__file__).parent.parent
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'
TPL_DIR = ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup'

CSS = CSS_PATH.read_text()


# ---------------------------------------------------------------------------
# PI-1: picks.html has zero .card.wc-card usage.
# ---------------------------------------------------------------------------

def test_picks_template_has_no_card_wc_card():
    """`picks.html` no longer carries `class="card … wc-card …"` on any
    wrapper. Mirrors P2's `test_board_templates_have_no_card_wc_card` shape:
    order-independent lookaheads (so the test catches `wc-card card`,
    `card wc-card-flush wc-card`, etc.) and full-text `finditer` (so a
    multi-line class attribute from a wrapping formatter is still caught).

    The `.wc-card-flush` modifier survives — it's the zero-padding utility
    class kept by P3 — but `wc-card` as a standalone token must not appear.
    Regex caveat: Python's `\b` treats `-` as a non-word boundary, so a
    naive `\bwc-card\b` matches the `wc-card` prefix inside `wc-card-flush`.
    Use a negative lookahead `(?![\\w-])` on the trailing edge so `wc-card`
    must be followed by a non-name char (space, quote, end of class list).
    """
    picks = TPL_DIR / 'picks.html'
    pattern = re.compile(r'class="(?=[^"]*\bcard\b)(?=[^"]*\bwc-card(?![\w-]))[^"]*"')
    text = picks.read_text()
    occurrences = []
    for m in pattern.finditer(text):
        line_num = text.count('\n', 0, m.start()) + 1
        occurrences.append((line_num, m.group(0)))

    assert occurrences == [], (
        f'Expected zero `.card.wc-card` usages in picks.html post-P3; '
        f'found {len(occurrences)}: {occurrences!r}.'
    )


# ---------------------------------------------------------------------------
# PI-2: .card.wc-card .pick-events-* carve-outs absent.
# ---------------------------------------------------------------------------

def test_pick_events_dark_carve_outs_absent():
    """The two P2 dark-substrate carve-outs for the accordion drill-down
    (`.pick-event-item` + `.pick-event-stage`) were retired in P3 because
    the `_pick_row.html` partial — their only consumer — now renders only
    inside light `.player-picks-desktop` cards.
    """
    forbidden = [
        r'\.card\.wc-card \.pick-events-list \.pick-event-item\s*\{',
        r'\.card\.wc-card \.pick-event-stage\s*\{',
    ]
    for pattern in forbidden:
        assert re.search(pattern, CSS) is None, (
            f'Forbidden dark carve-out re-appeared: `{pattern}`. P3 retired '
            f'this when picks.html migrated off `.card.wc-card`.'
        )


# ---------------------------------------------------------------------------
# PI-3: .card.wc-card .score-events-* carve-outs absent.
# ---------------------------------------------------------------------------

def test_score_events_dark_carve_outs_absent():
    """The three P2 dark-substrate carve-outs for the accordion footer +
    empty state were retired in P3. Their sole consumer was the picks.html
    ROSTER read-only wrapper.
    """
    forbidden = [
        r'\.card\.wc-card \.score-events-total\s*[,{]',
        r'\.card\.wc-card \.score-events-total strong\s*\{',
        r'\.card\.wc-card \.score-events-empty\s*\{',
    ]
    for pattern in forbidden:
        assert re.search(pattern, CSS) is None, (
            f'Forbidden dark carve-out re-appeared: `{pattern}`. P3 retired '
            f'this when picks.html migrated off `.card.wc-card`.'
        )


# ---------------------------------------------------------------------------
# PI-4: .card.wc-card .wc-multiplier-chip carve-out absent; light base intact.
# ---------------------------------------------------------------------------

def test_multiplier_chip_dark_carve_out_absent_and_light_base_intact():
    """The `.card.wc-card .wc-multiplier-chip` carve-out P2 introduced (so
    the chip read bone-on-bone-alpha on navy) was retired in P3 — the
    chip's only `.card.wc-card` consumer was picks.html's now-migrated
    pick-row table. The base `.wc-multiplier-chip` rule (light substrate,
    `color: var(--text-primary)` on `rgba(0, 0, 0, .04)`) is the single
    canonical rendering.

    Property-scoped regex on the base color (negative lookbehind on
    `[-\\w]`) mirrors PR #15 CR R7-D so a future `background-color:` or
    `border-color:` declaration with `var(--text-primary)` can't false-pass.
    """
    # (a) Dark carve-out absent.
    assert '.card.wc-card .wc-multiplier-chip {' not in CSS, (
        '`.card.wc-card .wc-multiplier-chip` carve-out was retired in P3. '
        'A regression here means the cleanup was undone.'
    )

    # (b) Light base intact.
    base_match = re.search(
        r'(?<!\.card\.wc-card )\.wc-multiplier-chip\s*\{([^}]+)\}',
        CSS,
    )
    assert base_match is not None, (
        'Expected the light-substrate `.wc-multiplier-chip` base rule.'
    )
    base_block = base_match.group(1)
    assert re.search(r'(?<![-\w])color:\s*var\(--text-primary\)', base_block), (
        f'`.wc-multiplier-chip` base must paint `color: var(--text-primary)` '
        f'on light substrate; block={base_block!r}.'
    )


# ---------------------------------------------------------------------------
# PI-5: .card.wc-card.player-picks-desktop table+team-link family absent.
# ---------------------------------------------------------------------------

def test_player_picks_desktop_dark_compound_family_absent():
    """The five P2 dark-substrate carve-outs scoped to the compound class
    `.card.wc-card.player-picks-desktop` were retired in P3 when picks.html
    dropped `.wc-card` from its wrapper class list. Locks the family
    individually so a partial restore is also caught.

    The `.text-muted` cluster-3 counter-rule at the same compound
    (`.card.wc-card.player-picks-desktop .table-worldcup > tbody > tr > td
    .text-muted`) is NOT in scope here — per the strategy doc it survives
    as a vestigial orphan awaiting P5's full `.card.wc-card` retirement.
    """
    forbidden = [
        r'\.card\.wc-card\.player-picks-desktop \.table-worldcup > tbody > tr > td\s*\{',
        r'\.card\.wc-card\.player-picks-desktop \.table-worldcup > tbody > tr:hover > td\s*\{',
        r'\.card\.wc-card\.player-picks-desktop \.table-worldcup > tfoot > tr > td\s*\{',
        r'\.card\.wc-card\.player-picks-desktop \.team-link\s*\{',
        r'\.card\.wc-card\.player-picks-desktop \.team-link:hover\s*\{',
    ]
    for pattern in forbidden:
        assert re.search(pattern, CSS) is None, (
            f'Forbidden ROSTER dark compound carve-out re-appeared: '
            f'`{pattern}`. P3 retired this in lockstep with picks.html '
            f'migration; a regression here means the cleanup was undone.'
        )
