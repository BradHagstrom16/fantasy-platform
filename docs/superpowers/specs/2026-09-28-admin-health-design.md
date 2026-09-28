# Admin health at a glance (open-items §H) — design

## Context

The platform admin dashboard (`/admin/`, `core/admin/routes.py:36`) shows member and enrollment counts only. Today the only record of whether each timer ran is healthchecks.io and the systemd journal. Neither can tell a `--scheduled` stand-down from real work (the ops-hardening runbook notes this at `:120`), and neither is visible from the site. The dashboard also lists the archived World Cup first, because the game list is hardcoded (`routes.py:41-81`).

Goal: from `/admin/`, see at a glance each job's last run and its result, the Odds API credit balance, and the live games at the top.

**Brad's rulings (2026-09-28):**
- Runs are recorded in a `sync_runs` table, written at the CLI layer. The systemd hook `utils/job_alert.py` is not used, because it has no DB, no exit code, must work when the app is broken, and is import-locked by `tests/test_job_alerts.py:227`.
- The credit balance is the last value a job saw. The page makes no live probe.
- Only the club `ODDS_API_KEY` balance is shown. The edge key is left out.

## Design

### 1. Model: `models/sync_run.py::SyncRun` → table `sync_runs`
Columns:
- `id`
- `job String(40)`: the systemd unit name, e.g. `cfb-scores` or `club-remind`. This is the same slug the healthchecks checks use.
- `started_at`, `finished_at`: `DateTime(timezone=True)`, same convention as `models/content.py`.
- `outcome String(16)`: one of `running | ok | idle | stood_down | error`.
- `exit_code Integer`
- `summary String(500)`: the job's first line, truncated.
- `odds_credits_remaining Integer` (nullable)
- `via String(10)`: `systemd` if `INVOCATION_ID` is set in the environment, otherwise `shell`.

There is an index on `(job, started_at)`. `SyncRun` is re-exported in `models/__init__.py`, and there is one Alembic migration (reviewed with the `migration-reviewer` agent). Rows are never pruned: about 50 a day, a few MB a year.

### 2. Recorder: `utils/sync_runs.py`
- **`JOBS`** is an ordered dict from job key to a display label, e.g. `'cfb-scores': 'Survivor scores'`. It is the single list of recordable jobs: the ten live units, the six golf units, and `docket-setup` for hand runs. World Cup is excluded; its jobs are off for good.
- **`record_run(job)`** is a context manager:
  - **On entry:** it inserts a `running` row and commits at once. A killed or hung run (`TimeoutStartSec`) then stays visible as "running since…".
  - **On exit:** it updates the row with `finished_at`, the exit code, the outcome and the summary.
  - **Separate connection:** it writes through a connection of its own (`db.engine.begin()`, Core on `SyncRun.__table__`), so the job's own commits and rollbacks can never take the run row with them.
  - **Outcome rules:**
    - An uncaught exception records `error` with `ExcClass: message`, then re-raises.
    - `SystemExit(n)` records the exit code, then re-raises.
    - Otherwise the outcome is whatever the CLI set on the yielded handle (`run.outcome` / `run.summary`). The default is `ok` for exit 0 and `error` for anything else.
  - **Never fails the job:** a failed recorder write logs a warning and leaves the job's outcome and exit code alone. The DB is a real boundary; for example, a timer can fire between `git pull` and `flask db upgrade` in `deploy.sh`.
- **`note_credits(n)`** keeps the lowest `x-requests-remaining` seen during the current run, in a `ContextVar`. It depends on nothing, so the model import stays inside the writer and nothing becomes circular.

### 3. Credit capture: `utils/odds_api.py::_log_credits`
When the header parses as an int, it also calls `note_credits(int)`. Every Odds API call from a recorded job then saves the balance on that run's row, including the free `/sports` probe in `games/gameday.py`. Nothing else changes. `flask docket edge` is not wrapped, so the edge key's balance never reaches the table.

### 4. Wiring the CLIs
Each scheduled command body goes inside `with record_run(key) as run:` and sets `run.outcome` where the job already knows it. **Exit codes do not change.**

| CLI | Key | Outcome source |
|---|---|---|
| `games/cfb/cli.py::_run_mode` (not `status`) | `cfb-{mode}` | result `status`: `error` → `error`, `skipped` → `idle`, else `ok`. For `scores`, a STUCK week or a failed ADR-062 open retry → `error` and a successful retry → `ok`, whatever the status says; that line leads the summary. The CLI still exits 0; the row tells the truth. |
| `games/docket/cli.py` sync (not `status`) | `docket-{mode}` | `_no_work` under `--scheduled` → `stood_down`; `_fail` / `_check_sync_status` → `error` through the exit code |
| `games/gameday_cli.py` | `scores-gameday` | summary `idle` → `idle`, `floor` → `stood_down`, `error` → `error` |
| `games/club_desk_cli.py` desk / paper (not `--dry-run`) | `club-remind` / `club-paper` | `run.exit_code`, plus the desk's own stand-down status |
| `games/golf/cli.py::sync-run` | `golf-{unit}`, through an explicit mode→unit map (`live-with-wd` → `golf-live-wd`) | `exit_code` |

Read-only modes (`status`, `--dry-run`, `edge`) are never recorded.

### 5. Dashboard (`core/admin/routes.py` + `admin/dashboard.html`)
- **Reorder** the games list to CFB, Docket, Golf, then World Cup.
- **Credits in the masthead:** "N Odds API credits left · as of {format_ct}". The value is the newest non-null `odds_credits_remaining`. If there is none, the line is left out.
- **New Jobs section:** one row for each `JOBS` key that has at least one run, in `JOBS` order. So held golf jobs stay hidden until they first run. Each row shows:
  - the label
  - the latest run's time in CT (`utils.time.format_ct`), with its duration
  - the outcome as a word, not colour alone
  - the summary line
  - "by hand" when `via == 'shell'`
  - the most recent `error` within 7 days, if one exists and the latest run is not itself the error
- **Query:** one query for the latest row per job (a `max(id)` group-by subquery), plus one for recent errors.
- **UI work goes through the `impeccable` skill** with the top-level `DESIGN.md` (platform admin is not a game room). It reuses the existing `.admin-league-row` primitives and adds no eyebrow above a heading.

### 6. Tests (new `tests/test_sync_runs.py`, `app`/`client` from conftest)
- **Recorder:** `ok`, CLI-set outcome, exception → `error` and re-raise, `SystemExit(1)` → `exit_code=1`, the `running` row exists mid-run, the job's `db.session.rollback()` does not remove the row, a failed recorder write leaves the job's result alone, and `via` follows `INVOCATION_ID`.
- **Credits:** two `_log_credits` calls inside a run save the lower value; calls outside a run are ignored.
- **Lock: every scheduled unit records under its own name.** Parse every non-worldcup `deploy/*.service` ExecStart (same selection as `tests/test_job_alerts.py:27`), map it through the CLI's key logic, and assert the result equals the unit name and is in `JOBS`. A new timer without a recorder fails CI.
- **Wiring per CLI:** use CliRunner with the service function patched (the pattern in `tests/test_gameday_pass.py`), and assert the row's job and outcome. Status and dry-run modes write nothing.
- **Dashboard** (extends `tests/test_admin_leagues.py`): World Cup renders after CFB and Docket; the credits line shows; a job row shows its outcome; a job with no runs is absent.
- **Suites:** the existing timer and job-alert suites stay green with no unit-file edits.

## Execution order (one PR)
1. Model, migration, recorder, `note_credits` hook, and recorder tests.
2. Wire the five CLIs and add the lock test.
3. Dashboard reorder, credits, and Jobs section (impeccable), plus dashboard tests.
4. CLAUDE.md: one bullet under Platform integration or Production ops (a new scheduled command must record through `record_run`, citing the test lock). Tick §H in `docs/open-items.md`.


## Verification
- Run `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -n auto --dist loadfile` on both SQLite and `TEST_DATABASE_URL=postgresql:///ccc_test`, then `venv/bin/ruff check .`.
- Check the migration against an empty database: `flask db upgrade` then `flask db check` on `ccc_migrations_test`.
- Local smoke on `ccc_local`:
  - Run `flask cfb sync --mode autopick` (no API call) and `flask scores game-day` (idle, no API call).
  - Load `/admin/` on port 5099, check it through `/browse`, and screenshot the Jobs section and the new order.
- After deploy: the next hourly `club-remind` firing should put a `club-remind … via systemd` row on the prod dashboard. The first `docket-scores` or gameday call should fill in the credits line.
