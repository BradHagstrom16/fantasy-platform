# CCC Home Redesign (Spec B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the home page wholesale with four state-aware variants (logged-out / pre-WC / live-WC / post-WC) on the CCC brand foundation merged in Spec A, plus a daily snapshot infrastructure powering live-state dossier sparklines.

**Architecture:** Thin shell `index.html` dispatches to one of four `_home_<state>.html` partials based on `worldcup_state()` (a 3-phase helper reading `TOURNAMENT_DEADLINE_UTC` + match #104 completion). Per-state data is assembled by `core/main/home_context.py` builders. New `WorldCupRankSnapshot` model + nightly cron seed the sparkline. New `/* === HOME (CCC) === */` section in `style.css` ports component classes from the design bundle, scoped under a `.home-shell` wrapper.

**Tech Stack:** Flask, Flask-SQLAlchemy 2.0, Flask-Migrate (Alembic), Jinja2, Bootstrap 5.3, vanilla JS, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-28-ccc-home-redesign-design.md` — read this in full before starting. Layout diagrams, decision rationale, and data-source mappings live there. This plan implements that spec.

**Branch:** `redesign/ccc-home` in worktree `../fantasy-platform-ccc-home`.

**Frontend-design skill usage:** Tasks marked `[FD]` benefit from `/frontend-design:frontend-design` invocation during implementation — these are the parts where the spec goes beyond the design bundle (post-WC undesigned components, wide-desktop variants, polish microinteractions). Direct ports of existing mockups don't need it.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `core/main/home_context.py` | Create | Per-state data assembly: 4 builder functions, 1 tagline helper |
| `core/main/routes.py` | Modify | Rewrite `index()` to dispatch on `worldcup_state()` |
| `core/main/templates/main/index.html` | Modify (rewrite) | Thin shell that includes one of 4 `_home_<state>.html` |
| `core/main/templates/main/_home_out.html` | Create | Logged-out marketing surface |
| `core/main/templates/main/_home_pre.html` | Create | Pre-deadline state shell |
| `core/main/templates/main/_home_live.html` | Create | Live tournament state shell |
| `core/main/templates/main/_home_post.html` | Create | Post-tournament recap state shell |
| `core/main/templates/main/_countdown_card.html` | Create | Pre-state DD:HH:MM:SS countdown |
| `core/main/templates/main/_ballot_card.html` | Create | Pre-state sealed-roster card (9-flag grid) |
| `core/main/templates/main/_submit_picks_cta.html` | Create | Pre-state enrolled-no-picks CTA card |
| `core/main/templates/main/_join_cta_card.html` | Create | Unenrolled pre-deadline CTA card |
| `core/main/templates/main/_view_cta_card.html` | Create | Unenrolled post-deadline CTA card |
| `core/main/templates/main/_dossier_card.html` | Create | Live-state rank/sparkline/stats card |
| `core/main/templates/main/_recent_results.html` | Create | Live-state completed-matches strip |
| `core/main/templates/main/_champion_banner.html` | Create | Post-state champion banner |
| `core/main/templates/main/_game_tiles_compact.html` | Create | 3-tile compact game strip (pre/live/post) |
| `core/main/templates/main/_commish_note.html` | Create | Long-form Commish narrative (file-edited; ships with seed) |
| `core/main/templates/main/_dispatches.html` | Create | Short-feed dispatches (file-edited; ships empty) |
| `core/main/templates/main/_game_card.html` | (untouched) | Used as-is by `_home_out.html` |
| `games/worldcup/services/state.py` | Create | `worldcup_state()` helper + dev-only `WC_FAKE_NOW` seam |
| `games/worldcup/services/__init__.py` | Modify | Re-export `worldcup_state` |
| `games/worldcup/models.py` | Modify | Add `WorldCupRankSnapshot` model |
| `games/worldcup/cli.py` | Modify | Add `snapshot-ranks` command with `--backfill` flag |
| `games/registry.py` | Modify | Add `'completed'` to `GameStatus` Literal |
| `migrations/versions/XXXX_add_worldcup_rank_snapshot.py` | Create (auto-generated) | Single new table migration |
| `static/css/tokens.css` | Modify | Add 3 Spec B tokens at bottom |
| `static/css/style.css` | Modify | Add `/* === HOME (CCC) === */` section after admin-eyebrow block |
| `static/js/countdown.js` | Create | Vanilla JS countdown ticker (~25 lines) |
| `tests/test_home_context.py` | Create | Unit tests for state detection + 4 context builders |

**Total:** 19 new files, 7 modified.

---

## Task 1: Worktree setup

**Files:**
- N/A (workspace operation)

- [ ] **Step 1: Confirm you're at the repo root on `main`**

```bash
cd /Users/bhagstrom/fantasy-platform
git status
git branch --show-current
```

Expected: branch is `main`, working tree clean (or only untracked `fantasy-platform-and-world-cup-design/`).

- [ ] **Step 2: Create the worktree on a new branch off `main`**

```bash
git worktree add ../fantasy-platform-ccc-home -b redesign/ccc-home main
```

Expected: `Preparing worktree (new branch 'redesign/ccc-home')` followed by `HEAD is now at <hash> ...`.

- [ ] **Step 3: Switch into the worktree**

```bash
cd ../fantasy-platform-ccc-home
git branch --show-current
```

Expected: `redesign/ccc-home`.

- [ ] **Step 4: Set up the venv link and instance dir**

```bash
ln -s /Users/bhagstrom/fantasy-platform/venv venv
mkdir -p instance
ls -la venv
```

Expected: `venv -> /Users/bhagstrom/fantasy-platform/venv` and `instance/` exists. Symlinking the venv avoids a multi-minute reinstall.

- [ ] **Step 5: Verify the app boots in the worktree**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db upgrade
```

Expected: existing migrations apply cleanly to a fresh `instance/fantasy_platform.db`.

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/python -c "from app import create_app; app = create_app(); print('OK')"
```

Expected: `OK`. No need to start the server — that comes after each visual task.

---

## Task 2: WorldCupRankSnapshot model + migration

**Files:**
- Modify: `games/worldcup/models.py` (append at end)
- Create: `migrations/versions/XXXX_add_worldcup_rank_snapshot.py` (auto-generated by Alembic)

- [ ] **Step 1: Add the model to `games/worldcup/models.py`**

Append at the bottom of the file:

```python
class WorldCupRankSnapshot(db.Model):
    """Daily snapshot of each enrollment's rank + total_score.

    Written by ``flask worldcup snapshot-ranks``, run nightly via cron.
    Powers the live-state dossier sparkline and week-delta calculations
    on the home page (Spec B).
    """
    __tablename__ = 'worldcup_rank_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(
        db.Integer, db.ForeignKey('worldcup_enrollment.id'),
        nullable=False, index=True
    )
    captured_at = db.Column(db.DateTime, nullable=False, index=True)
    rank = db.Column(db.Integer, nullable=False)
    total_score = db.Column(db.Float, nullable=False)

    enrollment = db.relationship('WorldCupEnrollment', backref='rank_snapshots')

    __table_args__ = (
        db.UniqueConstraint(
            'enrollment_id', 'captured_at',
            name='unique_worldcup_snapshot_per_day'
        ),
    )

    def __repr__(self):
        return f'<WorldCupRankSnapshot enr={self.enrollment_id} at={self.captured_at} rank={self.rank}>'
```

- [ ] **Step 2: Re-export the model so Alembic discovers it**

Open `models/__init__.py`. If it re-exports `WorldCupEnrollment`, append `WorldCupRankSnapshot` to the same import line:

```bash
grep -n "WorldCup" /Users/bhagstrom/fantasy-platform/models/__init__.py
```

If `WorldCupRankSnapshot` is not present, edit the existing `from games.worldcup.models import ...` line to include it.

- [ ] **Step 3: Generate the migration**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db migrate -m "add worldcup rank snapshot"
```

Expected: a new file appears under `migrations/versions/` with a hash prefix. Output ends with `Generating migrations/versions/<hash>_add_worldcup_rank_snapshot.py ... done`.

- [ ] **Step 4: Have the migration reviewed**

Use the `migration-reviewer` agent to scan the new migration file for safety. The migration should be a single `op.create_table('worldcup_rank_snapshot', ...)` with a `op.create_index` for the `enrollment_id` and `captured_at` columns and a `op.create_unique_constraint`. The downgrade should be a single `op.drop_table`. No destructive ops.

- [ ] **Step 5: Apply the migration in dev**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db upgrade
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade <prev> -> <new>, add worldcup rank snapshot`.

- [ ] **Step 6: Verify round-trip**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db downgrade
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db upgrade
```

Expected: clean downgrade then re-upgrade with no errors.

- [ ] **Step 7: Commit**

```bash
git add games/worldcup/models.py models/__init__.py migrations/versions/
git commit -m "feat(worldcup): add WorldCupRankSnapshot model + migration

Daily rank/score snapshot per enrollment, powering the live-state
dossier sparkline and week-delta on the home page (Spec B)."
```

---

## Task 3: snapshot-ranks CLI command

**Files:**
- Modify: `games/worldcup/cli.py`

- [ ] **Step 1: Update imports in `games/worldcup/cli.py`**

Add to the imports at the top:

```python
from datetime import datetime, timedelta, timezone
from games.worldcup.constants import SEASON_YEAR, WORLDCUP_TZ
from games.worldcup.models import WorldCupTeam, WorldCupMatch, WorldCupEnrollment, WorldCupRankSnapshot
```

(Adjust the existing imports — do not add a duplicate `datetime` import. `WORLDCUP_TZ` is already exported from constants.py per `grep` earlier; `WorldCupRankSnapshot` is the new model.)

- [ ] **Step 2: Append the new command at the bottom of `games/worldcup/cli.py`**

```python
@worldcup_cli.command('snapshot-ranks')
@click.option('--backfill', type=int, default=0,
              help='Backfill N past days (one snapshot per day) using current rank/score')
def snapshot_ranks(backfill: int):
    """Capture today's rank + score snapshot for every enrollment.

    Idempotent: re-running for the same day is a no-op.
    With --backfill N, writes snapshots for the past N days using the
    current rank/score (best-effort backfill for first deploy).
    """
    days_to_capture = list(range(backfill, -1, -1)) if backfill else [0]

    for days_ago in days_to_capture:
        target_day_local = (
            datetime.now(WORLDCUP_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
            - timedelta(days=days_ago)
        )
        captured_at_utc = target_day_local.astimezone(timezone.utc).replace(tzinfo=None)

        enrollments = (
            WorldCupEnrollment.query
            .filter_by(season_year=SEASON_YEAR)
            .order_by(WorldCupEnrollment.total_score.desc())
            .all()
        )

        rows_added = 0
        for rank, enr in enumerate(enrollments, start=1):
            existing = WorldCupRankSnapshot.query.filter_by(
                enrollment_id=enr.id, captured_at=captured_at_utc
            ).first()
            if existing:
                continue
            db.session.add(WorldCupRankSnapshot(
                enrollment_id=enr.id,
                captured_at=captured_at_utc,
                rank=rank,
                total_score=enr.total_score,
            ))
            rows_added += 1

        db.session.commit()
        click.echo(f'Snapshot for {captured_at_utc.date()} — {rows_added} new rows')
```

(Note `.replace(tzinfo=None)` on `captured_at_utc` — Flask-SQLAlchemy with SQLite stores naive UTC datetimes for `db.DateTime`; matches existing patterns in `models.py`'s `created_at` defaults.)

- [ ] **Step 3: Smoke test the command (no enrollments yet → 0 rows)**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks
```

Expected: `Snapshot for YYYY-MM-DD — 0 new rows` (no enrollments in fresh dev DB yet).

- [ ] **Step 4: Smoke test backfill mode**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks --backfill 3
```

Expected: 4 lines (today + 3 backdated), each `0 new rows`.

- [ ] **Step 5: Verify idempotency by re-running**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks
```

Expected: still `0 new rows` (no enrollments to snapshot, but also no errors and no double-writes — the unique constraint never trips because we filter first).

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/cli.py
git commit -m "feat(worldcup): add snapshot-ranks CLI with --backfill flag

Daily snapshot writer for the rank-snapshot table. Idempotent — safe
to re-run any day. Backfill mode for first-deploy seeding."
```

---

## Task 4: worldcup_state() helper + dev-only WC_FAKE_NOW seam (TDD)

**Files:**
- Create: `games/worldcup/services/state.py`
- Modify: `games/worldcup/services/__init__.py`
- Create: `tests/test_home_context.py` (initial — three state tests)

- [ ] **Step 1: Create the test file with the three state-detection tests**

`tests/test_home_context.py`:

```python
"""Unit tests for home-page state detection and context assembly (Spec B)."""
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db


@pytest.fixture
def app():
    """Testing app with in-memory SQLite + WC_FAKE_NOW disabled."""
    os.environ.pop('WC_FAKE_NOW', None)
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _seed_final_match(completed: bool, winner_id: int | None = None):
    """Seed match #104 (the Final). Used to flip live → post."""
    from games.worldcup.models import WorldCupMatch
    match = WorldCupMatch(
        match_number=104,
        stage='final',
        is_completed=completed,
        winner_team_id=winner_id,
    )
    db.session.add(match)
    db.session.commit()


def test_worldcup_state_pre_when_before_deadline(app):
    """Before TOURNAMENT_DEADLINE_UTC, state is 'pre'."""
    from games.worldcup.services.state import worldcup_state
    # Default: TOURNAMENT_DEADLINE_UTC = 2026-06-11 19:00 UTC. Today is well before.
    with app.app_context():
        # In test runs after kickoff this would naturally fail; force-mock:
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['WC_FAKE_NOW'] = '2026-05-01T00:00:00Z'
        try:
            assert worldcup_state() == 'pre'
        finally:
            del os.environ['WC_FAKE_NOW']
            os.environ.pop('ENVIRONMENT', None)


def test_worldcup_state_live_after_deadline_no_final(app):
    """After deadline + final not complete, state is 'live'."""
    from games.worldcup.services.state import worldcup_state
    with app.app_context():
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['WC_FAKE_NOW'] = '2026-06-15T00:00:00Z'
        try:
            assert worldcup_state() == 'live'
        finally:
            del os.environ['WC_FAKE_NOW']
            os.environ.pop('ENVIRONMENT', None)


def test_worldcup_state_post_when_final_completed(app):
    """After deadline + final marked complete, state is 'post'."""
    from games.worldcup.services.state import worldcup_state
    with app.app_context():
        _seed_final_match(completed=True, winner_id=None)
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['WC_FAKE_NOW'] = '2026-07-20T00:00:00Z'
        try:
            assert worldcup_state() == 'post'
        finally:
            del os.environ['WC_FAKE_NOW']
            os.environ.pop('ENVIRONMENT', None)
```

- [ ] **Step 2: Run the tests — verify they fail**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/test_home_context.py -v
```

Expected: 3 errors with `ModuleNotFoundError: No module named 'games.worldcup.services.state'`.

- [ ] **Step 3: Implement the helper at `games/worldcup/services/state.py`**

```python
"""World Cup tournament-state detection for home-page rendering.

Single function: ``worldcup_state()`` returns 'pre' | 'live' | 'post'.

Used by ``core/main/routes.py`` to dispatch the home page to the
correct state partial. Spec B section 4a is the canonical reference.
"""
import os
from datetime import datetime, timezone
from typing import Literal

from games.worldcup.constants import TOURNAMENT_DEADLINE_UTC
from games.worldcup.models import WorldCupMatch

WorldCupState = Literal['pre', 'live', 'post']

FINAL_MATCH_NUMBER = 104  # The Final per FIFA bracket numbering


def _now_utc() -> datetime:
    """Current UTC time, with a development-only test seam.

    In dev (ENVIRONMENT=development), if WC_FAKE_NOW is set to an
    ISO 8601 string, return that instead of real time. Production
    never reads WC_FAKE_NOW.
    """
    if os.environ.get('ENVIRONMENT') == 'development':
        fake = os.environ.get('WC_FAKE_NOW')
        if fake:
            return datetime.fromisoformat(fake.replace('Z', '+00:00'))
    return datetime.now(timezone.utc)


def worldcup_state() -> WorldCupState:
    """Return the current World Cup phase.

    pre  — picks open, deadline not yet passed
    live — deadline passed, final (#104) not yet marked complete
    post — final match marked complete (single source of truth per Spec B D7)
    """
    if _now_utc() < TOURNAMENT_DEADLINE_UTC:
        return 'pre'
    final = WorldCupMatch.query.filter_by(
        match_number=FINAL_MATCH_NUMBER, is_completed=True
    ).first()
    return 'post' if final is not None else 'live'
```

- [ ] **Step 4: Re-export from `games/worldcup/services/__init__.py`**

Open the file and append (or merge with existing exports):

```python
from games.worldcup.services.state import worldcup_state, WorldCupState

__all__ = [..., 'worldcup_state', 'WorldCupState']
```

If `__all__` doesn't exist, just add the import — Python's import system handles re-export via `from games.worldcup.services import worldcup_state`.

- [ ] **Step 5: Run the tests — verify they pass**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/test_home_context.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Run pyright on the new file**

```bash
venv/bin/pyright games/worldcup/services/state.py
```

Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add games/worldcup/services/state.py games/worldcup/services/__init__.py tests/test_home_context.py
git commit -m "feat(worldcup): add worldcup_state() phase detection helper

3-phase helper (pre/live/post) with dev-only WC_FAKE_NOW test seam.
Used by the home page route to dispatch to per-state partials. Spec B
section 4a."
```

---

## Task 5: build_home_context() — _context_out() (TDD)

**Files:**
- Create: `core/main/home_context.py`
- Modify: `tests/test_home_context.py` (append 1 test)

- [ ] **Step 1: Append the test to `tests/test_home_context.py`**

```python
def test_context_out_basic(app):
    """Logged-out context returns game tiles + total_enrolled."""
    from core.main.home_context import build_home_context
    with app.app_context():
        ctx = build_home_context(None, None)
        assert 'available_games' in ctx
        assert 'coming_soon_games' in ctx
        assert ctx['total_enrolled'] == 0  # no enrollments seeded
        # WC is the only open game in the registry currently
        assert any(g.slug == 'worldcup' for g in ctx['available_games'])
```

- [ ] **Step 2: Run the new test — verify it fails**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/test_home_context.py::test_context_out_basic -v
```

Expected: `ModuleNotFoundError: No module named 'core.main.home_context'`.

- [ ] **Step 3: Create `core/main/home_context.py` with `_context_out()`**

```python
"""Per-state data assembly for the home page (Spec B section 4).

Public entry point: ``build_home_context(user, state)`` dispatches to
one of four private builders based on state, returning a dict the
template consumes via ``**ctx``.
"""
from typing import Optional, Any

from flask_login import AnonymousUserMixin

from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment
from games.worldcup.services.state import WorldCupState
from games.registry import (
    available_games, coming_soon_games, joined_games,
)


def build_home_context(user: Any, state: Optional[WorldCupState]) -> dict:
    """Assemble the render context for the home page in the given state.

    state=None for unauthenticated users (logged-out marketing surface).
    For authenticated users, state must be 'pre' | 'live' | 'post'.
    """
    if state is None:
        return _context_out()
    enrollment = WorldCupEnrollment.query.filter_by(
        user_id=user.id, season_year=SEASON_YEAR
    ).first()
    if state == 'pre':
        return _context_pre(user, enrollment)
    if state == 'live':
        return _context_live(user, enrollment)
    return _context_post(user, enrollment)


def _context_out() -> dict:
    """Logged-out marketing surface — no user, no WC enrollment."""
    anon = AnonymousUserMixin()
    return {
        'available_games': available_games(anon),
        'coming_soon_games': coming_soon_games(),
        'total_enrolled': WorldCupEnrollment.query.filter_by(
            season_year=SEASON_YEAR
        ).count(),
    }


# Stubs for the other three; filled in by Tasks 6-8.
def _context_pre(user, enrollment): raise NotImplementedError
def _context_live(user, enrollment): raise NotImplementedError
def _context_post(user, enrollment): raise NotImplementedError
```

- [ ] **Step 4: Run the test — verify it passes**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/test_home_context.py::test_context_out_basic -v
```

Expected: 1 passed.

- [ ] **Step 5: Run pyright**

```bash
venv/bin/pyright core/main/home_context.py
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add core/main/home_context.py tests/test_home_context.py
git commit -m "feat(home): add build_home_context dispatcher + _context_out

Public entry point for per-state home data assembly. Logged-out
builder returns registry game lists + WC enrollment count for the
\"{N} competitors in the club\" line."
```

---

## Task 6: _context_pre() with three enrollment scenarios (TDD)

**Files:**
- Modify: `core/main/home_context.py`
- Modify: `tests/test_home_context.py` (append 3 tests + helper)

- [ ] **Step 1: Append a user-creation helper + 3 tests to `tests/test_home_context.py`**

```python
def _make_user(username='alice', email='alice@example.com'):
    """Create + persist a User. Returns the User."""
    from models.user import User
    user = User(username=username, email=email)
    user.set_password('test1234')
    db.session.add(user)
    db.session.commit()
    return user


def _make_enrollment(user, picks_submitted=False, total_score=0.0):
    """Create + persist a WorldCupEnrollment for the current SEASON_YEAR."""
    from games.worldcup.models import WorldCupEnrollment
    from games.worldcup.constants import SEASON_YEAR
    enr = WorldCupEnrollment(
        user_id=user.id,
        season_year=SEASON_YEAR,
        picks_submitted=picks_submitted,
        total_score=total_score,
    )
    db.session.add(enr)
    db.session.commit()
    return enr


def test_context_pre_unenrolled(app):
    """Logged-in but no WC enrollment → is_enrolled=False, no picks."""
    from core.main.home_context import build_home_context
    with app.app_context():
        user = _make_user()
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['WC_FAKE_NOW'] = '2026-05-01T00:00:00Z'
        try:
            ctx = build_home_context(user, 'pre')
            assert ctx['is_enrolled'] is False
            assert ctx['picks'] == []
            assert ctx['display_name'] == 'alice'
            assert 'court_line' in ctx
            assert 'deadline_utc' in ctx
        finally:
            del os.environ['WC_FAKE_NOW']
            os.environ.pop('ENVIRONMENT', None)


def test_context_pre_enrolled_no_picks(app):
    """Enrolled but picks_submitted=False → is_enrolled=True, picks=[]."""
    from core.main.home_context import build_home_context
    with app.app_context():
        user = _make_user()
        _make_enrollment(user, picks_submitted=False)
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['WC_FAKE_NOW'] = '2026-05-01T00:00:00Z'
        try:
            ctx = build_home_context(user, 'pre')
            assert ctx['is_enrolled'] is True
            assert ctx['picks'] == []
        finally:
            del os.environ['WC_FAKE_NOW']
            os.environ.pop('ENVIRONMENT', None)


def test_context_pre_enrolled_sealed(app):
    """Enrolled + picks_submitted=True → picks list populated."""
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupPick
    with app.app_context():
        user = _make_user()
        enr = _make_enrollment(user, picks_submitted=True)
        # Seed one team + one pick (the test only checks structure, not 9 picks)
        team = WorldCupTeam(
            fifa_code='USA', name='United States', display_name='USA',
            tier=1, multiplier=1.0, confederation='CONCACAF', group_letter='A',
        )
        db.session.add(team)
        db.session.commit()
        pick = WorldCupPick(enrollment_id=enr.id, team_id=team.id, tier=1)
        db.session.add(pick)
        db.session.commit()
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['WC_FAKE_NOW'] = '2026-05-01T00:00:00Z'
        try:
            ctx = build_home_context(user, 'pre')
            assert ctx['is_enrolled'] is True
            assert len(ctx['picks']) == 1
            assert ctx['picks'][0].team.fifa_code == 'USA'
        finally:
            del os.environ['WC_FAKE_NOW']
            os.environ.pop('ENVIRONMENT', None)
```

- [ ] **Step 2: Run the 3 new tests — verify they fail with NotImplementedError**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/test_home_context.py -k "context_pre" -v
```

Expected: 3 failures with `NotImplementedError`.

- [ ] **Step 3: Implement `_context_pre()` in `core/main/home_context.py`**

Replace the `_context_pre` stub with:

```python
from datetime import datetime, timezone
from games.worldcup.constants import (
    SEASON_YEAR, TOURNAMENT_DEADLINE_UTC, WORLDCUP_TZ,
)
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupPick, WorldCupTeam, WorldCupMatch,
)


def _context_pre(user, enrollment) -> dict:
    """Pre-deadline state: countdown card, optional ballot, opening matches."""
    is_enrolled = enrollment is not None
    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )

    picks = []
    if is_enrolled and enrollment.picks_submitted:
        picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )

    next_3_matches = (
        WorldCupMatch.query
        .filter(WorldCupMatch.kickoff_utc.isnot(None))
        .order_by(WorldCupMatch.kickoff_utc.asc())
        .limit(3)
        .all()
    )

    deadline_ct = TOURNAMENT_DEADLINE_UTC.astimezone(WORLDCUP_TZ)

    # court_line: "Thursday ◆ Tribute window open ◆ 2 days to kickoff"
    now_local = datetime.now(WORLDCUP_TZ)
    weekday = now_local.strftime('%A')
    delta = TOURNAMENT_DEADLINE_UTC - datetime.now(timezone.utc)
    days = delta.days
    hours = delta.seconds // 3600
    if days > 1:
        proximity = f'{days} days to kickoff'
    elif days == 1:
        proximity = '1 day to kickoff'
    elif hours > 1:
        proximity = f'{hours} hours to kickoff'
    elif delta.total_seconds() > 0:
        minutes = (delta.seconds // 60) % 60
        proximity = f'{minutes} minutes to kickoff'
    else:
        proximity = 'kickoff imminent'
    court_line = f'{weekday} ◆ Tribute window open ◆ {proximity}'

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'picks': picks,
        'display_name': display_name,
        'deadline_utc': TOURNAMENT_DEADLINE_UTC,
        'deadline_ct': deadline_ct,
        'total_enrolled': WorldCupEnrollment.query.filter_by(
            season_year=SEASON_YEAR
        ).count(),
        'next_3_matches': next_3_matches,
        'court_line': court_line,
        'joined_games': joined_games(user),
        'coming_soon_games': coming_soon_games(),
    }
```

- [ ] **Step 4: Run the tests — verify they pass**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/test_home_context.py -k "context_pre" -v
```

Expected: 3 passed.

- [ ] **Step 5: Run pyright**

```bash
venv/bin/pyright core/main/home_context.py
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add core/main/home_context.py tests/test_home_context.py
git commit -m "feat(home): _context_pre with countdown + ballot + opening matches

Builds the pre-deadline render context: deadline timestamps, dynamic
court line copy, sealed-roster picks (if any), next 3 matches by
kickoff order, and registry game lists for the compact tile strip."
```

---

## Task 7: _context_live() with dossier + tagline helper (TDD)

**Files:**
- Modify: `core/main/home_context.py`
- Modify: `tests/test_home_context.py` (append 2 tests)

- [ ] **Step 1: Append the 2 live-state tests to `tests/test_home_context.py`**

```python
def test_context_live_unenrolled(app):
    """Live state, no enrollment → is_enrolled=False, dossier dict missing."""
    from core.main.home_context import build_home_context
    with app.app_context():
        user = _make_user()
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['WC_FAKE_NOW'] = '2026-06-15T00:00:00Z'
        try:
            ctx = build_home_context(user, 'live')
            assert ctx['is_enrolled'] is False
            assert ctx['dossier'] is None
            assert ctx['top_3_plus_you'] == []  # no enrollments seeded
        finally:
            del os.environ['WC_FAKE_NOW']
            os.environ.pop('ENVIRONMENT', None)


def test_context_live_enrolled_basic(app):
    """Live state, enrolled → dossier populated with rank/points/alive."""
    from core.main.home_context import build_home_context
    with app.app_context():
        user = _make_user()
        _make_enrollment(user, picks_submitted=True, total_score=100.0)
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['WC_FAKE_NOW'] = '2026-06-15T00:00:00Z'
        try:
            ctx = build_home_context(user, 'live')
            assert ctx['is_enrolled'] is True
            assert ctx['dossier']['rank'] == 1  # only 1 enrollment
            assert ctx['dossier']['total_score'] == 100.0
            assert ctx['dossier']['alive_count'] == 0  # no picks seeded
            assert ctx['dossier']['week_delta_rank'] is None  # no snapshots
        finally:
            del os.environ['WC_FAKE_NOW']
            os.environ.pop('ENVIRONMENT', None)
```

- [ ] **Step 2: Run the new tests — verify they fail with NotImplementedError**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/test_home_context.py -k "context_live" -v
```

Expected: 2 failures with `NotImplementedError`.

- [ ] **Step 3: Implement `_context_live()` and the tagline helper in `core/main/home_context.py`**

Replace the `_context_live` stub. Also add the imports at the top if not present:

```python
from games.worldcup.models import WorldCupRankSnapshot
```

Then replace `def _context_live(user, enrollment): raise NotImplementedError` with:

```python
def _tagline_for(rank: int, week_delta_rank: Optional[int],
                 alive_count: int, is_you: bool = False) -> Optional[str]:
    """Return a contextual one-liner for a leaderboard row, or None.

    Finite string set per Spec B D11 — server-derived from data, not LLM-style
    free-form text.
    """
    if is_you and week_delta_rank is not None:
        if week_delta_rank <= -10:
            return f"Climbed {abs(week_delta_rank)} · the Commish takes notes."
        if week_delta_rank < 0:
            return f"Climbing {abs(week_delta_rank)} spots quietly."
        if week_delta_rank == 0:
            return "Holding steady."
        if week_delta_rank < 10:
            return f"Slipped {week_delta_rank} spots. The Commish notices."
        return f"Down {week_delta_rank} · the Commish averts his eyes."
    if rank == 1:
        return "Paid tribute. Paid off."
    if rank in (2, 3) and alive_count == 9:
        return "Still warm. Still winning."
    if rank in (2, 3):
        return "Played the favorites."
    return None


def _context_live(user, enrollment) -> dict:
    """Live-tournament state: dossier, leaderboard preview, recent results."""
    is_enrolled = enrollment is not None

    # Leaderboard query — used for both rank and top-3
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(WorldCupEnrollment.total_score.desc())
        .all()
    )
    total_count = len(all_enrollments)

    dossier = None
    if is_enrolled:
        # Find user's rank (1-indexed)
        user_rank = next(
            (i + 1 for i, e in enumerate(all_enrollments) if e.id == enrollment.id),
            None,
        )

        # Alive count
        picks_with_teams = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .all()
        )
        alive_count = sum(1 for p in picks_with_teams if not p.team.is_eliminated)

        # Week-delta from snapshot history
        week_delta_rank = None
        week_delta_points = None
        sparkline_data = []
        recent_snapshots = (
            WorldCupRankSnapshot.query
            .filter_by(enrollment_id=enrollment.id)
            .order_by(WorldCupRankSnapshot.captured_at.asc())
            .limit(7)
            .all()
        )
        if recent_snapshots:
            sparkline_data = [s.rank for s in recent_snapshots]
            if len(recent_snapshots) >= 2:
                oldest = recent_snapshots[0]
                week_delta_rank = (user_rank or 0) - oldest.rank
                week_delta_points = float(enrollment.total_score) - float(oldest.total_score)

        dossier = {
            'rank': user_rank,
            'total_count': total_count,
            'total_score': enrollment.total_score,
            'alive_count': alive_count,
            'week_delta_rank': week_delta_rank,
            'week_delta_points': week_delta_points,
            'sparkline_data': sparkline_data,
        }

    # Top 3 + you row (if user is enrolled and outside top 3)
    top_3 = all_enrollments[:3]
    top_3_plus_you = []
    for i, enr in enumerate(top_3, start=1):
        top_3_plus_you.append({
            'rank': i,
            'enrollment': enr,
            'is_you': is_enrolled and enr.id == enrollment.id,
            'tagline': _tagline_for(i, None, 0, is_you=False),
        })
    if is_enrolled and dossier and dossier['rank'] and dossier['rank'] > 3:
        top_3_plus_you.append({
            'rank': dossier['rank'],
            'enrollment': enrollment,
            'is_you': True,
            'tagline': _tagline_for(
                dossier['rank'], dossier['week_delta_rank'],
                dossier['alive_count'], is_you=True,
            ),
            'separator_above': True,
        })

    # Recent results — last 5 completed matches
    recent_results = (
        WorldCupMatch.query
        .filter_by(is_completed=True)
        .order_by(WorldCupMatch.match_number.desc())
        .limit(5)
        .all()
    )

    # Roster intersection — for foot-row rendering
    user_team_ids = set()
    if is_enrolled:
        user_team_ids = {p.team_id for p in WorldCupPick.query.filter_by(
            enrollment_id=enrollment.id
        ).all()}

    your_pick_results = []
    for match in recent_results:
        roster_match = None
        if match.home_team_id in user_team_ids:
            roster_match = {'team_id': match.home_team_id, 'side': 'home'}
        elif match.away_team_id in user_team_ids:
            roster_match = {'team_id': match.away_team_id, 'side': 'away'}
        your_pick_results.append({'match': match, 'roster_match': roster_match})

    # Court line + stage label
    most_recent = recent_results[0] if recent_results else None
    stage_label = _stage_label(most_recent.stage if most_recent else 'group')
    weekday = datetime.now(WORLDCUP_TZ).strftime('%A')
    if dossier and dossier['week_delta_rank'] is not None:
        if dossier['week_delta_rank'] < 0:
            trend = "you're climbing"
        elif dossier['week_delta_rank'] == 0:
            trend = "you're holding"
        else:
            trend = "you're slipping"
    else:
        trend = "the Council is in session"
    court_line = f'{weekday} ◆ {stage_label} ◆ {trend}'

    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'dossier': dossier,
        'top_3_plus_you': top_3_plus_you,
        'your_pick_results': your_pick_results,
        'court_line': court_line,
        'stage_label': stage_label,
        'display_name': display_name,
        'joined_games': joined_games(user),
        'coming_soon_games': coming_soon_games(),
    }


def _stage_label(stage: str) -> str:
    """Map WorldCupMatch.stage to a display label."""
    return {
        'group': 'Group Stage',
        'r32': 'Round of 32',
        'r16': 'Round of 16',
        'qf': 'Quarterfinals',
        'sf': 'Semifinals',
        'final': 'The Final',
    }.get(stage, 'Group Stage')
```

Also add `Optional` to the imports:

```python
from typing import Optional, Any
```

- [ ] **Step 4: Run the tests — verify they pass**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/test_home_context.py -k "context_live" -v
```

Expected: 2 passed.

- [ ] **Step 5: Run pyright**

```bash
venv/bin/pyright core/main/home_context.py games/worldcup/services/state.py
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add core/main/home_context.py tests/test_home_context.py
git commit -m "feat(home): _context_live with dossier + tagline helper

Live state assembles rank/sparkline/alive/week-delta dossier, top-3 +
you leaderboard preview with finite-string contextual taglines per
D11, and recent-results with roster intersection."
```

---

## Task 8: _context_post() (TDD)

**Files:**
- Modify: `core/main/home_context.py`
- Modify: `tests/test_home_context.py` (append 1 test)

- [ ] **Step 1: Append the post-state test**

```python
def test_context_post_with_champion(app):
    """Post state with match #104 completed → champion_team populated."""
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupMatch
    with app.app_context():
        # Seed the champion + final match
        bra = WorldCupTeam(
            fifa_code='BRA', name='Brazil', display_name='Brazil',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='C',
        )
        arg = WorldCupTeam(
            fifa_code='ARG', name='Argentina', display_name='Argentina',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='B',
        )
        db.session.add_all([bra, arg])
        db.session.commit()
        final = WorldCupMatch(
            match_number=104, stage='final',
            home_team_id=bra.id, away_team_id=arg.id,
            home_score=3, away_score=2, extra_time=True,
            winner_team_id=bra.id, is_completed=True,
        )
        db.session.add(final)
        db.session.commit()

        user = _make_user()
        ctx = build_home_context(user, 'post')
        assert ctx['champion_team'].fifa_code == 'BRA'
        assert 'Argentina' in ctx['champion_summary']
        assert '3' in ctx['champion_summary']
        assert ctx['is_enrolled'] is False
```

- [ ] **Step 2: Run — verify it fails**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/test_home_context.py::test_context_post_with_champion -v
```

Expected: failure with `NotImplementedError`.

- [ ] **Step 3: Implement `_context_post()` in `core/main/home_context.py`**

Replace the `_context_post` stub:

```python
def _context_post(user, enrollment) -> dict:
    """Post-tournament state: champion banner + podium + roster recap."""
    is_enrolled = enrollment is not None

    # Champion data — match #104
    final_match = WorldCupMatch.query.filter_by(match_number=104).first()
    champion_team = None
    champion_summary = ''
    if final_match and final_match.winner_team_id:
        champion_team = final_match.winner_team
        loser = (
            final_match.home_team if final_match.away_team_id == final_match.winner_team_id
            else final_match.away_team
        )
        winner_score = max(final_match.home_score or 0, final_match.away_score or 0)
        loser_score = min(final_match.home_score or 0, final_match.away_score or 0)
        suffix = ''
        if final_match.penalties:
            suffix = ' on penalties'
        elif final_match.extra_time:
            suffix = ' in extra time'
        if loser:
            champion_summary = (
                f'Defeated {loser.display_name} {winner_score}–{loser_score}{suffix}'
            )

    # Final podium — top 3
    all_enrollments = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(WorldCupEnrollment.total_score.desc())
        .all()
    )
    top_3_final = all_enrollments[:3]
    total_count = len(all_enrollments)

    your_final_rank = None
    your_climbed_n = None
    your_roster_recap = []
    if is_enrolled:
        your_final_rank = next(
            (i + 1 for i, e in enumerate(all_enrollments) if e.id == enrollment.id),
            None,
        )
        # Climbed N spots — first snapshot vs latest
        snapshots = (
            WorldCupRankSnapshot.query
            .filter_by(enrollment_id=enrollment.id)
            .order_by(WorldCupRankSnapshot.captured_at.asc())
            .all()
        )
        if snapshots and your_final_rank:
            first = snapshots[0]
            your_climbed_n = first.rank - your_final_rank  # positive = climbed

        # Roster recap — every pick with points + best_finish
        from games.worldcup.world_cup_countries import TIERS
        picks = (
            WorldCupPick.query
            .filter_by(enrollment_id=enrollment.id)
            .join(WorldCupTeam)
            .order_by(WorldCupTeam.tier, WorldCupTeam.display_name)
            .all()
        )
        for pick in picks:
            your_roster_recap.append({
                'pick': pick,
                'tier_name': TIERS[pick.tier]['name'],
                'best_finish': pick.team.best_finish or 'Group',
                'points': pick.multiplied_points,
                'is_champion': champion_team and pick.team_id == champion_team.id,
            })

    display_name = (
        enrollment.get_display_name() if is_enrolled
        else user.get_display_name()
    )

    return {
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'champion_team': champion_team,
        'champion_summary': champion_summary,
        'final_match': final_match,
        'top_3_final': top_3_final,
        'total_count': total_count,
        'your_final_rank': your_final_rank,
        'your_climbed_n': your_climbed_n,
        'your_roster_recap': your_roster_recap,
        'display_name': display_name,
        'joined_games': joined_games(user),
        'coming_soon_games': coming_soon_games(),
    }
```

- [ ] **Step 4: Run the test — verify it passes**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/test_home_context.py -v
```

Expected: all tests pass (3 state + 1 out + 3 pre + 2 live + 1 post = 10 passed).

- [ ] **Step 5: Run pyright + commit**

```bash
venv/bin/pyright core/main/home_context.py
```

Expected: 0 errors.

```bash
git add core/main/home_context.py tests/test_home_context.py
git commit -m "feat(home): _context_post with champion + podium + roster recap

Post-tournament state assembles champion data from match #104,
podium top-3, your-final-rank from leaderboard, and per-pick recap
with tier name + best finish + points + champion-row flag."
```

---

## Task 9: Route rewrite + index.html dispatcher shell + state stubs

**Files:**
- Modify: `core/main/routes.py`
- Modify: `core/main/templates/main/index.html` (rewrite)
- Create: `core/main/templates/main/_home_out.html` (stub)
- Create: `core/main/templates/main/_home_pre.html` (stub)
- Create: `core/main/templates/main/_home_live.html` (stub)
- Create: `core/main/templates/main/_home_post.html` (stub)

- [ ] **Step 1: Rewrite `core/main/routes.py`**

Replace the entire file contents with:

```python
"""
Fantasy Sports Platform — Main Routes
=======================================
Home page and platform-level pages. State-aware per Spec B.
"""
from flask import render_template
from flask_login import current_user

from core.main import main_bp
from core.main.home_context import build_home_context
from games.worldcup.services.state import worldcup_state


@main_bp.route('/')
def index():
    """Platform home page. Dispatches to one of four state partials.

    State-detection logic + per-state data assembly per Spec B sections 4a–4d.
    """
    if not current_user.is_authenticated:
        ctx = build_home_context(None, None)
        return render_template('main/index.html', state='out', **ctx)
    state = worldcup_state()
    ctx = build_home_context(current_user, state)
    return render_template('main/index.html', state=state, **ctx)
```

- [ ] **Step 2: Rewrite `core/main/templates/main/index.html` as the dispatcher shell**

```jinja
{% extends "base.html" %}

{% block title %}Corrupt Commish Club{% endblock %}

{% block content %}
<div class="home-shell home-shell--{{ state }}">
{% if state == 'out' %}
  {% include 'main/_home_out.html' %}
{% elif state == 'pre' %}
  {% include 'main/_home_pre.html' %}
{% elif state == 'live' %}
  {% include 'main/_home_live.html' %}
{% elif state == 'post' %}
  {% include 'main/_home_post.html' %}
{% endif %}
</div>
{% endblock %}
```

- [ ] **Step 3: Create stub partials so the route doesn't 500**

Create `core/main/templates/main/_home_out.html`:

```jinja
<div class="container my-5 text-center">
  <h1>HOME OUT — stub</h1>
  <p>State: out</p>
  <p>Total enrolled: {{ total_enrolled }}</p>
</div>
```

Create `core/main/templates/main/_home_pre.html`:

```jinja
<div class="container my-5 text-center">
  <h1>HOME PRE — stub</h1>
  <p>Display name: {{ display_name }}</p>
  <p>Court line: {{ court_line }}</p>
  <p>Enrolled: {{ is_enrolled }}</p>
  <p>Picks: {{ picks|length }}</p>
</div>
```

Create `core/main/templates/main/_home_live.html`:

```jinja
<div class="container my-5 text-center">
  <h1>HOME LIVE — stub</h1>
  <p>Display name: {{ display_name }}</p>
  <p>Court line: {{ court_line }}</p>
  <p>Enrolled: {{ is_enrolled }}</p>
  {% if dossier %}
    <p>Rank: {{ dossier.rank }} of {{ dossier.total_count }}</p>
    <p>Score: {{ dossier.total_score }} · Alive: {{ dossier.alive_count }}</p>
  {% endif %}
</div>
```

Create `core/main/templates/main/_home_post.html`:

```jinja
<div class="container my-5 text-center">
  <h1>HOME POST — stub</h1>
  <p>Champion: {{ champion_team.display_name if champion_team else 'Pending' }}</p>
  <p>{{ champion_summary }}</p>
  <p>Your final rank: {{ your_final_rank or '—' }}</p>
</div>
```

- [ ] **Step 4: Boot the dev server and verify pre state renders (default)**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5001
```

In a browser, visit `http://127.0.0.1:5001/`. Without auth, expect "HOME OUT — stub" with "Total enrolled: 0".

- [ ] **Step 5: Verify pre state renders for a logged-in user**

In the running dev session, register a user via `/register` (or use existing). After login, the home should now show "HOME PRE — stub" with the user's display name and "Picks: 0". (Default `WC_FAKE_NOW` is unset → real time → still pre-deadline since today is before June 11 2026.)

- [ ] **Step 6: Verify live state renders with WC_FAKE_NOW**

Stop the server (Ctrl+C). Restart with the env override:

```bash
WC_FAKE_NOW=2026-06-15T00:00:00Z ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5001
```

Logged-in, refresh `/`. Expect "HOME LIVE — stub".

- [ ] **Step 7: Verify post state renders by mocking match #104**

In a separate terminal:

```bash
cd ../fantasy-platform-ccc-home
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask shell <<'EOF'
from games.worldcup.models import WorldCupMatch
from extensions import db
m = WorldCupMatch.query.filter_by(match_number=104).first()
if m:
    m.is_completed = True
    db.session.commit()
    print('Marked #104 complete')
else:
    print('No match 104 — seed first via flask worldcup init')
EOF
```

If you haven't seeded matches yet (`flask worldcup init`), do so first, then re-run the snippet. Refresh `/` in the browser. Expect "HOME POST — stub".

Reset for further work:

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask shell <<'EOF'
from games.worldcup.models import WorldCupMatch
from extensions import db
m = WorldCupMatch.query.filter_by(match_number=104).first()
m.is_completed = False
db.session.commit()
EOF
```

- [ ] **Step 8: Run the full test suite — verify nothing broke**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/ -q
```

Expected: 119 prior tests + 10 new = 129 passed.

- [ ] **Step 9: Commit**

```bash
git add core/main/routes.py core/main/templates/main/
git commit -m "feat(home): state-aware route + dispatcher shell + state stubs

Route dispatches on worldcup_state(); index.html includes one of four
state partials. Stub partials render placeholder content so the four
states are individually verifiable in dev before real templates land."
```

---

## Task 10: Registry GameStatus 'completed' literal

**Files:**
- Modify: `games/registry.py:15`

- [ ] **Step 1: Add `'completed'` to the `GameStatus` Literal**

Open `games/registry.py`. The current line is:

```python
GameStatus = Literal['coming_soon', 'open', 'closed', 'completed']
```

It already includes `'completed'` per the existing code — confirm by grep:

```bash
grep -n "GameStatus" games/registry.py
```

If `'completed'` is already present, **skip this task and proceed to Task 11**. The spec mentioned this as a single-line add but the codebase already has it.

If absent, edit line 15 to add `'completed'` to the Literal members.

- [ ] **Step 2: If you made an edit, commit**

```bash
git add games/registry.py
git commit -m "chore(registry): confirm 'completed' GameStatus is available

Used by the compact game tiles strip to render the WC tile's
'COMPLETED' label in the post-tournament home state."
```

---

## Task 11: tokens.css additions + style.css HOME section bootstrap

**Files:**
- Modify: `static/css/tokens.css` (append at bottom)
- Modify: `static/css/style.css` (insert new section after admin-eyebrow)

- [ ] **Step 1: Append three Spec B tokens to `static/css/tokens.css`**

Open the file. Just before the closing `}` of `:root`, add:

```css
  /* === Spec B additions (CCC home redesign) === */
  --live-orange:        #FF8A3C;
  --podium-glow:        radial-gradient(circle, rgba(242,211,107,.5) 0%, transparent 70%);
  --champion-glow:      radial-gradient(circle, rgba(242,211,107,.4) 0%, transparent 60%);
```

- [ ] **Step 2: Locate the insertion point in `static/css/style.css`**

```bash
grep -n "/\* === GOLF PICK 'EM" static/css/style.css
```

Expected: line 269. The HOME section goes immediately before this line (after the `/* === CCC ADMIN EYEBROW === */` block).

- [ ] **Step 3: Insert the HOME section header + base wrapper rules**

Insert immediately before the GOLF section header:

```css
/* === HOME (CCC) ============================================== */
/* Components used by core/main/templates/main/_home_*.html      */
/* Ported from fantasy-platform-and-world-cup-design/project/    */
/*   styles/app.css, scoped under .home-shell to avoid           */
/*   collisions with platform components.                        */

.home-shell {
  position: relative;
  min-height: calc(100vh - 56px - 200px); /* nav minus footer */
  background: var(--purple-950);
  background-image: radial-gradient(
    ellipse at top,
    var(--purple-900) 0%,
    var(--purple-950) 60%
  );
  color: var(--bone);
  font-family: var(--font-news);
  padding: 2rem 1rem 3rem;
}

.home-shell--out {
  /* Logged-out hero gets a slightly stronger vignette */
  background-image: radial-gradient(
    ellipse at center top,
    var(--purple-800) 0%,
    var(--purple-950) 70%
  );
}

.home-shell--post {
  /* Champion banner backdrop is gentler than live */
  background-image: radial-gradient(
    ellipse at top,
    var(--purple-850) 0%,
    var(--purple-950) 65%
  );
}

@media (min-width: 768px) {
  .home-shell {
    padding: 3rem 1rem 4rem;
  }
}

/* Home content max-width for non-live states (mobile-first single column) */
.home-shell .home-col {
  max-width: 640px;
  margin: 0 auto;
}

/* Section heads — shared across all home states */
.home-shell .sec-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 1.5rem 0 0.75rem;
}
.home-shell .sec-head .t {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 1.25rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--bone);
}
.home-shell .sec-head .more {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.85rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--gold-light);
  text-decoration: none;
}
.home-shell .sec-head .more:hover {
  color: var(--gold-hi);
}

/* Metal-text helper (renamed from design's .metal-text per Spec B 9c) */
.home-metal-text {
  background: var(--metal-gold);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

/* === HOME — END ============================================== */

```

- [ ] **Step 4: Verify CSS validity by booting the dev server**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5001
```

In a browser, visit `http://127.0.0.1:5001/` (any state). The `.home-shell` background should be deep purple with a vignette. The stub text should still be visible (centered, light-colored).

- [ ] **Step 5: Commit**

```bash
git add static/css/tokens.css static/css/style.css
git commit -m "feat(home): add tokens + HOME section scaffold to style.css

3 Spec B tokens at bottom of tokens.css; new HOME section in
style.css after admin-eyebrow with .home-shell wrapper, per-state
background variants, sec-head shared component, and home-metal-text
helper."
```

---

## Task 12: Logged-out state — _home_out.html + CSS

**Files:**
- Modify: `core/main/templates/main/_home_out.html` (replace stub)
- Modify: `static/css/style.css` (append within HOME section)

- [ ] **Step 1: Replace stub `_home_out.html` with the real markup**

Per Spec B section 5a layout. Replace the entire file contents:

```jinja
{# Logged-out home — Spec B section 5 #}
<div class="home-col">

  {# Hero #}
  <div class="out-hero">
    <div class="out-eyebrow">◈ Fantasy for crooked kings &amp; queens ◈</div>
    <h1 class="out-title">
      <span class="out-title-a">The Fix</span>
      <span class="out-title-b">Is In.</span>
    </h1>
    <p class="out-sub">
      A fantasy pool for fiefdoms, not spreadsheets. Pay tribute.
      Bend the odds to your will. No honor required.
    </p>
  </div>

  {# Value props #}
  <div class="out-props">
    <div class="out-prop">
      <div class="out-prop-icon">
        <i class="bi bi-trophy-fill"></i>
      </div>
      <div class="out-prop-text">
        <div class="t">Rule the fiefdom</div>
        <div class="s">Pick a Favorite, a Dark Horse, a Sacred Underdog. Every choice pays.</div>
      </div>
    </div>
    <div class="out-prop">
      <div class="out-prop-icon">
        <i class="bi bi-graph-up-arrow"></i>
      </div>
      <div class="out-prop-text">
        <div class="t">Climb the leaderboard</div>
        <div class="s">Live rank. Weekly dispatches when rivals fall.</div>
      </div>
    </div>
    <div class="out-prop">
      <div class="out-prop-icon">
        <i class="bi bi-journal-text"></i>
      </div>
      <div class="out-prop-text">
        <div class="t">Read the Commish&rsquo;s Note</div>
        <div class="s">Weekly recaps in plain language. No shame. Just receipts.</div>
      </div>
    </div>
  </div>

  {# Join CTA #}
  <div class="join">
    <div class="join-head">
      <div class="seal">◈ Open Court &middot; 2026 WC</div>
      {% if total_enrolled > 0 %}
      <div class="count">
        <span class="v">{{ total_enrolled }}</span> competitors in the club
      </div>
      {% endif %}
    </div>
    <div class="join-title">Join the <span class="home-metal-text">competition</span>.</div>
    <p class="join-sub">
      Pre-kickoff: anyone can join the game. Once group stage locks on June 11,
      you can still join the club &mdash; but your ballot closes with the rest.
    </p>
    <a class="join-cta" href="{{ url_for('auth.register') }}">
      Join the Club
      <i class="bi bi-arrow-right"></i>
    </a>
    <div class="join-alt">
      Already sworn in? <a href="{{ url_for('auth.login') }}">Sign in</a>
    </div>
  </div>

</div>{# /.home-col #}

{# Full game cards — registry-driven, breaks out of .home-col for full-width grid #}
<div class="container my-5">
  <div class="row g-4 justify-content-center">
    {% for game in available_games %}
    <div class="col-sm-6 col-md-4">
      {% with state='logged_out' %}{% include 'main/_game_card.html' %}{% endwith %}
    </div>
    {% endfor %}
    {% for game in coming_soon_games %}
    <div class="col-sm-6 col-md-4">
      {% with state='coming_soon' %}{% include 'main/_game_card.html' %}{% endwith %}
    </div>
    {% endfor %}
  </div>
</div>
```

- [ ] **Step 2: Append the out-hero / out-props / join CSS within the HOME section**

In `static/css/style.css`, locate the line `/* === HOME — END ============================================== */`. Insert the following block immediately BEFORE that closing comment:

```css
/* --- Logged-out: hero --- */
.home-shell .out-hero {
  text-align: center;
  padding: 2rem 0 2.5rem;
}
.home-shell .out-eyebrow {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.75rem;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--gold-light);
  margin-bottom: 1.5rem;
}
.home-shell .out-title {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 2.4rem;
  line-height: 0.95;
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.home-shell .out-title .out-title-a {
  display: block;
  background: var(--metal-gold);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.home-shell .out-title .out-title-b {
  display: block;
  color: var(--bone);
  margin-top: 0.2rem;
}
@media (min-width: 768px) {
  .home-shell .out-title { font-size: 3.5rem; }
}
.home-shell .out-sub {
  font-family: var(--font-news);
  font-size: 1.05rem;
  line-height: 1.5;
  color: var(--bone-mute);
  margin: 1.5rem auto 0;
  max-width: 480px;
}

/* --- Logged-out: value props --- */
.home-shell .out-props {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 1.5rem 0;
  border-top: 1px solid rgba(243,239,230,.08);
  border-bottom: 1px solid rgba(243,239,230,.08);
}
.home-shell .out-prop {
  display: flex;
  gap: 1rem;
  padding: 1.25rem 0.5rem;
  border-bottom: 1px solid rgba(243,239,230,.05);
}
.home-shell .out-prop:last-child { border-bottom: none; }
.home-shell .out-prop-icon {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--gold-light);
  font-size: 1.1rem;
}
.home-shell .out-prop-text .t {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 1.05rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--bone);
}
.home-shell .out-prop-text .s {
  font-family: var(--font-news);
  font-size: 0.9rem;
  color: var(--bone-mute);
  margin-top: 0.25rem;
  line-height: 1.4;
}

/* --- Logged-out: Join CTA card --- */
.home-shell .join {
  margin-top: 2rem;
  padding: 1.75rem 1.5rem 2rem;
  background: linear-gradient(180deg,
    var(--purple-800) 0%,
    var(--purple-900) 100%);
  border: 1px solid rgba(201,162,39,.3);
  border-radius: 14px;
  text-align: center;
}
.home-shell .join-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.home-shell .join-head .seal {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--gold-light);
}
.home-shell .join-head .count {
  font-family: var(--font-news);
  font-size: 0.85rem;
  color: var(--bone-mute);
  font-style: italic;
}
.home-shell .join-head .count .v {
  color: var(--bone);
  font-style: normal;
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 1rem;
}
.home-shell .join-title {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 2rem;
  line-height: 1;
  text-transform: uppercase;
  color: var(--bone);
  margin: 0.5rem 0 1rem;
}
.home-shell .join-sub {
  font-family: var(--font-news);
  font-size: 0.95rem;
  color: var(--bone-mute);
  line-height: 1.5;
  max-width: 380px;
  margin: 0 auto 1.5rem;
}
.home-shell .join-cta {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.85rem 2rem;
  background: var(--metal-gold);
  color: var(--purple-950) !important;
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 1rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  text-decoration: none;
  border-radius: 8px;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.home-shell .join-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(201,162,39,.25);
  color: var(--purple-950) !important;
}
.home-shell .join-alt {
  margin-top: 1rem;
  font-family: var(--font-news);
  font-size: 0.9rem;
  color: var(--bone-mute);
}
.home-shell .join-alt a {
  color: var(--gold-light);
  text-decoration: underline;
}
.home-shell .join-alt a:hover { color: var(--gold-hi); }
```

- [ ] **Step 3: Visually verify the logged-out home in browser**

Boot the dev server (logged out):

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask run --port 5001
```

Visit `http://127.0.0.1:5001/` in incognito (or after `/logout`). Verify:
- "The Fix" / "Is In." hero with metal-gold gradient on "The Fix"
- Three value props (last says "Read the Commish's Note")
- Join CTA card with gold border, "Join the Club" gold-gradient button
- Three game cards below (WC live, CFB coming soon, Golf coming soon)
- No social-proof block
- Footer voice strip visible at bottom

If `total_enrolled == 0` (clean dev DB), the "{N} competitors" line is correctly suppressed.

- [ ] **Step 4: Commit**

```bash
git add core/main/templates/main/_home_out.html static/css/style.css
git commit -m "feat(home): logged-out marketing surface

Hero (\"The Fix Is In.\"), three value props, Join CTA card with
\"Join the Club\" button, registry-driven full game cards. No
social-proof block per D3-c."
```

---

## Task 13: Pre-state shell + greet block

**Files:**
- Modify: `core/main/templates/main/_home_pre.html` (replace stub)
- Modify: `static/css/style.css` (append `.greet` rules)

- [ ] **Step 1: Replace `_home_pre.html` with the full shell**

```jinja
{# Pre-deadline home — Spec B section 6 #}
<div class="home-col">

  {# Greet block #}
  <div class="greet">
    <p class="greet-line">
      Welcome back to the fiefdom &mdash;
      <span class="v">{{ display_name }}</span>
    </p>
    <h1 class="greet-title">
      The Council
      <span class="home-metal-text">Awaits</span>
    </h1>
    <div class="greet-court">{{ court_line }}</div>
  </div>

  {# Countdown #}
  {% include 'main/_countdown_card.html' %}

  {# Dossier slot — three variants #}
  {% if not is_enrolled %}
    {% include 'main/_join_cta_card.html' %}
  {% elif not enrollment.picks_submitted %}
    {% include 'main/_submit_picks_cta.html' %}
  {% else %}
    {% include 'main/_ballot_card.html' %}
  {% endif %}

  {# Opening matches #}
  {% if next_3_matches %}
  <div class="sec-head">
    <div class="t">Opening Matches</div>
    <a class="more" href="{{ url_for('worldcup.schedule') }}">Schedule &rsaquo;</a>
  </div>
  {% for match in next_3_matches %}
    {% include 'main/_fixture_card.html' %}
  {% endfor %}
  {% endif %}

  {# Compact game tiles #}
  {% include 'main/_game_tiles_compact.html' %}

  {# Optional narrative partials — silently absent if empty #}
  {% include 'main/_commish_note.html' ignore missing %}
  {% include 'main/_dispatches.html' ignore missing %}

</div>{# /.home-col #}
```

- [ ] **Step 2: Append `.greet` CSS within the HOME section**

In `static/css/style.css`, immediately before the `/* === HOME — END */` marker, append:

```css
/* --- Greet (used by pre/live/post) --- */
.home-shell .greet {
  text-align: center;
  padding: 1rem 0 1.5rem;
}
.home-shell .greet-line {
  font-family: var(--font-news);
  font-style: italic;
  font-size: 0.95rem;
  color: var(--bone-mute);
  margin: 0 0 0.75rem;
}
.home-shell .greet-line .v {
  color: var(--gold-light);
  font-style: normal;
  font-family: var(--font-teko);
  font-weight: 600;
  letter-spacing: 0.04em;
  margin-left: 0.4rem;
}
.home-shell .greet-title {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 2.4rem;
  line-height: 0.95;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  color: var(--bone);
  margin: 0;
}
@media (min-width: 768px) {
  .home-shell .greet-title { font-size: 3.2rem; }
}
.home-shell .greet-court {
  font-family: var(--font-news);
  font-style: italic;
  font-size: 0.9rem;
  color: var(--bone-mute);
  margin-top: 0.75rem;
}
.home-shell .greet-court .sep {
  color: rgba(242,211,107,.5);
  margin: 0 0.4rem;
}
```

- [ ] **Step 3: Visually verify (greet renders, countdown/ballot/etc are placeholder includes)**

The page will 500 right now because `_countdown_card.html` etc. don't exist yet. Verify *only the greet block* by temporarily commenting out the includes:

In `_home_pre.html`, wrap each include in `{# #}` comments. Refresh. Verify the greet block renders (display name, "The Council Awaits" title, court line). Then uncomment so the next tasks can fill in the partials.

(Better alternative: skip step 3 and verify after Task 17.)

- [ ] **Step 4: Commit (greet rules only — partials come next)**

```bash
git add core/main/templates/main/_home_pre.html static/css/style.css
git commit -m "feat(home): pre-state shell + greet block

Full pre-state markup with includes for countdown, ballot variants,
opening matches, compact game tiles, and narrative partials. Greet
CSS added (shared with live and post)."
```

---

## Task 14: Pre-state countdown card + countdown.js

**Files:**
- Create: `core/main/templates/main/_countdown_card.html`
- Create: `static/js/countdown.js`
- Modify: `static/css/style.css` (append `.decree` rules)
- Modify: `core/main/templates/main/_home_pre.html` (add scripts block)

- [ ] **Step 1: Create `_countdown_card.html`**

```jinja
{# Pre-deadline countdown card — Spec B section 6 + D8 #}
<div class="decree" data-deadline-utc="{{ deadline_utc.strftime('%Y-%m-%dT%H:%M:%SZ') }}">
  <div class="decree-seal">
    <div class="s">By Decree of the Commish <span class="num">No 001</span></div>
    <div class="s decree-seal-year">2026 WC</div>
  </div>

  <div class="decree-body">
    <h2>Tribute Due In</h2>
    <div class="decree-days">
      <div class="d-cell">
        <div class="v" data-cd-days>{{ '%02d'|format(((deadline_utc - now_utc).days)|default(0)) }}</div>
        <div class="u">Days</div>
      </div>
      <div class="d-sep">:</div>
      <div class="d-cell">
        <div class="v" data-cd-hours>00</div>
        <div class="u">Hours</div>
      </div>
      <div class="d-sep">:</div>
      <div class="d-cell">
        <div class="v" data-cd-mins>00</div>
        <div class="u">Min</div>
      </div>
      <div class="d-sep">:</div>
      <div class="d-cell">
        <div class="v" data-cd-secs>00</div>
        <div class="u">Sec</div>
      </div>
    </div>
    <p class="decree-foot">Once group stage begins, all picks lock.</p>
  </div>

  <div class="decree-actions">
    <a class="decree-cta" href="{{ url_for('worldcup.picks') }}">
      <i class="bi bi-pencil-square"></i>
      Review &amp; Edit My Roster
    </a>
    <div class="decree-links">
      <a href="{{ url_for('worldcup.rules') }}">
        <i class="bi bi-journal"></i> House Rules
      </a>
      <a href="{{ url_for('worldcup.rules') }}#scoring">
        <i class="bi bi-check-circle"></i> Scoring
      </a>
    </div>
  </div>
</div>
```

(The initial values in `data-cd-hours/mins/secs` are zeros — `countdown.js` populates real values on first tick. The `data-cd-days` initial value is server-rendered as a fallback if JS is disabled. We pass `now_utc` from the context for that fallback — add it to `_context_pre()` next.)

- [ ] **Step 2: Add `now_utc` to `_context_pre()` return dict**

In `core/main/home_context.py`, in the `_context_pre()` return dict, add:

```python
        'now_utc': datetime.now(timezone.utc),
```

- [ ] **Step 3: Create `static/js/countdown.js`**

```javascript
// Countdown ticker — drives the .decree countdown card on the pre-state home.
// Reads data-deadline-utc on the .decree element; ticks every second; reloads
// the page when the deadline is reached so the next request sees state='live'.
(function () {
  var el = document.querySelector('.decree[data-deadline-utc]');
  if (!el) return;

  var deadline = new Date(el.getAttribute('data-deadline-utc')).getTime();
  if (isNaN(deadline)) return;

  var dEl = el.querySelector('[data-cd-days]');
  var hEl = el.querySelector('[data-cd-hours]');
  var mEl = el.querySelector('[data-cd-mins]');
  var sEl = el.querySelector('[data-cd-secs]');
  if (!dEl || !hEl || !mEl || !sEl) return;

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function tick() {
    var now = Date.now();
    var diff = deadline - now;
    if (diff <= 0) {
      dEl.textContent = '00';
      hEl.textContent = '00';
      mEl.textContent = '00';
      sEl.textContent = '00';
      // Wait one tick so the user sees zero, then reload for state transition
      setTimeout(function () { window.location.reload(); }, 1500);
      return;
    }
    var days = Math.floor(diff / (1000 * 60 * 60 * 24));
    var hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
    var mins = Math.floor((diff / (1000 * 60)) % 60);
    var secs = Math.floor((diff / 1000) % 60);
    dEl.textContent = pad(days);
    hEl.textContent = pad(hours);
    mEl.textContent = pad(mins);
    sEl.textContent = pad(secs);
  }

  tick();
  setInterval(tick, 1000);
})();
```

- [ ] **Step 4: Load the JS only on the pre-state page**

Add a scripts block at the bottom of `_home_pre.html`:

```jinja
{% block scripts %}
  {{ super() }}
  <script src="{{ url_for('static', filename='js/countdown.js') }}"></script>
{% endblock %}
```

Wait — `_home_pre.html` is an include, not an extending template, so `{% block scripts %}` won't work from inside an include. Move this to the dispatcher shell `core/main/templates/main/index.html` instead, conditionally:

Replace `index.html` with:

```jinja
{% extends "base.html" %}

{% block title %}Corrupt Commish Club{% endblock %}

{% block content %}
<div class="home-shell home-shell--{{ state }}">
{% if state == 'out' %}
  {% include 'main/_home_out.html' %}
{% elif state == 'pre' %}
  {% include 'main/_home_pre.html' %}
{% elif state == 'live' %}
  {% include 'main/_home_live.html' %}
{% elif state == 'post' %}
  {% include 'main/_home_post.html' %}
{% endif %}
</div>
{% endblock %}

{% block scripts %}
  {{ super() }}
  {% if state == 'pre' %}
    <script src="{{ url_for('static', filename='js/countdown.js') }}"></script>
  {% endif %}
{% endblock %}
```

(Verify `base.html` actually has a `{% block scripts %}` — it does, line 241.)

Remove the abandoned scripts block from `_home_pre.html` (it never worked there anyway).

- [ ] **Step 5: Append `.decree` CSS within the HOME section**

In `static/css/style.css`, before the END marker:

```css
/* --- Pre-state: countdown card --- */
.home-shell .decree {
  position: relative;
  margin: 1.5rem 0;
  padding: 0;
  background: linear-gradient(180deg,
    var(--purple-800) 0%,
    var(--purple-900) 100%);
  border: 1px solid rgba(201,162,39,.35);
  border-radius: 14px;
  overflow: hidden;
}
.home-shell .decree::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(
    ellipse at top,
    rgba(242,211,107,.06) 0%,
    transparent 60%
  );
}
.home-shell .decree-seal {
  display: flex;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px dashed rgba(201,162,39,.25);
  position: relative;
  z-index: 1;
}
.home-shell .decree-seal .s {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--gold-light);
}
.home-shell .decree-seal .s .num {
  color: var(--bone-mute);
  margin-left: 0.4rem;
}
.home-shell .decree-seal-year {
  color: var(--bone-mute) !important;
}
.home-shell .decree-body {
  padding: 1.5rem 1rem 1rem;
  text-align: center;
  position: relative;
  z-index: 1;
}
.home-shell .decree-body h2 {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 1rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--gold-light);
  margin: 0 0 1.25rem;
}
.home-shell .decree-days {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
}
.home-shell .decree-days .d-cell {
  text-align: center;
  min-width: 56px;
}
.home-shell .decree-days .d-cell .v {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 2.8rem;
  line-height: 1;
  color: var(--bone);
  font-variant-numeric: tabular-nums;
}
.home-shell .decree-days .d-cell .u {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--bone-mute);
  margin-top: 0.25rem;
}
.home-shell .decree-days .d-sep {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 2.4rem;
  color: var(--gold-light);
  opacity: 0.5;
}
@media (min-width: 768px) {
  .home-shell .decree-days .d-cell .v { font-size: 3.6rem; }
  .home-shell .decree-days .d-cell { min-width: 72px; }
}
.home-shell .decree-foot {
  font-family: var(--font-news);
  font-style: italic;
  font-size: 0.85rem;
  color: var(--bone-mute);
  margin: 1rem 0 0;
}
.home-shell .decree-actions {
  padding: 1rem 1rem 1.25rem;
  text-align: center;
  position: relative;
  z-index: 1;
  border-top: 1px solid rgba(243,239,230,.06);
}
.home-shell .decree-cta {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.7rem 1.5rem;
  background: var(--metal-gold);
  color: var(--purple-950) !important;
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.95rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  text-decoration: none;
  border-radius: 6px;
  transition: transform 0.15s ease;
}
.home-shell .decree-cta:hover {
  transform: translateY(-1px);
  color: var(--purple-950) !important;
}
.home-shell .decree-links {
  margin-top: 0.75rem;
  display: flex;
  justify-content: center;
  gap: 1.25rem;
}
.home-shell .decree-links a {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.75rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--bone-mute);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.home-shell .decree-links a:hover { color: var(--gold-light); }
```

- [ ] **Step 6: Visually verify the countdown ticks**

Boot the dev server. Logged in (any non-WC-enrolled user is fine), refresh `/`. The page errors because ballot/game-tiles partials don't exist yet. Temporarily comment out those includes in `_home_pre.html`. Reload. The countdown card should render with deep purple bg, gold border, and the four cells should tick down every second.

Re-enable the includes after verification (next tasks fill them in).

- [ ] **Step 7: Commit**

```bash
git add core/main/templates/main/_countdown_card.html core/main/templates/main/index.html core/main/templates/main/_home_pre.html core/main/home_context.py static/js/countdown.js static/css/style.css
git commit -m "feat(home): pre-state countdown card with tick JS

Server-rendered DD/HH/MM/SS initial values + 25-line vanilla JS
ticker. data-deadline-utc on .decree drives the tick. Page reloads
on deadline-zero so next request transitions to live state."
```

---

## Task 15: Pre-state ballot variants (sealed, submit-CTA, join-CTA, view-CTA)

**Files:**
- Create: `core/main/templates/main/_ballot_card.html`
- Create: `core/main/templates/main/_submit_picks_cta.html`
- Create: `core/main/templates/main/_join_cta_card.html`
- Create: `core/main/templates/main/_view_cta_card.html`
- Modify: `static/css/style.css` (append `.ballot` + `.cta-card` rules)

- [ ] **Step 1: Create `_ballot_card.html` (sealed roster — 9 flags)**

```jinja
{# Sealed roster card — pre-state, enrolled, picks_submitted=True #}
<a href="{{ url_for('worldcup.picks') }}?edit=1" class="ballot-card">
  <div class="ballot-head">
    <div>
      <div class="ballot-label">Your roster</div>
      <div class="ballot-status">Sealed &amp; delivered</div>
    </div>
    <div class="ballot-locked">
      <span class="dot"></span>
      Locked in
    </div>
  </div>
  <div class="ballot-flags">
    {% for pick in picks %}
    <span class="ballot-flag" title="{{ pick.team.display_name }}">{{ pick.team.flag_emoji }}</span>
    {% endfor %}
  </div>
  <div class="ballot-foot">
    Nine nations bend the knee to you.
    <em>Edit any time before the whistle.</em>
  </div>
</a>
```

- [ ] **Step 2: Create `_submit_picks_cta.html`**

```jinja
{# Enrolled-no-picks CTA — pre-state, enrolled, picks_submitted=False #}
<a href="{{ url_for('worldcup.picks') }}" class="cta-card cta-card--seal">
  <div class="cta-card-eyebrow">◇ Roster open</div>
  <div class="cta-card-title">Seal Your Roster</div>
  <p class="cta-card-body">
    You're enrolled but haven't locked in nine nations yet. The Commish notices.
  </p>
  <div class="cta-card-action">
    Seal the Oath
    <i class="bi bi-arrow-right"></i>
  </div>
</a>
```

- [ ] **Step 3: Create `_join_cta_card.html`**

```jinja
{# Unenrolled pre-deadline CTA #}
<a href="{{ url_for('worldcup.join') }}" class="cta-card cta-card--join">
  <div class="cta-card-eyebrow">◈ Open Court</div>
  <div class="cta-card-title">Join the World Cup pool</div>
  <p class="cta-card-body">
    Picks lock at kickoff on June 11. Pay tribute, pick nine nations,
    take your seat at the council.
  </p>
  <div class="cta-card-action">
    Join the pool
    <i class="bi bi-arrow-right"></i>
  </div>
</a>
```

- [ ] **Step 4: Create `_view_cta_card.html`**

```jinja
{# Unenrolled post-deadline CTA — used by live + post states #}
<a href="{{ url_for('worldcup.index') }}" class="cta-card cta-card--view">
  <div class="cta-card-eyebrow">◇ Tournament in session</div>
  <div class="cta-card-title">View the World Cup</div>
  <p class="cta-card-body">
    Picks have locked. The leaderboard, schedule, and stats are all open
    to you &mdash; even without a roster.
  </p>
  <div class="cta-card-action">
    View the pool
    <i class="bi bi-arrow-right"></i>
  </div>
</a>
```

- [ ] **Step 5: Append ballot + CTA card CSS within HOME section**

Before the END marker:

```css
/* --- Pre-state: sealed ballot card --- */
.home-shell .ballot-card {
  display: block;
  margin: 1.5rem 0;
  padding: 1.25rem 1.25rem 1.5rem;
  background: linear-gradient(180deg,
    rgba(100,219,160,.08) 0%,
    rgba(26,10,54,.5) 100%);
  border: 1px solid rgba(100,219,160,.3);
  border-radius: 12px;
  text-decoration: none;
  color: var(--bone);
  transition: transform 0.15s ease, border-color 0.15s ease;
}
.home-shell .ballot-card:hover {
  transform: translateY(-2px);
  border-color: rgba(100,219,160,.5);
  color: var(--bone);
}
.home-shell .ballot-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.75rem;
}
.home-shell .ballot-label {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--bone-mute);
}
.home-shell .ballot-status {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 1.1rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--bone);
  margin-top: 0.2rem;
}
.home-shell .ballot-locked {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: #64DBA0;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.home-shell .ballot-locked .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #64DBA0;
}
.home-shell .ballot-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0.75rem 0;
}
.home-shell .ballot-flag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  font-size: 1.6rem;
  line-height: 1;
  background: rgba(10,6,18,.5);
  border: 1px solid rgba(201,162,39,.22);
  border-radius: 8px;
}
.home-shell .ballot-foot {
  font-family: var(--font-news);
  font-style: italic;
  font-size: 0.85rem;
  color: var(--bone-mute);
  line-height: 1.4;
  margin-top: 0.5rem;
}
.home-shell .ballot-foot em {
  color: var(--gold-light);
  font-style: italic;
}

/* --- CTA cards (join, view, seal) --- */
.home-shell .cta-card {
  display: block;
  margin: 1.5rem 0;
  padding: 1.5rem 1.25rem;
  border-radius: 12px;
  text-decoration: none;
  transition: transform 0.15s ease, border-color 0.15s ease;
}
.home-shell .cta-card:hover { transform: translateY(-2px); }
.home-shell .cta-card-eyebrow {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.7rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--gold-light);
  margin-bottom: 0.5rem;
}
.home-shell .cta-card-title {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 1.6rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--bone);
  margin-bottom: 0.5rem;
}
.home-shell .cta-card-body {
  font-family: var(--font-news);
  font-size: 0.95rem;
  line-height: 1.5;
  color: var(--bone-mute);
  margin-bottom: 1rem;
}
.home-shell .cta-card-action {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.95rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--gold-light);
}
.home-shell .cta-card--seal {
  background: linear-gradient(180deg,
    rgba(201,162,39,.1) 0%,
    rgba(26,10,54,.5) 100%);
  border: 1px solid rgba(201,162,39,.35);
}
.home-shell .cta-card--join {
  background: linear-gradient(180deg,
    var(--purple-800) 0%,
    var(--purple-900) 100%);
  border: 1px solid rgba(201,162,39,.3);
}
.home-shell .cta-card--view {
  background: linear-gradient(180deg,
    var(--purple-850) 0%,
    var(--purple-950) 100%);
  border: 1px solid rgba(243,239,230,.12);
}
```

- [ ] **Step 6: Visually verify all 3 pre-state ballot variants**

Three browser scenarios (use `flask shell` or admin to flip flags):

1. **Logged in, no enrollment** → "Join the World Cup pool" card visible.
2. **Logged in, enrollment exists, picks_submitted=False** → "Seal Your Roster" card visible.
3. **Logged in, enrollment exists, picks_submitted=True with 9 picks** → green sealed-roster card with 9 flag emojis visible.

To set up scenario 3 quickly via shell:

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask shell <<'EOF'
from games.worldcup.models import WorldCupEnrollment, WorldCupPick, WorldCupTeam
from extensions import db
enr = WorldCupEnrollment.query.first()
if enr:
    enr.picks_submitted = True
    teams = WorldCupTeam.query.limit(9).all()
    for t in teams:
        existing = WorldCupPick.query.filter_by(enrollment_id=enr.id, team_id=t.id).first()
        if not existing:
            db.session.add(WorldCupPick(enrollment_id=enr.id, team_id=t.id, tier=t.tier))
    db.session.commit()
    print('Seeded picks for enrollment', enr.id)
EOF
```

(Requires `flask worldcup init` to have been run first to seed teams.)

- [ ] **Step 7: Commit**

```bash
git add core/main/templates/main/_ballot_card.html core/main/templates/main/_submit_picks_cta.html core/main/templates/main/_join_cta_card.html core/main/templates/main/_view_cta_card.html static/css/style.css
git commit -m "feat(home): pre-state ballot variants + unenrolled CTA cards

3 ballot states (sealed/no-picks/unenrolled) + view CTA for live/post.
The dossier-slot pattern (per state, pick the right partial) lives in
each state's parent partial; this commit ships the leaves."
```

---

## Task 16: Pre-state opening matches + compact game tiles

**Files:**
- Create: `core/main/templates/main/_fixture_card.html`
- Create: `core/main/templates/main/_game_tiles_compact.html`
- Modify: `static/css/style.css` (append `.match-card` and `.court-games` rules)

- [ ] **Step 1: Create `_fixture_card.html` (used in pre-state opening matches loop)**

```jinja
{# Fixture card — upcoming match with kickoff time #}
<div class="match-card match-card--upcoming">
  <div class="match-head">
    <div class="grp">{{ match.stage|title }}{% if match.group_letter %} · Group {{ match.group_letter }}{% endif %}</div>
    {% if match.kickoff_utc %}
    <span class="live-pill live-pill--kickoff">
      {{ match.kickoff_utc.strftime('%a %d %b · %H:%M UTC') }}
    </span>
    {% endif %}
  </div>
  <div class="match-body">
    <div class="m-side">
      <div class="m-flag">{{ match.home_team.flag_emoji if match.home_team else '🏳️' }}</div>
      <div class="m-name">{{ match.home_team.fifa_code if match.home_team else 'TBD' }}</div>
    </div>
    <div class="m-center">
      <div class="clock">vs</div>
    </div>
    <div class="m-side">
      <div class="m-flag">{{ match.away_team.flag_emoji if match.away_team else '🏳️' }}</div>
      <div class="m-name">{{ match.away_team.fifa_code if match.away_team else 'TBD' }}</div>
    </div>
  </div>
  {% if match.venue or match.city %}
  <div class="match-foot">
    <div class="match-foot-note">
      {{ match.venue or '' }}{% if match.venue and match.city %} · {% endif %}{{ match.city or '' }}
    </div>
    <div class="match-foot-status">
      ◯ PICK DUE
    </div>
  </div>
  {% endif %}
</div>
```

- [ ] **Step 2: Create `_game_tiles_compact.html`**

```jinja
{# Compact 3-tile game strip — used by pre/live/post #}
<div class="court-games-wrap">
  <div class="sec-head">
    <div class="t">Your Games</div>
  </div>
  <div class="court-games">
    {# WC tile — always present, label depends on state #}
    {% set wc_label = 'ROSTER OPEN' %}
    {% if state == 'pre' and is_enrolled and enrollment.picks_submitted %}
      {% set wc_label = 'SEALED' %}
    {% elif state == 'live' and dossier and dossier.rank %}
      {% set wc_label = 'LIVE · #' ~ dossier.rank %}
    {% elif state == 'live' %}
      {% set wc_label = 'LIVE' %}
    {% elif state == 'post' %}
      {% set wc_label = 'COMPLETED' %}
    {% endif %}
    <a class="cg cg--active" href="{{ url_for('worldcup.index') }}">
      <div class="g">⚽</div>
      <div class="n">World Cup</div>
      <div class="p">{{ wc_label }}</div>
    </a>

    {# CFB and Golf — pulled from coming_soon_games registry #}
    {% for game in coming_soon_games %}
    <div class="cg cg--soon">
      <div class="g">{{ game.emoji }}</div>
      <div class="n">{{ game.display_name.split()[0] if game.slug == 'cfb' else 'Golf' }}</div>
      <div class="p">{% if game.slug == 'cfb' %}Sep 3{% else %}2027{% endif %}</div>
    </div>
    {% endfor %}
  </div>
</div>
```

(Date strings hard-coded per Spec B 6b note — registry doesn't carry launch-date metadata yet.)

- [ ] **Step 3: Append `.match-card` (upcoming variant) + `.court-games` CSS**

Before the END marker:

```css
/* --- Match card — shared (upcoming + final) --- */
.home-shell .match-card {
  margin: 0.75rem 0;
  background: linear-gradient(180deg,
    var(--purple-850) 0%,
    var(--purple-950) 100%);
  border: 1px solid rgba(255,255,255,.08);
  border-radius: 12px;
  overflow: hidden;
}
.home-shell .match-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid rgba(255,255,255,.06);
}
.home-shell .match-head .grp {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--bone-mute);
}
.home-shell .live-pill {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.7rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
}
.home-shell .live-pill--kickoff {
  background: rgba(242,211,107,.08);
  border: 1px solid rgba(242,211,107,.32);
  color: var(--gold-light);
}
.home-shell .live-pill--final {
  background: rgba(243,239,230,.08);
  border: 1px solid rgba(243,239,230,.22);
  color: rgba(243,239,230,.7);
}
.home-shell .match-body {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 0.75rem;
  align-items: center;
  padding: 1rem;
}
.home-shell .m-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}
.home-shell .m-flag {
  font-size: 2rem;
  line-height: 1;
}
.home-shell .m-name {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.85rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--bone);
}
.home-shell .m-score {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 2.4rem;
  line-height: 0.9;
  color: var(--bone);
  font-variant-numeric: tabular-nums;
}
.home-shell .m-center {
  text-align: center;
}
.home-shell .m-center .clock {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 1.1rem;
  color: var(--gold-light);
}
.home-shell .m-center .ft {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.65rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--bone-mute);
  margin-top: 0.2rem;
}
.home-shell .match-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.6rem 1rem;
  border-top: 1px solid rgba(255,255,255,.06);
  background: rgba(0,0,0,.25);
}
.home-shell .match-foot-note {
  font-family: var(--font-news);
  font-style: italic;
  font-size: 0.8rem;
  color: var(--bone-mute);
}
.home-shell .match-foot-status {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--gold-light);
}

/* --- Compact game tiles strip (pre/live/post) --- */
.home-shell .court-games-wrap {
  margin-top: 1.5rem;
}
.home-shell .court-games {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0.6rem;
}
.home-shell .cg {
  display: block;
  text-align: center;
  padding: 0.85rem 0.5rem 0.65rem;
  border-radius: 10px;
  text-decoration: none;
  transition: transform 0.15s ease;
}
.home-shell .cg:hover { transform: translateY(-2px); }
.home-shell .cg--active {
  background: linear-gradient(180deg,
    rgba(201,162,39,.12) 0%,
    rgba(26,10,54,.5) 100%);
  border: 1px solid rgba(201,162,39,.4);
}
.home-shell .cg--soon {
  background: rgba(26,10,54,.5);
  border: 1px solid rgba(243,239,230,.08);
  opacity: 0.7;
  cursor: default;
}
.home-shell .cg .g {
  font-size: 1.6rem;
  line-height: 1;
  margin-bottom: 0.4rem;
}
.home-shell .cg .n {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.85rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--bone);
}
.home-shell .cg .p {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.65rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--gold-light);
  margin-top: 0.25rem;
}
.home-shell .cg--soon .p {
  color: var(--bone-mute);
}
```

- [ ] **Step 4: Visually verify pre-state with all sections rendering**

Boot dev server with at least one enrollment + matches seeded. Refresh `/` logged in. Verify:
- Greet, countdown card (ticking), one of the three ballot variants, opening matches (3 fixture cards), compact game tiles all render.
- The compact tiles show ⚽ World Cup with state-correct label, then 🏈 CFB · Sep 3, then ⛳ Golf · 2027.

- [ ] **Step 5: Commit**

```bash
git add core/main/templates/main/_fixture_card.html core/main/templates/main/_game_tiles_compact.html static/css/style.css
git commit -m "feat(home): opening matches fixture card + compact game tiles

Fixture card renders the upcoming-match shape (used by pre-state).
Compact 3-tile game strip with state-aware WC label, used by
pre/live/post states."
```

---

## Task 17: Commish's Note + Dispatches partials with seed default

**Files:**
- Create: `core/main/templates/main/_commish_note.html`
- Create: `core/main/templates/main/_dispatches.html`
- Modify: `static/css/style.css` (append `.commish-note` + `.dispatches` rules)

- [ ] **Step 1: Create `_commish_note.html` with seed default copy**

```jinja
{# Commish's Note — file-edited long-form. Spec B D9. Edit this file
   directly when writing weekly recaps; commit + deploy.
   Set the entire file contents to empty string to suppress. #}
<div class="commish-note">
  <div class="sec-head">
    <div class="t">From the Commish</div>
  </div>
  <div class="commish-note-body">
    <p>
      Welcome to the Club. The Commish keeps the ledger; you keep the picks.
      Tribute window opens until June 11 &mdash; pick nine nations, take
      your seat, and we'll see who reads the table on the other side.
    </p>
    <p class="commish-note-byline">&mdash; the Commish</p>
  </div>
</div>
```

- [ ] **Step 2: Create `_dispatches.html` (empty body — Brad fills in mid-tournament)**

```jinja
{# Dispatches — file-edited short-form event feed. Spec B D9.
   Each .dispatch row is a 1-2 sentence event-driven note.
   Currently empty; ships hidden until Brad starts populating. #}

{# To enable, uncomment + edit:
<div class="dispatches">
  <div class="sec-head">
    <div class="t">Dispatches</div>
  </div>

  <div class="dispatch dispatch--pool">
    <div class="dispatch-num">+24</div>
    <div class="dispatch-text">
      <div class="who">Germany advanced</div>
      <div class="what">Dark Horse ×2.0 cleared the group. The council nods.</div>
    </div>
    <div class="dispatch-time">2h</div>
  </div>

  <div class="dispatch dispatch--pool">
    <div class="dispatch-num"><i class="bi bi-x"></i></div>
    <div class="dispatch-text">
      <div class="who">Scotland eliminated</div>
      <div class="what">Out in R32. Eight nations still earning.</div>
    </div>
    <div class="dispatch-time">1d</div>
  </div>
</div>
#}
```

- [ ] **Step 3: Append CSS for both partials**

Before the END marker:

```css
/* --- Commish's Note (long-form narrative) --- */
.home-shell .commish-note {
  margin: 1.5rem 0;
}
.home-shell .commish-note-body {
  background: linear-gradient(180deg,
    var(--purple-850) 0%,
    var(--purple-950) 100%);
  border: 1px solid rgba(243,239,230,.08);
  border-left: 3px solid var(--gold);
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
}
.home-shell .commish-note-body p {
  font-family: var(--font-news);
  font-size: 1rem;
  line-height: 1.65;
  color: var(--bone);
  margin: 0 0 1rem;
}
.home-shell .commish-note-body p:last-child { margin-bottom: 0; }
.home-shell .commish-note-byline {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.8rem !important;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--gold-light) !important;
  font-style: normal !important;
  margin-top: 1rem !important;
}

/* --- Dispatches (short-feed) --- */
.home-shell .dispatches {
  margin: 1rem 0;
}
.home-shell .dispatch {
  display: grid;
  grid-template-columns: 48px 1fr auto;
  gap: 0.75rem;
  align-items: center;
  padding: 0.85rem 1rem;
  background: rgba(26,10,54,.4);
  border: 1px solid rgba(243,239,230,.05);
  border-radius: 8px;
  margin-bottom: 0.5rem;
}
.home-shell .dispatch--yours {
  border-left: 3px solid var(--gold-light);
}
.home-shell .dispatch--pool {
  border-left: 3px solid var(--bone-mute);
}
.home-shell .dispatch-num {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 1.4rem;
  color: var(--gold-light);
  text-align: center;
  line-height: 1;
}
.home-shell .dispatch-text .who {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.95rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--bone);
}
.home-shell .dispatch-text .what {
  font-family: var(--font-news);
  font-size: 0.85rem;
  color: var(--bone-mute);
  margin-top: 0.2rem;
  line-height: 1.4;
}
.home-shell .dispatch-time {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.7rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--bone-mute);
}
```

- [ ] **Step 4: Visually verify pre-state with the Commish's Note rendering at the bottom**

Refresh `/` logged in. The "From the Commish" card with the seed welcome paragraph + "— the Commish" byline should appear after the compact game tiles.

- [ ] **Step 5: Commit**

```bash
git add core/main/templates/main/_commish_note.html core/main/templates/main/_dispatches.html static/css/style.css
git commit -m "feat(home): commish-note + dispatches partials (file-edited)

Commish's Note ships with seed welcome copy; Brad overwrites for
weekly recaps. Dispatches ships empty (commented examples in-file)
for Brad to enable mid-tournament. Both \`{% include ignore missing %}\`'d."
```

---

## Task 18: Pre-state full verification across enrollment scenarios

**Files:**
- N/A (verification only)

- [ ] **Step 1: Verify all 3 logged-in pre-state scenarios in browser**

Boot dev server. Run through each scenario; for each, refresh `/` and confirm the visual.

**Scenario A: Logged in, no WC enrollment**
- Greet block ✓
- Countdown card (ticking) ✓
- "Join the World Cup pool" CTA card ✓ (no ballot/no-picks card)
- Opening matches (if matches seeded) ✓
- Compact game tiles ✓ (WC tile says "ROSTER OPEN")
- Commish's Note seed default ✓

**Scenario B: Logged in, enrolled, picks_submitted=False**
- Greet ✓
- Countdown ✓
- "Seal Your Roster" gold CTA card ✓
- Opening matches ✓
- Compact game tiles (WC says "ROSTER OPEN") ✓
- Commish's Note ✓

**Scenario C: Logged in, enrolled, picks_submitted=True with 9 picks**
- Greet ✓
- Countdown ✓
- Sealed green ballot card with 9 flag emojis (linked to `/worldcup/picks?edit=1`) ✓
- Opening matches ✓
- Compact game tiles (WC says "SEALED") ✓
- Commish's Note ✓

**Scenario D: Logged out**
- Renders `_home_out.html` (verified earlier in Task 12) ✓

- [ ] **Step 2: Mobile viewport check**

In Chrome DevTools, switch to iPhone 13 (390x844). All three logged-in scenarios should:
- Render single-column, no horizontal scroll
- Countdown cells visible without overflow (4 cells, separators between)
- Compact game tiles strip stays 3-across

- [ ] **Step 3: Run the test suite (sanity)**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/ -q
```

Expected: all 129 tests pass.

- [ ] **Step 4: Commit (no code change — this is a verification milestone)**

If you needed to fix any visual bugs during verification, commit those. Otherwise no commit; tag this milestone in the PR description.

---

## Task 19: Live-state shell + greet (with dossier slot)

**Files:**
- Modify: `core/main/templates/main/_home_live.html` (replace stub)

- [ ] **Step 1: Replace `_home_live.html` with the full shell**

```jinja
{# Live-tournament home — Spec B section 7 #}
<div class="container-fluid home-live">
  <div class="row">

    {# Mobile: single column. Desktop: two columns (60/40 split). #}
    <div class="col-12 col-lg-7 home-live-left">

      {# Greet — full width on mobile, left col on desktop #}
      <div class="greet">
        <p class="greet-line">
          Council is in session &mdash;
          <span class="v">{{ display_name }}</span>
        </p>
        <h1 class="greet-title">
          Your <span class="home-metal-text">Dossier</span>
        </h1>
        <div class="greet-court">{{ court_line }}</div>
      </div>

      {# Dossier slot — enrolled or view-CTA #}
      {% if not is_enrolled %}
        {% include 'main/_view_cta_card.html' %}
      {% else %}
        {% include 'main/_dossier_card.html' %}
      {% endif %}

      {# Recent Results — left col on desktop #}
      <div class="sec-head">
        <div class="t">Recent Results</div>
        <a class="more" href="{{ url_for('worldcup.schedule') }}">All fixtures &rsaquo;</a>
      </div>
      {% include 'main/_recent_results.html' %}

    </div>{# /.col-lg-7 #}

    <div class="col-12 col-lg-5 home-live-right">

      {# Leaderboard preview — full width mobile, right col desktop #}
      <div class="sec-head">
        <div class="t">Leaderboard</div>
        <a class="more" href="{{ url_for('worldcup.leaderboard') }}">Full ledger &rsaquo;</a>
      </div>
      <div class="rolls">
        {% for row in top_3_plus_you %}
        {% if row.separator_above %}<div class="roll-dots">&middot; &middot; &middot;</div>{% endif %}
        <div class="roll-row{% if row.is_you %} roll-row--you{% endif %}">
          <div class="roll-rank{% if row.rank == 1 %} roll-rank--gold{% endif %}">{{ row.rank }}</div>
          <div class="roll-meta">
            <div class="roll-name">
              {{ row.enrollment.get_display_name() }}
              {% if row.is_you %}<span class="roll-you-chip">YOU</span>{% endif %}
            </div>
            {% if row.tagline %}
            <div class="roll-tagline">{{ row.tagline }}</div>
            {% endif %}
          </div>
          <div class="roll-pts">{{ '%.0f'|format(row.enrollment.total_score) }}<span class="u">PTS</span></div>
        </div>
        {% endfor %}
      </div>

      {# Narrative partials — bottom of right col on desktop #}
      {% include 'main/_commish_note.html' ignore missing %}
      {% include 'main/_dispatches.html' ignore missing %}

    </div>{# /.col-lg-5 #}

  </div>{# /.row #}

  {# Compact game tiles strip — full width below both columns #}
  <div class="row">
    <div class="col-12">
      {% include 'main/_game_tiles_compact.html' %}
    </div>
  </div>

</div>
```

- [ ] **Step 2: Smoke test (live state will partially render — dossier + recent results stubs come next)**

Set `WC_FAKE_NOW=2026-06-15T00:00:00Z` and refresh `/` logged in. Expect a 500 because `_dossier_card.html` and `_recent_results.html` don't exist yet. Confirm the error trace points to a missing template (not a syntax error). Move on to Task 20.

- [ ] **Step 3: Commit**

```bash
git add core/main/templates/main/_home_live.html
git commit -m "feat(home): live-state shell with two-column desktop layout

Bootstrap row + col-12/col-lg-7/col-lg-5 split. Greet + dossier +
recent results in left col; leaderboard + narrative partials in
right col. Compact game tiles full-width below."
```

---

## Task 20: Live-state dossier card + SVG sparkline

**Files:**
- Create: `core/main/templates/main/_dossier_card.html`
- Modify: `static/css/style.css` (append `.dossier` rules)

- [ ] **Step 1: Create `_dossier_card.html` with server-rendered SVG sparkline**

```jinja
{# Live-state dossier card — Spec B section 7c #}
<div class="dossier">
  <div class="dossier-stamp">◈ Classified · CCC ◈</div>

  <div class="dossier-rank">
    <div class="rank-num">
      <span class="rank-hash">#</span>{{ dossier.rank }}
    </div>
    <div class="rank-meta">
      <div class="rank-of">of {{ dossier.total_count }} competitors</div>
      {% if dossier.week_delta_rank is not none %}
        {% if dossier.week_delta_rank < 0 %}
        <div class="rank-mvmt rank-mvmt--up">
          <i class="bi bi-caret-up-fill"></i>
          Up {{ dossier.week_delta_rank|abs }} this week
        </div>
        {% elif dossier.week_delta_rank > 0 %}
        <div class="rank-mvmt rank-mvmt--down">
          <i class="bi bi-caret-down-fill"></i>
          Down {{ dossier.week_delta_rank }} this week
        </div>
        {% else %}
        <div class="rank-mvmt rank-mvmt--flat">
          <i class="bi bi-dash"></i>
          Holding this week
        </div>
        {% endif %}
      {% endif %}
    </div>
  </div>

  {# Sparkline — server-rendered SVG #}
  {% if dossier.sparkline_data and dossier.sparkline_data|length >= 2 %}
  <div class="dossier-sparkline">
    <div class="sparkline-cap">
      <span>Rank · last {{ dossier.sparkline_data|length }} days</span>
      <span>{{ dossier.sparkline_data[0] }} &rarr; {{ dossier.sparkline_data[-1] }}</span>
    </div>
    {% set data = dossier.sparkline_data %}
    {% set width = 318 %}
    {% set height = 48 %}
    {% set pad = 3 %}
    {% set max_v = data|max %}
    {% set min_v = data|min %}
    {% set range_v = (max_v - min_v) if (max_v - min_v) > 0 else 1 %}
    {% set step_x = (width - pad*2) / (data|length - 1) %}
    <svg width="100%" height="{{ height }}" viewBox="0 0 {{ width }} {{ height }}" preserveAspectRatio="none">
      <defs>
        <linearGradient id="spark-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#F2D36B" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="#F2D36B" stop-opacity="0"/>
        </linearGradient>
      </defs>
      {# Baseline dashes #}
      {% for t in [0, 0.5, 1] %}
      <line x1="{{ pad }}" x2="{{ width - pad }}"
            y1="{{ pad + t * (height - pad*2) }}" y2="{{ pad + t * (height - pad*2) }}"
            stroke="rgba(242,211,107,0.1)" stroke-dasharray="2 4"/>
      {% endfor %}
      {# Path — invert y so smaller rank = higher visual #}
      {% set path = [] %}
      {% set area = [] %}
      {% for v in data %}
        {% set i = loop.index0 %}
        {% set x = pad + i * step_x %}
        {% set y = pad + ((v - min_v) / range_v) * (height - pad*2) %}
        {% if i == 0 %}
          {% set _ = path.append('M' ~ x ~ ',' ~ y) %}
          {% set _ = area.append('M' ~ x ~ ',' ~ y) %}
        {% else %}
          {% set _ = path.append('L' ~ x ~ ',' ~ y) %}
          {% set _ = area.append('L' ~ x ~ ',' ~ y) %}
        {% endif %}
        {% if loop.last %}
          {% set _ = area.append('L' ~ x ~ ',' ~ height) %}
          {% set _ = area.append('L' ~ pad ~ ',' ~ height) %}
          {% set _ = area.append('Z') %}
        {% endif %}
      {% endfor %}
      <path d="{{ area|join(' ') }}" fill="url(#spark-fill)"/>
      <path d="{{ path|join(' ') }}" fill="none" stroke="#F2D36B" stroke-width="1.8"
            stroke-linecap="round" stroke-linejoin="round"/>
      {# Dots — last point is bigger and brighter #}
      {% for v in data %}
        {% set i = loop.index0 %}
        {% set x = pad + i * step_x %}
        {% set y = pad + ((v - min_v) / range_v) * (height - pad*2) %}
        <circle cx="{{ x }}" cy="{{ y }}"
                r="{{ 3 if loop.last else 1.4 }}"
                fill="{{ '#FFF1B8' if loop.last else '#F2D36B' }}"
                {% if loop.last %}stroke="#F2D36B" stroke-width="1"{% endif %}/>
      {% endfor %}
    </svg>
  </div>
  {% else %}
  <div class="dossier-sparkline-empty">
    Tracking starts {{ dossier.sparkline_data[0] if dossier.sparkline_data else 'tonight' }} &mdash; trends arrive after the first daily snapshot.
  </div>
  {% endif %}

  {# 3-stat strip #}
  <div class="dossier-meta">
    <div class="d-meta">
      <div class="k">{{ '%.0f'|format(dossier.total_score) }}</div>
      <div class="l">Points</div>
    </div>
    <div class="d-meta">
      <div class="k{% if dossier.alive_count == 9 %} d-meta-k--gold{% elif dossier.alive_count <= 4 %} d-meta-k--red{% endif %}">{{ dossier.alive_count }} / 9</div>
      <div class="l">Alive</div>
    </div>
    <div class="d-meta">
      {% if dossier.week_delta_points is not none %}
      <div class="k{% if dossier.week_delta_points > 0 %} d-meta-k--green{% elif dossier.week_delta_points < 0 %} d-meta-k--red{% endif %}">
        {% if dossier.week_delta_points >= 0 %}+{% endif %}{{ '%.0f'|format(dossier.week_delta_points) }}
      </div>
      {% else %}
      <div class="k">—</div>
      {% endif %}
      <div class="l">This Week</div>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Append `.dossier` CSS within HOME section**

Before the END marker:

```css
/* --- Live-state: dossier card --- */
.home-shell .dossier {
  position: relative;
  margin: 1rem 0 1.5rem;
  padding: 1.25rem;
  background: linear-gradient(180deg,
    var(--purple-800) 0%,
    var(--purple-950) 100%);
  border: 1px solid rgba(201,162,39,.3);
  border-radius: 14px;
}
.home-shell .dossier-stamp {
  position: absolute;
  top: 0.85rem;
  right: 1rem;
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.65rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--gold-light);
  opacity: 0.6;
}
.home-shell .dossier-rank {
  display: flex;
  align-items: flex-end;
  gap: 1rem;
  padding-top: 0.5rem;
}
.home-shell .rank-num {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 4.5rem;
  line-height: 0.85;
  color: var(--bone);
  font-variant-numeric: tabular-nums;
}
.home-shell .rank-hash {
  font-size: 2.2rem;
  color: var(--gold-light);
}
.home-shell .rank-meta {
  flex: 1;
  padding-bottom: 0.4rem;
}
.home-shell .rank-of {
  font-family: var(--font-news);
  font-size: 0.85rem;
  font-style: italic;
  color: var(--bone-mute);
}
.home-shell .rank-mvmt {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.75rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-top: 0.4rem;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.home-shell .rank-mvmt--up { color: #64DBA0; }
.home-shell .rank-mvmt--down { color: #FF8089; }
.home-shell .rank-mvmt--flat { color: var(--bone-mute); }

.home-shell .dossier-sparkline {
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(243,239,230,.06);
}
.home-shell .sparkline-cap {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.7rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--bone-mute);
  margin-bottom: 0.5rem;
}
.home-shell .dossier-sparkline-empty {
  margin-top: 1.25rem;
  padding: 0.85rem 0;
  border-top: 1px solid rgba(243,239,230,.06);
  font-family: var(--font-news);
  font-style: italic;
  font-size: 0.85rem;
  color: var(--bone-mute);
  text-align: center;
}

.home-shell .dossier-meta {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0.5rem;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(243,239,230,.06);
}
.home-shell .d-meta {
  text-align: center;
}
.home-shell .d-meta .k {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 1.6rem;
  line-height: 1;
  color: var(--bone);
  font-variant-numeric: tabular-nums;
}
.home-shell .d-meta-k--gold { color: var(--gold-light); }
.home-shell .d-meta-k--green { color: #64DBA0; }
.home-shell .d-meta-k--red { color: #FF8089; }
.home-shell .d-meta .l {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.65rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--bone-mute);
  margin-top: 0.35rem;
}
```

- [ ] **Step 3: Visually verify dossier card (with at least 2 snapshots seeded)**

Set up: log in, ensure WC enrollment exists, run `flask worldcup snapshot-ranks --backfill 3` to seed 4 snapshots. Then `WC_FAKE_NOW=2026-06-15T00:00:00Z flask run`. Refresh `/`.

Expect: Dossier card with rank #1 (only enrollment), "of 1 competitors" line, "Holding this week" trend (since backfill snapshots all have same rank), sparkline (flat line — all 4 points equal), 3-stat strip (Points / 0/9 Alive / +0 This Week).

- [ ] **Step 4: Commit**

```bash
git add core/main/templates/main/_dossier_card.html static/css/style.css
git commit -m "feat(home): live dossier card with server-rendered SVG sparkline

Rank/of-N/trend, 7-day sparkline (Jinja-generated SVG, no JS),
3-stat strip (Points / Alive / This Week). Sparkline gracefully
degrades to a 'tracking starts' note when <2 snapshots."
```

---

## Task 21: Live-state recent results + leaderboard preview CSS

**Files:**
- Create: `core/main/templates/main/_recent_results.html`
- Modify: `static/css/style.css` (append `.rolls` + final-match-card variants)

- [ ] **Step 1: Create `_recent_results.html`**

```jinja
{# Live-state recent results — last 5 completed matches with roster intersection #}
{% if your_pick_results %}
{% for item in your_pick_results %}
{% set match = item.match %}
<div class="match-card match-card--final">
  <div class="match-head">
    <div class="grp">
      {{ match.stage|title }}{% if match.group_letter %} · Group {{ match.group_letter }}{% endif %}
    </div>
    <span class="live-pill live-pill--final">Final</span>
  </div>
  <div class="match-body">
    <div class="m-side">
      <div class="m-flag">{{ match.home_team.flag_emoji if match.home_team else '🏳️' }}</div>
      <div class="m-name">{{ match.home_team.fifa_code if match.home_team else 'TBD' }}</div>
      <div class="m-score">{{ match.home_score if match.home_score is not none else '—' }}</div>
    </div>
    <div class="m-center">
      <div class="ft">FT</div>
    </div>
    <div class="m-side">
      <div class="m-flag">{{ match.away_team.flag_emoji if match.away_team else '🏳️' }}</div>
      <div class="m-name">{{ match.away_team.fifa_code if match.away_team else 'TBD' }}</div>
      <div class="m-score">{{ match.away_score if match.away_score is not none else '—' }}</div>
    </div>
  </div>
  {% if item.roster_match and is_enrolled %}
  <div class="match-foot">
    <div class="match-foot-note">
      YOUR ROSTER &middot;
      {% set rm_team = match.home_team if item.roster_match.side == 'home' else match.away_team %}
      <strong>{{ rm_team.display_name }}</strong>
    </div>
    {% set won = (item.roster_match.side == 'home' and match.winner_team_id == match.home_team_id) or (item.roster_match.side == 'away' and match.winner_team_id == match.away_team_id) %}
    <div class="match-foot-status{% if won %} match-foot-status--win{% else %} match-foot-status--loss{% endif %}">
      {% if won %}+ POINTS EARNED{% else %}NO POINTS{% endif %}
    </div>
  </div>
  {% endif %}
</div>
{% endfor %}
{% else %}
<div class="match-empty">
  <p>No completed matches yet. Once results roll in, they'll land here.</p>
</div>
{% endif %}
```

- [ ] **Step 2: Append leaderboard preview CSS + final match-foot variants**

Before the END marker:

```css
/* --- Live-state: leaderboard preview (rolls) --- */
.home-shell .rolls {
  margin: 0;
}
.home-shell .roll-row {
  display: grid;
  grid-template-columns: 36px 1fr auto;
  gap: 0.85rem;
  align-items: center;
  padding: 0.85rem 1rem;
  background: rgba(26,10,54,.4);
  border: 1px solid rgba(243,239,230,.05);
  border-radius: 8px;
  margin-bottom: 0.4rem;
}
.home-shell .roll-row--you {
  background: linear-gradient(180deg,
    rgba(201,162,39,.1) 0%,
    rgba(26,10,54,.5) 100%);
  border-color: rgba(201,162,39,.4);
}
.home-shell .roll-rank {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 1.4rem;
  color: var(--bone-mute);
  text-align: center;
}
.home-shell .roll-rank--gold {
  color: var(--gold-light);
}
.home-shell .roll-name {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 1rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--bone);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.home-shell .roll-you-chip {
  font-size: 0.6rem;
  letter-spacing: 0.2em;
  background: var(--gold-light);
  color: var(--purple-950);
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
}
.home-shell .roll-tagline {
  font-family: var(--font-news);
  font-style: italic;
  font-size: 0.8rem;
  color: var(--bone-mute);
  margin-top: 0.15rem;
  line-height: 1.3;
}
.home-shell .roll-pts {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 1.3rem;
  color: var(--bone);
  font-variant-numeric: tabular-nums;
}
.home-shell .roll-pts .u {
  font-size: 0.6rem;
  letter-spacing: 0.18em;
  margin-left: 0.3rem;
  color: var(--bone-mute);
  font-weight: 500;
}
.home-shell .roll-dots {
  text-align: center;
  font-family: var(--font-teko);
  letter-spacing: 0.5em;
  color: var(--bone-mute);
  margin: 0.25rem 0;
}

/* --- Match foot status variants (live-state recent results) --- */
.home-shell .match-foot-status--win { color: #64DBA0; }
.home-shell .match-foot-status--loss { color: var(--bone-mute); }
.home-shell .match-empty {
  padding: 2rem 1rem;
  text-align: center;
  font-family: var(--font-news);
  font-style: italic;
  color: var(--bone-mute);
  background: rgba(26,10,54,.3);
  border: 1px dashed rgba(243,239,230,.1);
  border-radius: 8px;
}
```

- [ ] **Step 3: Visually verify live state with leaderboard + recent results**

Seed at least one completed match via shell:

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask shell <<'EOF'
from games.worldcup.models import WorldCupMatch, WorldCupTeam
from extensions import db
m = WorldCupMatch.query.filter(WorldCupMatch.home_team_id.isnot(None)).first()
if m:
    m.home_score = 2
    m.away_score = 1
    m.is_completed = True
    m.winner_team_id = m.home_team_id
    db.session.commit()
    print(f'Match {m.match_number} marked final')
EOF
```

Refresh `/` (logged in, `WC_FAKE_NOW=2026-06-15T00:00:00Z`). Expect:
- Greet ✓
- Dossier (or view-CTA if unenrolled) ✓
- "Recent Results" header + 1+ final match cards ✓
- "Leaderboard" header + your row (highlighted gold) with tagline ✓
- Compact game tiles ✓ (WC says "LIVE · #1")

Verify both enrolled and unenrolled scenarios.

- [ ] **Step 4: Commit**

```bash
git add core/main/templates/main/_recent_results.html static/css/style.css
git commit -m "feat(home): live recent-results + leaderboard preview styling

Recent results renders last 5 completed matches with optional
roster-intersection foot row showing earned/no-points. Leaderboard
preview rolls with you-row highlight, you-chip, and contextual
taglines from _tagline_for()."
```

---

## Task 22: Live-state desktop two-column responsive CSS

**Files:**
- Modify: `static/css/style.css` (append responsive rules for `.home-live`)

- [ ] **Step 1: Append two-column desktop CSS**

Before the END marker:

```css
/* --- Live state: container sizing --- */
.home-shell .home-live {
  max-width: 1280px;
  margin: 0 auto;
}
@media (max-width: 991px) {
  /* Mobile: each column gets a max-width like the other states */
  .home-shell .home-live-left,
  .home-shell .home-live-right {
    max-width: 640px;
    margin: 0 auto;
  }
}
@media (min-width: 992px) {
  /* Desktop: tighter padding between columns */
  .home-shell .home-live-left { padding-right: 1.5rem; }
  .home-shell .home-live-right { padding-left: 1.5rem; }
  /* Greet stays text-aligned-left on desktop instead of centered */
  .home-shell .home-live .greet { text-align: left; }
}
```

- [ ] **Step 2: Visually verify desktop two-column layout**

Set browser width to ≥1024px (use DevTools responsive mode if needed). Refresh `/` in live state with the seeded data from Task 21. Expect:
- Left column (60% width): greet, dossier, recent results
- Right column (40% width): leaderboard, commish-note, dispatches
- Compact game tiles: full-width row below both columns

Set browser width to ≤768px. Verify columns stack into single mobile-first column with each constrained to ~640px max-width (same as other states).

- [ ] **Step 3: Commit**

```bash
git add static/css/style.css
git commit -m "feat(home): live-state two-column desktop responsive layout

Mobile-first single column up to 991px; col-lg-7/col-lg-5 split on
desktop with tighter inter-column padding. Greet text-aligns left on
desktop (vs centered mobile)."
```

---

## Task 23: Live-state full verification

**Files:**
- N/A (verification only)

- [ ] **Step 1: Verify all live-state scenarios in browser**

With `WC_FAKE_NOW=2026-06-15T00:00:00Z`, run through:

**Scenario A: Logged in, enrolled, with snapshots + completed matches + 9 picks**
- Greet ✓
- Dossier with sparkline (3+ data points), trend pill, 3-stat strip ✓
- Recent results (≥1 final card; foot row if any pick intersects) ✓
- Leaderboard preview with you-row + tagline ✓
- Commish's Note ✓ + Dispatches (empty unless you uncommented) ✓
- Compact game tiles (WC says "LIVE · #N") ✓
- Two-column desktop layout at ≥992px ✓

**Scenario B: Logged in, unenrolled (delete enrollment row to test)**
- Greet ✓
- "View the World Cup" CTA card in dossier slot ✓
- Recent results (no foot rows — no roster) ✓
- Leaderboard preview (top-3 only, no you-row) ✓

**Scenario C: Logged in, enrolled, no snapshots**
- Dossier shows current rank/points/alive but "Tracking starts tonight" instead of sparkline ✓

**Scenario D: Logged in, enrolled, no completed matches**
- Recent results empty state ("No completed matches yet") ✓

- [ ] **Step 2: Mobile viewport check (live state)**

Chrome DevTools, iPhone 13 (390x844). Live state should:
- Stack to single column
- Dossier card readable (rank #N at left, meta at right, sparkline beneath)
- Compact game tiles 3-across
- Leaderboard rolls full-width

- [ ] **Step 3: Run the test suite**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/ -q
```

Expected: 129 passed.

- [ ] **Step 4: Verification milestone (no commit unless bug fixes)**

If any visual bugs were caught and fixed, commit those.

---

## Task 24: Post-state shell + greet [FD]

**Files:**
- Modify: `core/main/templates/main/_home_post.html` (replace stub)

**Frontend-design skill recommendation:** This task and Tasks 25-27 build undesigned components (champion banner, podium, roster recap). Invoke `/frontend-design:frontend-design` to apply real design judgment to the layouts and visual language — the spec gives the structure but the polish is yours to shape.

- [ ] **Step 1: Replace `_home_post.html` with the full shell**

```jinja
{# Post-tournament home — Spec B section 8 #}
<div class="home-col">

  {# Greet #}
  <div class="greet">
    <p class="greet-line">
      The Court has adjourned &mdash;
      <span class="v">{{ display_name }}</span>
    </p>
    <h1 class="greet-title">
      The 2026
      <span class="home-metal-text">World Cup</span>
    </h1>
    <div class="greet-court">
      That's a wrap
      {% if champion_team %}◆ {{ champion_team.display_name }} took it{% endif %}
      ◆ the Commish closes the ledger
    </div>
  </div>

</div>{# /.home-col — banner breaks out below #}

{# Champion banner — full-bleed #}
{% include 'main/_champion_banner.html' %}

<div class="home-col">

  {# Final podium — top 3 #}
  {% if top_3_final %}
  <div class="sec-head">
    <div class="t">The Final Standings</div>
    <a class="more" href="{{ url_for('worldcup.leaderboard') }}">Full ledger &rsaquo;</a>
  </div>
  <div class="podium">
    {% if top_3_final|length >= 2 %}
    <div class="podium-tier podium-tier--second">
      <div class="podium-rank">2</div>
      <div class="podium-name">{{ top_3_final[1].get_display_name() }}</div>
      <div class="podium-pts">{{ '%.0f'|format(top_3_final[1].total_score) }} <span>PTS</span></div>
    </div>
    {% endif %}
    <div class="podium-tier podium-tier--first">
      <div class="podium-rank">1</div>
      <div class="podium-name">{{ top_3_final[0].get_display_name() }}</div>
      <div class="podium-pts">{{ '%.0f'|format(top_3_final[0].total_score) }} <span>PTS</span></div>
    </div>
    {% if top_3_final|length >= 3 %}
    <div class="podium-tier podium-tier--third">
      <div class="podium-rank">3</div>
      <div class="podium-name">{{ top_3_final[2].get_display_name() }}</div>
      <div class="podium-pts">{{ '%.0f'|format(top_3_final[2].total_score) }} <span>PTS</span></div>
    </div>
    {% endif %}
  </div>
  {% endif %}

  {# Roster recap slot — enrolled or view-CTA #}
  {% if not is_enrolled %}
    {% include 'main/_view_cta_card.html' %}
  {% else %}
    <div class="roster-recap">
      <div class="roster-recap-head">
        <div class="recap-eyebrow">You finished</div>
        <div class="recap-rank">
          <span class="hash">#</span>{{ your_final_rank }}
          <span class="of">of {{ total_count }}</span>
        </div>
        <div class="recap-sub">
          {{ '%.0f'|format(enrollment.total_score) }} points
          {% if your_climbed_n is not none and your_climbed_n != 0 %}
          &middot;
          {% if your_climbed_n > 0 %}climbed {{ your_climbed_n }} spots{% else %}slipped {{ your_climbed_n|abs }} spots{% endif %}
          {% endif %}
        </div>
      </div>

      <div class="sec-head sec-head--inset">
        <div class="t">Your Nine Nations</div>
      </div>
      <div class="roster-recap-rows">
        {% for row in your_roster_recap %}
        <div class="roster-recap-row{% if row.is_champion %} roster-recap-row--champion{% endif %}">
          <div class="rr-flag">{{ row.pick.team.flag_emoji }}</div>
          <div class="rr-code">{{ row.pick.team.fifa_code }}</div>
          <div class="rr-tier">{{ row.tier_name }}</div>
          <div class="rr-finish">{{ row.best_finish }}</div>
          <div class="rr-pts">+{{ '%.0f'|format(row.points) }}</div>
        </div>
        {% endfor %}
      </div>

      <a href="{{ url_for('worldcup.leaderboard') }}" class="roster-recap-cta">
        View Full Leaderboard
        <i class="bi bi-arrow-right"></i>
      </a>
    </div>
  {% endif %}

  {# Narrative partials #}
  {% include 'main/_commish_note.html' ignore missing %}
  {% include 'main/_dispatches.html' ignore missing %}

  {# Compact game tiles strip #}
  {% include 'main/_game_tiles_compact.html' %}

</div>{# /.home-col #}
```

- [ ] **Step 2: Smoke test (will fail until `_champion_banner.html` exists in Task 25)**

Set up: mark match #104 complete with a winner, then `WC_FAKE_NOW=2026-07-20T00:00:00Z`. Refresh `/`. Expect 500 (missing `_champion_banner.html`). Confirm error trace, move on.

- [ ] **Step 3: Commit**

```bash
git add core/main/templates/main/_home_post.html
git commit -m "feat(home): post-state shell with greet + podium + recap

Shell renders greet (full-width column) then breaks out for the
champion banner, then resumes column layout for podium, your-roster
recap (or view-CTA), narrative partials, and game tiles."
```

---

## Task 25: Champion banner with glow animation [FD]

**Files:**
- Create: `core/main/templates/main/_champion_banner.html`
- Modify: `static/css/style.css` (append `.champion-banner` rules)

**[FD]** Use `/frontend-design:frontend-design` to refine the banner's visual treatment — the spec describes structure (eyebrow, flag, name, summary, glow); the skill helps with the polish (glow intensity, halo geometry, typographic hierarchy).

- [ ] **Step 1: Create `_champion_banner.html`**

```jinja
{# Post-state champion banner — Spec B section 8b #}
<div class="champion-banner">
  <div class="champion-glow-bg"></div>
  <div class="champion-content">
    <div class="champion-eyebrow">◈ 2026 FIFA World Cup Champions ◈</div>

    {% if champion_team %}
    <div class="champion-flag">{{ champion_team.flag_emoji }}</div>
    <div class="champion-name">{{ champion_team.display_name }}</div>
    {% if champion_summary %}
    <div class="champion-summary">{{ champion_summary }}</div>
    {% endif %}
    {% if final_match and final_match.venue %}
    <div class="champion-detail">
      Final &middot; {{ final_match.venue }}{% if final_match.city %}, {{ final_match.city }}{% endif %}
      {% if final_match.kickoff_utc %} &middot; {{ final_match.kickoff_utc.strftime('%d %b %Y') }}{% endif %}
    </div>
    {% endif %}
    {% else %}
    <div class="champion-flag">🏆</div>
    <div class="champion-name">Champion Pending</div>
    <div class="champion-summary">The final result hasn't been entered yet.</div>
    {% endif %}
  </div>
</div>
```

- [ ] **Step 2: Append champion banner CSS with glow animation**

Before the END marker:

```css
/* --- Post-state: champion banner (full-bleed) --- */
.home-shell .champion-banner {
  position: relative;
  margin: 1.5rem -1rem;
  padding: 3rem 1rem 3.5rem;
  text-align: center;
  background: linear-gradient(180deg,
    var(--purple-950) 0%,
    var(--purple-900) 50%,
    var(--purple-950) 100%);
  border-top: 1px solid rgba(201,162,39,.3);
  border-bottom: 1px solid rgba(201,162,39,.3);
  overflow: hidden;
}
@media (min-width: 768px) {
  .home-shell .champion-banner {
    margin-left: 0;
    margin-right: 0;
    border-radius: 16px;
    border-left: 1px solid rgba(201,162,39,.3);
    border-right: 1px solid rgba(201,162,39,.3);
    max-width: 960px;
    margin-left: auto;
    margin-right: auto;
  }
}
.home-shell .champion-glow-bg {
  position: absolute;
  inset: 0;
  background: var(--champion-glow);
  pointer-events: none;
  animation: champion-pulse 4s ease-in-out infinite;
}
@keyframes champion-pulse {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.05); }
}
@media (prefers-reduced-motion: reduce) {
  .home-shell .champion-glow-bg {
    animation: none;
    opacity: 0.5;
  }
}
.home-shell .champion-content {
  position: relative;
  z-index: 1;
}
.home-shell .champion-eyebrow {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.8rem;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--gold-light);
  margin-bottom: 1.5rem;
}
.home-shell .champion-flag {
  font-size: 5rem;
  line-height: 1;
  margin-bottom: 1rem;
  filter: drop-shadow(0 4px 16px rgba(0,0,0,.4));
}
@media (min-width: 768px) {
  .home-shell .champion-flag { font-size: 7rem; }
}
.home-shell .champion-name {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 2.8rem;
  line-height: 1;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: var(--metal-gold);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin: 0.5rem 0;
}
@media (min-width: 768px) {
  .home-shell .champion-name { font-size: 4rem; }
}
.home-shell .champion-summary {
  font-family: var(--font-news);
  font-size: 1.05rem;
  color: var(--bone);
  margin-top: 1rem;
  font-style: italic;
}
.home-shell .champion-detail {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.75rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--bone-mute);
  margin-top: 0.5rem;
}
```

- [ ] **Step 3: Visually verify champion banner**

Set up: mark match #104 complete with a winner team, both teams seeded:

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask shell <<'EOF'
from games.worldcup.models import WorldCupMatch, WorldCupTeam
from extensions import db
m = WorldCupMatch.query.filter_by(match_number=104).first()
bra = WorldCupTeam.query.filter_by(fifa_code='BRA').first()
arg = WorldCupTeam.query.filter_by(fifa_code='ARG').first()
if m and bra and arg:
    m.home_team_id = bra.id
    m.away_team_id = arg.id
    m.home_score = 3
    m.away_score = 2
    m.extra_time = True
    m.winner_team_id = bra.id
    m.is_completed = True
    m.venue = 'Estadio Azteca'
    m.city = 'Mexico City'
    db.session.commit()
    print('Final mocked: BRA def ARG 3-2 (ET)')
EOF
```

Then `WC_FAKE_NOW=2026-07-20T00:00:00Z flask run`. Refresh `/`. Expect:
- Greet "The Court has adjourned" with display name
- Champion banner: 🇧🇷 flag, "Brazil" in metal-gold gradient, "Defeated Argentina 3–2 in extra time"
- Subtle gold glow pulse animation behind the flag

Test reduced-motion: in DevTools, emulate `prefers-reduced-motion: reduce`. Glow should freeze (no animation, opacity ~0.5).

- [ ] **Step 4: Commit**

```bash
git add core/main/templates/main/_champion_banner.html static/css/style.css
git commit -m "feat(home): post-state champion banner with glow animation

Full-bleed banner with metal-gold champion name, supporting summary
auto-rendered from final_match data (extra-time/penalties suffix),
gold glow pulse animation respecting prefers-reduced-motion."
```

---

## Task 26: Post-state podium [FD]

**Files:**
- Modify: `static/css/style.css` (append `.podium` rules)

**[FD]** Podium is undesigned — `/frontend-design:frontend-design` worth invoking for visual treatment.

- [ ] **Step 1: Append podium CSS**

Before the END marker:

```css
/* --- Post-state: final podium --- */
.home-shell .podium {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0.75rem;
  align-items: end;
  margin: 1rem 0 2rem;
}
.home-shell .podium-tier {
  text-align: center;
  padding: 1rem 0.5rem 1.25rem;
  background: linear-gradient(180deg,
    rgba(58,29,114,.6) 0%,
    var(--purple-950) 100%);
  border: 1px solid rgba(243,239,230,.08);
  border-radius: 8px 8px 0 0;
  position: relative;
}
.home-shell .podium-tier--first {
  background: linear-gradient(180deg,
    rgba(201,162,39,.25) 0%,
    var(--purple-900) 100%);
  border: 1px solid rgba(201,162,39,.5);
  padding-top: 1.5rem;
  padding-bottom: 1.75rem;
}
.home-shell .podium-tier--first::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--podium-glow);
  pointer-events: none;
  border-radius: inherit;
}
.home-shell .podium-tier--second { transform: translateY(20px); }
.home-shell .podium-tier--third { transform: translateY(35px); }
.home-shell .podium-rank {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 1.6rem;
  color: var(--bone-mute);
  margin-bottom: 0.5rem;
  position: relative;
  z-index: 1;
}
.home-shell .podium-tier--first .podium-rank {
  color: var(--gold-light);
  font-size: 2rem;
}
.home-shell .podium-name {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.95rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--bone);
  position: relative;
  z-index: 1;
  word-break: break-word;
}
.home-shell .podium-pts {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 1.5rem;
  color: var(--bone);
  margin-top: 0.5rem;
  font-variant-numeric: tabular-nums;
  position: relative;
  z-index: 1;
}
.home-shell .podium-pts span {
  font-size: 0.6rem;
  letter-spacing: 0.18em;
  margin-left: 0.25rem;
  color: var(--bone-mute);
  font-weight: 500;
}

@media (max-width: 480px) {
  /* Mobile: stack vertically with #1 on top */
  .home-shell .podium {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }
  .home-shell .podium-tier--second,
  .home-shell .podium-tier--third {
    transform: none;
  }
  .home-shell .podium-tier--first { order: -1; }
}
```

- [ ] **Step 2: Visually verify podium**

In post state with seeded enrollments (need ≥3), refresh `/`. Expect 3-tier podium: #1 center (gold border, glow, larger), #2 left (slight depression), #3 right (more depression).

If only 1 enrollment, only #1 renders. If 2, #1 + #2. The template handles partial top-3 gracefully.

Mobile <480px: podium stacks single-column with #1 first.

- [ ] **Step 3: Commit**

```bash
git add static/css/style.css
git commit -m "feat(home): post-state final podium with #1 elevation

3-tier podium with gold border + glow on #1, depression effect on
#2/#3. Stacks single-column below 480px with #1 first."
```

---

## Task 27: Post-state roster recap with champion-row accent [FD]

**Files:**
- Modify: `static/css/style.css` (append `.roster-recap` rules)

**[FD]** Roster recap is undesigned — invoke `/frontend-design:frontend-design`.

- [ ] **Step 1: Append roster recap CSS**

Before the END marker:

```css
/* --- Post-state: roster recap --- */
.home-shell .roster-recap {
  margin: 2rem 0 1.5rem;
  padding: 1.5rem 1.25rem 1.75rem;
  background: linear-gradient(180deg,
    var(--purple-850) 0%,
    var(--purple-950) 100%);
  border: 1px solid rgba(243,239,230,.08);
  border-radius: 14px;
}
.home-shell .roster-recap-head {
  text-align: center;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid rgba(243,239,230,.08);
  margin-bottom: 1.25rem;
}
.home-shell .recap-eyebrow {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.75rem;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--bone-mute);
  margin-bottom: 0.5rem;
}
.home-shell .recap-rank {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 3.2rem;
  line-height: 1;
  background: var(--metal-gold);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.home-shell .recap-rank .hash {
  font-size: 1.6rem;
  -webkit-text-fill-color: var(--gold-light);
}
.home-shell .recap-rank .of {
  font-family: var(--font-news);
  font-style: italic;
  font-size: 1rem;
  -webkit-text-fill-color: var(--bone-mute);
  color: var(--bone-mute);
  margin-left: 0.4rem;
}
.home-shell .recap-sub {
  font-family: var(--font-news);
  font-style: italic;
  font-size: 0.95rem;
  color: var(--bone-mute);
  margin-top: 0.5rem;
}
.home-shell .sec-head--inset {
  padding-top: 0.5rem;
}

.home-shell .roster-recap-rows {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 1.5rem;
}
.home-shell .roster-recap-row {
  display: grid;
  grid-template-columns: 32px 48px 1fr auto auto;
  gap: 0.75rem;
  align-items: center;
  padding: 0.75rem 0.75rem;
  border-bottom: 1px solid rgba(243,239,230,.05);
}
.home-shell .roster-recap-row:last-child { border-bottom: none; }
.home-shell .roster-recap-row--champion {
  background: linear-gradient(90deg,
    rgba(201,162,39,.18) 0%,
    rgba(201,162,39,.05) 100%);
  border-left: 3px solid var(--gold-light);
  margin-left: -3px;
  padding-left: calc(0.75rem - 3px);
}
.home-shell .rr-flag {
  font-size: 1.4rem;
  line-height: 1;
}
.home-shell .rr-code {
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.95rem;
  letter-spacing: 0.06em;
  color: var(--bone);
}
.home-shell .rr-tier {
  font-family: var(--font-news);
  font-style: italic;
  font-size: 0.85rem;
  color: var(--bone-mute);
}
.home-shell .rr-finish {
  font-family: var(--font-teko);
  font-weight: 500;
  font-size: 0.8rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--gold-light);
}
.home-shell .rr-pts {
  font-family: var(--font-teko);
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--bone);
  font-variant-numeric: tabular-nums;
  min-width: 48px;
  text-align: right;
}
.home-shell .roster-recap-cta {
  display: block;
  width: 100%;
  text-align: center;
  padding: 0.85rem 1.5rem;
  background: var(--metal-gold);
  color: var(--purple-950) !important;
  font-family: var(--font-teko);
  font-weight: 600;
  font-size: 0.95rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  text-decoration: none;
  border-radius: 6px;
  transition: transform 0.15s ease;
}
.home-shell .roster-recap-cta:hover {
  transform: translateY(-1px);
  color: var(--purple-950) !important;
}

@media (max-width: 480px) {
  /* Mobile: hide tier name, show only flag/code/finish/pts */
  .home-shell .roster-recap-row {
    grid-template-columns: 32px 48px 1fr auto;
  }
  .home-shell .rr-tier { display: none; }
}
```

- [ ] **Step 2: Visually verify roster recap**

Seed 9 picks for an enrollment + mark some teams with `best_finish`:

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask shell <<'EOF'
from games.worldcup.models import WorldCupTeam, WorldCupPick, WorldCupEnrollment
from extensions import db
enr = WorldCupEnrollment.query.first()
bra = WorldCupTeam.query.filter_by(fifa_code='BRA').first()
if bra:
    bra.best_finish = 'Champion'
    db.session.commit()
# (Existing test setup from Task 15 should have picks already)
EOF
```

Refresh `/` (post state, enrolled). Expect:
- "You finished #N of M" header with metal-gold rank
- Sub-line "X points · climbed N spots" (or just points if no snapshots)
- Roster recap rows for each pick — champion row has gold tint + left border
- "View Full Leaderboard" gold-gradient button at bottom

- [ ] **Step 3: Commit**

```bash
git add static/css/style.css
git commit -m "feat(home): post-state roster recap with champion-row accent

Per-pick row showing flag/code/tier/best-finish/points. Champion's
team row gets gold gradient background + gold left border. Mobile
hides tier name to fit 4-column grid."
```

---

## Task 28: Post-state full verification

**Files:**
- N/A (verification only)

- [ ] **Step 1: Verify post-state scenarios**

With match #104 complete + `WC_FAKE_NOW=2026-07-20T00:00:00Z`:

**Scenario A: Logged in, enrolled with 9 picks (one team being champion)**
- Greet "Court has adjourned" ✓
- Champion banner with flag + name + summary ✓
- Final podium (3-tier) ✓
- Your-roster-recap with champion-row gold accent ✓
- "View Full Leaderboard" button works ✓
- Commish's Note + Dispatches ✓
- Compact game tiles (WC says "COMPLETED") ✓

**Scenario B: Logged in, unenrolled**
- Greet ✓
- Champion banner ✓
- Final podium ✓
- "View the World Cup" CTA in roster recap slot ✓
- Compact game tiles ✓

**Scenario C: Match #104 marked complete but `winner_team_id` is null**
- Champion banner falls back to "Champion Pending" with 🏆 ✓
- Other sections render normally ✓

- [ ] **Step 2: Mobile + reduced-motion check**

iPhone 13 (390x844):
- Champion banner full-bleed ✓
- Podium stacks single-column with #1 first ✓
- Roster recap rows hide tier-name column ✓

`prefers-reduced-motion: reduce`:
- Champion glow animation freezes at static opacity ✓

- [ ] **Step 3: Run test suite**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/ -q
```

Expected: 129 passed.

- [ ] **Step 4: Reset dev DB for next task**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask shell <<'EOF'
from games.worldcup.models import WorldCupMatch
from extensions import db
m = WorldCupMatch.query.filter_by(match_number=104).first()
if m:
    m.is_completed = False
    db.session.commit()
EOF
```

- [ ] **Step 5: Verification milestone (no commit unless bug fixes)**

---

## Task 29: Polish pass — hover, focus, reduced-motion, touch [FD]

**Files:**
- Modify: `static/css/style.css` (append polish overrides at end of HOME section)

**[FD]** Polish microinteractions are exactly where `/frontend-design:frontend-design` shines.

- [ ] **Step 1: Append polish overrides at the end of HOME section**

Before the END marker:

```css
/* --- Polish: focus rings (a11y) --- */
.home-shell a:focus-visible,
.home-shell button:focus-visible {
  outline: 2px solid var(--gold-light);
  outline-offset: 2px;
  border-radius: 4px;
}

/* --- Polish: touch device hover suppression --- */
@media (hover: none) {
  .home-shell .ballot-card:hover,
  .home-shell .cta-card:hover,
  .home-shell .cg:hover,
  .home-shell .join-cta:hover,
  .home-shell .decree-cta:hover,
  .home-shell .roster-recap-cta:hover {
    transform: none;
  }
}

/* --- Polish: subtle gold underline on compact tile hover --- */
.home-shell .cg--active:hover .n {
  text-decoration: underline;
  text-decoration-color: var(--gold-light);
  text-underline-offset: 4px;
}

/* --- Polish: card-style links use the same lift as auth buttons --- */
.home-shell .ballot-card,
.home-shell .cta-card,
.home-shell .cg--active {
  transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}
.home-shell .ballot-card:hover,
.home-shell .cta-card:hover,
.home-shell .cg--active:hover {
  box-shadow: 0 6px 20px rgba(0,0,0,.3);
}

/* --- Polish: prevent layout shift on countdown digit changes --- */
.home-shell .decree-days .d-cell .v {
  display: inline-block;
  min-width: 2.6rem;
  text-align: center;
}

/* --- Polish: print-friendly fallback (just in case) --- */
@media print {
  .home-shell {
    background: white !important;
    color: black !important;
  }
  .home-shell .champion-glow-bg,
  .home-shell .decree::after { display: none; }
}
```

- [ ] **Step 2: Verify polish in dev**

Across all 4 states, in browser:
- Tab through interactive elements: all should show a clear gold focus ring
- Hover over any card: subtle lift + shadow appears
- Touch device (DevTools mobile mode): hover lifts disabled
- Countdown digits change without left/right shifting

- [ ] **Step 3: Commit**

```bash
git add static/css/style.css
git commit -m "feat(home): polish — focus rings, touch hover suppression, layout stability

A11y focus rings on all interactive elements. Touch devices opt out
of hover lifts via @media (hover: none). Countdown digits use
fixed-width cells to prevent layout shift on tick. Print fallback."
```

---

## Task 30: Cross-state full verification

**Files:**
- N/A (verification only)

- [ ] **Step 1: Run automated gates**

**Gate 1 — full test suite:**
```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/ -q
```
Expected: 129 passed (119 prior + 10 new).

**Gate 2 — type checking:**
```bash
venv/bin/pyright
```
Expected: 0 errors.

**Gate 3 — migration round-trip:**
```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db downgrade
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask db upgrade
```
Expected: clean round-trip.

**Gate 4 — snapshot CLI sanity:**
```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks --backfill 7
```
Expected: idempotent, no errors.

- [ ] **Step 2: Run the full Spec B manual visual checklist (15 surfaces)**

Per Spec B section 11b. For each, mark pass/fail in your local notes; you'll paste into the PR description in Task 32.

| # | State | Expected |
|---|---|---|
| 1 | `/` logged-out | Hero, value props (3rd = "Read the Commish's Note"), Join CTA, full game cards, no social-proof block |
| 2 | `/` pre + enrolled + sealed | Greet, ticking countdown, ballot card with 9 flags → `/picks?edit=1`, opening matches, compact tiles, footer voice strip |
| 3 | `/` pre + enrolled + no picks | Same shell + "Seal Your Roster" CTA |
| 4 | `/` pre + unenrolled | Same shell + "Join the World Cup pool" CTA |
| 5 | `/` live + enrolled (`WC_FAKE_NOW=2026-06-15T00:00:00Z`) | Dossier with sparkline, top-3+you leaderboard, recent results with roster-overlap foots, compact tiles |
| 6 | `/` live + unenrolled | Same shell + "View the World Cup" CTA + no you-row |
| 7 | `/` post + enrolled (mock match #104 complete) | Champion banner, podium, roster recap with champion-row gold accent |
| 8 | `/` post + unenrolled | Same shell + "View the World Cup" CTA |
| 9 | Compact game tiles | All 3 logged-in states; WC label state-correct ("ROSTER OPEN"/"SEALED"/"LIVE · #N"/"COMPLETED") |
| 10 | Countdown | Ticks; reloads at zero |
| 11 | Sparkline | 7+ data points renders curve; <2 → "tracking starts"; 0 → block hidden |
| 12 | Mobile (375x667) | All 4 states no horizontal scroll, compact tiles 3-across |
| 13 | Desktop (≥992px) live | Two-column layout activates |
| 14 | Reduced motion | Champion glow + sparkline animations respect setting |
| 15 | Footer voice strip | Renders unchanged across all 4 states |

- [ ] **Step 3: If any item fails, fix inline + commit**

Each fix is its own small commit referencing the failing checklist item:
```bash
git commit -m "fix(home): {description} (checklist item #N)"
```

- [ ] **Step 4: Reset dev DB to a clean pre-state for the PR reviewer**

```bash
ENVIRONMENT=development FLASK_APP=app.py venv/bin/flask shell <<'EOF'
from games.worldcup.models import WorldCupMatch
from extensions import db
m = WorldCupMatch.query.filter_by(match_number=104).first()
if m and m.is_completed:
    m.is_completed = False
    m.winner_team_id = None
    db.session.commit()
    print('Reset match #104')
EOF
```

---

## Task 31: Final pyright + test sweep

**Files:**
- N/A (verification only)

- [ ] **Step 1: Pyright on every modified Python file**

```bash
venv/bin/pyright \
  core/main/routes.py \
  core/main/home_context.py \
  games/worldcup/services/state.py \
  games/worldcup/services/__init__.py \
  games/worldcup/models.py \
  games/worldcup/cli.py \
  games/registry.py \
  tests/test_home_context.py
```

Expected: 0 errors.

- [ ] **Step 2: Full pyright sweep (in case touched something else)**

```bash
venv/bin/pyright
```

Expected: 0 errors across the project.

- [ ] **Step 3: Full pytest with verbose output**

```bash
ENVIRONMENT=testing FLASK_APP=app.py venv/bin/python -m pytest tests/ -v
```

Expected: all tests pass, 10 new in `test_home_context.py`.

- [ ] **Step 4: Code review pass with `pr-review-toolkit`**

Invoke the `pr-review-toolkit:review-pr` skill (or run the included specialists individually). Address any priority-high issues; defer minor style nits to follow-ups.

- [ ] **Step 5: CodeRabbit review**

Invoke `coderabbit:review` for a holistic multi-file analysis. Address actionable items; ignore style noise.

If any fixes land, commit each as a small focused commit and re-run gates 1-3.

---

## Task 32: Open the pull request

**Files:**
- N/A (PR operation)

- [ ] **Step 1: Push the branch**

```bash
cd /Users/bhagstrom/fantasy-platform-ccc-home
git push -u origin redesign/ccc-home
```

- [ ] **Step 2: Open the PR with `gh`**

```bash
gh pr create --title "Spec B — CCC home redesign (4 states + snapshot infra)" --body "$(cat <<'EOF'
## Summary

Implements Spec B: replaces the home page wholesale with four state-aware variants
(logged-out / pre-WC / live-WC / post-WC) on the CCC brand foundation merged in
Spec A, plus a daily snapshot infrastructure powering the live-state dossier
sparkline and week-delta.

- **Spec:** `docs/superpowers/specs/2026-04-28-ccc-home-redesign-design.md`
- **Plan:** `docs/superpowers/plans/2026-04-28-ccc-home-redesign-plan.md`
- **Predecessor:** Spec A (CCC brand foundation, merged as `2859881`)

## Architecture

- Thin shell `index.html` dispatches to one of four `_home_<state>.html` partials
  based on `worldcup_state()` (3-phase helper: pre/live/post)
- Per-state data assembly in `core/main/home_context.py` (4 builders + 1 tagline helper)
- New `WorldCupRankSnapshot` model + `flask worldcup snapshot-ranks` CLI
  + nightly cron entry (already added to the production deployment plan's Task 25)
- New `/* === HOME (CCC) === */` section in `style.css` with ~25 component classes
  scoped under `.home-shell` wrapper

## Manual visual checklist

(Paste the 15-item table from Task 30 Step 2 with pass/fail marks.)

## Verification gates passed

- [x] All 119 prior tests + 10 new = 129 passed
- [x] pyright: 0 errors
- [x] Migration round-trip clean
- [x] Snapshot CLI idempotent
- [x] All 4 states render correctly with `WC_FAKE_NOW` mocking
- [x] Mobile (375x667) and desktop (≥992px) verified across all states
- [x] Reduced-motion respected for champion glow + sparkline animations

## Production deployment notes

The snapshot cron entry is already woven into
`docs/superpowers/plans/2026-04-21-production-deployment.md` Task 25 Step 2.
When Brad resumes the deploy plan after Spec B + Spec C land, the snapshot
job ships as part of normal cron setup. No separate action required at merge.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Return the PR URL to Brad**

`gh pr create` prints the URL — paste it for the user.

- [ ] **Step 4 (post-merge, not in this PR): Update CLAUDE.md and clean up**

Per Spec B section 11e:
1. Run `/claude-md-management:revise-claude-md` to capture session learnings.
2. `git worktree remove ../fantasy-platform-ccc-home` from the main checkout.
3. Add backfill snapshots on production after Task 25 of the deploy plan ships:
   ```bash
   ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks --backfill 7
   ```

---

## Appendix A: Spec ↔ Plan task mapping

| Spec section | Plan task(s) |
|---|---|
| 3a Worktree | Task 1 |
| 3b/3c File layout | Tasks 2-32 (collectively) |
| 4a `worldcup_state()` | Task 4 |
| 4b–4d data assembly + route | Tasks 5-9 |
| 5 Logged-out state | Task 12 |
| 6 Pre-deadline state | Tasks 13-18 |
| 7 Live state | Tasks 19-23 |
| 8 Post state | Tasks 24-28 |
| 9 CSS strategy + tokens | Tasks 11-27 (CSS appended per-task) |
| 10 Snapshot infra | Tasks 2-3 |
| 11 Verification & exit criteria | Tasks 30-32 |
| 13 Implementation guidance | Followed throughout (execution order matches Spec 13a) |

## Appendix B: Frontend-design skill invocation points [FD]

Tasks 24, 25, 26, 27, 29 — all post-state and polish work.
