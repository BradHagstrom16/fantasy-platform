"""CFB pick page: the colorize + animate pass (impeccable, 2026-09-01).

Color is state, never decoration, in this room (games/cfb/DESIGN.md 6.5-6.7):
  - the status strip wears the summons signature (crimson top rule, the
    obligation line in bone-white) only while the pick is UNANSWERED, and
    escalates the countdown by hierarchy inside the last 24 hours (6.14)
  - the held block carries the confirmed check, the locked block the lock
    (6.6: confirmed = calm positive accent + check icon; locked = lock icon)
Motion clarifies a selection or a state change (6.14): the commit bar's
arrival and its name swap are the authored moments, the disclosure's cards
stagger in with a capped delay, and every rule has a reduced-motion path.
"""
import dataclasses
import os
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

import games.registry as registry
from extensions import db
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)

CSS = Path('static/css/style.css').read_text(encoding='utf-8')
TEMPLATE = Path('games/cfb/templates/cfb/pick.html').read_text(encoding='utf-8')

DEADLINE = datetime(2026, 9, 5, 11, 0)          # Sat 11:00 CT (naive pool clock)
FAR_NOW = {'ENVIRONMENT': 'testing', 'CFB_FAKE_NOW': '2026-09-01T17:00:00'}   # Tue
SOON_NOW = {'ENVIRONMENT': 'testing', 'CFB_FAKE_NOW': '2026-09-05T13:00:00'}  # 3h out
LOCK_NOW = {'ENVIRONMENT': 'testing', 'CFB_FAKE_NOW': '2026-09-04T12:00:00'}  # Fri


@pytest.fixture(autouse=True)
def cfb_open():
    flipped = [
        dataclasses.replace(e, status='open') if e.slug == 'cfb' else e
        for e in registry.GAMES
    ]
    with patch.object(registry, 'GAMES', flipped):
        yield


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _seed(*, held=False, game_time=None):
    week = make_week(1, deadline=DEADLINE, is_active=True)
    fav, dog = make_team('Navy'), make_team('South Carolina')
    game = make_game(week, fav, dog, spread=-7.0)
    if game_time is not None:
        game.game_time = game_time
    user = make_user('member')
    make_enrollment(user)
    if held:
        make_pick(user, week, fav)
    db.session.commit()
    return user


def _status_classes(html):
    m = re.search(r'<div class="(cfb-pick-status[^"]*)"', html)
    return m.group(1).split() if m else []


# ── the status strip: color is state ─────────────────────────────────────

def test_unanswered_strip_wears_the_summons_signature(client, app):
    user = _seed()
    _login(client, user)
    with patch.dict(os.environ, FAR_NOW):
        html = client.get('/cfb/pick/1').get_data(as_text=True)
    assert 'is-unanswered' in _status_classes(html)
    assert 'is-soon' not in _status_classes(html)


def test_held_strip_goes_quiet(client, app):
    user = _seed(held=True)
    _login(client, user)
    with patch.dict(os.environ, FAR_NOW):
        html = client.get('/cfb/pick/1').get_data(as_text=True)
    assert 'is-unanswered' not in _status_classes(html)


def test_countdown_escalates_inside_24_hours(client, app):
    user = _seed()
    _login(client, user)
    with patch.dict(os.environ, SOON_NOW):
        html = client.get('/cfb/pick/1').get_data(as_text=True)
    assert 'is-soon' in _status_classes(html)


def test_held_block_carries_the_check_and_locked_the_lock(client, app):
    user = _seed(held=True, game_time=datetime(2026, 9, 3, 19, 0))
    _login(client, user)
    with patch.dict(os.environ, FAR_NOW):
        held = client.get('/cfb/pick/1').get_data(as_text=True)
    assert re.search(r'cfb-holding(?! is-locked)[^>]*>\s*<span class="cfb-eyebrow">'
                     r'<i class="bi bi-check-circle-fill cfb-holding-mark"', held)
    with patch.dict(os.environ, LOCK_NOW):   # Thursday kickoff, deadline still ahead
        locked = client.get('/cfb/pick/1').get_data(as_text=True)
    assert 'cfb-holding is-locked' in locked
    assert 'bi-lock-fill cfb-holding-mark' in locked


# ── CSS: the state colors + the motion system ────────────────────────────

def _block(selector):
    m = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', CSS)
    return m.group(1) if m else ''


def test_unanswered_strip_css_is_a_crimson_top_rule_with_white_lead():
    assert re.search(r'border-top:\s*3px solid var\(--game-primary\)',
                     _block('.cfb-pick-status.is-unanswered'))
    assert 'var(--cfb-white)' in _block('.cfb-pick-status.is-unanswered .cfb-status-line')


def test_soon_countdown_is_large_bold_crimson_bright():
    block = _block('.cfb-pick-status.is-soon .cfb-deadline strong')
    assert 'var(--cfb-crimson-bright)' in block
    assert re.search(r'font-size:\s*1\.2[5-9]?rem', block)  # >= 19.2px bold = large text
    assert re.search(r'font-weight:\s*700', block)          # WCAG bold is 700, not 600


def test_holding_mark_is_survived_green_and_locked_is_bone():
    assert 'var(--cfb-survived)' in _block('.cfb-holding-mark')
    assert 'var(--cfb-bone-muted)' in _block('.cfb-holding.is-locked .cfb-holding-mark')


def test_motion_tokens_and_authored_moments_exist():
    assert re.search(r'--cfb-ease-out:\s*cubic-bezier\(\.16,\s*1,\s*\.3,\s*1\)', CSS)
    assert '@keyframes cfb-bar-rise' in CSS
    assert 'animation: cfb-bar-rise' in _block('#pickConfirmBar.is-arriving')
    assert 'animation: cfb-ack' in _block('.cfb-confirm-line.is-updated')
    assert 'animation: cfb-card-rise' in _block('.cfb-board-rest[open] .team-pick-card')


def test_disclosure_stagger_is_capped():
    delays = re.findall(
        r'\.cfb-board-rest\[open\] \.team-pick-card:nth-child\(n\+\d+\)\s*\{\s*animation-delay:\s*(\d+)ms',
        CSS)
    assert delays and max(int(d) for d in delays) <= 200


def test_room_entrance_is_operate_tempo():
    m = re.search(r'body\.game-cfb \.animate-in\s*\{[^}]*animation-duration:\s*\.(\d+)s', CSS)
    assert m and int(m.group(1)) <= 40


def test_every_new_motion_has_a_reduced_motion_path():
    reduced = CSS[CSS.index('#pickConfirmBar.is-arriving'):]
    assert re.search(r'@media \(prefers-reduced-motion: reduce\)[^@]*#pickConfirmBar\.is-arriving[^{}]*\{[^}]*animation:\s*none', reduced)
    assert re.search(r'@media \(prefers-reduced-motion: reduce\)[^@]*\.cfb-confirm-line\.is-updated[^{}]*\{[^}]*animation:\s*none', reduced)
    assert re.search(r'@media \(prefers-reduced-motion: reduce\)[^@]*\.cfb-board-rest\[open\] \.team-pick-card[^{}]*\{[^}]*animation:\s*none', reduced)


# ── JS: the moments are triggered by the picker, not on load ─────────────

def test_picker_js_arms_the_bar_arrival_and_the_name_ack():
    script = TEMPLATE.split('{% block scripts %}', 1)[1]
    assert "classList.add('is-arriving')" in script
    assert "classList.remove('is-arriving')" in script      # cleared on animationend
    assert "classList.add('is-updated')" in script
    # the existing hooks stay byte-identical
    assert "option.classList.add('selected', 'bg-primary', 'text-white');" in script
