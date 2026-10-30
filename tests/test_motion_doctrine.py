"""The platform motion doctrine (DESIGN.md §4.5, ADR-076, Brad 2026-10-29).

Five locks:

1. **No curve overshoots.** No `cubic-bezier()` in the stylesheets has a y
   value above 1 or below 0 (the card hover's `.34, 1.56, .64, 1` was the last;
   impeccable bans bounce and elastic easing), and the detector carries no
   whitelist for one.
2. **Reduced motion keeps the confirmation.** The shared `fade-in` animates
   opacity only, and every animation a reduced-motion block names is free of
   `transform`: the spatial part drops, the fade that says "it landed" stays.
3. **A reduced-motion rule wins the cascade.** A rule inside
   `@media (prefers-reduced-motion: reduce)` has no more specificity than the
   rule it overrides, so a later rule with the same selector silently beats
   it. Until 2026-10-29 the platform `.animate-in` guard sat above
   `.animate-in` and did nothing.
4. **The gaps stay closed.** The page hero, the CFB champion's hero, the auth
   card, the navbar menu and the flash alert each have a reduced-motion path.
5. **A card lifts only when it is a door.** `.card:hover` moves nothing; a
   linked card (`a.card`) still lifts.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLE = (ROOT / 'static/css/style.css').read_text(encoding='utf-8')
TOKENS = (ROOT / 'static/css/tokens.css').read_text(encoding='utf-8')
REDUCED = 'prefers-reduced-motion'


def _rules(css: str):
    """Every leaf rule as (enclosing at-rule preludes, selector prelude, body,
    offset). Comments are blanked first so offsets stay true."""
    css = re.sub(r'/\*.*?\*/', lambda m: ' ' * len(m.group()), css, flags=re.S)
    rules, stack, start = [], [], 0
    for i, ch in enumerate(css):
        if ch == '{':
            stack.append((css[start:i].rsplit(';', 1)[-1].strip(), i))
            start = i + 1
        elif ch == '}':
            prelude, opened = stack.pop()
            body = css[opened + 1:i]
            if '{' not in body:
                rules.append((tuple(p for p, _ in stack), prelude, body, opened))
            start = i + 1
    return rules


RULES = _rules(STYLE)


def _in_reduced(context) -> bool:
    # `reduce`, not `no-preference`: The Door's opt-in sits under the latter.
    return any(re.search(REDUCED + r'\s*:\s*reduce', p) for p in context)


def _selectors(prelude: str) -> set[str]:
    return {re.sub(r'\s+', ' ', s.strip()) for s in prelude.split(',') if s.strip()}


def _keyframes() -> dict[str, str]:
    frames: dict[str, str] = {}
    for context, _prelude, body, _pos in RULES:
        for at in context:
            m = re.match(r'@keyframes\s+([\w-]+)', at)
            if m:
                frames[m.group(1)] = frames.get(m.group(1), '') + body
    return frames


# ── 1. No overshoot ──────────────────────────────────────────────────────

def test_no_curve_overshoots():
    for name, css in (('style.css', STYLE), ('tokens.css', TOKENS)):
        for args in re.findall(r'cubic-bezier\(([^)]*)\)', css):
            if 'var(' in args:
                continue
            _x1, y1, _x2, y2 = (float(v) for v in args.split(','))
            assert 0 <= y1 <= 1 and 0 <= y2 <= 1, (
                f'{name}: cubic-bezier({args}) overshoots; the platform eases out '
                'with var(--ease-out) and never bounces (DESIGN.md §4.5, ADR-076)')


def test_detector_whitelists_no_bounce():
    config = json.loads((ROOT / '.impeccable/config.json').read_text(encoding='utf-8'))
    ignored = config['detector'].get('ignoreValues', [])
    assert not [v for v in ignored if v['rule'] == 'bounce-easing']


def test_motion_tokens_exist():
    assert re.search(r'--ease-out:\s*cubic-bezier\(\.16,\s*1,\s*\.3,\s*1\)', TOKENS)
    assert re.search(r'--motion-feedback:\s*150ms', TOKENS)


# ── 2. Reduced motion keeps the confirmation ─────────────────────────────

def test_fade_in_animates_opacity_only():
    body = _keyframes()['fade-in']
    props = set(re.findall(r'([a-z-]+)\s*:', body))
    assert props == {'opacity'}


def test_reduced_motion_names_no_spatial_keyframe():
    frames = _keyframes()
    for context, prelude, body, _pos in RULES:
        if not _in_reduced(context):
            continue
        for value in re.findall(r'(?:^|;)\s*animation(?:-name)?\s*:([^;]*)', body):
            for name in re.findall(r'[\w-]+', value):
                if name in frames:
                    assert 'transform' not in frames[name], (
                        f'{prelude}: reduced motion runs @keyframes {name}, which '
                        'moves; keep the opacity-only fade-in instead (ADR-076)')


# ── 3. Every reduced-motion rule wins the cascade ────────────────────────

SHORTHANDS = {'animation': r'animation(?:-name)?', 'transition': r'transition(?:-property)?'}


def _sets(body: str, family: str) -> bool:
    return bool(re.search(r'(?:^|;)\s*' + SHORTHANDS[family] + r'\s*:', body))


def test_no_later_rule_overrides_a_reduced_motion_rule():
    losers = []
    for index, (context, prelude, body, _pos) in enumerate(RULES):
        if not _in_reduced(context):
            continue
        for family in SHORTHANDS:
            if not _sets(body, family):
                continue
            mine = _selectors(prelude)
            for later_ctx, later_prelude, later_body, _ in RULES[index + 1:]:
                if (not _in_reduced(later_ctx) and not any('@keyframes' in c for c in later_ctx)
                        and mine & _selectors(later_prelude) and _sets(later_body, family)):
                    losers.append(f'{sorted(mine & _selectors(later_prelude))} ({family})')
    assert not losers, (
        'A reduced-motion override sits above a rule with the same selector, '
        f'which wins the cascade; move the override below it: {losers}')


def test_the_cascade_lock_bites():
    rules = _rules('@media (prefers-reduced-motion: reduce) { .a { animation: none; } }\n'
                   '.a { animation: rise .2s; }')
    assert len(rules) == 2 and _in_reduced(rules[0][0]) and not _in_reduced(rules[1][0])


# ── 4. The gaps stay closed ──────────────────────────────────────────────

def _reduced_animation_for(selector: str) -> str | None:
    for context, prelude, body, _pos in RULES:
        if _in_reduced(context) and selector in _selectors(prelude):
            m = re.search(r'(?:^|;)\s*animation\s*:([^;]*)', body)
            if m:
                return m.group(1).strip()
    return None


def test_unguarded_entrances_now_have_a_reduced_path():
    for selector in ('.page-hero h1', '.page-hero .lead', '.auth-card',
                     '.championship-hero .champion-name',
                     '.championship-hero .champion-subtitle',
                     '.championship-hero .prize-badge',
                     '.animate-in', '.animate-in-scale'):
        assert _reduced_animation_for(selector) == 'none', selector


def test_answering_surfaces_fade_under_reduced_motion():
    for selector in ('.navbar .dropdown-menu', '.alert',
                     '.alert.alert-success.alert-dismissible',
                     'html[data-app-state="subscribed"] .app-panel[data-state="subscribed"]'):
        value = _reduced_animation_for(selector)
        assert value and value.startswith('fade-in'), selector


# ── 5. A card lifts only when it is a door ───────────────────────────────

def test_a_content_card_does_not_lift():
    for context, prelude, body, _pos in RULES:
        if '.card:hover' in _selectors(prelude) and not _in_reduced(context):
            assert 'transform' not in body or re.search(r'transform:\s*none', body), prelude
    assert not any('.stat-block:hover' in _selectors(p) and 'translate' in b
                   for _c, p, b, _ in RULES)


def test_a_linked_card_still_lifts():
    lifts = [b for c, p, b, _ in RULES
             if 'a.card:hover' in _selectors(p) and not _in_reduced(c)]
    assert any('translateY(-2px)' in b for b in lifts)
