"""WC Tab Unification — Phase 2 (BOARD body migration) regression locks.

P2 migrated the World Cup BOARD's content cards off the dark `.card.wc-card`
surface onto the Casual-Light Stats pattern. Templates touched:
`leaderboard.html` (desktop standings + mobile cards) and `player_detail.html`
(desktop picks table + sealed-fallback). CSS rules either flipped to red on
white, split into a light base + `.card.wc-card`-scoped carve-out (preserving
ROSTER until P3), or were removed outright when their BOARD-only consumers
disappeared.

These tests pin the migration so it can't silently drift back:

- PI-1: BOARD templates have zero `.card.wc-card` usage.
- PI-2: `.your-standing-tribune + .card` red-divider rule exists; the
  pre-P2 `.your-standing-tribune + .card.wc-card` gold form is gone.
- PI-3: `.card.leaderboard-card-current` carries a red border on the
  light substrate; the pre-P2 `.card.wc-card.leaderboard-card-current`
  gold form is gone.
- PI-4: `.player-picks-desktop .table-worldcup > tbody > tr > td` base
  paints `var(--text-primary)` (light substrate, player_detail.html).
- PI-5: `.card.wc-card.player-picks-desktop .table-worldcup > tbody > tr
  > td` (and the four sibling rules in that carve-out block) were
  retired in P3 when picks.html migrated off `.card.wc-card`. Locked here
  in the lockstep-rewrite style P2 used for the tribune gold→red flip
  (`test_pi1_red_divider_rule_threads_tribune_to_standings`): the same
  test ID survives, its invariant is now "carve-out absent" instead of
  "carve-out present".
- PI-6: `.pick-events-list .pick-event-item` base paints a dark-on-light
  pair (`var(--text-primary)` text + `var(--border)` dashed border); the
  `.card.wc-card .pick-events-list .pick-event-item` carve-out was
  retired in P3 in the same lockstep rewrite.
- PI-7: BOARD-only dark-card rule families removed in lockstep
  (`.card.wc-card .leaderboard-table ...`, `.card.wc-card.leaderboard-card`,
  `.card.wc-card.leaderboard-card .rank-delta-*`). Parallels P1's removal
  of `.card.wc-card .btn-game` when CTAs went global red.
"""
from pathlib import Path
import re


ROOT = Path(__file__).parent.parent
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'
TPL_DIR = ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup'

CSS = CSS_PATH.read_text()

BOARD_TEMPLATES = [
    TPL_DIR / 'leaderboard.html',
    TPL_DIR / 'player_detail.html',
]


# ---------------------------------------------------------------------------
# PI-1: BOARD templates have zero .card.wc-card usage.
# ---------------------------------------------------------------------------

def test_board_templates_have_no_card_wc_card():
    """leaderboard.html and player_detail.html have no `class="card wc-card …"`
    matches. Mirrors P1's `test_hub_templates_have_no_card_wc_card_except_*`
    pattern but without exceptions — neither BOARD template carries a
    ceremonial dark wrapper (the champion banner exception lives on HUB).
    """
    # Order-independent: lookaheads require both `card` and `wc-card` tokens
    # somewhere in the class list, regardless of which comes first or what
    # other classes (`border-0`, `animate-in`, …) interleave between them.
    pattern = re.compile(r'class="(?=[^"]*\bcard\b)(?=[^"]*\bwc-card\b)[^"]*"')
    occurrences = []
    # Scan the full template text (not splitlines+per-line search) so a
    # multi-line class attribute — `class="card\n  wc-card border-0"` from a
    # formatter that wrapped a long attribute — is still caught. `[^"]*` in
    # the pattern already matches newlines (negated char classes include
    # `\n`); the per-line scan was the bottleneck. Line numbers are derived
    # from `match.start()` for the reported `occurrences` entry.
    for tpl in BOARD_TEMPLATES:
        text = tpl.read_text()
        for m in pattern.finditer(text):
            line_num = text.count('\n', 0, m.start()) + 1
            occurrences.append((tpl.name, line_num, m.group(0)))

    assert occurrences == [], (
        f'Expected zero `.card.wc-card` usages across BOARD templates '
        f'(leaderboard.html, player_detail.html); found {len(occurrences)}: '
        f'{occurrences!r}.'
    )


# ---------------------------------------------------------------------------
# PI-2: Your Position tribune red-divider rule.
# ---------------------------------------------------------------------------

def test_tribune_divider_uses_red_on_plain_card_selector():
    """`.your-standing-tribune + .card { border-top: 2px solid var(--wc-red)
    !important; }` rule exists, with the mobile-sibling companion.

    Companion to `test_design_p6_s6_1_3.py::test_pi1_red_divider_rule_*` —
    that test owns the assertion; this one duplicates the headline check
    here so the P2 file is self-contained and a future reader scanning the
    P2 locks doesn't have to chase a sibling test file. Both can fail
    independently if either selector form regresses.
    """
    assert re.search(
        r'\.your-standing-tribune \+ \.card,\s*'
        r'\.your-standing-tribune \+ \.card \+ \.d-md-none\s*\{'
        r'\s*border-top:\s*2px solid var\(--wc-red\)\s*!important\s*;',
        CSS,
    ), (
        'P2 tribune divider must carry `.your-standing-tribune + .card { '
        'border-top: 2px solid var(--wc-red) !important; }` (with the mobile '
        'sibling selector).'
    )
    assert '.your-standing-tribune + .card.wc-card' not in CSS, (
        'Pre-P2 form `.your-standing-tribune + .card.wc-card` must not '
        're-appear — P2 flipped to `.your-standing-tribune + .card`.'
    )


# ---------------------------------------------------------------------------
# PI-3: leaderboard-card-current red border on plain .card.
# ---------------------------------------------------------------------------

def test_leaderboard_card_current_carries_red_border_on_plain_card():
    """`.card.leaderboard-card-current { border: 1px solid var(--wc-red)
    !important; }` exists; the pre-P2 `.card.wc-card.leaderboard-card-current
    { … var(--game-accent) … }` form is gone.

    The mobile current-user emphasis. Gold (`--game-accent`) was correct on
    the old navy substrate; red is correct on the new white substrate per
    the accent doctrine (red as primary "this is you" on light WC surfaces).
    """
    assert re.search(
        r'\.card\.leaderboard-card-current\s*\{\s*'
        r'border:\s*1px solid var\(--wc-red\)\s*!important\s*;',
        CSS,
    ), (
        'P2 mobile current-user emphasis must paint '
        '`.card.leaderboard-card-current { border: 1px solid var(--wc-red) '
        '!important; }`.'
    )
    assert not re.search(
        r'\.card\.wc-card\.leaderboard-card-current\s*[,{]',
        CSS,
    ), (
        'Pre-P2 `.card.wc-card.leaderboard-card-current` rule must be '
        'removed — its consumer (mobile leaderboard card on `.card.wc-card`) '
        'is gone.'
    )


# ---------------------------------------------------------------------------
# PI-4 + PI-5: .player-picks-desktop substrate split.
# ---------------------------------------------------------------------------

def test_player_picks_desktop_base_paints_light_substrate():
    """`.player-picks-desktop .table-worldcup > tbody > tr > td { color:
    var(--text-primary); border-color: var(--border); … }` — the LIGHT base.

    player_detail.html migrated to plain `.card` (white) in P2. The previous
    base rule (`color: var(--text-on-dark)`) painted bone text — invisible on
    white. Lock the flip.
    """
    match = re.search(
        r'(?<!\.card\.wc-card)\.player-picks-desktop \.table-worldcup > tbody > tr > td\s*\{([^}]+)\}',
        CSS,
    )
    assert match is not None, (
        'Expected a `.player-picks-desktop .table-worldcup > tbody > tr > td` '
        'base rule (the light-substrate path for player_detail.html post-P2).'
    )
    block = match.group(1)
    # Property-scoped regex (negative lookbehind on `[-\w]`) so a future
    # `background-color: var(--text-primary)` or `border-color: var(--text-on-dark)`
    # can't silently flip either branch. Mirrors PR #15 CR R7-D pattern.
    assert re.search(r'(?<![-\w])color:\s*var\(--text-primary\)', block), (
        f'`.player-picks-desktop` base must paint `color: var(--text-primary)` '
        f'on the new light substrate; block={block!r}.'
    )
    assert not re.search(r'(?<![-\w])color:\s*var\(--text-on-dark\)', block), (
        f'`.player-picks-desktop` base must not paint '
        f'`color: var(--text-on-dark)` anymore — that token is for the ROSTER '
        f'`.card.wc-card` carve-out (P3 retires it); block={block!r}.'
    )


def test_player_picks_desktop_dark_carve_out_was_retired_in_p3():
    """`.card.wc-card.player-picks-desktop` carve-out for the `.table-worldcup
    > tbody > tr > td` cell (and its four siblings: `tr:hover > td`,
    `tfoot > tr > td`, `.team-link`, `.team-link:hover`) was retired in P3
    when picks.html migrated off `.card.wc-card` — the carve-out's only
    consumer disappeared. Mirrors P2 PI-7's "BOARD-only dark-card rule
    families removed in lockstep" pattern.

    The cluster-3 `.text-muted` counter-rule at
    `.card.wc-card.player-picks-desktop .table-worldcup > tbody > tr > td
    .text-muted` is NOT asserted here — it survives as an orphan awaiting
    P5's full `.card.wc-card` retirement (deferred per the strategy doc's
    "preserve cross-tab carve-outs until P5" note).
    """
    forbidden = [
        r'\.card\.wc-card\.player-picks-desktop \.table-worldcup > tbody > tr > td\s*[,{]',
        r'\.card\.wc-card\.player-picks-desktop \.table-worldcup > tbody > tr:hover > td\s*[,{]',
        r'\.card\.wc-card\.player-picks-desktop \.table-worldcup > tfoot > tr > td\s*[,{]',
        r'\.card\.wc-card\.player-picks-desktop \.team-link\s*[,{]',
        r'\.card\.wc-card\.player-picks-desktop \.team-link:hover\s*[,{]',
    ]
    for pattern in forbidden:
        assert re.search(pattern, CSS) is None, (
            f'Forbidden ROSTER dark carve-out rule re-appeared in style.css: '
            f'`{pattern}`. P3 retired this in lockstep with the picks.html '
            f'template migration; a regression here means the cleanup was '
            f'undone.'
        )


# ---------------------------------------------------------------------------
# PI-6: .pick-events-* accordion substrate split.
# ---------------------------------------------------------------------------

def test_pick_events_item_base_paints_light_substrate():
    """`.pick-events-list .pick-event-item` base paints dark text + dark
    dashed border — the post-P2 light-substrate variant for the
    player_detail accordion drill-down."""
    match = re.search(
        r'(?<!\.card\.wc-card )\.pick-events-list \.pick-event-item\s*\{([^}]+)\}',
        CSS,
    )
    assert match is not None, (
        'Expected a `.pick-events-list .pick-event-item` base rule.'
    )
    block = match.group(1)
    # Property-scoped — see PR #15 CR R7-D pattern.
    assert re.search(r'(?<![-\w])color:\s*var\(--text-primary\)', block), (
        f'Accordion item base must paint `color: var(--text-primary)` on '
        f'light substrate; block={block!r}.'
    )
    assert 'border-bottom: 1px dashed var(--border)' in block, (
        f'Accordion item base must paint `border-bottom: 1px dashed '
        f'var(--border)` on light substrate; block={block!r}.'
    )


def test_pick_events_item_dark_carve_out_was_retired_in_p3():
    """`.card.wc-card .pick-events-list .pick-event-item` and the companion
    `.card.wc-card .pick-event-stage` rule were retired in P3 when picks.html
    migrated off `.card.wc-card` — the carve-outs' only DOM consumer (the
    ROSTER read-only desktop accordion) disappeared. Mirrors P2 PI-7's
    "removed in lockstep" pattern.
    """
    forbidden = [
        r'\.card\.wc-card \.pick-events-list \.pick-event-item\s*[,{]',
        r'\.card\.wc-card \.pick-event-stage\s*[,{]',
    ]
    for pattern in forbidden:
        assert re.search(pattern, CSS) is None, (
            f'Forbidden ROSTER accordion dark carve-out rule re-appeared in '
            f'style.css: `{pattern}`. P3 retired this in lockstep with the '
            f'picks.html template migration; a regression here means the '
            f'cleanup was undone.'
        )


# ---------------------------------------------------------------------------
# PI-7: BOARD-only dark-card rules removed in lockstep.
# ---------------------------------------------------------------------------

def test_board_only_dark_card_rule_families_removed():
    """None of the four BOARD-only dark-substrate rule families re-appear as
    live CSS rules. These all targeted classes (`.leaderboard-card`,
    `.leaderboard-table`) that exist only on BOARD; once leaderboard.html
    moved off `.card.wc-card`, the rules orphaned at zero consumers and
    were removed in lockstep (parallels P1's `.card.wc-card .btn-game`
    removal). Locked here so a future cleanup doesn't accidentally
    reintroduce them via a vestigial-style restore.
    """
    forbidden_rules = [
        # Mobile rank-delta lifts (live-token green/red on dark navy).
        r'\.card\.wc-card\.leaderboard-card \.rank-delta-up\s*[,{]',
        r'\.card\.wc-card\.leaderboard-card \.rank-delta-down\s*[,{]',
        # Desktop rank-delta lifts inside the leaderboard table.
        r'\.card\.wc-card \.leaderboard-table \.row-current-user > td \.rank-delta-up\s*[,{]',
        r'\.card\.wc-card \.leaderboard-table \.row-current-user > td \.rank-delta-down\s*[,{]',
        # Desktop leaderboard-table thead + row-current-user lifts.
        r'\.card\.wc-card \.leaderboard-table thead th\s*[,{]',
        r'\.card\.wc-card \.leaderboard-table \.row-current-user > td\s*[,{]',
        # Mobile leaderboard-card text overrides. Each pattern accepts `[,{]`
        # as the terminator so a future regression catches both the legacy
        # selector-list form (`.card.wc-card.leaderboard-card,\n.card.wc-
        # card.leaderboard-card a { ... }`) AND a hypothetical standalone
        # block (`.card.wc-card.leaderboard-card { ... }`).
        r'\.card\.wc-card\.leaderboard-card\s*[,{]',
        r'\.card\.wc-card\.leaderboard-card \.text-muted\s*[,{]',
    ]
    for pattern in forbidden_rules:
        assert re.search(pattern, CSS) is None, (
            f'Forbidden BOARD-only dark-card rule re-appeared in style.css: '
            f'`{pattern}`. P2 removed these in lockstep with the template '
            f'migration; a regression here means the cleanup was undone.'
        )
