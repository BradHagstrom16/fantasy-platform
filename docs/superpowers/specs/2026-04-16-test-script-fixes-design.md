# Test Script Fixes — Sections 5, 6, 7 (Design Spec)

**Date:** 2026-04-16
**Author:** Brad (with Claude)
**Status:** Draft → pending user review
**Related:** `Human End-to-End Test Script.md` sections 5A, 6, 7B, 7C, 7D; ADR-024 (denormalized scoring), ADR-026 (public leaderboard), ADR-027 (enrollment-scoped admin)

---

## 1. Purpose

Address six issues surfaced in the April 2026 human end-to-end test pass on the World Cup Fantasy Pool, before launch.

1. **Leaderboard — tiebreaker exposed pre-deadline.** The `usa_goals_guess` column/value is visible on the public leaderboard before the pick deadline, leaking tiebreaker info.
2. **Schedule — no indication that times are Central Time.** Kickoff times render on `/worldcup/schedule` with no timezone hint.
3. **Admin match entry — winner must be picked manually.** Admin enters the score **and** must also click the winner/draw radio, even though the score usually determines the winner.
4. **Scoring attribution — no way to see where points came from.** Players can't see how their team (or other players' teams) accumulated points. Completed-match cards on the schedule don't show points awarded.
5. **Admin editing completed matches — no UI link.** Once a match is completed, the only way to reach its result page is by typing `/worldcup/admin/match/<id>` directly.
6. **Knockout assignment — cannot be cleared.** `/worldcup/admin/set-knockout/<id>` only supports assign/replace; there is no way to clear an assignment.

## 2. Non-Goals

- **Sticky/frozen subnav** (mentioned in the test script's "Still Needs Work" section) — out of scope here.
- **Golf / CFB regression fixes** — Section 8 of the test script. Out of scope.
- **Tournament deadline reset** (`TOURNAMENT_DEADLINE_UTC` in `games/worldcup/constants.py`) — a one-line cleanup step, not a design decision. Listed as the final implementation step.
- **New score-event history table.** Deliberately avoided; ADR-024 mandates that every number is rebuildable from match state. Scoring attribution is **derived on display**, not stored.

## 3. Architecture Context

**God nodes** (per graphify `GRAPH_REPORT.md`):
- `WorldCupMatch`, `WorldCupTeam`, `WorldCupPick`, `WorldCupEnrollment` — all touched here, but read-only; no schema change.

**ADRs that constrain this design:**
- **ADR-024 — Denormalized scoring.** Team/pick totals are recomputed from scratch by `recalculate_all_scores()`. We add a sibling derive helper for display-time attribution; we do **not** persist score events.
- **ADR-026 — Public leaderboard.** The tiebreaker-hide logic must work for anonymous visitors (`deadline_passed` computed from `datetime.now(utc)`, no user context needed).
- **ADR-027 — Enrollment-scoped admin.** All admin route changes remain behind `@worldcup_admin_required`; no new auth work.

**No migrations. No new routes.** Only new POST actions on existing admin endpoints.

## 4. Design

### 4.1 Public — hide tiebreaker pre-deadline (issue #1)

**Files:** `games/worldcup/routes.py`, `games/worldcup/templates/worldcup/leaderboard.html`.

- Route `leaderboard()` computes `deadline_passed = datetime.now(timezone.utc) >= TOURNAMENT_DEADLINE_UTC` and passes it into the template.
- **Desktop table:** `{% if deadline_passed %}` wraps both the `Tiebreaker` `<th>` and the matching `<td>`. Column disappears entirely pre-deadline.
- **Mobile card:** same conditional wraps the `<small>TB: N</small>` line.
- Audit `index.html` and `admin/users.html` for any other places that display `usa_goals_guess` to unauthenticated viewers. Admin-facing views can continue to show the value (they're behind `@worldcup_admin_required`).

### 4.2 Public — Central Time caption on schedule (issue #2)

**Files:** `games/worldcup/templates/worldcup/schedule.html`.

- Add a small caption line inside the existing `page-hero` lead:
  ```html
  <small class="d-block mt-1 opacity-75"
         style="letter-spacing:.08em; text-transform:uppercase; font-size:.72rem;">
    All kickoff times shown in Central Time
  </small>
  ```
- No changes to `admin/dashboard.html` (header already reads `Kickoff (CT)`) or `admin/match_result.html` (strftime already appends `CT`).

### 4.3 Public — scoring attribution (issue #4)

The biggest piece. One shared service helper powers both the schedule chip and the player-detail drill-down.

#### 4.3.1 New derive helpers in `services/scoring.py`

```python
from dataclasses import dataclass
from typing import Literal

ScoreSource = Literal['group_win', 'group_draw', 'advancement', 'knockout', 'podium']

@dataclass(frozen=True)
class ScoreEvent:
    source: ScoreSource
    label: str              # e.g., "Win vs RSA (Jun 11)", "Group runner-up", "R16: beat CRO"
    base_points: float      # un-multiplied
    match_id: int | None    # for optional linking; None for advancement/podium
    occurred_on: date | None  # for chronological ordering; None for advancement/podium

def compute_team_score_events(team: WorldCupTeam) -> list[ScoreEvent]:
    """Replay this team's scoring sources against current match/team state.
    Returns chronologically-ordered events. Sum of base_points equals
    team.base_points (asserted in unit tests)."""

def compute_match_attribution(match: WorldCupMatch) -> dict | None:
    """For a completed match, return:
      { 'type': 'group_win' | 'group_draw' | 'knockout',
        'events': [(team_display_name, fifa_code, +base_points), ...] }
    Returns None for incomplete matches. Knockout events include any
    podium bonus that triggers from this match."""
```

Both functions mirror the logic already in `recalculate_all_scores()` but emit human-readable rows instead of mutating DB state. The supported sources map to existing scoring constants:

| source | Value | Trigger |
|---|---|---|
| `group_win` | `GROUP_WIN` (3) | Group match where team is winner |
| `group_draw` | `GROUP_DRAW` (1) | Group match where team drew |
| `advancement` | `ADVANCE_GROUP_WINNER`/`ADVANCE_RUNNER_UP`/`ADVANCE_BEST_THIRD` | `team.advancement_method` set |
| `knockout` | `KNOCKOUT_POINTS[stage]` for R32/R16/QF/SF | Team is winner of a non-group match |
| `podium` | `KNOCKOUT_POINTS['champion'/'runner_up'/'third_place']` | `team.best_finish` set |

**Invariant check (unit-tested):** for every team `t`, `sum(e.base_points for e in compute_team_score_events(t)) == t.base_points`. If the derive logic ever drifts from `recalculate_all_scores()`, the test fails before users see wrong drill-downs.

#### 4.3.2 Schedule chip

**Files:** `games/worldcup/routes.py` `schedule()`, `games/worldcup/templates/worldcup/schedule.html`, `static/css/style.css`.

- Route passes `attribution_by_match_id = {m.id: compute_match_attribution(m) for m in matches}` alongside the existing match lists.
- Each `match-result-card` renders a compact chip below the score when `attribution` is non-null:
  - **Group win:** `ARG +3 base`
  - **Group draw:** `ARG +1 · RSA +1 base`
  - **Knockout win:** `ARG +11 base (R16)` — includes any podium bonus rolled into the same chip.
- **Visual:** new `.match-points-chip` class — Old Glory blue surface (`rgba(0,40,104,.08)` light / appropriate dark-mode variant), 2px World Cup red accent border-left, Teko font for numerals, fixed-width so cards stay aligned.

#### 4.3.3 Player detail accordion + picks-page parity

**Files:** `games/worldcup/routes.py` `player_detail()`, `games/worldcup/templates/worldcup/player_detail.html`, `games/worldcup/templates/worldcup/picks.html`, new partial `games/worldcup/templates/worldcup/_pick_row.html`, `static/css/style.css`.

- Route `player_detail()` builds `events_by_pick = {pick.id: compute_team_score_events(pick.team) for pick in picks}` and passes it in. Same helper used on `picks.html` for the current user's own picks.
- Extract a shared partial `_pick_row.html` accepting `pick` and `events` — used by both `player_detail.html` (desktop table rows + mobile cards) and `picks.html` (read-only post-submission view).
- Each pick row becomes expandable. Default: same appearance as today + a small chevron toggle. Expanded: indented event timeline reveals below the row with a 140ms `max-height` + `opacity` transition.
- Each event line shows: a source dot, date (or `—` for non-dated like advancement/podium), label, and `+N base`.
- Footer row shows: `Total base × {{ multiplier }} = {{ multiplied }}` — making the tier math visible.
- **Pre-deadline:** accordion is not rendered; existing privacy rules (picks hidden from others) still apply.
- **Post-deadline, no events yet:** expanded row shows `No scoring events yet.`
- **Mobile:** same accordion pattern using `.player-pick-card` as the toggle target.

**Motion/polish:** CSS-only expand/collapse; no JS library. Events within a pick stagger in with `animation-delay: calc(var(--i) * 40ms)` for a quick 4-frame cascade — restrained.

### 4.4 Admin — auto-winner derivation (issue #3)

**Files:** `games/worldcup/templates/worldcup/admin/match_result.html`, `static/css/style.css`.

JS-only; no Python change (`process_match_result()` already trusts the form's winner radio).

- Inline `<script>` listens to `input` on both score fields.
- Derives winner on each change:
  - `home > away` → check `winner_home`
  - `away > home` → check `winner_away`
  - `home == away && stage == 'group'` → check `winner_draw`
  - `home == away && stage != 'group'` → clear radios, reveal a small muted hint `"Equal score — pick the winner and mark ET or penalties"` near the winner group
- Auto-check respects user override: any manual radio `change` sets `data-user-override="1"` on the radio group container; subsequent score edits no longer auto-flip it.
- **Polish:** 160ms background-color pulse on the auto-selected label via `@keyframes wc-auto-pulse` using `--game-accent`. Subtle cue that the selection was derived.

### 4.5 Admin — completed matches list (issue #5)

**Files:** `games/worldcup/routes.py` `admin_dashboard()`, `games/worldcup/templates/worldcup/admin/dashboard.html`.

- Route adds:
  ```python
  completed_matches = (
      WorldCupMatch.query
      .filter_by(is_completed=True)
      .order_by(
          WorldCupMatch.updated_at.desc(),
          WorldCupMatch.match_number.desc(),
      )
      .all()
  )
  ```
  Secondary sort on `match_number` guarantees deterministic ordering when two matches share a `updated_at` instant (e.g., recalc touching both simultaneously).
- New collapsible card below "Matches Needing Scores":
  - Columns: `#`, `Stage`, `Result` (e.g., `ARG 2–1 RSA` or `MEX 1–1 CAN (draw)`), `Updated` (relative time), `Action` ([Edit]).
  - Collapsed by default once list exceeds 5 rows (`<div class="collapse">` + "Show all N" toggle).
  - `Edit` button links to the existing `/worldcup/admin/match/<id>` route — that page already supports clear + re-enter.
- **Sort:** `updated_at DESC` so a just-mis-entered result is top-of-list when admin returns.

### 4.6 Admin — clear knockout team assignment (issue #6)

**Files:** `games/worldcup/routes.py` `admin_set_knockout()`, `games/worldcup/templates/worldcup/admin/set_knockout.html`.

- Route extended to handle `request.form.get('action') == 'clear'`:
  ```python
  if request.form.get('action') == 'clear':
      if match.is_completed:
          flash('Clear the match result first before clearing team assignment.', 'error')
          return redirect(url_for('worldcup.admin_set_knockout', match_id=match_id))
      match.home_team_id = None
      match.away_team_id = None
      db.session.commit()
      flash(f'Match #{match.match_number}: team assignment cleared.', 'warning')
      return redirect(url_for('worldcup.admin_dashboard'))
  ```
- Template adds a secondary `btn-outline-danger` button + `confirm()` dialog, visible **only** when at least one team is currently assigned AND the match is incomplete. When the match is completed, show a muted lock hint instead telling the admin to clear the result first.

**Invariant preserved:** `match.winner_team_id` always points to a currently-assigned team. The block-when-completed guard prevents contradictory state.

## 5. Testing

### 5.1 Unit tests — extend `tests/test_worldcup_scoring.py`

- `test_compute_team_score_events_matches_stored_base_points` — simulate a full tournament; for every team assert `sum(e.base_points for e in compute_team_score_events(t)) == t.base_points`.
- `test_compute_match_attribution_group_win` — 2–1 yields `[(winner, +3)]`.
- `test_compute_match_attribution_group_draw` — 1–1 yields both sides at `+1`.
- `test_compute_match_attribution_knockout` — R16 win yields `[(winner, +11)]`.
- `test_compute_match_attribution_incomplete` — returns `None`.
- `test_score_events_include_advancement` — group winner gets an `advancement` event at `ADVANCE_GROUP_WINNER` points.
- `test_score_events_include_podium` — champion gets a `podium` event at `KNOCKOUT_POINTS['champion']`.

### 5.2 New admin-route tests — `tests/test_worldcup_admin.py`

- `test_clear_knockout_blocked_when_match_completed` — POST `action=clear` to a completed knockout; assert flash error, state unchanged.
- `test_clear_knockout_nulls_both_teams` — POST `action=clear` to an incomplete knockout with teams assigned; assert both `home_team_id` and `away_team_id` become `None`.
- `test_admin_dashboard_lists_completed_matches` — after completing a match, assert it appears in the dashboard response body and the ordering is `updated_at DESC`.
- `test_leaderboard_hides_tiebreaker_pre_deadline` — monkey-patch `datetime.now` to a pre-deadline instant; assert `usa_goals_guess` string doesn't appear in anonymous-visitor response.
- `test_leaderboard_shows_tiebreaker_post_deadline` — symmetric check.

### 5.3 Type checking

- `venv/bin/pyright` must remain at 0 errors. The new `ScoreEvent` dataclass is fully typed; helper return types are declared explicitly.

### 5.4 Manual verification

Re-run the following sections from `Human End-to-End Test Script.md`:
- 5A (tiebreaker hidden pre-deadline, visible post-deadline)
- 6 (CT caption on schedule)
- 7B (auto-winner derivation; attribution chips on schedule; drill-down on player detail)
- 7C (dashboard "Completed Matches" section exposes edit link)
- 7D (clear knockout button works; blocked when result recorded)

## 6. File Map

**New:**
- `tests/test_worldcup_admin.py`
- `games/worldcup/templates/worldcup/_pick_row.html`

**Modified (Python):**
- `games/worldcup/services/scoring.py`
- `games/worldcup/routes.py`
- `tests/test_worldcup_scoring.py`

**Modified (templates):**
- `games/worldcup/templates/worldcup/leaderboard.html`
- `games/worldcup/templates/worldcup/schedule.html`
- `games/worldcup/templates/worldcup/player_detail.html`
- `games/worldcup/templates/worldcup/picks.html`
- `games/worldcup/templates/worldcup/admin/dashboard.html`
- `games/worldcup/templates/worldcup/admin/match_result.html`
- `games/worldcup/templates/worldcup/admin/set_knockout.html`

**Modified (CSS):**
- `static/css/style.css` — inside the existing `/* === WORLD CUP FANTASY POOL === */` section: `.match-points-chip`, `.score-events-list`, `.pick-accordion`, `.pick-accordion-toggle`, `@keyframes wc-auto-pulse`.

## 7. Implementation Sequence (finalized in writing-plans)

Rough order (final plan will refine):

1. Add `ScoreEvent` dataclass + derive helpers to `scoring.py` + unit tests (TDD).
2. Schedule attribution chip (route + template + CSS).
3. Player detail accordion + shared `_pick_row.html` partial (+ picks.html parity).
4. Leaderboard tiebreaker conditional.
5. Schedule CT caption.
6. Admin dashboard completed-matches section + route query.
7. Admin match-result auto-winner JS + pulse animation.
8. Admin set-knockout clear action + template button + admin-route tests.
9. Reset `TOURNAMENT_DEADLINE_UTC` in `games/worldcup/constants.py` to the real kickoff date (final step).
10. Full manual re-test of sections 5A, 6, 7B, 7C, 7D.

---

**End of spec.**
