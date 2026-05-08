"""P0 S0.1 — lock: every CCC card class carries brand-tinted shadow, never neutral gray.

DESIGN.md "Press-Room Shadow Rule" (section 4):
    All shadows tint with brand purple (or gold on CTA-hover). Neutral-gray
    shadows are slop and break the press-room atmosphere. Never use
    `rgba(0, 0, 0, ...)` directly; always tint toward `rgba(58, 29, 114, ...)`
    or `rgba(201, 162, 39, ...)`.

This file scans `static/css/style.css` for two violations:
  1. Any `box-shadow` line that declares a neutral `rgba(0, 0, 0, ...)` value.
  2. Absence of the brand-tinted `--shadow-sm`/`--shadow-md` token references
     anywhere in the file (proving the brand scale is in active use).
"""
from pathlib import Path

CSS_PATH = Path(__file__).parent.parent / 'static' / 'css' / 'style.css'


def test_no_neutral_gray_box_shadow_in_card_rules():
    """No line in style.css may declare a `box-shadow` with neutral-gray
    `rgba(0, 0, 0, ...)`. All shadows route through the brand-tinted scale.

    The `.card.wc-card` background is `rgba(0, 17, 46, ...)` (navy fill, not a
    shadow) so we explicitly skip lines that use the navy triplet.
    """
    src = CSS_PATH.read_text()
    offenders = []
    for line_no, line in enumerate(src.splitlines(), start=1):
        if 'box-shadow' not in line:
            continue
        # Skip the navy card-fill triplet so a future refactor that inlines
        # background+shadow on one line doesn't trip this lock.
        if 'rgba(0, 17' in line or 'rgba(0,17' in line:
            continue
        if 'rgba(0, 0, 0' in line or 'rgba(0,0,0' in line:
            offenders.append((line_no, line.strip()))
    assert not offenders, f"Neutral-gray box-shadows found: {offenders}"


def test_brand_shadow_tokens_referenced():
    """The brand-tinted `--shadow-*` scale must be in active use somewhere
    in style.css, proving the tokens defined in tokens.css have consumers."""
    src = CSS_PATH.read_text()
    assert (
        'var(--shadow-sm)' in src
        or 'var(--shadow-md)' in src
        or 'var(--shadow-lg)' in src
    ), "Brand shadow tokens (--shadow-sm/md/lg) must be referenced in style.css"


def test_no_bootstrap_shadow_utility_on_ccc_cards_in_templates():
    """In-scope templates (World Cup + auth + core/main) must not apply
    Bootstrap's `shadow-sm`/`shadow-lg`/`shadow` utility class on an element
    that already carries `card`, `card.wc-card`, `game-card`, `auth-card`, or
    `leaderboard-card`. The brand-tinted scoped CSS rule supplies the shadow.

    Admin templates are explicitly out of scope per the impeccable plan §1.6
    and are not scanned.
    """
    repo_root = Path(__file__).parent.parent
    in_scope_dirs = [
        repo_root / 'games' / 'worldcup' / 'templates',
        repo_root / 'core' / 'auth' / 'templates',
        repo_root / 'core' / 'main' / 'templates',
        repo_root / 'templates',
    ]
    offenders = []
    for d in in_scope_dirs:
        if not d.exists():
            continue
        for path in d.rglob('*.html'):
            text = path.read_text()
            for line_no, line in enumerate(text.splitlines(), start=1):
                # Only scrutinise lines that look like a class attribute on an
                # element carrying one of the CCC card classes.
                if 'class=' not in line:
                    continue
                has_card_class = (
                    'card' in line
                    or 'auth-card' in line
                    or 'leaderboard-card' in line
                    or 'game-card' in line
                )
                if not has_card_class:
                    continue
                # Match `shadow-sm`, `shadow-lg`, or bare `shadow` as a class
                # token (whitespace or quote on either side).
                tokens = line.split()
                for tok in tokens:
                    cleaned = tok.strip('"\'>=')
                    if cleaned in ('shadow', 'shadow-sm', 'shadow-lg'):
                        offenders.append((str(path.relative_to(repo_root)), line_no, line.strip()))
                        break
    assert not offenders, (
        "Bootstrap shadow utilities found on CCC card elements (strip them; "
        f"scoped CSS supplies brand-tinted shadows): {offenders}"
    )
