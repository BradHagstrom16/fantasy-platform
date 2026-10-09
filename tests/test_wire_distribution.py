"""The Wire's distribution (ADR-074, 2026-10-08): every surface says what The
Wire is (the Club's push notifications), and a member meets the ask where they
already are: the lounge strip, the account menu, and the moment after a pick in
each room.

Locks:
  - /app: the old eyebrow class is gone (the Eyebrow Rule itself is
    tests/test_eyebrow_above_heading.py, which globs core/push/templates),
    every panel a member can rest on names "push notifications" (the
    transient "checking" excepted), one verb ("Turn on The Wire"), the iOS 26
    Safari path (Share, View More, Add to Home Screen), Android Chrome
    resolving to the button in the tab instead of the iPhone steps, and a
    non-iOS browser without push (or whose worker never registers) landing
    on the nopush panel so "Checking" always ends
  - /app reads "subscribed" only once the server has claimed the browser's
    subscription for the member signed in now (push.js, a source lock)
  - the account menu carries The Wire for members only, on The Wire or not
    (it is also the way to Turn off and Send a test)
  - the lounge strip renders for a member who is not on The Wire
  - the CFB nudge renders under a held pick in the open week, names the
    team, and is absent with no pick or for an eliminated member; its source
    sits only inside the held-pick branch of the weekly call
  - the Docket nudge closes the filed card and the closed card, not the
    blank, partial or x2/number cards, and leaves once every scoring side is
    final (the promise is spent)
  - this member, not this device (Brad 2026-10-08): a member who holds any
    push subscription row sees none of the strip, the profile link or the
    two room nudges, on any device, and still sees the menu item
  - the three overdrive moments (PR B): core/push imports nothing under
    games. but the registry; the notification preview paints on the tab,
    unsubscribed and subscribed panels only; the install coach (the step
    glyphs, the fixed pointer shown only on the tab panel and the no-JS
    default, Android's install button hidden inside the unsubscribed
    panel); push.js morphs the button into the card through a view
    transition and fires the first dispatch once; the strip carries the
    live wire and its script, with the heading untouched
"""
import ast
import re
from datetime import datetime
from pathlib import Path

from extensions import db
from models.push import PushSubscription
from tests import _cfb_fixtures as cfb
from tests._docket_fixtures import (
    IN_WEEK1,
    at,
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)
from tests.test_docket_sheet_flow import (
    KICK_SAT,
    _file,
    _file_eight_with_x2_and_number,
    _final,
)

REPO = Path(__file__).resolve().parent.parent
PANEL = re.compile(r'<section class="app-panel" data-state="(\w+)">(.*?)</section>', re.S)


def _member(client, name='wiremember'):
    user = make_user(name)
    db.session.commit()
    login(client, user)
    return user


def _text(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


def _on_the_wire(user):
    """One live subscription row for the member, any device."""
    db.session.add(PushSubscription(
        user_id=user.id, endpoint=f'https://push.example/{user.username}',
        p256dh='k', auth='a'))
    db.session.commit()


# ── /app ─────────────────────────────────────────────────────────────────

def test_app_has_no_eyebrow_over_any_heading(app, client):
    _member(client)
    body = client.get('/app').get_data(as_text=True)
    assert 'auth-eyebrow' not in body


def test_every_member_panel_says_push_notifications(app, client):
    _member(client)
    body = client.get('/app').get_data(as_text=True)
    panels = dict(PANEL.findall(body))
    assert len(panels) == 10
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
    # A non-iOS browser without push is told so; only iOS falls to the steps.
    assert android < script.index("else if (!iOS) { state = 'nopush'; }") \
        < script.index("else { state = 'tab'; }")
    # "checking" needs the worker API too, or push.js could never resolve it.
    assert "('serviceWorker' in navigator)" in body[:body.index('var state;')]
    # After every iOS and standalone branch, before the iPhone-steps default.
    assert script.index("else if (standalone) { state = 'checking'; }") < android
    assert android < script.index("else { state = 'tab'; }")


def test_app_says_subscribed_only_after_the_server_claims_the_subscription():
    # A shared browser can still hold another member's subscription: /app
    # waits on the ownership upsert before it reads as "subscribed" (#268).
    src = (REPO / 'static/js/push.js').read_text()
    resolve = src[src.index('function resolveAppState(reg)'):src.index('function restoreCta(btn)')]
    assert 'claimSubscription(reg).then' in resolve
    assert "setState(claim.ok ? 'subscribed' : 'unsubscribed')" in resolve
    assert "if (sub) { setState('subscribed')" not in resolve
    # One upsert per /app open: the load handler leaves it to resolveAppState.
    assert 'if (isStandalone() && !onApp) { upsertOnOpen(reg); }' in src


# ── The overdrive moments (PR B) ─────────────────────────────────────────

def test_core_push_imports_no_game_but_the_registry():
    """The hijack lock: `/app` reaches a game's preview only through
    games.registry (the seam tests/test_registry_seam.py guards for the
    lounge), never a game module."""
    for path in sorted((REPO / 'core/push').glob('*.py')):
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.ImportFrom):
                names = [node.module or '']
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                if name.startswith('games'):
                    assert name == 'games.registry', f'{path.name} imports {name}'


def test_preview_paints_on_the_tab_unsubscribed_and_subscribed_panels(app, client):
    _member(client)
    panels = dict(PANEL.findall(client.get('/app').get_data(as_text=True)))
    with_card = {s for s, html in panels.items() if 'app-wire-screen' in html}
    assert with_card == {'tab', 'unsubscribed', 'subscribed'}
    # The card the button becomes carries the shared transition name.
    assert 'app-wire--target' in panels['subscribed']
    assert 'app-wire--target' not in panels['unsubscribed']
    # Nothing we send says "from CCC": the app name and "now" are the chrome
    # the phone draws, and the title and body are the sender's own words.
    assert 'from CCC' not in panels['tab']


def test_install_coach_markup_sits_where_it_should(app, client):
    _member(client)
    body = client.get('/app').get_data(as_text=True)
    panels = dict(PANEL.findall(body))
    # One pointer, outside every panel.
    assert body.count('class="app-coach"') == 1
    assert not any('app-coach' in html for html in panels.values())
    # A glyph on each iPhone step, in both panels that show the steps.
    for state in ('tab', 'inapp'):
        assert panels[state].count('app-step-glyph') == 4, state
    # Android's install button: hidden, inside the unsubscribed panel only.
    holders = [s for s, html in panels.items() if 'id="app-install"' in html]
    assert holders == ['unsubscribed']
    assert re.search(r'id="app-install"\s+hidden', panels['unsubscribed'])
    assert 'app-install' not in panels['nopush']


def test_install_coach_pointer_shows_only_on_the_tab_panel():
    css = (REPO / 'static/css/style.css').read_text()
    shown = re.findall(r'html(?:\[data-app-state="(\w+)"\]|:not\(\[data-app-state\]\)) \.app-coach', css)
    assert set(shown) == {'tab', ''}, shown
    assert '@media (display-mode: standalone)' in css
    coach = css[css.index('.app-coach {'):css.index('.app-cta-wrap .app-install')]
    assert 'var(--coach-x, 50%)' in coach
    assert 'coach-bounce' in coach and '2;' in coach.split('coach-bounce')[1][:40]
    assert '@media (prefers-reduced-motion: reduce)' in coach


def test_push_js_morphs_the_button_and_fires_the_first_dispatch_once():
    src = (REPO / 'static/js/push.js').read_text()
    assert 'document.startViewTransition' in src
    assert "setState('subscribed')" in src[src.index('function morphToSubscribed'):]
    assert 'prefers-reduced-motion' in src
    assert "if (ok) { morphToSubscribed(); firstDispatch(sub); return; }" in src
    first = src[src.index('function firstDispatch(sub)'):src.index('function wireCta(reg)')]
    assert "postJSON('/push/test', { endpoint: sub.endpoint })" in first
    assert 'resp.status === 429' in first           # already sent, not an error
    assert 'firstDispatchSent' in first
    assert "window.addEventListener('beforeinstallprompt'" in src
    css = (REPO / 'static/css/style.css').read_text()
    assert '#push-cta { view-transition-name: wire-card; }' in css
    assert '.app-wire--target .app-wire-screen { view-transition-name: wire-card; }' in css


def test_lounge_strip_carries_the_live_wire(app, client):
    _member(client)
    body = client.get('/').get_data(as_text=True)
    strip = re.search(r'<section class="wire-strip"(.*?)</section>', body, re.S).group(1)
    for cls in ('wire-strip-art', 'wire-strip-wire', 'wire-strip-pulse', 'wire-strip-phone'):
        assert strip.count(f'class="{cls}"') == 1, cls
    assert re.search(r'js/wire-strip\.js\?v=\w+', strip)
    # The heading's accessible name keeps its two phrases apart.
    assert ('<span class="wire-strip-name">The Wire</span> '
            '<span class="wire-strip-sep" aria-hidden="true">&middot;</span> '
            'Push notifications from the Club') in strip
    css = (REPO / 'static/css/style.css').read_text()
    live = css[css.index('.home-shell .wire-strip-art'):css.index('/* --- Pre-state: countdown card.')]
    assert 'IntersectionObserver' in (REPO / 'static/js/wire-strip.js').read_text()
    assert 'infinite' not in live                 # the pulse travels once
    assert '@media (prefers-reduced-motion: reduce)' in live


# ── The account menu ─────────────────────────────────────────────────────

MENU_ITEM = re.compile(r'<a class="dropdown-item" href="/app">\s*<i class="bi bi-bell me-2"></i>The Wire\s*</a>')


def test_account_menu_carries_the_wire_for_members(app, client):
    _member(client)
    body = client.get('/profile').get_data(as_text=True)
    assert MENU_ITEM.search(body), 'The Wire missing from the account menu'
    assert 'Turn on The Wire' in body                  # the profile link too


def test_account_menu_stays_for_a_member_on_the_wire_but_the_profile_link_goes(app, client):
    user = _member(client)
    _on_the_wire(user)
    body = client.get('/profile').get_data(as_text=True)
    assert MENU_ITEM.search(body), 'the menu item is also the way to Turn off'
    assert 'Turn on The Wire' not in body


def test_account_menu_absent_for_visitors(client):
    assert not MENU_ITEM.search(client.get('/login').get_data(as_text=True))


# ── The lounge strip ─────────────────────────────────────────────────────

def test_lounge_strip_renders_for_a_member(app, client):
    _member(client)
    body = client.get('/').get_data(as_text=True)
    strip = re.search(r'<section class="wire-strip"(.*?)</section>', body, re.S)
    assert strip, 'lounge strip missing'
    text = _text(strip.group(1))
    assert 'Push notifications from the Club' in text
    assert 'Turn on The Wire' in text
    assert body.count('class="wire-strip"') == 1


def test_lounge_strip_absent_for_visitors(client):
    assert 'wire-strip' not in client.get('/').get_data(as_text=True)


def test_lounge_strip_omitted_for_a_member_on_the_wire(app, client):
    """This member, not this device: one subscription row on any device and
    the lounge stops asking, with nothing painted to hide."""
    user = _member(client)
    assert 'wire-strip' in client.get('/').get_data(as_text=True)
    _on_the_wire(user)
    assert 'wire-strip' not in client.get('/').get_data(as_text=True)


# ── The rooms ────────────────────────────────────────────────────────────

CFB_DEADLINE = datetime(2026, 9, 5, 11, 0)       # Sat 11:00 CT: Week 1 locks
CFB_PICKING = '2026-09-01T17:00:00'              # the Tuesday before: open


def _cfb_room(monkeypatch, client, *, pick=True, eliminated=False, on_wire=False):
    """The Survivor hub for an enrolled member while Week 1 is open."""
    week = cfb.make_week(1, deadline=CFB_DEADLINE, is_active=True)
    navy, dog = cfb.make_team('Navy'), cfb.make_team('South Carolina')
    cfb.make_game(week, navy, dog, spread=-7.0)
    user = cfb.make_user('cfbwire')
    cfb.make_enrollment(user, eliminated=eliminated)
    if pick:
        cfb.make_pick(user, week, navy)
    db.session.commit()
    if on_wire:
        _on_the_wire(user)
    login(client, user)
    monkeypatch.setenv('CFB_FAKE_NOW', CFB_PICKING)
    return client.get('/cfb/').get_data(as_text=True)


def test_cfb_nudge_renders_under_a_held_pick_and_names_the_team(monkeypatch, client):
    html = _cfb_room(monkeypatch, client)
    assert html.count('cfb-wire-note') == 1
    text = _text(html)
    assert 'Get a push notification the hour Navy goes final.' in text
    assert 'Turn on The Wire' in text


def test_cfb_nudge_omitted_for_a_member_on_the_wire(monkeypatch, client):
    html = _cfb_room(monkeypatch, client, on_wire=True)
    assert 'Your pick' in html and 'Navy' in html         # the pick still shows
    assert 'cfb-wire-note' not in html


def test_cfb_nudge_absent_without_a_pick(monkeypatch, client):
    assert 'cfb-wire-note' not in _cfb_room(monkeypatch, client, pick=False)


def test_cfb_nudge_absent_for_an_eliminated_member(monkeypatch, client):
    html = _cfb_room(monkeypatch, client, eliminated=True)
    assert 'Your season ended.' in html
    assert 'cfb-wire-note' not in html


def test_cfb_nudge_rides_only_the_held_pick_branch():
    src = (REPO / 'games/cfb/templates/cfb/index.html').read_text()
    held = src.index('{% if user_pick %}')
    nudge = src.index('class="cfb-wire-note"')
    branch_end = src.index('{% else %}', held)
    assert held < nudge < branch_end
    assert src.count('cfb-wire-note') == 1
    assert 'the hour {{ user_pick.team.name }} goes final' in src


def _docket_week(monkeypatch, client, *, on_wire=False):
    user = make_user('docketwire')
    make_enrollment(user)
    db.session.commit()
    if on_wire:
        _on_the_wire(user)
    login(client, user)
    week = make_week(1)
    games = [make_game(week, kickoff=KICK_SAT, home=f'Home {i}', away=f'Away {i}')
             for i in range(8)]
    week.tiebreaker_game_id = games[7].id
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    return week, games


def test_docket_nudge_closes_the_filed_card(monkeypatch, app, client):
    week, games = _docket_week(monkeypatch, client)

    _file(client, games[0])
    partial = client.get('/docket/').get_data(as_text=True)
    assert 'docket-wire-note' not in partial

    _file_eight_with_x2_and_number(client, week, games)
    html = client.get('/docket/').get_data(as_text=True)
    # The filed card is the only card on the page, so one nudge on the page
    # is one nudge on the card.
    assert html.count('<div class="docket-filed"') == 1
    assert html.count('docket-wire-note') == 1
    assert 'the hour each side is decided' in _text(html)


def test_docket_nudge_omitted_for_a_member_on_the_wire(monkeypatch, app, client):
    week, games = _docket_week(monkeypatch, client, on_wire=True)
    _file_eight_with_x2_and_number(client, week, games)
    html = client.get('/docket/').get_data(as_text=True)
    assert 'Sheet filed' in html
    assert 'docket-wire-note' not in html


def test_docket_nudge_stays_on_the_closed_card_until_the_last_side_is_final(
        monkeypatch, app, client):
    """Sunday afternoon the card is closed and nothing is decided: the
    promise stands. Two finals in, it still stands for the six to play. Once
    every scoring side is final there is nothing left to promise."""
    week, games = _docket_week(monkeypatch, client)
    _file_eight_with_x2_and_number(client, week, games)
    at(monkeypatch, '2026-09-06T18:00:00')          # closed, Sunday 1 PM CT
    html = client.get('/docket/').get_data(as_text=True)
    assert 'is-closed' in html
    assert html.count('docket-wire-note') == 1

    _final(games[0], home=30, away=20)
    _final(games[1], home=20, away=30)
    db.session.commit()
    html = client.get('/docket/').get_data(as_text=True)
    assert 'docket-filed-record' in html                # the running record leads
    assert html.count('docket-wire-note') == 1

    for game in games[2:]:
        _final(game, home=30, away=20)
    db.session.commit()
    html = client.get('/docket/').get_data(as_text=True)
    assert 'is-closed' in html
    assert 'docket-wire-note' not in html
