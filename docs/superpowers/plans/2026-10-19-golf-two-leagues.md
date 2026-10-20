## Handoff to the implementing session (read this first)

The spec is `docs/superpowers/specs/2026-10-19-golf-two-leagues-design.md`; the full session record with the review ledger (Parts 2 and 4) is `~/.claude/plans/a-large-golf-pick-rosy-ocean.md`.


1. This file is the spec (Part 1), the code inventory (Part 2), the plan (Part 3) and the
   review record (Part 4). Read all of it before Task 0; Part 4's decisions D1-D4 are binding and
   are already folded into Part 3.
2. Start with Task 0 on branch `golf-two-leagues-a`: copy Part 1 to
   `docs/superpowers/specs/2026-10-19-golf-two-leagues-design.md` and Part 3 (with its Global
   Constraints and Review Focus) to `docs/superpowers/plans/2026-10-19-golf-two-leagues.md`, and
   commit both. From then on the repo copy is the plan; tick its checkboxes as tasks land
   (Brad's checkbox discipline).
3. Execution mode per task (my recommendation, grounded in this repo's history):
   - **superpowers:subagent-driven-development** for the data and seam tasks: A1, A2, A3, A4, A5,
     C1, C3. Each is a bounded, well-specified change with exact signatures and named tests, the
     kind an independent reviewer per task catches mistakes in (a 59-site test rewrite, two
     migrations, a platform table). Subagents in this repo cannot Edit/Write under additional
     directories, so give each one the worktree's own paths.
   - **superpowers:executing-plans** (inline, this session) for every UI task: B1, B2, B3, B4, B5,
     C2, and the docs task C4. Impeccable must run in the session that owns the surface (Brad's
     standing feedback: a subagent running impeccable has to prove the invocation with content
     fingerprints, which is more ceremony than the work), and every one of these reads
     `games/golf/DESIGN.md` beside the root `DESIGN.md`.
4. Three PRs, each green before the next starts: A (data + URLs), then B and C in parallel
   worktrees (B merges first, C rebases), C4 last. The D3 regression audit goes in every PR body.
5. The gstack upgrade to 1.91.148.0 was skipped by plan mode (auto-upgrade is on); run
   `/gstack-upgrade` at the start of the fresh session.


## Review decisions folded into this plan (plan-eng-review, 2026-10-19)

- **D1** Original arrangement: `GolfLeague` table + `league_id` FKs + `services/leagues.py` + `flask golf league list|set`.
- **D2** Mail flags stay per tournament, latching once after both leagues (accepted 7/10 shortcut; upgrade to a per-league latch table only if a duplicate letter is observed; mark the latch site `gstack-shortcut(dec-6e3392bc)`).
- **D3** Regression contract: only the URL prefix, the `league_id=` kwarg and the `golf_leagues` fixture may change in existing tests; every PR body carries `git diff main -- tests/ | grep '^-.*assert'` with one sentence per line.
- **D4** A golf Settle the Tab card ships in PR B (Task B5).
- **S1** Letters build links by string with the league slug (no `url_for` in a timer). **S2** An unknown league renders the club 404 page (`g.golf_league = None` tolerated by the sub-nav and context processor).
- **Q1-Q3, P1, G1-G3** folded into A1, A5, C1 as written below.

# Two leagues for The Pay Sheet: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two independent One & Done leagues (Handicap, Pollyanna) inside the one golf game, on one schedule and one sync, with a member of both able to play both.

**Architecture:** A `GolfLeague` row is the league; `league_id` joins `GolfEnrollment`, `GolfPick` and `GolfSeasonPlayerUsage` to it and every league-scoped read filters on it. The league lives in the URL (`/golf/<league>/...`): a blueprint `url_value_preprocessor` resolves it into `g.golf_league` and a `url_defaults` hook puts it back into every `url_for` inside the room, so templates keep calling `url_for('golf.index')`. The record gains a `division` so one `flask records close golf YEAR` writes one board per league.

**Tech Stack:** Flask 3 / SQLAlchemy 2 / Alembic / pytest (SQLite + Postgres jobs) / Jinja; the `impeccable` skill for every rendered surface.

**Spec:** `docs/superpowers/specs/2026-10-19-golf-two-leagues-design.md` (committed with this plan at Task 0).

**Shipping shape: three PRs**, each green on its own.
- **PR A: the league dimension.** Model, migration, every service and route scoped, the URL league, a functional join choice, the CLI, the legacy import. The room works for two leagues; it does not yet look designed for them.
- **PR B: the room.** The impeccable pass: league stamps, the sub-nav switch, the join page, the pick page's other-sheet line, the Back Office scoping (commissioner toggle, move, Settle the Book platform-only).
- **PR C: the club.** The record's division, the lounge, the letters, the announce audiences, the docs and ADR.

### Global Constraints

- Both leagues play the Pay Sheet's rules unchanged; only `entry_fee` and `penalty_per_incident` are per league (seed values: 25 and 15 for both).
- League names and slugs: `handicap` "Handicap Pay Sheet" (ordinal 1, the house league), `pollyanna` "Pollyanna Pay Sheet" (ordinal 2).
- One registry entry `golf`; `short_name='Golf'` never changes; `display_name` "The Pay Sheet" stays.
- No new SlashGolf call anywhere (`tests/test_golf_timers.py` cadence untouched).
- Every email is a Club Letter (`utils.email_layout.Letter`, no eyebrow above the heading, ADR-066); a league letter's headline opens with the league name.
- `datetime.now(UTC)`; SQLAlchemy 2.0 style for new/changed lines; boolean filters `.is_()`; relationships plain many-to-one on the child, no `backref`, no collections, no `lazy='dynamic'` (`tests/test_golf_model_relationships.py`).
- Schema changes by Alembic only; the migration must pass `flask db upgrade` + `flask db check` on an empty Postgres and the Postgres pytest job.
- Enrollment rows are created only by `/golf/join` and `/admin/enrollments`; never from an admin or pick path.
- Stage by explicit path; never `git add -A`.
- **Regression contract (D3):** in existing tests only the URL prefix, the `league_id=` kwarg and the `golf_leagues` fixture may change; every PR description carries `git diff main -- tests/ | grep '^-.*assert'` with one sentence per removed or changed assertion, and names any test whose assertion had to change and why. Both CI runs green at the end of A5, B5 and C4.
- Letters never use `url_for` (no request context in a timer): links are `f"{site_url}/golf/{league.slug}/..."`.
- UI tasks (PR B, the lounge in PR C) invoke `impeccable` with `games/golf/DESIGN.md` read beside the root `DESIGN.md`.

### Review Focus

Inputs the spec implies but no feature test would otherwise exercise; each line's test is pinned to the task named.
1. A member of both leagues spends the same golfer in both the same week: both usage rows must exist after processing, neither silently dropped (Task A2).
2. An unknown league slug in the URL (`/golf/nowhere/`) is a 404, never the house league (Task A5).
3. A URL built outside the room without `league=` (the lounge, a letter) fails loudly with a `BuildError`, never silently picks a league (Task A5).
4. The Pollyanna commissioner POSTs to a Handicap admin route and to Settle the Book: redirected with the flash, nothing written (Task B4).
5. `flask records close golf YEAR` when one league has a banked board and the other has no enrollee: the empty league is skipped and named, the other closes (Task C1).

---

### Task 0: Commit the spec and the plan

**Files:**
- Create: `docs/superpowers/specs/2026-10-19-golf-two-leagues-design.md` (Part 1 of this file, verbatim)
- Create: `docs/superpowers/plans/2026-10-19-golf-two-leagues.md` (Part 3 of this file)

- [ ] **Step 1:** Create the branch `golf-two-leagues-a` from `main`; write both files.
- [ ] **Step 2:** Commit: `docs: golf two-leagues design + plan`

---

## PR A: the league dimension

Tasks A2 to A4 change service signatures the routes still call the old way, so route tests stay red inside PR A until A5 lands; each task runs its own named test files, and A5 runs the whole suite. The branch is one PR, so nothing red is ever on `main`.

### Task A1: `GolfLeague` model, seed, and the migration

**Files:**
- Modify: `games/golf/models.py` (new class before `GolfEnrollment`; `league_id` on `GolfEnrollment`, `GolfPick`, `GolfSeasonPlayerUsage`; constraints)
- Modify: `games/golf/constants.py` (`LEAGUE_SEED`)
- Create: `games/golf/services/leagues.py`
- Create: `migrations/versions/<rev>_golf_leagues.py` (`down_revision='8a05e7e5c96f'`)
- Modify: `models/__init__.py` (re-export `GolfLeague`)
- Modify: `tests/conftest.py` (fixture `golf_leagues`)
- Test: `tests/test_golf_leagues.py` (new; the spec lock for the whole change), `tests/test_golf_model_relationships.py`

**Interfaces (produces):**
- `GolfLeague(db.Model)`, table `golf_league`: `id`, `slug String(20) unique`, `name String(60)`, `entry_fee Integer not null`, `penalty_per_incident Integer not null`, `ordinal Integer unique not null`, `created_at`.
- `constants.LEAGUE_SEED = (('handicap', 'Handicap Pay Sheet', 1), ('pollyanna', 'Pollyanna Pay Sheet', 2))`; fee 25 and penalty 15 for both come from `config ENTRY_FEE` and `models.PENALTY_PER_INCIDENT` at seed time only.
- `services/leagues.py`: `seed_leagues() -> list[GolfLeague]` (idempotent upsert by slug, commits), `leagues() -> list[GolfLeague]` (by ordinal), `league_by_slug(slug) -> GolfLeague | None`, `house_league() -> GolfLeague` (ordinal 1).
- `GolfEnrollment.league_id` FK not null `index=True`, `league = db.relationship('GolfLeague')`; unique `('user_id', 'league_id', 'season_year', name='unique_golf_enrollment')`.
- `GolfPick.league_id` FK not null `index=True`, `league` relationship; unique `('user_id', 'league_id', 'tournament_id', name='unique_golf_user_tournament_pick')`.
- `GolfSeasonPlayerUsage.league_id` FK not null `index=True`; unique `('user_id', 'league_id', 'player_id', 'season_year', name='unique_golf_player_usage')`.
- conftest fixture `golf_leagues(app) -> dict[str, GolfLeague]` keyed by slug (calls `seed_leagues()`).

- [x] **Step 1:** Write failing tests in `tests/test_golf_leagues.py`:
  - `test_seed_leagues_is_idempotent_and_ordered`: two calls, `[l.slug for l in leagues()] == ['handicap', 'pollyanna']`, `house_league().slug == 'handicap'`, fees `25`, penalties `15`.
  - `test_the_same_member_holds_a_line_in_both_leagues`: two `GolfEnrollment` rows for one user, same season, different `league_id`, commit succeeds; a third with a repeated league raises `IntegrityError`.
- [x] **Step 2:** Run `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_golf_leagues.py -q`; expect ImportError on `games.golf.services.leagues`.
- [x] **Step 3:** Implement the model, constants, service, conftest fixture. Add `league_id=` to every `GolfEnrollment(`, `GolfPick(`, `GolfSeasonPlayerUsage(` constructor in `tests/` (59 sites across 18 files: `grep -ln "GolfEnrollment(\|GolfPick(\|GolfSeasonPlayerUsage(" tests/*.py`), each taking the `golf_leagues` fixture and `golf_leagues['handicap'].id`. Helpers inside `games/golf/services/legacy_import.py` and `instance/` seeders are Task A4's.
- [x] **Step 4:** Generate the migration on `ccc_local` (`FLASK_APP=app.py venv/bin/flask db migrate -m "golf leagues"`), then hand-edit: create `golf_league`; insert the two seed rows with `op.bulk_insert`; add the three `league_id` columns nullable; `UPDATE ... SET league_id = (SELECT id FROM golf_league WHERE slug='handicap')`; alter to NOT NULL; drop the three old unique constraints by name and create the new ones (batch mode, like `migrations/versions/8d3f6b1a2c95_add_season_year_to_docket_week.py`); downgrade reverses. Invoke the `migration-reviewer` agent on the file before upgrading.
- [x] **Step 5:** Run the whole suite on SQLite and the migration chain on Postgres: `createdb ccc_migrations_test` if absent, `TEST_DATABASE_URL=postgresql:///ccc_migrations_test ENVIRONMENT=testing FLASK_APP=app.py venv/bin/flask db upgrade && ... flask db check`; expect clean. Run `venv/bin/ruff check .`.
- [x] **Step 6:** Commit: `feat(golf): GolfLeague + league_id on enrollment, pick and usage (ADR-075)`

### Task A2: League-scoped model methods and the enrollment seam

**Files:**
- Modify: `games/golf/models.py` (`calculate_total_points`, `get_used_player_ids`, `penalty_owed`, `validate_availability`, `clear_resolution`, `resolve_pick`, `_record_season_usage`)
- Modify: `games/golf/services/enrollment.py`
- Modify: `games/golf/services/reads.py`
- Test: `tests/test_golf_leagues.py`, `tests/test_golf_scoring.py`, `tests/test_golf_penalty.py`

**Interfaces:**
- `_record_season_usage(user_id, league_id, player_id, season_year)`; `resolve_pick` passes `self.league_id`.
- `GolfEnrollment.penalty_owed(season_year=None)` multiplies by `self.league.penalty_per_incident`; `GolfEnrollment.penalty_outstanding` unchanged in signature.
- `GolfPick.validate_availability(season_year)` and `clear_resolution(season_year)` filter usage and other picks on `self.league_id`.
- `services/enrollment.py`: `get_enrollment(user_id, league=None) -> GolfEnrollment | None` (`league` a `GolfLeague`; `None` = the member's lowest-ordinal enrollment this season, the registry's contract), `enrollments_for(user_id) -> list[GolfEnrollment]` (this season, by ordinal), `admin_enroll(user_id, league=None) -> GolfEnrollment` (`None` = `house_league()`).
- `services/reads.py`: `season_enrollments(season_year, league_id)`, `tournament_picks(tournament_id, league_id)`; the rest unchanged.

- [x] **Step 1:** Failing tests in `tests/test_golf_leagues.py`:
  - `test_spending_a_golfer_in_one_league_leaves_him_unspent_in_the_other`: Brad in both; a resolved pick on Scheffler in Handicap; `validate_availability` for a Pollyanna pick on Scheffler returns `[]`; after resolving that too, `GolfSeasonPlayerUsage` has two rows for (Brad, Scheffler), one per league (Review Focus 1).
  - `test_clear_resolution_deletes_only_this_leagues_usage`.
  - `test_total_points_and_penalty_are_per_line`: Handicap total ignores Pollyanna picks; Pollyanna's `penalty_per_incident=20` makes `penalty_owed()` 20 per flagged pick there and 15 in Handicap.
  - `test_get_enrollment_without_a_league_is_the_house_line_first`; `test_admin_enroll_seats_the_house_league`.
- [x] **Step 2:** Run; expect failures on the old signatures.
- [x] **Step 3:** Implement. Update the existing callers of `season_enrollments` / `tournament_picks` to pass a league id only in the service modules this task touches; the routes and the lounge come in A5 and C2 (they fail to import nothing, they fail at call time, which A5's tests cover).
- [x] **Step 4:** Run `tests/test_golf_leagues.py tests/test_golf_scoring.py tests/test_golf_penalty.py tests/test_golf_model_relationships.py -q`; expect PASS.
- [x] **Step 5:** Commit: `feat(golf): league-scoped usage, totals, penalty and the enrollment seam`

### Task A3: League-scoped season aggregates and builders

**Files:**
- Modify: `games/golf/services/stats.py` (`_usage_counts`, `remaining_pct_map`, `spent_weeks`, `season_race`, `_banked_picks`, `superlatives`, `field_form`, `burn_list`, `override_tally`)
- Modify: `games/golf/services/sheet.py` (no signature change; `week_lines` keeps `lines[user_id]`, correct once its picks are one league's)
- Test: `tests/test_golf_stats.py`, `tests/test_golf_sheet.py`, `tests/test_golf_leagues.py`

**Interfaces:** every listed `stats.py` function gains a `league_id` positional parameter right after `season_year` (`spent_weeks(user_id, league_id, season_year)`); the shared ones (`ytd_earnings`, `season_progress`, `_missed_cuts`, `race_chart_geometry`, `counted_golfer`) are unchanged.

- [x] **Step 1:** Failing test `test_the_other_leagues_picks_never_reach_a_leagues_aggregates`: Brad with a banked pick in each league the same week; for Handicap, `_usage_counts`, `spent_weeks`, `season_race`, `superlatives`, `field_form`, `burn_list`, `override_tally` show only the Handicap pick (assert on counts and golfer ids).
- [x] **Step 2:** Run; expect TypeError on the old signatures.
- [x] **Step 3:** Implement: each function adds `GolfPick.league_id == league_id` (or the usage/enrollment equivalent) beside its season filter.
- [x] **Step 4:** Run the three test files; PASS. Commit: `feat(golf): season aggregates scoped by league`

### Task A4: Sync, reminders and the legacy import per league

**Files:**
- Modify: `games/golf/services/sync.py` (`process_tournament_picks`)
- Modify: `games/golf/services/reminders.py` (`send_picks_open_email`, `send_results_recap_email`, `get_users_without_picks`, `run_reminder_check`, the three letter builders)
- Modify: `games/golf/services/legacy_import.py` (`run_import`, `verify_scoring`), `games/golf/cli.py` (`import-legacy --league`, `verify-legacy --league`, new group `flask golf league list|set`)
- Modify: `instance/seed_*` golf seeders if any construct the three models (gitignored; fix locally)
- Test: `tests/test_golf_sync.py`, `tests/test_golf_automation.py`, `tests/test_golf_conformance.py`, `tests/test_golf_legacy_import.py`, `tests/test_golf_leagues.py`

**Interfaces:**
- `process_tournament_picks(tournament)` unchanged signature; usage cleanup and the enrollment lookup add `league_id == pick.league_id`; recap sending unchanged (the sender loops leagues).
- `send_picks_open_email(tournament) -> int`, `send_results_recap_email(tournament_id) -> int`, `run_reminder_check()`: loop `leagues()`; per league the roster is `season_enrollments(season, league.id)`, the pick URL is the string `f"{site_url}/golf/{league.slug}/pick/{tournament.id}"` (today's shape at `reminders.py:195,761`, with the slug added; the results link `f"{site_url}/golf/{league.slug}/tournament/{id}"` the same way; no `url_for`, there is no request context in a timer; review finding S1), the headline is `f'{league.name}, {the_event(name)}: ...'`, the fee line reads `league.entry_fee`. Tournament flags (`picks_open_notified`, `recap_email_sent`, `last_reminder_type`) latch once after both leagues (D2: accepted shortcut, upgrade to a per-league latch table only if a duplicate letter is ever observed; mark the latch site `gstack-shortcut(dec-6e3392bc): per-tournament latch, upgrade when a duplicate letter lands`).
- `get_users_without_picks(tournament_id, season_year, league_id)`.
- `run_import(path, season=2026, *, league='handicap', ...)`; `verify_scoring(season, league='handicap', legacy_path=None)`.
- CLI: `flask golf league list` prints slug, name, fee, penalty, ordinal; `flask golf league set SLUG [--name] [--entry-fee N] [--penalty N]` (exit 1 on unknown slug).

- [x] **Step 1:** Failing tests: `test_process_tournament_picks_retotals_each_line_separately`; `test_picks_open_goes_once_per_line_so_brad_gets_two_letters` (two letters to Brad, one to a Pollyanna member, headlines start with the league name, each link carries its league slug); `test_reminder_passes_loop_both_leagues_and_latch_once`; `test_import_legacy_takes_a_league` (every imported enrollment/pick/usage row carries the given league id; the oracle still 0 diffs); `test_league_set_cli_changes_the_fee`.
- [x] **Step 2:** Run; expect failures.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run the five test files; PASS. Commit: `feat(golf): sync, letters and the import learn the league`

### Task A5: The league in the URL, the resolver, and every route scoped

**Files:**
- Modify: `games/golf/routes.py` (preprocessor, defaults, `_viewer_enrollment`, `inject_golf_globals`, `golf_admin_required`, new `golf_league_member_required`, new `golf_platform_admin_required`, every route)
- Modify: `games/golf/templates/golf/join.html` (functional two-league form only; the design pass is B2)
- Modify: `core/records/routes.py` (`SEASON_ARCHIVES[('golf', 2026)] = ('golf.record_room', {'league': 'handicap', 'season': 2026})`)
- Modify: `templates/base.html` golf sub-nav (links build as before through the defaults; `subnav-label-sub` reads `{{ golf_league.name }} · {{ season_year }}`)
- Test: `tests/test_golf_leagues.py`, `tests/test_golf_admin_route_matrix.py`, `tests/test_golf_cleanup.py` (query-count locks), `tests/test_golf_pick_page.py`, `tests/test_golf_scorecard.py`, `tests/test_golf_record_room.py`, `tests/test_golf_admin_pages.py`, `tests/test_records_page.py`

**Interfaces:**
- URL rules: league-scoped `'/<league>/'` (`index`), `'/<league>/tournament/<int:tournament_id>'`, `'/<league>/results'`, `'/<league>/member'`, `'/<league>/member/<int:user_id>'`, `'/<league>/stats'`, `'/<league>/pick/<int:tournament_id>'`, `'/<league>/my-picks'`, `'/<league>/admin/'`, `'/<league>/admin/tournaments'`, `'/<league>/admin/users'`, `'/<league>/admin/payments'`, `'/<league>/admin/update-payment/<int:user_id>'`, `'/<league>/admin/override-pick'`, `'/<league>/admin/process-results/<int:tournament_id>'`. Shared: `'/'` (`room`, redirects to `index` for `g.golf_league`), `'/join'`, `'/schedule'`, `'/leaderboard'`.
- `@golf_bp.url_value_preprocessor def _pull_league(endpoint, values)`: pops `league`; when given, `g.golf_league = league_by_slug(slug)`, and if that is `None` the preprocessor leaves `g.golf_league = None` and calls `abort(404)` (review S2: the 404 page extends `base.html`, whose golf sub-nav and `inject_golf_globals` run under `request.blueprint == 'golf'`, so both must tolerate `None` at this one boundary: the sub-nav renders the label and no pills, the context processor yields no line); else `viewer_league()`.
- `@golf_bp.url_defaults def _push_league(endpoint, values)`: if `'league' not in values` and `current_app.url_map.is_endpoint_expecting(endpoint, 'league')` and `g` has `golf_league`: `values['league'] = g.golf_league.slug`. Outside the room nothing is set, so `url_for` raises `BuildError` (Review Focus 3).
- `viewer_league() -> GolfLeague`: anonymous or no line → `house_league()`; one line → its league; more → the `golf_league` cookie's league if it is one of theirs, else the lowest ordinal. `@golf_bp.after_request` sets the cookie (`samesite='Lax'`, 180 days) on league pages for a member with more than one line, only when its value would change (review Q3).
- Context processor calls `enrollments_for(current_user.id)` once (review Q1) and derives from that list: `golf_lines` (the list, `[]` when anonymous), the viewer's line in `g.golf_league` (for `golf_is_admin` and `golf_has_line`), plus `golf_league` (the row), `entry_fee = golf_league.entry_fee`, `penalty_per_incident = golf_league.penalty_per_incident`.
- `golf_admin_required`: platform admin, else `get_enrollment(user.id, g.golf_league).is_admin`.
- `golf_platform_admin_required`: `current_user.is_admin` only (flash "Platform admin only." and redirect to `golf.admin_dashboard`); applied to `admin_tournaments` and `admin_process_results` (Brad's ruling 10; B4 adds the roster controls).
- `golf_league_member_required`: `get_enrollment(current_user.id, g.golf_league)` else flash `f'Join the {g.golf_league.name} to pick there.'` and redirect to `golf.join`; stacked under `@enrollment_required('golf')` on `make_pick` and `my_picks`.
- Every route replaces `season_enrollments(season)` with `season_enrollments(season, g.golf_league.id)`, `tournament_picks(tid)` with the league form, every `GolfPick`/`GolfEnrollment`/`GolfSeasonPlayerUsage` `filter_by(user_id=...)` adds `league_id=g.golf_league.id`, `PENALTY_PER_INCIDENT` reads become `g.golf_league.penalty_per_incident`, `current_app.config['ENTRY_FEE']` reads become `g.golf_league.entry_fee`, and `finishes_for('golf', season)` in `_champions` becomes `finishes_for('golf', season, division=g.golf_league.slug)` once C1 lands (until then pass no division; C1 flips it).
- `join`: GET lists `leagues()` with `enrollments_for` marking the joined ones; POST reads `league` (slug), 400 on unknown, flashes "already on that sheet" if enrolled there, else creates `GolfEnrollment(user_id, league_id, season_year)` and redirects to `golf.index` for that league. `can_join` on `index` becomes "not on this league's sheet".
- `member_scorecard`: `seasons` comes from the member's enrollments in `g.golf_league`; 404 when the member has no line in this league that season.

- [x] **Step 1:** Failing tests in `tests/test_golf_leagues.py`:
  - `test_room_root_resolves_to_the_viewers_league` (anonymous → `/golf/handicap/`; a Pollyanna-only member → `/golf/pollyanna/`; Brad with the cookie `golf_league=pollyanna` → `/golf/pollyanna/`).
  - `test_unknown_league_is_404` (Review Focus 2; asserts the status AND that the body is the club's 404 page, not a 500: review S2).
  - `test_url_for_outside_the_room_needs_a_league` (in a plain app request context `url_for('golf.index')` raises `BuildError`; `url_for('golf.index', league='pollyanna') == '/golf/pollyanna/'`).
  - `test_each_leagues_sheet_board_and_stats_show_only_its_lines` (render `/golf/handicap/`, the board, `/stats`, Brad's scorecard: the Pollyanna golfer's name never appears).
  - `test_pick_route_needs_a_line_in_that_league`.
  - `test_join_seats_the_chosen_league_and_allows_the_second`.
  - `test_admin_pages_scope_to_the_league_and_settle_the_book_is_platform_only` (a Pollyanna commissioner: 200 on `/golf/pollyanna/admin/users`, 302 on `/golf/handicap/admin/users`, 302 on `/golf/pollyanna/admin/tournaments`).
- [x] **Step 2:** Run; expect 404s on the new URLs.
- [x] **Step 3:** Implement. Then update every existing golf route test's URLs (`/golf/` → `/golf/handicap/` where the page is league-scoped) and `tests/test_records_page.py`'s golf archive link.
- [x] **Step 4:** Run `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -n auto --dist loadfile -q` and the Postgres run; expect PASS. `venv/bin/ruff check .` clean.
- [x] **Step 5:** Commit: `feat(golf): the league in the URL; every room read scoped`
- [ ] **Step 6:** Smoke on the dev server (`FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099`, `ccc_local` after `flask db upgrade`) as a platform admin: `/golf/` redirects; `/golf/handicap/` and `/golf/pollyanna/` both render; join into Pollyanna; a pick in each league on the same golfer succeeds. Open PR A; CodeRabbit clean; merge.

---

## PR B: the room

Branch `golf-two-leagues-b` from `main` after PR A. Every task here runs `impeccable` (`--target games/golf`) with `games/golf/DESIGN.md` read beside the root `DESIGN.md`; no eyebrow above a heading (ADR-066); `.golf-*` primitives only.

### Task B1: The league stamp and the switch

**Files:**
- Modify: `templates/base.html` (golf sub-nav: the label sub-line, a `.subnav-pill` per other league of the viewer's when `golf_lines|length > 1`, linking `url_for('golf.index', league=line.league.slug)`)
- Modify: `games/golf/templates/golf/{index,tournament_detail,member_scorecard,record_room,make_pick}.html` and `admin/{dashboard,tournaments,users,payments,override_pick}.html` (the `golf-context` line opens with `golf_league.name`; `<title>` blocks name the league)
- Modify: `static/css/style.css` (golf section) only if the switch needs a modifier
- Test: `tests/test_golf_leagues.py`, `tests/test_eyebrow_above_heading.py`

- [x] **Step 1:** Failing test `test_every_league_page_is_stamped_and_only_a_member_of_both_sees_the_switch`: each listed page's rendered HTML contains the league name in the context line; Brad's render of `/golf/handicap/` has a pill to `/golf/pollyanna/`; a Handicap-only member's render has none. Carried from PR A's review: `test_shared_pages_keep_the_league_the_viewer_came_from` (the Schedule pill and the room's door carry `?league=`), `test_record_room_lists_only_this_leagues_seasons`.
- [x] **Step 2:** Run; FAIL. **Step 3:** Implement under impeccable. **Step 4:** PASS; run `tests/test_design_*.py`, `tests/test_eyebrow_above_heading.py`. **Step 5:** Commit: `golf: the league stamp and the sub-nav switch`

### Task B2: The join page with two sheets

**Files:**
- Modify: `games/golf/templates/golf/join.html`; `games/golf/routes.py::join` only if the template needs more context
- Test: `tests/test_golf_leagues.py`

Copy: one block per league in ordinal order with its name, its fee from the row, a one-line "who this sheet is for" placeholder Brad replaces (`Handicap`: "The Thursday crowd that came over from the old site."; `Pollyanna`: "The group that moved over from Splash."), and one `.btn-game` per league reading "Take a seat on the {name}"; a league the viewer is already on shows "You're on this sheet" and a link to its standings instead of the button. The rules card stays once, above both.

- [x] **Step 1:** Failing test `test_join_page_offers_both_sheets_and_marks_the_joined_one`. **Step 2:** FAIL. **Step 3:** Implement under impeccable. **Step 4:** PASS. **Step 5:** Commit: `golf: the join page offers both sheets`

### Task B3: The other sheet on the pick page

**Files:**
- Modify: `games/golf/routes.py::make_pick` (computes `other_sheets`), `games/golf/templates/golf/make_pick.html`
- Test: `tests/test_golf_leagues.py`, `tests/test_golf_pick_page.py`

**Interfaces:** `other_sheets: list[dict]` with `league` (the row), `pick` (`GolfPick | None` for this tournament in that league), `url` (`url_for('golf.make_pick', league=..., tournament_id=...)`); empty for a member of one league. Rendered after the facts list as one `golf-pick-line` per entry: "On the {name}: {Primary}, backup {Backup} · change" or "Nothing filed on the {name} yet · pick there".

- [x] **Step 1:** Failing test `test_pick_page_tells_a_member_of_both_what_the_other_sheet_holds` (both strings; a one-league member sees neither). **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS (and `tests/test_golf_cleanup.py`'s query counts: one extra query per other league at most). **Step 5:** Commit: `golf: the pick page names the other sheet` (also the A2 minors: `get_used_player_ids` docstring, `GolfPick.__repr__`)

### Task B4: The Roster's controls and the Back Office scope

**Files:**
- Modify: `games/golf/routes.py` (new `admin_commissioner`, `admin_move_line`; dashboard hides the meter for a league commissioner)
- Modify: `games/golf/templates/golf/admin/{users,dashboard,_book}.html`
- Test: `tests/test_golf_leagues.py`, `tests/test_golf_admin_route_matrix.py`, `tests/test_golf_admin_pages.py`

**Interfaces:**
- `POST /<league>/admin/commissioner/<int:user_id>` form `action=make|remove`, `@golf_platform_admin_required`; flips `is_admin` on that league's enrollment; 404 without a line.
- `POST /<league>/admin/move/<int:user_id>`, `@golf_platform_admin_required`; refuses (flash, nothing written) when a `GolfPick` exists for that enrollment's `(user_id, league_id)` in the season or the member already has a line in the other league; else sets `league_id` to the other league. Two leagues exist, so "the other" is `leagues()` minus this one.
- The Roster shows both controls to platform admin only (CSRF forms, POST); the book nav omits "Settle the Book" and the dashboard omits the API meter for a non-platform admin.
- `/admin/enrollments` (`core/admin/enrollments.py`): the golf precheck becomes `get_enrollment(user_id, house_league())` (today's `get_enrollment(user_id)` reports a Pollyanna-only member as already enrolled), `admin_enroll` keeps seating the house league, and the page says so beside golf ('Seats the Handicap Pay Sheet'); test in `tests/test_golf_leagues.py` (final review of PR A, Important #1).

- [x] **Step 1:** Failing tests: `test_platform_admin_appoints_and_removes_a_commissioner`; `test_move_refuses_once_a_pick_exists_or_the_other_line_is_held`; `test_move_switches_the_line`; `test_league_commissioner_cannot_post_to_the_other_league_or_settle_the_book` (Review Focus 4: a POST to `/golf/handicap/admin/update-payment/<id>` by the Pollyanna commissioner leaves `has_paid` False; `/golf/pollyanna/admin/process-results/<id>` 302s; the Pollyanna dashboard has no meter and no Settle the Book link).
- [x] **Step 2:** FAIL. **Step 3:** Implement under impeccable. **Step 4:** PASS; full suite + ruff. **Step 5:** Commit: `golf: commissioner toggle, the move, and the back office scope`. Carried from PR A's review: `test_admin_enrollments_seats_the_house_league_and_says_so` (registry `admin_enrolled` + `admin_enroll_note`), `test_platform_dashboard_counts_each_league_once` (one dashboard row per league).

### Task B5: Settle the Tab for golf (D4)

**Files:**
- Create: `games/golf/services/payment.py`
- Modify: `games/golf/routes.py::index` (the nudge in the sheet's context), `games/golf/templates/golf/index.html` (the card, after "Your line"), `games/golf/services/reminders.py::_picks_open_letter` (the fee footnote strip, the shape CFB's picks-open letter uses)
- Test: `tests/test_golf_payment_nudge.py` (new; mirrors `tests/test_cfb_payment_nudge.py`), `tests/test_payment_rails.py`

**Interfaces:**
- `payment_nudge_for(line, is_platform_admin) -> dict | None` (as built, Step 3): `None` when the viewer holds no line in the league, the line is paid, the viewer is platform admin or that line carries the pen, or `utils/payment.py::payment_rails` returns None (either rail blank or the Zelle number unparseable); otherwise the rails (Venmo link, Zelle number) plus `entry_fee = league.entry_fee` and `league_name = league.name`. Room surfaces only (never the join page or the lounge, ADR-056); `has_paid` stays admin-confirmed.
- The card is a `.golf-*` leaf on the league's sheet (impeccable, `games/golf/DESIGN.md`; red stays a deduction: "Unpaid" is the one red word); the letter's footnote strip names the league's fee and Brad's rails.

- [x] **Step 1:** Failing tests: `test_nudge_shows_for_an_unpaid_line_in_that_league_only` (Brad unpaid in Pollyanna, paid in Handicap: the Pollyanna sheet carries the card with Pollyanna's fee, the Handicap sheet does not); `test_nudge_hides_for_admins_commissioners_and_blank_rails`; `test_picks_open_letter_carries_the_leagues_fee_strip` (+ `test_no_member_self_mark_control`).
- [x] **Step 2:** FAIL. **Step 3:** Implement under impeccable (the gate takes the line, `payment_nudge_for(line, is_platform_admin)`, the CFB/Docket shape; the card is a `.golf-leaf` of the room's own, not the platform partial; `tab_block` gained `name=` so the strip names the league). **Step 4:** PASS; full suite + ruff; the D3 assertion audit in the PR body. **Step 5:** Commit: `golf: Settle the Tab per league`.
- [x] **Step 6:** Smoke the sheet, the four Back Office pages and the card on 5099 (done 2026-10-19 via /browse; report `.gstack/browse-reports/2026-10-19-1741-golf-prb/`, local, not committed); open PR B (draft). CodeRabbit clean; merged 2026-10-19 as db3cf0e (#271).

---

## PR C: the club

Branch `golf-two-leagues-c` from `main` after PR B.

### Task C1: The record's division

**Files:**
- Modify: `models/records.py` (`FinishDraft`, `SeasonFinish`, `seasons_on_record`, `finishes_for`, `champions`, `_check_board`, `record_season`)
- Modify: `games/golf/services/records.py`, `core/records/cli.py`, `core/records/routes.py`, `core/records/templates/records/index.html`, `games/golf/routes.py::_champions` / `_champion_line` (the anchor it builds at `routes.py:200` gains `-{division}`: review Q2)
- Create: `migrations/versions/<rev>_season_finish_division.py`
- Test: `tests/test_records.py`, `tests/test_records_cli.py`, `tests/test_records_page.py`, `tests/test_golf_records.py`, `tests/test_auth_avatar_phone.py` (the trophy)

**Interfaces:**
- `FinishDraft` gains `division: str = ''` (the league slug) and `division_name: str = ''` (the league's name, frozen).
- `SeasonFinish.division String(20) not null server_default ''`, `division_name String(60) not null server_default ''`; uniques become `('game','season_year','division','name')` and `('game','season_year','division','user_id')`; migration backfills golf rows to `'handicap'` / `'Handicap Pay Sheet'`.
- `seasons_on_record() -> list[tuple[str, int, str, str]]` (game, year, division, division_name); `finishes_for(game, season_year, division=None)` (`None` = every division); `_check_board` validates per division; `record_season` writes every draft's division; `reigning_champion_user_ids` unchanged (place-1 rows of the latest season per game, now one per league).
- Golf `season_finishes(year)` returns the drafts of every league with an enrollee, each tagged; a league with no enrollee is skipped and named on stderr by the CLI (Review Focus 5). `SeasonNotClosed` rules unchanged.
- `SEASON_ARCHIVES` keys become `(game, year, division)`: `('cfb', 2025, '')`, `('worldcup', 2026, '')`, `('golf', 2026, 'handicap')`.
- `/records`: a fold per (game, year, division) headed `game_name` + `division_name` when set; anchors `#board-{game}-{year}` gain `-{division}` when set; the roll of champions shows the division name under the game.

- [x] **Step 1:** Failing tests: `test_close_golf_writes_one_board_per_league` (two place-1 rows, both trophies via `reigning_champion_user_ids`); `test_records_show_prints_both_divisions` (review G3); `test_a_league_with_no_enrollee_is_skipped_and_named`; `test_check_board_validates_per_division` (Brad at place 1 in both divisions passes; the same user twice in one division fails); `test_records_page_folds_each_league` and the archive link `/golf/handicap/stats?season=2026`; the migration backfill asserted on Postgres (`@pytest.mark.postgres`).
- [x] **Step 2:** FAIL. **Step 3:** Implement; `migration-reviewer` on the migration; Postgres migration chain. **Step 4:** PASS; full suite both engines. **Step 5:** Commit: `records: a division per board (golf's two leagues)`

### Task C2: The lounge

**Files:**
- Modify: `games/golf/services/lounge.py` (`build_lounge_context`), `games/golf/templates/golf/lounge/{_panel_pre,_panel_live,_panel_post,_conv_card}.html`
- Test: `tests/test_golf_lounge.py`, `tests/test_lounge_accent_firewall.py`, `tests/test_lounge_cta_parity.py`

**Interfaces:** `build_lounge_context(user, state)` adds `league` (slug of the viewer's league: `enrollments_for` lowest ordinal, else `house_league()`), `league_name`, and `other_lines: list[dict(name, place, money, url)]` for a member of more than one league; `total_enrolled` counts every golf seat (the club's number), the board and `mine` are the viewer's league's. Every `url_for('golf.…')` in the four partials passes `league=g.league`. Pre-panel copy under impeccable names both sheets in one line ("Two sheets this year: the Handicap and the Pollyanna. Take a seat on either."); the ask stays one `.hl-cta` to `golf.join`.

- [x] **Step 1:** Failing tests: `test_lounge_panel_is_the_viewers_league_and_names_the_other_for_brad`; `test_lounge_links_carry_the_league`; the firewall and CTA parity locks keep passing. **Step 2:** FAIL. **Step 3:** Implement under impeccable (root `DESIGN.md` headliner system + `games/golf/DESIGN.md` §8.24). **Step 4:** PASS. **Step 5:** Commit: `golf lounge: the viewer's sheet, the other sheet named`

### Task C3: Announce audiences per league

**Files:**
- Modify: `core/admin/announce.py` (`_golf_recipients(active_only, league_slug=None)`, audience keys `golf`, `golf:handicap`, `golf:pollyanna`, labels from `leagues()`, validation and `audience_label`), `core/admin/templates/admin/announce.html` only if the picker needs structure
- Test: `tests/test_announce_blocks.py` or `tests/test_announce_drafts.py` (whichever holds the audience tests), `tests/test_golf_leagues.py`

**Interfaces:** `resolve_recipients(audiences, active_only)` accepts `golf:<slug>`; `golf` alone is every league; the Announcement row stores the keys as today (comma-joined); the Tribune files golf issues as before.

- [x] **Step 1:** Failing test `test_announce_golf_audiences_are_per_league_or_all`. **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit: `announce: a golf audience per league`

### Task C4: Docs, ADR, memory

**Files:**
- Modify: `ARCHITECTURE_DECISION_LOG.md` (ADR-075: two leagues in one game; options: two registry slugs, one slug with a league dimension; choice and rationale from Part 1)
- Modify: `games/golf/DESIGN.md` (§3 the room's URL carries the league; §9 invariants: every league read is league-scoped, the URL is the league, the usage key is per league, the commissioner is the league enrollment, Settle the Book is platform-only, the record is per division; the PR B reconciliations: §6.11 and §7.14 (Settle the Tab is the room's own `.golf-leaf` on The Sheet since PR B, not the platform partial; the entry fee only, no penalties), §7.11 (the small line is the league's name beside the season, the switch pill `.subnav-pill--switch` for a member of both, the Schedule pill's `?league=`), §7.12 (the two-sheet join page, `LEAGUE_BLURBS`, "Take a seat on the {name}"), §7.8 (the other-sheet line under the facts), §8.20 (the Roster's controls, the commissioner's four-leaf book and tab-only dashboard), the §9 "The name" bullet)
- Modify: `CLAUDE.md` (golf bullet: two leagues, `/golf/<league>/`, `flask golf league list|set`, `import-legacy --league`; records bullet: division; the `records close golf` line; the Payment rails bullet: golf's per-league gate, the commissioner exclusion, `tests/test_golf_payment_nudge.py`)
- Modify: `ARCHITECTURE_DECISION_LOG.md` ADR-056's row (the rails now cover the Pay Sheet, per league)
- Modify: `docs/golf-pickem-launch-prep-roadmap-2026-06-30.md` (the prod import runbook adds `--league handicap`)
- Test: `tests/test_golf_design_doc.py`, `tests/test_design_*.py`

- [x] **Step 1:** Write the rows and sections; run `tests/test_golf_design_doc.py`; PASS. **Step 2:** Commit: `docs: ADR-075 two golf leagues; DESIGN.md §9; CLAUDE.md`.
- [ ] **Step 3:** Open PR C; CodeRabbit clean; merge. Deploy with `./deploy.sh` (pre-migrate dump runs; `32cd68a3e8ea` seeds both leagues into empty golf tables, `e79308879acb` files the record's existing golf rows under division `handicap` (prod has none) and every other game's under `''`); post-deploy: `systemctl status`, journal scan, `ps -o args= -C gunicorn`, then `flask golf league list` on the box shows both rows.

### Verification (end to end)

1. `ENVIRONMENT=testing venv/bin/python -m pytest tests/ -n auto --dist loadfile` on SQLite and with `TEST_DATABASE_URL=postgresql:///ccc_test`; `venv/bin/ruff check .`; the migration chain on `ccc_migrations_test`.
2. Dev server on 5099 against `ccc_local` (migrated), `GOLF_FAKE_NOW` at a 2026 Thursday: as Brad (both leagues) pick the same golfer in each; the two sheets, boards, scorecards and Record Rooms show only their own line; the sub-nav switch; the join page; the Pollyanna commissioner's Back Office has no Settle the Book and cannot reach Handicap pages; `flask records close golf 2026` on the local import writes two boards (after a `--league pollyanna` import of a copy, or one board with the empty league named).
3. `flask golf import-legacy ~/… --league handicap --dry-run` on the local archive: oracle 0 diffs.
4. `flask club desk --dry-run` is untouched (golf's reminders are not on the desk); `flask golf sync-run --mode remind` with `GOLF_FAKE_NOW` in a reminder window prints two letters for Brad, one per league.

---

