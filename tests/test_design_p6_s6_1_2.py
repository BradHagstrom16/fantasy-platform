"""S6.1.2 — Cross-phase polish (Iter 2). Layer A locks.

Three PIs in one cluster iteration; each routed in from §0.4 of the
impeccable design improvement plan (P6 §8 docket):

- PI-1 (Group D): Tribune-voice H1 pass. The S4.4.1 cross-phase route
  flagged 8 surfaces carrying SaaS-utility H1s ("Group Standings",
  "Match Schedule", "Rules"). Step 0 at S6.1.1 found most already
  Tribune-voiced ("The Standings", "The Field Office", "Sign the
  ledger", etc.); only `schedule.html`, `rules.html`, and `groups.html`
  remained functional. Closes S4.4.1 cross-phase route. Pairs with
  DESIGN.md §3 Display primitive ratification (Tribune voice for
  user-facing WC H1s; dispensations for dynamic noun + auth-utility
  register).

- PI-2 (Group F): markup-as-icon a11y + `<time datetime>` semantics.
  S2.4.1 cross-phase route: `stats.html` Tournament Progress bar used
  bare ✓/← glyphs without aria. Fix: each segment becomes
  `<div role="listitem" aria-label="{phase}, {status}">` and the
  glyphs go `aria-hidden="true"`. S2.2.1 cross-phase route:
  `.schedule-day-date` lacked machine-readable date semantics. Fix:
  wrap in `<time datetime="{day.day_iso}">`.

- PI-3 (Group G): DESIGN.md doc-only — two primitive policies the
  iterations had been honoring informally but never wrote down. Tier
  primitives (`.wc-tier-dot` / `.tier-badge` / `.wc-multiplier-chip`,
  three non-overlapping roles) get a §5 subsection. Caption-tier
  dispensation note lands in §3 Hierarchy under Body: explicit
  caption/metadata classes may step down to ≥0.75rem (12px) when the
  primary read-target on the same row carries the dominant hierarchy.
  Closes S4.2.1 + S4.3.1 cross-phase routes (both re-routed by S4.5 as
  decided no-op + DESIGN.md route).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN_MD = REPO_ROOT / 'DESIGN.md'
SCHEDULE_HTML = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'schedule.html'
RULES_HTML = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'rules.html'
GROUPS_HTML = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'groups.html'
STATS_HTML = REPO_ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'stats.html'


# ---------------------------------------------------------------------------
# PI-1 locks: Tribune-voice H1 strings on the three routed surfaces.
# ---------------------------------------------------------------------------

def test_pi1_schedule_h1_uses_tribune_voice():
    """`schedule.html` H1 is the Tribune-voiced "The Match Sheet"."""
    html = SCHEDULE_HTML.read_text()
    assert '<h1>The Match Sheet</h1>' in html, (
        '`schedule.html` H1 must read "The Match Sheet" (S6.1.2 PI-1, Group D).'
    )
    assert '<h1>Match Schedule</h1>' not in html, (
        'Old functional "Match Schedule" H1 must not re-appear.'
    )


def test_pi1_rules_h1_uses_tribune_voice_and_strips_entity():
    """`rules.html` H1 reads "House Rules" with no `&amp;` entity bleed."""
    html = RULES_HTML.read_text()
    assert '<h1>House Rules</h1>' in html, (
        '`rules.html` H1 must read "House Rules" (S6.1.2 PI-1, Group D).'
    )
    assert '<h1>Rules &amp; Scoring</h1>' not in html, (
        'Old "Rules &amp; Scoring" H1 must not re-appear; the &amp; entity '
        'broke the editorial register.'
    )


def test_pi1_groups_h1_uses_tribune_voice():
    """`groups.html` H1 is the Tribune-voiced "The Group Sheet"."""
    html = GROUPS_HTML.read_text()
    assert '<h1>The Group Sheet</h1>' in html, (
        '`groups.html` H1 must read "The Group Sheet" (S6.1.2 PI-1, Group D).'
    )
    assert '<h1>Group Standings</h1>' not in html, (
        'Old functional "Group Standings" H1 must not re-appear.'
    )


def test_pi1_design_md_ratifies_h1_tribune_voice_primitive():
    """DESIGN.md §3 Display bullet ratifies the H1 Tribune-voice primitive.

    Lock the *policy*, not the specific copy: future surfaces should
    look up the Display bullet and learn that user-facing WC H1s carry
    editorial section names, with named dispensations for dynamic noun
    H1s and the logged-in utility auth register.
    """
    design = DESIGN_MD.read_text()
    assert 'Tribune voice' in design, (
        'DESIGN.md must call out Tribune voice as the H1 policy on user-facing '
        'WC surfaces.'
    )
    # The dispensation list must name both carve-outs explicitly so a future
    # editor can't drop one and silently regress the rule.
    assert 'dynamic H1' in design or 'dynamic noun' in design or 'dynamic h1' in design.lower(), (
        'DESIGN.md must name the dynamic-noun H1 dispensation.'
    )
    assert 'logged-in utility' in design.lower() or 'auth-utility' in design.lower(), (
        'DESIGN.md must name the auth-utility H1 dispensation.'
    )


# ---------------------------------------------------------------------------
# PI-2 locks: markup-as-icon a11y on stats progress + `<time datetime>` on
# schedule day-date.
# ---------------------------------------------------------------------------

def test_pi2_schedule_day_date_uses_time_element():
    """`.schedule-day-date` renders as a `<time>` with `datetime` attribute.

    The Jinja branches on `day.day_iso` so the TBD bucket (no ISO date)
    keeps the plain span; locked dates get machine-readable semantics.
    """
    html = SCHEDULE_HTML.read_text()
    # The `<time>` branch must be present.
    assert re.search(
        r'<time class="schedule-day-date" datetime="\{\{\s*day\.day_iso\s*\}\}">',
        html,
    ), (
        '`schedule-day-date` must render as `<time datetime="{{ day.day_iso }}">` '
        'when `day.day_iso` is truthy (S6.1.2 PI-2, Group F).'
    )
    # And the TBD fallback (no iso date) must still exist so the macro stays
    # safe when `day.day_iso` is None.
    assert re.search(
        r'\{% if day\.day_iso %\}<time class="schedule-day-date"',
        html,
    ), (
        'The `<time>` element must be wrapped in `{% if day.day_iso %}` so '
        'the TBD bucket renders a plain `<span>` (locked separately below).'
    )
    assert re.search(
        r'\{% else %\}<span class="schedule-day-date">',
        html,
    ), (
        'The TBD bucket must fall back to a plain `<span>` (no `<time>` with '
        'an empty `datetime` attribute, which would be invalid HTML).'
    )


def test_pi2_stats_progress_wrap_carries_list_role():
    """`#progress-bar-wrap` carries `role="list"` and a Tournament-progress label.

    Lock the role + aria-label on the wrapper; without it, the listitem
    semantics on the inner segments would be orphaned.
    """
    html = STATS_HTML.read_text()
    assert re.search(
        r'id="progress-bar-wrap"[^>]*role="list"',
        html,
    ), (
        '`#progress-bar-wrap` must carry `role="list"` (S6.1.2 PI-2, Group F).'
    )
    assert re.search(
        r'id="progress-bar-wrap"[^>]*aria-label="Tournament progress',
        html,
    ), (
        '`#progress-bar-wrap` must carry an `aria-label` naming "Tournament '
        'progress" so SR users hear the region context.'
    )


def test_pi2_stats_progress_segments_render_with_listitem_aria_label():
    """The JS render emits each segment with `role="listitem"` + `aria-label`.

    The aria-label interpolates the phase name + status word ("completed"
    / "current" / "upcoming"), which is what a screen reader speaks
    instead of "check" / "left arrow" (the old bug).
    """
    html = STATS_HTML.read_text()
    # The render line:
    #   return `<div role="listitem" aria-label="${p.label}, ${status}" style="${style}">${p.label}${glyph}</div>`;
    assert re.search(
        r'<div role="listitem" aria-label="\$\{p\.label\}, \$\{status\}"',
        html,
    ), (
        'Stats progress JS must render each segment as '
        '`<div role="listitem" aria-label="${p.label}, ${status}">` '
        '(S6.1.2 PI-2, Group F).'
    )
    # The visible glyph must carry `aria-hidden="true"` so SR users don't
    # hear "check" / "left arrow" alongside the status word.
    assert re.search(
        r"<span aria-hidden=\"true\">\s*✓</span>",
        html,
    ), (
        'Completed-phase glyph must render as `<span aria-hidden="true"> ✓</span>` '
        'so screen readers skip the decorative checkmark.'
    )
    assert re.search(
        r"<span aria-hidden=\"true\">\s*←</span>",
        html,
    ), (
        'Current-phase glyph must render as `<span aria-hidden="true"> ←</span>` '
        'so screen readers skip the decorative arrow.'
    )
    # And the status-word vocabulary must be the canonical "completed / current
    # / upcoming" trio. Lock the JS literal so a refactor can't silently swap
    # to "done" / "now" / "next" without also updating the aria contract.
    assert "'completed'" in html and "'current'" in html and "'upcoming'" in html, (
        'Status-word trio must be the canonical "completed" / "current" / '
        '"upcoming" set in the stats progress render JS.'
    )


# ---------------------------------------------------------------------------
# PI-3 locks: DESIGN.md tier-vocab + caption-tier dispensation (doc-only).
# ---------------------------------------------------------------------------

def test_pi3_design_md_documents_tier_primitive_vocabulary():
    """The WC-scoped DESIGN.md documents the three-way tier primitive split.

    WC tab unification P5 moved per-game primitives (including the tier trio)
    out of the platform-foundation `DESIGN.md` and into the game's own
    `games/worldcup/DESIGN.md` so the foundation file stays lean and per-game
    doctrine lives where future maintainers expect it.
    """
    wc_design = (REPO_ROOT / 'games' / 'worldcup' / 'DESIGN.md').read_text()
    # Each of the three primitives must be named explicitly so the
    # vocabulary doesn't drift back to the pre-S4.5 "is this a tier-badge or
    # a multiplier-chip" ambiguity.
    assert '`.wc-tier-dot`' in wc_design, (
        'games/worldcup/DESIGN.md must name `.wc-tier-dot` as the '
        'visual-mark primitive.'
    )
    assert '`.tier-badge`' in wc_design, (
        'games/worldcup/DESIGN.md must name `.tier-badge` as the '
        'numeric-text-companion primitive.'
    )
    assert '`.wc-multiplier-chip`' in wc_design, (
        'games/worldcup/DESIGN.md must name `.wc-multiplier-chip` as the '
        'multiplier-indicator primitive.'
    )


def test_pi3_design_md_documents_caption_tier_dispensation():
    """The caption-tier <16px dispensation stays documented across the doc split.

    The dispensation locks the S4.5 decided-no-op decision: caption classes
    (`.tier-mobile-card-picks`, `.tier-teams-list`, etc.) are *allowed* to
    step down to >=12px when the primary read-target on the same row carries
    the dominant hierarchy. Without this lock a future iteration that re-runs
    the audit would re-flag the <16px text as a floor violation.

    The 2026-07-20 design-spine revisit split the documentation: the top-level
    DESIGN.md keeps the *principle* (the 12px floor + a pointer to per-game
    lists); the WC class list moved to games/worldcup/DESIGN.md so per-game
    exceptions don't accrete into the platform foundation.
    """
    design = DESIGN_MD.read_text()
    # The dispensation must explicitly carry the 12px floor so a future
    # editor can't silently relax it to "just step down whenever".
    assert '12px' in design, (
        'DESIGN.md must name the 12px floor on the caption-tier dispensation.'
    )
    # And the platform doc must route readers to the per-game class lists.
    assert 'games/worldcup/DESIGN.md' in design, (
        'DESIGN.md must point the caption-floor dispensation at the per-game '
        'class lists (games/worldcup/DESIGN.md).'
    )
    # The grounding class list lives in the WC doc: at least one caption
    # class must be named there so the policy stays tied to real surfaces.
    wc_design = (REPO_ROOT / 'games' / 'worldcup' / 'DESIGN.md').read_text()
    assert (
        '.tier-mobile-card-picks' in wc_design
        or '.tier-teams-list' in wc_design
        or '.wc-microcaption' in wc_design
    ), (
        'games/worldcup/DESIGN.md must name at least one caption-class the '
        '<16px dispensation covers (`.tier-mobile-card-picks`, '
        '`.tier-teams-list`, or `.wc-microcaption`).'
    )
    # The note must connect the dispensation to "primary read-target on the
    # same row" so the policy isn't read as a blanket caption escape hatch.
    assert 'primary read-target' in design or 'dominant hierarchy' in design, (
        'DESIGN.md must connect the dispensation to "primary read-target on the '
        'same row carries the dominant hierarchy" so it reads as a paired-row '
        'policy, not an across-the-board escape hatch.'
    )
