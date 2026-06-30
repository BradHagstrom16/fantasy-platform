# PK Score Display + UX Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate penalty shootout goals from regulation/ET goals in storage and display (FIFA-style `1 (3) – 1 (4)`), and add clickable links to the top-3 leaderboard names on the lounge home page.

**Architecture:** Add `home_pen`/`away_pen` columns to `WorldCupMatch`, update the sync service to read `extraTime` score (not `fullTime`) for PK matches and capture the PK tally, propagate those fields through `process_match_result()`, and update all score-display templates. Top-3 links are a standalone template + CSS change.

**Tech Stack:** Flask, SQLAlchemy 2.0, Flask-Migrate (Alembic), Jinja2, pytest

## Global Constraints

- Run tests with: `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q`
- Migrations: Flask-Migrate only — `FLASK_APP=app.py venv/bin/flask db migrate -m "..."` then `flask db upgrade`; never raw SQL
- Never call `datetime.now()` directly in application code; use `games/worldcup/services/state.now_utc()`
- `home_pen` / `away_pen` must be `nullable=True` with no default — non-PK matches leave them `NULL`
- Display guard: only render PK format when `match.penalties and match.home_pen is not none`
- Commit message style: `feat:` for features, `fix:` for bug fixes, `test:` for test-only commits

---

### Task 1: Add `home_pen` / `away_pen` columns to `WorldCupMatch`

**Files:**
- Modify: `games/worldcup/models.py:124-129`
- Create: `migrations/versions/<hash>_add_wc_match_pen_cols.py` (generated)

**Interfaces:**
- Produces: `WorldCupMatch.home_pen` (Integer, nullable) and `WorldCupMatch.away_pen` (Integer, nullable) — consumed by Tasks 2, 3, 4, and 5

- [ ] **Step 1: Add the two columns to the model**

In `games/worldcup/models.py`, after line 125 (`away_score = db.Column(db.Integer, nullable=True)`):

```python
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    home_pen = db.Column(db.Integer, nullable=True)   # penalty shootout tally only
    away_pen = db.Column(db.Integer, nullable=True)
```

- [ ] **Step 2: Generate the migration**

```bash
FLASK_APP=app.py venv/bin/flask db migrate -m "add home_pen away_pen to worldcup_match"
```

Open the generated file in `migrations/versions/`. Verify it adds exactly two nullable integer columns (`home_pen`, `away_pen`) with `nullable=True` and no server default. The upgrade should look like:

```python
op.add_column('worldcup_match', sa.Column('home_pen', sa.Integer(), nullable=True))
op.add_column('worldcup_match', sa.Column('away_pen', sa.Integer(), nullable=True))
```

The downgrade should drop both columns.

- [ ] **Step 3: Apply the migration**

```bash
FLASK_APP=app.py venv/bin/flask db upgrade
```

Expected: `Running upgrade ... -> <hash>, add home_pen away_pen to worldcup_match`

- [ ] **Step 4: Smoke test — columns exist**

```bash
ENVIRONMENT=testing venv/bin/python -c "
from app import create_app
from extensions import db
app = create_app('testing')
with app.app_context():
    db.create_all()
    from games.worldcup.models import WorldCupMatch
    cols = [c.name for c in WorldCupMatch.__table__.columns]
    assert 'home_pen' in cols, f'home_pen missing; cols={cols}'
    assert 'away_pen' in cols, f'away_pen missing; cols={cols}'
    print('OK — home_pen and away_pen present')
"
```

- [ ] **Step 5: Commit**

```bash
git add games/worldcup/models.py migrations/
git commit -m "feat: add home_pen/away_pen columns to WorldCupMatch for PK tally storage"
```

---

### Task 2: Update `process_match_result()` to accept and store pen columns

**Files:**
- Modify: `games/worldcup/services/scoring.py:275-305`
- Modify: `tests/test_worldcup_scoring.py`

**Interfaces:**
- Consumes: `WorldCupMatch.home_pen`, `WorldCupMatch.away_pen` (from Task 1)
- Produces: `process_match_result(match_id, home_score, away_score, winner_fifa_code, is_draw=False, extra_time=False, penalties=False, home_pen=None, away_pen=None)` — called by Task 3 (sync) and Task 4 (CLI repair)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_worldcup_scoring.py`, inside the existing `class TestKnockoutRounds` block (after `test_knockout_with_penalties`):

```python
    def test_pk_match_stores_pen_columns(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'PKA', 'PK Alpha', 4, 4.0)
            t2 = _make_team(db.session, 'PKB', 'PK Beta', 5, 7.0)
            match = _make_match(db.session, 201, 'R32', t1, t2)
            db.session.commit()

            process_match_result(
                match.id, 1, 1, 'PKA',
                extra_time=True, penalties=True,
                home_pen=3, away_pen=4,
            )

            db.session.refresh(match)
            assert match.home_score == 1
            assert match.away_score == 1
            assert match.home_pen == 3
            assert match.away_pen == 4

    def test_non_pk_match_pen_columns_null(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'REG1', 'Reg One', 4, 4.0)
            t2 = _make_team(db.session, 'REG2', 'Reg Two', 5, 7.0)
            match = _make_match(db.session, 202, 'R32', t1, t2)
            db.session.commit()

            process_match_result(match.id, 2, 0, 'REG1')

            db.session.refresh(match)
            assert match.home_pen is None
            assert match.away_pen is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_scoring.py::TestKnockoutRounds::test_pk_match_stores_pen_columns tests/test_worldcup_scoring.py::TestKnockoutRounds::test_non_pk_match_pen_columns_null -v
```

Expected: FAIL — `process_match_result() got an unexpected keyword argument 'home_pen'`

- [ ] **Step 3: Update `process_match_result()` signature and body**

In `games/worldcup/services/scoring.py`, change the function signature (line 275) and add the two store lines after `match.penalties = penalties` (line 304):

```python
def process_match_result(
    match_id: int,
    home_score: int,
    away_score: int,
    winner_fifa_code: str | None,
    is_draw: bool = False,
    extra_time: bool = False,
    penalties: bool = False,
    home_pen: int | None = None,
    away_pen: int | None = None,
) -> dict:
```

And in the body, after `match.penalties = penalties`:

```python
    match.home_pen = home_pen
    match.away_pen = away_pen
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_scoring.py::TestKnockoutRounds::test_pk_match_stores_pen_columns tests/test_worldcup_scoring.py::TestKnockoutRounds::test_non_pk_match_pen_columns_null -v
```

Expected: PASS

- [ ] **Step 5: Run full scoring suite to check no regressions**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_scoring.py -q
```

Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/services/scoring.py tests/test_worldcup_scoring.py
git commit -m "feat: process_match_result accepts home_pen/away_pen for PK tally storage"
```

---

### Task 3: Update `sync_scores()` to read ET score and PK tally for PK matches

**Files:**
- Modify: `games/worldcup/services/sync.py:248-270`

**Interfaces:**
- Consumes: `process_match_result(..., home_pen=, away_pen=)` from Task 2
- Produces: For `PENALTY_SHOOTOUT` duration fixtures: `home_score`/`away_score` = ET score; `home_pen`/`away_pen` = penalty tally

- [ ] **Step 1: Update `sync_scores()` knockout branch**

In `games/worldcup/services/sync.py`, replace lines 248-270 (the block from `ft = ...` through the `process_match_result(...)` call for knockout matches):

```python
        ft = (f.get('score') or {}).get('fullTime') or {}
        home, away = ft.get('home'), ft.get('away')
        if home is None or away is None:
            continue

        if shell.stage == 'group':
            is_draw = (f['score'].get('winner') == 'DRAW')
            res = process_match_result(shell.id, home, away, None, is_draw=is_draw)
        else:
            # Knockout requires assigned teams (bracket confirmed by admin first).
            if not shell.home_team_id or not shell.away_team_id:
                skipped_unassigned += 1
                continue
            duration = f['score'].get('duration', 'REGULAR')
            winner_side = f['score'].get('winner')
            api_winner = f.get('homeTeam') if winner_side == 'HOME_TEAM' else f.get('awayTeam')
            winner_fifa = _fifa_for_tla((api_winner or {}).get('tla'))

            home_pen, away_pen = None, None
            if duration == 'PENALTY_SHOOTOUT':
                # Use extraTime score (pre-PK) for home_score/away_score.
                # fullTime from the API bundles PK goals into the total.
                et = (f.get('score') or {}).get('extraTime') or {}
                pen = (f.get('score') or {}).get('penalties') or {}
                et_home, et_away = et.get('home'), et.get('away')
                if et_home is not None and et_away is not None:
                    home, away = et_home, et_away
                home_pen = pen.get('home')
                away_pen = pen.get('away')

            res = process_match_result(
                shell.id, home, away, winner_fifa,
                extra_time=duration in ('EXTRA_TIME', 'PENALTY_SHOOTOUT'),
                penalties=duration == 'PENALTY_SHOOTOUT',
                home_pen=home_pen,
                away_pen=away_pen,
            )
```

- [ ] **Step 2: Run full test suite to verify no regressions**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: all tests pass (sync_scores has no unit test today; regression protection is via the scoring tests and integration smoke).

- [ ] **Step 3: Commit**

```bash
git add games/worldcup/services/sync.py
git commit -m "fix: sync reads extraTime score (not fullTime) for PK matches, captures pen tally"
```

---

### Task 4: Add `flask worldcup repair-pk-scores` CLI command

Corrects already-completed PK matches whose `home_pen` is still `NULL` — i.e., matches that were synced before this fix. Idempotent: skips matches where `home_pen` is already populated.

**Files:**
- Modify: `games/worldcup/cli.py` (add command before `register_worldcup_cli`)

**Interfaces:**
- Consumes: `WorldCupMatch.home_pen`, `WorldCupMatch.penalties`, `WorldCupMatch.api_fixture_id` (Task 1); `_api_get`, `FINISHED_STATUSES` from `sync.py`

- [ ] **Step 1: Add the command to `cli.py`**

In `games/worldcup/cli.py`, insert before the `register_worldcup_cli` function:

```python
@worldcup_cli.command('repair-pk-scores')
def repair_pk_scores():
    """Correct already-completed PK match scores (ET score + pen tally).

    sync_scores() skips completed shells; this command re-fetches those
    matches from the API and writes the ET score to home_score/away_score
    and the penalty tally to home_pen/away_pen. Idempotent — skips matches
    where home_pen is already set.
    """
    from games.worldcup.services.sync import _api_get, FINISHED_STATUSES

    data = _api_get('competitions/WC/matches')

    # Only target completed PK matches still missing their pen tally.
    candidates = {
        m.api_fixture_id: m
        for m in WorldCupMatch.query.filter(
            WorldCupMatch.api_fixture_id.isnot(None),
            WorldCupMatch.is_completed.is_(True),
            WorldCupMatch.penalties.is_(True),
            WorldCupMatch.home_pen.is_(None),
        ).all()
    }

    if not candidates:
        click.echo('No PK matches need repair.')
        return

    fixed, failed = [], []
    for f in data.get('matches', []):
        if f.get('status') not in FINISHED_STATUSES:
            continue
        shell = candidates.get(f.get('id'))
        if not shell:
            continue

        score = f.get('score') or {}
        if score.get('duration') != 'PENALTY_SHOOTOUT':
            continue

        et = score.get('extraTime') or {}
        pen = score.get('penalties') or {}
        et_home, et_away = et.get('home'), et.get('away')
        pen_home, pen_away = pen.get('home'), pen.get('away')

        if None in (et_home, et_away, pen_home, pen_away):
            failed.append(shell.match_number)
            continue

        shell.home_score = et_home
        shell.away_score = et_away
        shell.home_pen = pen_home
        shell.away_pen = pen_away
        fixed.append(shell.match_number)

    db.session.commit()
    click.echo(f'Fixed {len(fixed)} PK match(es): match numbers {fixed}')
    if failed:
        click.echo(f'WARNING — API missing ET/pen data for: {failed}')
```

- [ ] **Step 2: Verify the command is importable**

```bash
FLASK_APP=app.py venv/bin/flask worldcup --help
```

Expected: `repair-pk-scores` appears in the command list.

- [ ] **Step 3: Run full test suite**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add games/worldcup/cli.py
git commit -m "feat: add repair-pk-scores CLI command to correct pre-fix PK match records"
```

---

### Task 5: Update all score-display templates to render PK format

Five display sites. The conditional in every case:

```
{% if match.penalties and match.home_pen is not none %}
```

When true → show `score (pen_home)` style. When false → show raw score as today.

**Files:**
- Modify: `core/main/templates/main/_recent_results.html:32,40,95,97`
- Modify: `games/worldcup/templates/worldcup/_home_live.html:129`
- Modify: `games/worldcup/templates/worldcup/schedule.html:139,146`
- Modify: `games/worldcup/templates/worldcup/admin/dashboard.html:175`
- Test: `tests/test_worldcup_admin.py`

**Interfaces:**
- Consumes: `WorldCupMatch.home_pen`, `WorldCupMatch.away_pen`, `WorldCupMatch.penalties` (Task 1)

- [ ] **Step 1: Write a failing template test**

Add to `tests/test_worldcup_admin.py` (near `test_admin_dashboard_lists_completed_matches`):

```python
def test_admin_dashboard_shows_pk_format(client, app):
    """Completed PK match renders as '1 (3)–1 (4)' not '5–6'."""
    admin_auth_id = _make_admin_user(app)
    with app.app_context():
        t1 = WorldCupTeam(
            fifa_code='TSA', name='Team SA', display_name='Team SA',
            tier=4, multiplier=4.0, confederation='T', group_letter='A',
        )
        t2 = WorldCupTeam(
            fifa_code='TSB', name='Team SB', display_name='Team SB',
            tier=5, multiplier=7.0, confederation='T', group_letter='A',
        )
        db.session.add_all([t1, t2])
        db.session.flush()
        m = WorldCupMatch(
            match_number=901, stage='R32',
            home_team_id=t1.id, away_team_id=t2.id,
            home_score=1, away_score=1,
            home_pen=3, away_pen=4,
            is_completed=True, penalties=True, extra_time=True,
            winner_team_id=t1.id,
        )
        db.session.add(m)
        db.session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = admin_auth_id
        sess['_fresh'] = True

    resp = client.get('/worldcup/admin/')
    assert resp.status_code == 200
    body = resp.data.decode()
    assert '1 (3)' in body
    assert '1 (4)' in body
    # Must NOT show the PK-inflated totals as bare scores
    assert '5&ndash;6' not in body
    assert '5–6' not in body
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_admin.py::test_admin_dashboard_shows_pk_format -v
```

Expected: FAIL — body does not contain `(3)`.

- [ ] **Step 3: Update `admin/dashboard.html` line 175**

Replace:
```html
<strong>{{ match.home_score }}&ndash;{{ match.away_score }}</strong>
```

With:
```html
<strong>{{ match.home_score }}{% if match.penalties and match.home_pen is not none %} ({{ match.home_pen }}){% endif %}&ndash;{{ match.away_score }}{% if match.penalties and match.away_pen is not none %} ({{ match.away_pen }}){% endif %}</strong>
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_admin.py::test_admin_dashboard_shows_pk_format -v
```

Expected: PASS

- [ ] **Step 5: Update lounge `_recent_results.html` — roster match card scores**

In `core/main/templates/main/_recent_results.html`:

Line 32 — roster card home score. Replace:
```html
<div class="m-score">{{ match.home_score if match.home_score is not none else '·' }}</div>
```
With:
```html
<div class="m-score">{{ match.home_score if match.home_score is not none else '·' }}{% if match.penalties and match.home_pen is not none %} ({{ match.home_pen }}){% endif %}</div>
```

Line 40 — roster card away score. Replace:
```html
<div class="m-score">{{ match.away_score if match.away_score is not none else '·' }}</div>
```
With:
```html
<div class="m-score">{{ match.away_score if match.away_score is not none else '·' }}{% if match.penalties and match.away_pen is not none %} ({{ match.away_pen }}){% endif %}</div>
```

Lines 95 and 97 — compact strip scores. Replace:
```html
<span class="ra-score">{{ match.home_score if match.home_score is not none else '·' }}</span>
<span class="ra-sep">vs</span>
<span class="ra-score">{{ match.away_score if match.away_score is not none else '·' }}</span>
```
With:
```html
<span class="ra-score">{{ match.home_score if match.home_score is not none else '·' }}{% if match.penalties and match.home_pen is not none %} ({{ match.home_pen }}){% endif %}</span>
<span class="ra-sep">vs</span>
<span class="ra-score">{{ match.away_score if match.away_score is not none else '·' }}{% if match.penalties and match.away_pen is not none %} ({{ match.away_pen }}){% endif %}</span>
```

- [ ] **Step 6: Update WC hub results strip `_home_live.html` line 129**

Replace:
```html
<span class="wc-result-score wc-numeral" aria-label="Score">{{ m.home_score }}&ndash;{{ m.away_score }}</span>
```
With:
```html
<span class="wc-result-score wc-numeral" aria-label="Score">{{ m.home_score }}{% if m.penalties and m.home_pen is not none %} ({{ m.home_pen }}){% endif %}&ndash;{{ m.away_score }}{% if m.penalties and m.away_pen is not none %} ({{ m.away_pen }}){% endif %}</span>
```

- [ ] **Step 7: Update `schedule.html` KO bracket scores (lines 139 and 146)**

Line 139 — home team KO score. Replace:
```html
<span class="wc-ko-score wc-numeral">{% if m.is_completed %}{{ m.home_score }}{% endif %}</span>
```
With:
```html
<span class="wc-ko-score wc-numeral">{% if m.is_completed %}{{ m.home_score }}{% if m.penalties and m.home_pen is not none %} ({{ m.home_pen }}){% endif %}{% endif %}</span>
```

Line 146 — away team KO score. Replace:
```html
<span class="wc-ko-score wc-numeral">{% if m.is_completed %}{{ m.away_score }}{% endif %}</span>
```
With:
```html
<span class="wc-ko-score wc-numeral">{% if m.is_completed %}{{ m.away_score }}{% if m.penalties and m.away_pen is not none %} ({{ m.away_pen }}){% endif %}{% endif %}</span>
```

- [ ] **Step 8: Run full test suite**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add core/main/templates/main/_recent_results.html \
        games/worldcup/templates/worldcup/_home_live.html \
        games/worldcup/templates/worldcup/schedule.html \
        games/worldcup/templates/worldcup/admin/dashboard.html \
        tests/test_worldcup_admin.py
git commit -m "fix: display PK scores in FIFA format (ET score + pen tally) across all templates"
```

---

### Task 6: Add clickable links to top-3 leaderboard names on lounge home page

**Files:**
- Modify: `core/main/templates/main/_home_live.html:55-61`
- Modify: `static/css/style.css` (lounge rolls section)

**Interfaces:**
- Consumes: `row.enrollment.id` (already in context via `top_3_plus_you`); `worldcup.player_detail` route (existing, takes `enrollment_id`)

- [ ] **Step 1: Update `_home_live.html` to wrap display name in anchor**

In `core/main/templates/main/_home_live.html`, find the `.roll-name` div (around line 57-61):

```html
          <div class="roll-name">
            {{ row.enrollment.user.get_avatar() }} {{ row.enrollment.get_display_name() }}
            {% if row.is_you %}<span class="roll-you-chip">YOU</span>{% endif %}
          </div>
```

Replace with:

```html
          <div class="roll-name">
            {{ row.enrollment.user.get_avatar() }}<a href="{{ url_for('worldcup.player_detail', enrollment_id=row.enrollment.id) }}" class="roll-name-link">{{ row.enrollment.get_display_name() }}</a>
            {% if row.is_you %}<span class="roll-you-chip">YOU</span>{% endif %}
          </div>
```

- [ ] **Step 2: Add `.roll-name-link` CSS**

In `static/css/style.css`, find the lounge rolls section (search for `.roll-name`). Add after the `.roll-name` rule:

```css
.roll-name-link {
    color: inherit;
    text-decoration: none;
}
.roll-name-link:hover,
.roll-name-link:focus-visible {
    text-decoration: underline;
}
```

- [ ] **Step 3: Write a test**

Append at the end of `tests/test_worldcup_admin.py` (which already has `_make_admin_user` and all necessary imports):

```python
def test_player_detail_route_accessible_to_admin(client, app):
    """player_detail at /worldcup/leaderboard/<id> returns 200 for an admin."""
    admin_auth_id = _make_admin_user(app)
    with app.app_context():
        from models.user import User
        user = User.query.filter_by(is_admin=True).first()
        enrollment = WorldCupEnrollment(
            user_id=user.id,
            season_year=2026,
            picks_submitted=False,
        )
        db.session.add(enrollment)
        db.session.commit()
        eid = enrollment.id

    with client.session_transaction() as sess:
        sess['_user_id'] = admin_auth_id
        sess['_fresh'] = True

    resp = client.get(f'/worldcup/leaderboard/{eid}')
    assert resp.status_code == 200
```

- [ ] **Step 4: Run the test**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_admin.py::test_player_detail_route_accessible_to_admin -v
```

Expected: PASS (the route exists; this is a sanity check that the `player_detail` URL resolves correctly).

- [ ] **Step 5: Run full test suite**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add core/main/templates/main/_home_live.html static/css/style.css tests/test_worldcup_admin.py
git commit -m "feat: top-3 leaderboard names on lounge home link to player detail page"
```

---

## Post-Implementation Checklist

- [ ] Run the full test suite one final time: `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q`
- [ ] Start dev server and visually verify a completed PK match (requires `repair-pk-scores` to have run, or manually set `home_pen`/`away_pen` on a local test match via `flask shell`)
- [ ] Verify top-3 names are clickable in the browser and route to the correct player detail page
- [ ] Verify non-PK matches still display normally (no parentheses)
- [ ] On prod after deploy: run `flask worldcup repair-pk-scores` to correct existing PK match records
