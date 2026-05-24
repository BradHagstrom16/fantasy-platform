"""Regression locks — picks.html pre-vs-live surface split + form polish.

$impeccable critique 2026-05-24 follow-up (worldcup/picks). The picks read-only
view used one scoring-ledger layout in every state; before kickoff the Points
column / total / accordion were a ledger of zeros. This split gates the scoring
ledger on `deadline_passed`:

- PRE-DEADLINE submitted: sealed-roster read. No Points column, no total, no
  drill-down accordion. The multiplier carries the stakes; a "9 Sealed" stamp
  confirms the lock.
- LIVE / POST submitted: the scoring ledger returns (Points + accordion) plus
  per-pick alive/out status and an "X of 9 alive" survival count, mirroring the
  hub Leverage Board's `is_eliminated` signal for cross-tab cohesion.

Plus form polish: per-tier header tint (tier-card-N), tier-full card lock,
deduped tier eyebrow, and `%g` multiplier formatting (x1 not x1.0).
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WC_TPL = REPO / 'games' / 'worldcup' / 'templates' / 'worldcup'
PICKS = WC_TPL / 'picks.html'
PICK_ROW = WC_TPL / '_pick_row.html'
ROUTES = REPO / 'games' / 'worldcup' / 'routes.py'
CSS = REPO / 'static' / 'css' / 'style.css'


@pytest.fixture(scope='module')
def picks_src() -> str:
    return PICKS.read_text()


@pytest.fixture(scope='module')
def pick_row_src() -> str:
    return PICK_ROW.read_text()


@pytest.fixture(scope='module')
def routes_src() -> str:
    return ROUTES.read_text()


@pytest.fixture(scope='module')
def css_src() -> str:
    return CSS.read_text()


# --- Pre-vs-live scoring gate ------------------------------------------------

def test_show_scoring_is_bound_to_deadline_passed(picks_src):
    """The read-only branch derives `show_scoring` from `deadline_passed`, the
    single switch that flips the pre-deadline sealed read into the live ledger."""
    assert '{% set show_scoring = deadline_passed %}' in picks_src


def test_points_th_gated_behind_show_scoring(picks_src):
    """The Points column header only renders when scoring is live."""
    assert '{% if show_scoring %}<th scope="col" class="text-end">Points</th>{% endif %}' in picks_src


def test_pick_row_points_cell_and_accordion_gated(pick_row_src):
    """Pre-deadline rows carry no Points cell and no drill-down accordion
    (nothing to score yet); both live behind `show_scoring`."""
    assert '{% if show_scoring %}' in pick_row_src
    # The accordion row (colspan=4) must be inside a show_scoring guard.
    assert 'pick-accordion-row' in pick_row_src
    # Eliminated rows mark out only when scoring is live.
    assert 'is_out = show_scoring and pick.team.is_eliminated' in pick_row_src


def test_sealed_stamp_present_pre_deadline(picks_src):
    """Pre-deadline header shows a '9 Sealed' confirmation in place of the
    meaningless total."""
    assert 'wc-pick-sealed' in picks_src
    assert '9 Sealed' in picks_src


# --- Live/post survival status -----------------------------------------------

def test_alive_count_passed_from_route(routes_src):
    """Route computes alive_count from is_eliminated (hub-parity) and passes it
    on both render paths."""
    assert 'alive_count = sum(1 for p in existing_picks if not p.team.is_eliminated)' in routes_src
    assert routes_src.count('alive_count=alive_count') == 2


def test_alive_line_and_low_alert_present(picks_src):
    """Live/post header surfaces 'X of 9 alive'; <=4 lifts to the red alert."""
    assert 'wc-pick-alive' in picks_src
    assert 'of 9 alive' in picks_src
    assert 'wc-pick-alive--low' in picks_src


def test_out_status_label_styled_not_color_alone(css_src):
    """Eliminated picks read through structure + label: struck name + an 'Out'
    label, with the mobile label lifted back to danger to match desktop."""
    assert '.wc-pick-status-out' in css_src
    assert '.pick-team-out' in css_src
    assert '.player-pick-card .pick-points small.wc-pick-status-out' in css_src


# --- Form polish: tier tint, lock, eyebrow dedupe, %g multiplier -------------

def test_tier_card_carries_per_tier_class(picks_src, css_src):
    """Each tier card carries a tier-card-N class so the header tint can
    differentiate the five stacked cards."""
    assert 'tier-card tier-card-{{ tier_num }}' in picks_src
    assert '.tier-card-1 .tier-card-header' in css_src
    assert '.tier-card-5 .tier-card-header' in css_src


def test_tier_full_lock_wired(picks_src, css_src):
    """A full tier dims its remaining unselected cards (recognition over the
    prior silent counter flash)."""
    assert 'function updateTierLocks()' in picks_src
    assert "classList.toggle('tier-locked'" in picks_src
    assert '.wc-team-card.tier-locked' in css_src


def test_tier_eyebrow_deduped(picks_src):
    """The tier eyebrow no longer echoes the heading name; it reads 'Tier N'
    and the heading carries the name + multiplier."""
    assert 'Tier {{ tier_num }} · {{ tier[\'name\'] }}' not in picks_src
    assert '<span class="wc-eyebrow wc-eyebrow-red">Tier {{ tier_num }}</span>' in picks_src


def test_multiplier_uses_g_format(picks_src, pick_row_src):
    """Multipliers format with %g so whole tiers read x1/x4/x7, not x1.0."""
    # Raw float interpolation retired everywhere the chip renders.
    assert '&times;{{ tier[\'multiplier\'] }}' not in picks_src
    assert '&times;{{ pick.team.multiplier }}' not in pick_row_src
    assert '"%g"|format(tier[\'multiplier\'])' in picks_src
    assert '"%g"|format(pick.team.multiplier)' in pick_row_src


def test_empty_summary_copy_in_voice(picks_src):
    """Empty pick-summary copy carries the imperative club voice."""
    assert 'Select your 9 teams...' not in picks_src
    assert 'Choose your nine nations.' in picks_src


# --- Form ergonomics: clear-all + unsaved-edit guard (#3) --------------------

def test_clear_all_button_present_and_wired(picks_src):
    """Pick summary carries a Clear all action (hidden until selections exist)
    with a JS handler that bulk-deselects."""
    assert 'id="clearAll"' in picks_src
    assert 'pick-summary-clear' in picks_src
    assert "getElementById('clearAll')" in picks_src


def test_clear_all_visibility_tracks_selection(picks_src):
    """The button hides when nothing is selected."""
    assert 'clearBtn.hidden = selected.length === 0' in picks_src


def test_unsaved_edit_guard_present(picks_src):
    """beforeunload warns on leaving with unsaved pick changes; submit clears
    the flag so sealing never trips it."""
    assert "window.markDirty" in picks_src
    assert "addEventListener('beforeunload'" in picks_src
    assert 'dirty && !submitting' in picks_src
    # Sealing the form sets submitting so the guard stays silent on submit.
    assert "submitting = true" in picks_src
    # A pick toggle marks the form dirty.
    assert 'markDirty();' in picks_src


# --- Form ergonomics: tier-jump / progress rail (#7) -------------------------

def test_tier_jump_rail_markup(picks_src):
    """A tier-jump rail renders 5 chips, each a jump anchor with a live count."""
    assert 'class="tier-jump"' in picks_src
    assert 'href="#tier-{{ tier_num }}"' in picks_src
    assert 'id="jump-count-{{ tier_num }}"' in picks_src
    # Each tier card is an anchor target.
    assert 'id="tier-{{ tier_num }}"' in picks_src


def test_tier_jump_counts_update_with_selections(picks_src):
    """updateCounters mirrors each tier's count + complete state onto the rail."""
    assert "getElementById('jump-count-' + t)" in picks_src
    assert "getElementById('jump-' + t)" in picks_src


def test_tier_jump_scroll_respects_reduced_motion(picks_src):
    """Jump scroll is smooth, but instant under prefers-reduced-motion."""
    assert "prefers-reduced-motion: reduce" in picks_src
    assert "scrollIntoView" in picks_src


def test_tier_jump_css_present_and_anchors_offset(css_src):
    """Rail styling + complete state exist, and tier anchors carry a
    scroll-margin so a jump clears the sticky chrome."""
    assert '.tier-jump {' in css_src
    assert '.tier-jump-chip.complete' in css_src
    assert 'scroll-margin-top' in css_src


def test_tier_jump_count_avoids_raw_text_muted_on_white(css_src):
    """The chip count sits on a white chip; it must use --text-secondary, not
    the dark-substrate --text-muted (CLAUDE.md bone-substrate invariant)."""
    import re
    block = re.search(r'\.tier-jump-count\s*\{([^}]*)\}', css_src)
    assert block is not None
    assert 'var(--text-muted)' not in block.group(1)
    assert 'var(--text-secondary)' in block.group(1)
