"""Regression locks — WC Stats Hub ("The Field Office") editorial redesign.

This iteration followed an $impeccable critique of `worldcup/stats`. Two classes
of change are pinned here:

P0 correctness bug
------------------
The chart/bar palette JS read the per-tier tokens (`--wc-tier1..5`) off
`document.documentElement`. Those tokens are scoped to `body.game-worldcup`
(style.css) and do NOT cascade up to `<html>`, so they resolved to empty
strings and every Chart.js chart + `.wc-pick-bar-fill` rendered Chart.js-default
black. The fix reads from `document.body` (which carries `game-worldcup` and
still inherits the `:root` tokens like `--wc-navy`). This is the headline lock:
WC token-reading JS must read from the game-scoped element, not `<html>`.

Editorial-first restructure (confirmed shape brief)
---------------------------------------------------
"Dossier over telemetry" — 4 Chart.js charts collapsed to 1 signature scatter;
the Board donut became an editorial Group/Knockout split strip; the By Tier
bar + donut became a Newsreader verdict line under the ledger; the ~48-row pick
distribution moved behind a native <details> disclosure; empty/low-data states
were authored in Tribune voice.

Complements the prior `test_design_p2_s2_4_1.py` locks (masthead, ledger,
3 `is-lead` cards, `tbl()` recognition), which remain green under this redesign.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'stats.html'
TPL = TEMPLATE_PATH.read_text()


# ---------------------------------------------------------------------------
# P0: token read-site — the headline lock.
# ---------------------------------------------------------------------------

def test_chart_tokens_read_from_body_not_documentelement():
    """The CSS-custom-property reader must source from `document.body`, which
    carries `body.game-worldcup` (where `--wc-tier1..5` live). Reading from
    `document.documentElement` returns empty strings for the body-scoped tier
    tokens and silently renders every chart black."""
    assert 'getComputedStyle(document.body)' in TPL, (
        "Chart palette must read tokens from document.body (the game-worldcup "
        "scope), where --wc-tier1..5 are defined."
    )
    assert 'getComputedStyle(document.documentElement)' not in TPL, (
        "Must NOT read design tokens off <html> — body-scoped game tokens "
        "(--wc-tier1..5) don't cascade up to documentElement. This was the P0 "
        "bug that rendered every tier chart/bar Chart.js-default black."
    )


# ---------------------------------------------------------------------------
# Editorial-first: one signature chart, the rest distilled to editorial DOM.
# ---------------------------------------------------------------------------

def test_only_the_scatter_remains_a_chartjs_chart():
    """4 Chart.js charts collapsed to 1. The popularity-vs-payoff scatter is
    the one genuinely 2-D insight a table can't carry; everything else became
    editorial DOM."""
    assert TPL.count('new Chart(') == 1, (
        "Exactly one Chart.js chart should remain (the scatter)."
    )
    assert 'id="ch-scatter"' in TPL, "The signature scatter canvas must stay."
    for retired in ('ch-accum', 'ch-tier-bar', 'ch-tier-donut'):
        assert retired not in TPL, (
            f"Retired chart canvas `{retired}` must be gone (donut/bar charts "
            f"were replaced by editorial DOM)."
        )


def test_board_points_split_replaces_donut():
    """The Board's Points Breakdown donut became an editorial navy/red split
    strip + summary lines. The card head keeps the 'Points Breakdown' label."""
    assert 'id="points-split"' in TPL
    assert 'wc-points-split' in TPL
    assert 'renderPointsSplit()' in TPL
    assert '<span>Points Breakdown</span>' in TPL


def test_by_tier_carries_editorial_verdict_line():
    """The retired avg-bar + total-donut distill into one Newsreader verdict
    line under the ledger, populated by renderTierLedger()."""
    assert 'id="tier-verdict"' in TPL
    assert 'wc-stats-ledger-note' in TPL


def test_pick_distribution_collapsed_in_native_disclosure():
    """The ~48-row pick distribution moved behind a native <details> so the
    casual reader isn't met with a wall of rows. It stays a `.is-lead` card
    (the lead of the tab when expanded) carrying its 'The cross-section'
    eyebrow."""
    assert '<details class="wc-stat-card is-lead mb-4 wc-disclosure">' in TPL
    assert 'wc-disclosure-summary' in TPL
    assert 'class="wc-eyebrow">The cross-section<' in TPL


def test_empty_states_authored_in_tribune_voice():
    """Low-data / pre-tournament states reward participation rather than
    rendering blank. Each panel carries an authored empty line."""
    assert 'Awaiting the first whistle' in TPL          # Board split (0 points)
    assert 'No tier has returned points yet' in TPL      # By Tier verdict
    assert 'No nation is carrying the field yet' in TPL  # Field: Carrying
    assert 'dragged a roster down, yet' in TPL           # Field: Dead Weight


# ---------------------------------------------------------------------------
# a11y: gold progress-bar segments carry dark text (AA).
# ---------------------------------------------------------------------------

def test_gold_progress_segments_use_dark_text():
    """The SF (gold-fill) done segment and the current-segment (gold tint)
    must carry dark chamber-purple text, not white/gold — white-on-gold was
    sub-AA (~2.2:1). The Final segment already used dark text on gold."""
    assert 'background:rgba(212,168,32,.9);color:var(--platform-primary-dark)' in TPL, (
        "SF progress segment (gold fill) must use dark text for AA contrast."
    )
    assert 'background:rgba(212,168,32,.9);color:#fff' not in TPL, (
        "White-on-gold SF segment is sub-AA; must not return."
    )
