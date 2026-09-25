"""Every stylesheet closes each block it opens.

A lost ``}`` is silent in the browser: the rules after it nest inside the
still-open block and apply only under its condition. PR #240's Brief CSS
landed inside The Tribune's phone ``@media`` that way, so The Brief went
unstyled at desktop width while every other test stayed green.
"""
import re
from pathlib import Path

import pytest

CSS_DIR = Path(__file__).resolve().parent.parent / 'static' / 'css'


@pytest.mark.parametrize('sheet', sorted(p.name for p in CSS_DIR.glob('*.css')))
def test_braces_balance(sheet):
    text = (CSS_DIR / sheet).read_text()
    text = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group().count('\n'), text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', '""', text)
    opened = []
    for line_no, line in enumerate(text.split('\n'), 1):
        for char in line:
            if char == '{':
                opened.append(line_no)
            elif char == '}':
                assert opened, f'{sheet}:{line_no}: a "}}" closes nothing'
                opened.pop()
    assert not opened, f'{sheet}: block opened at line {opened[-1]} is never closed'
