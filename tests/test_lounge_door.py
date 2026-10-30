"""The Door: the walk from a lounge headliner panel into its room (ADR-077,
DESIGN.md §4.5, Brad 2026-10-29).

One cross-document view transition. The room opens out of the clicked
panel's rectangle (a clip-path window, never an opacity blend, so the dark
lounge and a light room never mix), the panel head becomes the room's
masthead, the panel name travels into its H1, and Back closes the room into
the panel. static/js/door.js scopes it: only the lounge and a page of the
panel's own game ever transition; every other navigation is a plain load.

Locks:
1. The opt-in exists only with script and without reduced motion, so a
   no-JS or reduced-motion member never gets a transition at all.
2. door.js loads render-blocking in <head> (pagereveal must be registered
   before the first render), versioned, and stands every non-door
   navigation down.
3. Every door rule waits for its door-in / door-out type; the keyframes
   move only clip-path and opacity; the lounge firewall holds.
4. Both ends carry what the script looks for: a door slug on every seated
   panel, a masthead with its words on every room page the lounge links to.
"""
import os
import re
from pathlib import Path
from unittest.mock import patch

from extensions import db
from models.user import User

ROOT = Path(__file__).resolve().parent.parent
STYLE = (ROOT / 'static/css/style.css').read_text(encoding='utf-8')
TOKENS = (ROOT / 'static/css/tokens.css').read_text(encoding='utf-8')
DOOR_JS = (ROOT / 'static/js/door.js').read_text(encoding='utf-8')
BASE = (ROOT / 'templates/base.html').read_text(encoding='utf-8')

DUAL_PRE = {'ENVIRONMENT': 'testing',
            'CFB_FAKE_NOW': '2026-08-18T17:00:00',
            'DOCKET_FAKE_NOW': '2026-08-18T17:00:00'}


def _door_block() -> str:
    start = STYLE.index('/* === THE DOOR')
    end = STYLE.index('/* Panels own their interior spacing', start)
    return STYLE[start:end]


def _strip_comments(css: str) -> str:
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def _top_level_split(prelude: str) -> list[str]:
    """A selector list split on its own commas, not those inside ( )."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(prelude):
        depth += ch == '('
        depth -= ch == ')'
        if ch == ',' and depth == 0:
            parts.append(prelude[start:i])
            start = i + 1
    return parts + [prelude[start:]]


def _keyframes_body(name: str) -> str:
    start = STYLE.index('{', STYLE.index('@keyframes ' + name + ' '))
    depth = 0
    for i in range(start, len(STYLE)):
        depth += STYLE[i] == '{'
        depth -= STYLE[i] == '}'
        if depth == 0:
            return STYLE[start + 1:i]
    raise AssertionError(name)


# ── 1. The opt-in ────────────────────────────────────────────────────────

def test_the_opt_in_needs_script_and_motion():
    css = _strip_comments(STYLE)
    rules = [m.start() for m in re.finditer(r'@view-transition\s*\{', css)]
    assert len(rules) == 1, 'one @view-transition opt-in, in the door block'
    guard = css.rfind('@media', 0, rules[0])
    prelude = css[guard:css.index('{', guard)]
    assert 'scripting: enabled' in prelude
    assert 'prefers-reduced-motion: no-preference' in prelude
    assert re.search(r'@view-transition\s*\{\s*navigation:\s*auto;?\s*\}', css)


def test_door_durations_are_tokens_and_the_exit_is_faster():
    door_in = int(re.search(r'--door-in:\s*(\d+)ms', TOKENS).group(1))
    door_out = int(re.search(r'--door-out:\s*(\d+)ms', TOKENS).group(1))
    # DESIGN.md §4.5: a view transition runs 300-500ms; exits run faster.
    assert 300 <= door_out < door_in <= 500


# ── 2. The scoper ────────────────────────────────────────────────────────

def test_door_js_loads_render_blocking_in_head():
    head = BASE[:BASE.index('</head>')]
    tag = re.search(r'<script[^>]*js/door\.js[^>]*>', head)
    assert tag, 'door.js must load in <head>, before the first render'
    assert 'defer' not in tag.group() and 'async' not in tag.group()
    assert '?v={{ asset_version }}' in tag.group()


def test_door_js_stands_down_every_other_navigation():
    assert "addEventListener('pageswap'" in DOOR_JS
    assert "addEventListener('pagereveal'" in DOOR_JS
    # No activation (Safari before 26, a cross-origin trip): a plain load.
    assert 'e.activation' in DOOR_JS and 'navigation.activation' in DOOR_JS
    assert DOOR_JS.count('skipTransition()') >= 4
    # Lounge <-> room only: the lounge is "/", a room is a game-<slug> body.
    assert "location.pathname === '/'" in DOOR_JS
    assert 'game-' in DOOR_JS and 'data-door-slug' in DOOR_JS
    # A panel offscreen has no doorway to open from.
    assert 'function inView' in DOOR_JS
    # A bfcache-restored page keeps inline names; two under one name abort.
    assert 'function reset' in DOOR_JS


def test_door_js_names_only_the_three_pairs():
    names = set(re.findall(r"name\([^,]+,\s*'([\w-]+)'\)", DOOR_JS))
    assert names == {'door', 'door-words'}
    assert "types.add('door-in')" in DOOR_JS and "types.add('door-out')" in DOOR_JS


# ── 3. The moment ────────────────────────────────────────────────────────

def test_every_door_rule_waits_for_its_type():
    block = _strip_comments(_door_block())
    for prelude in re.findall(r'([^{}]+)\{[^{}]*\}', block):
        prelude = prelude.strip()
        if not prelude or prelude.startswith(('@', 'from', 'to', '65%')):
            continue
        for selector in _top_level_split(prelude):
            assert ':active-view-transition-type(door-' in selector, selector


def test_the_keyframes_move_only_clip_and_opacity():
    for name in ('door-open', 'door-close', 'door-fade-out'):
        body = _keyframes_body(name)
        props = set(re.findall(r'([a-z-]+)\s*:', body))
        assert props <= {'clip-path', 'opacity'}, (name, props)


def test_the_room_opens_from_the_panel_window_without_a_blend():
    block = _door_block()
    # The new room is clipped open from the panel; the lounge holds still.
    assert re.search(r'door-in\)::view-transition-old\(root\)\s*\{\s*animation:\s*none', block)
    assert re.search(r'door-in\)::view-transition-new\(root\)\s*\{\s*animation:\s*door-open', block)
    assert 'inset(var(--door-t) var(--door-r) var(--door-b) var(--door-l) round 14px)' in block
    # The navbar holds still.
    assert re.search(r'::view-transition-group\(ccc-nav\)\s*\{\s*animation:\s*none', block)
    assert re.search(r'::view-transition-old\(ccc-nav\)\s*\{\s*display:\s*none', block)


def test_the_door_keeps_the_lounge_firewall():
    block = _strip_comments(_door_block())
    assert 'var(--game-' not in block
    assert 'gold' not in block


# ── 4. Both ends ─────────────────────────────────────────────────────────

def _login(client, username):
    user = User(username=username, email=f'{username}@test.com')
    user.set_password('pw')
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def test_every_seated_panel_carries_its_door_slug(app, client):
    _login(client, 'doorlounge')
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    links = re.findall(r'<a class="hl-panel-link" href="(/[a-z]+/)" data-door-slug="([a-z]+)">', text)
    assert links == [('/cfb/', 'cfb'), ('/docket/', 'docket')]


def test_the_cfb_room_opens_on_a_masthead_with_its_h1(client):
    text = client.get('/cfb/').get_data(as_text=True)
    assert re.search(r'class="page-hero cfb-hero">.*?<h1>The Survivors</h1>', text, re.S)


def test_the_docket_landings_open_on_a_masthead_with_its_h1():
    for page in ('sheet.html', 'join.html'):
        source = (ROOT / 'games/docket/templates/docket' / page).read_text(encoding='utf-8')
        # door.js takes the first .page-hero and the H1 inside it.
        assert source.count('class="page-hero') == 1, page
        assert re.search(r'<div class="page-hero docket-hero">\s*<div class="container">\s*'
                         r'(?:\{%[^%]*%\}\s*)?<h1', source), page


def test_the_pay_sheet_opens_on_its_league_line(client, golf_leagues):
    text = client.get('/golf/handicap/').get_data(as_text=True)
    line = re.search(r'<p class="golf-context">\s*<span class="golf-context-items">\s*<span[^>]*>([^<]+)</span>',
                     text)
    assert line and line.group(1) == 'Handicap Pay Sheet'
    # The Pay Sheet has no hero band: the door never leaves a dark block in it.
    assert 'page-hero' not in text
