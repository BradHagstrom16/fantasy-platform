"""WC Tab Unification - Phase 4 (SCHEDULE light polish) regression locks.

P4 aligns schedule.html typography + spacing against the locked Stats reference
without changing the substrate. Three CSS edits ship in style.css:

- `.schedule-day-header.is-today` color: `var(--purple-700)` -> `var(--wc-red)`.
  Closes an accent-rank-doctrine miss; the adjacent `.schedule-today-badge` is
  already `--wc-red`. Purple is CCC platform chrome per DESIGN.md section 2 and
  does not belong on a WC body surface scoped under `body.game-worldcup`.

- `.schedule-legend` font-size: `.85rem` -> `.95rem`. Matches the Stats
  reference panel-supporting paragraph rhythm (stats.html line 108).

- `body.game-worldcup .section-heading { font-size: 1.75rem; }` is added as a
  new WC-scoped lift on top of the platform `.section-heading` (1.6rem). The
  platform default is untouched so CFB's h3/h4/h5 consumers of `.section-heading`
  in `games/cfb/templates/cfb/*.html` are not affected. Matches the Stats
  reference panel H2 (stats.html line 107).

These tests pin each edit. Regex idioms inherit the P3 / P3.5 hardening:
- CSS scans use `^...` start-of-line anchoring with `re.MULTILINE` so substring
  matches inside larger composite rules cannot false-pass.
- Property scans use `(?<![-\\w])` negative lookbehind to avoid catching
  longer property names that end in the same suffix.
- Forbidden-rule patterns terminate with `\\s*[,{]` so a selector listed in a
  comma group still trips the assertion.
"""
from pathlib import Path
import re


ROOT = Path(__file__).parent.parent
CSS_PATH = ROOT / 'static' / 'css' / 'style.css'

CSS = CSS_PATH.read_text()


# ---------------------------------------------------------------------------
# PI-1: .schedule-day-header.is-today uses var(--wc-red), not --purple-*.
# ---------------------------------------------------------------------------

def test_schedule_day_header_is_today_uses_wc_red():
    """`.schedule-day-header.is-today` paints in `--wc-red` post-P4. The prior
    `--purple-700` was a stale platform-chrome token leaking into the WC body
    surface; the adjacent `.schedule-today-badge` already uses `--wc-red`, so
    the header color now agrees with the badge.

    Asserts two invariants on the rule block:
    1. The block contains `color: var(--wc-red)` (the affirmative lock).
    2. The block does NOT contain any `--purple-` token (the negative lock —
       a future regression that lifted the badge back to purple would be
       caught even if it picked a different shade like `--purple-800`).
    """
    pattern = re.compile(
        r'^\.schedule-day-header\.is-today\s*\{([^}]*)\}',
        re.MULTILINE,
    )
    match = pattern.search(CSS)
    assert match is not None, (
        '`.schedule-day-header.is-today { ... }` rule block not found in '
        'style.css. P4 expects this rule to exist with `color: var(--wc-red)`.'
    )
    block = match.group(1)

    assert re.search(r'(?<![-\w])color:\s*var\(\s*--wc-red\s*\)', block), (
        'P4 PI-1: `.schedule-day-header.is-today` must paint `color: '
        'var(--wc-red)`. The accent rank doctrine on WC body surfaces is '
        'red -> white -> navy -> gold (quaternary); purple is platform '
        'chrome and does not belong on a WC-scoped highlight.'
    )

    assert '--purple-' not in block, (
        'P4 PI-1: `.schedule-day-header.is-today` rule block contains a '
        '`--purple-*` token. Purple is CCC platform chrome (DESIGN.md '
        'section 2); WC body surfaces use the navy/red/white/gold-quaternary '
        'accent vocabulary. Rewrite to `--wc-red` or another WC-palette token.'
    )


# ---------------------------------------------------------------------------
# PI-2: .schedule-legend font-size is .95rem.
# ---------------------------------------------------------------------------

def test_schedule_legend_font_size_matches_stats_rhythm():
    """`.schedule-legend` font-size is `.95rem` post-P4 (was `.85rem`). The
    bump aligns with the Stats reference's panel-supporting paragraph rhythm
    on stats.html line 108 (`font-size:.95rem`).

    Accepts both `.95rem` and `0.95rem` (CSS treats them as equivalent and
    the codebase uses the leading-dot form elsewhere; the test should not
    reject either).
    """
    pattern = re.compile(
        r'^\.schedule-legend\s*\{([^}]*)\}',
        re.MULTILINE,
    )
    match = pattern.search(CSS)
    assert match is not None, (
        '`.schedule-legend { ... }` rule block not found in style.css. P4 '
        'expects this rule to exist with `font-size: .95rem`.'
    )
    block = match.group(1)

    assert re.search(r'(?<![-\w])font-size:\s*0?\.95rem\b', block), (
        'P4 PI-2: `.schedule-legend` must declare `font-size: .95rem` '
        '(or `0.95rem`). Aligns with the Stats reference panel-supporting '
        'paragraph rhythm at stats.html line 108. A regression back to '
        '`.85rem` would reintroduce the typography gap that P4 closed.'
    )


# ---------------------------------------------------------------------------
# PI-3: body.game-worldcup .section-heading lifts font-size to 1.75rem.
# ---------------------------------------------------------------------------

def test_wc_scoped_section_heading_lift_exists():
    """A new WC-scoped lift on `.section-heading` ships in P4 to align with
    the Stats reference panel H2 (stats.html line 107, `font-size:1.75rem`).
    Scoped via `body.game-worldcup .section-heading` so CFB's consumers of
    `.section-heading` at h3/h4/h5 levels (cfb/index.html, cfb/pick.html,
    cfb/my_picks.html) are NOT lifted - a global bump would balloon the
    CFB heading hierarchy.

    Asserts the rule exists at start-of-line (anchored per P3 CR R3-R4
    idiom) and carries `font-size: 1.75rem` in its block.
    """
    pattern = re.compile(
        r'^body\.game-worldcup\s+\.section-heading\s*\{([^}]*)\}',
        re.MULTILINE,
    )
    match = pattern.search(CSS)
    assert match is not None, (
        'P4 PI-3: expected a `body.game-worldcup .section-heading { ... }` '
        'rule lifting `.section-heading` to 1.75rem on WC pages. The plain '
        '`.section-heading` rule alone (1.6rem) leaves the schedule panel-H2 '
        'one rhythm step under the Stats reference.'
    )
    block = match.group(1)

    assert re.search(r'(?<![-\w])font-size:\s*1\.75rem\b', block), (
        'P4 PI-3: `body.game-worldcup .section-heading` exists but does not '
        'declare `font-size: 1.75rem`. The lift is the entire point of the '
        'rule - any other value reverts the schedule panel-H2 away from the '
        'Stats reference rhythm.'
    )


# ---------------------------------------------------------------------------
# PI-4: The base .section-heading rule keeps its 1.6rem platform default.
# ---------------------------------------------------------------------------

def test_base_section_heading_stays_at_platform_default():
    """The unscoped `.section-heading` rule must keep `font-size: 1.6rem` so
    CFB consumers (`cfb/index.html` h3, `cfb/pick.html` h4 + h5,
    `cfb/my_picks.html` h5) are not lifted by P4. A future commit that
    globalises the lift by editing the base rule instead of the WC-scoped
    sibling would balloon CFB headings; this assertion catches that.
    """
    pattern = re.compile(
        r'^\.section-heading\s*\{([^}]*)\}',
        re.MULTILINE,
    )
    match = pattern.search(CSS)
    assert match is not None, (
        'Base `.section-heading { ... }` platform rule not found in '
        'style.css. CFB templates depend on it at h3/h4/h5 levels.'
    )
    block = match.group(1)

    assert re.search(r'(?<![-\w])font-size:\s*1\.6rem\b', block), (
        'P4 PI-4: base `.section-heading` font-size shifted off 1.6rem. The '
        'WC lift is scoped via `body.game-worldcup .section-heading` (PI-3); '
        'the base rule must remain the platform default so CFB consumers '
        '(cfb/index.html, cfb/pick.html, cfb/my_picks.html) stay unaffected. '
        'If the platform default genuinely needs to change, do it in a '
        'separate PR with CFB visual smoke.'
    )
