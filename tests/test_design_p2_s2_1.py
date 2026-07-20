"""P2 S2.1 regression locks — home_shell live + _home_live cluster.

Layer A (per plan §1.3): source-pattern locks for the design decisions made
in S2.1. Each test asserts a structural invariant that, if regressed, would
re-introduce the issue the impeccable critique flagged.

Test surface map:
- `.home-metal-text` no longer applies gradient text (impeccable absolute ban).
- The dossier 3-up hero-metric grid is gone (impeccable absolute ban).
- The Tribune ledger composition is in its place.
- `_recent_results.html` differentiates roster vs non-roster matches.
- The fixture ladder in `_home_pre.html` does not use the banned
  `match.stage|title` filter. (Was: `_fixture_card.html`, retired in
  S6.1.5 PI-5 when the rail collapsed to an editorial typographic ladder.)
- The Commish byline no longer ships the en-dash that read as a SaaS-blog tell.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()
DOSSIER = (ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'lounge' / '_dossier_card.html').read_text()
RECENT = (ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'lounge' / '_recent_results.html').read_text()
HOME_PRE = (ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'lounge' / '_home_pre.html').read_text()
COMMISH = (ROOT / 'core' / 'main' / 'templates' / 'main' / '_commish_note.html').read_text()


# ---------------------------------------------------------------------------
# P0a: Gradient text ban (impeccable absolute ban; DESIGN.md §6 Don't #2)
# ---------------------------------------------------------------------------

def test_home_metal_text_does_not_apply_gradient_text():
    """`.home-metal-text` must not pair `background-clip: text` with a gradient
    background. The metal-gold gradient is reserved for primary CTAs (Trophy
    Rule); using it on type also violates the absolute ban on gradient text."""
    block = _css_block(CSS, '.home-metal-text')
    assert block, '.home-metal-text rule missing from style.css'
    assert 'background-clip' not in block, (
        '.home-metal-text re-introduced background-clip; gradient text is an '
        'impeccable absolute ban (SKILL.md shared design laws + DESIGN.md §6).'
    )
    assert 'var(--metal-gold)' not in block, (
        '.home-metal-text re-introduced --metal-gold; the metal-gold gradient '
        'is reserved for primary CTAs (Trophy Rule).'
    )


def test_out_title_a_does_not_apply_gradient_text():
    """Same lock for the logged-out hero (`.out-title .out-title-a`)."""
    block = _css_block(CSS, '.home-shell .out-title .out-title-a')
    assert block, '.home-shell .out-title .out-title-a rule missing'
    assert 'background-clip' not in block
    assert 'var(--metal-gold)' not in block


def test_dossier_sparkline_uses_flat_gold_fill_not_gradient():
    """The sparkline area-fill must be a flat tint, not a gradient. The
    metal-gold gradient is the trophy; decorating a chart with it dilutes
    the trophy (Trophy Rule, DESIGN.md §6)."""
    assert 'spark-fill' not in DOSSIER, (
        'spark-fill linearGradient re-introduced; sparkline area must be flat.'
    )
    assert 'rgba(242,211,107,0.16)' in DOSSIER or 'rgba(242, 211, 107, 0.16)' in DOSSIER, (
        'Sparkline area fill missing the flat low-opacity gold tint.'
    )


# ---------------------------------------------------------------------------
# P0b: Hero-metric template ban (impeccable absolute ban)
# ---------------------------------------------------------------------------

def test_dossier_hero_metric_three_up_strip_is_gone():
    """`dossier-meta` 3-up grid (`.k` big number + `.l` tiny label, repeated)
    is the canonical hero-metric template. SKILL.md absolute ban list."""
    assert 'dossier-meta' not in DOSSIER
    assert 'd-meta' not in DOSSIER
    assert 'dossier-meta' not in CSS
    assert '.home-shell .d-meta' not in CSS


def test_dossier_renders_the_ledger_composition():
    """The ledger replacement: an Eyebrow + a Newsreader-prose line that
    embeds the numerals as Teko-bold spans. One line, three facts, asymmetric."""
    assert 'dossier-ledger' in DOSSIER
    assert 'ledger-eyebrow' in DOSSIER
    assert 'ledger-line' in DOSSIER
    # The ledger CSS must wire the numerals as Teko-bold tabular numerals
    assert '.home-shell .ledger-line .lk' in CSS
    assert 'font-family: var(--font-teko)' in _css_block(CSS, '.home-shell .ledger-line .lk')


# ---------------------------------------------------------------------------
# P1: Recent Results differentiation (DESIGN.md §6 Don't #7 — identical cards)
# ---------------------------------------------------------------------------

def test_recent_results_renders_roster_match_as_full_card():
    """The user's roster-intersection match is a full match-card with a
    `--roster` modifier so the design system can give it visual rest."""
    assert 'match-card--roster' in RECENT
    assert 'match-card--roster' in CSS


def test_recent_results_collapses_neutral_matches_into_one_strip():
    """Non-roster matches collapse into the `Also Today` ledger strip rather
    than rendering as identical full match-cards."""
    assert 'results-also' in RECENT
    assert 'results-also-eyebrow' in RECENT
    assert 'results-also-row' in RECENT
    assert '.home-shell .results-also' in CSS


# ---------------------------------------------------------------------------
# P2: Honest "this week" copy + casual-friendly labels
# ---------------------------------------------------------------------------

def test_dossier_does_not_say_this_week():
    """The week-delta is gated behind ≥7 daily snapshots in home_context, so
    "over 7 days" is honest. "This week" was technically wrong on early-deploy
    days where the window was 2-3 snapshots; the copy must not say it."""
    assert 'this week' not in DOSSIER, (
        'Dossier copy still says "this week"; use "over 7 days" — the actual '
        'window the home_context gate enforces.'
    )


def test_dossier_uses_in_the_club_not_competitors():
    """"competitors" is platform-language; CCC's audience is a friend group
    of 10-30 people. PRODUCT.md frames them as members of a club."""
    assert 'competitors' not in DOSSIER
    assert 'in the Club' in DOSSIER


# ---------------------------------------------------------------------------
# Bonus harden: banned `match.stage|title` (DESIGN.md §6 Don't #10)
# ---------------------------------------------------------------------------

def test_home_pre_fixture_ladder_does_not_use_banned_title_filter():
    """`{{ match.stage|title }}` mangles ALL-CAPS knockout codes ('SF' → 'Sf')
    and underscored values ('third_place' → 'Third_Place'). CLAUDE.md gotcha
    + DESIGN.md §6 Don't #10. Use the stage_label SSoT instead.

    S6.1.5 PI-5 — when the rail collapsed from 3 match-cards to the editorial
    fixture ladder, the stage rendering moved from `_fixture_card.html` into
    `_home_pre.html` directly. The ban check moved with it."""
    src_no_comments = re.sub(r'\{#.*?#\}', '', HOME_PRE, flags=re.S)
    assert 'match.stage|title' not in src_no_comments, (
        '_home_pre.html re-introduced banned `match.stage|title`; use '
        'stage_label(match.stage) — the SSoT documented in CLAUDE.md.'
    )
    assert 'stage_label(match.stage)' in src_no_comments


# ---------------------------------------------------------------------------
# Polish freebies (caught by critique, fixed in S2.1)
# ---------------------------------------------------------------------------

def test_commish_byline_no_en_dash():
    """The `&ndash; the Commish` byline read as the SaaS-blog "— Sincerely,"
    pattern. The Tribune fiction is a club newspaper; bylines sign off
    in caps, not in typographer's dashes. PRODUCT.md Copy Discipline."""
    assert '&ndash;' not in COMMISH
    assert '&mdash;' not in COMMISH
    # Whatever the byline says, it must not start with a dash glyph
    byline_match = re.search(r'<p class="commish-note-byline">([^<]+)</p>', COMMISH)
    assert byline_match, 'commish-note-byline element missing'
    assert not byline_match.group(1).strip().startswith(('-', '–', '—')), (
        f'Commish byline still leads with a dash glyph: {byline_match.group(1)!r}'
    )


def test_match_foot_status_loss_uses_red_not_bone_mute():
    """The audit critique flagged `--bone-mute` on `--purple-950` for the
    "NO POINTS" status as washed-out. Loss is an emotional moment per
    PRODUCT.md Pleasure principle — the color must read distinct, not muted."""
    block = _css_block(CSS, '.home-shell .match-foot-status--loss')
    assert block, 'match-foot-status--loss rule missing'
    assert 'bone-mute' not in block, (
        'match-foot-status--loss reverted to bone-mute; the audit flagged this '
        'as washed-out on the dark surface. Keep the red.'
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _css_block(src: str, selector: str) -> str:
    """Return the body of the first CSS rule matching `selector`, or ''.

    Naive parser — just finds `selector { ... }` and returns the contents
    between the braces. Sufficient for these source-pattern locks; if a real
    CSS parser becomes necessary later, swap in `tinycss2`.
    """
    # Escape regex metachars in selector
    pat = re.escape(selector) + r'\s*\{([^}]*)\}'
    m = re.search(pat, src)
    return m.group(1) if m else ''
