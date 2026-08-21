"""S5.1.1 — _home_post.html first iteration. Layer A regression locks.

Three Priority Issues closed:

- PI-1: "Your Finish" card collapsed from two adjacent display-4 numerals
  (rank + final points 50/50 split, the hero-metric-adjacency reflex
  S2.3.1 broke on team_detail) to one dominant rank numeral plus a
  Newsreader derivation prose line carrying points + climb microcopy.

- PI-2: Champion banner gained a Tribune retrospection line ("A final
  the club will remember.") below the defeat summary so the moment reads
  as editorial record, not wire-service teletype. The defeat summary
  itself gains "in the Final" framing so the result reads as the
  championship match, not a pickup game.

- PI-3: Champion banner eyebrow renamed from "Champion" to "World Cup
  Winner" so it doesn't double the page-hero "Champion of the Pool"
  eyebrow on rank=1 viewers (two different registers — user vs
  tournament — were collapsing to the same word).
"""
from __future__ import annotations

import os
import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from extensions import db
from games.worldcup.constants import TOURNAMENT_DEADLINE_UTC
from games.worldcup.services.home_context import _context_post
from tests._worldcup_fixtures import make_match, seed_full_tournament

TEMPLATE = Path(__file__).resolve().parents[1] / 'games' / 'worldcup' / 'templates' / 'worldcup' / '_home_post.html'
STYLE_CSS = Path(__file__).resolve().parents[1] / 'static' / 'css' / 'style.css'


# ---------------------------------------------------------------------------
# PI-1 locks: Your Finish hero collapse (one dominant rank numeral)
# ---------------------------------------------------------------------------

def test_pi1_your_finish_card_drops_paired_display4_numerals():
    """The prior two-display-4 50/50 split is gone.

    Source-pattern lock: the post template must NOT carry a second
    `wc-numeral display-4` element inside a Final-Points column. If
    someone re-introduces the paired-numeral SaaS-stat-strip shape, this
    test fails before the rendered output gets re-seen by a critique.
    """
    src = TEMPLATE.read_text()
    # The historical shape carried both "Your Finish" + "Final Points"
    # captions paired with display-4 numerals in a single .row. The
    # collapse removes both the right-column eyebrow and its numeral.
    assert 'Final Points' not in src, (
        'Final Points display-4 column should be gone — points are now '
        'rendered as supporting prose in .wc-standing-derivation.'
    )
    # Only one .wc-numeral.display-4 is allowed to remain on this surface
    # (none, post-collapse — we use .wc-standing-rank now). Lock that the
    # paired structure is not re-introduced.
    paired = re.findall(r'wc-numeral\s+display-4', src)
    assert len(paired) == 0, (
        f'Expected zero .wc-numeral.display-4 (collapsed to .wc-standing-rank); '
        f'found {len(paired)}.'
    )


def test_pi1_your_finish_card_uses_wc_standing_primitive():
    """The collapsed hero uses the hub-shared .wc-standing-* class set.

    Hub coherence pass 2026-05 generalized the post-only `.post-finish-*`
    primitive into a hub-shared `.wc-standing-*` family used by both live
    ("Your Standing") and post ("Your Finish"). Lock the new names here.
    """
    src = TEMPLATE.read_text()
    assert 'wc-standing-card' in src
    assert 'wc-standing-rank-cluster' in src
    assert 'wc-standing-rank' in src
    assert 'wc-standing-of' in src
    assert 'wc-standing-derivation' in src
    # The retired post-only primitive is gone.
    assert 'post-finish-card' not in src
    assert 'post-finish-rank' not in src


def test_pi1_wc_standing_css_primitives_present():
    """CSS for the hub-shared primitive set is committed to style.css.

    Lock the scoped selectors + the dominant numeral sizing so a future
    edit can't silently regress to a small rank + big points elsewhere.
    """
    css = STYLE_CSS.read_text()
    assert '.wc-standing-card .wc-standing-rank' in css
    assert '.wc-standing-card .wc-standing-derivation' in css
    # Dominant numeral lives between 3-5rem at base; the team_detail S2.3.1
    # masthead anchors at 2.6rem, the season finale + live standing sit
    # slightly above that. Lock a floor of 3rem to prevent regression to
    # the prior display-4 (3.5rem at the bigger Bootstrap breakpoint)
    # paired pattern.
    match = re.search(
        r'\.wc-standing-card\s+\.wc-standing-rank\s*\{[^}]*font-size:\s*([\d.]+)rem',
        css,
    )
    assert match is not None, '.wc-standing-rank must declare font-size in rem'
    assert float(match.group(1)) >= 3.0, (
        f'.wc-standing-rank font-size should be >= 3rem (Tribune masthead); '
        f'found {match.group(1)}rem.'
    )


# ---------------------------------------------------------------------------
# PI-2 locks: Champion banner Tribune retrospection
# ---------------------------------------------------------------------------

def test_pi2_champion_summary_carries_final_framing(app):
    """The champion_summary string carries 'in the Final' framing.

    Service-level lock on the home_context post builder. Removing the
    suffix re-collapses the line to wire-service ('Defeated X N–N')
    register and fails the Tribune voice gate. The existing
    test_context_post_champion_summary_includes_score still locks the
    score; this test guarantees the framing language.
    """
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    teams = seed['teams']
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True, home_score=3, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing', 'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert 'in the Final' in ctx['champion_summary'], (
        f"champion_summary missing Tribune framing: {ctx['champion_summary']!r}"
    )


def test_pi2_champion_retrospect_line_in_template():
    """The retrospection line is rendered when champion_team is present.

    Markup lock: the `.champion-retrospect` element + its Tribune
    sign-off copy must live inside the `{% if champion_team %}` branch
    of the champion banner so the line never surfaces on the
    admin-error fallback (where the banner shows "Tournament Complete /
    Champion not yet declared.").
    """
    src = TEMPLATE.read_text()
    assert 'class="champion-retrospect"' in src
    assert 'A final the club will remember' in src

    # Position guard: the retrospection line must sit inside the
    # `{% if champion_team %}` branch, not the `{% else %}` fallback.
    # Walk the source structurally rather than by string distance.
    champion_branch = re.search(
        r'\{%\s*if\s+champion_team\s*%\}(.*?)\{%\s*else\s*%\}',
        src, re.DOTALL,
    )
    assert champion_branch is not None
    assert 'champion-retrospect' in champion_branch.group(1)


def test_pi2_champion_retrospect_css_present():
    """Scoped CSS for .champion-retrospect ships with the template.

    Re-scoped from `.card.wc-card.wc-hero-grad .champion-retrospect` to
    `.wc-champion-banner .champion-retrospect` in WC tab unification P5
    (the dark `.card.wc-card` substrate retired; the champion banner is
    now its own dedicated primitive).
    """
    css = STYLE_CSS.read_text()
    assert '.wc-champion-banner .champion-retrospect' in css
    # Newsreader italic is the Tribune editorial register per DESIGN.md §3.
    match = re.search(
        r'\.wc-champion-banner\s+\.champion-retrospect\s*\{([^}]+)\}',
        css,
    )
    assert match is not None
    block = match.group(1)
    assert 'var(--font-news)' in block
    assert 'italic' in block


# ---------------------------------------------------------------------------
# PI-3 locks: Champion banner eyebrow disambiguates from page-hero
# ---------------------------------------------------------------------------

def test_pi3_champion_banner_eyebrow_disambiguates_from_page_hero():
    """The banner eyebrow no longer doubles the page-hero 'Champion ...'.

    For rank=1 viewers the page-hero voice copy renders eyebrow
    'Champion of the Pool' (speaking to the viewer's standing). The
    champion banner directly below was eyebrowed 'Champion' (speaking
    to the tournament's winning country). Two literal 'Champion'
    eyebrows in 80px of vertical space read as one repeated label
    rather than two distinct registers.

    S5.1.1 first replaced 'Champion' with 'World Cup Winner' to
    separate user-register from tournament-register. S5.3 PI-3
    superseded that with 'Final Decree' for cross-cluster Tribune
    voice consistency with the platform _champion_banner.html (which
    S5.2.1 PI-3 set to 'Final Decree'). Both retired strings stay
    locked out; the new lock anchors the current 'Final Decree' state
    via the S5.3 test file's positive assertion.
    """
    src = TEMPLATE.read_text()
    # The banner eyebrow text inside the champion_team branch
    champion_branch = re.search(
        r'\{%\s*if\s+champion_team\s*%\}(.*?)\{%\s*else\s*%\}',
        src, re.DOTALL,
    )
    assert champion_branch is not None
    branch_src = champion_branch.group(1)
    # Both retired wordings stay out.
    assert (
        '<div class="wc-eyebrow mb-1">Champion</div>' not in branch_src
    ), 'Banner eyebrow still says bare "Champion" — clashes with page-hero.'
    assert (
        '<div class="wc-eyebrow mb-1">World Cup Winner</div>'
        not in branch_src
    ), (
        'Banner eyebrow still says "World Cup Winner" — superseded by S5.3 '
        'PI-3 with "Final Decree" for cross-cluster Tribune voice alignment.'
    )


def test_pi3_admin_error_fallback_eyebrow_unchanged():
    """The else branch (winner_team_id missing) keeps 'Tournament Complete'.

    Locks that the PI-3 rename only retouches the success-branch
    eyebrow and doesn't bleed into the defensive admin-error fallback,
    which already carries its own distinct phrasing.
    """
    src = TEMPLATE.read_text()
    fallback = re.search(
        r'\{%\s*else\s*%\}(.*?)\{%\s*endif\s*%\}',
        src, re.DOTALL,
    )
    assert fallback is not None
    assert (
        '<div class="wc-eyebrow mb-1">Tournament Complete</div>'
        in fallback.group(1)
    )


# ---------------------------------------------------------------------------
# Rendered-HTML smoke (a defense-in-depth net for the source-grep locks above)
# ---------------------------------------------------------------------------

def test_home_post_renders_expected_tribune_voice(app):
    """End-to-end: post-state hub home renders all three S5.1.1 lifts."""
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

    # PI-1: collapsed Your Finish hero — new primitives present, paired display-4 absent.
    assert 'wc-standing-rank' in body
    assert 'wc-standing-derivation' in body
    # No second wc-numeral display-4 (Final Points column has been removed).
    assert body.count('wc-numeral display-4') == 0
    assert 'Final Points' not in body

    # PI-2: Tribune retrospection rendered (champion_team present in this seed).
    assert 'champion-retrospect' in body
    assert 'A final the club will remember' in body
    assert 'in the Final' in body

    # PI-3: Banner eyebrow renamed. S5.1.1 set this to 'World Cup Winner';
    # S5.3 PI-3 superseded with 'Final Decree' for cross-cluster Tribune
    # voice alignment. Render-smoke now asserts the current 'Final Decree'
    # state.
    assert 'Final Decree' in body
    assert 'World Cup Winner' not in body
