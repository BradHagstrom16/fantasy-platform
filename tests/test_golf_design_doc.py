"""The Pay Sheet's design doctrine (games/golf/DESIGN.md, U0) and its CSS truth.

The per-game doc is loaded INSTEAD of the root DESIGN.md under
``impeccable context --target games/golf``, so it must declare its own
tokens, and the CSS under ``body.game-golf`` must agree with them (the
CFB rule: if doc and CSS disagree, the CSS is the runtime truth, so the
lock keeps them equal). Brad's two rulings from the 2026-10-06 design
consultation are string-locked: "Blue is personal. Green is environmental."
and gold never enters the room.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'games' / 'golf' / 'DESIGN.md'
CSS = ROOT / 'static' / 'css' / 'style.css'

# The doc's frontmatter tokens that the CSS must carry, slot by slot.
GAME_SLOTS = {
    '--game-primary': 'golf-pen',
    '--game-primary-dark': 'golf-pen-pressed',
    '--game-primary-light': 'golf-pen-lift',
    '--game-accent': 'golf-pen',
    '--game-accent-light': 'golf-pen-bright',
}

# The paper rebase: exactly these four platform tokens, nothing else.
REBASED = {
    '--bg-page': 'golf-paper',
    '--surface-card': 'golf-surface',
    '--text-primary': 'golf-ink',
    '--text-secondary': 'golf-pencil',
}


def _frontmatter_colors():
    text = DOC.read_text(encoding='utf-8')
    head = text.split('---', 2)[1]
    colors = {}
    for line in head.splitlines():
        m = re.match(r'\s+(golf-[a-z-]+):\s+"(#[0-9A-Fa-f]{6})"', line)
        if m:
            colors[m.group(1)] = m.group(2).lower()
    return colors


def _golf_body_block():
    css = CSS.read_text(encoding='utf-8')
    m = re.search(r'body\.game-golf\s*\{([^}]*)\}', css)
    assert m, 'style.css has no body.game-golf block'
    return m.group(1)


def _declared(block):
    return {
        k.strip(): v.strip().lower()
        for k, v in re.findall(r'(--[a-z-]+)\s*:\s*([^;]+);', block)
    }


def test_doc_exists_and_extends_the_root():
    text = DOC.read_text(encoding='utf-8')
    assert text.startswith('---\n')
    assert 'extends: ../../DESIGN.md' in text


def test_frontmatter_names_the_pay_sheet_family():
    colors = _frontmatter_colors()
    for name in (*GAME_SLOTS.values(), *REBASED.values(), 'golf-rule',
                 'golf-marker', 'golf-course', 'golf-subnav-black'):
        assert name in colors, name


@pytest.mark.parametrize('slot,name', sorted(GAME_SLOTS.items()))
def test_game_slot_equals_the_doc(slot, name):
    assert _declared(_golf_body_block())[slot] == _frontmatter_colors()[name]


@pytest.mark.parametrize('token,name', sorted(REBASED.items()))
def test_paper_rebase_equals_the_doc(token, name):
    assert _declared(_golf_body_block())[token] == _frontmatter_colors()[name]


def test_the_rebase_is_exactly_four_platform_tokens():
    declared = _declared(_golf_body_block())
    platform = {k for k in declared if not k.startswith('--game-')
                and not k.startswith('--golf-')}
    assert platform == set(REBASED), platform


def test_no_gold_in_the_room():
    block = _golf_body_block()
    assert 'c9a227' not in block.lower()
    assert 'b8993e' not in block.lower()
    assert '--gold' not in block
    doc = DOC.read_text(encoding='utf-8')
    assert 'Gold: platform ceremony only' in doc or 'gold (platform-ceremonial only' in doc


def test_subnav_accent_is_the_pen():
    css = CSS.read_text(encoding='utf-8')
    m = re.search(r'\.subnav-golf\s*\{([^}]*)\}', css)
    assert m
    declared = _declared(m.group(1))
    colors = _frontmatter_colors()
    assert declared['--subnav-accent'] == colors['golf-pen']
    background = re.search(r'background:\s*(#[0-9A-Fa-f]{6})', m.group(1))
    assert background and background.group(1).lower() == colors['golf-subnav-black']


def test_the_rulings_are_in_the_doc():
    doc = DOC.read_text(encoding='utf-8')
    assert 'Blue is personal. Green is environmental.' in doc
    assert '**Accent rank:**' in doc
    assert 'Pick a golfer. Bank their earnings. Spend them once.' in doc
