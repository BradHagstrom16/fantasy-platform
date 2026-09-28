# The club's permanent record + season scoping (open-items §E) — design

**Date:** 2026-09-28 · **Status:** approved (Brad, 2026-09-28) · **Ships as:** four PRs (the Record's data, the `/records` page, CFB season scoping, Docket season scoping) · **Supersedes:** ADR-053 (the champion constant) and two rulings of `2026-07-30-cfb-2025-history-ledger-design.md` (no user linking; a provenance line with no link)

## Context

Open-items §E names four gaps: the reigning champion is a hand-typed username constant (`models/user.py:98`, ADR-053); there is no `/records` page; the 26 free-text 2025 CFB names link to no member account; and below the enrollment row nothing carries a season (`CfbWeek`, `CfbPick`, `DocketWeek`, `DocketPick`), so 2027 cannot sit beside 2026.

What exploration established:
- No game stores its champion. WC (`games/worldcup/services/lounge.py:574 archive_summary`), CFB (`games/cfb/services/lounge.py:828 _context_post` over `get_official_standings`) and the Docket (`games/docket/services/season_pass.py:230 season_ledger`, `.season_complete`, `.leader`) recompute the winner from live standings on every request.
- 2025 CFB is a frozen JSON ledger (`games/cfb/data/season_2025.json`, 26 names, no user link). `tests/test_cfb_history.py::test_no_forbidden_keys` forbids `user_id`/`username` in that file and ADR-057 keeps it frozen, so links live in a separate file.
- Golf is the season-scoping template (`season_year` on `GolfTournament`, picks scoped through it). CFB and Docket collide across seasons only on the unique `week_number` of both week tables (created unnamed) and on `cfb_team` (row presence = this season's pool; `CfbPick.team_id` FKs it). Silent traps: `get_used_team_ids` and the cumulative spread are lifetime queries; the next week number is `max+1` over the whole table.
- ~116 unscoped week/pick query sites (CFB ~78, Docket ~38) plus ~26 outcome/result sites. Nearly every test week goes through `tests/_cfb_fixtures.py::make_week` / `tests/_docket_fixtures.py::make_week`.
- A cross-game page belongs in `core/` in the Tribune's shape (`core/tribune/`: light bone reading room; blueprint + routes + templates; registered in `app.py:67-85`; dropdown link `templates/base.html:105-108`). Core reads platform content through `models/` and `games.registry`, never a game module (the hijack/seam locks in `tests/test_registry_seam.py`, `tests/test_docket_lounge_strip.py:186-230`).
- The registry already imports each game's `services.lounge` at load time, so a per-game `services.records` wired the same way adds no cycle. `test_registry_seam.py` does not enumerate dataclass fields; a new defaulted field breaks no mock.
- No test locks the tail of the Tribune CSS section; new sections are appended at the end of `style.css`.
- The test `app` fixture holds one app context for the whole test, so a `flask.g` cache persists across requests inside a test and must be cleared by its writer.
- PRODUCT.md principle 5: "A season is a record, not a session. Completed seasons stay reachable with their real data intact."

**Brad's rulings (2026-09-28):** season column, not archive-and-reseed · any game's reigning champion wears the trophy (the admin crown still wins) · everything ships now as a PR sequence · `/records` is public.

**Decisions taken with the rulings:** the page is "The Record" at `core/records/` → `/records`, in the Tribune's light register; the table lives in `models/records.py`; each room keeps its own archive and `/records` indexes them; the lounge is untouched; golf's seam stays `None` until Phase U7.

---

## Design

### D1. `models/records.py::SeasonFinish` → table `season_finishes`
Columns (conventions of `models/content.py`: commented columns, `DateTime(timezone=True)` + `default=lambda: datetime.now(UTC)`):
`id` · `game String(20)` (registry slug) · `season_year Integer` · `user_id` FK `users.id` nullable, indexed (NULL = never linked) · `name String(80)` (the name as the season recorded it; frozen) · `place Integer` (competition rank, ties share) · `outcome String(30)` nullable (`champion` / `survived` / `eliminated` for CFB; NULL elsewhere) · `detail String(200)` nullable · `field_size Integer` · `closed_at`.
`UniqueConstraint('game','season_year','name', name='uq_season_finish_game_year_name')`, `Index('ix_season_finish_game_year', 'game','season_year')`, `user = db.relationship('User')`.

Module-level, in the same file: `FinishDraft` frozen dataclass (`user_id, name, place, outcome, detail`); `SeasonNotClosed`, `SeasonAlreadyOnRecord`; `seasons_on_record()`, `finishes_for(game, year)`, `champions()`, `reigning_champion_user_ids()`, `record_season(game, year, drafts, *, force=False)` (refuses existing rows unless `force`, which deletes and rewrites in one transaction; `field_size = len(drafts)`; commits; clears the `g` cache). Re-export in `models/__init__.py`; one migration chained on `cac4d3e60af5`.

### D2. The reigning champion is derived
`reigning_champion_user_ids()` fetches every `place == 1` row, reduces in Python to each game's greatest `season_year`, returns the linked `user_id`s as a frozenset cached on `flask.g` for the app context (one query per request however many rows call `get_avatar()`). `User.is_reigning_champion` → `self.id in reigning_champion_user_ids()`, imported lazily inside the property (no cycle; a transient user with `id=None` is simply not a member of the set). Delete `REIGNING_CHAMPION_USERNAME`. Copy becomes game-neutral: "As a reigning club champion, your avatar is the trophy this season." (`core/auth/templates/auth/profile.html:51-60`, comments at `models/user.py:92`, `core/auth/routes.py:284`). cubbies22 keeps the trophy through the 2025 CFB row until CFB 2026 closes; then the 2026 winner and the Docket 2026 winner both wear it.

### D3. Registry seam + per-game builders
`GameRegistryEntry.season_finishes: Callable[[int], list[FinishDraft]] | None = None` (comment in the shape of `join_open`). Each game implements `games/<slug>/services/records.py::season_finishes(season_year)` and raises `SeasonNotClosed` when the season is not final:
- **CFB:** `season_year == 2025` → `get_season_2025()` + the link map `games/cfb/data/season_2025_links.json` (`{"Fourth & Pine": "cubbies22", ...}`, usernames resolved through `func.lower(User.username) == normalize_identifier(v)`; a miss raises and nothing commits). Otherwise require the configured season and `cfb_lounge_state() == 'post'`. Survivors take `get_official_standings` ranks (`champion` for rank 1, `survived` for others in a tiebreak finish); eliminated players rank after every survivor by out-week only (later out = better, same week shares a place), out week from the `CfbWeekOutcome` row with `eliminated_this_week`. Detail: `"2 lives · spread -163.5"` / `"Out Week 16 · spread -144.5"`.
- **WC:** require `SEASON_YEAR` and `worldcup_state() == 'post'`; enrollments by `total_score desc, id asc` (the `archive_summary` query shape), competition rank, detail `"487.0 pts"`. One new read-only file, no edit to any existing WC module; recorded in `docs/worldcup-archive-invariants.md` as the second sanctioned post-archive addition.
- **Docket:** `season_ledger(season_year)`; `SeasonNotClosed` unless `.season_complete`; `place = row.standing.rank`, detail formatted the way `docket/ledger.html` prints points and wins (reuse its formatter, never a second one).
- **Golf:** `None`.

### D4. CLI `flask records` (`core/records/cli.py`, `AppGroup`, registered in `app.py` after `register_tribune_cli`)
`close GAME YEAR [--force]` (`GAME` a `click.Choice` of registry slugs; exits 1 on a `None` seam, `SeasonNotClosed`, or existing rows without `--force`; prints the board and every unlinked name so the link map can be extended and re-run with `--force`). `show [GAME] [YEAR]` read-only. Hand-run only, never a timer, so no `record_run`. Help text states the ordering dependency: CFB 2026 close needs PR 3, Docket 2026 close needs PR 4.

### D5. `/records` page (`core/records/` blueprint, public GET)
Context: `champions()` rows with `get_entry(slug).display_name`; boards from `seasons_on_record()` newest first via `finishes_for`; the room's own archive link from `SEASON_ARCHIVES = {('cfb', 2025): 'cfb.history', ('worldcup', 2026): 'worldcup.leaderboard', ('docket', 2026): 'docket.ledger'}` (endpoint strings, `url_for` resolves; no game import). Per row: place, avatar via `row.user.get_avatar()` when linked, the recorded name, "now {display_name}" only when it differs, detail.
Register: the Tribune's light reading room (Teko masthead "The Record", one Newsreader lede, 2px gold rule, 40rem column, hairline lists), namespaced `.records-*` classes only, body class `records-page`, own `/* === THE RECORD === */` section appended at the end of `style.css` with its `≤575.98px` block, a `<details>` per board with the newest open, no eyebrow above any heading (ADR-066). Nav: dropdown item `bi-trophy` "The Record" beside The Tribune (`base.html:105-108`) for members; the footer utility line (`base.html:298-301`) gains the link as the anonymous entry point. `games/cfb/templates/cfb/history.html:103-104` provenance line gains a second sentence linking `/records` (an internal link, not the banned clubhouse URL; ADR-068 records the supersession). UI work invokes the `impeccable` skill with no `--target` and runs the detector.

### D6. Season column (CFB and Docket)
- `CfbWeek.season_year`, `CfbTeam.season_year`, `DocketWeek.season_year`: `Integer NOT NULL`; models declare `__table_args__` uniques `uq_cfb_week_season_number (season_year, week_number)`, `uq_cfb_team_season_name (season_year, name)`, `uq_docket_week_season_number (season_year, week_number)` and drop `unique=True` from the columns so `flask db check` compares like with like. `CfbPick`/`DocketPick` stay scoped through `week_id` (golf's shape).
- **Migration recipe, both dialects.** Step 1: `batch_alter_table` add the column with `server_default='2026'` (fills existing rows; own batch block). Step 2 branches on `op.get_bind().dialect.name`: sqlite → `batch_alter_table(table, naming_convention={'uq': 'uq_%(table_name)s_%(column_0_name)s'})`, then `alter_column(server_default=None)`, `drop_constraint(f'uq_{table}_{col}', type_='unique')`, `create_unique_constraint(new, ['season_year', col])` (Alembic's documented recipe for unnamed constraints in batch mode; each table carries exactly one unnamed unique); postgresql → reflect the real name with `sa.inspect(bind).get_unique_constraints(table)` filtered on `column_names == [col]` (the `[old] =` unpack fails loudly), then plain `op.alter_column` / `op.drop_constraint` / `op.create_unique_constraint`. Downgrade reverses with the Postgres default names given explicitly. `migration-reviewer` agent reviews before the local upgrade.
- **Per-year calendars.** CFB `games/cfb/constants.py:26-46` → `SEASON_SCHEDULES = {2026: {...existing keys..., 'enrollment_deadline_utc', 'season_live_utc'}}` + `season_schedule(year)` (a `KeyError` is the loud failure); the 14 `SEASON_SCHEDULE` readers move to `season_schedule(_get_season_year())` and the old name is deleted; `games/cfb/services/lounge.py:81,93` derive `ENROLLMENT_DEADLINE_UTC`/`SEASON_LIVE_UTC` from the calendar (the equality lock in `tests/test_lounge_multi_featured.py:548` is unchanged). Docket `games/docket/services/weeks.py:22-30` → `SEASON_CALENDARS = {2026: SeasonCalendar(week_1_boundary_local, total_weeks, first_nfl_week, enrollment_deadline_utc)}`; `SEASON_YEAR = 2026` stays the current-season module constant (config.py:72-73 ruling holds); `WEEK_1_BOUNDARY_LOCAL`/`TOTAL_WEEKS`/`FIRST_NFL_WEEK` become aliases of `SEASON_CALENDARS[SEASON_YEAR]` so the 24 importers are untouched; boundary functions take `season_year=SEASON_YEAR`; `games/docket/services/lounge.py:81` derives from the calendar. 2027 is one more dict key when its dates exist.
- **Read helpers.** New `games/cfb/services/weeks.py` (imports models + utils only): `season_weeks`, `week_by_number(n, season_year)`, `active_week`, `complete_weeks`, `latest_week`, `season_teams`, `deactivate_all`; `week_state.py:39-58` calls them. New `games/docket/services/week_reads.py`: `week_by_number(n, season_year=SEASON_YEAR)`, `season_weeks`.
- **Site rules (grep, don't trust line numbers):**

| Kind | Rule | Where |
|---|---|---|
| (a) `filter_by(week_number=n)` | `week_by_number(n, season)` | CFB routes, cli, announce_blocks, lounge; Docket ~12 sites (desk, importer `ensure_week`, scores, season_pass, cli, admin) |
| (b) `is_active=True` lookups, `CfbWeek.query.update({'is_active': False})` | `active_week` / `deactivate_all` | routes, automation, week_state |
| (c) whole-table scans (`order_by(week_number).all()`, `is_complete` filters) | `season_weeks` / `complete_weeks`; Docket `week_rollups_from_db` joins `DocketWeek.season_year` and its docstring at `season_pass.py:182-185` flips | automation (incl. `_lowest_orphan_week`), field, card, lounge, gameday, week_state; Docket season_pass, cli, admin_routes |
| (d) `max(week_number)+1` | `latest_week(season)` | automation |
| (e) picks / outcomes / results filtered by user only | join the week and filter `season_year`: `get_used_team_ids`, the cumulative-spread total (docstring: lifetime = the season), `_eliminated_in_another_week`, card, routes, lounge; Docket `DocketWeekResult` / `DocketTiebreakerPrediction` reads | game_logic, card, routes, lounge; Docket sheets, brief, record, history |
| (f) by `week_id` | untouched | — |
| (g) Docket time-window reads (`current_week`/`upcoming_week` on `start_at`/`end_at`) | untouched, already season-safe | picks.py |
| teams | `season_teams(season)`: `pool_teams_by_conference`, field, card, admin Manage Teams (add stamps `season_year`), the score-fetcher name map; `populate-teams` refuses a non-empty **season** | game_logic, field, card, routes, automation, cli |
| constructors | `CfbWeek(season_year=...)`, `CfbTeam(season_year=...)`, `DocketWeek(season_year=...)` | cfb automation + routes + cli; docket importer |

- **Fixtures.** `make_week`/`make_team` in both fixture modules default `season_year` to the game's current season with an override kwarg; the ~6 direct `CfbWeek(`/`DocketWeek(` constructions and local `_make_week` helpers pass it.

---

## Execution order

**PR 1 — The Record (data).** Commit the spec `docs/superpowers/specs/2026-09-28-club-record-season-scoping-design.md` (this plan's Context + Design + rulings) first. Then D1, D2, D3, D4; ADR-068 (supersedes ADR-053; records the two 2025-spec supersessions: linking and the provenance link; the seam decision; the `g` cache contract); CLAUDE.md (Avatars bullet at `:184`, a Records bullet under Platform integration, the two CLI lines); `docs/worldcup-archive-invariants.md` line; tick the champions box in open-items §E.
Tests `tests/test_records.py` (conftest fixtures): `record_season` idempotency and `--force`; reigning derivation (latest season per game, unlinked champion crowns nobody, two games → two trophies, admin champion still crown, writer clears the cache); each builder on a seeded closed season and its `SeasonNotClosed` on an open one; the 2025 import with a temporary link map (26 rows, exactly one place 1, unknown username raises, nothing committed); link-map hygiene (every key is a 2025 standings name, values are usernames, raw text contains no `email`/`user_id`/`id`); `records close` via `app.test_cli_runner()`; source lock: `core/records/*.py` and `models/records.py` import nothing under `games.` except `games.registry`; registry seam: the three entries carry a callable, golf `None`. Rewrite `tests/test_auth_avatar_phone.py:132-197`: drop the literal-constant test; the trophy/case/admin tests seed a row through `record_season`; profile test asserts "reigning club champion".

**PR 2 — `/records` page.** D5; tests `tests/test_records_page.py` (or in `test_records.py`): 200 anonymous, names and detail present, anonymous response not `no-store`, no `<form`/POST, both nav links, the `/cfb/history` link, CSS section with a `575.98px` block; add `core/records/templates` to `ROOM_TEMPLATES` in `tests/test_eyebrow_above_heading.py:32`. Tick the `/records` and 2025-links boxes.

**PR 3 — CFB season scoping.** D6 CFB half; ADR-069 (covers both games); `tests/test_season_scoping.py` CFB half: a two-season seed (2025 weeks/teams/games/picks/outcomes beside 2026) asserting standings, card, field, lounge state/context, used teams, cumulative spread, autopick, setup's next week number and `[[survivor-board]]` ignore the other season; source lock regex `\b(CfbWeek\.query|select\(CfbWeek\)|filter_by\(week_number=)` over `games/cfb/**/*.py` allow-listing only `services/weeks.py`; `@pytest.mark.postgres` unique-pair test (same week number in two seasons inserts; same season twice raises `IntegrityError`).

**PR 4 — Docket season scoping.** D6 Docket half; the Docket half of `test_season_scoping.py` (ledger, sheets, brief, record, desk, `[[docket-week]]`) with the same lock over `games/docket/**/*.py` allow-listing `services/week_reads.py`; the preview-wipe recipe in `games/docket/cli.py:20-38` updated to the helper; CLAUDE.md Season scoping bullet under Code conventions; tick the last §E box.

**Deploy timing.** PR 1 and PR 2 any weekday morning; run `flask records close worldcup 2026` and `flask records close cfb 2025` in the same sitting as the PR 1 deploy (the trophy is derived from the table from that deploy on, so the gap is minutes). PR 3 and PR 4: Wed or Thu 09:00–15:00 CT, after Tuesday's Paper and before Thursday's game-day passes, never Fri–Sun; the unique swap locks tables of ≤49 rows for milliseconds and Alembic runs the file in one transaction; `deploy.sh` takes the ADR-067 `pg_dump` before migrating. Later closes: `records close docket 2026` after Jan 12 (after PR 4), `records close cfb 2026` after the CFP final (after PR 3).

---

## Verification (every PR)
```
venv/bin/ruff check .
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q -n auto --dist loadfile
TEST_DATABASE_URL=postgresql:///ccc_test ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q -n auto --dist loadfile
TEST_DATABASE_URL=postgresql:///ccc_migrations_test ENVIRONMENT=testing FLASK_APP=app.py venv/bin/flask db upgrade && TEST_DATABASE_URL=postgresql:///ccc_migrations_test ENVIRONMENT=testing FLASK_APP=app.py venv/bin/flask db check
```
Plus per PR: PR 1 `flask records close cfb 2025` against the local `ccc_local` DB with a seeded `cubbies22`, then `records show`; PR 2 `/browse` smoke on `flask run --port 5099` (logged out and in, 390px and 1280px) and `npx impeccable detect --json` on the changed targets; PR 3/4 the `migration-reviewer` pass before the `ccc_migrations_test` upgrade, `/browse` smoke of the room, Field, admin Manage Teams / Create Week (CFB) and the ledger / sheets / admin week (Docket) under `CFB_FAKE_NOW` / `DOCKET_FAKE_NOW`; after each prod deploy the ADR-040 checklist (`systemctl status`, journal, `ps -o args= -C gunicorn`), and after PR 3/4 `\d cfb_week` / `\d docket_week` showing the pair constraint.
