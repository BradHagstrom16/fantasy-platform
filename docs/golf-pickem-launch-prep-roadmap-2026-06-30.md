# Golf Pick 'Em — Pre-Launch Hardening Roadmap

## Context

Golf Pick 'Em (`games/golf/`, registry `status='coming_soon'`, `launch_label='2027'`) is a port of the
standalone reference app at `/Users/bhagstrom/Golf_Pick_Em`. A read-only pre-launch audit
(`docs/golf-pickem-platform-code-audit-2026-06-30.md`) found ~40 findings — 13 must-fix — where the
platform port silently diverged from the battle-tested standalone or violated platform conventions.
Left unfixed, Golf would launch with wrong Zurich scoring, no cut/DQ penalty pot, Zurich picks skipped
entirely at sync, projections underreported at majors, standings/emails polluting non-Golf users,
duplicate reminders, no production automation, and near-zero test coverage.

Three exploration agents verified every finding against live code, mapped exact standalone port
sources (file/line), and confirmed the CFB pre-launch precedent (one scoped PR per area, CodeRabbit on
each). Brad ruled on the open questions (recorded as ADR-033..036):

- **Zurich team-event scoring → FULL payout** (both partners get the full team payout). Matches the
  standalone's actual live code + UI; removes the platform's incorrect ÷2. Only stale docs said ÷2.
- **Major missed-cut/DQ penalty → PORT AS-IS** ($15/incident side pot, live-refreshed, admin-tracked).
- **Scope → FULL ROADMAP to launch**, executed as scoped PRs across sessions; first PRs = correctness.
- **Standings → Golf-enrollment-scoped** (stop listing every platform user).

**Outcome:** Golf reaches functional parity with the proven standalone, conforms to platform
conventions (avatars, enrollment-scoped mail, config-plumbed keys, season-scoping, CCC branding),
gains production automation + real test coverage, and is UI-elevated to the DESIGN.md bar before the
registry status flips to `'open'`.

## Execution model

- Each PR below is one session, carried through its full CodeRabbit approval cycle to merge
  (per `feedback_cr_approval_sessions`); UI PRs also load `/impeccable`.
- Branch off `main` as `golf/launch-prep-*` topic branches. TDD: write the named tests first
  (`superpowers:test-driven-development`), then implement.
- Record Brad's four rulings as entries in `ARCHITECTURE_DECISION_LOG.md` (the platform's binding-
  decision log) as the first commit of PR 1.
- No `tests/conftest.py` exists — every test file defines its own `app`/`client` fixtures
  (copy the shape from `tests/test_golf_auto_enroll_removed.py`). Flip status in tests via
  `set_status(monkeypatch, 'golf', 'open')` from `tests/_registry_helpers.py`. Admin auth seeds
  `sess['_user_id'] = user.auth_id` (never `str(user.id)`).
- All new columns via Flask-Migrate (`flask db migrate` → **review the generated file** → `db upgrade`),
  committed with the model change.

---

## Execution strategy (multi-session)

**Timeline.** It is Jun 2026; Golf launches **Jan 2027** — ~7 months of runway. No schedule pressure;
optimize for correctness and clean handoffs, not speed. The failure mode to avoid is batching too much
into one session and losing review quality — **one PR per session, clear between each.**

**Now vs. later.** PRs 1-6 (backend correctness, ops, conformance) can all be done **now**, in any
near-term window, independent of World Cup being live and CFB launching: Golf stays behind the
`coming_soon` gate (interior routes unreachable), and the code is isolated (own blueprint, `golf_`
tables, own tests) with only additive/benign shared-file touches. They land on `main` invisibly to
users. **Phase U (design elevation) + Phase L (launch ops) are deferred** to near the Jan 2027 launch.
Each PR must keep the full shared suite (WC + CFB) green — the only cross-game discipline.

**Step 0 (do first, one small commit to `main`):** relocate this roadmap into the repo at
`docs/golf-pickem-launch-prep-roadmap-2026-06-30.md` so it is version-controlled and survives clears;
its `- [ ]` checkboxes become the resume signal. Record the 4 rulings in `ARCHITECTURE_DECISION_LOG.md`
in the same commit.

**Durable state each new session reads to resume** (nothing relies on prior session context):
- the repo roadmap (checkboxes = progress) + `docs/golf-pickem-platform-code-audit-2026-06-30.md`
- `ARCHITECTURE_DECISION_LOG.md` (the rulings) + the golf memory files

**Sequencing:**
- **PR 1 → 2 → 3 strictly sequential** — shared scoring/sync core (`models.py`, `resolve_pick`,
  `sync.py`); each merges to `main` before the next starts → no cross-PR conflicts.
- PR 4/5/6 are mutually independent (low collision); still run one-per-session for simplicity.
- Phase U = one session per screen cluster (mirror CFB's A1-A6 + admin desk).
- PR 3 (penalty) is self-contained and the best split candidate if a session runs long
  (3a backend: model/flagging/live-refresh/CLI/migration + tests; 3b UI: admin payments/standings/badges).

**Per-session ritual:**
1. Read the repo roadmap + audit + `ARCHITECTURE_DECISION_LOG.md` + golf memory.
2. `git checkout main && git pull`; branch `golf/launch-prep-<area>`.
3. TDD — write the named tests first, implement, full suite green (~1467 + new).
4. Carry through the full CodeRabbit cycle to merge (`--merge --delete-branch`).
5. Flip the checkbox in the repo roadmap; add a one-line memory note; clear.

**Live parity oracle (strong recommendation, not time-gated).** The standalone holds known-good
results for the full 2026 PGA season. After PR 1-3 merge, run the platform sync over those 2026
tournaments and diff its scoring/penalty against the standalone's stored outputs — a real-data answer
key available anytime (validating live during the remaining 2026 events through ~Aug is a bonus
realism check). Best launch de-risker available, stronger than synthetic tests alone.

**Suggested calendar (loose, ~1-2 PRs/week with slack — ~10-14 sessions total):**
- **Jun-Jul:** PR 1-3 (correctness) + shadow-validate against live 2026 tournaments.
- **Jul-Aug:** PR 4-6 (ops, conformance, cleanup).
- **Sep-Nov:** Phase U (UI elevation).
- **Dec:** production rehearsal (mirror `docs/production-launch-test-script.md`) on a sandbox season.
- **Jan 2027:** flip `registry` status → `'open'`, seed the 2027 schedule, enable `golf-*` timers.

---

## PR 1 — Scoring & resolution correctness  *(FIRST — highest-risk data integrity)*

Files: `games/golf/models.py`, `games/golf/services/sync.py` (`process_tournament_picks`),
`games/golf/templates/golf/{index,tournament_detail,my_picks}.html`.

- [x] **Record the 4 rulings in `ARCHITECTURE_DECISION_LOG.md`** (Zurich full payout, penalty port,
      full-roadmap scope, golf-scoped standings).
- [x] **Zurich → full payout.** Delete the three `if self.tournament.is_team_event: earnings = earnings // 2`
      blocks (`models.py:504-506`, `533-535`, `get_current_earnings` `572-573`). Update the module
      docstring (`models.py:14`, "team events earn half") and the two stale standalone-parity comments.
      Leave the WD branches ("do NOT modify") untouched — only the halving is removed.
- [x] **Document + test multiplier precedence.** With halving gone, only the major ×1.5 remains
      (`int(earnings * 1.5)`). Add a comment stating the precedence and a test locking major math even
      though no 2026 event is both major and team.
- [x] **Transactional reprocessing.** Rewrite `process_tournament_picks` (`sync.py:641-708`) to mirror
      the standalone `process_tournament_results()` (`Golf_Pick_Em/app.py:1208-1245`): per-pick
      `with db.session.begin_nested():` savepoint, delete usage for **{primary, backup, old-active}**
      inside the savepoint (subsumes the too-narrow `clear_resolution`, models.py:406-429), call
      `resolve_pick()` + `enrollment.calculate_total_points()` inside it, `raise` on unresolved to roll
      back that pick only, single outer `commit()`. Fixes the current "no rollback anywhere → partial
      clears persist + stale enrollment totals" defect.
- [x] **Postgres-safe usage insert.** Replace `from sqlalchemy.dialects.sqlite import insert` +
      `.on_conflict_do_nothing()` (`models.py:19`, `546-551`) with a Postgres-safe upsert
      (`dialects.postgresql.insert`) or an ORM existence-check. **Verify first** by running
      `resolve_pick` against `ccc_local` (Postgres). Grep `games/golf/` for other `dialects.sqlite`
      imports and fix any.
- [x] **Live early-WD backup activation.** Port `is_backup_activated()` + `is_wd_before_round_2()`
      (`Golf_Pick_Em/models.py:632-655`, `384-393`); route `get_current_earnings()` and the active-
      player display in `index.html` (:136,:156), `tournament_detail.html` (:145), `my_picks.html`
      through it so a pre-R2 primary WD shows the activated backup live, not the dead primary.

Tests (`tests/test_golf_scoring.py`): `test_resolve_pick_primary_finishes`,
`test_resolve_pick_primary_wd_before_r2_backup_finishes`, `test_resolve_pick_primary_wd_after_r2`,
`test_resolve_pick_both_wd_before_r2`, `test_calculate_total_points_team_event_rule` (full payout),
`test_clear_resolution_removes_old_usage`, reprocess failure-isolation (one bad pick doesn't corrupt
others' totals), backup-activation display.

---

## PR 2 — Sync & API ingestion correctness  *(CRITICAL — Zurich picks currently skipped)*

Files: `games/golf/services/sync.py`, `games/golf/constants.py`, `games/golf/utils.py`,
`games/golf/cli.py`.

- [x] **Team-row flattening [CRITICAL].** Port `_iter_player_rows()`
      (`Golf_Pick_Em/sync_api.py:434-463`); route the field, live, withdrawals, and results loops +
      the `leaderboard_lookup` build (`sync.py:588-590,595,734,804`, etc.) through it. Team rows
      inherit team-level fields (incl. `earnings`) per member — consistent with full-payout ruling.
- [x] **ISO timestamp parsing.** Port the 3-format `_parse_tee_time_timestamp`
      (`Golf_Pick_Em/sync_api.py:366-407`: Mongo EJSON, ISO 8601, epoch-ms) for the `teeTimeTimestamp`
      field, and route schedule `date.start` through it (SlashGolf migrated to ISO — currently
      silently skips events).
- [x] **Major purse estimates + effective purse.** Replace the `None` major values in
      `constants.py` `PURSE_ESTIMATES` with the real numbers from `Golf_Pick_Em/models.py:44-78`
      (Masters 22.5M, PGA 19M, U.S. Open 21.5M, The Open 17M, + `DEFAULT_PURSE`). Add `effective_purse`
      / `purse_is_estimate` properties on `GolfTournament` and `_backfill_purse_from_schedule()` called
      in results finalization when `not tournament.purse`.
- [x] **Major multiplier on live projections.** Add `is_major=False` to
      `utils.calculate_projected_earnings()` (`utils.py:105`), apply `×1.5` after base calc, and pass
      `tournament.is_major` from the live sync + any route/template projection call sites.
- [x] **Position normalization.** Port `normalize_position()` (`Golf_Pick_Em/sync_api.py:138-166`);
      apply at every `final_position` write (results `sync.py:623`, withdrawals, live).
- [x] **Schedule seeding.** Add `flask golf seed-schedule` (locked 2026 list + real major purses,
      idempotent upsert on name+season) mirroring `Golf_Pick_Em/import_tournaments.py`, plus
      `flask golf force-schedule-sync` (bypasses the Monday gate). Current `sync_schedule()` is
      update-only, so a fresh season has zero tournaments.

Tests (`tests/test_golf_sync.py`): `test_sync_field_flattens_team_rows`,
`test_sync_results_flattens_team_rows`, `test_sync_schedule_parses_iso_date_start`,
`test_live_projection_applies_major_multiplier`, position-normalization, seed-creates-events.

---

## PR 3 — Major missed-cut/DQ penalty system  *(audit #1 must-fix)*

Faithful port of the standalone's $15/incident side pot. Files: `games/golf/models.py`,
`games/golf/services/{sync,reminders}.py`, `games/golf/cli.py`, `games/golf/routes.py`,
`games/golf/templates/golf/{index,my_picks,tournament_detail,admin/payments}.html`, migration.

- [x] **Model.** Add `GolfPick.penalty_triggered` (Boolean) + `GolfEnrollment.penalty_paid` (Integer),
      `PENALTY_PER_INCIDENT = 15`, and `penalty_owed(season)` / `penalty_outstanding(season)` derived
      methods (owed = flagged picks × $15; outstanding = max(0, owed − paid)). Sources:
      `Golf_Pick_Em/models.py:38,99,140-154,437`. Migration.
- [x] **Flag at finalization.** In `resolve_pick()`, set `penalty_triggered` = major AND active
      result status ∈ {cut, dq} (`Golf_Pick_Em/models.py:584-592`). Re-derived (True/False) every
      resolution — no separate clear.
- [x] **Live refresh.** Port `refresh_live_penalty()` (`Golf_Pick_Em/models.py:657-674`); call it in
      the live-leaderboard sync when `tournament.is_major`; add `flask golf refresh-live-penalties`.
- [x] **Admin payments.** Extend `admin/payments.html` + its AJAX endpoint with owed / paid /
      outstanding per user and pot totals (`Golf_Pick_Em/app.py:955-1016`).
- [x] **Standings + badges.** Add the penalty pot to the entry-total math on `index.html` and penalty
      badges on `index`/`my_picks`/`tournament_detail` (gated `is_major and results_finalized`).
      (Recap email omits penalties, matching the standalone.)

Tests: `test_resolve_pick_major_cut_penalty` (+ live-refresh flip, owed/outstanding math).

---

## PR 4 — Ops hardening & automation  *(mirrors CFB ops-hardening PR #71)*

Files: `config.py`, `games/golf/cli.py`, `games/golf/services/{reminders,sync}.py`, `deploy/`,
`tests/test_golf_automation.py`, `AGENTS.md`, `CLAUDE.md`.

- [x] **Config-plumb the API key.** Add `SLASHGOLF_API_KEY = os.environ.get('SLASHGOLF_API_KEY', '')`
      to `config.py` `Config` (next to the unused `SLASHGOLF_API_HOST`, ~line 50); read via
      `current_app.config` in `cli.py:41` + `routes.py:780`. Add a test locking the key in `Config`
      (the `MAIL_FROM_ADDRESS` config-plumbing gotcha).
- [x] **Season-scope automation queries.** Add `season_year` filters to `get_active_tournaments`,
      `get_recently_completed_tournaments`, `get_tournaments_pending_finalization`,
      `get_upcoming_tournaments_window` (`sync.py:889-929`).
- [x] **Reminder de-dup.** Add `GolfTournament.last_reminder_type` (migration) + the `REMINDER_ORDER`
      skip-current-or-later-tier check, recording tier only after a successful send
      (`Golf_Pick_Em/models.py:216`, `send_reminders.py:1076-1128`).
- [x] **Systemd units.** Author `deploy/golf-{schedule,field,live,results,remind}.{timer,service}`
      mirroring the `cfb-*`/`worldcup-*` structure: `Type=oneshot`, `User=deploy`,
      `EnvironmentFile=.env`, `Environment=ENVIRONMENT=production`, inline-TZ `OnCalendar` (no
      `TimeZone=` directive), `Persistent=true`. Cadence per the audit §7 table.
- [x] **CLI safety + docs.** Add `remind` to `sync-run --mode` (or document `flask golf remind`);
      gate/dev-only the unsafe `--mode all`; make the `os.makedirs` log-dir init lazy (not at import);
      document the golf command block in `AGENTS.md` + `CLAUDE.md`.

Tests: `test_reminder_dedup_skips_sent_tier`, `test_get_used_player_ids_current_season_only`,
season-scoping, config-key lock.

---

## PR 5 — Routes, standings & email conformance  *(mirrors CFB §7 conformance)*

Files: `games/golf/routes.py`, `games/golf/services/reminders.py`,
`games/golf/templates/golf/{tournament_detail,admin/override_pick}.html`, `README.md`.

- [x] **Golf-scoped standings.** Remove the append-all-platform-users block (`routes.py:181-193`);
      show only current-season `GolfEnrollment` rows.
- [x] **Enrollment-scoped mail.** Replace `User.query.all()` (`reminders.py:240,581,848`) with
      `GolfEnrollment.query.filter_by(season_year=SEASON_YEAR, ...)` — mirror
      `games/worldcup/services/notifications.py`.
- [x] **Avatars.** Render `user.get_avatar()` before the display name on `tournament_detail.html`
      (:116-117) and any other standings table missing it (mirror `worldcup/leaderboard.html`).
      (index.html already had it; admin tables are not player standings.)
- [x] **Admin override hardening [HIGH].** Server-side validate override POST against field membership
      + season usage (excluding the pick's own players) (`routes.py:652`); remove the selected pick's
      players from the GET `used_player_ids` (`routes.py:733`); `db.session.rollback()` on existing-
      pick validation failure (`routes.py:425`).
- [x] **Admin branding + email safety.** Replace hardcoded `ADMIN_EMAIL="bhagstrom0@gmail.com"` /
      `ADMIN_NAME="Sun Day Regrets"` (`reminders.py:57-58`) with `current_app.config.get('ADMIN_EMAIL')`
      + CCC branding; `markupsafe.escape` dynamic values interpolated into email HTML
      (`reminders.py:285,707,761-762,778`).
- [x] **Complete-vs-finalized gating.** Gate `tournament_detail.html` final/earnings mode on
      `results_finalized` (:104), not `status=='complete'`.
- [x] **README status.** Fix `README.md:68-72` (Golf/CFB shown "Live" but registry says
      `coming_soon`) to match `games/registry.py`.

Tests: `test_admin_override_rejects_used_or_non_field_player`,
`test_admin_override_requires_confirm_for_complete`, standings/email scoping.
**Confirm-gate decision:** the standalone's confirm-before-reresolve preview is a
new interaction surface (out of scope for this conformance PR), deferred to a later
hardening/UI slice; `test_admin_override_complete_tournament_reresolves_immediately`
reconciles the roadmap's named `test_admin_override_requires_confirm_for_complete`
by locking the current one-step re-resolve.

---

## PR 6 — Cleanups & test backfill  *(mirrors CFB §9)*

Files: `games/golf/models.py`, `games/golf/services/sync.py`, `games/golf/routes.py`.

- [x] Remove dead code: `GolfTournamentField.is_alternate` (migration), unused `get_tournament()` /
      `_update_pick_deadline_from_leaderboard()` / `get_just_completed_tournament()`, redundant
      `send_admin_field_alert` import (`sync.py:519`).
- [x] Add `joinedload`/route DTOs for the standings + tournament-detail N+1s (`routes.py:163,305`).
- [x] Short-circuit `sync_tournament_results()` when already `results_finalized` (unless forced).
- [x] Backfill any remaining tests from the audit's recommended suite
      (`test_update_status_from_time_never_auto_completes`, availability-rejection tests, etc.).

---

## Phase R — Legacy retirement audit  *(2026-08-24; the standalone's 2026 season is over)*

The parity audit that closed out the PythonAnywhere app: addendum in
`docs/golf-pickem-platform-code-audit-2026-06-30.md` (§"2026-08-24 addendum"). Brad's rulings, binding:
**(1)** import the full 2026 season into the `golf_*` tables as an archived season; **(2)** import the
13 members without a platform account carrying their Werkzeug password hashes, attach the 5 email
matches, flag the one username collision for Brad; joining 2027 stays self-serve; **(3)** stay on the
FREE SlashGolf tier and keep the legacy cadence (three live reads a day during play); **(4)** Phase U
starts ~mid-Sep 2026 once CFB/Docket launch week settles.

- [x] Legacy DB archived: `~/Golf_Pick_Em/archive/golf_pickem_2026_final.db` (+ a gitignored copy in
      `instance/`), sha256 `09f397c6eafa5989f3130b6f4f59e15f93621a6ce195f59608fa4ec584199864`, matching
      the PythonAnywhere original; `env_config.sh` (the API key) beside it, 0400. Scheduled-task
      cadence recorded; web app left to expire.
- [x] Audit bugs fixed: "team events half" copy (ADR-033), the un-season-scoped reminder lookup, the
      hardcoded "Golf 2026" subnav label.
- [x] Timers retuned to the free-tier cadence + locked (`tests/test_golf_timers.py`): live noon + 4 PM,
      new `golf-live-wd` at 8 PM (`live-with-wd`), results Sun 20:30 / Mon 08:00 / Mon 18:00 — ~115
      calls/mo of 250.

## Phase I — Import the 2026 season  *(next; `feat/golf-legacy-import`)*

`flask golf import-legacy PATH [--season 2026] [--dry-run] [--link L=P]... [--rename L=N]... [--no-verify]
[--force]` + `flask golf verify-legacy [PATH]` over a new `games/golf/services/legacy_import.py` (the
`seed_schedule` precedent, not the CFB JSON ledger — the schema is a 1:1 port). No migration.

- [ ] Service + CLI: read-only sqlite open; natural-key upserts (never explicit ids); user matching by
      folded email, collision → exit 1 before any write; attached users never modified; `GolfEnrollment
      (season_year=2026)` carries `total_points`/`has_paid`/`penalty_paid` but **not** `is_admin`;
      `recap_email_sent` forced True (weeks 1–7 are 0 in the legacy DB — `process_tournament_picks`
      would mail a January recap); result-status strings verbatim (Sony/Zurich casing anomalies).
- [ ] Parity oracle: re-run `resolve_pick()` + `calculate_total_points()` over every 2026 pick inside a
      SAVEPOINT that is always rolled back, diff the five pick fields + totals + the usage set against
      the legacy values; default-on in `import-legacy`, standalone as `verify-legacy`; never calls
      `process_tournament_picks`.
- [ ] Tests `tests/test_golf_legacy_import.py` (+ `_golf_legacy_fixtures.py` writing the legacy DDL):
      matching/collision/link/rename, hash carried verbatim + login, verbatim pick fields, placeholder
      adoption after `seed_schedule`, idempotent re-run, oracle zero-diff + perturbation cases,
      never-commits-or-emails.
- [ ] ADR-055; `CLAUDE.md` Commands lines + "never `seed-schedule` 2026 after the import" (3 legacy
      names differ from `TOURNAMENTS_2026`).
- [ ] Prod runbook: scp the archive DB to `/home/deploy/` (outside the checkout) → deploy → read-only
      row count (expect 0) → `--dry-run` (5 attach / 13 create / 1 collision / 0 diffs) → Brad resolves
      `brockhusk` (`--link` or `--rename`) → real run → `verify-legacy` → re-run for 0 created / 0
      changed → `SEASON_YEAR=2027` in `.env` + restart (so 19 imported members don't get a navbar link
      into a `coming_soon` room) → one imported member logs in with their old password.

## Phase U — UI elevation to the DESIGN.md bar  *(starts ~mid-Sep 2026; one session per cluster)*

The 2026-08-24 audit found the rules engine, sync and email at parity but the **surfaces** behind the
legacy app. Every cluster reads top-level `DESIGN.md` + `games/golf/DESIGN.md`; the legacy
`Golf_Pick_Em/DESIGN.md` ("The Greenside Ledger") is reference, not doctrine — the room is CCC-branded.
Ordered by user impact.

- [ ] **U0** Author `games/golf/DESIGN.md` (does not exist yet): Golf palette (Augusta green `#006747` +
      gold `#b8993e`), accent-rank, register, named primitives incl. the pill vocabulary (Backup ↳
      replaces, Override 👑, Penalty $15, Unpaid, Projected/Banked, Used). Subnav pills **Standings ·
      Schedule · Results · Stats · My Scorecard · Admin**.
- [ ] **U1 Standings** — pills, legend bar, League Rules card, next-pick thread card during live play,
      shared-rank ties (the platform's competition-rank convention), mobile card rendering,
      projected-vs-banked.
- [ ] **U2 Make pick** — burn-% per option (port `stats.remaining_pct_map`), punctuation-normalized
      search (`jj` → `J.J.`), two-way mutual exclusion, "N available · M used", empty-field state; CCC
      email chrome for the four emails (retire the standalone green/gold).
- [ ] **U3 Tournament detail** — Your Pick card, Penalties Assessed card, "updates at noon, 4 PM and
      8 PM Central · last synced" banner, competition ranking, "Didn't pick (N)" `<details>`, team/major
      stakes bands, legend, mobile cards.
- [ ] **U4 Member Scorecard** — `/golf/member/<id>` replacing self-only `my_picks` (keep `/golf/my-picks`
      as the redirect alias): tiles (Rank ordinal, Total, In the Money, Golfers Used, Overrides, Best
      Pick, Missed Cuts at Majors + pot status), idle-golfer muting, Used Golfers card, Commissioner's
      Ledger, member switcher, server-side pick secrecy; **season selector** (2026 archive ↔ current).
- [ ] **U5 Stats Hub** — port `Golf_Pick_Em/stats.py` → `games/golf/services/stats.py` (+ its ~50
      tests): Season Race SVG (server-side geometry) + "Play the season" replay JS
      (`games/golf/static/js/season-replay.js`, `burn-list.js` — the blueprint's `static/` dir doesn't
      exist yet), superlatives, Form Guide, Burn List, Still on the Board; reduced-motion + SR mirror
      table preserved; season-aware so 2026 is browsable.
- [ ] **U6 Admin** — API-usage meter (parse `api_calls.log` against the 250 budget),
      confirm-before-reresolve gate on override (deferred from PR 5), admin tables on `.table-golf`.
- [ ] **U7 Season archive / champion** — 2026 champion + final board; lounge integration
      (`lounge_state`/`lounge_context`) as a separate decision.
- [ ] Bundled: `lazy='dynamic'`/`backref` cleanup; season-scope `clear_resolution`
      (`models.py:501-507`); 2026 result-status casing in display code.

## Phase L — Launch

- [ ] `TOURNAMENTS_2027` in `constants.py` (+ majors/team flags) and a 2027 `SEASON_CUTOFF_DATE` —
      `seed_schedule` raises for any other year until then.
- [ ] Flip `games/registry.py` golf `status` `'coming_soon'` → `'open'` (+ `launch_label`). For
      pre-launch local testing use `git update-index --skip-worktree games/registry.py` (never commit
      the flip); tests use `set_status`.
- [ ] Prod `.env`: `SLASHGOLF_API_KEY` (from the archived `env_config.sh`), `SYNC_MODE=free`,
      `SEASON_YEAR=2027` (set at Phase I). `flask golf seed-schedule` for 2027 on prod.
- [ ] Enable + start the six `golf-*` timers (`systemd-analyze calendar` each); confirm the monthly
      call estimate stays ≤ 250 against the U6 meter.
- [ ] Production verification pass (mirror `docs/production-launch-test-script.md`): seed → picks →
      live sync → results → penalty → standings.

---

## Verification

- **Per PR:** `ENVIRONMENT=testing venv/bin/python -m pytest tests/test_golf_*.py -q` (new modules
  must pass); full suite green before merge. No linter/pyright — pytest is the gate.
- **Scoring (PR 1-3):** run the dev server against `ccc_local` (Postgres, per
  `feedback_local_postgres_not_sqlite`); create a team-event + a major tournament with hand-seeded
  results and confirm full-payout Zurich, backup activation, and a triggered penalty render correctly.
  Confirm the Postgres usage-insert path via a real `resolve_pick` (not SQLite).
- **Sync (PR 2):** exercise `flask golf sync-run --mode {schedule,field,live,results}` in dev; verify a
  Zurich team row creates per-player field/result rows and an ISO `date.start` updates (doesn't skip).
- **Ops (PR 4):** `systemd-analyze calendar '<OnCalendar>'` on the droplet for each timer; dry-run the
  reminder dedup by advancing `CFB_FAKE_NOW`-style time / re-invoking `flask golf remind`.
- **UI (Phase U):** browser smoke each golf screen (chrome-devtools `emulate "375x812x2,mobile,touch"`
  for true mobile width) after `set_status`/skip-worktree flip to `'open'`.

## Progress log

- **2026-06-30** — Roadmap + audit committed; ADR-033..036 recorded.
- **2026-06-30** — **PR 1 (scoring & resolution correctness) merged (#103).** Zurich full payout;
  fixed a latent Postgres crash in `resolve_pick` (sqlite-dialect insert → every resolve threw and was
  silently swallowed → zero scoring on prod); transactional per-pick savepoint reprocessing; live
  early-WD backup activation. +12 scoring tests; suite 1479; CodeRabbit APPROVED.
- **2026-07-01** — **PR 2 (sync & API ingestion correctness) merged (#104).** `_iter_player_rows`
  team-row flattening across field/live/withdrawals/results (Zurich picks were skipped everywhere);
  3-format ISO `_parse_tee_time_timestamp` (+relaxed-EJSON `$date`) routed through schedule `date.start`;
  real major purses + `effective_purse`/`purse_is_estimate` + `_backfill_purse_from_schedule`;
  `is_major` ×1.5 on live projections (and fixed a self-caught double-apply in `get_current_earnings`);
  `normalize_position` at every `final_position` write; `flask golf seed-schedule` (purse-0 rows,
  placeholder `api_tourn_id` linked by name at first `sync_schedule`) + `force-schedule-sync`.
  +43 tests (test_golf_sync.py); suite 1479→1522; verified on `ccc_local` Postgres; CodeRabbit APPROVED
  (2 review rounds).
- **2026-07-01** — **PR 3 (major missed-cut/DQ penalty side pot, ADR-034) merged (#105).** Faithful
  port of the $15/incident side pot: `GolfPick.penalty_triggered` + `GolfEnrollment.penalty_paid`,
  `penalty_owed`/`penalty_outstanding` (season-scoped), `resolve_pick()` flagging (re-derived every
  resolution; cleared on failed/skipped resolution), `refresh_live_penalty()` (handles active AND
  complete-but-unresolved majors via the widened `is_backup_activated`), live-sync refresh (isolated
  try/except so it can't mask the leaderboard sync) + `flask golf refresh-live-penalties`, admin
  payments owed/paid/outstanding + pot totals (AJAX rejects fractional penalty), prize-pool footer +
  penalty badges (shared `_penalty_badge.html` macro, gated live-OR-finalized major via
  `show_penalty_badge`). Migration `683bff36f66e` (server_default backfill; round-tripped + resolve
  smoke on `ccc_local` Postgres). +41 tests (test_golf_penalty.py); suite 1522→1563; visual smoke of
  all four surfaces; CodeRabbit APPROVED (3 review rounds). **Next: PR 4 (ops hardening & automation).**
- **2026-07-01** — **PR 4 (ops hardening & automation) merged (#106).** Config-plumbed
  `SLASHGOLF_API_KEY` (cli.py + routes.py read via `current_app.config`; base-`Config` env line);
  season-scoped the four automation queries via a shared `_resolve_season_year` helper; reminder
  de-dup (`GolfTournament.last_reminder_type` + `REMINDER_ORDER` skip-current-or-later, recorded only
  after a successful send — ported from the standalone; migration `1dbde6204bc2`, nullable String(10),
  round-tripped on `ccc_local` Postgres); 10 systemd units
  `deploy/golf-{schedule,field,live,results,remind}.{timer,service}` (inline-TZ `OnCalendar`, cadence
  per audit §7; **field timer is `Persistent=false`** so a downtime replay can't fire "Picks Are Open"
  post-deadline — deliberately unlike the other golf timers); CLI safety (`remind` mode short-circuits
  before the API client → API-key-free; `--mode all` disabled when `ENVIRONMENT=production`; lazy +
  fault-tolerant API-call file logging via `GOLF_API_LOG_DIR`); refreshed the CLAUDE.md Golf CLI block.
  +12 tests (test_golf_automation.py); suite 1563→1575; season-scoping verified on `ccc_local` Postgres.
  CodeRabbit APPROVED (1 fix round: field-timer replay + test season-pin + config-key lock tightened;
  it **withdrew** the partial-delivery de-dup concern after the standalone-parity trade-off rationale,
  and the `OnFailure=` nitpick was declined for platform consistency — no existing cfb-*/worldcup-* unit
  uses it). **Timers authored but NOT enabled — enabling + `systemd-analyze calendar` validation is
  Phase L.** `AGENTS.md` (untracked local Codex mirror) updated locally, intentionally not committed.
  **Next: PR 5 (routes, standings & email conformance).**
- **2026-07-01** — **PR 5 (routes, standings & email conformance) merged (#107).** Golf-scoped
  standings (ADR-036 — dropped the append-all-platform-users block); enrollment-scoped mail across
  `send_picks_open_email` / `send_results_recap_email` / `get_users_without_picks(tournament_id,
  season_year)` (replaced `User.query.all()`, mirrors worldcup notifications + CFB); `get_avatar()`
  before the display name on `tournament_detail` standings; admin-override hardening (server-side
  validate field membership + season usage excl. the pick's own players, **validate-before-mutate**,
  rollback on failure, GET used-list excludes own players; `make_pick` existing-pick path also rolls
  back); admin branding + `markupsafe.escape` on every dynamic name in HTML email bodies
  (`_admin_alert_recipient` mirrors CFB `_send_admin_email`); `results_finalized` gating on
  `tournament_detail` (earnings column + Best Pick card); README statuses match the registry.
  **Confirm-before-reresolve gate deliberately DEFERRED** (new preview-screen surface, out of PR-5
  scope) — `test_admin_override_complete_tournament_reresolves_immediately` reconciles the roadmap's
  named confirm test by locking the one-step re-resolve. +18 tests (test_golf_conformance.py); suite
  1575→1593; enrollment scoping + override validation verified on `ccc_local` Postgres (rolled back).
  CodeRabbit (ASSERTIVE): 6 findings → accepted 5 (override season/status guard, resolve-fail
  rollback, no-email reminder skip, Best-Pick gating, symmetric backup-player test) + **pushed back on
  the prod-only ADMIN_EMAIL-fallback removal** (CFB parity + documented deploy convention — CR withdrew
  it and recorded a learning). **Next: PR 6 (cleanups & test backfill).**
- **2026-07-01** — **PR 6 (cleanups & test backfill) merged (#108).** Final backend-hardening
  slice (mirrors CFB §9); no player-facing change. Dead code (audit §9): dropped the unused
  `GolfTournamentField.is_alternate` column (migration `1816342926ce`; round-tripped
  upgrade→downgrade→upgrade on `ccc_local` Postgres, `migration-reviewer` SAFE — downgrade
  restores the original nullable Boolean); deleted callerless sync helpers
  `SlashGolfAPI.get_tournament()`, `TournamentSync._update_pick_deadline_from_leaderboard()`,
  `get_just_completed_tournament()`; dropped the redundant `send_admin_field_alert` import in the
  picks-open branch (the used import lives in the Wednesday-evening field-alert branch). N+1
  (audit §5): `joinedload(GolfEnrollment.user)` on `index()` standings +
  `joinedload(user/primary_player/backup_player/active_player)` on `tournament_detail()` picks
  (options on the existing `.query`, not a `select()` rewrite — per the ORM-migration policy).
  Results sync (audit §4): `sync_tournament_results(tournament, force=False)` short-circuits an
  already-finalized tournament (no API round-trip / reprocessing) unless `force=True` — all CLI
  callers already pull from `results_finalized == False`-filtered queries, so it's a defensive
  guard for direct calls. +10 tests (`tests/test_golf_cleanup.py`): recommended-suite backfill
  (`update_status_from_time` never auto-completes, `validate_availability` rejects used /
  non-field players, `calculate_total_points` carries the major ×1.5), N+1 query-count
  **invariance** locks for both routes, results short-circuit + force locks, `is_alternate`
  absence lock. Suite 1593→1603; migration + N+1 counting verified on `ccc_local` Postgres.
  CodeRabbit (CHANGES_REQUESTED): 3 actionable, all Minor test-tightening (fresh-instance
  past-end assertion, exact `errors ==` asserts vs `any(...)`, full `api.calls` map on the
  short-circuit) → all applied, re-review clean (all threads `review_comment_addressed`).
  **Golf PRs 1-6 complete — the backend is hardened to standalone parity + platform conventions.
  Next: Phase U (UI elevation — author `games/golf/DESIGN.md` first), deferred to near the
  Jan 2027 launch.**
- **2026-08-24** — **Phase R (legacy retirement audit).** The standalone's 2026 season ended
  (32/32 finalized, 19 members, 563 picks, 13 major-cut penalties); full feature inventory of both
  codebases → audit addendum. Rules engine / sync / email confirmed at parity; the surfaces are not
  (Stats Hub absent, Member Scorecard self-only, no burn-% picker, no mobile cards, no shared-rank
  detail) → Phase U rewritten above. Discovered the real PythonAnywhere cadence was three live reads
  a day (the README's "no live polling" was stale) and that the free-tier budget is gated by the
  task schedule alone → timers retuned + `tests/test_golf_timers.py`. Three bugs fixed (ADR-033 copy,
  un-season-scoped reminder lookup, hardcoded subnav year). Legacy DB archived (sha256 above); Brad's
  four rulings recorded in Phase R. **Next: Phase I (import the 2026 season).**

## Key reference sources

- Audit: `docs/golf-pickem-platform-code-audit-2026-06-30.md` (+ its 2026-08-24 addendum)
- Legacy 2026 season data (the parity-oracle answer key): `~/Golf_Pick_Em/archive/golf_pickem_2026_final.db`
  (read-only, gitignored; copy in `instance/`); sha256 `09f397c6…9864`
- Standalone port sources (read-only reference, retired 2026-08-24): `/Users/bhagstrom/Golf_Pick_Em/{models.py, sync_api.py, app.py, send_reminders.py, import_tournaments.py, force_schedule_sync.py, stats.py, static/js/season-replay.js, static/js/burn-list.js}`
- Platform exemplars to mirror: `games/worldcup/services/notifications.py` (enrollment-scoped mail),
  `games/worldcup/templates/worldcup/leaderboard.html` (avatars), `deploy/cfb-*.{timer,service}`,
  `config.py` (`ODDS_API_KEY`/`FOOTBALL_DATA_API_KEY` pattern), `tests/test_cfb_automation.py`.
