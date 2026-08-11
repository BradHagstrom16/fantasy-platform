"""Regression locks for the home pre-state polish pass (branch `home/pre-state-polish-r1`).

Surface: `/` rendered for a logged-in pre-deadline user. The pass made six
content/layout changes that need locking against future drift:

  P0 #2: countdown card lost its hardcoded "Review & Edit My Roster" CTA
         block + the "Days to the Whistle" subtitle + the "ticking" trail.
  P0 #3: fixture cards lost the misleading "◯ PICK DUE" status badge.
         (S6.1.5 PI-5 — the fixture cards themselves were later retired in
         favor of the editorial fixture ladder in `_home_pre.html`.)
  P0 #5: pre-state Commish note replaced with user-supplied verbatim copy
         (first-person voice). S6.1.5 — Americanized "favours" → "favors"
         per user request; the rest of the verbatim copy stays locked.
  P0 #6: dossier CTA labels reworded to functional voice:
         - Unenrolled  → "Join the World Cup Pool"
         - Enrolled, no picks → "Make Your Picks"
         - Enrolled with picks → "Review & Edit My Roster"
  P1 #7: `.home-shell` min-height resolves through `--ccc-nav-h` and
         `--ccc-footer-h` custom properties (not hardcoded 56px/200px).
  P1 #8: countdown derivation upgraded from `<p>` to `<div role="timer"
         aria-live="off">`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from models.content import COMMISH_NOTE_DEFAULTS
from models.user import User

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'lounge'
STYLE_CSS = REPO_ROOT / 'static' / 'css' / 'style.css'
TOKENS_CSS = REPO_ROOT / 'static' / 'css' / 'tokens.css'

COUNTDOWN = (TEMPLATES / '_countdown_card.html').read_text()
# The "From the Commish" note copy moved from this template's Jinja branches
# to the admin-editable COMMISH_NOTE_DEFAULTS fallback (models/content.py).
# The standalone join/seal CTA partials were consolidated into the decree
# (the decree now carries the single state-aware CTA), so those files no
# longer exist; their label locks moved onto COUNTDOWN below.
BALLOT = (TEMPLATES / '_ballot_card.html').read_text()
# S6.1.5 PI-5 — `_fixture_card.html` retired; rail now renders the editorial
# fixture ladder inline in `_home_pre.html`. The two fixture-card-specific
# locks below have been migrated to the new surface.
HOME_PRE = (TEMPLATES / '_home_pre.html').read_text()
BASE_HTML = (REPO_ROOT / 'templates' / 'base.html').read_text()


# ---------------------------------------------------------------------------
# App fixture for HTTP-level assertions (the unenrolled-home rendering test).
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _login_as_unenrolled(app, client, username='newcomer'):
    """Register + log in a user with no WorldCupEnrollment row.

    Returns the user's id. The home route sees this user as logged-in,
    pre-deadline, no enrollment — the exact state the polish pass targets.
    """
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com')
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        uid = u.id
        auth_id = u.auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    return uid


# ---------------------------------------------------------------------------
# P0 #2 — countdown card no longer carries its CTA / subtitle / "ticking"
# ---------------------------------------------------------------------------

def test_decree_carries_the_single_state_aware_cta():
    """Consolidation (supersedes P0 #2): the decree is now the SINGLE
    pre-state CTA surface. It carries one `.decree-cta` whose destination
    branches on enrollment state, and the standalone join/seal dossier
    cards are gone — so there is exactly one CTA, in the decree, never two
    stacked. The original P0 #2 intent ("one CTA, no duplicates") is
    preserved; only its location moved from the dossier slot into the box."""
    assert 'decree-cta' in COUNTDOWN, (
        'The decree lost its embedded `.decree-cta`. The decree is the '
        'single pre-state action surface now (the separate join/seal cards '
        'were retired); without it the box has no call to action.'
    )
    # State-aware destinations, all three branches present.
    for endpoint in ("worldcup.join", "worldcup.picks", "worldcup.index"):
        assert endpoint in COUNTDOWN, (
            f"decree CTA must route to {endpoint} for its state branch."
        )
    # No stacked second CTA: the standalone dossier cards must not be
    # re-introduced above the decree.
    assert '_join_cta_card.html' not in HOME_PRE, (
        'The join CTA card is back above the decree. The CTA was '
        'consolidated into the decree; two stacked CTAs is the regression '
        'this lock guards against.'
    )
    assert '_submit_picks_cta.html' not in HOME_PRE, (
        'The seal CTA card is back above the decree. The CTA was '
        'consolidated into the decree.'
    )
    # The hardcoded ballot-edit phrase still must not leak into the decree
    # (the ballot card owns "Review & Edit My Roster", not the countdown).
    assert 'Review &amp; Edit My Roster' not in COUNTDOWN, (
        'The "Review & Edit My Roster" phrase belongs to the ballot card, '
        'not the decree. The sealed-state decree CTA is "Enter the World Cup".'
    )


def test_countdown_card_drops_days_to_the_whistle_subtitle():
    """The big-numeral unit label was retitled from "Days to the Whistle"
    to "Days" (cuter is not clearer). The class `.decree-hero-unit` is
    preserved so the eyebrow CSS rule still applies."""
    assert 'Days to the Whistle' not in COUNTDOWN, (
        'Subtitle re-introduced. The P0 polish pass tightened it to "Days".'
    )
    assert 'decree-hero-unit' in COUNTDOWN, (
        'The .decree-hero-unit class is the eyebrow register the design '
        'system applies — removing it breaks the gold-light styling.'
    )


def test_countdown_card_drops_ticking_trail():
    """The "ticking" word trailing the H · M · S derivation was redundant
    with the seconds tick visible right next to it."""
    assert 'decree-tick-trail' not in COUNTDOWN, (
        'The ticking-trail span is back. The polish pass removed it; the '
        'orphan CSS rule was deleted at the same time.'
    )
    # Strip Jinja `{# ... #}` comments before scanning so a code comment
    # documenting the JS file (which legitimately mentions "ticking") does
    # not mask the user-facing-markup assertion.
    visible = re.sub(r'\{#.*?#\}', '', COUNTDOWN, flags=re.DOTALL)
    assert 'ticking' not in visible, (
        'The word "ticking" reappeared in the user-visible countdown markup.'
    )


# ---------------------------------------------------------------------------
# P1 #8 — countdown derivation has correct timer semantics
# ---------------------------------------------------------------------------

def test_countdown_derivation_is_timer_role_with_silenced_live_region():
    """The HH · MM · SS derivation is a live numeric clock, not a paragraph.
    `role="timer"` carries the right semantic; `aria-live="off"` keeps
    screen readers from announcing every per-second tick."""
    assert 'role="timer"' in COUNTDOWN, (
        'P1 #8: decree-derivation should be `role="timer"` for the right SR '
        'semantic. A `<p>` reads as prose, not a clock.'
    )
    assert 'aria-live="off"' in COUNTDOWN, (
        'P1 #8: aria-live must be "off" so SRs do not announce the '
        'per-second tick (1Hz announcements would be noise).'
    )
    # S6.1.5 PI-1 — aria-label tightened from "Time remaining until World Cup
    # tribute window closes" to "Time remaining until kickoff" so the
    # announcement matches the new sealed-user copy register ("The Council
    # Convenes In" / "Kickoff In"). The intent — describe what the timer
    # counts down TO, not the visible unit symbols — is preserved.
    assert (
        'aria-label="Time remaining until kickoff"' in COUNTDOWN
    ), (
        'P1 #8: aria-label should describe what the timer counts down TO, '
        'not restate the visible unit symbols.'
    )


# ---------------------------------------------------------------------------
# P0 #3 — fixture cards no longer carry the misleading PICK DUE badge
# ---------------------------------------------------------------------------

def test_fixture_ladder_has_no_pick_due_badge():
    """S6.1.5 PI-5 — migrated from `_fixture_card.html` to the inline
    fixture ladder. The `◯ PICK DUE` badge was misleading then and would
    still be misleading now — there is one global tournament deadline,
    not a per-match deadline.

    PR #30 CR — the check is scoped to the `<ol class="fixture-ladder">`
    block so a future "PICK DUE" string elsewhere in `_home_pre.html`
    (e.g., a hypothetical pick-CTA section) doesn't false-positive the
    lock. The invariant is "no per-match PICK DUE badge in the FIXTURE
    LADDER", not "no PICK DUE anywhere in the file."
    """
    m = re.search(
        r'<ol\s+class="fixture-ladder"[^>]*>.*?</ol>',
        HOME_PRE,
        re.DOTALL,
    )
    assert m, (
        'fixture ladder block not found in `_home_pre.html`; the rail '
        'should still render `<ol class="fixture-ladder">...</ol>`.'
    )
    fixture_ladder_html = m.group(0)
    assert 'PICK DUE' not in fixture_ladder_html, (
        'PICK DUE badge is back in the fixture ladder. Picks are due once, '
        'at the tournament deadline, not per match.'
    )


def test_fixture_ladder_kickoff_uses_ct_filter_not_utc_strftime():
    """S6.1.5 PI-5 — migrated from `_fixture_card.html` to the inline
    fixture ladder. Kickoff times still render in Central Time via the
    `|ct` filter, not raw UTC.

    PR #30 CR — both the negative (no raw-UTC strftime) and positive
    (uses `|ct`) checks are scoped to the fixture-ladder block extracted
    from HOME_PRE. The global form would mask a regression in either
    direction: a `%H:%M UTC` string could appear in some other section
    while the ladder stays clean, or `|ct` could survive elsewhere while
    the ladder itself reverted. The invariant is "the LADDER renders
    kickoff via `|ct`, not raw UTC."
    """
    m = re.search(
        r'<ol\s+class="fixture-ladder"[^>]*>.*?</ol>',
        HOME_PRE,
        re.DOTALL,
    )
    assert m, (
        'fixture ladder block not found in `_home_pre.html`; the rail '
        'should still render `<ol class="fixture-ladder">...</ol>`.'
    )
    fixture_ladder_html = m.group(0)
    # PR #30 CR — split per Ruff PT018: bundled `A and B` asserts yield
    # imprecise failure messages. Two separate asserts make the regressing
    # form (quoted strftime literal vs raw format string) explicit.
    assert "'%H:%M UTC'" not in fixture_ladder_html, (
        "Fixture ladder reverted to a quoted UTC strftime literal "
        "(`'%H:%M UTC'`). Use the `|ct` Jinja filter (registered in "
        "app.py); the helper lives at utils/time.py."
    )
    assert "%H:%M UTC" not in fixture_ladder_html, (
        "Fixture ladder reverted to a raw UTC strftime format "
        "(`%H:%M UTC`). Use the `|ct` Jinja filter (registered in "
        "app.py); the helper lives at utils/time.py."
    )
    assert re.search(r'\|ct\b', fixture_ladder_html), (
        'Fixture ladder no longer pipes kickoff through the `ct` filter. '
        'The platform display TZ is America/Chicago — see utils/time.py.'
    )


# ---------------------------------------------------------------------------
# P0 #5 — Commish note pre-state copy is user-supplied verbatim
# ---------------------------------------------------------------------------

def test_commish_note_pre_state_copy_verbatim():
    """The pre-state default is still the first-person voice
    (`I hope you enjoy the site`) supplied by the platform owner, distinct
    from the elevated Commish tone in the live + post defaults.

    The copy moved from a `_commish_note.html` Jinja branch to the
    admin-editable `COMMISH_NOTE_DEFAULTS['pre']` fallback (models/content.py);
    the verbatim anchor is locked there now.

    S6.1.5 — "favours" → "favors" per the user's explicit US-spelling
    request. The rest of the verbatim copy stays locked; only this token
    crossed the Atlantic."""
    pre = re.sub(r'\s+', ' ', COMMISH_NOTE_DEFAULTS['pre'])
    expected_phrases = [
        'Welcome to the Club, I hope you enjoy the site.',
        'Pass along any feedback that you have.',
        'World Cup tribute window is open until June 11th.',
        'Pick your nine nations wisely, take your seat, and watch the action unfold.',
        'Fortune favors the bold.',
    ]
    for phrase in expected_phrases:
        assert phrase in pre, (
            f'Pre-state Commish default is missing: {phrase!r}. The verbatim '
            f'copy is owner-supplied; do not paraphrase or "polish".'
        )
    # Hard lock on the US spelling — the prior UK form was retired in
    # S6.1.5 per explicit user request.
    assert 'favours' not in COMMISH_NOTE_DEFAULTS['pre'], (
        '"favours" is back. The S6.1.5 critique pass Americanized the '
        'pre-state Commish copy to "favors" per user request.'
    )


def test_commish_note_post_branch_unchanged_by_pre_state_edit():
    """Sanity check: the live + post defaults retain the elevated Commish
    voice. The polish pass only touched the pre-state copy."""
    assert "The 2026 ledger is closed." in COMMISH_NOTE_DEFAULTS['post']
    assert "Picks are sealed." in COMMISH_NOTE_DEFAULTS['live']


# ---------------------------------------------------------------------------
# P0 #6 — dossier CTA labels match the user's functional spec
# ---------------------------------------------------------------------------

def test_decree_join_branch_label():
    assert 'Join the World Cup pool' in COUNTDOWN, (
        'The unenrolled decree CTA label should read "Join the World Cup pool".'
    )


def test_decree_picks_branch_label():
    assert 'Make your picks' in COUNTDOWN, (
        'The enrolled-no-picks decree CTA label should read "Make your picks".'
    )
    assert 'Seal the Oath' not in COUNTDOWN, (
        'Old Commish-voice button label is back. The decree CTA is functional '
        '(verb + object), not ceremonial.'
    )


def test_decree_sealed_branch_label():
    assert 'Enter the World Cup' in COUNTDOWN, (
        'The sealed-state decree CTA should read "Enter the World Cup" and '
        'route to the WC hub.'
    )


def test_ballot_card_edit_action_is_review_and_edit_my_roster():
    assert 'Review &amp; Edit My Roster' in BALLOT, (
        'The has-picks edit action was reworded to "Review & Edit My '
        'Roster" so the home-page CTA matches the user-facing spec.'
    )


# ---------------------------------------------------------------------------
# P1 #7 — home-shell heights resolve through CSS custom properties
# ---------------------------------------------------------------------------

def test_tokens_declare_chrome_height_custom_properties():
    tokens = TOKENS_CSS.read_text()
    assert '--ccc-nav-h:' in tokens, (
        '--ccc-nav-h token is missing. tokens.css is the SSoT for chrome '
        'heights; layout calc()s consume them.'
    )
    assert '--ccc-footer-h:' in tokens, (
        '--ccc-footer-h token is missing.'
    )


def test_home_shell_min_height_uses_chrome_tokens():
    """The .home-shell rule must resolve through the tokens, not hardcoded
    56px/200px. If the nav or footer ever changes height, only the tokens
    move; every calc() that derives from chrome flows through."""
    css = STYLE_CSS.read_text()
    # Capture just the .home-shell { ... } block (first match — there are
    # later @media overrides for breakpoints).
    m = re.search(r'\.home-shell\s*\{[^}]*\}', css)
    assert m, '.home-shell rule not found in style.css'
    block = m.group(0)
    assert 'var(--ccc-nav-h)' in block, (
        '.home-shell min-height must reference var(--ccc-nav-h). The '
        'hardcoded 56px form leaks if the navbar ever changes height.'
    )
    assert 'var(--ccc-footer-h)' in block, (
        '.home-shell min-height must reference var(--ccc-footer-h).'
    )


# ---------------------------------------------------------------------------
# Roster Spine mobile stacking — every grid cell explicitly placed
# ---------------------------------------------------------------------------

def _extract_media_blocks(css: str, query: str) -> list[str]:
    """Return the brace-matched bodies of every media block opened by
    `query`. Regex alone can't capture a media block (nested braces), so
    walk the braces. CSS comments are stripped first: style.css comments
    legitimately carry stray braces (e.g. the "{n}" and "{LETTER}" cron/
    regex examples), and a brace inside a comment would corrupt the depth
    count."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    blocks = []
    i = 0
    while True:
        i = css.find(query, i)
        if i == -1:
            break
        j = css.find('{', i)
        if j == -1:
            raise ValueError(
                f'No opening brace after {query!r} at index {i}; '
                'style.css is malformed or truncated.'
            )
        depth, k = 1, j + 1
        while depth and k < len(css):
            if css[k] == '{':
                depth += 1
            elif css[k] == '}':
                depth -= 1
            k += 1
        if depth:
            raise ValueError(
                f'Unbalanced braces in media block opened at index {j}; '
                'style.css is malformed or truncated.'
            )
        blocks.append(css[j + 1:k - 1])
        i = k
    return blocks


def test_ballot_spine_mobile_grid_places_every_cell_explicitly():
    """The ≤480px ballot-spine block must place all five tier-row children
    on the two-row mobile grid with explicit, value-locked grid-row +
    grid-column. The pre-fix block pinned -name and -count to the same
    column track (two items locked to one track can't share a row, so the
    count dropped to its own line) and left -mult to grid auto-placement,
    which wrapped it to a 4th row inside the 1.75rem tag column as an
    orphaned "×1". Each tier burned 4 visual rows; the redesigned stack is
    2 (header beat tag | name | count | ×mult, then countries indented to
    the spine on row 2). Values are asserted, not just property presence:
    the realistic regression is a wrong-value edit (picks back on row 1,
    two children sharing a column, a collapsed track list), and each of
    those must fail here."""
    css = STYLE_CSS.read_text()
    blocks = [
        b for b in _extract_media_blocks(css, '@media (max-width: 480px)')
        if '.ballot-spine-tier-row' in b
    ]
    assert len(blocks) == 1, (
        'Expected exactly one max-width:480px block styling '
        f'.ballot-spine-tier-row, found {len(blocks)}'
    )
    block = blocks[0]
    row = re.search(r'\.ballot-spine-tier-row\s*\{([^}]*)\}', block)
    assert row and 'grid-template-columns: 1.75rem auto 1fr 2.2rem' in row.group(1), (
        'The mobile ballot-spine row must keep the 4-track grid '
        '(tag | name | count | mult); collapsing the track list re-breaks '
        'the header row.'
    )
    expected = {
        'tag': ('grid-row: 1', 'grid-column: 1'),
        'name': ('grid-row: 1', 'grid-column: 2'),
        'count': ('grid-row: 1', 'grid-column: 3'),
        'mult': ('grid-row: 1', 'grid-column: 4'),
        'picks': ('grid-row: 2', 'grid-column: 2 / -1'),
    }
    for child, (grow, gcol) in expected.items():
        m = re.search(
            r'\.ballot-spine-tier-' + child + r'\s*\{([^}]*)\}', block)
        assert m, (
            f'.ballot-spine-tier-{child} has no rule in the 480px '
            'ballot-spine block; an unplaced child falls to grid '
            'auto-placement and orphans onto its own row.'
        )
        decls = m.group(1)
        assert grow in decls and gcol in decls, (
            f'.ballot-spine-tier-{child} must declare "{grow}; {gcol}" in '
            'the mobile block (header children on distinct row-1 columns, '
            'picks indented on row 2; wrong values re-create the orphaned '
            'stacking this lock guards against).'
        )


# ---------------------------------------------------------------------------
# Flash-messages container only renders when there is a message (P0 #4)
# ---------------------------------------------------------------------------

def test_flash_messages_container_is_conditional():
    """The base template previously always rendered `<div class="container
    mt-3">` for flash messages, leaving a cream stripe between the navbar
    and the purple home-shell even when no message existed. The container
    now sits inside the `{% if messages %}` guard."""
    # Whitespace-flexible regex so reindenting `base.html` (auto-formatter,
    # tab→space conversion, etc.) does not break this lock without
    # behavior actually regressing. The semantic invariant is: an `{% if
    # messages %}` block appears, and the `<div class="container mt-3">`
    # sits inside it.
    pattern = re.compile(
        r'\{%\s*if\s+messages\s*%\}\s*<div\s+class="container\s+mt-3"',
        re.DOTALL,
    )
    assert pattern.search(BASE_HTML), (
        'Flash-messages container is no longer guarded by `{% if messages '
        '%}`. The unconditional render leaves a cream gap between navbar '
        'and home-shell on the pre-state home page.'
    )


# ---------------------------------------------------------------------------
# End-to-end: rendered HTML at `/` for the unenrolled pre-state user
# ---------------------------------------------------------------------------

def _extract_decree_block(html: str) -> str:
    """Return the substring covering the `<div class="decree">...</div>`
    countdown card, with nested divs balanced.

    The countdown card is the surface the assertion in
    `test_unenrolled_pre_state_home_renders_correct_cta_and_copy` scopes to.
    A blanket `phrase not in body` check would pass spuriously the moment
    any unrelated future template introduces the phrase elsewhere on the
    home page; scoping to this fragment keeps the assertion intent-aligned
    with what the polish pass actually changed (P0 #2: CTA removed from
    THIS card, the dossier slot below owns the conditional CTA).
    """
    # Resilient to attribute order + quote style: matches `<div ... class="…
    # decree …" …>` whether `class` is first or last, single- or double-
    # quoted, with or without other classes alongside `decree`. Word
    # boundaries on `decree` so a future `.decree-foo` class on a different
    # element doesn't accidentally match.
    open_re = re.compile(
        r'<div\b[^>]*\bclass=["\'][^"\']*\bdecree\b[^"\']*["\']'
    )
    m = open_re.search(html)
    assert m, '.decree countdown card not found in rendered HTML'
    start = m.start()
    depth = 0
    i = start
    while i < len(html):
        if html.startswith('<div', i):
            depth += 1
            i += 4
        elif html.startswith('</div>', i):
            depth -= 1
            if depth == 0:
                return html[start:i + len('</div>')]
            i += len('</div>')
        else:
            i += 1
    raise AssertionError('.decree block has unbalanced <div> tags')


# Clock is frozen to a known pre-deadline UTC instant so `worldcup_state()`
# always resolves to 'pre' in CI, regardless of when the suite runs.
# TOURNAMENT_DEADLINE_UTC is 2026-06-11 19:00 UTC; we pick a day in early
# May so the countdown shows a comfortable double-digit `Days` value if a
# future failure dumps the rendered body. The env-var seam requires BOTH
# WC_FAKE_NOW and ENVIRONMENT in the same patch dict — see CLAUDE.md
# "Mocking the time/deadline seam" + the `now_utc()` guard in
# `games/worldcup/services/state.py`. Without ENVIRONMENT=testing the
# seam silently no-ops (test-isolated processes don't inherit it).
_FROZEN_PRE_DEADLINE_NOW = '2026-05-15T12:00:00+00:00'


@patch.dict(os.environ, {
    'WC_FAKE_NOW': _FROZEN_PRE_DEADLINE_NOW,
    'ENVIRONMENT': 'testing',
})
def test_unenrolled_pre_state_home_renders_correct_cta_and_copy(app, client, monkeypatch):
    """Integrated render: log in a fresh user with no enrollment, hit `/`,
    and verify (a) the dossier shows the Join CTA, (b) the Commish copy
    reads the user-supplied text, (c) the countdown card does NOT carry
    the deleted "Review & Edit My Roster" button copy.

    Wall-clock independence: the test patches `WC_FAKE_NOW` to a fixed
    pre-deadline instant so `worldcup_state()` resolves to 'pre' on any
    CI run, including post-2026-06-11. The pre-fix version of this test
    relied on real time, which would have flipped the home to 'live'
    state and silently broken the assertions for the rest of time
    (caught by CR on PR #20).

    WC-era pinned: the 2026-08-11 changeover features CFB in the real
    registry; this render lock covers the archived WC pre-state lounge.
    """
    from tests._registry_helpers import set_is_featured, set_status
    set_status(monkeypatch, 'worldcup', 'open')
    set_is_featured(monkeypatch, 'worldcup', True)
    set_status(monkeypatch, 'cfb', 'coming_soon')
    set_is_featured(monkeypatch, 'cfb', False)
    _login_as_unenrolled(app, client)
    resp = client.get('/')
    assert resp.status_code == 200
    body = resp.data.decode()

    # The decree shows the Join CTA for unenrolled.
    assert 'Join the World Cup pool' in body, (
        'Unenrolled pre-state home is missing the decree Join CTA label.'
    )

    # Commish copy is the user-supplied verbatim (US-spelling per S6.1.5).
    assert 'Fortune favors the bold.' in body, (
        'Pre-state Commish note is not rendering the user-supplied copy.'
    )

    # The deleted countdown CTA copy must not appear *inside the countdown
    # card itself*. The ballot card (which carries the same phrase for
    # enrolled-with-picks users) lives in the dossier slot below and isn't
    # rendered here anyway, but scoping to .decree future-proofs the lock
    # against any other home-page surface ever using the phrase legitimately
    # — convention per CR on PR #20.
    decree = _extract_decree_block(body)
    assert 'Review &amp; Edit My Roster' not in decree, (
        'The countdown CTA was supposed to be removed, but the phrase '
        '"Review & Edit My Roster" is leaking back into the .decree '
        'countdown card markup.'
    )
