"""CFB weekly results / "Saturday's Verdict" locks (A4).

A2.0 stood up the dark substrate, A2 elevated the hub, A3 the pick flow; A4
brings the weekly consequence surface (games/cfb/templates/cfb/weekly_results.html
-- route cfb.weekly_results, /cfb/results) to the games/cfb/DESIGN.md bar. These
locks encode the contracts A4 changes via the established CSS-scan idioms
(anchored regex over style.css + the template). Each fails on the pre-A4 state
and passes once A4 lands:

  - .elimination-alert is MIGRATED off the side-stripe (the old
    `border-left: 4px solid var(--cfb-lost-life)`, a platform absolute ban) to a
    full-container cold treatment: full border + restrained lost-red tint + a
    bone-white title with a leading icon (the named A2/migration debt, S4 +
    the Cold-Elimination Rule)
  - the H1 carries the Survivor voice ("Saturday's Verdict" / "The Cut"), never
    the flat "... Results" route label (S3)
  - survivor-state is coded by structure + label, never color alone: the new
    .badge-pending is a HOLLOW (transparent + outline) chip, distinct from the
    FILLED survived/lost chips (S5); off-palette Bootstrap yellow / crimson data
    chips are gone (S2 Crimson-Is-Identity + survivor-state palette)
  - the current-user row carries the structural .cfb-you-tag, not a tint alone
  - the week verdict is one editorial summary line, not the four-up .stat-block
    hero-metric grid (a platform absolute ban)
  - the field ledger folds Opponent + Score into the Pick cell (five columns,
    compact survivor-state columns) so alive-status stays on-screen at mobile
    width (S6 -- survivor sessions skew mobile)
  - the named em-dash / double-hyphen copy debt is gone (S3 no-em-dash rule)

ASCII-only per the CFB phase rule; non-ASCII glyphs referenced via escapes.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static" / "css" / "style.css").read_text()
TPL = (ROOT / "games" / "cfb" / "templates" / "cfb" / "weekly_results.html").read_text()

EM_DASH = chr(0x2014)        # em dash (chr() keeps the source ASCII-clean)


def _rule(anchored_selector):
    """Body of a CSS rule, selector anchored at line start (MULTILINE)."""
    m = re.search(anchored_selector + r"\s*\{([^}]*)\}", CSS, re.M)
    assert m, f"CSS rule not found: {anchored_selector}"
    return m.group(1)


# -- The named debt: .elimination-alert OFF the side-stripe (S4) ------------

def test_elimination_alert_has_no_side_stripe():
    block = _rule(r"^\.elimination-alert")
    # The platform absolute ban: a colored border-left/right > 1px as an accent.
    # The pre-A4 rule carried `border-left: 4px solid var(--cfb-lost-life)`.
    assert not re.search(r"(?<![-\w])border-left\s*:", block), \
        "the .elimination-alert side-stripe (border-left) is a platform absolute ban (S4)"
    assert not re.search(r"(?<![-\w])border-right\s*:", block), \
        "no border-right side-stripe either"


def test_elimination_alert_is_a_full_container_lost_red():
    block = _rule(r"^\.elimination-alert")
    assert re.search(r"(?<![-\w])border\s*:\s*1px solid", block), \
        "the migrated cut block must carry a FULL border (full-container treatment, S4)"
    assert "230,57,70" in block.replace(" ", ""), \
        "the cut block keeps the lost-red survivor-state accent (tint/border), dropping the stripe"


def test_cut_title_is_bone_white_with_a_leading_icon():
    block = _rule(r"^\.cfb-cut-title")
    assert re.search(r"(?<![-\w])color:\s*var\(\s*--cfb-white", block), \
        "the cut title reads bone-white (cold/final), not an alarm-red shout (Cold-Elimination Rule)"
    icon = _rule(r"^\.cfb-cut-title \.bi")
    assert "--cfb-lost-life" in icon, "the leading cut icon carries the lost-red accent"
    assert "bi-x-circle-fill" in TPL, "the cut block must render a leading icon (S4 full-container)"


# -- Survivor voice on the H1 (S3) ------------------------------------------

def test_results_h1_carries_survivor_voice():
    assert "Saturday's Verdict" in TPL and "The Cut" in TPL, \
        "the results H1 must carry the Survivor register (Saturday's Verdict / The Cut), not a label"
    # The pre-A4 H1 was `<h1>{{ get_week_display_name(week) }} Results</h1>`.
    assert "Results</h1>" not in TPL, \
        "the flat '... Results' route-label H1 is a S3 voice regression"


# -- Survivor-state by structure + label, never color alone (S5) ------------

def test_badge_pending_is_a_hollow_outline_chip():
    block = _rule(r"^\.badge-pending")
    assert re.search(r"(?<![-\w])background:\s*transparent", block), \
        "the pending chip must be HOLLOW (transparent), structurally distinct from the filled W/L chips"
    assert re.search(r"(?<![-\w])border\s*:\s*1px solid", block), \
        "the pending chip carries an outline (structure), not hue alone (S5)"
    assert ">TBD<" in TPL, "a pending result must carry a readable label (TBD), not a bare colored mark"


def test_no_off_palette_or_crimson_data_chips():
    # Pre-A4 used Bootstrap yellow (bg-warning) for AUTO / no-pick / PENDING and
    # crimson (bg-primary) for the distribution COUNT -- crimson is identity, not
    # data (S2), and yellow is off the survivor-state palette entirely.
    for offending in ("bg-warning", "bg-primary", "bg-secondary", "bg-light"):
        assert offending not in TPL, \
            f"'{offending}' is off the CFB survivor-state palette / uses crimson as data (S2)"
    assert "cfb-auto-tag" in TPL, "the auto-pick marker must be the neutral .cfb-auto-tag, not Bootstrap yellow"


def test_current_user_row_has_a_structural_tag():
    assert "cfb-you-tag" in TPL, \
        "the current-user row must carry the structural .cfb-you-tag, not lean on the crimson tint alone (S2)"


# -- Editorial verdict line, not the four-up hero-metric grid ---------------

def test_week_summary_is_one_line_not_a_stat_grid():
    assert "cfb-week-summary" in TPL, "the week verdict must render the editorial .cfb-week-summary line"
    assert "stat-block" not in TPL, \
        "the four-up .stat-block grid (the hero-metric / identical-card-grid template) must be gone"
    block = _rule(r"^\.cfb-summary-num")
    assert "Teko" in block, "the summary numbers carry Teko weight (S3 -- numbers carry the tension)"


# -- Survivor-first field ledger: folded columns, mobile-readable (S6) ------

def test_field_ledger_folds_columns_for_mobile():
    # Five columns (Player / Pick / Result / Lives / Status); Opponent + Score
    # fold into the Pick cell so survivor-state never scrolls off at 375px.
    assert "<th>Pick</th>" in TPL, "the ledger folds the matchup into a single Pick column"
    assert "<th>Opponent</th>" not in TPL and "<th>Score</th>" not in TPL, \
        "the standalone Opponent / Score columns are folded away (mobile survivor-state readability, S6)"
    assert "cfb-pick-meta" in TPL, "the matchup sub-line (.cfb-pick-meta) rides inside the Pick cell"
    block = _rule(r"^\.cfb-field-table th\.cfb-col-center,\n\.cfb-field-table td\.cfb-col-center")
    assert "width: 1%" in block and "nowrap" in block, \
        "the survivor-state columns stay compact so five columns fit inside mobile width"


# -- No em-dash / double-hyphen copy (S3) -----------------------------------

def test_results_has_no_em_dash_or_double_hyphen_copy():
    assert "&mdash;" not in TPL, "the &mdash; copy debt (e.g. the old 'All Picks &mdash; Week N') must be gone (S3)"
    assert EM_DASH not in TPL, "no literal em-dash may appear in CFB results copy (S3)"
    assert not re.search(r">\s*--\s*<", TPL), \
        "no double-hyphen placeholder ('--') as displayed content (S3 no-double-hyphen)"
