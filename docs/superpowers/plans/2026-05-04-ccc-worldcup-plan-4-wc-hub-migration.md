# Spec C — Plan 4: WC Hub migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `worldcup.index` from a single 312-line inline-branching template to a Spec-B-style state-shell — `home_shell.html` + 4 per-state partials + a new `games/worldcup/services/home_context.py` builder, dispatched on a 4-state resolver (`out`/`pre`/`live`/`post`). Side quests: lift `_stage_label` to a WC-scoped module; extract Plan 3's trend helpers to a shared service; add a state-keyed voice copy module.

**Architecture:** Mirrors Spec B's platform-home pattern (`core/main/home_context.build_home_context`) scoped to the WC blueprint. The route shrinks to a thin dispatcher; each state builder returns a flat dict consumed by `**ctx` in its partial. Shared infrastructure (Plan 2's `compute_rank_neighbors`, the lifted `stage_label`, the extracted trend helpers, the new voice copy module) keeps each builder focused on its own state shape. No game rules, scoring, or route mutation logic changes.

**Tech Stack:** Bootstrap 5.3, Jinja2, vanilla CSS, SQLAlchemy 2.0, Chart.js 4.4 (untouched). WC palette + `.wc-*` foundation utilities live on `main` from Plan 1's commit `6434cae`. Plans 2 + 3 already shipped — `compute_rank_neighbors` (Plan 2 commit `9df1a21`), the leaderboard payload extension + trend helpers (Plan 3 squash-merge `44d05ca`), and `team_detail` route + ownership privacy invariant (Plan 2). `WorldCupRankSnapshot` is the trend data source; `flask worldcup snapshot-ranks` (with `--backfill N`) is the existing seeding CLI.

**Spec reference:** `docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md` §9 (Plan 4) and §5 (cross-cutting decisions).

**Cross-plan dependency note:** This plan **completes** the `_stage_label` lift that Plan 3 deferred. After Plan 4 merges, `core/main/home_context._stage_label` and the inline `from core.main.home_context import _stage_label` in `team_detail()` (routes.py:648) both move to importing from `games.worldcup.services.stage`. Tournament-level phase (`_derive_tournament_phase`) stays in `routes.py` per CLAUDE.md "phase ≠ stage" — they're distinct value spaces and lifting both into one module would re-blur what we deliberately keep separate.

---

## Execution plan — 5 batches with `/clear` between

**This plan is 16 tasks — too much for one session.** Execute in 5 batches; `/clear` between each. After clear, the next session re-orients via: read this plan, `git log --oneline -10`, `git status`, `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q` baseline.

| Batch | Tasks | Mode | Section |
|---|---|---|---|
| **1** | 0, 1, 2 | T0 inline; T1, T2 subagent | Worktree + Section A (lifts/extracts, no behavior change) |
| **2** | 3, 4, 5 | All subagent | Section B (foundation modules) + Section C scaffolding |
| **3** | 6, 7, 8, 9 | All subagent (one per task) | Section C builders (the 4 state context builders) |
| **4** | 10, 11, 12, 13 | All subagent (one per task) | Section D (shell + 4 partials) |
| **5** | 14, 15 | All inline | Section E cutover (route swap, manual smoke matrix) + final PR/CR cycle |

**Per-batch end gate:** full `pytest tests/ -q` green + `pyright games/worldcup/` clean + all expected commits landed. If any fail, fix before `/clear` — never clear over a red baseline.

**Subagent worktree perms:** before any subagent Edit/Write on the worktree path, ensure `.claude/settings.local.json` has the worktree pre-approved (per `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/feedback_subagent_worktree_perms.md`). The Batch 1 driver handles this inline after Task 0.

**Hybrid rationale:**
- **Subagents in B1 mid → B4**: mechanical, well-specified, TDD-disciplined work. Subagents get fresh context per task and the two-stage review pattern catches issues that pure inline execution misses (Plan 3 lesson).
- **Inline at B1 start (T0)**: worktree setup needs eyeballs on git state.
- **Inline at B5**: cutover (T14) is judgment-heavy with a manual smoke matrix; PR (T15) is interactive with unpredictable CodeRabbit cycles.

**Recommended cadence:** don't attempt all 5 batches in one sitting. Natural pauses: B1+B2 in one session (foundation in place), B3 alone (largest cognitive load), B4+B5 in a final session (templates → cutover → PR).

---

## Pre-flight

### Task 0: Worktree setup + baseline verification

**Files:** none modified yet. This task creates the working environment.

- [ ] **Step 1: Create the worktree branch off main**

```bash
cd /Users/bhagstrom/fantasy-platform
git fetch origin main
git worktree add -b redesign/ccc-worldcup-plan4 ../fantasy-platform-ccc-wc-plan4 origin/main
cd ../fantasy-platform-ccc-wc-plan4
```

Expected: new directory `../fantasy-platform-ccc-wc-plan4` exists; `git status` reports clean working tree on branch `redesign/ccc-worldcup-plan4`.

- [ ] **Step 2: Verify Plans 1, 2, 3 foundations are on main**

```bash
git log --oneline -8
grep -n "wc-eyebrow\|wc-card\|page-hero.wc-hero-grad" static/css/style.css | head -5
grep -n "compute_rank_neighbors" games/worldcup/services/ranking.py
grep -n "WorldCupRankSnapshot" games/worldcup/models.py
grep -n "_show_trend_column\|_compute_trend_by_enrollment" games/worldcup/routes.py
grep -n "team_detail" templates/base.html
grep -n "_stage_label" core/main/home_context.py
```

Expected: log shows recent merges including Plan 3 (`44d05ca`); style.css contains all foundation utilities; `compute_rank_neighbors` defined in `ranking.py`; `WorldCupRankSnapshot` model exists; both trend helpers exist in `routes.py`; sub-nav references `worldcup.team_detail`; `_stage_label` exists in `core/main/home_context.py`. If any are missing, you are not branched off the right `main` — stop and reconcile.

- [ ] **Step 3: Verify baseline tests pass before changing anything**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: all baseline tests pass (Plan 3's merge brought the suite to 191/191; subsequent merges may shift this — the absolute count doesn't matter, just that everything is green). If any fail, stop and investigate — they are baseline regressions, not introduced by this plan.

- [ ] **Step 4: Verify pyright is clean on the WC blueprint**

```bash
venv/bin/pyright games/worldcup/
```

Expected: 0 errors.

- [ ] **Step 5: Confirm spec + Plan 3 plan files are accessible (cross-references)**

```bash
test -f docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md && echo "spec present"
test -f docs/superpowers/plans/2026-05-04-ccc-worldcup-plan-3-public-analytics.md && echo "plan3 present"
```

Expected: both lines print.

---

## Section A — Pre-work (lifts and extracts, no behavior change)

### Task 1: Lift `_stage_label` to `games/worldcup/services/stage.py`

`_stage_label()` currently lives in `core/main/home_context.py` (lines 71–81). It maps `WorldCupMatch.stage` codes to display labels — a WC-specific helper sitting in cross-game code per Spec B's introduction. Plan 4 lifts it to a WC-scoped module, drops the leading underscore (it's now a public helper), and updates all callers. **Tournament-level phase** (`_derive_tournament_phase` in `games/worldcup/routes.py:76`) is **NOT** lifted — distinct value space per CLAUDE.md.

**Files:**
- Create: `games/worldcup/services/stage.py`
- Create: `tests/test_worldcup_stage.py`
- Modify: `core/main/home_context.py` (remove `_stage_label` definition; import + alias from new module)
- Modify: `games/worldcup/routes.py:646-660` (replace inline `from core.main.home_context import _stage_label` with new import)

- [ ] **Step 1: Write the failing test**

Create `tests/test_worldcup_stage.py`:

```python
"""Tests for games.worldcup.services.stage.stage_label.

Single SSoT for mapping WorldCupMatch.stage codes to display labels.
NOT to be confused with tournament-level phase ('pre_tournament' /
'group_stage' / 'knockout' / 'completed') — that's _derive_tournament_phase
in routes.py, a different value space per CLAUDE.md.
"""
import pytest

from games.worldcup.services.stage import stage_label


@pytest.mark.parametrize('code,expected', [
    ('group', 'Group Stage'),
    ('R32', 'Round of 32'),
    ('R16', 'Round of 16'),
    ('QF', 'Quarterfinals'),
    ('SF', 'Semifinals'),
    ('third_place', 'Third-Place Match'),
    ('final', 'The Final'),
])
def test_stage_label_known_codes(code, expected):
    assert stage_label(code) == expected


def test_stage_label_unknown_code_falls_back_to_group_stage():
    """Defensive default — matches the pre-lift behavior."""
    assert stage_label('mystery') == 'Group Stage'


def test_stage_label_does_not_mangle_all_caps():
    """Regression: Jinja's |title filter mangles 'SF' -> 'Sf'.
    stage_label() must preserve the canonical display form."""
    assert stage_label('SF') == 'Semifinals'
    assert stage_label('QF') == 'Quarterfinals'
    assert stage_label('R32') == 'Round of 32'


def test_stage_label_does_not_mangle_underscores():
    """Regression: Jinja's |title filter renders 'third_place' -> 'Third_Place'."""
    assert stage_label('third_place') == 'Third-Place Match'
```

- [ ] **Step 2: Run test to verify it fails**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_stage.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'games.worldcup.services.stage'`.

- [ ] **Step 3: Create the new module**

Create `games/worldcup/services/stage.py`:

```python
"""Stage-label SSoT for WorldCupMatch.stage codes.

This is the single source of truth for mapping a WorldCupMatch.stage value
('group' | 'R32' | 'R16' | 'QF' | 'SF' | 'third_place' | 'final') to its
display label. Templates must NOT use `match.stage|title` — Jinja's
|title filter mangles ALL-CAPS ('SF' -> 'Sf', 'QF' -> 'Qf') and underscored
values ('third_place' -> 'Third_Place'). Plumb this helper through the
context dict instead.

NOT to be confused with tournament-level phase
('pre_tournament' | 'group_stage' | 'knockout' | 'completed'), which lives
in games/worldcup/routes._derive_tournament_phase. That's a different
value space per the CLAUDE.md "Tournament current_phase != WorldCupMatch.stage"
rule — distinct semantics, distinct callers, not co-located here.
"""


def stage_label(stage: str) -> str:
    """Map WorldCupMatch.stage to a display label.

    Unknown codes fall back to 'Group Stage' (defensive default — matches
    the legacy behavior of the underscored helper this replaced in
    core/main/home_context).
    """
    return {
        'group': 'Group Stage',
        'R32': 'Round of 32',
        'R16': 'Round of 16',
        'QF': 'Quarterfinals',
        'SF': 'Semifinals',
        'third_place': 'Third-Place Match',
        'final': 'The Final',
    }.get(stage, 'Group Stage')
```

- [ ] **Step 4: Run the new test to verify it passes**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_stage.py -v
```

Expected: 4 tests pass (3 are parametrized into 7 cases — total 10 PASSED).

- [ ] **Step 5: Update `core/main/home_context.py` to import from the new module**

Edit `core/main/home_context.py`:

Remove the `_stage_label` function definition (lines 71–81). Add this import alongside the existing imports near the top of the file:

```python
from games.worldcup.services.stage import stage_label as _stage_label
```

The alias `_stage_label` preserves all existing call sites in this file (lines 305, 310, plus any others). The aliased import is intentional — it avoids touching the `_stage_label` references throughout the rest of `home_context.py`. Future cleanup may rename them, but that's not Plan 4's scope.

- [ ] **Step 6: Update `games/worldcup/routes.py` `team_detail` route to use the new module**

Edit `games/worldcup/routes.py`:

Find the inline import in the `team_detail` route (currently at line 648):

```python
    # Inline _stage_label so we don't depend on core/main internals from a game blueprint.
    # If Plan 4 lifts _stage_label() into games/worldcup/services/stage.py, swap to that import.
    from core.main.home_context import _stage_label
```

Replace with a top-of-file import. Add to the existing imports near the top of `routes.py` (alongside the other `from games.worldcup.services...` imports around lines 27–43):

```python
from games.worldcup.services.stage import stage_label
```

Then in the `team_detail` route, remove the inline `from core.main.home_context import _stage_label` line and update the `render_template(...)` call to pass `stage_label=stage_label` (no underscore — same name as the imported symbol).

The `team_detail.html` template currently calls `{{ stage_label(match.stage) }}` (line 110) — that stays unchanged because the dict key is still `stage_label`.

- [ ] **Step 7: Verify all callers were updated**

```bash
grep -n "_stage_label\|stage_label" core/main/home_context.py games/worldcup/routes.py games/worldcup/services/stage.py
```

Expected:
- `core/main/home_context.py` — import alias line + the existing `_stage_label(...)` calls (now aliased)
- `games/worldcup/routes.py` — top-of-file import + `stage_label=stage_label` in `team_detail`
- `games/worldcup/services/stage.py` — function definition

No remaining `from core.main.home_context import _stage_label` anywhere.

```bash
grep -rn "from core.main.home_context import _stage_label" .
```

Expected: no matches.

- [ ] **Step 8: Run the full test suite to confirm no regressions**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: all baseline tests still pass + new `test_worldcup_stage.py` 10 cases pass. Both `tests/test_worldcup_team_detail.py` (Plan 2's tests using `stage_label` in the template) and `tests/test_home_context.py` (Spec B's tests using `_stage_label` aliased) must remain green.

- [ ] **Step 9: Run pyright to catch any unresolved references**

```bash
venv/bin/pyright core/main/home_context.py games/worldcup/routes.py games/worldcup/services/stage.py
```

Expected: 0 errors.

- [ ] **Step 10: Commit**

```bash
git add games/worldcup/services/stage.py tests/test_worldcup_stage.py core/main/home_context.py games/worldcup/routes.py
git commit -m "refactor(wc): lift _stage_label to games/worldcup/services/stage

- New module: games/worldcup/services/stage.py exposes stage_label() as
  the single SSoT for WorldCupMatch.stage display labels.
- core/main/home_context aliases the new symbol back to _stage_label to
  preserve existing call sites without touching them.
- team_detail route swaps its inline import for a top-of-file one.
- Tournament-level phase (_derive_tournament_phase in routes.py) stays put
  per CLAUDE.md (distinct value space).

Plan 4 prep work — no behavior change."
```

---

### Task 2: Extract trend helpers to `games/worldcup/services/trends.py`

Plan 3 left `_show_trend_column()` and `_compute_trend_by_enrollment()` inline in `games/worldcup/routes.py` (lines 399–471). Plan 4's `_context_live` builder needs the same helpers. Routes is already 1178 lines; extracting now keeps the SSoT honest and avoids cross-importing private symbols.

**Naming**: drop the leading underscore — they become public service functions. `show_trend_column()` and `compute_trend_by_enrollment()`. The leaderboard route updates its imports in lockstep.

**Files:**
- Create: `games/worldcup/services/trends.py`
- Create: `tests/test_worldcup_trends.py`
- Modify: `games/worldcup/routes.py` — remove `_show_trend_column` + `_compute_trend_by_enrollment` definitions; update `leaderboard()` to call from new module

- [ ] **Step 1: Write the failing tests**

Create `tests/test_worldcup_trends.py`:

```python
"""Tests for games.worldcup.services.trends.

Two functions extracted from routes.py for reuse by both leaderboard()
and the new home_context._context_live builder:
- show_trend_column() — global gate, count(distinct captured_date) >= 7,
  scoped to active SEASON_YEAR via WorldCupEnrollment join
- compute_trend_by_enrollment(ids) — per-enrollment delta vs latest
  captured_date snapshot; None when no snapshot exists
"""
import pytest
from datetime import date, timedelta

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment, WorldCupRankSnapshot
from games.worldcup.services.trends import (
    show_trend_column, compute_trend_by_enrollment,
)


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(email='u@test'):
    u = User(email=email, password_hash='x', display_name='U')
    db.session.add(u)
    db.session.flush()
    return u


def _make_enrollment(user, total_score=0.0, season_year=SEASON_YEAR):
    e = WorldCupEnrollment(
        user_id=user.id, season_year=season_year, total_score=total_score,
    )
    db.session.add(e)
    db.session.flush()
    return e


def _seed_snapshots(enrollment, days_back, total_score=0.0, rank=1):
    """Insert one snapshot per day in days_back (a list of int days back from today)."""
    today = date.today()
    for d in days_back:
        s = WorldCupRankSnapshot(
            enrollment_id=enrollment.id,
            captured_date=today - timedelta(days=d),
            total_score=total_score,
            rank=rank,
        )
        db.session.add(s)
    db.session.flush()


def test_show_trend_column_false_when_no_snapshots(app):
    assert show_trend_column() is False


def test_show_trend_column_false_when_fewer_than_seven_distinct_days(app):
    user = _make_user()
    enr = _make_enrollment(user)
    _seed_snapshots(enr, days_back=[0, 1, 2, 3, 4, 5])  # 6 distinct days
    db.session.commit()
    assert show_trend_column() is False


def test_show_trend_column_true_when_seven_distinct_days(app):
    user = _make_user()
    enr = _make_enrollment(user)
    _seed_snapshots(enr, days_back=[0, 1, 2, 3, 4, 5, 6])  # 7 distinct days
    db.session.commit()
    assert show_trend_column() is True


def test_show_trend_column_scoped_to_active_season(app):
    """Snapshots from a prior cup must not satisfy the current-cup gate."""
    user = _make_user()
    prior_enr = _make_enrollment(user, season_year=SEASON_YEAR - 4)
    _seed_snapshots(prior_enr, days_back=[0, 1, 2, 3, 4, 5, 6])  # 7 days, prior season
    db.session.commit()
    assert show_trend_column() is False


def test_compute_trend_by_enrollment_returns_none_when_no_history(app):
    user = _make_user()
    enr = _make_enrollment(user, total_score=42.0)
    db.session.commit()
    result = compute_trend_by_enrollment([enr.id])
    assert result == {enr.id: None}


def test_compute_trend_by_enrollment_uses_latest_snapshot(app):
    """trend = current_score - latest_snapshot_score (latest = MAX captured_date)."""
    user = _make_user()
    enr = _make_enrollment(user, total_score=50.0)
    today = date.today()
    db.session.add(WorldCupRankSnapshot(
        enrollment_id=enr.id, captured_date=today - timedelta(days=3),
        total_score=30.0, rank=5,
    ))
    db.session.add(WorldCupRankSnapshot(
        enrollment_id=enr.id, captured_date=today - timedelta(days=1),
        total_score=45.0, rank=3,
    ))
    db.session.commit()
    result = compute_trend_by_enrollment([enr.id])
    assert result == {enr.id: 5.0}  # 50 - 45 = 5


def test_compute_trend_by_enrollment_handles_empty_input(app):
    assert compute_trend_by_enrollment([]) == {}


def test_compute_trend_by_enrollment_batches_multiple_ids(app):
    user_a = _make_user('a@test')
    user_b = _make_user('b@test')
    enr_a = _make_enrollment(user_a, total_score=20.0)
    enr_b = _make_enrollment(user_b, total_score=10.0)
    today = date.today()
    db.session.add(WorldCupRankSnapshot(
        enrollment_id=enr_a.id, captured_date=today - timedelta(days=2),
        total_score=15.0, rank=1,
    ))
    db.session.add(WorldCupRankSnapshot(
        enrollment_id=enr_b.id, captured_date=today - timedelta(days=1),
        total_score=8.0, rank=2,
    ))
    db.session.commit()
    result = compute_trend_by_enrollment([enr_a.id, enr_b.id])
    assert result == {enr_a.id: 5.0, enr_b.id: 2.0}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_trends.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'games.worldcup.services.trends'`.

- [ ] **Step 3: Create the new module**

Create `games/worldcup/services/trends.py`:

```python
"""World Cup Fantasy Pool — Trend helpers
==========================================
Snapshot-derived helpers shared across surfaces:
- leaderboard.html Trend column (Plan 3)
- worldcup home _live state trend payload (Plan 4)

The "show trend column" gate uses a season-scoped count of distinct
captured_date values from WorldCupRankSnapshot. Without the season filter
(joined via WorldCupEnrollment.season_year == SEASON_YEAR), a prior cup's
snapshots would falsely satisfy the gate at the start of the next one —
that bug was caught in PR #7 (Plan 3) and is locked by
tests/test_worldcup_leaderboard.py::test_trend_column_gate_scoped_to_active_season.

The "compute trend" helper resolves "latest snapshot per enrollment" by
MAX(captured_date) — SQLite-friendly subquery, no window functions.
"""
from sqlalchemy import distinct, func

from extensions import db
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment, WorldCupRankSnapshot


def show_trend_column() -> bool:
    """True iff count(distinct captured_date) >= 7 in the active season.

    Single global gate (not per-user) per Plan 3 ambiguity-A1 resolution.
    Mirrors Spec B's >= 7 gating on the home-page sparkline.
    """
    distinct_days = (
        db.session.query(func.count(distinct(WorldCupRankSnapshot.captured_date)))
        .join(
            WorldCupEnrollment,
            WorldCupEnrollment.id == WorldCupRankSnapshot.enrollment_id,
        )
        .filter(WorldCupEnrollment.season_year == SEASON_YEAR)
        .scalar() or 0
    )
    return distinct_days >= 7


def compute_trend_by_enrollment(enrollment_ids):
    """For each enrollment id, return current_score - latest_snapshot_score.

    Latest = MAX(captured_date) per enrollment. Returns None for enrollments
    with no snapshot history (template renders '—').

    One round-trip — pull the latest snapshot per enrollment via a
    (enrollment_id, MAX(captured_date)) subquery joined back for total_score.
    Returns dict[int, float | None] keyed by enrollment id.
    """
    if not enrollment_ids:
        return {}

    latest_dates = (
        db.session.query(
            WorldCupRankSnapshot.enrollment_id.label('eid'),
            func.max(WorldCupRankSnapshot.captured_date).label('max_date'),
        )
        .filter(WorldCupRankSnapshot.enrollment_id.in_(enrollment_ids))
        .group_by(WorldCupRankSnapshot.enrollment_id)
        .subquery()
    )

    rows = (
        db.session.query(
            WorldCupRankSnapshot.enrollment_id,
            WorldCupRankSnapshot.total_score,
        )
        .join(
            latest_dates,
            (WorldCupRankSnapshot.enrollment_id == latest_dates.c.eid) &
            (WorldCupRankSnapshot.captured_date == latest_dates.c.max_date),
        )
        .all()
    )

    snapshot_score_by_eid = {eid: score for eid, score in rows}

    enrollments_by_id = {
        e.id: e for e in WorldCupEnrollment.query
        .filter(WorldCupEnrollment.id.in_(enrollment_ids))
        .all()
    }

    trend = {}
    for eid in enrollment_ids:
        snap = snapshot_score_by_eid.get(eid)
        enr = enrollments_by_id.get(eid)
        if snap is None or enr is None:
            trend[eid] = None
        else:
            trend[eid] = round(enr.total_score - snap, 2)
    return trend
```

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_trends.py -v
```

Expected: 8 tests PASSED.

- [ ] **Step 5: Update `games/worldcup/routes.py` to import from the new module**

Edit `games/worldcup/routes.py`:

1. **Remove** the two helper definitions (`_show_trend_column` lines 399–417 and `_compute_trend_by_enrollment` lines 420–471).

2. **Add** these imports near the top of the file (alongside the existing `from games.worldcup.services.*` imports around lines 27–43):

```python
from games.worldcup.services.trends import (
    show_trend_column, compute_trend_by_enrollment,
)
```

3. **Update call sites** in `leaderboard()`:
   - `_show_trend_column()` → `show_trend_column()`
   - `_compute_trend_by_enrollment(...)` → `compute_trend_by_enrollment(...)`

   (There are two calls in `leaderboard()`. Find them with `grep -n "_show_trend_column\|_compute_trend_by_enrollment" games/worldcup/routes.py`.)

4. **Trim now-unused imports**: if `distinct` and `func` are no longer used elsewhere in `routes.py`, remove them from the `from sqlalchemy import ...` line at the top. Do `grep -n "distinct(\|func\." games/worldcup/routes.py` to check before deleting.

- [ ] **Step 6: Run the full leaderboard test suite to confirm no regressions**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_leaderboard.py tests/test_worldcup_trends.py -v
```

Expected: all leaderboard tests (Plan 3's 8+) plus 8 new trend tests PASS.

- [ ] **Step 7: Verify pyright clean on the modified files**

```bash
venv/bin/pyright games/worldcup/routes.py games/worldcup/services/trends.py
```

Expected: 0 errors.

- [ ] **Step 8: Run the full test suite**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add games/worldcup/services/trends.py tests/test_worldcup_trends.py games/worldcup/routes.py
git commit -m "refactor(wc): extract trend helpers to services/trends

- New module: games/worldcup/services/trends.py exposes show_trend_column()
  and compute_trend_by_enrollment() — both renamed without leading
  underscore (now public service functions).
- routes.py imports from the new module; leaderboard() call sites
  updated.
- Season-scoping invariant (gate joined via WorldCupEnrollment) preserved
  verbatim; tests/test_worldcup_trends.py locks it independently of the
  leaderboard route.

Plan 4 prep work — no behavior change. Reused by Plan 4's _context_live builder."
```

---

## Section B — Foundation modules (TDD)

### Task 3: Add `worldcup_hub_state(user)` 4-state resolver

`games/worldcup/services/state.worldcup_state()` returns 3 states (`'pre' | 'live' | 'post'`) and is consumed by `core/main/routes.py` for the platform home. The WC hub adds a 4th state — `'out'` — for anonymous-or-unenrolled visitors (the marketing surface). Add a thin wrapper that doesn't disturb the 3-state contract.

**Files:**
- Modify: `games/worldcup/services/state.py` — add `worldcup_hub_state(user)` + extend the `WorldCupState` Literal
- Create: `tests/test_worldcup_hub_state.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_worldcup_hub_state.py`:

```python
"""Tests for games.worldcup.services.state.worldcup_hub_state.

4-state resolver for the WC hub. 'out' overrides phase — anonymous OR
unenrolled-for-current-season users always see the marketing surface,
regardless of where the tournament is.
"""
import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.constants import SEASON_YEAR, TOURNAMENT_DEADLINE_UTC
from games.worldcup.models import WorldCupEnrollment, WorldCupMatch
from games.worldcup.services.state import worldcup_hub_state


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(email='u@test'):
    u = User(email=email, password_hash='x', display_name='U')
    db.session.add(u)
    db.session.flush()
    return u


def _enroll(user, season=SEASON_YEAR):
    e = WorldCupEnrollment(user_id=user.id, season_year=season)
    db.session.add(e)
    db.session.flush()
    return e


def test_anonymous_user_resolves_out(app):
    """None or AnonymousUserMixin → 'out'."""
    assert worldcup_hub_state(None) == 'out'


def test_authenticated_unenrolled_user_resolves_out(app):
    user = _make_user()
    db.session.commit()
    assert worldcup_hub_state(user) == 'out'


def test_authenticated_enrolled_pre_deadline_resolves_pre(app):
    user = _make_user()
    _enroll(user)
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        assert worldcup_hub_state(user) == 'pre'


def test_authenticated_enrolled_post_deadline_resolves_live_when_final_open(app):
    user = _make_user()
    _enroll(user)
    db.session.commit()
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        assert worldcup_hub_state(user) == 'live'


def test_authenticated_enrolled_resolves_post_when_final_completed(app):
    user = _make_user()
    _enroll(user)
    # Insert match #104 marked complete to flip the 'post' branch
    final = WorldCupMatch(
        match_number=104, stage='final', is_completed=True,
    )
    db.session.add(final)
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=30)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        assert worldcup_hub_state(user) == 'post'


def test_enrollment_for_prior_season_does_not_count_as_enrolled(app):
    """A user enrolled in a previous cup but not the current one is 'out'."""
    user = _make_user()
    _enroll(user, season=SEASON_YEAR - 4)
    db.session.commit()
    assert worldcup_hub_state(user) == 'out'
```

- [ ] **Step 2: Run test to verify it fails**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_hub_state.py -v
```

Expected: FAIL with `ImportError: cannot import name 'worldcup_hub_state' from 'games.worldcup.services.state'`.

- [ ] **Step 3: Add the new function to `services/state.py`**

Edit `games/worldcup/services/state.py`. Update the `WorldCupState` literal and append the new resolver:

```python
"""World Cup tournament-state detection for home-page rendering.

Two functions:
- ``worldcup_state()`` returns 'pre' | 'live' | 'post' (used by the platform
  home page in core/main/routes.py — Spec B).
- ``worldcup_hub_state(user)`` returns 'out' | 'pre' | 'live' | 'post'
  (used by the WC blueprint home — Plan 4). 'out' overrides phase: anonymous
  or unenrolled-for-current-season users always see the marketing surface.

Spec B section 4a is the canonical reference for the 3-state semantics;
Plan 4 of Spec C extends it with 'out'.
"""
import os
from datetime import datetime, timezone
from typing import Literal, Optional

from games.worldcup.constants import SEASON_YEAR, TOURNAMENT_DEADLINE_UTC
from games.worldcup.models import WorldCupMatch, WorldCupEnrollment

WorldCupState = Literal['pre', 'live', 'post']
WorldCupHubState = Literal['out', 'pre', 'live', 'post']

FINAL_MATCH_NUMBER = 104  # The Final per FIFA bracket numbering
```

(Update the imports + the `Literal` types as shown above. The new `WorldCupHubState` is exported for callers that want to type-check the hub-state branches.)

Replace the existing `now_utc()` and `worldcup_state()` definitions — they stay as-is. After `worldcup_state()`, append:

```python
def worldcup_hub_state(user) -> WorldCupHubState:
    """Resolve the WC hub state for a given user. 4-state.

    'out' overrides phase: anonymous OR unenrolled-for-current-season users
    always see the marketing surface, regardless of tournament phase.
    Otherwise delegates to worldcup_state() (3-state).

    Accepts None or any object with `is_authenticated` (Flask-Login's
    AnonymousUserMixin returns False for that attribute).
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return 'out'

    enrolled = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR,
    ).first() is not None
    if not enrolled:
        return 'out'

    return worldcup_state()
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_hub_state.py -v
```

Expected: 6 tests PASSED.

- [ ] **Step 5: Run the existing state tests to confirm no regression**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_home_context.py tests/test_home_routes.py -v
```

Expected: all green — the 3-state `worldcup_state()` contract is unchanged.

- [ ] **Step 6: Verify pyright clean**

```bash
venv/bin/pyright games/worldcup/services/state.py
```

Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add games/worldcup/services/state.py tests/test_worldcup_hub_state.py
git commit -m "feat(wc): add worldcup_hub_state(user) 4-state resolver

- 'out' overrides phase for anonymous or unenrolled-for-current-season users.
- Delegates to existing worldcup_state() for enrolled users (3-state contract
  preserved — core/main/routes.py is unaffected).
- New WorldCupHubState Literal exported for type-checking callers.

Plan 4 — foundation for the WC home_context dispatcher."
```

---

### Task 4: Create state-keyed voice copy module

The 4 builders + 4 partials need a substantial amount of state-keyed copy ("Sealed. Still amendable.", "Climbing 3 spots quietly.", etc). Centralizing it in `games/worldcup/services/voice.py` keeps partials free of hardcoded strings, makes copy testable, and gives a single point to revise tone later. Mirrors Spec B's `_tagline_for()` pattern but as a dedicated module.

**Naming convention**: a single dict `HUB_COPY` keyed by state, then by sub-key. A small accessor `hub_copy(state, key)` returns the dict at that path. Each partial gets a flat copy dict via the builder's context. The partial reads e.g. `{{ copy.eyebrow }}` rather than `{% if state == 'pre' %}...{% endif %}`.

**Files:**
- Create: `games/worldcup/services/voice.py`
- Create: `tests/test_worldcup_voice.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_worldcup_voice.py`:

```python
"""Tests for games.worldcup.services.voice.

State-keyed copy module. Tests verify the structure (every state has the
expected sub-keys), not the wording (which is allowed to evolve without
breaking tests).
"""
import pytest

from games.worldcup.services.voice import HUB_COPY, hub_copy, rank_tier


def test_hub_copy_has_all_four_states():
    assert set(HUB_COPY.keys()) == {'out', 'pre', 'live', 'post'}


def test_out_state_has_all_four_cta_variants():
    """Per spec section 9: 'guest' / 'unenrolled_pre' / 'unenrolled_live' /
    'unenrolled_post' (the last added in Plan 4 brainstorm to fill the
    spec gap)."""
    assert set(HUB_COPY['out'].keys()) == {
        'guest', 'unenrolled_pre', 'unenrolled_live', 'unenrolled_post',
    }


def test_pre_state_has_submitted_and_unsubmitted_variants():
    assert set(HUB_COPY['pre'].keys()) == {'submitted', 'unsubmitted'}


def test_live_state_has_four_rank_tier_variants():
    assert set(HUB_COPY['live'].keys()) == {'leader', 'chasing', 'mid', 'tail'}


def test_post_state_has_four_rank_tier_variants():
    assert set(HUB_COPY['post'].keys()) == {'champion', 'top_3', 'mid', 'tail'}


def test_every_leaf_dict_has_eyebrow_headline_subhead():
    """Every state/sub-state combo has the same 3 keys — partials rely
    on this structure."""
    for state, branches in HUB_COPY.items():
        for branch_key, leaf in branches.items():
            assert isinstance(leaf, dict), f'{state}/{branch_key} is not a dict'
            assert 'eyebrow' in leaf, f'{state}/{branch_key} missing eyebrow'
            assert 'headline' in leaf, f'{state}/{branch_key} missing headline'
            assert 'subhead' in leaf, f'{state}/{branch_key} missing subhead'


def test_hub_copy_accessor_returns_correct_leaf():
    leaf = hub_copy('out', 'guest')
    assert isinstance(leaf, dict)
    assert 'eyebrow' in leaf


def test_hub_copy_accessor_raises_on_unknown_state():
    with pytest.raises(KeyError):
        hub_copy('mystery', 'guest')


def test_hub_copy_accessor_raises_on_unknown_branch():
    with pytest.raises(KeyError):
        hub_copy('out', 'mystery')


@pytest.mark.parametrize('rank,total,expected', [
    (1, 10, 'leader'),
    (2, 10, 'chasing'),
    (3, 10, 'chasing'),
    (5, 10, 'mid'),
    (8, 10, 'tail'),
    (10, 10, 'tail'),
    (1, 1, 'leader'),
])
def test_rank_tier_buckets(rank, total, expected):
    """Rank tier mapping for live/post states.
    - 1 -> leader
    - 2-3 -> chasing
    - bottom 1/3 (rank > total * 2/3) -> tail
    - else -> mid
    """
    assert rank_tier(rank, total) == expected
```

- [ ] **Step 2: Run test to verify it fails**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_voice.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create the new module**

Create `games/worldcup/services/voice.py`:

```python
"""State-keyed voice copy for the WC hub.

Spec C Plan 4 introduces a 4-state hub (out/pre/live/post) with branching
sub-states inside each. Centralizing the strings here keeps partials free
of hardcoded text and makes copy revisable in one place.

Structure:
    HUB_COPY[state][branch] = {'eyebrow', 'headline', 'subhead'}

The 'out' state has 4 cta_state branches (guest, unenrolled_{pre,live,post}).
'pre' has 2 (submitted, unsubmitted). 'live' and 'post' have 4 rank-tier
branches each — see rank_tier() for the bucket boundaries.

Tone: Commish voice (the CCC house pattern — see Spec A's voice doctrine).
Sentence-case eyebrows are optional; uppercase happens in CSS via
.wc-eyebrow's text-transform.
"""

HUB_COPY = {
    'out': {
        'guest': {
            'eyebrow': 'The Pool Is Open',
            'headline': 'Pick 9 nations. Chase the trophy.',
            'subhead': 'Sign up to swear the Oath before the deadline.',
        },
        'unenrolled_pre': {
            'eyebrow': 'Tribute Window',
            'headline': 'Join the pool — the deadline is approaching.',
            'subhead': 'Pick 9 teams across 5 tiers. The Commish keeps score.',
        },
        'unenrolled_live': {
            'eyebrow': 'Tournament Underway',
            'headline': 'Registration is closed — but you can follow the action.',
            'subhead': 'See the leaderboard, browse rosters, follow recent results.',
        },
        'unenrolled_post': {
            'eyebrow': 'Pool Closed',
            'headline': 'The Oath is fulfilled. Meet your champion.',
            'subhead': 'See the final podium and the winning roster.',
        },
    },
    'pre': {
        'unsubmitted': {
            'eyebrow': 'Tribute Window Open',
            'headline': 'Make your picks before the deadline.',
            'subhead': 'Pick 9 teams across 5 tiers. The Commish keeps score.',
        },
        'submitted': {
            'eyebrow': 'Sealed. Still Amendable.',
            'headline': 'Your Oath is on file.',
            'subhead': 'You can amend until the deadline.',
        },
    },
    'live': {
        'leader': {
            'eyebrow': 'You Lead The Pool',
            'headline': 'The Commish takes notes.',
            'subhead': 'Hold the line.',
        },
        'chasing': {
            'eyebrow': 'In The Hunt',
            'headline': 'You are within striking distance.',
            'subhead': 'A few results away from the top.',
        },
        'mid': {
            'eyebrow': 'Mid-Pack',
            'headline': 'The Commish is watching.',
            'subhead': 'A run of green can change the picture quickly.',
        },
        'tail': {
            'eyebrow': 'Long Road Ahead',
            'headline': 'Underdogs make the season.',
            'subhead': 'Keep the faith.',
        },
    },
    'post': {
        'champion': {
            'eyebrow': 'Champion of the Pool',
            'headline': 'You won. The Oath is paid.',
            'subhead': 'See your final roster and the season recap.',
        },
        'top_3': {
            'eyebrow': 'Podium Finish',
            'headline': 'The Commish raises a glass.',
            'subhead': 'You finished on the podium.',
        },
        'mid': {
            'eyebrow': 'Season Closed',
            'headline': 'The Oath is fulfilled.',
            'subhead': 'See your final roster and the champion.',
        },
        'tail': {
            'eyebrow': 'Season Closed',
            'headline': 'There is always next cycle.',
            'subhead': 'See the champion and start plotting your return.',
        },
    },
}


def hub_copy(state: str, branch: str) -> dict:
    """Return the {eyebrow, headline, subhead} leaf for a state/branch path.

    Raises KeyError on unknown state or branch — fail loud per CLAUDE.md.
    """
    return HUB_COPY[state][branch]


def rank_tier(rank: int, total: int) -> str:
    """Bucket a rank into one of the live/post sub-state keys.

    - rank 1                     -> 'leader' (or 'champion' for post — caller
                                    swaps when state == 'post')
    - rank 2 or 3                -> 'chasing' (or 'top_3' for post)
    - bottom third (rank > total * 2 / 3)  -> 'tail'
    - everything else            -> 'mid'

    For 'post' state, the caller maps 'leader' -> 'champion' and
    'chasing' -> 'top_3' since the labels differ.
    """
    if rank == 1:
        return 'leader'
    if rank in (2, 3):
        return 'chasing'
    if total > 0 and rank > (total * 2) // 3:
        return 'tail'
    return 'mid'
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_voice.py -v
```

Expected: 9 tests + 7 parametrized cases = 16 PASSED.

- [ ] **Step 5: Verify pyright clean**

```bash
venv/bin/pyright games/worldcup/services/voice.py
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/services/voice.py tests/test_worldcup_voice.py
git commit -m "feat(wc): add HUB_COPY voice module for hub state copy

- HUB_COPY[state][branch] = {eyebrow, headline, subhead} structure with
  branches for all 4 states (out/pre/live/post) including the
  unenrolled_post case absent from the spec (Plan 4 brainstorm gap fill).
- hub_copy() accessor and rank_tier() bucket helper with full coverage.
- Tests assert structural shape, not exact wording — copy is allowed to
  evolve without breaking suites.

Plan 4 — partials read voice strings from the builder's context, not
hardcoded strings."
```

---

## Section C — Builders (TDD per state)

### Task 5: Reusable test fixture + service skeleton + dispatcher

The 4 state builders share enrollment + pick + match + snapshot fixtures. Plan 3's leaderboard tests created these inline; Plan 4 has 4 builder test files's worth of duplication if we follow the same pattern. Extract a reusable helper module (mirrors the existing `tests/_registry_helpers.py` convention) so each builder test imports the bits it needs.

This task **also** stubs `home_context.py` with the dispatcher and 4 empty builders so the dispatch test can pass before any builder has logic.

**Files:**
- Create: `tests/_worldcup_fixtures.py` (shared helpers, not a pytest fixture file — matches `tests/_registry_helpers.py` naming)
- Create: `games/worldcup/services/home_context.py` (skeleton with dispatcher + 4 stub builders)
- Create: `tests/test_worldcup_home_context.py` (dispatcher test only this task — builder tests come in Tasks 6-9)

- [ ] **Step 1: Write the failing dispatcher test**

Create `tests/test_worldcup_home_context.py`:

```python
"""Tests for games.worldcup.services.home_context.build_worldcup_home_context.

This file covers the dispatcher in Task 5; per-builder tests are added in
Tasks 6 (out), 7 (pre), 8 (live), 9 (post).
"""
import pytest

from app import create_app
from extensions import db
from games.worldcup.services.home_context import build_worldcup_home_context


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.mark.parametrize('state,expected_marker', [
    ('out', '_marker_out'),
    ('pre', '_marker_pre'),
    ('live', '_marker_live'),
    ('post', '_marker_post'),
])
def test_dispatcher_routes_to_correct_builder(app, state, expected_marker):
    """Each builder stub returns a context dict containing a unique marker
    key. Assert the dispatcher returns the right one."""
    ctx = build_worldcup_home_context(user=None, state=state)
    assert expected_marker in ctx, (
        f'state={state} expected marker {expected_marker} in context, '
        f'got keys: {list(ctx.keys())}'
    )


def test_dispatcher_raises_on_unknown_state(app):
    with pytest.raises(ValueError, match='unknown worldcup hub state'):
        build_worldcup_home_context(user=None, state='mystery')
```

- [ ] **Step 2: Run test to verify it fails**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_home_context.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create the shared fixture helper**

Create `tests/_worldcup_fixtures.py`:

```python
"""Shared World Cup test data helpers — used by Plan 4's builder tests
(tests/test_worldcup_home_context.py) and any future analytics tests.

Naming convention matches tests/_registry_helpers.py — the leading
underscore signals "test helper, not a pytest discovery file."
These are plain functions, not pytest fixtures (each test file
owns its own ``app`` fixture; helpers seed data inside it).
"""
from datetime import datetime, timezone, date, timedelta

from extensions import db
from models.user import User
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupPick, WorldCupTeam, WorldCupMatch,
    WorldCupRankSnapshot,
)


def make_user(email='u@test', display_name='U'):
    u = User(email=email, password_hash='x', display_name=display_name)
    db.session.add(u)
    db.session.flush()
    return u


def make_enrollment(user, total_score=0.0, picks_submitted=False,
                    usa_goals_guess=0, season=SEASON_YEAR, display_name=None):
    e = WorldCupEnrollment(
        user_id=user.id,
        season_year=season,
        total_score=total_score,
        picks_submitted=picks_submitted,
        usa_goals_guess=usa_goals_guess,
        display_name=display_name,
    )
    db.session.add(e)
    db.session.flush()
    return e


def make_team(fifa_code, name=None, tier=1, multiplier=1.0,
              group_letter='A', flag='🏳️'):
    t = WorldCupTeam(
        fifa_code=fifa_code,
        display_name=name or fifa_code,
        tier=tier,
        multiplier=multiplier,
        group_letter=group_letter,
        flag_emoji=flag,
    )
    db.session.add(t)
    db.session.flush()
    return t


def make_pick(enrollment, team):
    p = WorldCupPick(
        enrollment_id=enrollment.id,
        team_id=team.id,
        tier=team.tier,
    )
    db.session.add(p)
    db.session.flush()
    return p


def make_match(match_number, home_team=None, away_team=None,
               stage='group', kickoff=None, is_completed=False,
               home_score=None, away_score=None, winner_team=None):
    m = WorldCupMatch(
        match_number=match_number,
        stage=stage,
        home_team_id=home_team.id if home_team else None,
        away_team_id=away_team.id if away_team else None,
        kickoff_utc=kickoff or datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc),
        is_completed=is_completed,
        home_score=home_score,
        away_score=away_score,
        winner_team_id=winner_team.id if winner_team else None,
    )
    db.session.add(m)
    db.session.flush()
    return m


def make_snapshot(enrollment, days_back=0, total_score=0.0, rank=1):
    s = WorldCupRankSnapshot(
        enrollment_id=enrollment.id,
        captured_date=date.today() - timedelta(days=days_back),
        total_score=total_score,
        rank=rank,
    )
    db.session.add(s)
    db.session.flush()
    return s


def seed_full_tournament(num_enrollments=5, num_picks_each=9,
                         seed_snapshots=False, snapshot_days=7):
    """Create enrollments + 48 dummy teams + picks + optional snapshots.

    Returns dict with:
        users         — list[User]
        enrollments   — list[WorldCupEnrollment] in score-DESC order
        teams         — list[WorldCupTeam] (48 teams across 5 tiers)
        picks_by_enr  — dict[enrollment_id, list[WorldCupPick]]

    The ``num_picks_each`` matches TIER_PICK_COUNTS = (1, 1, 2, 2, 3) -> 9.
    Each enrollment gets distinct teams to avoid roster overlap.
    """
    # 48 teams: 5 across tier 1, 5 tier 2, 11 tier 3, 11 tier 4, 16 tier 5
    teams = []
    for tier_num, count in [(1, 5), (2, 5), (3, 11), (4, 11), (5, 16)]:
        for i in range(count):
            t = make_team(
                fifa_code=f'T{tier_num}{i:02d}',
                name=f'Tier{tier_num}-{i}',
                tier=tier_num,
                multiplier={1: 1.0, 2: 1.5, 3: 2.0, 4: 2.5, 5: 3.0}[tier_num],
                group_letter='ABCDEFGHIJKL'[i % 12],
                flag='🏳️',
            )
            teams.append(t)

    users = []
    enrollments = []
    picks_by_enr = {}
    # score descending by index — enr 0 is leader
    scores = [100.0 - i * 5 for i in range(num_enrollments)]
    for i, score in enumerate(scores):
        u = make_user(email=f'u{i}@test', display_name=f'Player{i}')
        e = make_enrollment(
            u, total_score=score, picks_submitted=True, usa_goals_guess=i,
            display_name=f'Player{i}',
        )
        users.append(u)
        enrollments.append(e)
        # 9 picks: tier 1×1, tier 2×1, tier 3×2, tier 4×2, tier 5×3
        # Pull from disjoint slices so two enrollments never share teams
        # (avoids primary-key-style collisions in any future stricter rules).
        tier_offsets = [0, 5, 10, 21, 32]   # start indices into `teams` per tier
        tier_pick_counts = [1, 1, 2, 2, 3]
        picks = []
        for tier_idx, (offset, count) in enumerate(zip(tier_offsets, tier_pick_counts)):
            for k in range(count):
                team = teams[offset + (i * count + k) % {0: 5, 1: 5, 2: 11, 3: 11, 4: 16}[tier_idx]]
                picks.append(make_pick(e, team))
        picks_by_enr[e.id] = picks

    if seed_snapshots:
        for e in enrollments:
            for d in range(snapshot_days):
                make_snapshot(
                    e, days_back=d,
                    total_score=float(e.total_score) - d * 0.5,
                    rank=enrollments.index(e) + 1,
                )

    db.session.commit()
    return {
        'users': users,
        'enrollments': enrollments,
        'teams': teams,
        'picks_by_enr': picks_by_enr,
    }
```

- [ ] **Step 4: Create the service skeleton**

Create `games/worldcup/services/home_context.py`:

```python
"""Per-state data assembly for the WC blueprint home (Spec C Plan 4).

Mirrors core/main/home_context for the platform home (Spec B). The WC home
adds a 4th state — 'out' — for anonymous-or-unenrolled visitors. State is
resolved by games.worldcup.services.state.worldcup_hub_state(user) and
passed in.

Public entry point: build_worldcup_home_context(user, state) — dispatches
to one of four private builders. Each builder returns a flat dict
consumed by the matching _home_<state>.html partial.

Each builder's return-shape contract is documented at the function level.
"""
from typing import Optional, Any

from games.worldcup.services.state import WorldCupHubState


def build_worldcup_home_context(user: Any, state: WorldCupHubState) -> dict:
    """Dispatch to the per-state context builder.

    Raises ValueError on unknown state — fail loud per CLAUDE.md.
    """
    if state == 'out':
        return _context_out(user)
    if state == 'pre':
        return _context_pre(user)
    if state == 'live':
        return _context_live(user)
    if state == 'post':
        return _context_post(user)
    raise ValueError(f'unknown worldcup hub state: {state!r}')


# =====================================================================
# Stub builders — each task in Section C replaces one of these
# with the full implementation + tests.
# =====================================================================

def _context_out(user: Optional[Any]) -> dict:
    """Stub — replaced in Task 6."""
    return {'_marker_out': True}


def _context_pre(user: Any) -> dict:
    """Stub — replaced in Task 7."""
    return {'_marker_pre': True}


def _context_live(user: Any) -> dict:
    """Stub — replaced in Task 8."""
    return {'_marker_live': True}


def _context_post(user: Any) -> dict:
    """Stub — replaced in Task 9."""
    return {'_marker_post': True}
```

- [ ] **Step 5: Run the dispatcher test to verify it passes**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_home_context.py -v
```

Expected: 4 dispatcher tests + 1 unknown-state test = 5 PASSED.

- [ ] **Step 6: Verify pyright clean**

```bash
venv/bin/pyright games/worldcup/services/home_context.py
```

Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add tests/_worldcup_fixtures.py games/worldcup/services/home_context.py tests/test_worldcup_home_context.py
git commit -m "feat(wc): scaffold home_context service + reusable test fixtures

- New module: games/worldcup/services/home_context.py with
  build_worldcup_home_context() dispatcher and 4 stub builders
  (replaced one-by-one in Tasks 6-9).
- New helper module: tests/_worldcup_fixtures.py exposes seed_full_tournament()
  and finer-grained make_* helpers; convention follows tests/_registry_helpers.py.
- Dispatcher tests assert each state routes to the right builder + unknown
  state raises ValueError.

Plan 4 — Section C scaffolding."
```

---

### Task 6: Implement `_context_out` builder

Builds the marketing surface for anonymous + unenrolled-current-season users. Branches by tournament phase to pick one of 4 `cta_state` values: `guest` (anon, pre-deadline), `unenrolled_pre`, `unenrolled_live`, `unenrolled_post`. Returns voice copy from `HUB_COPY['out'][cta_state]` plus enough data for the partial to render a tournament-aware CTA.

**Spec section 9 contract:** keys returned —
- `state` (always `'out'`)
- `cta_state` — one of `'guest'` / `'unenrolled_pre'` / `'unenrolled_live'` / `'unenrolled_post'`
- `copy` — voice dict from `hub_copy('out', cta_state)`
- `tournament_phase` — `_derive_tournament_phase()` value (consumed by the partial's phase chip)
- `entry_fee` — from `ENTRY_FEE` constant
- `total_enrolled` — count of WC enrollments for `SEASON_YEAR`
- `top_3_preview` — list of top-3 enrollments (only when `cta_state` in `unenrolled_live` or `unenrolled_post`; empty list otherwise)
- `deadline_ct` — Central Time deadline (only meaningful when `cta_state` is `guest` or `unenrolled_pre`; always set so the template can choose)
- `is_authenticated` — bool (anon vs authenticated-but-unenrolled)
- `display_name` — user's display name when authenticated, `None` when anon

**Files:**
- Modify: `games/worldcup/services/home_context.py` — replace `_context_out` stub
- Modify: `tests/test_worldcup_home_context.py` — add `_context_out` tests

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_worldcup_home_context.py`:

```python
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from games.worldcup.constants import (
    SEASON_YEAR, ENTRY_FEE, TOURNAMENT_DEADLINE_UTC,
)
from games.worldcup.services.home_context import _context_out
from tests._worldcup_fixtures import (
    make_user, make_enrollment, seed_full_tournament,
)


def test_context_out_anonymous_user_is_guest(app):
    ctx = _context_out(user=None)
    assert ctx['state'] == 'out'
    assert ctx['cta_state'] == 'guest'
    assert ctx['is_authenticated'] is False
    assert ctx['display_name'] is None


def test_context_out_authenticated_unenrolled_pre_deadline(app):
    user = make_user()
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_out(user=user)
    assert ctx['cta_state'] == 'unenrolled_pre'
    assert ctx['is_authenticated'] is True
    assert ctx['display_name'] == 'U'


def test_context_out_authenticated_unenrolled_live(app):
    user = make_user()
    db.session.commit()
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_out(user=user)
    assert ctx['cta_state'] == 'unenrolled_live'


def test_context_out_authenticated_unenrolled_post(app):
    user = make_user()
    # Mark final complete to trigger 'post' phase
    from games.worldcup.models import WorldCupMatch
    final = WorldCupMatch(match_number=104, stage='final', is_completed=True)
    db.session.add(final)
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_out(user=user)
    assert ctx['cta_state'] == 'unenrolled_post'


def test_context_out_includes_voice_copy(app):
    ctx = _context_out(user=None)
    assert 'copy' in ctx
    assert ctx['copy']['eyebrow']  # non-empty
    assert ctx['copy']['headline']
    assert ctx['copy']['subhead']


def test_context_out_includes_total_enrolled(app):
    seed_full_tournament(num_enrollments=3)
    ctx = _context_out(user=None)
    assert ctx['total_enrolled'] == 3


def test_context_out_top_3_preview_only_when_live_or_post(app):
    seed_full_tournament(num_enrollments=5)
    user = make_user(email='spectator@test')
    db.session.commit()

    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx_pre = _context_out(user=user)
    assert ctx_pre['top_3_preview'] == []

    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx_live = _context_out(user=user)
    assert len(ctx_live['top_3_preview']) == 3
    # Top-3 ordered by total_score DESC — seed gives 100 / 95 / 90 / 85 / 80
    assert [e.total_score for e in ctx_live['top_3_preview']] == [100.0, 95.0, 90.0]


def test_context_out_includes_entry_fee_and_deadline(app):
    ctx = _context_out(user=None)
    assert ctx['entry_fee'] == ENTRY_FEE
    assert ctx['deadline_ct'] is not None
```

- [ ] **Step 2: Run tests to verify they fail (or pass against the stub)**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_home_context.py -v
```

Expected: dispatcher tests still pass; the new `_context_out` tests fail with KeyError on `'cta_state'`, etc.

- [ ] **Step 3: Implement `_context_out`**

In `games/worldcup/services/home_context.py`:

1. **Add imports** at the top:

```python
from games.worldcup.constants import (
    SEASON_YEAR, ENTRY_FEE, TOURNAMENT_DEADLINE_UTC, WORLDCUP_TZ,
)
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupMatch,
)
from games.worldcup.services.state import worldcup_state
from games.worldcup.services.voice import hub_copy
```

2. **Replace** the `_context_out` stub with:

```python
def _context_out(user: Optional[Any]) -> dict:
    """Marketing surface for anonymous + authenticated-unenrolled users.

    cta_state branches on (auth, tournament phase):
    - anon                       -> 'guest'
    - authenticated, pre kickoff -> 'unenrolled_pre'
    - authenticated, live        -> 'unenrolled_live'
    - authenticated, post        -> 'unenrolled_post'
    """
    is_authenticated = (
        user is not None
        and getattr(user, 'is_authenticated', False)
    )
    display_name = (
        user.get_display_name() if is_authenticated else None
    )

    if not is_authenticated:
        cta_state = 'guest'
    else:
        # 'out' state is set; phase still relevant for cta variant
        phase_state = worldcup_state()  # 'pre' | 'live' | 'post'
        cta_state = {
            'pre': 'unenrolled_pre',
            'live': 'unenrolled_live',
            'post': 'unenrolled_post',
        }[phase_state]

    total_enrolled = WorldCupEnrollment.query.filter_by(
        season_year=SEASON_YEAR,
    ).count()

    top_3_preview = []
    if cta_state in ('unenrolled_live', 'unenrolled_post'):
        top_3_preview = (
            WorldCupEnrollment.query
            .filter_by(season_year=SEASON_YEAR)
            .order_by(
                WorldCupEnrollment.total_score.desc(),
                WorldCupEnrollment.id.asc(),
            )
            .limit(3)
            .all()
        )

    return {
        'state': 'out',
        'cta_state': cta_state,
        'copy': hub_copy('out', cta_state),
        'tournament_phase': _derive_tournament_phase(),
        'entry_fee': ENTRY_FEE,
        'total_enrolled': total_enrolled,
        'top_3_preview': top_3_preview,
        'deadline_ct': TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ),
        'is_authenticated': is_authenticated,
        'display_name': display_name,
    }
```

3. **Add a private `_derive_tournament_phase` proxy** (avoids cross-importing from `routes.py` which would create a circular dependency). Place it above `build_worldcup_home_context`:

```python
def _derive_tournament_phase() -> str:
    """Match-data derived tournament phase. Returns one of:
    'pre_tournament' | 'group_stage' | 'knockout' | 'completed'.

    Mirrors games.worldcup.routes._derive_tournament_phase exactly.
    Duplicated here (rather than imported) to avoid a circular import
    between the routes module and a service it depends on. CLAUDE.md
    "phase != stage" — distinct value space from stage_label.
    """
    completed_group = WorldCupMatch.query.filter_by(
        stage='group', is_completed=True,
    ).count()
    completed_knockout = WorldCupMatch.query.filter(
        WorldCupMatch.stage != 'group',
        WorldCupMatch.is_completed == True,  # noqa: E712
    ).count()
    final_completed = WorldCupMatch.query.filter_by(
        stage='final', is_completed=True,
    ).count()
    if final_completed > 0:
        return 'completed'
    if completed_knockout > 0:
        return 'knockout'
    if completed_group > 0:
        return 'group_stage'
    return 'pre_tournament'
```

(After Plan 4 ships, a follow-up could lift `_derive_tournament_phase` to its own module and have both `routes.py` and `home_context.py` import from it. Out of scope for Plan 4 — duplicating a 15-line read-only helper is the right tradeoff against introducing a circular dep risk now.)

- [ ] **Step 4: Run the tests**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_home_context.py -v
```

Expected: 13+ tests PASSED (5 dispatcher + 8 `_context_out`).

- [ ] **Step 5: Verify pyright clean**

```bash
venv/bin/pyright games/worldcup/services/home_context.py
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/services/home_context.py tests/test_worldcup_home_context.py
git commit -m "feat(wc): implement _context_out builder

- Branches cta_state on (auth, tournament phase): guest / unenrolled_pre /
  unenrolled_live / unenrolled_post.
- Top-3 preview only surfaces in live/post — keeps the marketing surface
  uncluttered before kickoff.
- _derive_tournament_phase duplicated locally (15 lines) to avoid a
  circular import with routes.py; same semantics.

Plan 4 — Section C builder 1 of 4."
```

---

### Task 7: Implement `_context_pre` builder

Builds the pre-deadline state for enrolled users. Branches on `picks_submitted` for the 'submitted' vs 'unsubmitted' voice variant. Surfaces a countdown card, the user's roster preview if submitted, and a top-3 leaderboard preview (zeros until kickoff).

**Spec section 9 contract:** keys returned —
- `state` (always `'pre'`)
- `branch` — `'submitted'` or `'unsubmitted'`
- `copy` — `hub_copy('pre', branch)`
- `enrollment` — the user's `WorldCupEnrollment`
- `display_name` — enrollment's display name
- `deadline_ct` — Central Time deadline
- `picks_submitted` — bool
- `user_picks` — list of `WorldCupPick` ordered (tier, team_name) when submitted; empty list otherwise
- `top_3_preview` — top-3 by total_score (zeros until kickoff)
- `total_enrolled` — count
- `tournament_phase` — phase for the shell's chip

**Files:**
- Modify: `games/worldcup/services/home_context.py` — replace `_context_pre` stub
- Modify: `tests/test_worldcup_home_context.py` — add `_context_pre` tests

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_worldcup_home_context.py`:

```python
from games.worldcup.services.home_context import _context_pre
from games.worldcup.models import WorldCupPick, WorldCupTeam


def test_context_pre_unsubmitted_branch(app):
    user = make_user()
    enr = make_enrollment(user, picks_submitted=False)
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    assert ctx['state'] == 'pre'
    assert ctx['branch'] == 'unsubmitted'
    assert ctx['picks_submitted'] is False
    assert ctx['user_picks'] == []


def test_context_pre_submitted_branch_with_picks(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    assert ctx['branch'] == 'submitted'
    assert ctx['picks_submitted'] is True
    assert len(ctx['user_picks']) == 9


def test_context_pre_user_picks_ordered_by_tier_then_team_name(app):
    seed = seed_full_tournament(num_enrollments=1)
    user = seed['users'][0]
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    tiers = [p.team.tier for p in ctx['user_picks']]
    # Tier 1 picks come first, tier 5 last
    assert tiers == sorted(tiers)


def test_context_pre_top_3_preview_renders_even_with_zero_scores(app):
    seed = seed_full_tournament(num_enrollments=5)
    # Reset scores to 0 — pre-kickoff state
    for e in seed['enrollments']:
        e.total_score = 0.0
    db.session.commit()
    user = seed['users'][0]
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    assert len(ctx['top_3_preview']) == 3
    assert all(e.total_score == 0.0 for e in ctx['top_3_preview'])


def test_context_pre_includes_voice_copy_per_branch(app):
    user = make_user()
    enr = make_enrollment(user, picks_submitted=False)
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    # Unsubmitted copy should mention "Make your picks"
    assert 'picks' in ctx['copy']['headline'].lower()


def test_context_pre_total_enrolled_count(app):
    seed_full_tournament(num_enrollments=4)
    user = make_user(email='outsider@test')
    enr = make_enrollment(user, picks_submitted=False)
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    assert ctx['total_enrolled'] == 5  # 4 + the outsider
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_home_context.py::test_context_pre_unsubmitted_branch -v
```

Expected: FAIL with `KeyError: 'state'` (the stub still returns `{'_marker_pre': True}`).

- [ ] **Step 3: Implement `_context_pre`**

In `games/worldcup/services/home_context.py`:

1. **Add imports** if not already present:

```python
from games.worldcup.models import WorldCupPick, WorldCupTeam
```

2. **Replace** the `_context_pre` stub with:

```python
def _context_pre(user: Any) -> dict:
    """Pre-deadline state for enrolled users.

    Branch: 'submitted' | 'unsubmitted' (drives voice copy variant).
    """
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR,
    ).first()
    # _context_pre is only invoked when state == 'pre' which requires the
    # user to be enrolled (worldcup_hub_state guarantees this). Asserting
    # rather than redirecting — fail loud if invariant violated.
    assert enrollment is not None, (
        f'_context_pre invoked for user {user.id} with no SEASON_YEAR enrollment'
    )

    branch = 'submitted' if enrollment.picks_submitted else 'unsubmitted'

    user_picks = []
    if enrollment.picks_submitted:
        user_picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )

    top_3_preview = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .limit(3)
        .all()
    )

    total_enrolled = WorldCupEnrollment.query.filter_by(
        season_year=SEASON_YEAR,
    ).count()

    return {
        'state': 'pre',
        'branch': branch,
        'copy': hub_copy('pre', branch),
        'enrollment': enrollment,
        'display_name': enrollment.get_display_name(),
        'deadline_ct': TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ),
        'picks_submitted': enrollment.picks_submitted,
        'user_picks': user_picks,
        'top_3_preview': top_3_preview,
        'total_enrolled': total_enrolled,
        'tournament_phase': _derive_tournament_phase(),
    }
```

- [ ] **Step 4: Run the tests**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_home_context.py -v
```

Expected: all `_context_pre` tests + previous tests PASS.

- [ ] **Step 5: Verify pyright clean**

```bash
venv/bin/pyright games/worldcup/services/home_context.py
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/services/home_context.py tests/test_worldcup_home_context.py
git commit -m "feat(wc): implement _context_pre builder

- Branches voice copy on picks_submitted (submitted vs unsubmitted).
- user_picks ordered by (tier, team_name) — matches Spec B's pre-state.
- top_3_preview always returned (renders as zeros pre-kickoff).
- Asserts enrollment exists — invariant from worldcup_hub_state.

Plan 4 — Section C builder 2 of 4."
```

---

### Task 8: Implement `_context_live` builder

The most complex builder. Combines: rank/lead deltas via `compute_rank_neighbors`, top-5 leaderboard preview, recent results with per-pick points, trend payload via the extracted trends helpers (only when `show_trend_column()` is True), and a rank-tier-keyed voice copy variant.

**Spec section 9 contract:** keys returned —
- `state` (always `'live'`)
- `branch` — `'leader' | 'chasing' | 'mid' | 'tail'` (rank-tier bucket)
- `copy` — `hub_copy('live', branch)`
- `enrollment` — user's enrollment
- `display_name`
- `your_standing` — dict from `compute_rank_neighbors` extended with `of_n` and a derived caption (mirrors the leaderboard's existing "Your Standing" payload — DRY)
- `user_picks` — list of `WorldCupPick` ordered (tier, team_name); each pick gets a transient `score_events` list via `compute_team_score_events(pick.team)` so the partial doesn't recompute scoring
- `top_5_preview` — top-5 by total_score with rank
- `recent_matches` — list of last 5 completed matches; for each, a transient `points_earned` (None unless one of the user's teams is in the match) computed via `points_for_pick_on_match`
- `stage_label` — function reference (the partial calls `{{ stage_label(match.stage) }}`)
- `trend` — dict with `show_column` (bool) + `delta` (float | None) for the user's enrollment; gated on `show_trend_column()`
- `tournament_phase`

**Files:**
- Modify: `games/worldcup/services/home_context.py` — replace `_context_live` stub
- Modify: `tests/test_worldcup_home_context.py` — add `_context_live` tests

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_worldcup_home_context.py`:

```python
from games.worldcup.services.home_context import _context_live


def test_context_live_includes_your_standing(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][0]  # rank 1
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['state'] == 'live'
    assert ctx['your_standing']['rank'] == 1
    assert ctx['your_standing']['of_n'] == 5
    assert ctx['your_standing']['lead_delta_up'] is None  # leader
    assert ctx['your_standing']['lead_delta_down'] == 5.0  # 100 - 95


def test_context_live_branch_for_leader(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][0]  # rank 1
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['branch'] == 'leader'


def test_context_live_branch_for_tail(app):
    seed = seed_full_tournament(num_enrollments=6)
    user = seed['users'][5]  # rank 6 of 6 — bottom third
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['branch'] == 'tail'


def test_context_live_branch_for_chasing(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][1]  # rank 2
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['branch'] == 'chasing'


def test_context_live_top_5_preview(app):
    seed = seed_full_tournament(num_enrollments=8)
    user = seed['users'][0]
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert len(ctx['top_5_preview']) == 5


def test_context_live_user_picks_carry_score_events(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    for pick in ctx['user_picks']:
        # transient attr — list (may be empty if no scoring data seeded)
        assert hasattr(pick, 'score_events')
        assert isinstance(pick.score_events, list)


def test_context_live_recent_matches_has_points_earned(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    # Mark a match completed so it shows up in recent_matches
    from tests._worldcup_fixtures import make_match
    teams = seed['teams']
    m = make_match(
        match_number=1, home_team=teams[0], away_team=teams[5],
        is_completed=True, home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert len(ctx['recent_matches']) >= 1
    for entry in ctx['recent_matches']:
        # entry is a dict with 'match' + 'points_earned' + 'stage_label'
        assert 'match' in entry
        assert 'points_earned' in entry  # None or float
        assert 'stage_label' in entry


def test_context_live_trend_gate_closed_when_under_seven_days(app):
    seed = seed_full_tournament(num_enrollments=2, seed_snapshots=True, snapshot_days=3)
    user = seed['users'][0]
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['trend']['show_column'] is False


def test_context_live_trend_open_when_seven_days(app):
    seed = seed_full_tournament(num_enrollments=2, seed_snapshots=True, snapshot_days=7)
    user = seed['users'][0]
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['trend']['show_column'] is True
    # delta = current 100 - latest snapshot (day 0) score
    assert ctx['trend']['delta'] is not None


def test_context_live_stage_label_callable_in_context(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert callable(ctx['stage_label'])
    assert ctx['stage_label']('SF') == 'Semifinals'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_home_context.py -v -k context_live
```

Expected: 10 `_context_live` tests fail (stub still returns marker dict).

- [ ] **Step 3: Implement `_context_live`**

In `games/worldcup/services/home_context.py`:

1. **Add imports**:

```python
from games.worldcup.services.ranking import compute_rank_neighbors
from games.worldcup.services.scoring import (
    compute_team_score_events, points_for_pick_on_match,
)
from games.worldcup.services.stage import stage_label
from games.worldcup.services.trends import (
    show_trend_column, compute_trend_by_enrollment,
)
from games.worldcup.services.voice import hub_copy, rank_tier
from games.worldcup.models import WorldCupMatch
```

2. **Replace** `_context_live` stub:

```python
def _context_live(user: Any) -> dict:
    """Live-tournament state — full dossier for an enrolled user."""
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR,
    ).first()
    assert enrollment is not None, (
        f'_context_live invoked for user {user.id} with no SEASON_YEAR enrollment'
    )

    # Rank/standing — reuses Plan 2's helper
    neighbors = compute_rank_neighbors(enrollment.id)
    total_enrolled = WorldCupEnrollment.query.filter_by(
        season_year=SEASON_YEAR,
    ).count()
    your_standing = {
        'rank': neighbors['rank'],
        'total': neighbors['points'],
        'of_n': total_enrolled,
        'lead_delta_up': neighbors['lead_delta_up'],
        'lead_delta_down': neighbors['lead_delta_down'],
    }

    # Voice tier
    branch = rank_tier(neighbors['rank'], total_enrolled)

    # Top-5 preview
    top_5 = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .limit(5)
        .all()
    )

    # User's picks with transient score_events
    user_picks = (
        WorldCupPick.query
        .filter_by(enrollment_id=enrollment.id)
        .join(WorldCupTeam)
        .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
        .all()
    )
    user_team_ids = {p.team_id for p in user_picks}
    user_picks_by_team_id = {p.team_id: p for p in user_picks}
    for pick in user_picks:
        # Transient attr — never persisted (CLAUDE.md ORM safety rule).
        pick.score_events = compute_team_score_events(pick.team)

    # Recent matches with per-match points-earned for user's roster
    recent = (
        WorldCupMatch.query
        .filter_by(is_completed=True)
        .order_by(WorldCupMatch.kickoff_utc.desc())
        .limit(5)
        .all()
    )
    recent_matches = []
    for match in recent:
        points_earned = None
        if match.home_team_id in user_team_ids:
            points_earned = points_for_pick_on_match(
                user_picks_by_team_id[match.home_team_id], match,
            )
        elif match.away_team_id in user_team_ids:
            points_earned = points_for_pick_on_match(
                user_picks_by_team_id[match.away_team_id], match,
            )
        recent_matches.append({
            'match': match,
            'points_earned': points_earned,
            'stage_label': stage_label(match.stage),
        })

    # Trend payload — gated globally
    show_trend = show_trend_column()
    delta = None
    if show_trend:
        delta_map = compute_trend_by_enrollment([enrollment.id])
        delta = delta_map.get(enrollment.id)

    return {
        'state': 'live',
        'branch': branch,
        'copy': hub_copy('live', branch),
        'enrollment': enrollment,
        'display_name': enrollment.get_display_name(),
        'your_standing': your_standing,
        'user_picks': user_picks,
        'top_5_preview': top_5,
        'recent_matches': recent_matches,
        'stage_label': stage_label,
        'trend': {'show_column': show_trend, 'delta': delta},
        'tournament_phase': _derive_tournament_phase(),
    }
```

- [ ] **Step 4: Run the tests**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_home_context.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Verify pyright clean**

```bash
venv/bin/pyright games/worldcup/services/home_context.py
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/services/home_context.py tests/test_worldcup_home_context.py
git commit -m "feat(wc): implement _context_live builder

- Reuses Plan 2's compute_rank_neighbors for Your Standing payload
  (parity with leaderboard).
- Reuses Plan 4 Task 2's extracted trend helpers (show_trend_column +
  compute_trend_by_enrollment); gate is per CLAUDE.md (season-scoped).
- compute_team_score_events powers per-pick score breakdown via transient
  pick.score_events (CLAUDE.md ORM safety: transient, not persisted).
- Recent matches build {match, points_earned, stage_label} dicts so the
  partial never falls back to match.stage|title (CLAUDE.md gotcha).
- Voice variant via rank_tier(rank, total_enrolled) — leader/chasing/mid/tail.

Plan 4 — Section C builder 3 of 4."
```

---

### Task 9: Implement `_context_post` builder

Final state: champion banner with the winning team + defeat summary, podium, user's final rank, and full roster recap with season scores. Reuses Spec B's defensive guards on `final_match` (winner FK can be None or null scores — surface the banner without a defeat summary in those cases rather than rendering nonsense).

**Spec section 9 contract:** keys returned —
- `state` (always `'post'`)
- `branch` — `'champion' | 'top_3' | 'mid' | 'tail'` (mapped from `rank_tier`: 'leader' → 'champion', 'chasing' → 'top_3')
- `copy` — `hub_copy('post', branch)`
- `enrollment`, `display_name`
- `champion_team` — winning team or `None` (if final not yet correctly resolved)
- `champion_summary` — defeat string or empty
- `final_match` — the WorldCupMatch row
- `your_final_rank` — int
- `your_climbed_n` — int (positive = climbed; from first snapshot vs final rank)
- `your_roster_recap` — list of dicts with `pick`, `tier_name`, `best_finish`, `points`, `is_champion`
- `top_3_final` — list[WorldCupEnrollment]
- `total_count` — int
- `tournament_phase`

**Files:**
- Modify: `games/worldcup/services/home_context.py` — replace `_context_post` stub
- Modify: `tests/test_worldcup_home_context.py` — add `_context_post` tests

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_worldcup_home_context.py`:

```python
from games.worldcup.services.home_context import _context_post


def test_context_post_includes_champion_team(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    teams = seed['teams']
    # Mark final completed with a winner
    from tests._worldcup_fixtures import make_match
    final = make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True,
        home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert ctx['state'] == 'post'
    assert ctx['champion_team'] is not None
    assert ctx['champion_team'].id == teams[0].id


def test_context_post_champion_summary_includes_score(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    teams = seed['teams']
    from tests._worldcup_fixtures import make_match
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True,
        home_score=3, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert '3' in ctx['champion_summary'] and '1' in ctx['champion_summary']


def test_context_post_branch_champion_for_rank_one(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][0]
    teams = seed['teams']
    from tests._worldcup_fixtures import make_match
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True, home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert ctx['branch'] == 'champion'


def test_context_post_branch_top_3_for_rank_two(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][1]
    teams = seed['teams']
    from tests._worldcup_fixtures import make_match
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True, home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert ctx['branch'] == 'top_3'


def test_context_post_roster_recap_marks_champion_pick(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    teams = seed['teams']
    # Pick that user's tier-1 team and use it as champion
    user_picks = seed['picks_by_enr'][seed['enrollments'][0].id]
    champion_pick_team = user_picks[0].team   # tier-1 pick
    from tests._worldcup_fixtures import make_match
    other = next(t for t in teams if t.id != champion_pick_team.id)
    make_match(
        match_number=104, stage='final',
        home_team=champion_pick_team, away_team=other,
        is_completed=True,
        home_score=2, away_score=0, winner_team=champion_pick_team,
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    champ_entries = [r for r in ctx['your_roster_recap'] if r['is_champion']]
    assert len(champ_entries) == 1


def test_context_post_handles_missing_final_gracefully(app):
    """If admin error left winner_team_id null on a 'completed' final,
    surface the banner without a defeat summary rather than crashing."""
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    teams = seed['teams']
    from tests._worldcup_fixtures import make_match
    # No winner_team — defensive guard path
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True, home_score=2, away_score=1,
        # winner_team intentionally omitted -> winner_team_id is None
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert ctx['champion_team'] is None
    assert ctx['champion_summary'] == ''


def test_context_post_top_3_final(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][0]
    teams = seed['teams']
    from tests._worldcup_fixtures import make_match
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True, home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert len(ctx['top_3_final']) == 3
    assert ctx['total_count'] == 5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_home_context.py -v -k context_post
```

Expected: all `_context_post` tests fail.

- [ ] **Step 3: Implement `_context_post`**

In `games/worldcup/services/home_context.py`:

1. **Add imports**:

```python
from games.worldcup.world_cup_countries import TIERS
from games.worldcup.models import WorldCupRankSnapshot
```

2. **Replace** the `_context_post` stub:

```python
def _context_post(user: Any) -> dict:
    """Tournament-complete state — champion banner, podium, roster recap."""
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR,
    ).first()
    assert enrollment is not None, (
        f'_context_post invoked for user {user.id} with no SEASON_YEAR enrollment'
    )

    # Champion data — match #104. Defensive guards mirror Spec B's
    # core/main/home_context._context_post:
    #   - winner_team_id may be None (admin error)
    #   - winner_team_id may FK to neither home nor away (admin error)
    #   - scores may be None even on is_completed=True (admin oversight)
    # In any of those cases, surface the banner WITHOUT a defeat summary
    # rather than rendering "Defeated X 0-0" or score-flipped nonsense.
    final_match = WorldCupMatch.query.filter_by(match_number=104).first()
    champion_team = None
    champion_summary = ''
    if final_match and final_match.winner_team_id:
        champion_team = final_match.winner_team
        winner_id = final_match.winner_team_id
        winner_is_home = winner_id == final_match.home_team_id
        winner_is_away = winner_id == final_match.away_team_id
        scores_present = (
            final_match.home_score is not None
            and final_match.away_score is not None
        )
        if (winner_is_home or winner_is_away) and scores_present:
            if winner_is_home:
                loser = final_match.away_team
                winner_score = final_match.home_score
                loser_score = final_match.away_score
            else:
                loser = final_match.home_team
                winner_score = final_match.away_score
                loser_score = final_match.home_score
            suffix = ''
            if final_match.penalties:
                suffix = ' on penalties'
            elif final_match.extra_time:
                suffix = ' in extra time'
            if loser:
                champion_summary = (
                    f'Defeated {loser.display_name} '
                    f'{winner_score}-{loser_score}{suffix}'
                )

    # Podium + total
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.id.asc(),
        )
        .all()
    )
    top_3_final = all_enrollments[:3]
    total_count = len(all_enrollments)

    your_final_rank = next(
        (i + 1 for i, e in enumerate(all_enrollments) if e.id == enrollment.id),
        None,
    )

    # Climbed-N — first snapshot vs final rank
    snapshots = (
        WorldCupRankSnapshot.query
        .filter_by(enrollment_id=enrollment.id)
        .order_by(WorldCupRankSnapshot.captured_date.asc())
        .all()
    )
    your_climbed_n = None
    if snapshots and your_final_rank:
        your_climbed_n = snapshots[0].rank - your_final_rank

    # Roster recap
    picks = (
        WorldCupPick.query
        .filter_by(enrollment_id=enrollment.id)
        .join(WorldCupTeam)
        .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
        .all()
    )
    your_roster_recap = []
    for pick in picks:
        your_roster_recap.append({
            'pick': pick,
            'tier_name': TIERS[pick.tier]['name'],
            'best_finish': pick.team.best_finish or 'Group',
            'points': pick.multiplied_points,
            'is_champion': champion_team is not None and pick.team_id == champion_team.id,
        })

    # Voice variant: 'leader' -> 'champion', 'chasing' -> 'top_3', else passthrough
    raw_branch = rank_tier(your_final_rank or total_count, total_count)
    branch = {
        'leader': 'champion',
        'chasing': 'top_3',
    }.get(raw_branch, raw_branch)

    return {
        'state': 'post',
        'branch': branch,
        'copy': hub_copy('post', branch),
        'enrollment': enrollment,
        'display_name': enrollment.get_display_name(),
        'champion_team': champion_team,
        'champion_summary': champion_summary,
        'final_match': final_match,
        'your_final_rank': your_final_rank,
        'your_climbed_n': your_climbed_n,
        'your_roster_recap': your_roster_recap,
        'top_3_final': top_3_final,
        'total_count': total_count,
        'tournament_phase': _derive_tournament_phase(),
    }
```

- [ ] **Step 4: Run the tests**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_home_context.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Verify pyright clean on entire WC blueprint**

```bash
venv/bin/pyright games/worldcup/
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/services/home_context.py tests/test_worldcup_home_context.py
git commit -m "feat(wc): implement _context_post builder

- Defensive guards on final_match mirror Spec B's core/main equivalent:
  surface champion banner without defeat summary rather than rendering
  'Defeated X 0-0' or score-flipped nonsense when winner_team_id is null,
  the FK doesn't match either side, or scores are missing.
- Voice variant maps rank_tier output: 'leader' -> 'champion',
  'chasing' -> 'top_3'.
- Roster recap flags is_champion per pick.

Plan 4 — Section C builder 4 of 4 (all 4 builders complete)."
```

---

## Section D — Templates

### Task 10: Create `home_shell.html` + `_home_out.html`

The shell template is a thin wrapper that renders the page hero + phase chip + state-keyed partial inside the WC blueprint's body. The first partial — `_home_out` — is the simplest (no dossier, no roster). Bundling them into one task lets the route refactor in Task 14 swap from `index.html` to `home_shell.html` without an intermediate broken state.

**Files:**
- Create: `games/worldcup/templates/worldcup/home_shell.html`
- Create: `games/worldcup/templates/worldcup/_home_out.html`

- [ ] **Step 1: Create `home_shell.html`**

```jinja
{% extends "base.html" %}
{% block title %}World Cup Fantasy Pool{% endblock %}

{% block content %}
<div class="page-hero wc-hero-grad">
  <div class="hero-glow"></div>
  <div class="container">
    <div class="d-flex align-items-center gap-3 flex-wrap">
      <h1 class="mb-0">World Cup Fantasy Pool</h1>
      <span class="phase-indicator {% if tournament_phase in ('group_stage', 'knockout') %}active{% endif %}">
        <span class="phase-dot"></span>
        {% if tournament_phase == 'pre_tournament' %}Pre-Tournament
        {% elif tournament_phase == 'group_stage' %}Group Stage
        {% elif tournament_phase == 'knockout' %}Knockout Round
        {% else %}Completed{% endif %}
      </span>
    </div>
    <p class="lead mb-0">
      {% if copy and copy.eyebrow %}
        <span class="wc-eyebrow">{{ copy.eyebrow }}</span>
      {% endif %}
    </p>
    {% if copy and copy.headline %}
      <h2 class="hero-headline mb-0">{{ copy.headline }}</h2>
    {% endif %}
    {% if copy and copy.subhead %}
      <p class="hero-subhead mb-0 text-muted">{{ copy.subhead }}</p>
    {% endif %}
  </div>
</div>

<div class="container pb-5">
  {% if state == 'out' %}
    {% include 'worldcup/_home_out.html' %}
  {% elif state == 'pre' %}
    {% include 'worldcup/_home_pre.html' %}
  {% elif state == 'live' %}
    {% include 'worldcup/_home_live.html' %}
  {% elif state == 'post' %}
    {% include 'worldcup/_home_post.html' %}
  {% endif %}

  {# Quick-links footer — absorbs Schedule / Groups / Rules nav demotions per spec D5 #}
  <div class="card wc-card mt-4">
    <div class="card-body">
      <div class="wc-eyebrow mb-2">Around the Pool</div>
      <div class="d-flex flex-wrap gap-2">
        <a href="{{ url_for('worldcup.schedule') }}" class="btn btn-sm btn-outline-secondary">
          <i class="bi bi-calendar3 me-1"></i>Schedule
        </a>
        <a href="{{ url_for('worldcup.groups') }}" class="btn btn-sm btn-outline-secondary">
          <i class="bi bi-grid-3x3 me-1"></i>Groups
        </a>
        <a href="{{ url_for('worldcup.rules') }}" class="btn btn-sm btn-outline-secondary">
          <i class="bi bi-book me-1"></i>Rules &amp; Scoring
        </a>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Create `_home_out.html`**

```jinja
{# Marketing surface — anonymous OR authenticated-unenrolled.
   cta_state branches: guest / unenrolled_pre / unenrolled_live / unenrolled_post.
   copy / state already in scope from the shell. #}

{# Top-3 preview only when live or post #}
{% if top_3_preview %}
<div class="card wc-card mb-4 animate-in">
  <div class="card-body">
    <div class="wc-eyebrow mb-2">Top of the Pool</div>
    <table class="table table-worldcup mb-0">
      <thead>
        <tr>
          <th style="width:50px">#</th>
          <th>Player</th>
          <th class="text-end">Points</th>
        </tr>
      </thead>
      <tbody>
        {% for e in top_3_preview %}
        <tr>
          <td><span class="wc-numeral">{{ loop.index }}</span></td>
          <td>{{ e.get_display_name() }}</td>
          <td class="text-end"><span class="wc-numeral">{{ "%.1f"|format(e.total_score) }}</span></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endif %}

<div class="card wc-card mb-4 animate-in">
  <div class="card-body p-4 text-center">
    {% if cta_state == 'guest' %}
      <div class="d-flex justify-content-center gap-2 flex-wrap">
        <a href="{{ url_for('auth.register') }}" class="btn btn-game btn-lg px-5">
          <i class="bi bi-globe2 me-2"></i>Sign Up to Join
        </a>
        <a href="{{ url_for('worldcup.rules') }}" class="btn btn-outline-secondary btn-lg px-4">
          <i class="bi bi-info-circle me-2"></i>See How It Works
        </a>
      </div>
    {% elif cta_state == 'unenrolled_pre' %}
      <div class="d-flex justify-content-center gap-2 flex-wrap">
        <a href="{{ url_for('worldcup.join') }}" class="btn btn-game btn-lg px-5">
          <i class="bi bi-globe2 me-2"></i>Join Now
        </a>
        <a href="{{ url_for('worldcup.rules') }}" class="btn btn-outline-secondary btn-lg px-4">
          <i class="bi bi-info-circle me-2"></i>See How It Works
        </a>
      </div>
      <div class="mt-3 text-muted small">
        Deadline: <strong>{{ deadline_ct.strftime('%b %-d, %Y at %-I:%M %p CT') }}</strong>
      </div>
    {% elif cta_state == 'unenrolled_live' %}
      <a href="{{ url_for('worldcup.leaderboard') }}" class="btn btn-game btn-lg px-5">
        <i class="bi bi-bar-chart me-2"></i>View the Leaderboard
      </a>
    {% elif cta_state == 'unenrolled_post' %}
      <a href="{{ url_for('worldcup.leaderboard') }}" class="btn btn-game btn-lg px-5">
        <i class="bi bi-trophy me-2"></i>See the Final Podium
      </a>
    {% endif %}

    {% if total_enrolled > 0 %}
      <div class="mt-3 text-muted small">
        {{ total_enrolled }} player{{ 's' if total_enrolled != 1 }} enrolled
      </div>
    {% endif %}
  </div>
</div>

{# Stats row — entry fee + format constants. Stays on every state's surface #}
<div class="row g-3 animate-in stagger-1">
  <div class="col-6 col-md-3">
    <div class="stat-block">
      <div class="stat-value wc-numeral">{{ total_enrolled }}</div>
      <div class="stat-label">Players</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="stat-block">
      <div class="stat-value wc-numeral">48</div>
      <div class="stat-label">Teams</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="stat-block">
      <div class="stat-value wc-numeral">9</div>
      <div class="stat-label">Picks Each</div>
    </div>
  </div>
  <div class="col-6 col-md-3">
    <div class="stat-block">
      <div class="stat-value wc-numeral">${{ entry_fee }}</div>
      <div class="stat-label">Entry Fee</div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Verify the templates render in isolation**

The shell + partial aren't wired to the route yet (Task 14 does that). Confirm the templates parse cleanly by running pyright + a Jinja-only smoke:

```bash
venv/bin/pyright games/worldcup/services/home_context.py
ENVIRONMENT=testing venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from flask import render_template_string
    # Just confirm the filenames load — no rendering
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader('games/worldcup/templates'))
    env.get_template('worldcup/home_shell.html')
    env.get_template('worldcup/_home_out.html')
    print('templates parse OK')
"
```

Expected: `templates parse OK` printed.

- [ ] **Step 4: Commit**

```bash
git add games/worldcup/templates/worldcup/home_shell.html games/worldcup/templates/worldcup/_home_out.html
git commit -m "feat(wc): add home_shell.html + _home_out.html partial

- Shell renders page-hero with .wc-hero-grad + state-keyed copy + phase chip,
  dispatches to _home_<state>.html partial, and absorbs Schedule/Groups/
  Rules nav demotions into a quick-links footer (spec D5).
- _home_out.html branches CTA on cta_state (guest / unenrolled_pre /
  unenrolled_live / unenrolled_post). Stats block reuses platform .stat-block
  with .wc-numeral.

Plan 4 Section D — 1 of 4 partials. Not yet wired to the route (Task 14)."
```

---

### Task 11: Create `_home_pre.html` partial

Pre-deadline state. Two sub-branches: `unsubmitted` (countdown + Make Picks CTA) and `submitted` (Sealed eyebrow + Amend CTA + roster preview). Top-3 preview always renders.

**Files:**
- Create: `games/worldcup/templates/worldcup/_home_pre.html`

- [ ] **Step 1: Create `_home_pre.html`**

```jinja
{# Pre-deadline state — picks open, deadline not yet passed.
   branch: 'submitted' | 'unsubmitted' (drives CTA + roster visibility).
   copy / state already in scope from the shell. #}

<div class="card wc-card mb-4 animate-in">
  <div class="card-body p-4 d-flex align-items-center justify-content-between flex-wrap gap-3">
    <div>
      <p class="mb-1 text-muted">
        Deadline: <strong>{{ deadline_ct.strftime('%b %-d, %Y at %-I:%M %p CT') }}</strong>
      </p>
    </div>
    {% if branch == 'unsubmitted' %}
      <a href="{{ url_for('worldcup.picks') }}" class="btn btn-game btn-lg">
        <i class="bi bi-pencil-square me-2"></i>Seal the Oath
      </a>
    {% else %}
      <a href="{{ url_for('worldcup.picks', edit=1) }}" class="btn btn-game px-4">
        <i class="bi bi-pencil-square me-1"></i>Amend the Oath
      </a>
    {% endif %}
  </div>
</div>

{# Roster preview — only when picks submitted #}
{% if branch == 'submitted' and user_picks %}
<div class="card wc-card mb-4 animate-in">
  <div class="card-body p-0">
    <div class="card-header">
      <span class="wc-eyebrow"><i class="bi bi-people-fill me-2"></i>Roster</span>
    </div>
    {% set picks_by_tier = {} %}
    {% for pick in user_picks %}
      {% if pick.team.tier not in picks_by_tier %}
        {% set _ = picks_by_tier.update({pick.team.tier: []}) %}
      {% endif %}
      {% set _ = picks_by_tier[pick.team.tier].append(pick) %}
    {% endfor %}
    <div class="roster-tiers p-3">
      {% for tier_num in range(1, 6) %}
      {% if tier_num in picks_by_tier %}
      <div class="roster-tier-row" style="--tier-color: var(--wc-tier{{ tier_num }});">
        <div class="roster-tier-label tier-badge tier-badge-{{ tier_num }}">T{{ tier_num }}</div>
        <div class="roster-tier-teams">
          {% for pick in picks_by_tier[tier_num] %}
          <div class="roster-team-card">
            <span class="roster-team-flag">{{ pick.team.flag_emoji }}</span>
            <span class="roster-team-name">{{ pick.team.display_name }}</span>
            <span class="roster-team-abbr">{{ pick.team.fifa_code }}</span>
            <span class="wc-multiplier-chip">×{{ pick.team.multiplier | int if pick.team.multiplier == (pick.team.multiplier | int) else pick.team.multiplier }}</span>
          </div>
          {% endfor %}
        </div>
      </div>
      {% endif %}
      {% endfor %}
    </div>
  </div>
</div>
{% endif %}

{# Top-3 preview (zeros until kickoff) #}
{% if top_3_preview %}
<div class="card wc-card mb-4 animate-in">
  <div class="card-body">
    <div class="d-flex align-items-center justify-content-between mb-2">
      <span class="wc-eyebrow"><i class="bi bi-trophy me-2"></i>Top of the Pool</span>
      <a href="{{ url_for('worldcup.leaderboard') }}" class="btn btn-sm btn-game">View All</a>
    </div>
    <table class="table table-worldcup mb-0">
      <thead>
        <tr>
          <th style="width:50px">#</th>
          <th>Player</th>
          <th class="text-end">Points</th>
        </tr>
      </thead>
      <tbody>
        {% for e in top_3_preview %}
        <tr {% if e.user_id == enrollment.user_id %}class="row-current-user"{% endif %}>
          <td><span class="wc-numeral">{{ loop.index }}</span></td>
          <td>
            <a href="{{ url_for('worldcup.player_detail', enrollment_id=e.id) }}" class="text-decoration-none fw-medium">
              {{ e.get_display_name() }}
            </a>
          </td>
          <td class="text-end"><span class="wc-numeral">{{ "%.1f"|format(e.total_score) }}</span></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% if total_enrolled > 0 and (top_3_preview | sum(attribute='total_score') == 0.0) %}
    <p class="text-muted small mb-0 mt-2">Awaiting kickoff.</p>
    {% endif %}
  </div>
</div>
{% endif %}
```

- [ ] **Step 2: Verify it parses**

```bash
ENVIRONMENT=testing venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader('games/worldcup/templates'))
    env.get_template('worldcup/_home_pre.html')
    print('parses OK')
"
```

Expected: `parses OK`.

- [ ] **Step 3: Commit**

```bash
git add games/worldcup/templates/worldcup/_home_pre.html
git commit -m "feat(wc): add _home_pre.html partial

- Branches CTA on submitted/unsubmitted (Seal vs Amend the Oath).
- Roster preview only when submitted; reuses tier-row pattern from
  legacy index.html.
- Top-3 preview with current-user highlight and zero-state caption
  ('Awaiting kickoff') when scores haven't begun.

Plan 4 Section D — 2 of 4 partials."
```

---

### Task 12: Create `_home_live.html` partial

Live state — the densest partial. Your Standing dossier (rank, points, lead deltas, voice copy), roster preview with score events, recent results with per-pick points, top-5 preview, optional trend ribbon.

**Files:**
- Create: `games/worldcup/templates/worldcup/_home_live.html`

- [ ] **Step 1: Create `_home_live.html`**

```jinja
{# Live state — deadline passed, tournament in progress.
   Available context:
     - your_standing: {rank, total, of_n, lead_delta_up, lead_delta_down}
     - copy: {eyebrow, headline, subhead}
     - branch: leader|chasing|mid|tail
     - user_picks: list[Pick] each with .score_events transient attr
     - top_5_preview, recent_matches, trend, stage_label, enrollment
#}

{# Your Standing block — hero stats #}
<div class="card wc-card mb-4 animate-in">
  <div class="card-body">
    <div class="row align-items-center g-3">
      <div class="col-md-6">
        <div class="wc-eyebrow mb-1">Your Standing</div>
        <div class="d-flex align-items-baseline gap-2">
          <span class="wc-numeral display-4">{{ your_standing.rank }}</span>
          <span class="text-muted">of {{ your_standing.of_n }}</span>
        </div>
        <div class="text-muted small mt-1">
          {% if your_standing.lead_delta_up is not none %}
            {{ your_standing.lead_delta_up }} pts from the lead
          {% endif %}
          {% if your_standing.lead_delta_up is not none and your_standing.lead_delta_down is not none %}
            ·
          {% endif %}
          {% if your_standing.lead_delta_down is not none %}
            {{ your_standing.lead_delta_down }} ahead of next
          {% endif %}
        </div>
      </div>
      <div class="col-md-6 text-md-end">
        <div class="wc-eyebrow mb-1">Points</div>
        <div class="wc-numeral display-4">{{ "%.1f"|format(your_standing.total) }}</div>
        {% if trend.show_column and trend.delta is not none %}
          <div class="small {% if trend.delta > 0 %}text-success{% elif trend.delta < 0 %}text-danger{% else %}text-muted{% endif %}">
            {% if trend.delta > 0 %}+{% endif %}{{ "%.1f"|format(trend.delta) }} since last snapshot
          </div>
        {% endif %}
      </div>
    </div>
  </div>
</div>

{# Roster preview with live scores #}
{% if user_picks %}
<div class="card wc-card mb-4 animate-in">
  <div class="card-body p-0">
    <div class="card-header d-flex align-items-center justify-content-between">
      <span class="wc-eyebrow"><i class="bi bi-people-fill me-2"></i>Roster</span>
      <a href="{{ url_for('worldcup.picks') }}" class="btn btn-sm btn-game">View Full Picks</a>
    </div>
    <div class="table-responsive">
      <table class="table table-worldcup mb-0">
        <thead>
          <tr>
            <th>Tier</th>
            <th>Team</th>
            <th class="text-end">Multiplier</th>
            <th class="text-end">Points</th>
          </tr>
        </thead>
        <tbody>
          {% for pick in user_picks %}
          <tr>
            <td><span class="wc-tier-dot tier-badge-{{ pick.team.tier }}"></span> T{{ pick.team.tier }}</td>
            <td>
              <a href="{{ url_for('worldcup.team_detail', team_id=pick.team_id) }}" class="text-decoration-none">
                {{ pick.team.flag_emoji }} {{ pick.team.display_name }}
              </a>
            </td>
            <td class="text-end"><span class="wc-multiplier-chip">×{{ pick.team.multiplier }}</span></td>
            <td class="text-end"><span class="wc-numeral">{{ "%.1f"|format(pick.multiplied_points) }}</span></td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
{% endif %}

{# Recent results with per-pick points-earned #}
{% if recent_matches %}
<div class="card wc-card mb-4 animate-in">
  <div class="card-body p-0">
    <div class="card-header">
      <span class="wc-eyebrow"><i class="bi bi-clock-history me-2"></i>Recent Results</span>
    </div>
    <div class="d-flex flex-column gap-2 p-3">
      {% for entry in recent_matches %}
      {% set m = entry.match %}
      <div class="match-result-card {% if entry.points_earned is not none %}is-roster-match{% endif %}">
        <span class="wc-eyebrow">{{ entry.stage_label }}</span>
        <span class="match-team home">{% if m.home_team %}{{ m.home_team.flag_emoji }} {{ m.home_team.display_name }}{% else %}TBD{% endif %}</span>
        <span class="match-score wc-numeral">{{ m.home_score }}-{{ m.away_score }}</span>
        <span class="match-team away">{% if m.away_team %}{{ m.away_team.flag_emoji }} {{ m.away_team.display_name }}{% else %}TBD{% endif %}</span>
        {% if entry.points_earned is not none %}
          <span class="text-success small">+{{ "%.1f"|format(entry.points_earned) }} pts</span>
        {% endif %}
      </div>
      {% endfor %}
    </div>
  </div>
</div>
{% endif %}

{# Top-5 preview #}
{% if top_5_preview %}
<div class="card wc-card mb-4 animate-in">
  <div class="card-body">
    <div class="d-flex align-items-center justify-content-between mb-2">
      <span class="wc-eyebrow"><i class="bi bi-trophy me-2"></i>Leaderboard</span>
      <a href="{{ url_for('worldcup.leaderboard') }}" class="btn btn-sm btn-game">View All</a>
    </div>
    <table class="table table-worldcup mb-0">
      <thead>
        <tr>
          <th style="width:50px">#</th>
          <th>Player</th>
          <th class="text-end">Points</th>
        </tr>
      </thead>
      <tbody>
        {% set ns = namespace(rank=0, prev_score=None) %}
        {% for e in top_5_preview %}
          {% if e.total_score != ns.prev_score %}
            {% set ns.rank = loop.index %}
          {% endif %}
          <tr {% if e.user_id == enrollment.user_id %}class="row-current-user"{% endif %}>
            <td><span class="wc-numeral">{{ ns.rank }}</span></td>
            <td>
              <a href="{{ url_for('worldcup.player_detail', enrollment_id=e.id) }}" class="text-decoration-none fw-medium">
                {{ e.get_display_name() }}
              </a>
            </td>
            <td class="text-end"><span class="wc-numeral">{{ "%.1f"|format(e.total_score) }}</span></td>
          </tr>
          {% set ns.prev_score = e.total_score %}
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endif %}
```

- [ ] **Step 2: Verify it parses**

```bash
ENVIRONMENT=testing venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader('games/worldcup/templates'))
    env.get_template('worldcup/_home_live.html')
    print('parses OK')
"
```

Expected: `parses OK`.

- [ ] **Step 3: Commit**

```bash
git add games/worldcup/templates/worldcup/_home_live.html
git commit -m "feat(wc): add _home_live.html partial

- Your Standing hero block (rank/points/lead deltas/trend) — same data
  shape as Plan 3's leaderboard 'Your Standing' for parity.
- Roster preview links each pick to /worldcup/team/<id> (Plan 2 route).
- Recent results highlight matches involving the user's roster with
  +N.N pts; stage label via context's stage_label callable (no |title).
- Top-5 preview uses dense rank (matches leaderboard).
- Trend ribbon only renders when trend.show_column gate is open.

Plan 4 Section D — 3 of 4 partials."
```

---

### Task 13: Create `_home_post.html` partial

Final state — champion banner with defeat summary, podium, your final rank + climbed-N, full roster recap with is_champion marker.

**Files:**
- Create: `games/worldcup/templates/worldcup/_home_post.html`

- [ ] **Step 1: Create `_home_post.html`**

```jinja
{# Post-tournament state — final has been marked complete.
   Available context:
     - champion_team (or None), champion_summary (string, may be empty)
     - final_match
     - your_final_rank, your_climbed_n
     - your_roster_recap: list of {pick, tier_name, best_finish, points, is_champion}
     - top_3_final, total_count
     - copy / state from shell
#}

{# Champion banner #}
{% if champion_team %}
<div class="card wc-card wc-hero-grad mb-4 animate-in">
  <div class="card-body p-4 text-center">
    <div class="wc-eyebrow mb-1">Champion</div>
    <div class="display-4 mb-1">
      <span class="champion-flag">{{ champion_team.flag_emoji }}</span>
      {{ champion_team.display_name }}
    </div>
    {% if champion_summary %}
      <div class="text-muted">{{ champion_summary }}</div>
    {% endif %}
  </div>
</div>
{% endif %}

{# Your finish #}
<div class="card wc-card mb-4 animate-in">
  <div class="card-body">
    <div class="row align-items-center g-3">
      <div class="col-md-6">
        <div class="wc-eyebrow mb-1">Your Finish</div>
        <div class="d-flex align-items-baseline gap-2">
          <span class="wc-numeral display-4">{{ your_final_rank }}</span>
          <span class="text-muted">of {{ total_count }}</span>
        </div>
        {% if your_climbed_n is not none and your_climbed_n != 0 %}
          <div class="small {% if your_climbed_n > 0 %}text-success{% else %}text-danger{% endif %}">
            {% if your_climbed_n > 0 %}
              Climbed {{ your_climbed_n }} spot{{ 's' if your_climbed_n != 1 }} since the start.
            {% else %}
              Slipped {{ -your_climbed_n }} spot{{ 's' if your_climbed_n != -1 }} since the start.
            {% endif %}
          </div>
        {% endif %}
      </div>
      <div class="col-md-6 text-md-end">
        <div class="wc-eyebrow mb-1">Final Points</div>
        <div class="wc-numeral display-4">{{ "%.1f"|format(enrollment.total_score) }}</div>
      </div>
    </div>
  </div>
</div>

{# Final podium #}
{% if top_3_final %}
<div class="card wc-card mb-4 animate-in">
  <div class="card-body p-0">
    <div class="card-header">
      <span class="wc-eyebrow"><i class="bi bi-trophy me-2"></i>Final Podium</span>
    </div>
    <table class="table table-worldcup mb-0">
      <thead>
        <tr>
          <th style="width:50px">#</th>
          <th>Player</th>
          <th class="text-end">Points</th>
        </tr>
      </thead>
      <tbody>
        {% set ns = namespace(rank=0, prev_score=None) %}
        {% for e in top_3_final %}
          {% if e.total_score != ns.prev_score %}
            {% set ns.rank = loop.index %}
          {% endif %}
          <tr {% if e.user_id == enrollment.user_id %}class="row-current-user"{% endif %}>
            <td><span class="wc-numeral">{{ ns.rank }}</span></td>
            <td>
              <a href="{{ url_for('worldcup.player_detail', enrollment_id=e.id) }}" class="text-decoration-none fw-medium">
                {{ e.get_display_name() }}
              </a>
            </td>
            <td class="text-end"><span class="wc-numeral">{{ "%.1f"|format(e.total_score) }}</span></td>
          </tr>
          {% set ns.prev_score = e.total_score %}
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endif %}

{# Roster recap #}
{% if your_roster_recap %}
<div class="card wc-card mb-4 animate-in">
  <div class="card-body p-0">
    <div class="card-header">
      <span class="wc-eyebrow"><i class="bi bi-people-fill me-2"></i>Final Roster</span>
    </div>
    <div class="table-responsive">
      <table class="table table-worldcup mb-0">
        <thead>
          <tr>
            <th>Tier</th>
            <th>Team</th>
            <th>Best Finish</th>
            <th class="text-end">Points</th>
          </tr>
        </thead>
        <tbody>
          {% for r in your_roster_recap %}
          <tr {% if r.is_champion %}class="row-champion-pick"{% endif %}>
            <td>
              <span class="wc-tier-dot tier-badge-{{ r.pick.team.tier }}"></span>
              {{ r.tier_name }}
            </td>
            <td>
              <a href="{{ url_for('worldcup.team_detail', team_id=r.pick.team_id) }}" class="text-decoration-none">
                {{ r.pick.team.flag_emoji }} {{ r.pick.team.display_name }}
              </a>
              {% if r.is_champion %}
                <span class="wc-eyebrow text-warning ms-1">Champion</span>
              {% endif %}
            </td>
            <td>{{ r.best_finish }}</td>
            <td class="text-end"><span class="wc-numeral">{{ "%.1f"|format(r.points) }}</span></td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
{% endif %}
```

- [ ] **Step 2: Verify it parses**

```bash
ENVIRONMENT=testing venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader('games/worldcup/templates'))
    env.get_template('worldcup/_home_post.html')
    print('parses OK')
"
```

Expected: `parses OK`.

- [ ] **Step 3: Commit**

```bash
git add games/worldcup/templates/worldcup/_home_post.html
git commit -m "feat(wc): add _home_post.html partial

- Champion banner only renders when champion_team is non-None (defensive
  guards in builder match Spec B's pattern).
- Your Finish + climbed/slipped delta from first vs final snapshot.
- Final podium uses dense rank.
- Roster recap flags champion pick with .row-champion-pick row class +
  inline 'Champion' eyebrow.

Plan 4 Section D — 4 of 4 partials complete."
```

---

## Section E — Cutover

### Task 14: Switch route + delete legacy `index.html`

Now wire `worldcup.index()` to dispatch via `build_worldcup_home_context`. Delete the old `index.html` in the same commit so there's no dead template lingering.

**Files:**
- Modify: `games/worldcup/routes.py` — `index()` route
- Delete: `games/worldcup/templates/worldcup/index.html`

- [ ] **Step 1: Update the route**

In `games/worldcup/routes.py`:

1. **Add imports** alongside the other service imports (around lines 27–43):

```python
from games.worldcup.services.state import worldcup_hub_state
from games.worldcup.services.home_context import build_worldcup_home_context
```

2. **Replace** the `index()` route (currently lines 141–188) with:

```python
@worldcup_bp.route('/')
def index():
    """World Cup hub — dispatches to a state-keyed partial.

    State resolved by worldcup_hub_state(user) (4-state: out/pre/live/post).
    Each state's context is built by games.worldcup.services.home_context;
    home_shell.html includes the matching _home_<state>.html partial.
    """
    user = current_user if current_user.is_authenticated else None
    state = worldcup_hub_state(user)
    context = build_worldcup_home_context(user, state)
    context['state'] = state
    return render_template('worldcup/home_shell.html', **context)
```

3. **Trim now-unused imports** if any (e.g., `TOURNAMENT_DEADLINE_UTC` may still be used elsewhere; do `grep -n "TOURNAMENT_DEADLINE_UTC\|WORLDCUP_TZ" games/worldcup/routes.py` to confirm before removing).

- [ ] **Step 2: Delete the legacy template**

```bash
rm games/worldcup/templates/worldcup/index.html
```

- [ ] **Step 3: Verify nothing references the deleted template**

```bash
grep -rn "worldcup/index.html\|render_template('worldcup/index" .
```

Expected: no matches outside `.git/`.

- [ ] **Step 4: Run the full test suite**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: all green. The existing `tests/test_worldcup_admin.py` smoke tests + any tests that hit `/worldcup/` (e.g., `test_join_flows.py`) should pass against the new shell.

- [ ] **Step 5: Run pyright on the entire WC blueprint**

```bash
venv/bin/pyright games/worldcup/
```

Expected: 0 errors.

- [ ] **Step 6: Manual smoke — fire up the dev server and exercise each state**

```bash
ENVIRONMENT=development FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

Visit each combination via `WC_FAKE_NOW`. **Stop the server between runs** (Ctrl+C) so the env-var prefix takes effect.

| State + persona | Command + URL | Verify |
|---|---|---|
| `out` / guest | unset `WC_FAKE_NOW`; visit http://localhost:5099/worldcup/ logged out | Hero shows "The Pool Is Open"; primary CTA is Sign Up; no roster |
| `out` / unenrolled_pre | log in as a user with no WC enrollment; `WC_FAKE_NOW='2026-06-10T00:00:00+00:00'` | Hero shows "Tribute Window"; CTA is Join Now; deadline shown |
| `out` / unenrolled_live | log in as unenrolled; `WC_FAKE_NOW='2026-06-15T00:00:00+00:00'` | Hero shows "Tournament Underway"; CTA is View the Leaderboard; top-3 preview if seeded |
| `out` / unenrolled_post | requires final match #104 marked complete in test data; `WC_FAKE_NOW='2026-07-20T00:00:00+00:00'` | Hero shows "Pool Closed"; CTA is See the Final Podium |
| `pre` / unsubmitted | log in as enrolled-no-picks; `WC_FAKE_NOW='2026-06-10T00:00:00+00:00'` | Hero "Tribute Window Open"; CTA "Seal the Oath"; no roster |
| `pre` / submitted | log in as enrolled with picks; `WC_FAKE_NOW='2026-06-10T00:00:00+00:00'` | Hero "Sealed. Still Amendable."; CTA "Amend the Oath"; roster preview |
| `live` / mid-pack | enrolled user with picks; `WC_FAKE_NOW='2026-06-15T00:00:00+00:00'` | Your Standing block with rank + points; roster table; recent results section |
| `post` / non-champion | requires final completed in DB | Champion banner visible; Your Finish; Roster Recap with no Champion badge |

Stop the dev server.

- [ ] **Step 7: Commit**

```bash
git add games/worldcup/routes.py games/worldcup/templates/worldcup/index.html
git commit -m "feat(wc): switch worldcup.index to home_shell dispatcher

- Route shrinks from ~50 lines of inline branching to a 5-line dispatcher.
- Legacy index.html deleted; home_shell.html + 4 partials drive every state.
- worldcup_hub_state(user) + build_worldcup_home_context(user, state)
  do all the work; the route just wires them.

Plan 4 — Section E cutover. Manual smoke matrix verified across all
4 states + sub-branches via WC_FAKE_NOW."
```

---

## Final verification + PR

### Task 15: End-to-end verification + open PR

- [ ] **Step 1: Run the full test suite**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -v
```

Expected: all tests pass — baseline + Plan 4 deltas. New test files: `test_worldcup_stage.py`, `test_worldcup_trends.py`, `test_worldcup_hub_state.py`, `test_worldcup_voice.py`, `test_worldcup_home_context.py`. Don't anchor to a fixed total; the baseline shifts as other PRs land.

- [ ] **Step 2: Run pyright on the entire WC blueprint**

```bash
venv/bin/pyright games/worldcup/
```

Expected: 0 errors.

- [ ] **Step 3: Run pyright on the cross-cutting files Plan 4 touched**

```bash
venv/bin/pyright core/main/home_context.py games/worldcup/services/state.py games/worldcup/services/home_context.py games/worldcup/services/voice.py games/worldcup/services/stage.py games/worldcup/services/trends.py
```

Expected: 0 errors.

- [ ] **Step 4: Verify legacy `_stage_label` import is gone everywhere**

```bash
grep -rn "from core.main.home_context import _stage_label" .
```

Expected: no matches outside the alias line in `core/main/home_context.py` itself (which is `from games.worldcup.services.stage import stage_label as _stage_label` — that's the lift target, allowed).

```bash
grep -rn "_show_trend_column\|_compute_trend_by_enrollment" games/worldcup/routes.py
```

Expected: no matches (both extracted to `services/trends.py` without underscore).

- [ ] **Step 5: Manual visual checklist — every state Plan 4 wired**

Start the dev server with the time seam available:

```bash
ENVIRONMENT=development FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

Run Task 14 Step 6's matrix — every state + sub-branch. Plus these regression checks:

| Surface | Verify |
|---|---|
| Sub-nav `Hub` pill | Active on `/worldcup/` (Plan 1 wiring) |
| Sub-nav 375px mobile | All 6 pills (Hub · Roster · Board · Schedule · Stats · Rules) fit on one row; admin pill if applicable |
| `/worldcup/leaderboard` | Trend column behavior unchanged after trends extraction |
| `/worldcup/team/<id>` | Stage-label rendering unchanged after the lift |
| Platform home `/` | Unchanged — `core/main/home_context._stage_label` aliasing preserved every existing call site |
| Fast smoke for `worldcup.index` errors | Tail `flask run` console for tracebacks while clicking through states |

Stop the server.

- [ ] **Step 6: Push the branch**

```bash
git push -u origin redesign/ccc-worldcup-plan4
```

- [ ] **Step 7: Open the PR**

```bash
gh pr create --title "Spec C Plan 4 — WC Hub migration (home_context dispatcher + 4 partials)" --body "$(cat <<'EOF'
## Summary

Lands Plan 4 of Spec C (CCC World Cup reskin) — the final slice of the initiative.

- **`worldcup.index` route migrated** to a Spec-B-style state-shell. Route shrinks from ~50 lines of inline branching to a 5-line dispatcher; `home_shell.html` + 4 `_home_<state>.html` partials handle every state. Mirrors `core/main/routes.home` + `core/main/home_context.build_home_context`.
- **NEW `games/worldcup/services/home_context.py`** — `build_worldcup_home_context(user, state)` dispatcher + 4 builders (`_context_out`, `_context_pre`, `_context_live`, `_context_post`).
- **NEW 4-state resolver** `worldcup_hub_state(user)` in `games/worldcup/services/state.py` — `'out'` overrides phase for anonymous OR unenrolled-current-season users. The 3-state `worldcup_state()` contract (consumed by `core/main/routes.py`) is preserved unchanged.
- **NEW state-keyed voice copy** in `games/worldcup/services/voice.py` — `HUB_COPY[state][branch] = {eyebrow, headline, subhead}` covering all 4 states + the `unenrolled_post` case absent from the spec (Plan 4 brainstorm gap fill).
- **`_stage_label` lifted** from `core/main/home_context` to a new `games/worldcup/services/stage.py` with the underscore dropped. `core/main/home_context` aliases the new symbol back to preserve existing call sites without diff churn. The inline `team_detail()` import in `routes.py` is replaced with a top-of-file import.
- **Trend helpers extracted** from `routes.py` to `games/worldcup/services/trends.py` (`show_trend_column`, `compute_trend_by_enrollment`). The leaderboard route + the new `_context_live` builder share them. Season-scoping invariant locked by tests.
- **Legacy `games/worldcup/templates/worldcup/index.html` deleted** — the 312-line inline-branching template is fully replaced by `home_shell.html` + 4 partials.
- **Reusable test helpers** in `tests/_worldcup_fixtures.py` (matches `tests/_registry_helpers.py` convention) — `seed_full_tournament(num_enrollments, snapshot_days, ...)` plus finer-grained `make_*` helpers. Used by all 5 new test files.

Spec: \`docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md\`
Plan: \`docs/superpowers/plans/2026-05-04-ccc-worldcup-plan-4-wc-hub-migration.md\`

## Test plan

- [x] All tests pass — baseline + new files (`test_worldcup_stage.py`, `test_worldcup_trends.py`, `test_worldcup_hub_state.py`, `test_worldcup_voice.py`, `test_worldcup_home_context.py`)
- [x] \`pyright\` clean on \`games/worldcup/\` and on each cross-cutting file Plan 4 touched
- [x] Manual visual smoke across all 4 states + sub-branches (guest / unenrolled_pre / unenrolled_live / unenrolled_post / pre-submitted / pre-unsubmitted / live mid-pack / post non-champion) at 375px and 1280px
- [x] Sub-nav \`Hub\` pill activates on \`/worldcup/\` (Plan 1 invariant — must not regress)
- [x] Mobile sub-nav still fits 6 pills on one row at 375px (Plan 1 invariant)
- [x] Platform home \`/\` unchanged after \`_stage_label\` lift — alias keeps every existing call site working
- [x] \`/worldcup/leaderboard\` Trend column behavior unchanged after trends extraction
- [x] \`/worldcup/team/<id>\` stage-label rendering unchanged after the lift
- [x] Champion-banner defensive guards: builder returns \`champion_team=None\` and empty summary when winner_team_id is null, FK doesn't match either side, or scores are absent
- [x] Pre-deadline ownership privacy invariant from Plan 2 unchanged (Plan 4 doesn't touch \`team_detail\` route logic)

@coderabbitai please review

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 8: Wait for CodeRabbit's review and address findings**

Wait until CodeRabbit's actual review comment lands (not the "processing" stub — see `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/feedback_coderabbit_timing.md`). Address findings via additional commits on the same branch. For each finding:

1. Read carefully. CodeRabbit catches things Claude's review missed.
2. Verify before implementing — if a finding seems off, push back with reasoning rather than blindly applying.
3. Implement fixes in a separate commit per logical batch (e.g., `fix(ccc-wc): address CR feedback on builder defensive guards`).
4. Re-push.

- [ ] **Step 9: Once approved, merge**

After CodeRabbit's review is addressed and the PR is approved, merge via the GitHub UI (squash recommended — matches Plans 1, 2, 3 pattern). After merge, Plan 4 is the final slice of Spec C; the CCC redesign initiative closes.

Update memory + CLAUDE.md per Spec C section 11:
- `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/project_ccc_redesign.md` — mark Spec C complete; close out the initiative.
- `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/project_ccc_specs_b_c_notes.md` — prune; preserve any useful conventions in CLAUDE.md instead.
- CLAUDE.md additions to consider via the `claude-md-improver` pass:
  - WC sub-nav structure (already added by Plan 1)
  - WC home_context builder pattern (mirrors Spec B; builder + dispatcher + 4 partials)
  - Trend helpers in `services/trends.py` (season-scoped gate, latest-snapshot delta)
  - Stage-label SSoT in `services/stage.py` (distinct from `_derive_tournament_phase`)
  - HUB_COPY voice module location

---

## Summary

| Task | Outcome |
|---|---|
| 0 | Worktree at `../fantasy-platform-ccc-wc-plan4`, baseline verified |
| 1 | `_stage_label` lifted to `games/worldcup/services/stage.py`; 10 cases lock the SSoT |
| 2 | Trend helpers extracted to `games/worldcup/services/trends.py`; 8 tests lock season-scoping + dict-shape contract |
| 3 | `worldcup_hub_state(user)` 4-state resolver added to `services/state.py`; 6 cases |
| 4 | `services/voice.py` with `HUB_COPY` + `hub_copy()` + `rank_tier()`; 16 cases |
| 5 | Reusable `tests/_worldcup_fixtures.py` + service skeleton with dispatcher + 4 stub builders; 5 dispatcher cases |
| 6 | `_context_out` builder (4 cta_state branches incl. `unenrolled_post`); 8 cases |
| 7 | `_context_pre` builder (submitted/unsubmitted); 6 cases |
| 8 | `_context_live` builder (rank + roster + recent + trend); 10 cases |
| 9 | `_context_post` builder (champion + podium + recap with defensive guards); 7 cases |
| 10 | `home_shell.html` + `_home_out.html` |
| 11 | `_home_pre.html` |
| 12 | `_home_live.html` |
| 13 | `_home_post.html` |
| 14 | Route swap + legacy `index.html` deleted; manual smoke matrix |
| 15 | E2E verification, visual smoke, PR with CodeRabbit review |

## Test plan

New test files (all green):
- `tests/test_worldcup_stage.py` — 10 cases (parametrized)
- `tests/test_worldcup_trends.py` — 8 cases
- `tests/test_worldcup_hub_state.py` — 6 cases
- `tests/test_worldcup_voice.py` — 16 cases (parametrized)
- `tests/test_worldcup_home_context.py` — 36+ cases (5 dispatcher + 8 out + 6 pre + 10 live + 7 post)

Plus regressions:
- `tests/test_worldcup_leaderboard.py` — Plan 3's tests stay green after trends extraction
- `tests/test_worldcup_team_detail.py` — Plan 2's tests stay green after `_stage_label` lift
- `tests/test_home_context.py` + `tests/test_home_routes.py` — Spec B's platform home stays green via the import alias
- All other tests in the suite green

## Notes for the executing agent

- **`_stage_label` alias is intentional** — the new `core/main/home_context.py` line `from games.worldcup.services.stage import stage_label as _stage_label` preserves every existing call site in that file without churn. Don't rename them; that's a separate cleanup.
- **`_derive_tournament_phase` duplication** — the home_context module duplicates this 15-line helper from `routes.py` rather than importing across modules (which would risk a circular dep). CLAUDE.md "phase != stage" — distinct value space; the duplication is the right tradeoff against introducing a circular import. A future cleanup could lift it to `services/stage.py` (or a new `services/phase.py`) once we know nothing else needs it; out of scope for Plan 4.
- **`unenrolled_post` is a Plan 4 addition** — the spec's section 9 only listed `'guest' / 'unenrolled_pre' / 'unenrolled_live'`. The `unenrolled_post` cta_state (and its `HUB_COPY['out']['unenrolled_post']` entry) was added during the Plan 4 brainstorm to fill the matrix. If this feels wrong post-merge, the simplest revert is to fold `unenrolled_post` into `unenrolled_live` in both the builder dict and `voice.py` — single-line changes in two files.
- **Transient `pick.score_events`** — `_context_live` sets a transient attribute on each pick (`pick.score_events = compute_team_score_events(pick.team)`). This is the CLAUDE.md ORM-safety pattern: never persist computed display data; transient attrs are read in-template and dropped at request end. Don't move this onto the model.
- **`compute_rank_neighbors` season-scoping** — Plan 2's helper returns the rank in the active SEASON_YEAR pool. `_context_live` reuses it as-is; do NOT add a season parameter. If multi-season support comes up later, that's a Plan 2 follow-up that updates ALL callers (leaderboard, team_detail, home_context).
- **Trend gate is global, not per-user** — copied from Plan 3 (`tests/test_worldcup_leaderboard.py::test_trend_column_gate_scoped_to_active_season` is the canonical lock). The extracted helper preserves the season-scoping join via `WorldCupEnrollment` exactly. Don't change to a per-user variant.
- **Don't pre-emptively run `flask db upgrade`** — there are no migrations in Plan 4. If pyright or tests ask for one, something is wrong elsewhere; investigate before generating one.
- **Avatar pattern** — required per CLAUDE.md on every standings/leaderboard surface. The partials emit `{{ e.get_display_name() }}` per existing convention. If an avatar is added later, do it via the `WorldCupEnrollment.user.get_avatar()` chain, not a separate query.
- **WC_FAKE_NOW seam** — only honored when `ENVIRONMENT=development` or `ENVIRONMENT=testing`. The dev-server commands in this plan include the `ENVIRONMENT=development` prefix. Plain `flask run` will NOT respect WC_FAKE_NOW.
- **CSS additions** — Plan 4 deliberately adds NO new CSS. All visual treatments use foundation utilities from Plan 1 (`.wc-eyebrow`, `.wc-numeral`, `.wc-card`, `.wc-hero-grad`, `.wc-tier-dot`, `.wc-multiplier-chip`) plus existing platform classes (`.stat-block`, `.match-result-card`, `.roster-team-card`, etc.). If a partial needs a class that doesn't exist, the right move is usually to compose existing utilities in markup rather than add a new class — match Plan 3's approach of using multi-class scoping (e.g., `.card.wc-card`) over single-class wins.
- **`_home_post` partial assumes enrollment exists** — `your_final_rank`, `your_climbed_n`, and `your_roster_recap` are only meaningful for an enrolled viewer. The state resolver (`worldcup_hub_state`) routes unenrolled viewers to `'out'` instead, so the post partial never runs for them. Don't add unenrolled-aware branches inside the partial.
- **Subagent worktree perms** — Per `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/feedback_subagent_worktree_perms.md`, if dispatching subagents to execute tasks in this worktree, pre-approve Edit/Write on the worktree path via `.claude/settings.local.json` to avoid auto-deny prompts.
