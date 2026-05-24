"""WC Schedule redesign regression locks ($impeccable critique 2026-05-24).

The schedule critique scored the page 26/40 and surfaced five priority issues.
This iteration closed all of them; each test below pins a structural decision
so a later edit cannot silently revert it.

Priority issues closed:
- P0 (layout): the prior one-`.card`-per-match layout stacked 100+ full-width
  cards whose content collapsed to a center island, leaving wide dead bands.
  The matchday is now the card (`.schedule-day`); matches are dense rows
  (`.sched-fixture-row`) on a `1fr auto 1fr` grid inside a `.sched-fixture-list` that packs
  into TWO columns at md+ so screen width carries fixtures, not empty space.
  The roster-highlight on-brand win folded in here.
- P1 (onboard): ~32 full-width "TBD" knockout slabs pre-tournament became a
  left-to-right bracket tree of compact cells (`.wc-bracket` / `.wc-ko-cell`)
  that stacks into round sections on mobile and fills in as teams advance.
- P2 (adapt): a sticky in-page wayfinding rail (`.schedule-nav`) so Group /
  Knockout / Today are reachable from anywhere on the long page.
- P3 (clarify/polish): the points chip re-anchored to a center caption beneath
  the score (`.match-points-chip` spans the row, no pill chrome); the static
  score box lost its button chrome; the group letter moved inline; non-
  interactive surfaces lost their hover lift.

Regex idioms inherit the WC DESIGN.md section 6 / P3 hardening:
- CSS scans anchor with `^...` + `re.MULTILINE` so a substring inside a larger
  composite rule cannot false-pass.
- Property scans use `(?<![-\\w])` negative lookbehind.
- Rule blocks are extracted with `\\{([^}]*)\\}` and asserted on.
"""
from datetime import datetime, timezone
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).parent.parent
SCHEDULE = (ROOT / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'schedule.html').read_text()
ROUTES = (ROOT / 'games' / 'worldcup' / 'routes.py').read_text()
CSS = (ROOT / 'static' / 'css' / 'style.css').read_text()


def _block(selector_regex: str):
    """Return the declaration body of the first rule whose selector matches,
    anchored at start-of-line. None if the rule is absent."""
    m = re.compile(rf'^{selector_regex}\s*\{{([^}}]*)\}}', re.MULTILINE).search(CSS)
    return m.group(1) if m else None


# ===========================================================================
# P0 — editorial fixture list replaces the per-match card / dead-space layout
# ===========================================================================

def test_per_match_card_retired_from_css():
    """The `.match-result-card` primitive (one elevated card per match, content
    collapsed to center) is fully retired. Its presence is the P0 dead-space
    regression; the matchday `.schedule-day` panel + `.sched-fixture-row` rows replace
    it. Anchored at start-of-line so any `.match-result-card...` rule trips."""
    assert re.search(r'^\.match-result-card', CSS, re.MULTILINE) is None, (
        "`.match-result-card` reappeared in style.css. The schedule redesign "
        "retired the one-card-per-match layout (P0 dead-space fix); matches are "
        "now `.sched-fixture-row` rows inside a `.schedule-day` panel."
    )


def test_per_match_card_retired_from_template():
    """The template must not reintroduce the retired card class."""
    assert 'match-result-card' not in SCHEDULE, (
        "schedule.html references `match-result-card`; the redesign renders "
        "matches as `.sched-fixture-row` rows, not per-match cards."
    )


def test_fixture_list_packs_two_columns_at_md():
    """The dead-space fix: `.sched-fixture-list` is single-column by default and packs
    into two columns at md+, so the desktop width carries fixtures rather than
    empty bands. There are two `.sched-fixture-list` rule blocks (base + the
    min-width:768px media); one must declare the two-column grid."""
    blocks = re.findall(r'\.sched-fixture-list\s*\{([^}]*)\}', CSS)
    assert blocks, "`.sched-fixture-list` rule not found in style.css."
    assert any('grid-template-columns: 1fr 1fr' in b for b in blocks), (
        "No `.sched-fixture-list` block declares `grid-template-columns: 1fr 1fr`. "
        "The two-column md+ pack is the P0 dead-space fix; without it the rows "
        "collapse back to a single centered column with empty side bands."
    )
    # And the base must exist as a real grid container.
    assert any('display: grid' in b for b in blocks), (
        "`.sched-fixture-list` must be a grid container."
    )


def test_fixture_row_is_three_column_grid():
    """Each fixture is a `1fr auto 1fr` grid (home | score/time | away) so the
    score column stays centered and the names converge on it."""
    block = _block(r'\.sched-fixture-row')
    assert block is not None, "`.sched-fixture-row` rule not found in style.css."
    assert re.search(r'grid-template-columns:\s*1fr auto 1fr', block), (
        "`.sched-fixture-row` must use `grid-template-columns: 1fr auto 1fr`."
    )


def test_score_box_has_no_button_chrome():
    """P3: the static scoreline must not wear interactive pill chrome. The
    `.sched-fixture-score` rule carries the navy color but NO background fill (the old
    `.match-score` tinted-navy pill read as a tappable button on a page where
    nothing in that slot is clickable)."""
    block = _block(r'\.sched-fixture-score')
    assert block is not None, "`.sched-fixture-score` rule not found in style.css."
    assert 'background' not in block, (
        "`.sched-fixture-score` declares a `background`; the static score must not "
        "wear button/pill chrome (P3 false-affordance fix). Keep it plain "
        "colored numerals."
    )


def test_points_chip_is_centered_caption_not_pill():
    """P3: the points attribution re-anchored from an orphaned bordered pill
    below the card to a caption that spans the fixture row and centers under the
    score. Lock: `.match-points-chip` spans the grid (`grid-column: 1 / -1`) and
    carries no `border` (the de-pill)."""
    block = _block(r'\.match-points-chip')
    assert block is not None, "`.match-points-chip` rule not found in style.css."
    assert re.search(r'grid-column:\s*1\s*/\s*-1', block), (
        "`.match-points-chip` must span the row (`grid-column: 1 / -1`) so it "
        "centers beneath the score as one match->result->points unit."
    )
    assert 'border' not in block, (
        "`.match-points-chip` still declares a `border`; P3 demoted it from a "
        "bordered pill to a plain caption. Remove the border/border-radius."
    )


def test_points_chip_keeps_self_explaining_title():
    """Carried from S2.2.1 PI-3: the chip stays self-explaining for casual
    users. The macro must keep the `title=` tooltip on the chip tag."""
    assert re.search(
        r'class="match-points-chip"[^>]*\btitle\s*=', SCHEDULE
    ), "`.match-points-chip` lost its `title=` tooltip."


def test_group_letter_is_inline_not_absolute():
    """P3: the group letter moved from a faint absolute-positioned corner glyph
    to an inline trailing tag next to the away team. The `.match-group-tag` rule
    must NOT position it absolutely."""
    block = _block(r'\.match-group-tag')
    assert block is not None, "`.match-group-tag` rule not found in style.css."
    assert 'position: absolute' not in block, (
        "`.match-group-tag` is absolutely positioned again; the redesign "
        "inlined it next to the away team for legibility (it was a faint, "
        "easy-to-miss corner glyph)."
    )


def test_schedule_day_panel_is_non_interactive():
    """The matchday panel is a container, not an affordance: no hover lift (the
    old per-match card had a hover shadow on a non-interactive surface). It must
    still carry the white card substrate at rest."""
    assert re.search(r'\.schedule-day:hover', CSS) is None, (
        "`.schedule-day:hover` exists; the matchday panel is non-interactive "
        "and must not lift on hover (P3 false-affordance fix)."
    )
    block = _block(r'\.schedule-day')
    assert block is not None, "`.schedule-day` rule not found in style.css."
    assert 'background: var(--bg-card)' in block, (
        "`.schedule-day` must keep the white card substrate (Casual-Light)."
    )


# ===========================================================================
# Roster highlight (on-brand win folded into P0)
# ===========================================================================

def test_route_passes_my_team_ids():
    """The schedule route hands the template the viewer's picked team ids so it
    can flag 'your team plays here' fixtures."""
    assert 'my_team_ids=my_team_ids' in ROUTES, (
        "schedule() must pass `my_team_ids` to the template for the roster "
        "highlight."
    )


def test_roster_highlight_is_not_colour_alone():
    """Owned-team fixtures are flagged by tint + weighted red name AND a
    visually-hidden '(your pick)' string, never colour alone (PRODUCT.md
    accessibility: avoid colour-only state)."""
    assert '.sched-fixture-name.is-mine-team' in CSS, (
        "`.sched-fixture-name.is-mine-team` styling missing."
    )
    block = _block(r'\.sched-fixture-name\.is-mine-team')
    assert block and 'var(--wc-red)' in block, (
        "Owned-team name must paint `--wc-red` (WC primary/current-user accent)."
    )
    assert SCHEDULE.count('(your pick)') >= 2, (
        "The visually-hidden '(your pick)' marker must accompany the colour cue "
        "on both the fixture row and the bracket cell, so the highlight is not "
        "colour-alone for assistive tech."
    )


# ===========================================================================
# Light-substrate token hygiene (CLAUDE.md: no raw --text-muted on bone/white)
# ===========================================================================

def test_new_schedule_classes_avoid_raw_text_muted():
    """The fixture + bracket surfaces sit on white/bone. Per the CLAUDE.md
    invariant, raw `color: var(--text-muted)` (calibrated for dark substrates,
    ~3.6:1 on white) must not appear on them; muted text uses `--text-secondary`
    (~6.9:1 AA)."""
    for sel in (r'\.sched-fixture-tbd', r'\.wc-ko-tbd', r'\.sched-fixture-kick'):
        block = _block(sel)
        assert block is not None, f"`{sel}` rule not found in style.css."
        assert 'var(--text-muted)' not in block, (
            f"`{sel}` uses raw `var(--text-muted)` on a light substrate; use "
            f"`--text-secondary` (AA on bone) instead."
        )


# ===========================================================================
# P1 — knockout bracket
# ===========================================================================

def test_bracket_primitives_exist():
    """The knockout bracket primitives ship: the flex tree container, the round
    columns, and the compact match cell."""
    for sel in ('.wc-bracket', '.wc-bracket-round', '.wc-bracket-col', '.wc-ko-cell'):
        assert sel in CSS, f"Bracket primitive `{sel}` missing from style.css."
    assert 'wc-bracket' in SCHEDULE and 'wc-ko-cell' in SCHEDULE, (
        "schedule.html must render the bracket primitives."
    )


def test_bracket_winner_emphasis_is_structural():
    """A decided cell lifts the winner with weight + ink (structure), not colour
    alone: the `.wc-ko-cell.is-decided .wc-ko-team.is-winner` rule carries a
    font-weight bump."""
    block = _block(r'\.wc-ko-cell\.is-decided \.wc-ko-team\.is-winner')
    assert block is not None, (
        "`.wc-ko-cell.is-decided .wc-ko-team.is-winner` rule not found; the "
        "advancing side needs a structural emphasis, not colour alone."
    )
    assert 'font-weight' in block, (
        "Winner emphasis must include a font-weight lift (structural cue)."
    )


def test_bracket_stacks_into_sections_on_mobile():
    """Mobile-first: below 992px the side-by-side bracket columns stack into
    full-width round sections (a horizontal 5-column tree cannot fit 375px).
    One `.wc-bracket` block must switch to `flex-direction: column`."""
    blocks = re.findall(r'\.wc-bracket\s*\{([^}]*)\}', CSS)
    assert blocks, "`.wc-bracket` rule not found in style.css."
    assert any('flex-direction: column' in b for b in blocks), (
        "No `.wc-bracket` block sets `flex-direction: column`; the bracket must "
        "stack into round sections on mobile rather than overflow horizontally."
    )
    assert re.search(r'@media\s*\(max-width:\s*991px\)', CSS), (
        "The bracket mobile-stack breakpoint (max-width: 991px) is missing."
    )


# ===========================================================================
# P2 — sticky in-page wayfinding rail
# ===========================================================================

def test_wayfinding_rail_is_sticky():
    """The `.schedule-nav` rail sticks below the sub-nav so section jumps are
    reachable from anywhere on the 100+ match page."""
    block = _block(r'\.schedule-nav')
    assert block is not None, "`.schedule-nav` rule not found in style.css."
    assert 'position: sticky' in block, (
        "`.schedule-nav` must be `position: sticky` (P2 persistent wayfinding)."
    )


def test_wayfinding_pills_meet_tap_floor_and_focus_ring():
    """Each pill is a real tap target (>=44px) with a visible keyboard focus
    ring (global P0 S0.3 floor + DESIGN.md focus-state requirement)."""
    block = _block(r'\.schedule-nav-pill')
    assert block is not None, "`.schedule-nav-pill` rule not found in style.css."
    assert re.search(r'min-height:\s*44px', block), (
        "`.schedule-nav-pill` missing the 44px tap-target floor."
    )
    fv = _block(r'\.schedule-nav-pill:focus-visible')
    assert fv is not None and 'outline' in fv, (
        "`.schedule-nav-pill:focus-visible` must paint a visible outline."
    )


def test_wayfinding_anchors_present_in_template():
    """The rail's pills target the two section anchors; the H2s carry the ids."""
    assert 'href="#group-stage"' in SCHEDULE and 'href="#bracket"' in SCHEDULE, (
        "Wayfinding pills must link to #group-stage and #bracket."
    )
    assert 'id="group-stage"' in SCHEDULE and 'id="bracket"' in SCHEDULE, (
        "The Group Stage and Knockout H2s must carry their anchor ids."
    )


def test_anchor_targets_clear_the_sticky_rail():
    """Anchored jumps must land below the sticky rail, not behind it. The
    matchday panels and the section H2s carry a scroll-margin-top that clears
    the navbar + sub-nav + rail."""
    day = _block(r'\.schedule-day')
    assert day and 'scroll-margin-top' in day, (
        "`.schedule-day` must set scroll-margin-top so #today lands below the "
        "sticky rail."
    )
    anchors = _block(r'#group-stage,\s*\n?#bracket')
    assert anchors and 'scroll-margin-top' in anchors, (
        "#group-stage / #bracket must set scroll-margin-top to clear the rail."
    )


# ===========================================================================
# Integration — render the route and assert behaviour, not just source
# ===========================================================================

@pytest.fixture
def app():
    from app import create_app
    from extensions import db
    from games.worldcup.models import (
        WorldCupTeam, WorldCupMatch, WorldCupEnrollment, WorldCupPick,
    )
    from models import User

    app = create_app('testing')
    with app.app_context():
        db.create_all()

        esp = WorldCupTeam(
            fifa_code='ESP', name='Spain', display_name='Spain', tier=1,
            multiplier=1.0, confederation='UEFA', group_letter='A',
        )
        fra = WorldCupTeam(
            fifa_code='FRA', name='France', display_name='France', tier=1,
            multiplier=1.0, confederation='UEFA', group_letter='A',
        )
        db.session.add_all([esp, fra])
        db.session.flush()

        # A pending group match (fixture row) + a completed knockout match
        # (decided bracket cell with a winner).
        grp = WorldCupMatch(
            match_number=1, stage='group', group_letter='A',
            home_team_id=esp.id, away_team_id=fra.id,
            kickoff_utc=datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc),
            is_completed=False,
        )
        ko = WorldCupMatch(
            match_number=89, stage='R32',
            home_team_id=esp.id, away_team_id=fra.id,
            home_score=2, away_score=1, winner_team_id=esp.id, is_draw=False,
            kickoff_utc=datetime(2026, 6, 28, 19, 0, tzinfo=timezone.utc),
            is_completed=True,
        )
        db.session.add_all([grp, ko])

        # A user who picked Spain, so their fixtures should light up.
        user = User(username='picker', email='picker@example.com')
        user.set_password('x')
        db.session.add(user)
        db.session.flush()
        enr = WorldCupEnrollment(user_id=user.id, season_year=2026)
        db.session.add(enr)
        db.session.flush()
        db.session.add(WorldCupPick(enrollment_id=enr.id, team_id=esp.id, tier=1))
        db.session.commit()

        app.config['_picker_id'] = user.id
        yield app
        db.drop_all()


def test_render_uses_redesigned_structure_not_cards(app):
    """End-to-end: the rendered schedule contains the new sched-fixture-list +
    bracket + wayfinding structure and NONE of the retired card markup."""
    html = app.test_client().get('/worldcup/schedule').data.decode()
    assert 'class="schedule-day"' in html
    assert 'sched-fixture-row' in html
    assert 'wc-bracket' in html and 'wc-ko-cell' in html
    assert 'schedule-nav' in html
    assert 'match-result-card' not in html, (
        "Retired per-match card markup rendered in the schedule HTML."
    )


def test_render_winner_emphasis_on_completed_knockout(app):
    """The completed R32 cell marks the winning side with `.is-winner`."""
    html = app.test_client().get('/worldcup/schedule').data.decode()
    assert 'wc-ko-team is-winner' in html, (
        "A completed knockout match must mark its winner with `.is-winner`."
    )


def test_roster_highlight_hidden_for_anonymous_viewer(app):
    """Anonymous viewers have no picks, so no fixture is flagged. Guards the
    privacy/correctness of the highlight (it is viewer-scoped, not global)."""
    html = app.test_client().get('/worldcup/schedule').data.decode()
    assert 'is-mine' not in html, (
        "Roster highlight rendered for an anonymous viewer with no picks."
    )
    assert '(your pick)' not in html


def test_roster_highlight_shown_for_owning_viewer(app):
    """The Spain picker sees their Spain fixtures flagged: the group row gets
    `.sched-fixture-row.is-mine`, the bracket cell gets `.is-mine`, the team name gets
    `.is-mine-team`, and the visually-hidden '(your pick)' marker renders."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(app.config['_picker_id'])
        sess['_fresh'] = True
    html = client.get('/worldcup/schedule').data.decode()
    assert 'sched-fixture-row is-mine' in html, (
        "The Spain picker's group fixture row must carry `.is-mine`."
    )
    assert 'is-mine-team' in html, (
        "The owned team's name must carry `.is-mine-team`."
    )
    assert '(your pick)' in html, (
        "The visually-hidden '(your pick)' marker must render for the owner."
    )
