"""S5.1.2 — _home_post.html second iteration. Layer A regression locks.

Single Priority Issue (inherited from S5.1.1 §0.4 backlog):

- PI-1: Final Podium player anchors + Final Roster team anchors carry the
  44×44 mobile tap-target floor (PRODUCT.md / CLAUDE.md S0.3 lock). Pre-fix
  the bare ``text-decoration-none [fw-medium]`` anchors rendered ~15px tall
  at 375 (S5.1.1 sweep: B1G_Brad 68×15, test2 33×15). Class-scoped via a
  new ``.post-table-link`` shared by both anchors (consistent with the
  ``.picker-link`` / ``.team-link`` / ``.join-alt a`` / ``.decree-links``
  precedents — not a broadcast on ``.card.wc-card .table a`` which would
  bleed onto other WC tables that already carry classed anchors).

The CSS uses inline-flex + min-height + min-width — NOT inline-block +
``line-height: 44px``, which collapses multi-line wrap onto a 44px baseline
and breaks long display names at the 320px viewport.
"""
from __future__ import annotations

import os
import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from extensions import db
from games.worldcup.constants import TOURNAMENT_DEADLINE_UTC
from tests._worldcup_fixtures import make_match, seed_full_tournament

TEMPLATE = Path(__file__).resolve().parents[1] / 'games' / 'worldcup' / 'templates' / 'worldcup' / '_home_post.html'
STYLE_CSS = Path(__file__).resolve().parents[1] / 'static' / 'css' / 'style.css'


# ---------------------------------------------------------------------------
# PI-1 locks: tap-target floor on Podium + Roster anchors
# ---------------------------------------------------------------------------

def test_pi1_podium_anchor_carries_post_table_link_class():
    """The Final Podium player anchor wears the .post-table-link class.

    Source-pattern lock so the class can't be silently stripped — losing
    the class drops the anchor back to ~15px tall and re-opens the S0.3
    tap-target floor regression.
    """
    src = TEMPLATE.read_text()
    # The podium anchor is the only `player_detail` link inside this
    # template; locking on the url_for + class pair pins the right anchor.
    match = re.search(
        r'<a\s+href="\{\{\s*url_for\(\'worldcup\.player_detail\'[^"]*\}\}"\s+class="([^"]+)"',
        src,
    )
    assert match is not None, 'Final Podium player anchor not found.'
    classes = match.group(1).split()
    assert 'post-table-link' in classes, (
        f'Podium player anchor missing .post-table-link tap-floor class; '
        f'classes={classes!r}.'
    )


def test_pi1_roster_anchor_carries_post_table_link_class():
    """The Final Roster team anchor wears the .post-table-link class.

    Same source-pattern lock as the podium test — pins the team_detail
    anchor specifically (the only one in this template).
    """
    src = TEMPLATE.read_text()
    match = re.search(
        r'<a\s+href="\{\{\s*url_for\(\'worldcup\.team_detail\'[^"]*\}\}"\s+class="([^"]+)"',
        src,
    )
    assert match is not None, 'Final Roster team anchor not found.'
    classes = match.group(1).split()
    assert 'post-table-link' in classes, (
        f'Roster team anchor missing .post-table-link tap-floor class; '
        f'classes={classes!r}.'
    )


def test_pi1_post_table_link_css_carries_44px_floor():
    """The .post-table-link CSS rule declares the 44×44 tap-target floor.

    Locks both axes — height AND width — because S5.1.1's sweep surfaced
    short display names (test2 33×15, Test1 36×15) that fail the width
    floor even when min-height alone lifts them off 15.
    """
    css = STYLE_CSS.read_text()
    match = re.search(r'\.post-table-link\s*\{([^}]+)\}', css)
    assert match is not None, '.post-table-link rule missing from style.css.'
    block = match.group(1)
    assert 'min-height: 44px' in block, (
        f'Missing min-height: 44px on .post-table-link; block={block!r}.'
    )
    assert 'min-width: 44px' in block, (
        f'Missing min-width: 44px on .post-table-link; block={block!r}.'
    )


def test_pi1_post_table_link_uses_inline_flex_not_inline_block():
    """The .post-table-link CSS uses inline-flex + align-items: center.

    Locks against the inline-block + line-height: 44px alternative that
    the §0.4 routed entry called out as a candidate but discarded —
    that pattern collapses multi-line wrap onto a single 44px baseline
    and breaks long display names ("United States" wrapping into two
    lines on a 320px viewport).
    """
    css = STYLE_CSS.read_text()
    match = re.search(r'\.post-table-link\s*\{([^}]+)\}', css)
    assert match is not None
    block = match.group(1)
    assert 'display: inline-flex' in block, (
        '.post-table-link must use inline-flex (matches .picker-link / '
        '.team-link precedent; preserves multi-line wrap).'
    )
    assert 'align-items: center' in block


def test_pi1_no_broadcast_table_anchor_rule():
    """Lock that the fix is class-scoped, not broadcast.

    The §0.4 routed entry offered ``.card.wc-card .table a { ... }`` as one
    candidate fix shape. That selector bleeds onto every WC table (leaderboard,
    schedule, player_detail, picks, team_detail) — all of which already carry
    classed anchors (.picker-link, .team-link) that own their tap-floor
    decisions. The S5.1.2 implementation deliberately did NOT take that path.
    Locking the absence so a future "tidy this up" pass can't promote
    .post-table-link to .card.wc-card .table a and double-target.
    """
    css = STYLE_CSS.read_text()
    # No rule that lifts the 44 floor on the broad selector. Matches any
    # whitespace-tolerant variant of the broadcast pattern.
    broadcast = re.search(
        r'\.card\.wc-card\s+\.table\s+a\s*\{[^}]*min-(height|width):\s*44',
        css,
    )
    assert broadcast is None, (
        'Found broadcast .card.wc-card .table a tap-floor rule — fix should '
        'stay class-scoped via .post-table-link.'
    )


# ---------------------------------------------------------------------------
# Rendered-HTML defense-in-depth: end-to-end post-state render carries class
# ---------------------------------------------------------------------------

def test_post_state_render_emits_post_table_link_on_both_anchor_types(app):
    """End-to-end: the post-state hub home renders .post-table-link on
    both the podium player anchors and the roster team anchors.

    Catches a future refactor that moves the anchors into a partial without
    threading the class through.
    """
    seed = seed_full_tournament(num_enrollments=3)
    user = seed['users'][0]
    teams = seed['teams']
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True, home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = user.get_id()
        sess['_fresh'] = True
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing', 'WC_FAKE_NOW': fake_post}):
        resp = client.get('/worldcup/')
    assert resp.status_code == 200
    body = resp.data.decode('utf-8')
    # Both anchor types carry the class. Lower bound: at least one of each.
    podium_hits = re.findall(
        r'<a[^>]*href="[^"]*/worldcup/leaderboard/\d+"[^>]*class="[^"]*post-table-link',
        body,
    )
    roster_hits = re.findall(
        r'<a[^>]*href="[^"]*/worldcup/team/\d+"[^>]*class="[^"]*post-table-link',
        body,
    )
    assert len(podium_hits) >= 1, (
        f'Expected at least one podium anchor with .post-table-link; '
        f'found {len(podium_hits)}.'
    )
    assert len(roster_hits) >= 1, (
        f'Expected at least one roster anchor with .post-table-link; '
        f'found {len(roster_hits)}.'
    )
