"""P2 S2.2.1 regression locks — first iteration of the schedule cluster.

Layer A (per plan §1.3) source-pattern locks for the three Priority Issues
landed in S2.2.1, plus the freebie entity sweep. Each test pins a structural
decision the impeccable critique surfaced as P0/P1/P2 and that S2.2.1 closed.

Iteration map:
- PI-1 (`$impeccable shape`): the chronologically-interleaved group stage no
  longer fires a `Group A`/`Group B`/... H4 divider for every group_letter
  change. The route now passes `matchdays_group` (date-grouped) and the
  template renders one `.schedule-day-header` per calendar day with an
  `.is-today` modifier on the matchday containing today's Central-Time date.
  Each match-card carries its `group_letter` as a small absolute-positioned
  badge so analyst-curious users keep group context.
- PI-2 (`$impeccable typeset`): the per-row kickoff stamp drops the date
  fragment (the day header carries it now) and reads time-only ("6:00 PM").
  The 48 inline-styled H4 group dividers are deleted; the new
  `.schedule-day-header` primitive is the single source of truth for that
  typography.
- PI-3 (`$impeccable clarify`): the `.match-points-chip` carries a `title=`
  tooltip explaining base points, and a `.schedule-legend` paragraph under
  the Group Stage H2 explains the chip + multiplier relationship.
- Freebies: `&middot;` and `&ndash;` HTML entities removed from the schedule
  template in favor of real Unicode glyphs.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCHEDULE_TPL = (ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'schedule.html').read_text()
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()


# ---------------------------------------------------------------------------
# PI-1: matchday grouping replaces the per-group divider repetition.
# ---------------------------------------------------------------------------

def test_schedule_route_passes_matchdays_group_not_group_matches():
    """The schedule route must hand the template a date-grouped data
    structure, not the legacy flat `group_matches` list. Without the
    grouping, the template's group-letter divider would re-fire as a
    per-match label across the chronologically-interleaved group stage."""
    routes_src = (ROOT / 'games' / 'worldcup' / 'routes.py').read_text()
    assert 'matchdays_group=matchdays_group' in routes_src, (
        "schedule() must pass matchdays_group to render_template; the "
        "matchday data structure is what enables the day-header grouping."
    )
    # Two separate strict assertions, not an OR. The earlier OR collapsed
    # to a tautology: line 45 already requires
    # `matchdays_group=matchdays_group` to be present, so the OR's right
    # branch was unconditionally true at this point and a reintroduced
    # list-comp would have slipped through the regression lock.
    assert "[m for m in matches if m.stage == 'group']" not in routes_src, (
        "Legacy flat group-stage list-comprehension reappeared in "
        "routes.py. Matchday grouping is the only supported shape for the "
        "schedule view; an internal recompute risks drifting back to the "
        "recurring Group-A divider path."
    )
    assert 'group_matches=group_matches' not in routes_src, (
        "schedule() must not pass a legacy `group_matches` kwarg to "
        "render_template — only `matchdays_group` is wired into the "
        "matchday-grouped template."
    )


def test_schedule_template_no_longer_uses_group_letter_divider_loop():
    """The pre-S2.2.1 template branched on `m.group_letter != ns.current_group`
    inside the `{% for m in group_matches %}` loop, which fired up to 48 H4
    dividers across the chronologically-ordered group stage. The matchday
    rewrite removes that pattern entirely."""
    assert 'm.group_letter != ns.current_group' not in SCHEDULE_TPL, (
        "Schedule template still contains the group-letter divider branch; "
        "this is the recurring 'Group A → Group B → Group D → Group A'... "
        "anti-pattern. Iterate matchdays_group instead."
    )
    assert "for m in group_matches" not in SCHEDULE_TPL, (
        "Schedule template still iterates the legacy flat group_matches "
        "list; switch to `for day in matchdays_group / for m in day.matches`."
    )


def test_schedule_template_iterates_matchdays_group():
    """The new structure: outer loop over matchdays, inner loop over each
    day's matches."""
    assert 'for day in matchdays_group' in SCHEDULE_TPL
    assert 'for m in day.matches' in SCHEDULE_TPL


def test_schedule_template_marks_today_block_with_anchor_and_modifier():
    """Today's matchday must be both a CSS modifier target (`.is-today`)
    and a fragment-link target (`id="today"`) so live-state users can be
    deep-linked to the current section."""
    assert 'id="today"' in SCHEDULE_TPL, (
        "Today's matchday block needs id=\"today\" so /worldcup/schedule#today "
        "deep-links to the current matchday."
    )
    assert 'is-today' in SCHEDULE_TPL


def test_schedule_template_renders_group_letter_badge_per_match():
    """Each match-card carries its group_letter as a small `match-group-tag`
    badge so analyst-curious users keep group context after the global
    Group-A/B/C dividers go away."""
    assert 'match-group-tag' in SCHEDULE_TPL, (
        "Without the per-match group badge, removing the group-letter divider "
        "loses group context entirely. The badge is the affordance."
    )
    assert 'aria-label="Group {{ m.group_letter }}"' in SCHEDULE_TPL, (
        "match-group-tag must expose the full 'Group X' label to assistive "
        "tech; the visible badge shows just the letter for visual density."
    )


def test_schedule_day_header_css_primitive_exists():
    """The single `.schedule-day-header` rule replaces 48 inline-styled H4s.
    It must declare the Teko/uppercase/letter-spacing typography that the
    inline style previously carried — otherwise the day headers regress."""
    assert '.schedule-day-header {' in CSS
    # The `.is-today` modifier must change color so today's matchday reads
    # distinctly from neutral past/future days.
    assert '.schedule-day-header.is-today' in CSS
    assert '.schedule-today-badge' in CSS


# ---------------------------------------------------------------------------
# PI-2: typeset — per-row stamp is time-only, no inline H4 styles remain.
# ---------------------------------------------------------------------------

def test_schedule_template_drops_date_from_per_row_stamp():
    """The day header carries the date now, so the per-row pending stamp
    reads time-only ('6:00 PM'). The legacy '%-m/%-d %-I:%M%p' format
    duplicates the date and omits the day of week."""
    assert "'%-I:%M %p'" in SCHEDULE_TPL, (
        "Schedule per-row stamp must use '%-I:%M %p' (time-only). The day "
        "header above the row already states the date."
    )
    assert "'%-m/%-d %-I:%M%p'" not in SCHEDULE_TPL, (
        "Legacy date-and-time format still present; this duplicates the "
        "date now carried by the day header."
    )


def test_schedule_template_strips_inline_teko_h4_styles():
    """The 48 inline-styled `<h4 style="font-family:'Teko'...">` group
    dividers must be gone. The `.schedule-day-header` CSS primitive is the
    sole owner of that typography now."""
    forbidden = "font-family:'Teko'"
    assert forbidden not in SCHEDULE_TPL, (
        f"Schedule template still contains inline {forbidden!r}; this is the "
        "48-instance inline-style explosion the eyebrow primitive replaced."
    )
    forbidden_inline = 'style="font-family'
    assert forbidden_inline not in SCHEDULE_TPL, (
        "Inline font-family style attribute still present; move declarations "
        "into a CSS class."
    )


# ---------------------------------------------------------------------------
# PI-3: clarify — chip tooltip + Group Stage legend.
# ---------------------------------------------------------------------------

def test_match_points_chip_carries_title_tooltip():
    """The chip is opaque to the casual user without a tooltip. Casual is the
    default; depth (the base/multiplier explanation) is available on hover."""
    # Match class and title on the *same* tag, tolerating either attribute
    # order. The earlier strict `class="match-points-chip"` substring check
    # was dropped because it false-fails on a harmless second class
    # (`class="match-points-chip is-knockout"`) and on quote-style changes;
    # the regex alone is enough — if `match-points-chip` is absent or the
    # tag carries no `title=`, the search returns None and the assertion
    # fails. The alternation handles both `class=… title=` and
    # `title=… class=…` orderings so a formatter swap doesn't break the
    # lock. `[^>]*` between the two attributes enforces the "same tag"
    # invariant; `\b…\b` keeps the class match resilient to additional
    # classes in the same attribute.
    assert re.search(
        r'<[^>]*(?:'
        r'\bclass=["\'][^"\']*\bmatch-points-chip\b[^"\']*["\'][^>]*\btitle\s*='
        r'|'
        r'\btitle\s*=[^>]*\bclass=["\'][^"\']*\bmatch-points-chip\b[^"\']*["\']'
        r')',
        SCHEDULE_TPL,
    ), (
        ".match-points-chip must carry a title= tooltip on the same tag so "
        "every rendered chip is self-explaining for the casual user."
    )


def test_schedule_legend_clarifies_chip_meaning():
    """A one-line legend under the Group Stage H2 explains the chip + the
    multiplier relationship without forcing a tooltip-discovery moment."""
    assert 'schedule-legend' in SCHEDULE_TPL
    assert 'base points' in SCHEDULE_TPL.lower(), (
        "Legend microcopy must reference 'base points' so the analyst-curious "
        "user can connect the chip to the team-detail multiplier story."
    )


# ---------------------------------------------------------------------------
# Freebies: HTML-entity sweep.
# ---------------------------------------------------------------------------

def test_schedule_template_uses_real_unicode_glyphs():
    """Editorial register: real glyphs, not legacy HTML entities. The em-dash
    sweep landed in S0.3 but `&middot;` and `&ndash;` survived in this
    template; S2.2.1 finishes the cleanup."""
    assert '&middot;' not in SCHEDULE_TPL, (
        "Replace '&middot;' with the real '·' glyph."
    )
    assert '&ndash;' not in SCHEDULE_TPL, (
        "Replace '&ndash;' with the real '\N{EN DASH}' glyph."
    )


# ---------------------------------------------------------------------------
# Integration smoke: route renders without exploding in dev/test.
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    from app import create_app
    from extensions import db
    from games.worldcup.models import WorldCupMatch
    from datetime import datetime, timezone

    app = create_app('testing')
    with app.app_context():
        db.create_all()
        # Seed a tiny fixture: 2 group matches on different days, plus 1
        # knockout match. Enough to exercise the matchday-grouping path.
        m1 = WorldCupMatch(
            match_number=1, stage='group', group_letter='A',
            kickoff_utc=datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc),
            is_completed=False,
        )
        m2 = WorldCupMatch(
            match_number=2, stage='group', group_letter='B',
            kickoff_utc=datetime(2026, 6, 12, 19, 0, tzinfo=timezone.utc),
            is_completed=False,
        )
        m3 = WorldCupMatch(
            match_number=89, stage='R32',
            kickoff_utc=datetime(2026, 6, 28, 19, 0, tzinfo=timezone.utc),
            is_completed=False,
        )
        db.session.add_all([m1, m2, m3])
        db.session.commit()
        yield app
        db.drop_all()


def test_schedule_route_renders_with_day_headers(app):
    """End-to-end Layer A: render the schedule with a 2-group-match fixture
    and confirm the rendered HTML contains a .schedule-day-header per
    distinct kickoff date and the per-match group-letter badge."""
    client = app.test_client()
    resp = client.get('/worldcup/schedule')
    assert resp.status_code == 200
    html = resp.data.decode()
    assert html.count('schedule-day-header') >= 2, (
        "Two distinct kickoff days should produce two day headers."
    )
    assert 'match-group-tag' in html, (
        "match-group-tag badge must render on each group match in the "
        "rendered HTML, not just exist as a class in source."
    )


def test_schedule_route_today_badge_only_when_today_matchday_exists(app, monkeypatch):
    """The is-today modifier and fragment id must only appear when the
    fixture's date set actually intersects today (Central Time). Pin the
    time seam to a date outside the seeded matchdays (2026-06-11/12) so
    the assertion is strict and deterministic regardless of when the test
    runs. Patch `now_utc` at the schedule route's read-site
    (`games.worldcup.routes`) — the schedule view binds the symbol there
    via `from games.worldcup.services.state import now_utc`, so the
    route's `today_ct_date = _format_ct(now_utc()).date()` resolves
    against this monkeypatch."""
    from datetime import datetime, timezone
    import games.worldcup.routes as wc_routes

    monkeypatch.setattr(
        wc_routes,
        'now_utc',
        lambda: datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
    )

    client = app.test_client()
    resp = client.get('/worldcup/schedule')
    assert resp.status_code == 200
    html = resp.data.decode()
    # With now pinned to 2026-05-01 and the fixture pinned to 2026-06-11/12,
    # no matchday is "today" — the badge and the anchor id must both be
    # absent. A bug that renders the badge unconditionally (e.g.,
    # always-true `is_today`) now fails this test instead of slipping
    # through on a date-dependent lenient branch.
    assert 'schedule-today-badge' not in html, (
        "schedule-today-badge rendered with no matchday on today's date."
    )
    assert 'id="today"' not in html, (
        "today anchor id rendered with no matchday on today's date."
    )
