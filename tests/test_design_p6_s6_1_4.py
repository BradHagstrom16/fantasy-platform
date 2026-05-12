"""S6.1.4 — Cross-phase polish (Iter 4). Layer A locks.

Two PIs in one cluster iteration, closing the final 2 of 19 §0.4 routes
(Group H — cross-state component silhouettes + leaderboard rolls anchor).

- PI-1 (Group H, silhouette item): cross-state silhouette taxonomy
  amendment. Inventory across the four converged home-state partials
  (`_home_out` / `_home_pre` / `_home_live` / `_home_post`) shows the
  seven gradient-card silhouettes already inhabit DESIGN.md §5's two
  recipes (Ceremonial, Informational) plus the `.ballot-card` third
  register. Two single-instance hero silhouettes layer on top:
  `.dossier` (live-state standing hero; Ceremonial recipe with extended
  `purple-800 → purple-950` terminus) and `.commish-note-body`
  (Informational with `border-top: 2px solid var(--gold)` major-section
  separator at card level). DESIGN.md §5 amended to ratify both. CSS
  consolidates `.commish-note-body` radius `8px → 12px` so the body
  lands on the canonical Informational radius family. Closes S2.1.1
  cross-cluster silhouette route.

- PI-2 (Group H, rolls item): Decided-already-closed by intervening
  surface work. Both `_home_live.html` top-5 preview rolls AND the
  `leaderboard.html` desktop + mobile-cards surface already wrap each
  player row in an anchor to `worldcup.player_detail`. The §0.4 premise
  (non-interactive `<div>` rolls with no tap-through to competitor
  detail) no longer holds at session-time. Locked here so a future
  refactor cannot silently regress the anchor coverage. Closes S2.1.1
  cross-cluster rolls route.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN_MD = REPO_ROOT / 'DESIGN.md'
STYLE_CSS = REPO_ROOT / 'static' / 'css' / 'style.css'
HOME_LIVE = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / '_home_live.html'
LEADERBOARD_HTML = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'leaderboard.html'


# ---------------------------------------------------------------------------
# PI-1 locks (Group H silhouette): DESIGN.md §5 amendment + CSS consolidation.
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _commish_note_body_rule() -> str:
    css = _read(STYLE_CSS)
    match = re.search(
        r'\.home-shell \.commish-note-body\s*\{[^}]+\}',
        css,
    )
    assert match is not None, '.commish-note-body rule must exist in style.css'
    return match.group(0)


def _dossier_rule() -> str:
    css = _read(STYLE_CSS)
    match = re.search(r'\.home-shell \.dossier\s*\{[^}]+\}', css)
    assert match is not None, '.dossier rule must exist in style.css'
    return match.group(0)


def _decree_rule() -> str:
    css = _read(STYLE_CSS)
    # First `.home-shell .decree {` rule (not `.decree-*` descendants).
    match = re.search(r'\.home-shell \.decree\s*\{[^}]+\}', css)
    assert match is not None, '.decree rule must exist in style.css'
    return match.group(0)


def _ceremonial_cta_rule() -> str:
    css = _read(STYLE_CSS)
    match = re.search(
        r'\.home-shell \.cta-card--seal,\s*\.home-shell \.cta-card--join\s*\{[^}]+\}',
        css,
    )
    assert match is not None, 'Ceremonial CTA rule must exist'
    return match.group(0)


def _cta_view_rule() -> str:
    css = _read(STYLE_CSS)
    match = re.search(r'\.home-shell \.cta-card--view\s*\{[^}]+\}', css)
    assert match is not None, '.cta-card--view rule must exist'
    return match.group(0)


def _match_card_rule() -> str:
    css = _read(STYLE_CSS)
    # The base `.match-card` rule (not `.match-card--*` modifiers).
    match = re.search(r'\.home-shell \.match-card\s*\{[^}]+\}', css)
    assert match is not None, '.match-card rule must exist'
    return match.group(0)


def test_commish_note_body_radius_consolidated_to_informational():
    """PI-1: radius normalized 8px → 12px so .commish-note-body lands on
    the canonical Informational radius family (DESIGN.md §5)."""
    rule = _commish_note_body_rule()
    assert 'border-radius: 12px' in rule, (
        '.commish-note-body must use the Informational 12px radius after '
        'S6.1.4 consolidation; found a different radius (was 8px pre-S6.1.4).'
    )
    # Belt-and-suspenders — the prior 8px value must NOT remain.
    assert 'border-radius: 8px' not in rule, (
        '.commish-note-body must no longer carry the legacy 8px radius.'
    )


def test_commish_note_body_keeps_informational_recipe_with_gold_top():
    """PI-1: `.commish-note-body` retains its informational gradient +
    bone-8% border base + gold-top major-section separator. The gold-top
    rule is the §6 Do canonical major-section separator applied at card
    level; it must not regress to a left-stripe (impeccable absolute ban)
    or vanish (would collapse the editorial variant)."""
    rule = _commish_note_body_rule()
    # Informational gradient
    assert 'var(--purple-850)' in rule
    assert 'var(--purple-950)' in rule
    # Informational bone-8 border (canonical Informational recipe color)
    assert 'rgba(243,239,230,.08)' in rule
    # Gold-top major-section separator (Informational + gold-rule variant)
    assert 'border-top: 2px solid var(--gold)' in rule


def test_dossier_silhouette_locked_as_ceremonial_variant():
    """PI-1: `.dossier` (live-state hero) is the single-instance
    Ceremonial-variant silhouette. Gold-30% border + 14px radius match
    Ceremonial; the gradient terminus extends to `purple-950` for the
    live hero's gravitas. DESIGN.md §5 ratifies this single-instance
    register."""
    rule = _dossier_rule()
    assert 'var(--purple-800)' in rule
    assert 'var(--purple-950)' in rule  # extended terminus
    assert 'rgba(201,162,39,.3)' in rule  # Ceremonial gold-30 border
    assert 'border-radius: 14px' in rule


def test_decree_ceremonial_recipe_preserved():
    """PI-1 invariant: `.decree` continues to anchor the Ceremonial
    recipe (purple-800 → purple-900 + gold-30 border + 14px). S6.1.4
    must not drift the canonical Ceremonial card."""
    rule = _decree_rule()
    assert 'var(--purple-800)' in rule
    assert 'var(--purple-900)' in rule
    assert 'rgba(201,162,39,.3)' in rule
    assert 'border-radius: 14px' in rule


def test_ceremonial_cta_recipe_preserved():
    """PI-1 invariant: `.cta-card--seal` + `.cta-card--join` continue to
    share the Ceremonial recipe with `.decree`."""
    rule = _ceremonial_cta_rule()
    assert 'var(--purple-800)' in rule
    assert 'var(--purple-900)' in rule
    assert 'rgba(201,162,39,.3)' in rule


def test_informational_cta_recipe_preserved():
    """PI-1 invariant: `.cta-card--view` continues to anchor the
    Informational recipe (purple-850 → purple-950 + bone-8 border +
    12px radius)."""
    rule = _cta_view_rule()
    assert 'var(--purple-850)' in rule
    assert 'var(--purple-950)' in rule
    assert 'rgba(243,239,230,.08)' in rule
    assert 'border-radius: 12px' in rule


def test_match_card_informational_recipe_preserved():
    """PI-1 invariant: `.match-card` continues to anchor the
    Informational recipe alongside `.cta-card--view` + `.commish-note-body`."""
    rule = _match_card_rule()
    assert 'var(--purple-850)' in rule
    assert 'var(--purple-950)' in rule
    assert 'rgba(243,239,230,.08)' in rule
    assert 'border-radius: 12px' in rule


def test_design_md_section_5_names_commish_note_body_as_informational():
    """PI-1: DESIGN.md §5 Card recipes amendment names
    `.commish-note-body` as an Informational variant, not a new
    register. The doc must list it alongside `.match-card` +
    `.cta-card--view` so a future designer can look up which recipe
    governs."""
    design = _read(DESIGN_MD)
    # Locate the Informational bullet (must contain .commish-note-body
    # after S6.1.4 amendment).
    informational_match = re.search(
        r'\*\*Informational\*\*\s*\(([^)]+)\)',
        design,
    )
    assert informational_match is not None, (
        'DESIGN.md §5 must keep the **Informational** bullet listing '
        'the card classes that share the Informational recipe.'
    )
    classes = informational_match.group(1)
    assert '.commish-note-body' in classes, (
        '.commish-note-body must be named in the Informational bullet '
        'after S6.1.4 ratifies it as a variant of the canonical recipe.'
    )
    assert '.match-card' in classes
    assert '.cta-card--view' in classes


def test_design_md_section_5_ratifies_dossier_as_hero_silhouette():
    """PI-1: DESIGN.md §5 amendment names `.dossier` as a
    single-instance hero silhouette (Ceremonial recipe with extended
    `purple-800 → purple-950` terminus). Without ratification the
    silhouette reads as accidental drift."""
    design = _read(DESIGN_MD)
    # `.dossier` is named, and the paragraph constrains it to a single
    # surface (do-not-duplicate language).
    assert '`.dossier`' in design, (
        'DESIGN.md §5 must name `.dossier` so a future designer knows '
        'the silhouette is a documented single-instance variant.'
    )
    assert 'single-instance' in design.lower() or 'do not duplicate' in design.lower(), (
        'DESIGN.md §5 must constrain the `.dossier` + `.ballot-card` hero '
        'silhouettes to single-surface use; otherwise the silhouette '
        'invites duplication.'
    )


# ---------------------------------------------------------------------------
# PI-2 locks (Group H rolls): leaderboard tap-through anchors already shipped.
# ---------------------------------------------------------------------------


def test_home_live_top5_preview_rolls_anchor_each_row_to_player_detail():
    """PI-2: `_home_live.html` top-5 preview rolls already wrap each
    row's player name in `<a href="{{ url_for('worldcup.player_detail',
    enrollment_id=e.id) }}">`. The §0.4 premise (non-interactive
    `<div>`s) was met by intervening surface work; this test locks the
    anchor coverage so a refactor cannot silently regress it."""
    html = _read(HOME_LIVE)
    # Must reference player_detail with enrollment_id=e.id.
    pattern = re.compile(
        r"url_for\(\s*'worldcup\.player_detail'\s*,\s*enrollment_id\s*=\s*e\.id\s*\)",
    )
    assert pattern.search(html) is not None, (
        '_home_live.html top-5 preview must anchor each row to '
        'worldcup.player_detail; without the anchor, the §0.4 '
        'tap-through-to-competitor-detail premise reopens.'
    )


def test_leaderboard_desktop_rows_anchor_display_name_to_player_detail():
    """PI-2: `leaderboard.html` desktop table already wraps the player
    display name in an anchor to `worldcup.player_detail`. Locks the
    consistency premise from the §0.4 rolls item — the leaderboard and
    the home-live rolls land on the same competitor-detail surface."""
    html = _read(LEADERBOARD_HTML)
    pattern = re.compile(
        r"url_for\(\s*'worldcup\.player_detail'\s*,\s*enrollment_id\s*=\s*e\.id\s*\)",
    )
    matches = pattern.findall(html)
    # Desktop + mobile-card surface both link; expect at least 2 sites.
    assert len(matches) >= 2, (
        'leaderboard.html must anchor both desktop rows AND mobile '
        f'cards to worldcup.player_detail; found {len(matches)} site(s).'
    )


def test_leaderboard_mobile_cards_use_row_href_resolver():
    """PI-2: leaderboard mobile cards resolve `row_href` to
    `worldcup.picks` (self-row) or `worldcup.player_detail` (others).
    Locks the conditional that S6.1.4 inherits from earlier surface
    work."""
    html = _read(LEADERBOARD_HTML)
    assert 'row_href' in html, (
        'leaderboard.html mobile cards must compute `row_href`; the '
        'tap-through pattern depends on the per-row href resolver.'
    )
    # Self-row points at picks; others point at player_detail.
    self_pattern = re.compile(r"url_for\(\s*'worldcup\.picks'\s*\)")
    assert self_pattern.search(html) is not None, (
        'leaderboard.html mobile cards must route the self-row to '
        'worldcup.picks so the user lands on their own ballot, not '
        'their own player_detail.'
    )
