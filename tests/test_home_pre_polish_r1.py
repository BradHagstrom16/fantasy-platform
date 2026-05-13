"""Regression locks for the home pre-state polish pass (branch `home/pre-state-polish-r1`).

Surface: `/` rendered for a logged-in pre-deadline user. The pass made six
content/layout changes that need locking against future drift:

  P0 #2: countdown card lost its hardcoded "Review & Edit My Roster" CTA
         block + the "Days to the Whistle" subtitle + the "ticking" trail.
  P0 #3: fixture cards lost the misleading "◯ PICK DUE" status badge.
  P0 #5: pre-state Commish note replaced with user-supplied verbatim copy
         (first-person voice, retains British "favours" spelling).
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
from models.user import User


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / 'core' / 'main' / 'templates' / 'main'
STYLE_CSS = REPO_ROOT / 'static' / 'css' / 'style.css'
TOKENS_CSS = REPO_ROOT / 'static' / 'css' / 'tokens.css'

COUNTDOWN = (TEMPLATES / '_countdown_card.html').read_text()
COMMISH = (TEMPLATES / '_commish_note.html').read_text()
JOIN_CTA = (TEMPLATES / '_join_cta_card.html').read_text()
SUBMIT_CTA = (TEMPLATES / '_submit_picks_cta.html').read_text()
BALLOT = (TEMPLATES / '_ballot_card.html').read_text()
FIXTURE = (TEMPLATES / '_fixture_card.html').read_text()
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
    with client.session_transaction() as sess:
        sess['_user_id'] = str(uid)
        sess['_fresh'] = True
    return uid


# ---------------------------------------------------------------------------
# P0 #2 — countdown card no longer carries its CTA / subtitle / "ticking"
# ---------------------------------------------------------------------------

def test_countdown_card_has_no_cta_block():
    """The countdown card had a hardcoded `Review & Edit My Roster` CTA
    that overrode the dossier slot below. P0 #2 removed it. The dossier
    slot now owns the single CTA surface; resurrecting the countdown CTA
    means the user sees two stacked CTAs again."""
    assert 'decree-actions' not in COUNTDOWN, (
        'decree-actions wrapper is back — the countdown CTA was deleted '
        'in favor of the dossier slot. Re-adding it duplicates the CTA.'
    )
    assert 'decree-cta' not in COUNTDOWN, (
        'decree-cta button is back. The dossier slot (`_join_cta_card.html` '
        '/ `_submit_picks_cta.html` / `_ballot_card.html`) owns the CTA now.'
    )
    assert 'Review &amp; Edit My Roster' not in COUNTDOWN, (
        'The hardcoded "Review & Edit My Roster" CTA was removed. If you '
        'need a roster-edit link here, branch it on enrollment state — but '
        'the design intent is to keep one CTA, in the dossier slot.'
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
    assert (
        'aria-label="Time remaining until World Cup tribute window closes"'
        in COUNTDOWN
    ), (
        'P1 #8: aria-label should describe what the timer counts down TO, '
        'not restate the visible unit symbols.'
    )


# ---------------------------------------------------------------------------
# P0 #3 — fixture cards no longer carry the misleading PICK DUE badge
# ---------------------------------------------------------------------------

def test_fixture_card_has_no_pick_due_badge():
    """The `◯ PICK DUE` badge rendered on every upcoming-match card was
    misleading — there is one global tournament deadline, not a per-match
    deadline. P0 #3 deleted the badge while keeping the venue/city note."""
    assert 'PICK DUE' not in FIXTURE, (
        'PICK DUE badge is back on the fixture card. Picks are due once, '
        'at the tournament deadline — not per match.'
    )


def test_fixture_card_kickoff_uses_ct_filter_not_utc_strftime():
    """Kickoff times should render in Central Time via the `|ct` filter,
    not as `strftime('%H:%M UTC')`. Locks the migration away from raw
    UTC display strings."""
    assert "'%H:%M UTC'" not in FIXTURE and "%H:%M UTC" not in FIXTURE, (
        'Fixture card reverted to a UTC strftime. Use the `|ct` Jinja '
        'filter (registered in app.py); the helper lives at utils/time.py.'
    )
    assert '|ct(' in FIXTURE, (
        'Fixture card is no longer piping kickoff through the `ct` filter. '
        'The platform display TZ is America/Chicago — see utils/time.py.'
    )


# ---------------------------------------------------------------------------
# P0 #5 — Commish note pre-state copy is user-supplied verbatim
# ---------------------------------------------------------------------------

def test_commish_note_pre_state_copy_verbatim():
    """The pre-state branch is now a first-person voice (`I hope you enjoy
    the site`) supplied by the platform owner, intentionally distinct from
    the elevated Commish tone in the live + post branches. The British
    spelling "favours" is intentional — do not Americanize."""
    # Collapse runs of whitespace so phrases that wrap across lines in the
    # template (with indentation) still match. The user-facing render
    # collapses whitespace the same way.
    normalized = re.sub(r'\s+', ' ', COMMISH)
    expected_phrases = [
        'Welcome to the Club, I hope you enjoy the site.',
        'Pass along any feedback that you have.',
        'World Cup tribute window is open until June 11th.',
        'Pick your nine nations wisely, take your seat, and watch the action unfold.',
        'Fortune favours the bold.',
    ]
    for phrase in expected_phrases:
        assert phrase in normalized, (
            f'Pre-state Commish note is missing: {phrase!r}. The verbatim '
            f'copy is owner-supplied; do not paraphrase or "polish".'
        )
    # Hard lock on the British spelling.
    assert 'favors' not in COMMISH, (
        '"favours" was Americanized to "favors". The user explicitly '
        'requested the British spelling — keep it.'
    )


def test_commish_note_post_branch_unchanged_by_pre_state_edit():
    """Sanity check: the live + post branches retain the elevated Commish
    voice. The polish pass only touched the pre-state branch."""
    assert "The 2026 ledger is closed." in COMMISH
    assert "Picks are sealed." in COMMISH


# ---------------------------------------------------------------------------
# P0 #6 — dossier CTA labels match the user's functional spec
# ---------------------------------------------------------------------------

def test_join_cta_label_is_join_the_world_cup_pool():
    assert 'Join the World Cup Pool' in JOIN_CTA, (
        'The unenrolled CTA was reworded to "Join the World Cup Pool".'
    )


def test_submit_picks_cta_label_is_make_your_picks():
    assert 'Make Your Picks' in SUBMIT_CTA, (
        'The enrolled-no-picks CTA was reworded to "Make Your Picks".'
    )
    assert 'Seal the Oath' not in SUBMIT_CTA, (
        'Old Commish-voice button label is back. The polish pass made '
        'this CTA functional, not ceremonial.'
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
# Flash-messages container only renders when there is a message (P0 #4)
# ---------------------------------------------------------------------------

def test_flash_messages_container_is_conditional():
    """The base template previously always rendered `<div class="container
    mt-3">` for flash messages, leaving a cream stripe between the navbar
    and the purple home-shell even when no message existed. The container
    now sits inside the `{% if messages %}` guard."""
    # The container div must follow the `{% if messages %}` check.
    if_then_container = (
        '{% if messages %}\n        <div class="container mt-3">'
    )
    assert if_then_container in BASE_HTML, (
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
    start = html.find('<div class="decree"')
    assert start >= 0, '.decree countdown card not found in rendered HTML'
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
def test_unenrolled_pre_state_home_renders_correct_cta_and_copy(app, client):
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
    """
    _login_as_unenrolled(app, client)
    resp = client.get('/')
    assert resp.status_code == 200
    body = resp.data.decode()

    # Dossier shows Join CTA for unenrolled.
    assert 'Join the World Cup Pool' in body, (
        'Unenrolled pre-state home is missing the Join CTA button label.'
    )

    # Commish copy is the user-supplied verbatim.
    assert 'Fortune favours the bold.' in body, (
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
