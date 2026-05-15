"""P1 S1.1 — lock the leaderboard reshape.

Source-pattern locks for the Tribune sidebar Your Position block, the Move
column rendering rank-delta (not points-delta), and the voice copy for the
hero/empty states. Pairs with tests/test_worldcup_leaderboard.py which
exercises the rendered HTML through the Flask test client.
"""
import re
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
TEMPLATE = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'leaderboard.html'
CSS = REPO_ROOT / 'static' / 'css' / 'style.css'


def test_your_standing_tribune_replaces_hero_metric_block():
    """The old hero-metric SaaS block (rank + points side by side) is gone;
    the Tribune sidebar shape is in place. No inline side-stripe styles."""
    src = TEMPLATE.read_text()
    assert 'your-standing-tribune' in src, \
        'Your Position must use the .your-standing-tribune class'
    # Old hero-metric class names from the prior shape must be absent.
    assert 'your-standing-rank-numeral' not in src
    assert 'your-standing-points-numeral' not in src
    assert 'your-standing-points-label' not in src
    # No template-inline side-stripe styles (P0 S0.2 absolute ban).
    assert 'border-left' not in src.lower()


def test_your_standing_tribune_caption_uses_newsreader():
    """Newsroom Rule: paragraph caption renders in Newsreader, not Teko."""
    css = CSS.read_text()
    rule = re.search(r'\.your-standing-tribune-caption\s*\{([^}]+)\}', css)
    assert rule, '.your-standing-tribune-caption rule must exist'
    body = rule.group(1)
    assert 'Newsreader' in body, \
        'Caption font-family must be Newsreader (DESIGN.md Newsroom Rule)'
    assert 'Teko' not in body, \
        'Caption must not regress to Teko display type'


def test_your_standing_tribune_eyebrow_is_gold():
    """Eyebrow Rule: contextual label is the gold token, not the WC red accent."""
    css = CSS.read_text()
    rule = re.search(
        r'\.your-standing-tribune\s+\.wc-eyebrow\s*\{([^}]+)\}', css
    )
    assert rule, 'Tribune eyebrow rule must exist'
    body = rule.group(1)
    assert 'var(--gold)' in body, \
        'Eyebrow color must be the brand gold token'


def test_your_standing_tribune_uses_brand_shadow_at_rest():
    """Lift-At-Rest Rule: card carries --shadow-sm at rest, never gray."""
    css = CSS.read_text()
    rule = re.search(r'\.your-standing-tribune\s*\{([^}]+)\}', css)
    assert rule, '.your-standing-tribune rule must exist'
    body = rule.group(1)
    assert 'var(--shadow-sm)' in body or 'var(--shadow-md)' in body, \
        'Tribune card must reference a brand-tinted shadow token'
    assert 'rgba(0, 0, 0' not in body and 'rgba(0,0,0' not in body, \
        'No neutral-gray shadow on the Tribune card'


def test_your_standing_tribune_renders_only_the_rank_numeral():
    """The reshape collapses two big numbers into one. The .total points
    numeral from the old block must not be referenced in the template."""
    src = TEMPLATE.read_text()
    assert 'your_standing.total' not in src, \
        'Tribune sidebar must not surface a second hero numeral (Points)'


def test_move_column_replaces_trend_column_header():
    """Desktop column header is "Move" (rank-delta), not "Trend" (points-delta).

    Match attributes loosely so the S6.1.3 PI-1 `title=` tooltip on the
    header (analyst progressive disclosure) doesn't break this lock —
    the contract here is "Move header exists, Trend header doesn't",
    not the literal attribute set.
    """
    src = TEMPLATE.read_text()
    assert re.search(r'<th[^>]*>Move</th>', src) is not None
    assert re.search(r'<th[^>]*>Trend</th>', src) is None


def test_move_column_uses_rank_delta_classes():
    """The new column uses rank-delta-{up,down,even,pending}, not the prior
    leaderboard-trend-{up,down}."""
    src = TEMPLATE.read_text()
    assert 'rank-delta-up' in src
    assert 'rank-delta-down' in src
    assert 'rank-delta-even' in src
    assert 'rank-delta-pending' in src
    assert 'leaderboard-trend-up' not in src
    assert 'leaderboard-trend-down' not in src


def test_rank_delta_styles_use_brand_state_tokens():
    """Up = success green, down = danger red. Both brand-tinted, neither raw hex."""
    css = CSS.read_text()
    up = re.search(r'\.rank-delta-up\s*\{([^}]+)\}', css)
    down = re.search(r'\.rank-delta-down\s*\{([^}]+)\}', css)
    assert up and 'var(--success)' in up.group(1), \
        '.rank-delta-up must use the success token'
    assert down and 'var(--danger)' in down.group(1), \
        '.rank-delta-down must use the danger token'


def test_voice_microcopy_replaces_legacy_strings():
    """Title, h1, eyebrow, empty state were rewritten in the editorial voice."""
    src = TEMPLATE.read_text()
    # Title + h1
    assert '<h1 class="mb-1">The Standings</h1>' in src
    assert 'The Standings · 2026 World Cup Pool' in src
    # State-aware eyebrow. Hub coherence pass (2026-05): pre-deadline copy
    # rewrote from the archaic "Tribute Window Open" to plain-spoken
    # "Picks Open" so the Casual-default reader doesn't pay a metaphor-
    # unpack cost above the fold; the Tribune voice still lives in H1
    # and the CTA register. Cross-tab parity: voice.HUB_COPY['pre'] and
    # voice.HUB_COPY['out']['unenrolled_pre'] mirror this string.
    assert "Tonight's Ledger" in src
    assert 'Picks Open' in src
    # Empty state copy — old SaaS line is gone
    assert 'No players enrolled yet' not in src
    assert 'The ledger awaits its first name.' in src


def test_move_column_muted_states_inherit_bootstrap_text_muted_redirect():
    """WC Tab Unification P2 retired the dark-substrate `.card.wc-card`-scoped
    bone lifts on Move-column Even/Pending — leaderboard.html migrated off
    `.card.wc-card` so the prior consumers are gone. Those states now inherit
    Bootstrap's `.text-muted` directly on the new light substrate, which the
    `:root { --bs-secondary-color: var(--text-secondary) }` redirect at
    style.css :7183 lifts from sub-AA gray to a ~6.9:1 token (S6.1.1 PI-2).

    Lock both halves of the new contract:
    (1) the pre-P2 dark lifts cannot return,
    (2) the Bootstrap-token redirect that paints the legible fallback survives.

    Companion: `tests/test_design_wc_tab_unification_p2.py::
    test_board_only_dark_card_rule_families_removed` is the forward-locking
    counterpart enforcing (1) across the broader BOARD rule family.
    """
    css = CSS.read_text()
    # (1) Pre-P2 dark lifts must not return.
    mobile_pattern = (
        r'\.card\.wc-card\.leaderboard-card\s+\.leaderboard-move-mobile\s+'
        r'\.rank-delta-(even|pending)'
    )
    assert not re.search(mobile_pattern, css), (
        'Pre-P2 mobile dark-lift on `.rank-delta-(even|pending)` must not '
        're-appear — the consumer (`.leaderboard-card` on `.card.wc-card`) '
        'is gone after P2.'
    )
    desktop_pattern = (
        r'\.card\.wc-card\s+\.leaderboard-table\s+\.row-current-user\s+>\s+'
        r'td\s+\.rank-delta-(even|pending)'
    )
    assert not re.search(desktop_pattern, css), (
        'Pre-P2 desktop dark-lift on `.rank-delta-(even|pending)` must not '
        're-appear — `.leaderboard-table` inside `.card.wc-card` no longer '
        'exists after P2.'
    )
    # (2) The Bootstrap `.text-muted` token redirect that paints the new
    # legible fallback must survive.
    assert re.search(
        r'--bs-secondary-color:\s*var\(--text-secondary\)',
        css,
    ), (
        'Bootstrap `.text-muted` must redirect to `var(--text-secondary)` '
        'via the `:root` override at style.css :7183 (S6.1.1 PI-2) — this is '
        'the AA-clearing fallback that the old dark-card-scoped lifts made '
        'redundant.'
    )


def test_mobile_placeholder_no_longer_uses_em_dash_glyph():
    """The prior `<small class="text-muted">—</small>` mobile placeholder is gone.

    Em-dashes in user-visible copy are policed in aggregate by
    tests/test_design_p0_copy_discipline.py::test_no_em_dash_in_user_facing_template_copy
    (which strips comments first). This narrower lock guards against the
    specific placeholder pattern from regressing back into the trend cell.
    """
    src = TEMPLATE.read_text()
    assert '<span class="text-muted">—</span>' not in src
    assert 'Trend: even' not in src  # the legacy mobile literal
