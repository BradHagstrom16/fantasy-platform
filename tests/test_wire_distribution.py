"""The Wire's distribution (ADR-074, 2026-10-08): every surface says what The
Wire is (the Club's push notifications), and a member meets the ask where they
already are: the lounge strip, the account menu, and the moment after a pick in
each room.

Locks:
  - /app: no eyebrow over any heading (ADR-066), every member-facing panel
    names "push notifications", one verb ("Turn on The Wire"), the iOS 26
    Safari path (Share, View More, Add to Home Screen), and Android Chrome
    resolving to the button in the tab instead of the iPhone steps
  - the account menu carries The Wire for members only, never the
    js-buzz-link hide (it is also the way to Turn off and Send a test)
  - the lounge strip renders for a member and hides through js-buzz-link
  - the CFB nudge rides only inside the held-pick branch of the weekly call
  - the Docket nudge closes the filed card, and only the filed card
"""
import re
from pathlib import Path

from extensions import db
from tests._docket_fixtures import (
    IN_WEEK1,
    at,
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)
from tests.test_docket_sheet_flow import KICK_SAT, _file, _file_eight_with_x2_and_number

REPO = Path(__file__).resolve().parent.parent
PANEL = re.compile(r'<section class="app-panel" data-state="(\w+)">(.*?)</section>', re.S)


def _member(client, name='wiremember'):
    user = make_user(name)
    db.session.commit()
    login(client, user)
    return user


def _text(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


# ── /app ─────────────────────────────────────────────────────────────────

def test_app_has_no_eyebrow_over_any_heading(app, client):
    _member(client)
    body = client.get('/app').get_data(as_text=True)
    assert 'auth-eyebrow' not in body


def test_every_member_panel_says_push_notifications(app, client):
    _member(client)
    body = client.get('/app').get_data(as_text=True)
    panels = dict(PANEL.findall(body))
    assert len(panels) == 9
    # "checking" is the transient half second before push.js settles; every
    # panel a member can rest on names the thing plainly.
    for state, html in panels.items():
        if state == 'checking':
            continue
        assert 'push notifications' in _text(html).lower(), state


def test_one_verb_turn_on_the_wire(app, client):
    _member(client)
    body = client.get('/app').get_data(as_text=True)
    assert 'Get on the wire' not in body
    panels = dict(PANEL.findall(body))
    assert 'Turn on The Wire' in _text(panels['unsubscribed'])


def test_iphone_steps_follow_the_ios_26_share_sheet(app, client):
    _member(client)
    panels = dict(PANEL.findall(client.get('/app').get_data(as_text=True)))
    for state in ('tab', 'inapp'):
        steps = _text(panels[state])
        share, more, home = (steps.index('Share'), steps.index('View More'),
                             steps.index('Add to Home Screen'))
        assert share < more < home, state


def test_android_tab_resolves_to_the_button_not_the_iphone_steps(app, client):
    body = client.get('/app').get_data(as_text=True)
    script = body[body.index('var state;'):body.index("el.setAttribute('data-app-state', state)")]
    android = script.index("else if (!iOS && canPush) { state = 'checking'; }")
    # After every iOS and standalone branch, before the iPhone-steps default.
    assert script.index("else if (standalone) { state = 'checking'; }") < android
    assert android < script.index("else { state = 'tab'; }")


# ── The account menu ─────────────────────────────────────────────────────

MENU_ITEM = re.compile(r'<a class="dropdown-item" href="/app">\s*<i class="bi bi-bell me-2"></i>The Wire\s*</a>')


def test_account_menu_carries_the_wire_for_members(app, client):
    _member(client)
    body = client.get('/profile').get_data(as_text=True)
    item = MENU_ITEM.search(body)
    assert item, 'The Wire missing from the account menu'
    assert 'js-buzz-link' not in item.group(0)


def test_account_menu_absent_for_visitors(client):
    assert not MENU_ITEM.search(client.get('/login').get_data(as_text=True))


# ── The lounge strip ─────────────────────────────────────────────────────

def test_lounge_strip_renders_for_a_member_and_hides_when_subscribed(app, client):
    _member(client)
    body = client.get('/').get_data(as_text=True)
    strip = re.search(r'<section class="wire-strip js-buzz-link"(.*?)</section>', body, re.S)
    assert strip, 'lounge strip missing'
    text = _text(strip.group(1))
    assert 'Push notifications from the Club' in text
    assert 'Turn on The Wire' in text
    assert body.count('wire-strip js-buzz-link') == 1


def test_lounge_strip_absent_for_visitors(client):
    assert 'wire-strip' not in client.get('/').get_data(as_text=True)


# ── The rooms ────────────────────────────────────────────────────────────

def test_cfb_nudge_rides_only_the_held_pick_branch():
    src = (REPO / 'games/cfb/templates/cfb/index.html').read_text()
    held = src.index('{% if user_pick %}')
    nudge = src.index('cfb-wire-note js-buzz-link')
    branch_end = src.index('{% else %}', held)
    assert held < nudge < branch_end
    assert src.count('cfb-wire-note') == 1
    assert 'the hour {{ user_pick.team.name }} goes final' in src


def test_docket_nudge_closes_the_filed_card(monkeypatch, app, client):
    user = make_user('docketwire')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    week = make_week(1)
    games = [make_game(week, kickoff=KICK_SAT, home=f'Home {i}', away=f'Away {i}')
             for i in range(8)]
    week.tiebreaker_game_id = games[7].id
    db.session.commit()
    at(monkeypatch, IN_WEEK1)

    _file(client, games[0])
    partial = client.get('/docket/').get_data(as_text=True)
    assert 'docket-wire-note' not in partial

    _file_eight_with_x2_and_number(client, week, games)
    html = client.get('/docket/').get_data(as_text=True)
    card = re.search(r'<div class="docket-filed">(.*?)</div>\s*$', html, re.S | re.M)
    assert html.count('docket-wire-note js-buzz-link') == 1
    assert card and 'docket-wire-note' in card.group(1)
    assert 'the hour each side is decided' in _text(html)
