# Go-Live Readiness — Design

**Date:** 2026-05-06
**Author:** Brad + Claude (brainstorming)
**Status:** Approved for implementation
**Implements:** post-redesign go-live for Specs A, B, and C Plans 1–5 against `docs/superpowers/plans/2026-04-21-production-deployment.md`

---

## 1. Context

Brad paused the production deployment plan after Phase 2 Task 10 (Droplet provisioned) on 2026-04-28. Between pause and resume, three major design specs shipped to `main`:

- **Spec A — CCC brand foundation.** Logo + favicons, navbar/footer, design tokens, auth-page restyle (login, register, forgot, reset, change, profile), email reskin.
- **Spec B — CCC home redesign.** Four-state home shell (`out` / `pre` / `live` / `post`) with a `build_home_context` dispatcher and a `flask worldcup snapshot-ranks` cron job for the live-state sparkline + week-delta trend.
- **Spec C — World Cup reskin** (Plans 1–5). New picks foundation, per-rival surfaces (`player_detail` reskin + new `team_detail` route with D11 ownership privacy), public analytics (leaderboard reskin + Stats Hub at `/worldcup/stats`), WC Hub migration onto `home_shell`, and visual-polish CSS sweep.

`main` is at `890bf66`, 264/264 tests, pyright clean.

Two outputs are required to ship safely:

1. **Audit + edit the deployment plan** in place — fix drift introduced by post-pause reality.
2. **Reset and rewrite the Human End-to-End Test Script** as a thorough production launch script that exercises every new screen, simulates a full World Cup on the live database, then resets to a clean launch baseline.

---

## 2. Scope decisions (locked during brainstorming)

| Decision | Choice |
|---|---|
| Test-script shape | **Single thorough production-only first-launch script.** No local-preflight split; one signoff record. |
| Test data on prod | **Plan A — clean test users (`testplayer1`, `testplayer2`), deleted via DB reset at the end.** |
| Tournament-state coverage | **Full simulation on prod** — `out` → `pre` → `live` → `post` driven by manual admin match entry, then full DB reset before announcing launch. |
| Deadline flip mechanic | **SSH hand-edit** of `TOURNAMENT_DEADLINE_UTC` in `games/worldcup/constants.py` (the canonical definition site; `services/state.py` re-imports it) + `systemctl restart fantasy-platform`. Reverted before final DB reset. |
| Score-recalc trigger | **Admin Recalc button** (`POST /worldcup/admin/recalc`) — instant, also tests the route. |
| Match volume during simulation | **Representative subset** — 4 group results (Tier-1 win, Tier-3 draw, Tier-4 underdog, Tier-5 win) covering each multiplier path; one group-advancement form run; 6 knockout matches (R32 → R16 → QF → SF → final → third-place). |
| Deliverable packaging | **Two docs** — in-place edits to the deployment plan + new `docs/Production Launch Test Script.md`. |

---

## 3. Deliverable 1 — Deployment plan audit deltas

**Target:** `docs/superpowers/plans/2026-04-21-production-deployment.md` (in-place edits, single commit).

### 3.1 Sequencing note (lines 16–27)

Replace the "Spec C — next brainstorm" + sports-data-API list with a **Resume status as of 2026-05-06** callout:

- Specs A, B, C Plans 1–5 all merged.
- `main` at `890bf66`, 264/264 tests, pyright clean.
- Sports-data API integration **deferred to post-launch**. Manual admin match entry powers tournament scoring at launch — adequate for the small private cup audience.
- Snapshot-ranks already woven into Task 25 cron schedule (no further infra changes from any of the three specs).
- Pick up at **Task 11** and continue through Task 27, then immediately run the new Production Launch Test Script.

### 3.2 Test-count drift (3 occurrences)

Tasks 2 Step 4, 5 Step 3, 9 Step 3 each say "all tests pass (119 tests)." Replace with:

> Expected: all tests pass — current baseline is **264** on `main`. Verify pytest's reported count matches the count on `main` at deploy time.

### 3.3 Drop redundant Task 20.5

Task 20 already runs `flask db upgrade` and creates the admin user. Delete Task 20.5 entirely **but** preserve its `flask shell` table-inspection check by inserting it as a new Step 4 of Task 20:

```python
# Verify migrations created the expected tables:
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask shell
>>> from extensions import db
>>> from sqlalchemy import inspect
>>> sorted(inspect(db.engine).get_table_names())
# Expected: includes 'user', 'golf_enrollment', 'cfb_enrollment',
#           'worldcup_enrollment', 'worldcup_pick', 'worldcup_match',
#           'worldcup_team', 'worldcup_rank_snapshot', and others.
>>> exit()
```

### 3.4 Pool-pre-ping callout in Task 2

Update Task 2 Step 2's expected `ProductionConfig` block to include the post-pause additions per CLAUDE.md:

```python
class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # DO Managed Postgres closes idle connections; long-lived Gunicorn workers
    # need pool_pre_ping to avoid OperationalError on first request after idle.
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 280}
```

### 3.5 Soften Task 5's expected-diff line-anchored assertions

Task 5 Step 1 shows the import block ending at `from extensions import ...`. Three specs of churn likely added imports. Soften Step 1's "expected output" from a line-exact match to:

> Expected: `ProxyFix` is imported from `werkzeug.middleware.proxy_fix` somewhere in the top-of-file import block, and applied to `app.wsgi_app` immediately before `return app`.

### 3.6 New Phase 5.5 cross-reference

After Task 25 (cron) and before Task 26 (UptimeRobot), insert a one-line callout:

> **Before configuring monitoring (Task 26), run the full Production Launch Test Script (`docs/Production Launch Test Script.md`).** UptimeRobot creates real alerts for real outages — you don't want it firing on test-induced systemd restarts during the tournament simulation.

### 3.7 No other infrastructure deltas

The .env list in Task 17 still covers every variable `config.py` reads. No new env vars from any of the three specs. No new system dependencies. Cron schedule in Task 25 already includes `worldcup snapshot-ranks` (added at the time the plan was paused).

---

## 4. Deliverable 2 — Production Launch Test Script

**Target path:** `docs/Production Launch Test Script.md` (new).
**Archive:** rename existing `docs/Human End-to-End Test Script.md` → `docs/archive/2026-04-11-human-e2e-test-script.md` (preserves the pre-redesign record).

### 4.1 Front matter

```markdown
# Production Launch Test Script
## Fantasy Platform — Post-Redesign Go-Live

**Date authored:** 2026-05-06
**Tester:** Brad
**Target URL:** https://<your-live-domain>
**Estimated time:** ~3.5 hours including tournament simulation + DB reset
**Prerequisites:** Deployment plan Tasks 11–25 complete (Postgres provisioned, domain registered, server set up, app deployed, cron jobs loaded)

This script walks the production environment end-to-end against the live
codebase. It registers two test users, simulates a full World Cup tournament
with admin-entered match results, verifies every redesigned surface from Specs
A/B/C, then resets the database to a clean launch baseline (admin user only,
no test data, no entered results) before real players are invited in.

🔴 = go/no-go blocker for launch. Fix before announcing.
⚪ = regression check. Note and triage post-launch.
✅ / ❌ / ⚠️ — mark each item as you go.
```

### 4.2 Section list (15 sections, top-to-bottom)

| § | Title | Risk | Coverage |
|---|---|---|---|
| 0 | Pre-flight (prod-side) | 🔴 | `systemctl status nginx fantasy-platform`; `journalctl -u fantasy-platform -n 50`; `flask worldcup status`; `df -h` / `free -h`; `curl -I https://<domain>` |
| 1 | Out state — chrome | 🔴 | Incognito; CCC brand mark, navbar voice labels, footer; HTTPS padlock; HTTP→HTTPS redirect; static asset 200 + cache-control; no mixed content |
| 2 | Registration + auth | 🔴 | Register `testplayer1` / `testplayer2` (use `bhagstrom0+test1@gmail.com` / `+test2`); auth-page pattern; avatar picker; **real password-reset email arrives**; reset link works; change-password; logout; login-with-`?next=` |
| 3 | WC enrollment + picks + pre-deadline surfaces | 🔴 | `/worldcup/join` (`game_must_be_open`); enroll both; submit + edit picks; sub-nav; `/worldcup/leaderboard` public, dense rank, **rivals' picks hidden pre-deadline**; `team_detail` — **D11: ownership count hidden from ALL viewers including the team's own picker**; `player_detail` respects gating; schedule (CT timestamps); groups; rules |
| 4 | Stats Hub (pre-tournament) | ⚪ | `/worldcup/stats`; phase chip "Pre-Tournament"; country / tier KPIs; tier combos table |
| 5 | Home state machine — `out` + `pre` | 🔴 | Logged-out home → `_home_out`; logged-in pre-deadline (no enrollment) → join CTA; logged-in pre-deadline (enrolled) → `_home_pre` (tracking-starts copy, picks summary) |
| 6 | Game switcher + Golf/CFB regression | ⚪ | Game switcher; `/golf/`, `/cfb/` indexes load no-500; sub-nav theme swaps |
| 7 | Admin two-tier scoping | 🔴 | Platform admin → `/worldcup/admin/`; testplayer1 (no admin) → flash redirect; same check for `/golf/admin`, `/cfb/admin` |
| 8 | Tournament prep — flip the deadline | — | SSH hand-edit `TOURNAMENT_DEADLINE_UTC` to yesterday in `games/worldcup/constants.py` (the canonical definition; `services/state.py` re-imports it, so editing `constants.py` is sufficient); `sudo systemctl restart fantasy-platform`; verify `/worldcup/picks` now read-only for both test users; curl POST returns redirect-with-error (not silent save) |
| 9 | Live state — group stage simulation | 🔴 | Enter 4 group results via admin (Tier-1 win, Tier-3 draw, Tier-4 underdog, Tier-5 win); admin Recalc; **leaderboard math pinned to exact expected values**; group advancement form; `flask worldcup snapshot-ranks --backfill 7`; `_home_live` partial (sparkline + week-delta + recent-results with `.is-roster-match` highlight) |
| 10 | Knockout simulation | 🔴 | `/worldcup/admin/set-knockout/<id>` for 1 R32 match; verify locked when result entered; clear-team-assignment guard; enter R32 → R16 → QF → SF → final → third-place (~6 KO matches); leaderboard math correct each stage; **team_detail ownership now reveals post-deadline**; player_detail accordion drill-down |
| 11 | Post state — champion crowned | 🔴 | After final entered: home → `_home_post`; champion banner with `.champion-flag`; final roster recap with `.row-champion-pick`; `team.best_finish` labels render literally ("Champion", "Round of 16", not raw codes); leaderboard final ranks; Stats Hub phase chip flips to "Completed" |
| 12 | Cron + email + monitoring smoke | 🔴 | `tail -n 20 /var/log/fantasy/*.log` — recent successful entries in `worldcup-recalc.log` and `worldcup-snapshot.log`; leave SSH open ~12 min and re-tail (one full 10-min cron cycle) — new entries appeared; trigger one more password reset → email arrives; UptimeRobot monitor green; DO resource alerts configured |
| 13 | Mobile pass — real device | ⚪ | iPhone or Android (not DevTools): home, picks, leaderboard, **team_detail**, **player_detail**, **stats**, schedule, post-state home (champion banner) — no horizontal scroll, sub-nav scrolls, hero typography legible |
| 14 | Cleanup — restore deadline + reset DB | 🔴 | SSH: revert `TOURNAMENT_DEADLINE_UTC` in `games/worldcup/constants.py` to real `datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))` → `sudo systemctl restart fantasy-platform`; **verify-on-prod guard: echo `DATABASE_URL` confirms `db.ondigitalocean.com`** before any destructive command; `flask db downgrade base && flask db upgrade && flask worldcup init && flask create-admin`; `flask worldcup status` → 48 teams, 104 matches, 0 completed, 0 enrolled |
| 15 | Post-reset sanity — the launch baseline | 🔴 | Re-verify deadline via `flask shell` (`from games.worldcup.constants import TOURNAMENT_DEADLINE_UTC; print(TOURNAMENT_DEADLINE_UTC)` — must print `2026-06-11 19:00:00+00:00`); `/worldcup/admin/users` shows admin only; `flask worldcup status` clean; **freshly recreated admin can hit `/worldcup/picks` and see the empty pick form** (mirrors what every real user does first); only then announce launch |

### 4.3 Per-section template

Every section uses the same shape:

```markdown
## Section N: <Title> <risk-marker>

> One-paragraph context: what this verifies and why it matters at launch.

```bash
# Exact commands (SSH / curl) when applicable
```

- [ ] Discrete check 1 — expected outcome stated explicitly
- [ ] Discrete check 2 — ...

**Notes:**
```

### 4.4 Score-math expected-value table (inline in §9 / §10)

To remove all ambiguity, §9 pins exact values. Example:

> **Expected:** if testplayer1 picked the Tier 4 team that won, leaderboard total = base 3 (group win) × multiplier 3.0 = **9.0**. If they picked the Tier 1 team that won, total = 3 × 1.0 = **3.0**. The Tier-3 draw scores 1 × 2.5 = **2.5** to anyone who picked the drawn team.

(The exact multipliers come from `games/worldcup/services/scoring.py`; the spec implementer should verify and pin the live values when writing the script.)

### 4.5 Production safeguards

- §0 includes `df -h` and `free -h` against the DO alert thresholds (>80% disk, >85% memory).
- §2 mandates Gmail `+alias` test addresses on Brad's real inbox, not throwaway domains, so password-reset emails are observable.
- §8 documents the deadline flip as an SSH-only edit (no git commit) — self-healing because the next legitimate `./deploy.sh` from `main` overwrites the file. Includes a "ALWAYS revert in §14 before DB reset" callout banner inline.
- §14 mandates an explicit `echo $DATABASE_URL | grep ondigitalocean` guard before any `db downgrade`; aborts the section if the connection string doesn't match production.
- A final box at the bottom of the doc lists exact rollback commands if anything between §0 and §15 goes red:
  - Restore deadline: `sudo nano games/worldcup/constants.py` → revert `TOURNAMENT_DEADLINE_UTC` to `datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))` → `sudo systemctl restart fantasy-platform`.
  - Roll back code: `git -C /home/deploy/fantasy-platform reset --hard <last-known-good-sha> && ./deploy.sh`.
  - Roll back DB: `psql $DATABASE_URL` → `\dt` (manual triage); preferred path is `flask db downgrade <prior-revision>`.

### 4.6 What the new script intentionally drops from the old one

- The "Completed Enhancements (shipped)" block at the top — stale changelog, not a test artifact.
- Section 4E's `games/worldcup/constants.py` file path — that constant lives in `services/state.py` now, and the new §8 / §14 use the correct path.
- Pre-completed checkboxes (`- [x]`) and old `Notes:` blocks — fresh baseline.
- `http://127.0.0.1:5000` references — replaced by `https://<your-live-domain>` throughout.

---

## 5. Risks & open knowns

| Risk | Mitigation |
|---|---|
| Forgetting to revert the deadline edit before DB reset → real cup launches with a yesterday-deadline | §8 includes a banner: "ALWAYS revert in §14 before DB reset"; §14 includes the explicit revert step before any `db downgrade`; §15 re-verifies the deadline value. |
| Running `db downgrade base` against a wrong (local SQLite) database by mistake | §14 mandates the `echo $DATABASE_URL` guard. |
| `WC_FAKE_NOW` is silently a no-op in production (`ENVIRONMENT=production`) — the SSH hand-edit is the only path for the live/post simulation | Documented inline at §8 with the rationale; cross-references CLAUDE.md "Time test seam" guidance. |
| Snapshot-ranks `--backfill 7` produces 7 days of identical ranks | Documented in §9 as expected; the script notes that real differentiation only accumulates after live cron runs. |
| Test users + their pick rows persist if cleanup forgets a step | DB reset (`db downgrade base && db upgrade && worldcup init`) is the canonical full-wipe; §14 spells it out completely; §15 re-verifies with `flask worldcup status` and `/worldcup/admin/users`. |
| The `.is-roster-match` and `.row-champion-pick` styles need real rendered context to verify (not just "page loads") | §9 calls out the highlight specifically; §11 calls out the row glow specifically; §13 mobile re-walk catches them on a real device. |

---

## 6. Done definition

- Deployment plan committed with the seven edits in §3, no other touches.
- New `docs/Production Launch Test Script.md` committed; old script moved to `docs/archive/`.
- Brainstorming spec (this doc) committed at `docs/superpowers/specs/2026-05-06-go-live-readiness-design.md`.
- After Brad reviews this spec, the writing-plans skill takes over to produce the implementation plan.
