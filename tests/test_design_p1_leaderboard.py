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
    """Desktop column header is "Move" (rank-delta), not "Trend" (points-delta)."""
    src = TEMPLATE.read_text()
    assert '<th scope="col" class="text-end">Move</th>' in src
    assert '<th scope="col" class="text-end">Trend</th>' not in src


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
    # State-aware eyebrow
    assert "Tonight's Ledger" in src
    assert 'Tribute Window Open' in src
    # Empty state copy — old SaaS line is gone
    assert 'No players enrolled yet' not in src
    assert 'The ledger awaits its first name.' in src


def test_move_column_muted_states_lift_off_dark_surface():
    """Even / Pending inherit `.text-muted` (#8A849B) which fades into the
    `.card.wc-card` navy. The reshape ships a scoped lift to a bone tone
    so those high-frequency states stay legible on dark surfaces. Lock it.
    """
    css = CSS.read_text()
    pattern = (
        r'\.card\.wc-card\.leaderboard-card\s+\.leaderboard-move-mobile\s+'
        r'\.rank-delta-(even|pending)'
    )
    assert re.search(pattern, css), \
        'Mobile-card Even/Pending must be lifted to bone on .card.wc-card'
    # Current-user desktop row also overrides td bg to solid navy — same lift.
    desktop_pattern = (
        r'\.card\.wc-card\s+\.leaderboard-table\s+\.row-current-user\s+>\s+'
        r'td\s+\.rank-delta-(even|pending)'
    )
    assert re.search(desktop_pattern, css), \
        'Current-user row Even/Pending must be lifted to bone on .card.wc-card'


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
