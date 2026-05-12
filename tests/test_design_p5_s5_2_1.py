"""S5.2.1 — Post-state component partials, first iteration. Layer A locks.

Three Priority Issues, each backed by a source-pattern regression test:

- PI-1: ``$impeccable harden`` — gradient text retired on
  ``.home-shell .champion-name``. The metal-gold gradient on text triggered
  the impeccable absolute ban (``background-clip: text`` + gradient bg) and
  DESIGN.md §6 Don't list ("The metal-gold gradient is for surfaces, never
  for type"). Replaced with solid ``var(--gold-light)``, mirroring the
  ``.home-metal-text`` precedent at style.css:461.

- PI-2: ``$impeccable clarify`` — ``_commish_note.html`` body branches on
  ``state`` (pre / live / post). The pre-state body ("Tribute window opens
  until June 11") was rendering in live and post too, leaving the Commish
  anticipating a deadline weeks after the trophy was lifted. The post body
  reads retrospective Tribune voice; live reads tournament-in-motion. The
  byline ("The Commish") stays in every branch.

- PI-3: ``$impeccable clarify`` — champion eyebrow text rewrite.
  ``◈ 2026 FIFA World Cup Champions ◈`` restated both the H1 above
  ("The 2026 World Cup") and the gold champion name immediately below. Per
  PRODUCT.md Copy Discipline ("Every word earns its place; no restated
  headings") replaced with ``◈ Final Decree ◈`` — Council voice that
  mirrors the pre-state ``By Decree of the Commish No 001`` decree stamp.

Three cross-phase gradient-text rules remain at style.css:2208 (.recap-rank
in S5.1 surface), :6644 (.card.wc-card.wc-hero-grad .champion-name), and
:6928 (.row-champion-pick .best-finish-champion). Routed to S6.1 per §0.4
backlog as a bundled cross-phase gradient-text retirement pass.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import create_app
from extensions import db
from flask import render_template


REPO_ROOT = Path(__file__).resolve().parents[1]
CHAMPION_BANNER = REPO_ROOT / 'core' / 'main' / 'templates' / 'main' / '_champion_banner.html'
COMMISH_NOTE = REPO_ROOT / 'core' / 'main' / 'templates' / 'main' / '_commish_note.html'
STYLE_CSS = REPO_ROOT / 'static' / 'css' / 'style.css'


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


# ---------------------------------------------------------------------------
# PI-1 locks: gradient text retired on .home-shell .champion-name
# ---------------------------------------------------------------------------

def test_pi1_champion_name_uses_solid_gold_light_not_gradient():
    """``.home-shell .champion-name`` carries solid ``color: var(--gold-light)``.

    Locks the absence of ``background-clip: text`` + gradient inside the
    rule block. A future "let's make it pop again" pass that reintroduces
    the metal-gold gradient on this selector fails here.
    """
    css = STYLE_CSS.read_text()
    match = re.search(
        r'\.home-shell\s+\.champion-name\s*\{([^}]+)\}',
        css,
    )
    assert match is not None, (
        '.home-shell .champion-name rule missing from style.css.'
    )
    block = match.group(1)
    assert 'color: var(--gold-light)' in block, (
        f'Expected solid color: var(--gold-light); block={block!r}.'
    )
    assert 'background-clip' not in block, (
        f'Gradient text retired — background-clip must not appear; '
        f'block={block!r}.'
    )
    assert 'background:' not in block, (
        f'No background declaration on the rule; block={block!r}.'
    )


def test_pi1_champion_name_keeps_teko_700_responsive_scale():
    """The PI-1 fix is color-only — Teko 700 + responsive size scale persist.

    Guards against an over-zealous follow-up trimming the size + family
    along with the gradient retirement.
    """
    css = STYLE_CSS.read_text()
    match = re.search(
        r'\.home-shell\s+\.champion-name\s*\{([^}]+)\}',
        css,
    )
    assert match is not None
    block = match.group(1)
    assert 'font-family: var(--font-teko)' in block
    assert 'font-weight: 700' in block
    assert 'font-size: 2.8rem' in block
    assert 'letter-spacing: 0.06em' in block
    assert 'text-transform: uppercase' in block

    # Desktop responsive bump still lands at 4rem.
    desktop = re.search(
        r'@media\s*\(min-width:\s*768px\)\s*\{\s*'
        r'\.home-shell\s+\.champion-name\s*\{\s*font-size:\s*4rem;\s*\}',
        css,
    )
    assert desktop is not None, (
        '.home-shell .champion-name 4rem desktop bump missing.'
    )


# ---------------------------------------------------------------------------
# PI-2 locks: _commish_note.html branches on state
# ---------------------------------------------------------------------------

def test_pi2_commish_note_branches_on_state():
    """The partial Jinja-branches on ``state == 'live'`` / ``'post'``.

    Locks the architectural choice of a single file with a state branch
    inside, rather than three separate per-state files. The byline stays
    outside the branch.
    """
    src = COMMISH_NOTE.read_text()
    assert "state == 'live'" in src, (
        'Live-state branch missing from _commish_note.html.'
    )
    assert "state == 'post'" in src, (
        'Post-state branch missing from _commish_note.html.'
    )
    # Byline is outside the branch (one occurrence, after the {% endif %}).
    byline_count = src.count('class="commish-note-byline"')
    assert byline_count == 1, (
        f'Byline must render once across all three states; '
        f'found {byline_count} occurrences (likely duplicated into branches).'
    )


def test_pi2_pre_state_keeps_tribute_window_copy(app):
    """Pre-state body still carries the canonical tribute-window prose.

    The PI fixed live/post bleed-through — it did NOT rewrite the pre body.
    Locking against a future pass that "tidies" the pre branch into
    something less specific.
    """
    out = render_template('main/_commish_note.html',
                          state='pre',
                          champion_team=None)
    assert 'Tribute window' in out
    assert 'Welcome to the Club' in out


def test_pi2_live_state_speaks_tournament_in_motion(app):
    """Live-state body never says "Tribute window" (pre-state copy)."""
    out = render_template('main/_commish_note.html',
                          state='live',
                          champion_team=None)
    assert 'Tribute window' not in out, (
        'Live state must not leak pre-state tribute-window copy.'
    )
    # Some token that anchors live voice — keep loose so the prose can be
    # tuned without breaking the test.
    assert 'tournament' in out.lower() or 'Picks are sealed' in out


def test_pi2_post_state_speaks_retrospectively(app):
    """Post-state body says "ledger is closed" and never anticipates."""
    out = render_template('main/_commish_note.html',
                          state='post',
                          champion_team=None)
    assert 'Tribute window' not in out, (
        'Post state must not leak pre-state tribute-window copy.'
    )
    assert 'ledger is closed' in out, (
        'Post-state Tribune voice should mark the ledger as closed.'
    )


def test_pi2_post_state_interpolates_champion_when_available(app):
    """When ``champion_team`` is supplied, the post body names them."""
    class StubTeam:
        display_name = 'United States'

    out = render_template('main/_commish_note.html',
                          state='post',
                          champion_team=StubTeam())
    assert 'United States' in out
    assert 'lifted the trophy' in out


def test_pi2_post_state_falls_back_when_champion_missing(app):
    """If ``champion_team`` is None the post body still reads cleanly."""
    out = render_template('main/_commish_note.html',
                          state='post',
                          champion_team=None)
    assert 'United States' not in out  # no stale leftover from prior render
    assert 'lifted' in out  # fallback prose still acknowledges the result
    # Make sure we didn't print the literal Jinja variable.
    assert 'champion_team' not in out


def test_pi2_byline_renders_in_every_state(app):
    """``The Commish`` byline persists across pre / live / post."""
    for state in ('pre', 'live', 'post'):
        out = render_template('main/_commish_note.html',
                              state=state,
                              champion_team=None)
        assert 'class="commish-note-byline"' in out, (
            f'Byline missing in state={state!r}.'
        )
        assert 'The Commish' in out


# ---------------------------------------------------------------------------
# PI-3 locks: champion eyebrow Tribune voice (no restatement)
# ---------------------------------------------------------------------------

def test_pi3_champion_eyebrow_does_not_restate_h1_or_name():
    """The eyebrow no longer says ``2026 FIFA World Cup Champions``.

    The H1 above the banner already says "The 2026 World Cup" and the gold
    name below already states the champion. The eyebrow must add a register
    label, not restate either of those facts.
    """
    src = CHAMPION_BANNER.read_text()
    # Pull the literal eyebrow text node.
    match = re.search(
        r'<div class="champion-eyebrow">([^<]+)</div>',
        src,
    )
    assert match is not None, 'champion-eyebrow div missing.'
    text = match.group(1).strip()
    assert '2026' not in text, (
        f'Eyebrow restates the H1 year token "2026"; text={text!r}.'
    )
    assert 'World Cup' not in text, (
        f'Eyebrow restates the H1 "World Cup"; text={text!r}.'
    )
    assert 'Champions' not in text, (
        f'Eyebrow restates the gold name role; text={text!r}.'
    )


def test_pi3_champion_eyebrow_carries_final_decree_voice():
    """The replacement eyebrow lands the Council-voice ``Final Decree`` line.

    Mirrors the pre-state ``By Decree of the Commish No 001`` decree-stamp
    precedent so post and pre register read as the same Council closing /
    opening a ledger.
    """
    src = CHAMPION_BANNER.read_text()
    match = re.search(
        r'<div class="champion-eyebrow">([^<]+)</div>',
        src,
    )
    assert match is not None
    text = match.group(1).strip()
    assert 'Final Decree' in text, (
        f'Expected the Council-voice "Final Decree" line; text={text!r}.'
    )
