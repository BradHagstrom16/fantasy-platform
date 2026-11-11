"""The Door: the walk from a lounge headliner panel into its room (ADR-077,
amended by ADR-079; DESIGN.md §4.5; Brad 2026-10-29 and 2026-11-11).

One cross-document view transition, and it is a pair of doors. A tap draws a
seam down the middle of the panel; the doors part from it until the doorway
is the panel, then the doorway grows to the screen while the lounge dims and
falls back. The room is a clip-path window (never an opacity blend, so the
dark lounge and a light room never mix) and nothing inside it moves. Back is
the same film run backwards. static/js/door.js scopes it: only the lounge and
a page of the panel's own game ever transition; every other navigation is a
plain load.

Locks:
1. The opt-in exists only with script and without reduced motion, so a
   no-JS or reduced-motion member never gets a transition at all.
2. door.js loads render-blocking in <head> (pagereveal must be registered
   before the first render), versioned, stands every non-door navigation
   down, names no element, and hands the stylesheet the doorway.
3. The latch: a plain tap draws the seam at once and it never sticks.
4. Every door rule waits for its door-in / door-out type; the keyframes move
   only clip-path, transform and opacity; the way out is the way in
   reversed; the lounge firewall holds.
5. Both ends carry what the script looks for: a door slug on every seated
   panel, a masthead on every room page the lounge links to.
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
    # DESIGN.md §4.5: the way in is an authored entrance (500-800ms), the way
    # out a view transition (300-500ms); exits run faster.
    assert 500 <= door_in <= 800
    assert 300 <= door_out <= 500
    assert door_out < door_in


def test_door_runs_on_its_own_curves():
    # --ease-out front-loads the travel (95% in the first 43% of the time),
    # which made the door read as a cut; the walk through eases on --ease-door.
    assert re.search(r'--ease-door:\s*cubic-bezier\(\.33,\s*1,\s*\.68,\s*1\)', TOKENS)
    block = _strip_comments(_door_block())
    assert 'var(--ease-out)' not in block
    assert 'var(--ease-door)' in block and 'var(--ease-door-part)' in block


def test_the_doors_part_on_a_soft_start():
    # The arriving page drops its first frames on its own start-up (measured
    # 2026-11-11: 50-100ms frames in the first ~110ms, then a steady 60fps).
    # A curve that leaves at speed spends its biggest jump on those frames,
    # so the parting beat leaves from rest (y1 = 0) and never overshoots.
    x1, y1, x2, y2 = map(float, re.search(
        r'--ease-door-part:\s*cubic-bezier\(([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)\)', TOKENS).groups())
    assert y1 == 0 and x1 > 0
    assert 0 <= y2 <= 1


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
    # Lounge <-> room only: the lounge is "/", a room is a game-<slug> body
    # that opens on a masthead.
    assert "location.pathname === '/'" in DOOR_JS
    assert 'game-' in DOOR_JS and 'data-door-slug' in DOOR_JS
    assert '.page-hero' in DOOR_JS and '.golf-context' in DOOR_JS
    # A panel offscreen has no doorway to open from.
    assert 'function inView' in DOOR_JS


def test_door_js_names_no_element():
    # ADR-079: nothing in the room moves, so no element is lifted into its own
    # group. The masthead and name morphs of the first build flew on their own
    # paths, out of step with the doorway. The navbar is pinned by CSS.
    assert 'viewTransitionName' not in DOOR_JS
    assert "types.add('door-in')" in DOOR_JS and "types.add('door-out')" in DOOR_JS
    names = set(re.findall(r'view-transition-name:\s*([\w-]+)', _strip_comments(_door_block())))
    assert names == {'ccc-nav'}


def test_door_js_hands_over_the_doorway():
    # The stylesheet reads exactly these: the doorway, the seam down its
    # middle, the point the lounge falls back from, the navbar's lower edge.
    handed = set(re.findall(r"setProperty\('(--door-[a-z]+)'", DOOR_JS))
    assert handed == {'--door-t', '--door-r', '--door-b', '--door-l',
                      '--door-sl', '--door-sr', '--door-cx', '--door-cy', '--door-nav'}
    used = set(re.findall(r'var\((--door-[a-z]+)\)', _strip_comments(_door_block())))
    assert used - {'--door-in', '--door-out'} == handed


def test_back_puts_the_lounge_scroll_back_before_it_looks_for_the_panel():
    # A signed-in lounge is no-store, so Back reloads it, and it reveals at
    # the top before the browser restores the scroll: the second panel on a
    # phone was out of sight and the door out never ran.
    assert 'stashScroll(window.scrollY)' in DOOR_JS
    out = DOOR_JS[DOOR_JS.index('// Lounge side of the door out'):]
    assert "navigationType === 'traverse'" in out
    assert out.index('restoreScroll()') < out.index('getBoundingClientRect()')


def test_the_door_is_the_arriving_pages_entrance():
    # The page's own load-in is finished before the first frame, on both
    # sides; a loop and a terminal moment are left alone.
    body = DOOR_JS[DOOR_JS.index('function settle'):DOOR_JS.index('// The latch.')]
    assert 'a.finish()' in body
    assert 'iterations === Infinity' in body and "closest('[data-moment], [role=\"alert\"]')" in body
    assert '::view-transition' in body
    reveal = DOOR_JS[DOOR_JS.index("addEventListener('pagereveal'"):]
    assert reveal.count('settle()') == 2


# ── 3. The latch ─────────────────────────────────────────────────────────

def test_a_tap_unlatches_the_panel():
    click = DOOR_JS[DOOR_JS.index("addEventListener('click'"):DOOR_JS.index("addEventListener('pageshow'")]
    # A plain click only: a new tab, a modified click or a handled one is not
    # a walk through the door.
    for guard in ('e.defaultPrevented', 'e.button !== 0', 'e.metaKey', 'e.ctrlKey',
                  'e.shiftKey', 'e.altKey', "'_blank'", 'location.origin'):
        assert guard in click, guard
    assert "location.pathname !== '/'" in click and 'inView(' in click
    assert "var LATCH = 'is-unlatched'" in DOOR_JS
    # It never sticks: a timeout, pageshow (a plain Back), and the door out
    # when it lands all let go.
    assert 'setTimeout(unlatch' in click
    assert re.search(r"addEventListener\('pageshow',\s*function \(\) \{\s*if \(!closing\) unlatch\(\);", DOOR_JS)
    assert 't.finished.then(landed, landed)' in DOOR_JS


def test_the_seam_is_the_panels_accent_and_keeps_its_confirmation():
    css = _strip_comments(STYLE)
    seam = re.search(r'\.home-shell \.hl-panel::after \{([^}]*)\}', css).group(1)
    assert 'var(--hl-accent-bright' in seam and 'pointer-events: none' in seam
    assert 'opacity: 0' in seam
    drawn = css.index('.home-shell .hl-panel.is-unlatched::after {')
    # Reduced motion: the draw stops, the seam still appears (opacity), and
    # the override sits below the rule it overrides.
    guard = css.index('@media (prefers-reduced-motion: reduce)', drawn)
    override = css[guard:css.index('.home-shell .hl-panel-head {', guard)]
    assert '.home-shell .hl-panel.is-unlatched::after' in override
    assert 'transform: none' in override
    assert 'transition: opacity var(--motion-feedback)' in override


def test_the_chevron_stays_put_under_reduced_motion():
    # The latch and a hover both step the chevron forward; under reduced
    # motion neither moves it (DESIGN.md §4.5), each at the specificity of the
    # rule it overrides and below it.
    css = _strip_comments(STYLE)
    steps = [
        '.home-shell .hl-panel.is-unlatched .hl-panel-chev',
        '.home-shell .hl-panel-link:hover .hl-panel-chev',
        '.home-shell .hl-panel-link:focus-visible .hl-panel-chev',
    ]
    last = max(css.index(s) for s in steps)
    guard = css.index('@media (prefers-reduced-motion: reduce)', last)
    override = css[guard:css.index('.home-shell .hl-panel-mark', guard)]
    for s in steps:
        assert s in override, s
    assert 'transform: none' in override


# ── 4. The moment ────────────────────────────────────────────────────────

def test_every_door_rule_waits_for_its_type():
    block = _strip_comments(_door_block())
    for prelude in re.findall(r'([^{}]+)\{[^{}]*\}', block):
        prelude = prelude.strip()
        if not prelude or prelude.startswith(('@', 'from', 'to')):
            continue
        for selector in _top_level_split(prelude):
            assert ':active-view-transition-type(door-' in selector, selector


def test_the_keyframes_move_only_clip_transform_and_opacity():
    block = _strip_comments(_door_block())
    assert set(re.findall(r'@keyframes ([\w-]+)', block)) == {'door-part', 'door-walk', 'door-recede'}
    for name in ('door-part', 'door-walk', 'door-recede'):
        props = set(re.findall(r'([a-z-]+)\s*:', _keyframes_body(name)))
        assert props <= {'clip-path', 'transform', 'opacity'}, (name, props)
    # A keyframe's own timing function drops a var(), so each beat is its own
    # animation and takes its curve from the shorthand.
    assert 'animation-timing-function' not in block


def test_the_doors_part_from_the_seam_then_the_room_is_walked_into():
    block = _strip_comments(_door_block())
    seam = 'inset(var(--door-t) var(--door-sr) var(--door-b) var(--door-sl) round 14px)'
    doorway = 'inset(var(--door-t) var(--door-r) var(--door-b) var(--door-l) round 14px)'
    part, walk = _keyframes_body('door-part'), _keyframes_body('door-walk')
    assert part.index(seam) < part.index(doorway)
    assert walk.index(doorway) < walk.index('inset(var(--door-nav) 0 0 0 round 0)')
    # In: part, then walk, one after the other inside --door-in.
    assert re.search(
        r'door-in\)::view-transition-new\(root\)\s*\{\s*animation:\s*'
        r'door-part calc\(var\(--door-in\) \* \.4\) var\(--ease-door-part\) both,\s*'
        r'door-walk calc\(var\(--door-in\) \* \.6\) var\(--ease-door\) calc\(var\(--door-in\) \* \.4\) forwards', block)


def test_the_way_out_is_the_same_film_backwards():
    block = _strip_comments(_door_block())
    # The same keyframes and curves under animation-direction: reverse (which
    # runs a curve backwards too), walk first, then the doors shut.
    assert re.search(
        r'door-out\)::view-transition-old\(root\)\s*\{\s*z-index:\s*1;\s*animation:\s*'
        r'door-walk calc\(var\(--door-out\) \* \.6\) var\(--ease-door\) reverse both,\s*'
        r'door-part calc\(var\(--door-out\) \* \.4\) var\(--ease-door-part\) calc\(var\(--door-out\) \* \.6\) reverse forwards',
        block)
    assert re.search(r'door-out\)::view-transition-new\(root\)\s*\{[^}]*'
                     r'animation:\s*door-recede var\(--door-out\) var\(--ease-door\) reverse both', block)


def test_the_lounge_falls_back_and_never_blends_with_the_room():
    block = _strip_comments(_door_block())
    assert re.search(r'door-in\)::view-transition-old\(root\)\s*\{[^}]*'
                     r'animation:\s*door-recede var\(--door-in\) var\(--ease-door\) both', block)
    # It dims over the club's own dark, never over the arriving room's ground,
    # and the two pages are laid over each other, never added together.
    assert re.search(r'::view-transition\s*\{\s*background:\s*var\(--ink\)', block)
    assert 'mix-blend-mode: normal' in block
    recede = _keyframes_body('door-recede')
    scale = float(re.search(r'scale\(([\d.]+)\)', recede).group(1))
    opacity = float(re.search(r'opacity:\s*([\d.]+)', recede).group(1))
    assert 0.9 <= scale < 1 and 0.4 <= opacity < 1
    # The room is only ever a clip window: no opacity on its keyframes.
    assert 'opacity' not in _keyframes_body('door-part') + _keyframes_body('door-walk')
    # The navbar holds still.
    assert re.search(r'::view-transition-group\(ccc-nav\)\s*\{\s*animation:\s*none', block)
    assert re.search(r'::view-transition-old\(ccc-nav\)\s*\{\s*display:\s*none', block)


def test_the_door_keeps_the_lounge_firewall():
    block = _strip_comments(_door_block())
    assert 'var(--game-' not in block
    assert 'gold' not in block


# ── 5. Both ends ─────────────────────────────────────────────────────────

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
