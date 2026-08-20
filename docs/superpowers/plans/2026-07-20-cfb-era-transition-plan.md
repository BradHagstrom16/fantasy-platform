# CFB Era Transition — World Cup Sunset + CFB Center of Gravity

**Date:** 2026-07-20
**Status:** ACTIVE — ratified 2026-07-20 (Brad's rulings recorded in §7). Execution tracked by the §8 checkboxes: Phases 0–3 complete; Phases 4–7 pending.
**Scope:** Planning artifact for (1) mothballing the completed 2026 World Cup game, (2) making CFB Survivor the platform's center of gravity for its ~Sep 3 launch, (3) sequencing the work. Supersedes and absorbs the Workstream C sketch in `~/.claude/plans/the-world-cup-is-reactive-manatee.md` (C1/C2), which planned the lounge transition but explicitly excluded WC shutdown.

---

## 1. Orientation findings (verified 2026-07-20)

Facts the plan rests on. Each was read from prod, the repo, or memory this session — not assumed.

**Prod live-ops (read from the droplet, read-only):**
- Four WC systemd timers still fire post-tournament: `worldcup-sync` (every 30 min), `worldcup-advancement` (hourly), `worldcup-digest` (daily 22:30 CT), `worldcup-digest-player` (daily 05:00 CT).
- One live crontab line: `worldcup snapshot-ranks` daily at 05:05 UTC. The `worldcup recalc` cron is already commented out, as are all CFB and Golf cron entries.
- No CFB timers are installed/enabled. The five `deploy/cfb-*` timer pairs (setup/spreads/scores/autopick/remind, from PR #71) exist in the repo only.
- Post-tournament behavior audit: `sync --mode scores` still polls football-data.org unconditionally (~48 calls/day, applies nothing — all 104 shells complete); if `FOOTBALL_DATA_API_KEY` were removed or expired, that poll converts into an admin alert email **every 30 minutes** (`sync.py:80` → `sync.py:627`). Advancement/digest/digest-player are DB-only no-ops with correct guards. `snapshot-ranks` appends one identical-rank row per enrollment every new calendar day — unbounded growth while archived.

**Lounge coupling (file-level inventory):**
- Home state is resolved by `worldcup_state()` in `core/main/routes.py` — clock vs `TOURNAMENT_DEADLINE_UTC`, then final match #104 completion. It is **fully decoupled from `registry.status`**: flipping registry statuses does not hand the lounge to CFB. `'post'` is a one-way latch on match #104 `is_completed` — the archive state renders forever with no expiry, which is exactly the desired mothball behavior.
- All four `_context_*` builders in `core/main/home_context.py` and every lounge partial except three (`_commish_note.html`, `_game_card.html`, the registry loops in `_home_out.html`/`_game_tiles_compact.html`) are WC-hardwired: WC models, `SEASON_YEAR`, tier/multiplier spine, rank snapshots, match #104, "nine nations" copy. Even the logged-out `total_enrolled` count queries `WorldCupEnrollment` directly (`home_context.py:103`).
- `featured_games()` and `_game_card.html` are **dead code** (test-only consumers). The natural featured-game seam exists in the registry but nothing real uses it.
- `GameStatus` values `'completed'` and `'closed'` are declared but **no code path reads them**. Flipping WC to either silently drops it from `available_games()` (the logged-out join CTA block vanishes) and from admin enrollment — no dedicated UI or copy anywhere.
- The navbar, game grids, coming-soon rails, and the CFB sub-nav in `base.html` are already registry-generic. The lounge partials are the WC-specific mass; the navbar is not a blocker.

**Test coupling:** exactly one test breaks on a WC status flip — `tests/test_home_context.py::test_context_out_basic` (asserts worldcup in `available_games`). Registry helper tests use mocks. No test exercises the real WC entry through `game_must_be_open`/`enrollment_required`.

**Reversibility facts (for the possible Women's World Cup):**
- Only `WorldCupEnrollment` is season-scoped (`season_year`, unique per user+season; `SEASON_YEAR = 2026` in `games/worldcup/constants.py`). Teams, matches, picks, and rank snapshots are single-season global tables. The 2026 data **is** the archive; a revival implies a schema/data decision (§7 Q3) that does not need answering now.
- Nothing in this plan deletes code, data, unit files, or the API key. Every mothball action is a disable, not a removal.

**`fantasy-cfb-prep` worktree:** it is the `cfb/launch-prep` git worktree parked at the PR #93 merge (`7a7a62c`, June 24), 117 commits behind main, remote branch deleted. Contents beyond the stale checkout: agent-config artifacts and the gitignored CFB sandbox (seeder, `cfbprep_*` logins, smoke screenshots). The CFB registry flip to `'open'` is live there under a `skip-worktree` guard (verified intact). It is a code sandbox, not a planning directory — which is why this plan lives here on main (`docs/superpowers/plans/`), per the established spine-doc-on-main discipline.

---

## 2. Area A — World Cup live-ops mothball

| | |
|---|---|
| **Current state** | Four WC timers + one cron still firing daily against a tournament that ended 2026-07-19. One (`worldcup-sync`) polls an external API for nothing and is one expired key away from 30-minute admin-email spam. One (`snapshot-ranks`) grows `worldcup_rank_snapshot` every day. |
| **Proposed change** | Disable (not remove) all five on the droplet. Keep unit files in `deploy/`, keep `FOOTBALL_DATA_API_KEY` in `.env`, keep all sync/digest code. Zero repo changes. |
| **Risk** | Near-zero. `systemctl disable --now` and commenting a crontab line are both one-command reversible. The only thing lost is the daily identical snapshot row, which no surface needs post-tournament (`_context_post`'s `your_climbed_n` reads the existing history). |
| **Rationale** | Stops silent API waste and pre-empts the error-spam failure mode without tearing anything out. This is the only genuinely time-sensitive item in the plan and is independent of everything else — it can run today. |

Exact commands (Brad runs these; `sudo` on the droplet needs an interactive TTY, so run them in a normal SSH session, not piped):

```bash
ssh -i ~/.ssh/id_ed25519 deploy@104.131.28.136

# 1) Stop and disable the four WC timers (reversible: enable --now to revive)
sudo systemctl disable --now worldcup-sync.timer worldcup-advancement.timer \
    worldcup-digest.timer worldcup-digest-player.timer

# 2) Confirm nothing WC is scheduled anymore
systemctl list-timers --all | grep -i worldcup   # expect: no lines, or all "n/a"

# 3) Comment out the snapshot-ranks cron line
crontab -e
#   → put a leading '#' on the line ending in: flask worldcup snapshot-ranks >> /var/log/fantasy/worldcup-snapshot.log 2>&1
#   → add a note above it: "# DISABLED 2026-07-20 — WC 2026 complete; re-enable for a future WC"

# 4) Verify
crontab -l | grep snapshot   # expect the line to start with '#'
```

Optional, low value: delete the handful of redundant `worldcup_rank_snapshot` rows captured after 2026-07-20. Recommend **skip** — harmless rows, and pruning is a destructive act for zero user-visible benefit (§7 Q2; RULED skip).

**Status 2026-07-20: PHASE 0 COMPLETE.** Steps 3–4 (crontab) executed non-interactively — `snapshot-ranks` line commented with a dated note, prior crontab backed up server-side at `~/crontab.bak.2026-07-20`, zero active cron jobs remain. Steps 1–2 (the four timers) run by Brad in an interactive session the same day; `systemctl list-timers --all | grep -i worldcup` returns nothing.

---

## 3. Area B — World Cup registry status + enrollment gating

| | |
|---|---|
| **Current state** | WC is `status='open'`, `is_featured=True`. `/worldcup/join` still accepts enrollments into a finished tournament; WC still appears in the admin add-user dropdown and as the logged-out page's join CTA. |
| **Proposed change** | Flip WC to `status='completed'`, `is_featured=False` **at the same moment** CFB flips to `open`/featured — one atomic changeover commit (Area E). Before that commit lands, give `'completed'` real handling: a completed/archived treatment in the registry-driven surfaces (e.g., the compact tile's existing `COMPLETED` label generalized off its hardcoded WC block) and an updated `test_context_out_basic`. |
| **Risk** | Interim exposure: for the ~4–5 weeks until changeover, a stray visitor could still join the finished WC pool. Audience is a ~30-person friend group; the join page itself renders post-tournament state, so the confusion window is small. Flipping early instead would leave the logged-out lounge with zero open games (hero + coming-soon rail only) — defensible "between seasons" honesty, but it removes the page's only CTA with nothing replacing it. |
| **Rationale** | One atomic flip means the out-state always has exactly one flagship CTA, tests change once, and the changeover is a single revertable commit. It also avoids doing `'completed'`-status design work twice. Flagged as §7 Q1 in case Brad prefers closing WC joins immediately. |

Admin routes need no change: platform-admin access to WC admin surfaces is wanted for the archive, the advancement-reminder and bracket emails are structurally dormant, and the group-recap email is admin-triggered only.

---

## 4. Area C — What is preserved for a WC revival (mothball, not delete)

Binding preservation rules for all subsequent work:

- **No WC table is wiped, no WC row deleted.** The 2026 season data is the archive and powers the permanent `'post'` lounge/room render, the public leaderboard, and player detail pages.
- **No WC code is deleted** — sync, bracket autofill, digests, CLI, tests all stay. The ~WC-half of the 1600+ test suite keeps running on every PR; it is the regression net under the lounge refactor (Area D).
- **`deploy/worldcup-*` unit files stay in the repo** — they are the revival recipe. Same for `FOOTBALL_DATA_API_KEY` in prod `.env` (free tier, costs nothing).
- **Revival-shape decision is explicitly deferred** (§7 Q3). Nothing above forecloses any of the three options (season-scope the schema / archive-and-reseed / sibling game slug for WWC).

---

## 5. Area D — Lounge generalization (the technical crux)

| | |
|---|---|
| **Current state** | The lounge is WC-hardwired at every layer below the state dispatcher: state resolution (`worldcup_state()` in `core/main/routes.py`), all four context builders, ten of thirteen partials. CLAUDE.md already flags this as the work CFB launch triggers. CFB's data shape is different in kind: week-based attrition, lives, no multipliers, no single tournament deadline. |
| **Proposed change** | Middle-path generalization (Option C below): make the registry's dormant featured-game seam load-bearing, split lounge context builders and partial trees per game behind it, and design the CFB-era lounge (including WC's archive presence and the handoff moment) with impeccable before implementation. |
| **Risk** | The main design risk is over-abstracting for a "generic game framework" nobody needs yet; the main schedule risk is under-estimating that the four-state shape itself is WC-flavored (CFB's "live" is a weekly rhythm with pick-pending/locked/verdict substates, not a continuous tournament). C1 design must resolve the CFB lounge state model before C2 code. |
| **Rationale** | Three approaches were weighed: |

- **Option A — full featured-game framework** (per-game lounge-context providers registered in the registry, generic state-machine contract every game implements). Rejected: YAGNI. Only one game dominates the lounge at a time by doctrine ("dominated by whichever single game is currently live"), and only CFB needs this now. The abstraction cost would be paid before a second consumer exists (Golf's lounge needs are unknown until ~2027).
- **Option B — swap-in-place** (rewrite the four builders/partials from WC to CFB directly, keep the hardwiring). Rejected: recreates today's exact debt for the next transition (Golf 2027, possible WWC), discards WC's post-state lounge render that we want to keep reachable, and contradicts CLAUDE.md's standing instruction to *generalize* off WC-specific concepts.
- **Option C — thin seam + per-game lounge modules (recommended).** Concretely:
  - Registry: promote the featured-game concept from dead code to the lounge's dispatch key (either make `featured_games()` load-bearing or add a `lounge_game()` helper returning the single featured-open game). Registry entries gain what the lounge needs to dispatch (state-resolver callable; later, a lounge-context callable).
  - `core/main/routes.py`: resolve state via the featured game's resolver instead of importing `worldcup_state` directly.
  - `core/main/home_context.py`: split into per-game lounge builders (WC's four builders move essentially as-is into a WC lounge module; CFB gets new ones). The dispatcher stays in core.
  - Templates: per-game partial trees (the existing WC partials become the WC set, kept intact for archive/revival; CFB gets its own `_home_*` set designed in C1). Registry-generic partials (`_game_tiles_compact` minus its hardcoded WC block, coming-soon rails) stay shared.
  - The lounge chrome remains CCC purple/gold — the dark-CFB-midnight identity belongs to the CFB *room*, not the lounge (lounge-vs-room doctrine). CFB flavor enters through content and signature surfaces (survival count, lives, weekly verdict), not substrate.

**C1 (design, impeccable) decides:** the CFB lounge state model (out/pre/live/post mapping + live-state weekly substates); the CFB lounge signature surface (the analog of WC's dossier/sparkline — noting the doctrine that the lounge and the game room must stay differentiated, so the lounge signature must not duplicate the CFB room's hub surfaces); how much WC survives in the CFB-era lounge (recommend: a compact archived tile — champion + your finish — the existing `COMPLETED` tile treatment made real; §7 Q5); the WC→CFB handoff moment for the few weeks where WC is `completed` and CFB is `open`-but-preseason.

**C2 (implementation) slices** are sequenced in §8. The refactor contract for the WC-extraction slice: **rendering is pixel-identical before and after** (the lounge still shows WC post-state until the changeover flip), locked by the existing `test_home_context.py` suite plus template-source locks as needed.

---

## 6. Area E — Registry changeover + Area F — CFB launch ops readiness

**E. The changeover (one commit, launch-gated):**

| | |
|---|---|
| **Current state** | CFB is `coming_soon`/unfeatured on main; `'open'` only in the guarded worktree. Season starts Thu Sep 3 (`week_1_start = 2026-09-03`, Brad-confirmed in the audit). |
| **Proposed change** | One PR flipping both entries: WC → `completed` + `is_featured=False`; CFB → `open` + `is_featured=True`. Same PR updates `test_context_out_basic`, the CLAUDE.md lounge/games sections, and any changeover copy. Target: **mid-August** (~Aug 17–24), giving the friend group 2–3 weeks to join and pick before the week-1 deadline. |
| **Risk** | Launch-day risk concentrates here by design — everything else merged earlier, gated on this flip. Revert = revert one commit. The worktree's skip-worktree guard stays untouched — the flip PR is cut from main directly (ruled 2026-07-20, §7 Q4). |
| **Rationale** | A single atomic flip is the smallest possible launch-day diff, and every gated surface (join, lounge dispatch, admin enrollment, tiles) switches together. |

**F. CFB ops enablement (runbook, no PR; execute launch week):**

- [x] Verify prod `.env`: `ODDS_API_KEY` valid (quota check), `ADMIN_EMAIL` = real mailbox (fixed 2026-07-06), Brevo SMTP vars intact. **Verified 2026-08-17:** all vars present; quota 491 credits remaining (the `/events` probe is free); bonus — 90 events already listed in the Week-1 window, so the Aug 31 setup run has a real slate waiting.
- [x] Audit prod `cfb_*` tables: expect teams present, zero transactional rows (`flask cfb sync --mode status` first; then psql read-only if anything looks off). Confirm no sandbox/test data ever reached prod. **Done 2026-08-17** (post-seed): 49 teams (exact set match vs `DEV_SEED_TEAMS`), 0 weeks / 0 games / 0 picks; the single enrollment is Brad's own post-flip join (2026-08-13) — no sandbox data.
- [ ] Enable the five CFB timers, **by explicit name** — `systemctl enable` does not accept glob patterns (systemd rejects them outright: *"Glob pattern passed to enable, but globs are not supported for this"*; and glob expansion elsewhere in `systemctl` only matches units already in memory, which these will not be). Verified on the droplet 2026-07-21.

  **STAGED, not all-at-once (amended 2026-08-17):** `run_setup` has no date guard — every firing creates week `last+1` and *activates* it on successful import (`games/cfb/services/automation.py`), and `Persistent=true` catch-up behavior on a *freshly enabled* timer is unverified on this droplet. Enabling `cfb-setup.timer` at the wrong moment (or a surprise catch-up firing) can therefore create **and activate Week 2 before the season starts**, silently deactivating Week 1. Mirror the docket-setup doctrine (hand-run the first import, enable the setup timer last):

  **Amended again 2026-08-19 (preview import):** Week 1 already exists on prod —
  the 2026-08-19 preview import created it (42 games, `is_active=True`, spreads
  deliberately empty, so the room shows the lines-pending board and picks are
  impossible). That retires the "Mon Aug 31 hand-run setup" step: Week 1 is not
  an orphan (`_lowest_orphan_week` only retries 0-game weeks), so **any**
  `--mode setup` run before Week 1 completes creates AND activates Week 2. The
  real Week-1 lines land via `--mode spreads` on Tue Sep 1 (first fetch locks,
  DQ-6 — no wipe needed since nothing is locked yet). Two data corrections were
  also found in the 2026-08-19 design review: the Week-1 row's `deadline`
  (16:00) and `start_date` (05:00) were written as UTC instants into the
  pool-tz wall-clock columns — fix `start_date` (to `2026-09-03 00:00:00`)
  before Week 1 starts Thu Sep 3, and `deadline` (to `2026-09-05 11:00:00`)
  before Sat Sep 5 11:00 AM CT, or the recorded week start and the
  deadline-driven lock + autopick each run five hours late.

  ```bash
  # Launch week (any day Aug 30–31): the four timers that stand down without an active week
  sudo systemctl enable --now \
      cfb-spreads.timer cfb-scores.timer \
      cfb-autopick.timer cfb-remind.timer
  # Tue Sep 1: cfb-spreads.timer's Tuesday firing locks the real Week-1 lines
  # against the existing week (hand-run `--mode spreads` only if the timer
  # hasn't fired yet); then verify — expect 42 games, spreads locked
  FLASK_APP=app.py ENVIRONMENT=production venv/bin/flask cfb sync --mode status
  # Tue Sep 1 (after the Mon 06:00 CT slot has passed): the setup timer, LAST —
  # its first natural firing is Mon Sep 7, which creates Week 2 on the designed cadence
  sudo systemctl enable --now cfb-setup.timer
  systemctl list-timers 'cfb-*' --no-pager     # list-timers DOES glob; expect 5 rows
  ```

  **No copying step** — since ADR-041 (PR #123) `deploy.sh` installs every unit in `deploy/` on every deploy, so the `cfb-*` units are already present in `/etc/systemd/system/`, `disabled`. Verify that before enabling: `systemctl list-unit-files 'cfb-*'` should list all ten.

  If any are missing, **a deploy that never ran is only one of the explanations** — the more likely one is that `systemd-analyze verify` rejected that unit, in which case `deploy.sh` warned, skipped it by name, and exited non-zero while still deploying the app. Read the deploy output and its exit status rather than inferring: find the `failed validation` line naming the unit, fix the repo file, and redeploy. Either way, hand-copying is the wrong fix — it skips the validation gate and drifts back on the next deploy. Do **not** un-comment the legacy CFB crontab lines — timers are the canonical mechanism; delete or leave the commented cron lines as history.
- [x] Week-1 dry run on prod timing — **superseded 2026-08-19 by the preview import**, which exercised the real setup path on prod (42 games imported and activated). Do NOT run `cfb sync --mode setup` on prod again before Week 1 completes (see the amendment above — it would create and activate Week 2); the remaining verifications are read-only: `cfb sync --mode status` after Tuesday's spreads firing (expect 42 games, spreads locked on first fetch), and the reminder-cohort check. Any further setup rehearsal happens in the local sandbox with `CFB_FAKE_NOW` anchors only.
- [x] Deadline-semantics sanity check on week 1 specifically (Thu Sep 3 season start vs the locked Sat-11am-CT cadence): confirm the intended player experience for Thu/Fri week-1 games. The cadence is deliberately locked by `test_cfb_cfp_datemath.py` — this is a *verify the product intent* item, not a code change. **Confirmed by Brad 2026-08-17:** rigid Sat 11:00 CT deadline stands; a pick locks at its game's kickoff (players waiting past Thursday simply lose the Thu/Fri teams as options). Enforcement verified both directions: can't change off a started pick (`games/cfb/routes.py` `pick_locked`) and can't pick a started team.
- [ ] Post-flip smoke on prod: join → pick → standings as a non-admin, plus all four lounge states via the changeover checklist.

**Known-deferred CFB items (by prior ruling, not launch-blocking):** CFP week 16–19 real dates + `get_playoff_teams()` hardcode (December, manual runbook); DQ-5 manual commish weekly email; `national_title_odds` display feature.

---

## 7. Open questions — RESOLVED 2026-07-20 (Brad's rulings)

1. **When does WC stop accepting joins?** RULED: at the atomic changeover (~mid-Aug). The ~4–5-week window where a finished pool is technically joinable is accepted.
2. **Prune the few post-final `worldcup_rank_snapshot` rows?** RULED: no — stop the cron (Area A) and keep the rows.
3. **Future Women's World Cup shape** (season-scope the schema / archive-and-reseed / sibling game slug)? RULED: defer entirely; nothing in this plan forecloses any option.
4. **The `fantasy-cfb-prep` worktree?** RULED: refresh; skip-worktree guard stays; the eventual changeover PR is cut from main, not the worktree. **Executed 2026-07-20:** `games/registry.py` had changed on main (Ruff commits), so the refresh lifted the guard, reset the file, ff-merged to `2446c6a` (= main), re-applied the CFB `'open'` flip (line 69 only), and re-set the guard. Verified: `ls-files -v` shows `S`, tree clean, WC/golf statuses untouched.
5. **WC's presence in the CFB-era lounge?** DIRECTIONAL, not final: leaning a quieter impeccable treatment of the compact archived tile (champion + your finish). Final call remains with C1 design.
6. **Merge strategy for C2?** RULED: **merge early, gated on the registry flip** — each C2 slice lands on main rendering identical WC output until the changeover commit throws the switch. The held-branch approach from the old Workstream C sketch is retired (its reason — WC still evolving the lounge in prod — expired with the final).

---

## 8. Sequencing (one PR per session, full CodeRabbit cycle to merge, per standing cadence)

- [x] **Phase 0 — WC ops mothball** — COMPLETE 2026-07-20 (crontab commented non-interactively; the four timers disabled by Brad; zero WC jobs scheduled).
- [x] **Phase 1 — C1 lounge design session(s)** — COMPLETE 2026-07-20: `docs/superpowers/specs/2026-07-20-cfb-era-lounge-design.md` (+ visual-companion mockup) covers all four states, the live-state beats, the WC archived tile + farewell, the handoff, and the state model; Brad's four C1 rulings recorded in the spec header.
- [x] **Phase 2 — C2 slice 1: registry seam** — COMPLETE 2026-07-20: `GameRegistryEntry.lounge_state` resolver + `lounge_game()` (replaces dead `featured_games()`); `core/main/routes.py` dispatches through the seam; `'completed'` semantics locked across helpers; rendering unchanged (WC still open/featured); 13 seam tests in `tests/test_registry_seam.py`.
- [x] **Phase 3 — C2 slice 2: WC lounge extraction** — COMPLETE 2026-07-20 (PR #116): builders moved to `games/worldcup/services/lounge.py`, the ten WC partials to `games/worldcup/templates/worldcup/lounge/`; `core/main/home_context.py` is the thin dispatcher (registry-generic keys + commish note); `GameRegistryEntry.lounge_context` added and `lounge_game()` requires both callables. Pixel-identical verified by byte-diff across 8 render scenarios + 4-state browser smoke; `test_home_context.py` untouched; suite 1685. `_game_tiles_compact` de-hardcode deferred to Phase 4 by in-session ruling (its per-state label logic is WC-specific; the C1 tile design drives the generalization).
- [x] **Phase 4 — C2 slice 3+: CFB lounge builders + partials** — COMPLETE 2026-07-20 (PRs #117/#118/#119, one session, each through its full CR cycle). Every CFB lounge state exists behind the seam (`games/cfb/services/lounge.py` + `games/cfb/templates/cfb/lounge/`); the Phase 5 flip is now the two-line registry diff by construction (the changeover seam test exercises the real callables). Dead on prod until the flip; every state + beat browser-smoked in the sandbox. Suite 1685 → 1739.
  - [x] **PR A — flip-minimum** (#117, merged 2026-07-20): `cfb_lounge_state()` resolver (C1 §2.1 table) + out/pre contexts (§9) + `cfb/lounge/` out/pre/decree/farewell partials + the `_game_tiles_compact` generalization (WC labels moved to the WC lounge module with parity locks; `.cg--archived` tile) + CFB entry wired with both lounge callables. Live/post contexts raise until their PRs; changeover seam test now exercises the real callables. Suite 1685 → 1712. Noted for Phase 5: auth brand-panel WC promo line + WC-era commish note copy.
  - [x] **PR B — live state** (#118, merged 2026-07-20): central beat resolution (OPEN/HELD/LOCKED/VERDICT + every sub-variant incl. autopick + no-contest + revival), §2.3 precedence (elimination week renders its VERDICT; standing eliminated module after), view variant, Who's Left phases A–D + attrition band, compact standings on the rolls silhouette with `.lounge-lives` pips, `get_official_standings()` extracted to `game_logic.py` as the room+lounge shared order/rank helper (room status-row rank now competition rank on exact ties). Suite 1712 → 1737; all beats browser-smoked in the sandbox.
  - [x] **PR C — post state** (#119, merged 2026-07-20): the terminal lounge — champion banner (`◈ SOLE SURVIVOR ◈` / tiebreak `◈ CHAMPION ◈` per the §1.10 language law; evidence names the actual deciding mechanism, incl. the lives-led finish CR caught), final-field snapshot, `CHAMPION · {name}` tile, commish-note `{champion}` interpolation via a duck-typed shim.
  - Phase 5 checklist additions found during Phase 4: auth brand-panel WC promo copy; admin commish notes (all states) still WC-era.
- [x] **Phase 5 — Changeover PR** — EXECUTED 2026-08-11, ahead of the ~Aug 17–24 window on Brad's greenlight ("no use keeping World Cup active"), with the §1 team-list precondition explicitly waived (AP preseason poll not yet out; `cfb_team` = 0 accepted until it is): the atomic double flip + test/copy/CLAUDE.md updates (§6 E), all per the paste-ready kit `2026-07-30-phase5-changeover-kit.md` (exact diffs, auth-callout Jinja/CSS, the three CFB commish notes, smoke checklist, early §6F readiness results).
- [ ] **Phase 6 — CFB ops enablement + launch smoke** (launch week: §6 F runbook).
- [ ] **Phase 7 — post-launch cleanups**: CLAUDE.md lounge-doctrine rewrite if any drift remains; memory updates; December CFP runbook when in season.

Rough capacity: 6–8 working sessions before the flip, against a ~4–5-week runway to mid-August — comfortable, per "thorough over fast."

---

## 9. Explicitly out of scope / untouched

- The WC **room** (`games/worldcup/` templates/routes/services): stays exactly as shipped, rendering post-state forever. No WC room work is proposed.
- WC scoring SSoT, elimination helper, stage labels, public leaderboard, player detail, stats hub: untouched.
- Golf: stays `coming_soon` (Jan 2027 launch; Phase U design is its own future effort). Golf timers stay disabled.
- The lite Google-Sheet pool, `_migration_source/`, and all gitignored local artifacts: untouched.
- Any WC data deletion, code deletion, or key removal: explicitly rejected throughout.
