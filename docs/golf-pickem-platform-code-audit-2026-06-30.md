# Golf Pick 'Em - Platform Code Audit

Date: 2026-06-30

Scope: Read-only pre-launch audit of `games/golf/` in `fantasy-platform` against the standalone reference app at `/Users/bhagstrom/Golf_Pick_Em`.

No files were modified during the audit itself.

## 1. Game Logic Parity - Pick Resolution

No finding: final-resolution WD branching in `GolfPick.resolve_pick()` matches the standalone for the three critical WD cases: early primary WD activates backup, late primary WD keeps primary at 0, both early WD uses primary at 0.

[HIGH] Major cut/DQ penalty system is missing  
File: `games/golf/models.py`, line ~328  
Issue: Platform `GolfPick` has no `penalty_triggered`, no user/enrollment penalty-paid state, and no live penalty refresh equivalent to standalone `Pick.refresh_live_penalty()`.  
Risk: Major missed-cut/DQ penalties will not be assessed, collected, shown, emailed, or added to the pot.  
Fix: Port the standalone penalty model, final `resolve_pick()` flagging, live refresh, payment/admin surfaces, and recap/stat displays.

[DESIGN QUESTION] Zurich team-event scoring source of truth conflicts  
File: `games/golf/models.py`, line ~504  
Issue: Platform halves team-event earnings, while the current standalone `models.py` does not; however standalone README/import comments and the audit brief say Zurich should divide by 2, while standalone tournament UI says both partners get full payout.  
Risk: Zurich scoring will be wrong unless Brad decides whether API earnings are team-level or already per-player.  
Fix: Resolve the rule, then align platform code, standalone docs/UI, and tests.

[DESIGN QUESTION] Major plus team-event multiplier order is undocumented  
File: `games/golf/models.py`, line ~504  
Issue: Platform halves first, then applies the 1.5x major multiplier.  
Risk: A future API anomaly or schedule misflag could produce unexpected scoring.  
Fix: Document the intended precedence and lock it with a test, even if no real 2026 event is both.

[HIGH] Failed reprocessing can persist partial clears  
File: `games/golf/services/sync.py`, line ~660  
Issue: `process_tournament_picks()` calls `clear_resolution()` then catches exceptions without a nested rollback; skipped picks also bypass `calculate_total_points()`.  
Risk: A mid-pick failure can clear points/usage but leave enrollment totals stale when the final commit succeeds.  
Fix: Use per-pick savepoints like standalone `process_tournament_results()` and roll back failed pick mutations.

[MEDIUM] Resolution cleanup is narrower than standalone  
File: `games/golf/models.py`, line ~406  
Issue: `clear_resolution()` deletes only the old active player usage, while standalone deletes primary, backup, and old active IDs before rebuilding.  
Risk: Historical bad rows or admin override edge cases can leave stale usage rows that block legal picks.  
Fix: Clear primary, backup, and old active usage for that pick/user/season before re-resolving.

[HIGH] Live early-WD backup activation is not reflected before finalization  
File: `games/golf/models.py`, line ~555; `games/golf/templates/golf/index.html`, line ~136  
Issue: Platform active displays use `active_player_id or primary_player_id`, but `active_player_id` is normally unset until results are processed.  
Risk: If a primary WDs before R2, the weekend UI keeps showing the dead primary instead of the activated backup.  
Fix: Port standalone `is_backup_activated()` logic and use it in `get_current_earnings()`, index, tournament detail, and my-picks.

## 2. Game Logic Parity - Player Eligibility and Usage

No finding: platform uses `GolfSeasonPlayerUsage`, matching the standalone's separate usage table approach.

No finding: player editing excludes the current pick's primary/backup in the normal pick route, matching standalone behavior.

[HIGH] Admin override trusts disabled UI for eligibility  
File: `games/golf/routes.py`, line ~652  
Issue: POST override validates only primary != backup; it does not server-check field membership or season usage.  
Risk: Admins can submit non-field or already-used golfers and corrupt usage/scoring.  
Fix: Validate selected IDs against field IDs and used IDs on POST, excluding the current pick's own players.

[MEDIUM] Admin override disables the existing pick's players  
File: `games/golf/routes.py`, line ~733; `games/golf/templates/golf/admin/override_pick.html`, line ~73  
Issue: GET loads `used_player_ids` but does not remove the selected pick's current primary/backup.  
Risk: The form can render the existing selected golfers as disabled/used.  
Fix: Mirror standalone and remove existing pick IDs from the used list before rendering.

[MEDIUM] Existing-pick validation error leaves mutated ORM object in-session  
File: `games/golf/routes.py`, line ~425  
Issue: The route mutates `existing_pick` before validation and does not roll back on validation errors.  
Risk: The rendered response can show invalid state, and later autoflush behavior is fragile.  
Fix: Validate before mutating or call `db.session.rollback()` on validation failure, as standalone does.

## 3. Game Logic Parity - Sync and API Integration

No finding: the API client exposes `/schedule`, `/tournament`, `/leaderboard`, and `/earnings`.

[CRITICAL] Team-event API rows are not flattened  
File: `games/golf/services/sync.py`, line ~421  
Issue: Platform loops raw `leaderboardRows`/earnings rows directly; standalone `_iter_player_rows()` expands Zurich team rows with nested `players`.  
Risk: Zurich fields, live results, withdrawals, and final earnings can skip every player in team-shaped rows.  
Fix: Port `_iter_player_rows()` and use it in field, live, withdrawals, and results sync.

[HIGH] ISO timestamp parsing is missing  
File: `games/golf/services/sync.py`, line ~196 and line ~357  
Issue: Platform parses Mongo/int timestamps but not ISO strings for `teeTimeTimestamp` or schedule `date.start`.  
Risk: Current SlashGolf ISO payloads can silently skip schedule updates and fail deadline derivation.  
Fix: Port standalone ISO parsing and route schedule date parsing through the shared timestamp parser.

[HIGH] Major purse estimates/backfill are missing  
File: `games/golf/constants.py`, line ~38; `games/golf/models.py`, line ~125  
Issue: Major purse estimates are `None`, and platform lacks `effective_purse`, `purse_is_estimate`, and finalization backfill.  
Risk: Major live projections and displays can be `$0`/TBD until the API schedule happens to carry the purse.  
Fix: Port standalone estimates, model properties, and `_backfill_purse_from_schedule()`.

[HIGH] Live projected earnings omit major multiplier  
File: `games/golf/utils.py`, line ~105; `games/golf/services/sync.py`, line ~829  
Issue: Platform `calculate_projected_earnings()` has no `is_major` argument.  
Risk: Active major projections are underreported by 1.5x.  
Fix: Add `is_major`, pass it from sync/routes/templates, and test major projections.

[MEDIUM] Final position normalization is missing  
File: `games/golf/services/sync.py`, line ~623  
Issue: Platform stores API `position` raw; standalone normalizes `None`, numeric dicts, and numbers to strings.  
Risk: Emails/templates can show dicts/None or fail on string assumptions.  
Fix: Port `normalize_position()` and use it at every `final_position` write.

[HIGH] Fresh schedule seeding is not implemented  
File: `games/golf/services/sync.py`, line ~322; `games/golf/cli.py`, line ~76  
Issue: `sync_schedule()` only updates existing tournaments, but no platform command/script creates the locked 2026 Golf schedule.  
Risk: A fresh platform season can have zero tournaments, and `sync-run --mode schedule` imports nothing.  
Fix: Add a controlled seed/import command equivalent to standalone `import_tournaments.py`, then let schedule sync update API IDs/purses.

[LOW] API call logging writes under the code tree at import time  
File: `games/golf/services/sync.py`, line ~48  
Issue: `os.makedirs(games/golf/logs)` runs during module import.  
Risk: A read-only deploy or missing permission can break app startup.  
Fix: Move logs to a configurable writable path and initialize lazily.

[MEDIUM] Automation queries are not season-scoped  
File: `games/golf/services/sync.py`, line ~901  
Issue: active/recent/pending tournament helpers filter by status/date but not `season_year`.  
Risk: Multi-season data can cause old or future tournaments to sync/process.  
Fix: Add explicit season-year filtering or accept a season argument.

## 4. Game Logic Parity - Tournament Status State Machine

No finding: `GolfTournament.update_status_from_time()` matches standalone by never time-auto-setting `complete`.

[MEDIUM] Complete display is not gated by finalized results  
File: `games/golf/templates/golf/tournament_detail.html`, line ~104  
Issue: The page switches to final/earnings mode based on `status == 'complete'`, not `results_finalized`.  
Risk: If API status marks complete before earnings import/process finishes, users can see incomplete final rows.  
Fix: Gate final earnings/recap presentation on `results_finalized` or an explicit processed state.

[LOW] Results sync does not short-circuit already-finalized tournaments  
File: `games/golf/services/sync.py`, line ~549  
Issue: `sync_tournament_results()` will re-fetch and rewrite finalized tournaments if called directly.  
Risk: Extra API usage and avoidable reprocessing.  
Fix: Return early when `results_finalized` is already true unless a forced reprocess flag is supplied.

## 5. Platform Integration Conformance

No finding: registry wiring is correct and Golf remains `coming_soon`.

No finding: no Golf route uses `str(user.id)` as Flask-Login session identity.

No finding: Golf reminder mail uses `send_platform_email()` rather than direct SMTP.

[MEDIUM] `SLASHGOLF_API_KEY` bypasses platform config  
File: `config.py`, line ~45; `games/golf/cli.py`, line ~39  
Issue: `SEASON_YEAR`, `ENTRY_FEE`, `SYNC_MODE`, and `FIXED_DEADLINE_HOUR_CT` are configured, but `SLASHGOLF_API_KEY` is read directly from `os.environ`.  
Risk: This is inconsistent with the platform config pattern and easy to miss in app-context code.  
Fix: Add `SLASHGOLF_API_KEY = os.environ.get(...)` to `Config` and read it from `current_app.config`.

[MEDIUM] Tournament detail standings omit avatars  
File: `games/golf/templates/golf/tournament_detail.html`, line ~116  
Issue: The player column renders `get_display_name()` without `user.get_avatar()`.  
Risk: Violates the platform standings integration requirement.  
Fix: Render avatar before display name on every Golf standings/results table.

[HIGH] Public standings include every platform user  
File: `games/golf/routes.py`, line ~181  
Issue: `index()` appends all unenrolled users with 0 points.  
Risk: Golf standings will be polluted by World Cup/CFB-only accounts.  
Fix: Show only Golf enrollments unless Brad explicitly wants a public all-platform board.

[MEDIUM] Hardcoded admin address and standalone branding remain  
File: `games/golf/services/reminders.py`, line ~56  
Issue: `ADMIN_EMAIL = "bhagstrom0@gmail.com"` and `ADMIN_NAME = "Sun Day Regrets"` are hardcoded.  
Risk: Prod alerts bypass `ADMIN_EMAIL` config and carry old branding.  
Fix: Use `current_app.config.get('ADMIN_EMAIL')` fallback and CCC/commish branding.

[LOW] Golf template sort filters are safe but should stay watched  
File: `games/golf/templates/golf/tournament_detail.html`, line ~114; `games/golf/templates/golf/admin/payments.html`, line ~56  
Issue: Current uses sort by `user.username`, not method names.  
Risk: No current bug, but this is the exact pattern to avoid if changed to `get_display_name`.  
Fix: Sort in routes for display-method ordering.

[LOW] N+1 risks in Golf pages  
File: `games/golf/routes.py`, line ~163 and line ~305  
Issue: standings and tournament detail load enrollments/picks without eager-loading user/player relationships.  
Risk: Small league is fine, but pages scale poorly.  
Fix: Add `joinedload`/route-level DTOs when doing the Golf polish pass.

## 6. Reminder and Email System

[HIGH] Reminder de-duplication is missing  
File: `games/golf/models.py`, line ~145; `games/golf/services/reminders.py`, line ~906  
Issue: Platform lacks standalone `last_reminder_type` and sends whenever the hourly job lands inside the tolerance window.  
Risk: Players can receive duplicate 24h/12h/1h reminders.  
Fix: Add `last_reminder_type`, skip already-sent or later tiers, and record after successful sends.

[HIGH] Golf emails target all platform users  
File: `games/golf/services/reminders.py`, line ~239; line ~848; line ~581  
Issue: picks-open, deadline reminders, and recaps iterate `User.query.all()`.  
Risk: Non-Golf users get Golf mail and no-pick reminders.  
Fix: Send only to current-season `GolfEnrollment` users, unless Brad chooses a deliberate marketing email.

[MEDIUM] Results recap marks sent after partial success  
File: `games/golf/services/sync.py`, line ~694  
Issue: `recap_email_sent` is set if `emails_sent > 0`, even if some recipients failed.  
Risk: Failed recipients never get retried.  
Fix: Track per-recipient delivery or mark sent only when all intended recipients succeed.

[MEDIUM] Dynamic HTML email content is not escaped  
File: `games/golf/services/reminders.py`, line ~284 and line ~704  
Issue: user names, tournament names, and golfer names are interpolated into HTML directly.  
Risk: Malformed names can break email markup.  
Fix: Escape dynamic values before HTML interpolation.

[LOW] Email palette is standalone-era Golf green/gold  
File: `games/golf/services/reminders.py`, line ~66  
Issue: Email design is not aligned to the CCC system.  
Risk: Cosmetic brand inconsistency only.  
Fix: Revisit during the planned Golf UI/email pass.

## 7. CLI and Automation Wiring

[HIGH] No Golf systemd timers/services exist  
File: `deploy/`  
Issue: Deploy has CFB and World Cup timers, but no Golf automation.  
Risk: Field syncs, reminders, live leaderboard, and results will not run in production.  
Fix: Add timers: schedule manual/season start, field Tue AM/PM and Wed AM/PM, live Thu-Sun every 30-60 min, results Sun night/Monday, remind hourly during the 24h window.

[MEDIUM] Reminder command is separate and undocumented in platform command block  
File: `games/golf/cli.py`, line ~52; `AGENTS.md`, line ~38  
Issue: `sync-run --mode` has no `remind`; reminder is `flask golf remind`, but AGENTS only documents sync-run modes.  
Risk: Timer authors may schedule the wrong command.  
Fix: Document `flask golf remind` or add `remind` to `sync-run`.

[MEDIUM] `sync-run --mode all` is unsafe as a recurring production job  
File: `games/golf/cli.py`, line ~76  
Issue: `all` chains schedule, field, live, withdrawals, results, and earnings with only partial weekday gates.  
Risk: A broad scheduled job can create excess API traffic and trigger emails at unintended times.  
Fix: Treat `all` as manual/dev-only or add explicit production safety gates.

[MEDIUM] Legacy one-off schedule tools were not ported  
File: `games/golf/cli.py`, line ~195  
Issue: Standalone has `import_tournaments.py` and `force_schedule_sync.py`; platform has neither equivalent.  
Risk: No clean way to seed season schedule or force mid-week purse refresh.  
Fix: Add platform CLI commands for initial seed and forced schedule refresh.

## 8. Test Coverage

[HIGH] Golf has almost no platform test coverage  
File: `tests/test_golf_auto_enroll_removed.py`, line ~1  
Issue: Only enrollment regression tests exist; core scoring/sync/reminder behavior is untested.  
Risk: High-risk season logic can regress silently.  
Fix: Add focused pytest coverage listed in the recommended suite below.

## 9. Dead Code and Miscellaneous

[LOW] `GolfTournamentField.is_alternate` is unused  
File: `games/golf/models.py`, line ~244  
Issue: No route, sync, display, or test reads/writes `is_alternate`.  
Risk: Dead schema adds confusion.  
Fix: Remove it in a migration or wire it to real alternate eligibility/display behavior.

[LOW] Unused sync helpers/endpoints remain  
File: `games/golf/services/sync.py`, line ~160; line ~254; line ~865  
Issue: `get_tournament()`, `_update_pick_deadline_from_leaderboard()`, and `get_just_completed_tournament()` are defined but unused.  
Risk: Maintainers may assume paths are active.  
Fix: Delete or call them from the intended sync flow.

[LOW] Platform README status is stale  
File: `README.md`, line ~68  
Issue: README says Golf and CFB are live, while registry says both are `coming_soon`.  
Risk: Operational confusion during launch planning.  
Fix: Align README with `games/registry.py`.

[LOW] Unused import in field sync notification block  
File: `games/golf/services/sync.py`, line ~519  
Issue: `send_admin_field_alert` is imported in the picks-open branch but not used there.  
Risk: Minor maintainability noise.  
Fix: Remove the unused import.

## Must-Fix Before Launch

1. Port or consciously redesign the major missed-cut/DQ penalty system.
2. Resolve Zurich team-event scoring source of truth and lock it with tests.
3. Add team-row flattening across field/live/withdrawals/results sync.
4. Add ISO timestamp/date parsing for SlashGolf schedule and tee times.
5. Add major purse estimates, effective purse display, and finalization backfill.
6. Apply major multiplier to live projected earnings.
7. Make live early-WD backup activation work in all player-facing active views.
8. Make pick reprocessing transactional so failed picks cannot persist partial clears.
9. Add schedule seeding/import tooling for a fresh platform season.
10. Harden admin override with server-side eligibility validation and complete-tournament confirmation.
11. Restrict Golf standings/emails/reminders to Golf enrollments unless intentionally public.
12. Add reminder de-duplication.
13. Add Golf production systemd timers/services.

## Parity Gaps

- Missing major cut/DQ penalty tracking, payment, live refresh, and UI.
- Zurich scoring rule is inconsistent between platform, standalone code, standalone docs, and standalone UI.
- Live early-WD backup activation is not reflected on platform pages.
- Team-event nested API rows are not flattened.
- ISO schedule/tee-time parsing is missing.
- Major purse estimates/effective purse/backfill are missing.
- Major live projected earnings are not multiplied by 1.5.
- Position normalization is missing.
- Standalone stats hub, burn list, and remaining-percentage pick UI are absent.
- Tournament detail omits no-pick users and standalone competition ranking behavior.
- Admin override lacks standalone validation and confirm-before-reresolve gate.
- Reminder de-dup via `last_reminder_type` is absent.
- Schedule seed/import and forced schedule refresh tools are absent.
- Live penalty refresh CLI is absent.
- Penalty-paid/payment tracking is absent.
- Make-pick mutual exclusion/search/remaining-percent JS is behind standalone.
- Results recap/reminders target all platform users instead of Golf members.
- Golf automation timers are absent.

## Recommended Test Suite

`test_resolve_pick_primary_finishes`: primary completes, primary used, backup unused, earnings awarded.

`test_resolve_pick_primary_wd_before_r2_backup_finishes`: backup activates, primary returns to pool, backup used.

`test_resolve_pick_primary_wd_after_r2`: primary counts for 0, primary used, backup unused.

`test_resolve_pick_both_wd_before_r2`: primary used for 0, backup returns to pool.

`test_resolve_pick_major_cut_penalty`: active major pick with cut/DQ triggers penalty.

`test_calculate_total_points_major_multiplier`: completed major points equal `earnings * 1.5`.

`test_calculate_total_points_team_event_rule`: Zurich points match Brad's decided rule.

`test_validate_availability_rejects_used_player`: primary/backup in season usage are rejected.

`test_validate_availability_rejects_non_field_player`: non-field primary/backup are rejected.

`test_update_status_from_time_never_auto_completes`: time flips upcoming to active but never complete.

`test_clear_resolution_removes_old_usage`: reprocess cleanup removes old primary/backup/active usage without touching other picks.

`test_get_used_player_ids_current_season_only`: enrollment usage returns only current-season player IDs.

`test_sync_schedule_parses_iso_date_start`: ISO `date.start` updates purse and does not skip event.

`test_sync_field_flattens_team_rows`: Zurich nested team rows create player field entries.

`test_sync_results_flattens_team_rows`: Zurich nested earnings rows create per-player results.

`test_live_projection_applies_major_multiplier`: active major projected earnings include 1.5x.

`test_reminder_dedup_skips_sent_tier`: hourly reminder does not resend the same/later tier.

`test_admin_override_requires_confirm_for_complete`: completed-tournament override previews first and commits only with confirm.

`test_admin_override_rejects_used_or_non_field_player`: POST validation blocks invalid override submissions.
