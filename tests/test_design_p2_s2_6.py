"""P2 S2.6 regression locks — live-cluster cross-cluster polish.

Layer A (per plan §1.3) source-pattern locks for the Priority Issues landed
in S2.6. S2.6 is cluster polish: patterns visible only when comparing 2+
live-cluster surfaces. Each test pins a cross-surface decision.

Iteration map:
- PI-1 (`$impeccable harden bootstrap-on-wc-card-table`): the surgical
  exclusion at style.css ~:5485 (`.card.wc-card .table > tbody > tr > td
  .text-muted`) relied on Bootstrap masking the navy parent with a white td
  background. Bootstrap 5.3 supplies that via `--bs-table-bg:
  var(--bs-body-bg)` (default `#fff`), but the assumption was implicit and
  a future Bootstrap upgrade or stray `--bs-body-bg` retune could silently
  re-surface the S2.5.1 dark-on-dark bug on any new `.card.wc-card .table`
  surface. Lock the white-td invariant explicitly via a CCC-owned token
  assignment (`.card.wc-card .table { --bs-table-bg: var(--bg-card); }`).
  Surfaces that want dark navy bleed-through still opt out via their own
  scoped `> tbody > tr > td { background-color: transparent; }` rule (see
  the canonical `.card.wc-card.player-picks-desktop` overrides).

- PI-3 (`$impeccable clarify text-muted-cluster-leak`): the live-cluster
  light surfaces leaked Bootstrap `.text-muted` (`#6c757d` neutral gray) on
  microcopy that the rest of the surface renders in CCC purple-tinted
  `--text-secondary` (`#5A5470`). Three sites identified by the S2.6 sweep:
  schedule stage-count `<small>` (x2), team_detail no-fixtures empty state,
  team_detail path-to-crown explainer. Each carries a surface-honest class
  (`.schedule-stage-count` / `.team-fixtures-empty` / `.team-path-fineprint`)
  that resolves to `--text-secondary` via scoped CSS, with the `text-muted`
  class removed from the templates so Bootstrap's `!important` declaration
  no longer needs to be fought.

- PI-4 (`$impeccable shape schedule-jump-to-today`): the S2.2.1 work added
  `id="today"` to the active matchday block but never surfaced a hero-level
  jump affordance. Mid-tournament the today block sits 6-11 matchdays into
  the page; live-state surfacing required a scroll. Add an above-the-fold
  `.schedule-jump-today` pill chip rendered only when a today matchday
  exists (template-side `|selectattr('is_today')` filter).

Routed forward to receiving sessions per §0.4:
- [S2.1.1 cross-cluster] gradient-card silhouette across home variants →
  S6.1 (needs pre/live/post home comparison after P4/P5).
- [S2.1.1 cross-cluster] leaderboard rolls non-interactive `<div>`s →
  S6.1 (needs rivalry/competitor surface design).
- [S2.3.1 cross-cluster] `.wc-eyebrow` saturation + `.wc-meta-label`
  ratification → S6.1 (broader cluster comparison after P3/P4/P5 land).
- [S2.4.1 cross-cluster] inline-Teko `.wc-microcaption` extraction →
  P4.5 (most candidate surfaces are pre-live: picks.html / rules.html /
  join.html — extracting now would be premature).
- [S2.4.1 cross-cluster] double-elevation on `.wc-stat-card` →
  decided no-op. DESIGN.md §4.4 "Lift-At-Rest Rule" explicitly mandates
  border + `--shadow-sm` at rest for the `.card` primitive ("Flat-at-rest
  is the wrong elevation philosophy for CCC; the Tribune is a printed
  object, not a wireframe"); the generic impeccable "pick one" heuristic
  is overridden by the committed policy.
"""
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent
SCHEDULE = (ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'schedule.html').read_text()
TEAM_DETAIL = (ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'team_detail.html').read_text()
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()


# ---------------------------------------------------------------------------
# PI-1: Lockstep-inverted in P3.5 — the .card.wc-card .table mask cluster
# retired when rules.html + team_detail.html migrated off the dark substrate.
# After P3.5 the only .card.wc-card consumer is the _home_post.html champion
# banner, which contains no Bootstrap table — so the white-td invariant has
# zero DOM consumer and the rule is fully orphaned. The lockstep rewrite
# (function rename to `..._was_retired_in_p3_5`) mirrors P3's precedent
# `tests/test_design_wc_tab_unification_p2.py::test_pick_events_item_dark_carve_out_was_retired_in_p3`.
# ---------------------------------------------------------------------------

def test_card_wc_card_table_pi1_rule_was_retired_in_p3_5():
    """The `.card.wc-card .table { --bs-table-bg: var(--bg-card); }` cluster
    invariant lock retired in P3.5. Anchored regex (start-of-line +
    `re.MULTILINE`, P3 CR R3-R4 idiom) so a substring match inside another
    rule can't false-pass."""
    pattern = re.compile(
        r'^\.card\.wc-card\s+\.table\s*\{',
        re.MULTILINE,
    )
    assert pattern.search(CSS) is None, (
        "S2.6 PI-1 `.card.wc-card .table { --bs-table-bg: var(--bg-card); }` "
        "must stay retired post-P3.5 — the rule's only DOM consumer was the "
        "rules.html / team_detail.html / picks.html wrappers, all migrated "
        "off .card.wc-card. Re-introducing it would orphan into the champion "
        "banner (which has no <table>) and re-attach a dependency the next "
        "wrapper migration would have to break again."
    )


def test_card_wc_card_table_pi1_surgical_exclusion_was_retired_in_p3_5():
    """The `.card.wc-card .table > tbody > tr > td .text-muted` exclusion
    (the cluster-3 buster that paired with the PI-1 lock above) retired in
    lockstep — it had no functional consumer once the lock above retired
    (no `.card.wc-card .table` to apply the lock means no light-substrate td
    to need the exclusion). Anchored regex per the P3 CR R3-R4 idiom."""
    pattern = re.compile(
        r'^\.card\.wc-card\s+\.table\s*>\s*tbody\s*>\s*tr\s*>\s*td\s*\.text-muted',
        re.MULTILINE,
    )
    assert pattern.search(CSS) is None, (
        "S2.6 PI-1 surgical exclusion re-appeared post-P3.5. The orphan "
        "retirement is chained on the PI-1 rule's retirement — restoring it "
        "without restoring the rule above leaves a vestigial selector."
    )


# ---------------------------------------------------------------------------
# PI-3: .text-muted Bootstrap gray retired on light live-cluster surfaces
# ---------------------------------------------------------------------------

def test_schedule_stage_count_pi3_no_longer_carries_text_muted():
    """The `<small>` stage counts on the Group Stage / knockout-stage section
    headings no longer ship the Bootstrap `.text-muted` class. They keep the
    surface-honest `.schedule-stage-count` class and lift their color via
    scoped CSS to `--text-secondary` (CCC purple-tinted), holding tonal
    consistency with `.schedule-day-date` / `.schedule-legend` on the same
    surface."""
    assert 'text-muted ms-2 schedule-stage-count' not in SCHEDULE, (
        "schedule.html section-heading <small> still carries Bootstrap "
        ".text-muted; PI-3 retired this in favor of .schedule-stage-count "
        "alone + scoped --text-secondary."
    )
    # Surface class still present and used twice (group stage + knockout macro).
    assert SCHEDULE.count('schedule-stage-count') >= 2


def test_schedule_stage_count_pi3_scoped_to_text_secondary():
    """The .schedule-stage-count CSS rule resolves to --text-secondary so it
    reads as CCC purple-tinted on bone, not Bootstrap neutral gray."""
    pattern = re.compile(
        r'\.schedule-stage-count\s*\{[^}]*color:\s*var\(--text-secondary\)',
        re.DOTALL,
    )
    assert pattern.search(CSS), (
        "S2.6 PI-3 .schedule-stage-count missing --text-secondary color rule."
    )


def test_team_detail_pi3_empty_and_fineprint_surface_classes():
    """team_detail.html no-fixtures empty state + path-to-crown explainer
    paragraphs sit on the bone page background (NOT inside .card.wc-card),
    so they need the page-level light-surface microcopy color, not the
    `--bone-mute` token reserved for dark substrates. Each carries its own
    surface-honest class with a scoped --text-secondary rule."""
    assert '<p class="team-fixtures-empty">' in TEAM_DETAIL, (
        "PI-3 team_detail no-fixtures empty-state lost .team-fixtures-empty class."
    )
    assert '<p class="team-path-fineprint' in TEAM_DETAIL, (
        "PI-3 team_detail path-to-crown explainer lost .team-path-fineprint class."
    )
    # Bootstrap .text-muted retired from these two slots.
    assert '<p class="text-muted">No fixtures available.' not in TEAM_DETAIL
    assert '<p class="text-muted small mt-2 mb-0">' not in TEAM_DETAIL
    # Scoped CSS resolves both to --text-secondary.
    pattern = re.compile(
        r'\.team-fixtures-empty,\s*\n?\s*\.team-path-fineprint\s*\{[^}]*color:\s*var\(--text-secondary\)',
        re.DOTALL,
    )
    assert pattern.search(CSS), (
        "S2.6 PI-3 .team-fixtures-empty / .team-path-fineprint missing scoped "
        "--text-secondary color rule."
    )


# ---------------------------------------------------------------------------
# PI-4: Jump-to-today affordance on schedule hero
# ---------------------------------------------------------------------------

def test_schedule_pi4_jump_to_today_anchor_in_hero():
    """The .schedule-jump-today pill is rendered inside the .page-hero (above
    the fold) and targets the existing id="today" anchor that landed in
    S2.2.1. Wrapped in a {% if today_days %} guard so it disappears
    pre/post-tournament when no today matchday exists."""
    assert 'class="schedule-jump-today"' in SCHEDULE
    assert 'href="#today"' in SCHEDULE
    # Conditional guard: only render when a today matchday exists.
    assert 'selectattr(\'is_today\')' in SCHEDULE, (
        "PI-4 jump-to-today missing the `is_today` matchday guard; the chip "
        "would render even pre-tournament with no anchor target."
    )


def test_schedule_pi4_jump_to_today_chip_meets_44_floor():
    """Per P0 S0.3 the global 44x44 tap-target floor applies to every new
    affordance. The .schedule-jump-today rule sets min-height: 44px."""
    pattern = re.compile(
        r'\.schedule-jump-today\s*\{[^}]*min-height:\s*44px',
        re.DOTALL,
    )
    assert pattern.search(CSS), (
        "S2.6 PI-4 .schedule-jump-today missing the 44px tap-target floor "
        "(regression of P0 S0.3 global tap-target sweep)."
    )


def test_schedule_pi4_jump_to_today_has_focus_visible():
    """Keyboard nav: the chip must surface a visible focus ring per the
    DESIGN.md focus-state requirement (every interactive element)."""
    assert ':focus-visible' in CSS  # baseline: some focus-visible exists
    pattern = re.compile(
        r'\.schedule-jump-today:focus-visible\s*\{[^}]*outline',
        re.DOTALL,
    )
    assert pattern.search(CSS), (
        "S2.6 PI-4 .schedule-jump-today:focus-visible missing outline rule."
    )
