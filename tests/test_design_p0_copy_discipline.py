"""P0 S0.3 — lock: no em-dashes (—) or `&mdash;` / `&#8212;` entities in
user-facing template copy.

PRODUCT.md "Copy Discipline" + DESIGN.md "Don't" list both ban em-dashes
in UI prose, button labels, error messages, and any rendered copy. Comments
(Jinja `{# ... #}`, HTML `<!-- ... -->`) are exempt — comments aren't
shipped to users; stripping them keeps the test focused on the policy.

The test strips multi-line comment spans before scanning, so a comment that
mentions an em-dash on a line that doesn't start with `{#` does not flag.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

# In-scope template directories per the P0 cross-cutting plan. Admin
# templates are explicitly out-of-scope for the impeccable design project.
TEMPLATE_DIRS = [
    ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup',
    ROOT / 'core' / 'main' / 'templates' / 'main',
    ROOT / 'core' / 'auth' / 'templates' / 'auth',
    ROOT / 'templates',
]

# Tokens that trigger the lock. en-dash (–) is allowed for numeric ranges
# and stays out of this list; em-dash and the matching HTML entities do not.
EMDASH_PATTERNS = ('—', '&mdash;', '&#8212;')

JINJA_COMMENT = re.compile(r'\{#.*?#\}', re.DOTALL)
HTML_COMMENT = re.compile(r'<!--.*?-->', re.DOTALL)
# JS/CSS line-comment: any line whose first non-space chars are `//`. Stripped
# because in-script source comments aren't user-rendered copy. Block comments
# `/* ... */` follow the same logic.
JS_LINE_COMMENT = re.compile(r'(?m)^\s*//.*$')
BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)


def _strip_comments(src: str) -> str:
    """Remove all Jinja `{# ... #}`, HTML `<!-- ... -->`, JS line comments
    (`//...`), and JS/CSS block comments (`/* ... */`).

    Multi-line comments are handled — `re.DOTALL` makes `.` cross newlines.
    Replacing with a single newline preserves line numbering for offender
    reporting; the policy only cares about presence/absence after stripping,
    not original line numbers.
    """
    src = JINJA_COMMENT.sub('\n', src)
    src = HTML_COMMENT.sub('\n', src)
    src = BLOCK_COMMENT.sub('\n', src)
    src = JS_LINE_COMMENT.sub('', src)
    return src


def _iter_in_scope_templates():
    for tdir in TEMPLATE_DIRS:
        if not tdir.exists():
            continue
        for path in tdir.rglob('*.html'):
            if 'admin' in path.parts:
                continue
            yield path


def test_no_em_dash_in_user_facing_template_copy():
    """No `—`, `&mdash;`, or `&#8212;` in any user-facing template line.

    Comments are stripped first; only rendered copy is scanned.
    """
    offenders = []
    for path in _iter_in_scope_templates():
        stripped = _strip_comments(path.read_text())
        for i, line in enumerate(stripped.splitlines(), start=1):
            if any(token in line for token in EMDASH_PATTERNS):
                # Trim the snippet for the failure message
                offenders.append((str(path.relative_to(ROOT)), i, line.strip()[:140]))
    assert not offenders, (
        f'Em-dash discipline violations ({len(offenders)} total). '
        f'First 20:\n' + '\n'.join(f'  {p}:{ln}: {snip}' for p, ln, snip in offenders[:20])
    )
