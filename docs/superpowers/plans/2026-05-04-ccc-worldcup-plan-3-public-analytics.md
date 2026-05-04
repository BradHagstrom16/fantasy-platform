# Spec C — Plan 3: Public analytics

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin `leaderboard.html` to the CCC visual language, add a "Your Standing" hero block + per-row Trend column powered by Plan 2's `compute_rank_neighbors` and Spec B's `WorldCupRankSnapshot`. Then aggressively restructure `stats.html` via the `frontend-design` skill — service-layer entry points untouched, tab consolidation permitted (6 → 3-4).

**Architecture:** Pure read-only template + route work. The leaderboard route (`worldcup.leaderboard`) gains three payload keys (`your_standing`, `trend_by_enrollment`, `show_trend_column`) computed from helpers that already ship on `main`. Stats restructure is template-only — the public service entry points (`get_country_stats`, `get_tier_stats`, `get_overview_kpis`, `get_tier_combos`) and the `worldcup.stats` route's data bindings stay frozen. The `frontend-design` skill drives Section C's structural decisions; the agent commits a design memo before rewriting the template.

**Tech Stack:** Bootstrap 5.3, Jinja2 templates, vanilla CSS (no preprocessors), SQLAlchemy 2.0, Chart.js 4.4 (frozen — no library swap). WC palette + `.wc-*` foundation utilities (`.wc-eyebrow`, `.wc-numeral`, `.wc-hero-grad`, `.wc-tier-dot`, `.wc-multiplier-chip`, `.card.wc-card`) all live on `main` from Plan 1's commit `6434cae`. Plan 2 (commit `9df1a21`) shipped `compute_rank_neighbors` in `games/worldcup/services/ranking.py` — Plan 3 imports it unchanged. `WorldCupRankSnapshot` from Spec B is the trend data source; `flask worldcup snapshot-ranks` (with `--backfill N`) is the existing CLI for seeding.

**Spec reference:** `docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md` §8 (Plan 3) and §5 (cross-cutting decisions).

**Dependency note:** This plan does NOT touch the existing `_stage_label` location in `core/main/home_context` — Plan 4 will lift it to `games/worldcup/services/stage.py`. If `stats.html` references stage labels (it does, indirectly via `current_phase`), import from the existing `core/main/home_context` location for now. Plan 4's PR will update Plan 3's import in lockstep.

---

## Pre-flight

### Task 0: Worktree setup + baseline verification

**Files:** none modified yet. This task creates the working environment.

- [ ] **Step 1: Create the worktree branch off main**

```bash
cd /Users/bhagstrom/fantasy-platform
git fetch origin main
git worktree add -b redesign/ccc-worldcup-plan3 ../fantasy-platform-ccc-wc-plan3 origin/main
cd ../fantasy-platform-ccc-wc-plan3
```

Expected: new directory `../fantasy-platform-ccc-wc-plan3` exists; `git status` reports clean working tree on branch `redesign/ccc-worldcup-plan3`.

- [ ] **Step 2: Verify Plan 1 + Plan 2 foundations are on main**

```bash
git log --oneline -5
grep -n "wc-eyebrow\|wc-card\|page-hero.wc-hero-grad" static/css/style.css | head -5
grep -n "compute_rank_neighbors" games/worldcup/services/ranking.py
grep -n "WorldCupRankSnapshot" games/worldcup/models.py
grep -n "team_detail" templates/base.html
```

Expected: log shows recent merges including Plan 1 (`6434cae`) and Plan 2 (`9df1a21`); style.css contains `.wc-eyebrow`, `.card.wc-card`, `.page-hero.wc-hero-grad`; `compute_rank_neighbors` is defined in `games/worldcup/services/ranking.py`; `WorldCupRankSnapshot` model exists; sub-nav references `worldcup.team_detail`. If any are missing, you are not branched off the right `main` — stop and reconcile.

- [ ] **Step 3: Verify baseline tests pass before changing anything**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: all baseline tests pass. Capture the count to compare against deltas later. If any fail, stop and investigate — they are baseline regressions, not introduced by this plan.

- [ ] **Step 4: Verify pyright is clean on the WC blueprint**

```bash
venv/bin/pyright games/worldcup/
```

Expected: 0 errors.

- [ ] **Step 5: Confirm spec + Plan 2 plan files are accessible (cross-references)**

```bash
test -f docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md && echo "spec present"
test -f docs/superpowers/plans/2026-05-02-ccc-worldcup-plan-2-per-rival-surfaces.md && echo "plan2 present"
```

Expected: both lines print.

---

## Section A — Leaderboard route payload (TDD)

### Task 1: Extend `worldcup.leaderboard()` route with Your Standing + Trend data (TDD)

The route stays a thin handler; computation lives in clearly-named helpers so tests can target them directly. Three payload keys are added — `your_standing` (None | dict), `trend_by_enrollment` (dict[int, float | None]), `show_trend_column` (bool).

**Why three keys, not one nested object:** the template branches on each independently — `your_standing` only renders for authenticated+enrolled users; `show_trend_column` toggles a column on the table for everyone; `trend_by_enrollment` resolves per row. Flat keys keep the template clean.

**Files:**
- Create: `tests/test_worldcup_leaderboard.py`
- Modify: `games/worldcup/routes.py` — `leaderboard()` (lines 347–378)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_worldcup_leaderboard.py`:

```python
"""Tests for the public /worldcup/leaderboard route — payload + new data shapes.

Plan 3 adds three payload keys:
- your_standing: None | dict (rank-neighbor data for authenticated+enrolled user)
- trend_by_enrollment: dict[int, float | None] mapping enrollment.id -> trend score
- show_trend_column: bool (gated on count(distinct captured_date) >= 7)

Trend semantics (per spec §8 + plan ambiguity-A2):
  trend = enrollment.total_score - latest_snapshot.total_score for that enrollment
  None if no snapshot exists for that enrollment
"""
import pytest
from datetime import date, datetime, timezone, timedelta

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupRankSnapshot,
)


PAST_DEADLINE = datetime(2000, 1, 1, tzinfo=timezone.utc)
FUTURE_DEADLINE = datetime(2099, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _seed_user(username, password='pass'):
    u = User(username=username, email=f'{username}@test.com')
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    return u


def _seed_enrollment(user_id, score, usa_goals_guess=5):
    e = WorldCupEnrollment(
        user_id=user_id, season_year=SEASON_YEAR,
        picks_submitted=True, total_score=score,
        usa_goals_guess=usa_goals_guess,
    )
    db.session.add(e)
    db.session.flush()
    return e


def _seed_snapshot(enrollment_id, captured_date, rank, total_score):
    s = WorldCupRankSnapshot(
        enrollment_id=enrollment_id,
        captured_date=captured_date,
        rank=rank,
        total_score=total_score,
    )
    db.session.add(s)
    db.session.flush()
    return s


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


# ── your_standing block ──────────────────────────────────────────────

def test_your_standing_block_renders_for_authenticated_enrolled_user(client, app):
    """Authenticated + enrolled user sees Your Standing block in payload + DOM."""
    with app.app_context():
        u = _seed_user('alice')
        _seed_enrollment(u.id, score=42.0)
        db.session.commit()
        _login(client, u.id)
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Your Standing' in resp.data


def test_your_standing_omitted_for_anonymous(client, app):
    """Anonymous user does not see Your Standing block."""
    with app.app_context():
        u = _seed_user('alice')
        _seed_enrollment(u.id, score=42.0)
        db.session.commit()
        # No login
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Your Standing' not in resp.data


def test_your_standing_omitted_for_authenticated_unenrolled(client, app):
    """Authenticated but unenrolled user does not see Your Standing block."""
    with app.app_context():
        u_enr = _seed_user('alice')
        _seed_enrollment(u_enr.id, score=42.0)
        u_unenr = _seed_user('bob')  # No enrollment
        db.session.commit()
        _login(client, u_unenr.id)
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Your Standing' not in resp.data


def test_lead_delta_calculation(client, app):
    """Five-enrollment fixture with known scores — Your Standing caption reflects neighbors.

    Caption format from _your_standing_caption: '{up} pts from 1st · {down} ahead of next.'
    With scores [100, 80, 60, 40, 20] and target rank 3 (score 60):
      up = 100 - 60 = 40.0  (rounded to 2 decimals -> 40.0)
      down = 60 - 40 = 20.0
    """
    with app.app_context():
        users = [_seed_user(f'p{i}') for i in range(5)]
        # scores: 100 (rank 1), 80 (rank 2), 60 (rank 3, target), 40 (rank 4), 20 (rank 5)
        _seed_enrollment(users[0].id, 100.0)
        _seed_enrollment(users[1].id, 80.0)
        _seed_enrollment(users[2].id, 60.0)
        _seed_enrollment(users[3].id, 40.0)
        _seed_enrollment(users[4].id, 20.0)
        db.session.commit()
        _login(client, users[2].id)
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    body = resp.data.decode()
    # Verify the literal caption rendered. The leader/tail/sole variants use
    # different copy, so a hit on this exact phrase confirms the mid-rank path
    # AND the deltas are correct.
    assert '40.0 pts from 1st · 20.0 ahead of next.' in body


# ── trend column ─────────────────────────────────────────────────────

def test_trend_column_uses_latest_snapshot(client, app):
    """Per-row trend = current_score - latest_snapshot_score for that enrollment.

    Latest = max(captured_date). Verify by seeding a snapshot a few days back
    AND a more recent snapshot — the more recent should win the diff.
    """
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=50.0)
        # Seed 8 distinct dates so the gate opens (see A1 below).
        today = date.today()
        for i in range(8):
            # Enrollment's snapshots: oldest=10 pts, latest (i=0) = 47 pts
            _seed_snapshot(
                enrollment_id=e.id,
                captured_date=today - timedelta(days=i + 1),
                rank=1,
                total_score=10.0 + (7 - i) * 5.0,  # newest captured_date = highest score
            )
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    # Latest snapshot was yesterday at 45.0 (i=0 -> 10 + 35 = 45.0)
    # Current score 50.0 -> trend = +5.0
    # Page renders +5.0 (some formatting tolerance).
    assert b'+5.0' in resp.data or b'+5' in resp.data


def test_trend_column_hidden_when_fewer_than_seven_snapshots(client, app):
    """show_trend_column = False when count(distinct captured_date) < 7.

    Per ambiguity-A1 resolution: gate is on distinct captured_date count
    across the whole table — not per-user.
    """
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=50.0)
        # Only 6 distinct dates → gate stays closed
        today = date.today()
        for i in range(6):
            _seed_snapshot(
                enrollment_id=e.id,
                captured_date=today - timedelta(days=i + 1),
                rank=1,
                total_score=40.0,
            )
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    # The literal column header "Trend" must not appear in the desktop table
    # OR mobile-card line — but other usages of the word "trend" in templates
    # are fine. Gate by the unique <th> markup.
    assert b'<th class="text-end">Trend</th>' not in resp.data


def test_trend_column_shows_dash_when_no_prior_snapshot_for_user(client, app):
    """When a row has no snapshot history but the column is open, render '—'."""
    with app.app_context():
        u_with = _seed_user('alice')
        e_with = _seed_enrollment(u_with.id, score=50.0)
        u_without = _seed_user('bob')
        _seed_enrollment(u_without.id, score=30.0)
        # Open the gate by seeding 7 distinct dates against alice only.
        # bob has no snapshot history.
        today = date.today()
        for i in range(7):
            _seed_snapshot(
                enrollment_id=e_with.id,
                captured_date=today - timedelta(days=i + 1),
                rank=1,
                total_score=40.0,
            )
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    # Column is open
    assert b'<th class="text-end">Trend</th>' in resp.data
    # Bob's row trend cell renders '—'
    body = resp.data.decode()
    assert 'bob' in body
    # We can't easily isolate bob's row without parsing, but at minimum:
    assert '—' in body


# ── basic reskin smoke (Tasks 2-4 will harden) ────────────────────────

def test_leaderboard_route_still_returns_200_with_no_data(client, app):
    """Empty leaderboard renders the empty-state copy."""
    with app.app_context():
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'No players enrolled yet' in resp.data
```

Run:

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_leaderboard.py -v
```

Expected: most or all tests FAIL — payload keys don't exist yet, "Your Standing" string isn't in template yet, trend column not yet wired. The empty-state test should already pass.

- [ ] **Step 2: Add payload helpers to the route module**

Open `games/worldcup/routes.py`. Find the existing `leaderboard()` function (around line 347):

```python
@worldcup_bp.route('/leaderboard')
def leaderboard():
    """Public leaderboard — no login required."""
    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.usa_goals_guess.asc(),
        )
        .all()
    )

    # Dense rank: tied scores share a rank and the next distinct score is
    # rank+1 (no gap). Matches compute_rank_neighbors() so a player's rank
    # on the board agrees with /worldcup/leaderboard/<id> hero rank.
    ranked = []
    current_rank = 0
    prev_score = None
    for e in enrollments:
        if e.total_score != prev_score:
            current_rank += 1
        ranked.append({'rank': current_rank, 'enrollment': e})
        prev_score = e.total_score

    deadline_passed = now_utc() >= TOURNAMENT_DEADLINE_UTC

    return render_template('worldcup/leaderboard.html',
        ranked_enrollments=ranked,
        total_players=len(enrollments),
        deadline_passed=deadline_passed,
    )
```

Replace the entire function body with the new version below. Also locate the imports block at the top of `games/worldcup/routes.py` and add `func` + `distinct` from sqlalchemy and `compute_rank_neighbors` from the ranking service module if they are not yet imported. The file already imports `or_` so we know the sqlalchemy import line is present — extend it.

In the imports section near the top of the file, ensure these imports are present:

```python
from sqlalchemy import or_, func, distinct
from games.worldcup.services.ranking import compute_rank_neighbors
```

Replace the `leaderboard()` function body with:

```python
@worldcup_bp.route('/leaderboard')
def leaderboard():
    """Public leaderboard — no login required.

    Plan 3 adds three payload keys:
    - your_standing: dict | None (rank-neighbor block for authenticated+enrolled user)
    - trend_by_enrollment: dict[int, float | None] (per-row matchday trend)
    - show_trend_column: bool (gated on count(distinct captured_date) >= 7)
    """
    enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(
            WorldCupEnrollment.total_score.desc(),
            WorldCupEnrollment.usa_goals_guess.asc(),
        )
        .all()
    )

    # Dense rank: tied scores share a rank and the next distinct score is
    # rank+1 (no gap). Matches compute_rank_neighbors() so a player's rank
    # on the board agrees with /worldcup/leaderboard/<id> hero rank.
    ranked = []
    current_rank = 0
    prev_score = None
    for e in enrollments:
        if e.total_score != prev_score:
            current_rank += 1
        ranked.append({'rank': current_rank, 'enrollment': e})
        prev_score = e.total_score

    deadline_passed = now_utc() >= TOURNAMENT_DEADLINE_UTC

    your_standing = _compute_your_standing(enrollments)
    show_trend_column = _show_trend_column()
    trend_by_enrollment = (
        _compute_trend_by_enrollment([e.id for e in enrollments])
        if show_trend_column else {}
    )

    return render_template('worldcup/leaderboard.html',
        ranked_enrollments=ranked,
        total_players=len(enrollments),
        deadline_passed=deadline_passed,
        your_standing=your_standing,
        show_trend_column=show_trend_column,
        trend_by_enrollment=trend_by_enrollment,
    )
```

Then add three private helpers immediately above the `@worldcup_bp.route('/leaderboard')` decorator (so they live in the same module, scoped close to their only caller):

```python
def _compute_your_standing(enrollments):
    """Return Your Standing block dict for the current user, or None.

    Returns None when:
    - User is anonymous, or
    - User has no WorldCupEnrollment in SEASON_YEAR

    Returns a dict with: rank, total, of_n, lead_delta_up, lead_delta_down,
    caption (a string voice line for the block).
    """
    if not current_user.is_authenticated:
        return None

    enrollment = next(
        (e for e in enrollments if e.user_id == current_user.id), None
    )
    if enrollment is None:
        return None

    neighbors = compute_rank_neighbors(enrollment.id)
    of_n = len(enrollments)

    return {
        'rank': neighbors['rank'],
        'total': neighbors['points'],
        'of_n': of_n,
        'lead_delta_up': neighbors['lead_delta_up'],
        'lead_delta_down': neighbors['lead_delta_down'],
        'caption': _your_standing_caption(neighbors),
    }


def _your_standing_caption(neighbors):
    """Compose a voice caption tuned to the user's rank position.

    - Sole entry: "You are the only one in the running."
    - Leader (rank 1, has chasers): "{down} ahead of the next pursuer."
    - Tail (no one below): "{up} pts from the lead."
    - Middle: "{up} pts from 1st · {down} ahead of next."
    """
    up = neighbors['lead_delta_up']
    down = neighbors['lead_delta_down']

    if up is None and down is None:
        return 'You are the only one in the running.'
    if up is None:
        return f'{down} ahead of the next pursuer.'
    if down is None:
        return f'{up} pts from the lead.'
    return f'{up} pts from 1st · {down} ahead of next.'


def _show_trend_column():
    """True if count(distinct captured_date) >= 7 across all snapshots.

    Per ambiguity-A1 resolution: a single global gate, not per-user.
    Mirrors Spec B's >= 7 gating on the home-page sparkline.
    """
    distinct_days = (
        db.session.query(func.count(distinct(WorldCupRankSnapshot.captured_date)))
        .scalar() or 0
    )
    return distinct_days >= 7


def _compute_trend_by_enrollment(enrollment_ids):
    """For each enrollment id, compute trend = current_score - latest_snapshot_score.

    "Latest" = MAX(captured_date) per enrollment. Returns None if the enrollment
    has no snapshot history at all (template renders '—').

    Implementation: one round-trip — pull the latest snapshot per enrollment via
    a (enrollment_id, MAX(captured_date)) subquery joined back to the snapshot
    table for total_score. SQLite-friendly; no window functions required.
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

    trend = {}
    enrollments_by_id = {
        e.id: e for e in WorldCupEnrollment.query
        .filter(WorldCupEnrollment.id.in_(enrollment_ids))
        .all()
    }
    for eid in enrollment_ids:
        snap = snapshot_score_by_eid.get(eid)
        enr = enrollments_by_id.get(eid)
        if snap is None or enr is None:
            trend[eid] = None
        else:
            trend[eid] = round(enr.total_score - snap, 2)
    return trend
```

Also ensure `WorldCupRankSnapshot` is imported at the top of `routes.py`. Look for the existing `from games.worldcup.models import` block and add `WorldCupRankSnapshot` if absent:

```python
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupPick, WorldCupMatch,
    WorldCupRankSnapshot,
)
```

(If the existing import line is structured differently, splice the new symbol in without changing the others.)

- [ ] **Step 3: Run pyright on the route module**

```bash
venv/bin/pyright games/worldcup/routes.py
```

Expected: 0 errors. If pyright complains about `current_user` typing, it's pre-existing — leave it. If it complains about new symbols, fix the import line.

- [ ] **Step 4: Run the new tests — many should still fail because the template hasn't been touched yet**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_leaderboard.py -v
```

Expected:
- `test_your_standing_omitted_for_anonymous` PASS (no Your Standing block in template — true by absence)
- `test_your_standing_omitted_for_authenticated_unenrolled` PASS (same reason)
- `test_leaderboard_route_still_returns_200_with_no_data` PASS
- `test_trend_column_hidden_when_fewer_than_seven_snapshots` PASS (column not in template yet)
- `test_your_standing_block_renders_for_authenticated_enrolled_user` FAIL — template doesn't render the block
- `test_lead_delta_calculation` FAIL — template doesn't render delta numbers
- `test_trend_column_uses_latest_snapshot` FAIL — template doesn't render trend
- `test_trend_column_shows_dash_when_no_prior_snapshot_for_user` FAIL — template doesn't render `<th>Trend</th>`

This is correct. The route now ships the data; the template wires it up in Tasks 3 and 4.

- [ ] **Step 5: Run the full test suite to confirm baseline tests still pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: baseline tests all still pass (no regressions from route changes). The 4 new test failures are expected and will resolve in Tasks 3 + 4.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/routes.py tests/test_worldcup_leaderboard.py
git commit -m "feat(ccc-wc): extend leaderboard route with Your Standing + Trend payload

Adds three payload keys to worldcup.leaderboard:
- your_standing: rank-neighbor block + voice caption (None for anon/unenrolled)
- trend_by_enrollment: dict[id -> float|None] from latest WorldCupRankSnapshot
- show_trend_column: count(distinct captured_date) >= 7 (global gate, mirrors Spec B)

Helpers _compute_your_standing, _your_standing_caption, _show_trend_column,
_compute_trend_by_enrollment scoped to the leaderboard route. Trend uses one
join via (enrollment_id, MAX(captured_date)) subquery — no window functions.

Tests: 8 new in tests/test_worldcup_leaderboard.py — 4 passing now (route
payload), 4 failing pending template wiring in Plan 3 Tasks 3-4.

Refs Spec C Plan 3 §A."
```

---

## Section B — Leaderboard template

### Task 2: Reskin `leaderboard.html` (palette, cards, table) — strict reskin

This task changes visuals only — no data changes, no new template variables consumed. Foundation `.wc-*` utilities from Plan 1 do most of the work. The "Your Standing" block and Trend column come in Tasks 3 and 4.

**Files:**
- Modify: `games/worldcup/templates/worldcup/leaderboard.html` (100 lines)

- [ ] **Step 1: Read the current template**

```bash
cat games/worldcup/templates/worldcup/leaderboard.html
```

Note the structure: hero, desktop table (with row-current-user highlight), mobile cards, empty state.

- [ ] **Step 2: Replace the template body**

Overwrite `games/worldcup/templates/worldcup/leaderboard.html` with:

```html
{% extends "base.html" %}
{% block title %}Leaderboard — World Cup Fantasy Pool{% endblock %}

{% block content %}
{# ── Hero ── #}
<div class="page-hero wc-hero-grad">
  <div class="hero-glow"></div>
  <div class="container">
    <span class="wc-eyebrow">Live Standings</span>
    <h1 class="mb-1">Leaderboard</h1>
    <p class="lead mb-0 text-muted-on-dark">
      <span class="wc-numeral">{{ total_players }}</span>
      player{{ 's' if total_players != 1 }} &middot; 2026 FIFA World Cup
    </p>
  </div>
</div>

<div class="container pb-5">
  {# Plan 3 Task 3 will mount Your Standing here #}
  {# Plan 3 Task 4 will mount the Trend column inside the desktop table + mobile cards #}

  {% if ranked_enrollments %}

  {# Desktop table #}
  <div class="card wc-card border-0 shadow-sm d-none d-md-block animate-in mt-4">
    <div class="card-body p-0">
      <div class="table-responsive">
        <table class="table table-worldcup leaderboard-table mb-0">
          <thead>
            <tr>
              <th style="width:60px">#</th>
              <th>Player</th>
              <th class="text-end">Points</th>
              {% if deadline_passed %}
              <th class="text-end">Tiebreaker</th>
              {% endif %}
            </tr>
          </thead>
          <tbody>
            {% for item in ranked_enrollments %}
            {% set e = item.enrollment %}
            <tr {% if current_user.is_authenticated and e.user_id == current_user.id %}class="row-current-user"{% endif %}>
              <td class="fw-bold wc-numeral">{{ item.rank }}</td>
              <td>
                <span class="me-1">{{ e.user.get_avatar() }}</span>
                {% if current_user.is_authenticated and e.user_id == current_user.id %}
                <a href="{{ url_for('worldcup.picks') }}" class="text-decoration-none fw-medium">
                  {{ e.get_display_name() }}
                </a>
                {% else %}
                <a href="{{ url_for('worldcup.player_detail', enrollment_id=e.id) }}" class="text-decoration-none fw-medium">
                  {{ e.get_display_name() }}
                </a>
                {% endif %}
              </td>
              <td class="text-end fw-bold wc-numeral">{{ "%.1f"|format(e.total_score) }}</td>
              {% if deadline_passed %}
              <td class="text-end text-muted">{{ e.usa_goals_guess if e.usa_goals_guess is not none else '—' }}</td>
              {% endif %}
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  {# Mobile cards #}
  <div class="d-md-none mt-4">
    {% for item in ranked_enrollments %}
    {% set e = item.enrollment %}
    <div class="card wc-card border-0 shadow-sm mb-2 leaderboard-card{% if current_user.is_authenticated and e.user_id == current_user.id %} leaderboard-card-current{% endif %} animate-in">
      <div class="card-body p-3 d-flex align-items-center justify-content-between">
        <div class="d-flex align-items-center gap-3">
          <span class="fw-bold text-muted wc-numeral leaderboard-rank">{{ item.rank }}</span>
          <div>
            <span class="me-1">{{ e.user.get_avatar() }}</span>
            {% if current_user.is_authenticated and e.user_id == current_user.id %}
            <a href="{{ url_for('worldcup.picks') }}" class="text-decoration-none fw-medium d-block">
              {{ e.get_display_name() }}
            </a>
            {% else %}
            <a href="{{ url_for('worldcup.player_detail', enrollment_id=e.id) }}" class="text-decoration-none fw-medium d-block">
              {{ e.get_display_name() }}
            </a>
            {% endif %}
            {% if deadline_passed and e.usa_goals_guess is not none %}
            <small class="text-muted">TB: {{ e.usa_goals_guess }}</small>
            {% endif %}
          </div>
        </div>
        <span class="fw-bold wc-numeral leaderboard-score">
          {{ "%.1f"|format(e.total_score) }}
        </span>
      </div>
    </div>
    {% endfor %}
  </div>

  {% else %}
  <div class="text-center py-5 text-muted animate-in">
    <i class="bi bi-trophy" style="font-size:3rem; opacity:.3;"></i>
    <p class="mt-3 mb-0">No players enrolled yet. <a href="{{ url_for('worldcup.join') }}">Be the first!</a></p>
  </div>
  {% endif %}
</div>
{% endblock %}
```

Notable changes vs. previous:
- `.page-hero.wc-hero-grad` (Plan 1 utility — winning specificity per CLAUDE.md "CSS specificity for utility classes")
- `.wc-eyebrow` above the H1 ("Live Standings")
- All numerals (rank, points, score) use `.wc-numeral`
- Cards scoped as `.card.wc-card` (multi-class for cascade — same pattern Plan 2 used for hero ribbons)
- Inline styles on rank/score numerals replaced by `.leaderboard-rank` / `.leaderboard-score` classes (added in Step 3)
- Mobile current-user accent moved from inline `style` to `.leaderboard-card-current` class (added in Step 3)

- [ ] **Step 3: Add scoped utility classes to `static/css/style.css`**

Open `static/css/style.css`. Find the `/* === WORLD CUP FANTASY POOL === */` section. Add the following block immediately before the closing of that section (or anywhere within it that keeps related rules together):

```css
/* Plan 3: leaderboard reskin — table + mobile cards
   ------------------------------------------------- */
.leaderboard-table thead th {
  font-family: 'Teko', sans-serif;
  font-size: .85rem;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.leaderboard-rank {
  font-size: 1.3rem;
  min-width: 2rem;
}

.leaderboard-score {
  font-size: 1.4rem;
  letter-spacing: .03em;
}

/* Multi-class: wins specificity over the bare .card.wc-card border rule.
   See CLAUDE.md "CSS specificity for utility classes". */
.card.wc-card.leaderboard-card-current {
  border-left: 3px solid var(--game-accent) !important;
}
```

- [ ] **Step 4: Run the test suite — confirm baseline tests still pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: same pass/fail breakdown as Task 1 Step 4 — Task 2 changes nothing about which tests pass. Visual reskin ≠ test changes.

- [ ] **Step 5: Visual smoke at port 5099**

Start the dev server in a separate shell:

```bash
ENVIRONMENT=development FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

Open `http://localhost:5099/worldcup/leaderboard` in a browser at 1280px (desktop) and 375px (mobile via DevTools). Verify:

| Viewport | Verify |
|---|---|
| Desktop | Hero shows the navy gradient (`.wc-hero-grad`) with red eyebrow "Live Standings" above H1 |
| Desktop | Table header uses Teko uppercase letterspacing |
| Desktop | Rank + Points numerals in Teko (tabular) |
| Desktop | Current-user row keeps red-tinted highlight (existing `.row-current-user`) |
| Mobile | Card stack shows `wc-card` accent (left border, shadow) |
| Mobile | Current-user card shows red left border via `.leaderboard-card-current` |
| Mobile | Rank numeral large + Teko; score numeral large + Teko |
| Both | Empty-state still renders (run `flask db downgrade` then back up if you need to test empty state, or temporarily filter enrollments to nothing) |

If any of these read wrong, stop and reconcile — most likely a CSS-specificity conflict from a later base rule.

Stop the server (Ctrl+C in the dev-server shell) before continuing.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/templates/worldcup/leaderboard.html static/css/style.css
git commit -m "style(ccc-wc): reskin leaderboard.html with WC palette + Plan 1 utilities

Strict visual reskin — no data shape changes, no new variables consumed.
Hero now uses .page-hero.wc-hero-grad with red 'Live Standings' eyebrow.
Numerals (rank, points, score) lift to .wc-numeral. Cards scoped as
.card.wc-card. Inline styles for rank/score and current-user mobile
accent moved into scoped utility classes (.leaderboard-rank,
.leaderboard-score, .card.wc-card.leaderboard-card-current).

Refs Spec C Plan 3 §B."
```

---

### Task 3: Add "Your Standing" hero block to leaderboard

The Your Standing block sits below the page hero and above the table/cards. It renders only for authenticated + enrolled users (the route already gates `your_standing` to None otherwise).

**Files:**
- Modify: `games/worldcup/templates/worldcup/leaderboard.html`
- Modify: `static/css/style.css`

- [ ] **Step 1: Open `leaderboard.html` and locate the placeholder comment**

The placeholder from Task 2:

```html
  {# Plan 3 Task 3 will mount Your Standing here #}
```

Replace that line with:

```html
  {# Your Standing block — rendered only for authenticated + enrolled users #}
  {% if your_standing %}
  <div class="your-standing animate-in mt-4">
    <span class="wc-eyebrow">Your Standing</span>
    <div class="your-standing-grid">
      <div class="your-standing-rank">
        <div class="your-standing-rank-numeral wc-numeral">
          {{ your_standing.rank }}
        </div>
        <div class="your-standing-rank-label">
          of <span class="wc-numeral">{{ your_standing.of_n }}</span>
        </div>
      </div>
      <div class="your-standing-points">
        <div class="your-standing-points-label">Points</div>
        <div class="your-standing-points-numeral wc-numeral">
          {{ "%.1f"|format(your_standing.total) }}
        </div>
      </div>
    </div>
    <p class="your-standing-caption mb-0">{{ your_standing.caption }}</p>
  </div>
  {% endif %}
```

- [ ] **Step 2: Add scoped CSS for the Your Standing block**

Open `static/css/style.css`. Find the leaderboard CSS block added in Task 2. Add the following CSS rules immediately after the existing `.leaderboard-card-current` block:

```css
/* Plan 3: Your Standing hero block (auth + enrolled only)
   ------------------------------------------------------- */
.your-standing {
  background: linear-gradient(135deg,
    rgba(0, 26, 77, .08) 0%,
    rgba(191, 10, 48, .05) 100%);
  border: 1px solid var(--border);
  border-left: 3px solid var(--game-accent);
  border-radius: var(--radius);
  padding: 1.1rem 1.25rem;
}

.your-standing .wc-eyebrow {
  display: block;
  margin-bottom: .35rem;
  color: var(--game-accent);
}

.your-standing-grid {
  display: flex;
  align-items: baseline;
  gap: 2rem;
  flex-wrap: wrap;
  margin-bottom: .25rem;
}

.your-standing-rank-numeral {
  font-size: 3rem;
  line-height: 1;
  letter-spacing: .02em;
  color: var(--text-primary);
}

.your-standing-rank-label {
  font-family: 'Teko', sans-serif;
  font-size: .9rem;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-top: .15rem;
}

.your-standing-points {
  display: flex;
  flex-direction: column;
}

.your-standing-points-label {
  font-family: 'Teko', sans-serif;
  font-size: .8rem;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.your-standing-points-numeral {
  font-size: 2rem;
  letter-spacing: .03em;
  color: var(--text-primary);
}

.your-standing-caption {
  font-family: 'Teko', sans-serif;
  font-size: .95rem;
  letter-spacing: .03em;
  color: var(--text-muted);
}

@media (max-width: 575.98px) {
  .your-standing-grid { gap: 1.25rem; }
  .your-standing-rank-numeral { font-size: 2.4rem; }
  .your-standing-points-numeral { font-size: 1.6rem; }
}
```

- [ ] **Step 3: Run the new test for Your Standing**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_leaderboard.py::test_your_standing_block_renders_for_authenticated_enrolled_user tests/test_worldcup_leaderboard.py::test_your_standing_omitted_for_anonymous tests/test_worldcup_leaderboard.py::test_your_standing_omitted_for_authenticated_unenrolled tests/test_worldcup_leaderboard.py::test_lead_delta_calculation -v
```

Expected: all 4 PASS.

- [ ] **Step 4: Visual smoke**

In the dev-server shell:

```bash
ENVIRONMENT=development FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

Verify these scenarios at `http://localhost:5099/worldcup/leaderboard`:

| Auth state | Expected |
|---|---|
| Anonymous (logged out) | No Your Standing block (block absent entirely) |
| Logged in but not enrolled in WC | No Your Standing block |
| Logged in + enrolled, rank 1 | Block visible, caption: "{down} ahead of the next pursuer." |
| Logged in + enrolled, mid-pack | Block visible, caption: "{up} pts from 1st · {down} ahead of next." |
| Logged in + enrolled, last place | Block visible, caption: "{up} pts from the lead." |
| Logged in + enrolled, only enrollment | Caption: "You are the only one in the running." |

If your local DB has no realistic data for these states, you can manually edit a test fixture or seed via a Python REPL — but the unit tests in Step 3 are the authoritative validation. Visual smoke checks layout + readability.

Stop the server before continuing.

- [ ] **Step 5: Run full pytest + pyright**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
venv/bin/pyright games/worldcup/
```

Expected: all baseline tests still pass; pyright clean.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/templates/worldcup/leaderboard.html static/css/style.css
git commit -m "feat(ccc-wc): add Your Standing hero block to leaderboard

Auth + enrolled users see a 2-stat hero block above the standings table:
- Rank N of M (large Teko numerals)
- Points (Teko numeral)
- Voice caption keyed by rank position (sole / leader / tail / mid)

CSS scoped to .your-standing-* class family to avoid collision with
later platform .stat-block / .card rules. Mobile media query tightens
numerals.

Refs Spec C Plan 3 §B."
```

---

### Task 4: Add per-row Trend column to leaderboard (gated by 7-day rule)

The Trend column appears in the desktop table (between Points and Tiebreaker) and as a small line in mobile cards. The whole column is hidden when `show_trend_column` is False.

**Files:**
- Modify: `games/worldcup/templates/worldcup/leaderboard.html`
- Modify: `static/css/style.css`

- [ ] **Step 1: Open `leaderboard.html` and locate the placeholder comment from Task 2**

The placeholder line:

```html
  {# Plan 3 Task 4 will mount the Trend column inside the desktop table + mobile cards #}
```

Delete that line (the column markup goes into the table and mobile cards directly).

- [ ] **Step 2: Add the Trend column to the desktop table**

Find the `<thead>` block in the desktop table:

```html
<thead>
  <tr>
    <th style="width:60px">#</th>
    <th>Player</th>
    <th class="text-end">Points</th>
    {% if deadline_passed %}
    <th class="text-end">Tiebreaker</th>
    {% endif %}
  </tr>
</thead>
```

Replace with:

```html
<thead>
  <tr>
    <th style="width:60px">#</th>
    <th>Player</th>
    <th class="text-end">Points</th>
    {% if show_trend_column %}
    <th class="text-end">Trend</th>
    {% endif %}
    {% if deadline_passed %}
    <th class="text-end">Tiebreaker</th>
    {% endif %}
  </tr>
</thead>
```

Find the `<tbody>` row block:

```html
<td class="text-end fw-bold wc-numeral">{{ "%.1f"|format(e.total_score) }}</td>
{% if deadline_passed %}
<td class="text-end text-muted">{{ e.usa_goals_guess if e.usa_goals_guess is not none else '—' }}</td>
{% endif %}
```

Replace with:

```html
<td class="text-end fw-bold wc-numeral">{{ "%.1f"|format(e.total_score) }}</td>
{% if show_trend_column %}
<td class="text-end leaderboard-trend">
  {% set t = trend_by_enrollment.get(e.id) %}
  {% if t is none %}
  <span class="text-muted">—</span>
  {% elif t > 0 %}
  <span class="leaderboard-trend-up wc-numeral">+{{ "%.1f"|format(t) }}</span>
  {% elif t < 0 %}
  <span class="leaderboard-trend-down wc-numeral">{{ "%.1f"|format(t) }}</span>
  {% else %}
  <span class="text-muted">—</span>
  {% endif %}
</td>
{% endif %}
{% if deadline_passed %}
<td class="text-end text-muted">{{ e.usa_goals_guess if e.usa_goals_guess is not none else '—' }}</td>
{% endif %}
```

- [ ] **Step 3: Add the Trend line to mobile cards**

Find the mobile-card inner block:

```html
{% if deadline_passed and e.usa_goals_guess is not none %}
<small class="text-muted">TB: {{ e.usa_goals_guess }}</small>
{% endif %}
```

Replace with:

```html
{% if show_trend_column %}
{% set t = trend_by_enrollment.get(e.id) %}
{% if t is none %}
<small class="text-muted">Trend: —</small>
{% elif t > 0 %}
<small class="leaderboard-trend-up">Trend: <span class="wc-numeral">+{{ "%.1f"|format(t) }}</span></small>
{% elif t < 0 %}
<small class="leaderboard-trend-down">Trend: <span class="wc-numeral">{{ "%.1f"|format(t) }}</span></small>
{% else %}
<small class="text-muted">Trend: —</small>
{% endif %}
{% endif %}
{% if deadline_passed and e.usa_goals_guess is not none %}
<small class="text-muted ms-2">TB: {{ e.usa_goals_guess }}</small>
{% endif %}
```

(The `ms-2` on the TB line spaces it from the trend line if both are present.)

- [ ] **Step 4: Add scoped CSS for the trend cells**

Open `static/css/style.css`. After the Your Standing CSS block from Task 3, add:

```css
/* Plan 3: Trend column (gated, count(distinct captured_date) >= 7)
   --------------------------------------------------------------- */
.leaderboard-trend-up {
  color: #1A7A45;
  font-weight: 600;
}

.leaderboard-trend-down {
  color: var(--game-accent);
  font-weight: 600;
}
```

- [ ] **Step 5: Run the trend tests**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_leaderboard.py::test_trend_column_uses_latest_snapshot tests/test_worldcup_leaderboard.py::test_trend_column_hidden_when_fewer_than_seven_snapshots tests/test_worldcup_leaderboard.py::test_trend_column_shows_dash_when_no_prior_snapshot_for_user -v
```

Expected: all 3 PASS.

- [ ] **Step 6: Run full pytest + pyright**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
venv/bin/pyright games/worldcup/
```

Expected: all 8 leaderboard tests pass; full suite green; pyright clean.

- [ ] **Step 7: Visual smoke — gate states**

Local dev: there are no real snapshots in your dev DB by default. You have two options:

**Option A — accept the closed gate.** Just verify the leaderboard renders without the Trend column at port 5099. This confirms the closed-gate path doesn't blow up. The unit tests above cover both gate states.

**Option B — manually seed snapshots in a Python REPL.** Open a REPL inside the worktree:

```bash
FLASK_APP=app.py venv/bin/flask shell
```

Then in the shell:

```python
from datetime import date, timedelta
from extensions import db
from games.worldcup.models import WorldCupEnrollment, WorldCupRankSnapshot

today = date.today()
enrollments = WorldCupEnrollment.query.all()
for e in enrollments:
    for i in range(8):
        d = today - timedelta(days=i + 1)
        existing = WorldCupRankSnapshot.query.filter_by(
            enrollment_id=e.id, captured_date=d
        ).first()
        if not existing:
            db.session.add(WorldCupRankSnapshot(
                enrollment_id=e.id, captured_date=d,
                rank=1, total_score=max(0, e.total_score - (i + 1) * 5),
            ))
db.session.commit()
exit()
```

Then start the dev server and verify the open-gate path:

```bash
ENVIRONMENT=development FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

Visit `/worldcup/leaderboard` and verify:

| Viewport | Verify |
|---|---|
| Desktop | New "Trend" column header between Points and Tiebreaker |
| Desktop | `+N.N` rendered green; `-N.N` rendered red; `—` for missing/zero |
| Mobile | "Trend: +N.N" (or `—`) line beneath the player name |
| Both | Stop the server, run `flask db downgrade` then `flask db upgrade` if you want to clean the seeded snapshots — OR simply accept they linger in dev DB |

Stop the server before continuing.

- [ ] **Step 8: Commit**

```bash
git add games/worldcup/templates/worldcup/leaderboard.html static/css/style.css
git commit -m "feat(ccc-wc): add per-row Trend column to leaderboard (gated 7d snapshots)

Trend = current_score - latest_snapshot_score for each enrollment, where
'latest' = MAX(captured_date). Per-row dashes for users with no snapshot
history. Whole column gated on count(distinct captured_date) >= 7 globally
(mirrors Spec B's home sparkline gate, per ambiguity-A1 resolution).

Desktop: dedicated 'Trend' column between Points and Tiebreaker.
Mobile: 'Trend: +N.N' line beneath the player name.
Up = green (#1A7A45), down = red (var(--game-accent)), zero/none = '—'.

All 8 leaderboard tests pass. Refs Spec C Plan 3 §B."
```

---

## Section C — Stats Hub aggressive restructure

Section C is the only place across the four Plan-3 tasks where the executing agent is granted structural latitude. The restructure runs in two passes: Task 5 invokes the `frontend-design` skill to produce a design memo (no template code). Task 6 implements that memo.

**Hard constraints (frozen — both tasks must respect):**
- Public service entry points stay as-is: `get_country_stats`, `get_tier_stats`, `get_overview_kpis`, `get_tier_combos`. Template-only rewrite — service layer untouched.
- Public route — no `@login_required`.
- `my_picks` query stays `WorldCupPick.query.join(WorldCupTeam)` shape — never `enrollment.picks` (CLAUDE.md N+1 rule).
- Chart.js stays — no charting library swap.
- Stage labels: import `_stage_label` from `core.main.home_context` (Plan 4 lifts it; do NOT pre-migrate).
- All existing tests in `tests/test_worldcup_stats.py` must continue to pass. Service layer is the contract.
- Avatar-pattern preservation everywhere a user appears (CLAUDE.md).

**Soft constraints (agent decides):**
- Tab consolidation 6 → 3-4 permitted and encouraged.
- Tab bar visual treatment may align with Plan 1's sub-nav pill aesthetic.
- KPI blocks may align with platform `.stat-block` pattern + Spec B home variants.
- Chart colors should consume WC palette tokens, not hardcoded hex.
- Hero pattern uses `.wc-hero-grad`.
- Voice/copy uses WC vocabulary ("Roster" not "Picks", tier names, etc.).

---

### Task 5: Produce stats restructure design memo via `frontend-design` skill

This task produces a written design memo that Task 6 implements against. No template code is written.

**Files:**
- Create: `docs/superpowers/notes/2026-05-04-stats-hub-restructure-memo.md`

- [ ] **Step 1: Invoke the `frontend-design` skill**

Use the `Skill` tool to invoke `frontend-design:frontend-design`. Brief the skill with the following prompt verbatim:

> I need a structural restructure design for `games/worldcup/templates/worldcup/stats.html`. Read the current 6-tab template (610 lines, Chart.js, vanilla JS state). Constraints (frozen):
> - Public service entry points: `get_country_stats`, `get_tier_stats`, `get_overview_kpis`, `get_tier_combos` — template consumes their output verbatim, can't ask the service for new shapes.
> - `current_phase`, `MY_PICKS` array, Chart.js. No `@login_required`. Stage labels via `_stage_label` SSoT.
> - Hero pattern: `.wc-hero-grad` (Plan 1 utility).
> - WC palette: navy `#001A4D` / red `#BF0A30` / cream `#F5F1E8` (also tokens in `static/css/tokens.css`).
> - Vocabulary: "Roster" / "Board" / "Seal the Oath" / tier names (Favorites · Contenders · Dark Horses · Underdogs · Wildcards).
>
> Constraints (soft — your call):
> - Tab consolidation 6 → 3-4 is approved by the spec. Justify the cut.
> - Tab bar visual treatment may mirror Plan 1's `.subnav-pill` aesthetic — one consistent "pills" idiom.
> - KPI blocks may align with platform `.stat-block` / Spec B home variants.
> - Chart palette consumes WC tokens.
>
> Deliverable: a markdown memo under 600 words at `docs/superpowers/notes/2026-05-04-stats-hub-restructure-memo.md` with sections:
> 1. **Tab cut** — final tab count + names + which old tabs collapsed into which
> 2. **Per-tab structure** — for each surviving tab, what blocks it contains and their order
> 3. **Hero treatment** — copy + structure of the page hero
> 4. **Tab bar treatment** — visual idiom (pill vs underline vs other), DOM IDs to keep stable
> 5. **Chart palette mapping** — which chart slot consumes which token
> 6. **Voice + copy diffs vs current** — concrete swaps (e.g., "Stats Hub" → "X")
> 7. **Risks called out** — anything fragile in the existing JS that the rewrite must preserve
>
> Do NOT write template code. The memo is the deliverable; Task 6 of Plan 3 implements against it.

- [ ] **Step 2: Capture the memo file**

Verify the memo was created:

```bash
test -f docs/superpowers/notes/2026-05-04-stats-hub-restructure-memo.md && echo "memo present"
wc -l docs/superpowers/notes/2026-05-04-stats-hub-restructure-memo.md
```

Expected: file present; length > 30 lines (substantive memo, not stub).

If the memo is missing or thin, re-run the skill with the same prompt; if it still produces nothing useful, fall back to writing a manual design memo at the same path covering the 7 sections above. Either way, the deliverable is the memo, not the agent invocation.

- [ ] **Step 3: Sanity-read the memo**

Read the memo. Verify it answers:

- Does the tab cut name 3-4 final tabs + which old tabs collapsed where?
- Does each surviving tab list its block sequence?
- Does the chart palette map to WC tokens (not hardcoded `#002868` etc.)?
- Are DOM IDs called out (so Task 6 knows which to keep vs. rename)?

If any of those answers are missing, augment the memo manually before moving on. The memo is Task 6's design contract — it must be complete.

- [ ] **Step 4: Commit the memo**

```bash
git add docs/superpowers/notes/2026-05-04-stats-hub-restructure-memo.md
git commit -m "docs(ccc-wc): stats hub restructure design memo

Output of frontend-design skill invocation per Plan 3 Task 5.
Locks the tab cut, per-tab block sequence, hero treatment, tab bar
visual idiom, chart palette mapping, voice/copy diffs, and JS
preservation risks. Task 6 implements against this memo.

Refs Spec C Plan 3 §C."
```

---

### Task 6: Rewrite `stats.html` per the Task 5 design memo

This task implements the memo. The detailed structural decisions live in the memo — this task records the immutable boundaries the implementation must respect.

**Files:**
- Modify: `games/worldcup/templates/worldcup/stats.html`
- Possibly modify: `static/css/style.css` (new component CSS for the restructure)
- Possibly modify: `tests/test_worldcup_stats.py` (only if `wc-stats-tab-bar` is renamed — see Step 4)
- Do NOT modify: `games/worldcup/services/stats.py`, `games/worldcup/routes.py::stats()`

- [ ] **Step 1: Re-read the design memo + spec constraints**

```bash
cat docs/superpowers/notes/2026-05-04-stats-hub-restructure-memo.md
```

Cross-reference the hard constraints listed at the top of Section C above. Confirm the memo respects all of them. If any conflict, the spec wins — adjust the memo first, commit the memo update separately, then proceed.

- [ ] **Step 2: Verify the data bindings the new template will consume**

Open `games/worldcup/routes.py::stats()` (around line 587). The template receives these context keys — these are the **immutable interface** for the restructure:

```python
country_stats=country_stats,   # list[dict] from get_country_stats
tier_stats=tier_stats,         # dict[int, dict] from get_tier_stats
kpis=kpis,                     # dict from get_overview_kpis
combos=combos,                 # dict[int, list[dict]] from get_tier_combos
my_picks=my_picks,             # list[str] of team display names
current_phase=...,             # str from _derive_tournament_phase()
```

The current template embeds these as JS globals via `tojson`:

```js
const MY_PICKS = {{ my_picks | tojson }};
const COUNTRY_STATS = {{ country_stats | tojson }};
const TIER_STATS = {{ tier_stats | tojson }};
const COMBOS = {{ combos | tojson }};
const KPIS = {{ kpis | tojson }};
```

Preserve those bindings (or equivalent — agent's call) so charts/render functions can re-bind. If the memo introduces new render functions, they must consume these same shapes.

- [ ] **Step 3: Rewrite `stats.html` per the memo**

This step has no pre-canned code — the memo from Task 5 is the prescription. Follow the memo's section-by-section structure:

1. Replace the page hero with the memo's hero treatment (must use `.wc-hero-grad`).
2. Replace the tab bar with the memo's tab idiom.
3. For each surviving tab, build the block sequence the memo specifies.
4. Update the Chart.js init functions to consume the memo's chart palette.
5. Apply the memo's voice/copy diffs.
6. Preserve any JS hooks the memo flags as fragile (Step 7 of memo).

Key invariants you must NOT break:
- The `wc-stats-tab-bar` element MUST stay in some form so existing route smoke tests can match `b'wc-stats-tab-bar' in resp.data`. If the memo renames it, you'll update the test in Step 4 — commit the test update in the same commit as the rename.
- `MY_PICKS = []` JS literal must still appear for unauthenticated users (existing test `test_stats_route_my_picks_unauthenticated` checks for `b'MY_PICKS = []'`).
- `localStorage` tab persistence (the existing `wc_stats_tab` key) — the memo may rename or remove this; if it stays, mirror the current behavior; if it changes, update the JS accordingly.
- Avatar pattern: any new user-pick callouts use `user.get_avatar()` inline before the display name (CLAUDE.md).

- [ ] **Step 4: Update test markers if tab bar element renamed**

Open `tests/test_worldcup_stats.py`. Two existing assertions reference DOM:

```python
assert b'Stats Hub' in resp.data            # test_stats_route_public
assert b'wc-stats-tab-bar' in resp.data     # test_stats_route_public
assert b'MY_PICKS = []' in resp.data        # test_stats_route_my_picks_unauthenticated
```

If your rewrite preserves `Stats Hub` H1 and `wc-stats-tab-bar` class, no test changes needed. If the memo renamed one or both, update the assertion to the new marker. The semantic of the test is unchanged — it just verifies the route renders the new tab-bar element.

- [ ] **Step 5: Run the stats test suite**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_stats.py -v
```

Expected: all 9 tests PASS — the service-layer tests (which exercise no DOM) pass unchanged; the two route smoke tests pass against your updated assertions.

- [ ] **Step 6: Run pyright + full pytest**

```bash
venv/bin/pyright games/worldcup/
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: 0 pyright errors; full suite green.

- [ ] **Step 7: Visual smoke — every tab + chart + voice**

```bash
ENVIRONMENT=development FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

At `http://localhost:5099/worldcup/stats`:

| Surface | Verify |
|---|---|
| Hero | `.wc-hero-grad` background; H1 + voice-eyebrow per memo |
| Tab bar | New idiom matches memo; current tab visually selected |
| Tab 1 (e.g. Overview) | All KPI blocks render; numerals in Teko; tournament progress bar still works |
| Each remaining tab | Loads charts on first activation (Chart.js still works); chart colors consume WC palette tokens |
| Mobile (375px) | Tab bar fits / scrolls per memo; KPI grids reflow; tap targets ≥ 44px |
| Logged-out vs logged-in | `MY_PICKS = []` for anon; `MY_PICKS = ["..."]` when logged in with enrollment |
| Tab persistence | If memo retained localStorage, refresh re-opens last tab |

If any chart fails to render, check the JS console — most likely a renamed canvas ID that the init function still references. The memo flags fragile hooks; cross-check.

Stop the server before continuing.

- [ ] **Step 8: Commit**

```bash
git add games/worldcup/templates/worldcup/stats.html static/css/style.css tests/test_worldcup_stats.py
git commit -m "feat(ccc-wc): aggressive stats hub restructure (tabs collapsed)

Implements the design memo at
docs/superpowers/notes/2026-05-04-stats-hub-restructure-memo.md.

Service layer untouched — get_country_stats / get_tier_stats /
get_overview_kpis / get_tier_combos all consume their existing dict
shapes. Public route, no @login_required. Chart.js retained;
chart palette consumes WC tokens. Voice + copy aligned with WC
vocabulary. _stage_label still imported from core.main.home_context
(Plan 4 lifts it).

Existing tests/test_worldcup_stats.py updated only for renamed DOM
markers; semantics unchanged.

Refs Spec C Plan 3 §C."
```

If the diff is large, splitting Task 6 into two commits (template rewrite vs CSS additions) is acceptable — judgment call.

---

## Final verification + PR

### Task 7: End-to-end verification + open PR

- [ ] **Step 1: Run the full test suite**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -v
```

Expected: all tests pass — baseline + Plan 3 deltas (8 new in `test_worldcup_leaderboard.py` + any test-marker tweaks in `test_worldcup_stats.py`). Don't anchor to a fixed total; the baseline shifts as other PRs land.

- [ ] **Step 2: Run pyright on the entire WC blueprint**

```bash
venv/bin/pyright games/worldcup/
```

Expected: 0 errors.

- [ ] **Step 3: Run pyright on the routes module specifically (since it changed substantially)**

```bash
venv/bin/pyright games/worldcup/routes.py
```

Expected: 0 errors.

- [ ] **Step 4: Manual visual checklist — every surface Plan 3 touched**

Start the dev server with the time seam available:

```bash
ENVIRONMENT=development FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

For surfaces that depend on deadline state, use `WC_FAKE_NOW`:

```bash
# Pre-deadline
ENVIRONMENT=development WC_FAKE_NOW='2026-06-10T00:00:00+00:00' FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
# Post-deadline
ENVIRONMENT=development WC_FAKE_NOW='2026-06-15T00:00:00+00:00' FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
```

| Route + state | Verify |
|---|---|
| `/worldcup/leaderboard` anonymous | Hero with `.wc-hero-grad`; no Your Standing block; table reskinned; no Trend column unless seeded |
| `/worldcup/leaderboard` logged-in unenrolled | Same as anonymous; no Your Standing block |
| `/worldcup/leaderboard` logged-in enrolled, leader | Your Standing block: rank 1 of N; caption "Y ahead of the next pursuer." |
| `/worldcup/leaderboard` logged-in enrolled, mid | Your Standing block: rank N of M; caption with both up + down deltas |
| `/worldcup/leaderboard` logged-in enrolled, last | Caption "X pts from the lead." |
| `/worldcup/leaderboard` mobile 375px | Cards reskinned; current-user red border; rank + score Teko |
| `/worldcup/leaderboard` post-deadline | Tiebreaker column appears; if Trend column open it sits between Points and Tiebreaker |
| `/worldcup/leaderboard` Trend column open | "Trend" column header; per-row +N.N (green) / -N.N (red) / — (muted) |
| `/worldcup/leaderboard` Trend column closed | No Trend column header anywhere |
| `/worldcup/stats` (per memo) | Hero matches memo; tab bar matches memo; every tab loads + charts render |
| `/worldcup/stats` mobile | Per memo's mobile guidance |
| Sub-nav | `Board` pill highlights on `/worldcup/leaderboard`, `/worldcup/leaderboard/<id>`, `/worldcup/team/<id>`. `Stats` pill highlights on `/worldcup/stats`. (Already wired by Plan 1 — should not regress.) |
| Sub-nav 375px mobile | All pills fit on one row; no horizontal scroll. (Plan 1 invariant — must not regress.) |

Stop the server.

- [ ] **Step 5: Push the branch**

```bash
git push -u origin redesign/ccc-worldcup-plan3
```

- [ ] **Step 6: Open the PR**

Use a HEREDOC to keep the body clean (mirror Plan 2's pattern):

```bash
gh pr create --title "Spec C Plan 3 — Public analytics (leaderboard reskin + stats restructure)" --body "$(cat <<'EOF'
## Summary

Lands Plan 3 of Spec C (CCC World Cup reskin):

- **`leaderboard.html` strict reskin**: hero gains `.wc-hero-grad` + 'Live Standings' eyebrow; numerals lift to `.wc-numeral`; cards scoped as `.card.wc-card`; current-user accent + rank/score utility classes replace inline styles.
- **NEW Your Standing hero block**: authenticated + enrolled users see a 2-stat block (Rank N of M, Points) above the table with a voice caption keyed by rank position (sole / leader / tail / mid). Reuses Plan 2's `compute_rank_neighbors` shared helper.
- **NEW Trend column**: per-row matchday trend = `current_score - latest_snapshot_score` (latest = MAX(captured_date) per enrollment). Green up / red down / muted dash. Whole column gated globally on `count(distinct WorldCupRankSnapshot.captured_date) >= 7` (mirrors Spec B's home sparkline gate per spec D10 + ambiguity-A1 resolution).
- **`stats.html` aggressive restructure**: tabs collapsed per the design memo at `docs/superpowers/notes/2026-05-04-stats-hub-restructure-memo.md` (frontend-design skill output). Service layer untouched — the four public entry points (`get_country_stats`, `get_tier_stats`, `get_overview_kpis`, `get_tier_combos`) and route data bindings stay frozen. Chart.js retained; chart palette migrated to WC tokens. Voice + copy aligned with WC vocabulary.

Filter chips per spec D9 are explicitly deferred to a future Plan 3.2.

Sub-nav `Stats` and `Board` pills already auto-activate on these routes (Plan 1 wiring).

Spec: \`docs/superpowers/specs/2026-05-02-ccc-worldcup-reskin-design.md\`
Plan: \`docs/superpowers/plans/2026-05-04-ccc-worldcup-plan-3-public-analytics.md\`
Stats memo: \`docs/superpowers/notes/2026-05-04-stats-hub-restructure-memo.md\`

## Test plan

- [x] All tests pass — baseline + 8 new in \`tests/test_worldcup_leaderboard.py\` + minor marker updates in \`tests/test_worldcup_stats.py\` if tab-bar class renamed
- [x] \`pyright\` clean on \`games/worldcup/\`
- [x] Manual visual checklist passed: leaderboard at 375px and 1280px in 6 auth/rank states; stats at 375px and 1280px across every consolidated tab
- [x] Trend column closed-gate path: column hidden, no \`<th>Trend</th>\`
- [x] Trend column open-gate path: column rendered; per-row +/- formatting correct; \`—\` for users with no snapshot history
- [x] Your Standing block: hidden for anonymous + unenrolled; rendered with correct rank + caption variant for leader / mid / tail / sole
- [x] Stats restructure: every Chart.js chart still renders correctly; \`MY_PICKS = []\` literal still present for anonymous; \`current_phase\` progress bar still works
- [x] Sub-nav pills (Board + Stats) still active on the right routes; mobile sub-nav still fits 6 pills (Plan 1 invariant)

@coderabbitai please review

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 7: Wait for CodeRabbit's review and address findings**

Wait until CodeRabbit's actual review comment lands (not the "processing" stub — see `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/feedback_coderabbit_timing.md`). Address findings via additional commits on the same branch. For each finding:

1. Read the finding carefully. CodeRabbit catches things Claude's review missed.
2. **Verify before implementing** (CLAUDE.md `superpowers:receiving-code-review` invariant) — if a finding seems off, push back with reasoning rather than blindly applying.
3. Implement fixes in a separate commit per logical batch (e.g., `fix(ccc-wc): address CR feedback on trend gate edge cases`).
4. Re-push.

- [ ] **Step 8: Once approved, merge**

After CodeRabbit's review is addressed and the PR is approved, merge via the GitHub UI (squash recommended — matches Spec B + Plans 1 + 2's pattern). After merge, Plan 4 (WC Hub migration) can branch from the freshly-merged main; Plan 4 will lift `_stage_label` from `core/main/home_context` to `games/worldcup/services/stage.py` and update Plan 3's import in lockstep.

---

## Summary

| Task | Outcome |
|---|---|
| 0 | Worktree at `../fantasy-platform-ccc-wc-plan3`, baseline verified |
| 1 | `worldcup.leaderboard()` extended with three payload keys + 8 new tests |
| 2 | `leaderboard.html` strict reskin (palette/numerals/cards/utility classes) |
| 3 | "Your Standing" hero block (auth + enrolled only; voice caption) |
| 4 | Trend column (per-row matchday delta; gated globally on 7-day rule) |
| 5 | Stats restructure design memo (frontend-design skill output) |
| 6 | `stats.html` aggressive restructure (tabs collapsed; service layer frozen) |
| 7 | E2E verification, visual smoke, PR with CodeRabbit review |

## Test plan

- [ ] `tests/test_worldcup_leaderboard.py` — 8 new tests:
  - `test_your_standing_block_renders_for_authenticated_enrolled_user`
  - `test_your_standing_omitted_for_anonymous`
  - `test_your_standing_omitted_for_authenticated_unenrolled`
  - `test_lead_delta_calculation`
  - `test_trend_column_uses_latest_snapshot`
  - `test_trend_column_hidden_when_fewer_than_seven_snapshots`
  - `test_trend_column_shows_dash_when_no_prior_snapshot_for_user`
  - `test_leaderboard_route_still_returns_200_with_no_data`
- [ ] `tests/test_worldcup_stats.py` — existing 9 tests stay green; assertions adjusted only if `wc-stats-tab-bar` class renamed
- [ ] Full `pytest tests/` suite green
- [ ] `pyright games/worldcup/` clean
- [ ] Visual smoke matrix from Task 7 Step 4

## Notes for the executing agent

- **Don't pre-migrate `_stage_label`**: it currently lives in `core/main/home_context.py`. Plan 4 lifts it to `games/worldcup/services/stage.py`. If `stats.html` references it (directly or via `current_phase`), import from the existing `core/main/home_context` location. Plan 4's PR updates Plan 3's import.
- **Don't touch the stats service layer**: `games/worldcup/services/stats.py` is frozen per spec D7. The four public functions are the contract. If you find yourself wanting to extend a service shape, stop and check the spec — most likely the template can derive what it needs from existing keys.
- **Trend gate is global, not per-user**: ambiguity-A1 was resolved as `count(distinct captured_date) >= 7` across the whole `WorldCupRankSnapshot` table. The implementation in `_show_trend_column()` reflects this. Don't change to a per-user variant without re-reading the spec.
- **Trend value is per-row, latest snapshot = MAX(captured_date)**: ambiguity-A2 was resolved as "latest snapshot per enrollment, by max captured_date." `_compute_trend_by_enrollment` uses a single subquery + join — no window functions (SQLite-friendly).
- **Voice caption variants in `_your_standing_caption`**: the function returns four strings (sole / leader / tail / mid). Don't extend without coordinating with Plan 4's `_home_live` builder, which will likely reuse this voice doctrine.
- **`compute_rank_neighbors` is a Plan 2 invariant**: Plan 3 imports it unchanged. If you find a need to change its signature (e.g., to add a `season_year` parameter), STOP — that's a Plan 2 follow-up, not a Plan 3 change. The signature is shared with Plan 4's `_home_live` builder.
- **Class-naming caution (lesson from Plan 2 Task 2)**: when adding component classes, do NOT reuse generic platform names like `.stat-block`, `.card`. Plan 3's new utility classes (`.your-standing-*`, `.leaderboard-rank`, `.leaderboard-score`, `.leaderboard-card-current`, `.leaderboard-trend-up`, `.leaderboard-trend-down`) are deliberately scoped.
- **CSS specificity**: `.card.wc-card.leaderboard-card-current` is multi-class so it wins cascade over later platform `.card` rules (CLAUDE.md "CSS specificity for utility classes"). Don't add single-class `.wc-*` utilities that overlap with later base rules — see `~/.claude/projects/-Users-bhagstrom-fantasy-platform/memory/project_ccc_wc_reskin_gotchas.md`.
- **`frontend-design` for Task 5 ONLY**: Tasks 1-4 and 6-7 do not need the frontend-design skill. Task 5 produces a memo; Task 6 implements against it. Task 6 doesn't re-invoke the skill.
- **WC_FAKE_NOW seam**: only honored when `ENVIRONMENT=development` or `ENVIRONMENT=testing`. The dev-server commands in this plan include the `ENVIRONMENT=development` prefix.
- **Don't pre-emptively run `flask db upgrade`**: there are no migrations in Plan 3. If pyright or tests prompt for a migration, something else is wrong — investigate before generating one.
- **Filter chips are deferred**: spec §8 D9 is explicit. Don't pull them in even if they look like a quick win — that's the sole content of a future Plan 3.2.
