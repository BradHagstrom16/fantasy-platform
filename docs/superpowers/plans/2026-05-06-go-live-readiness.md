# Go-Live Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit and edit `docs/superpowers/plans/2026-04-21-production-deployment.md` per spec §3 (six discrete deltas), archive the existing `docs/Human End-to-End Test Script.md`, and write a new `docs/production-launch-test-script.md` per spec §4 (15-section production-launch script with full World Cup simulation + DB reset).

**Architecture:** Doc-only changes in an isolated git worktree on branch `worktree/go-live-readiness`. All edits ship in two commits inside the worktree, then a PR is opened against `main` so CodeRabbit can review the docs before Brad executes the test against production.

**Tech Stack:** Markdown only. No code, no test suites involved. The driver spec lives at `docs/superpowers/specs/2026-05-06-go-live-readiness-design.md` (commit `a9b0d30`); every task references its spec section.

---

## File Structure

| File | Action | Source-of-truth section in spec |
|---|---|---|
| `docs/superpowers/plans/2026-04-21-production-deployment.md` | Modify (6 in-place edits) | §3.1–§3.6 |
| `docs/Human End-to-End Test Script.md` | Move to `docs/archive/2026-04-11-human-e2e-test-script.md` | §4 (one-liner) |
| `docs/archive/2026-04-11-human-e2e-test-script.md` | Created by `git mv` | §4 |
| `docs/production-launch-test-script.md` | Create | §4.1 + §4.2 + §4.5 |

No code files. No tests. No migrations. No CSS.

---

## Task 1: Worktree setup

**Files:** None — this task creates the working directory.

- [ ] **Step 1: Verify clean state on main**

```bash
git status
```

Expected: `nothing to commit, working tree clean`. If dirty, stash or commit before proceeding — the worktree branches from current `HEAD`.

- [ ] **Step 2: Create the worktree**

```bash
git worktree add -b worktree/go-live-readiness ../fantasy-platform-go-live-readiness
```

Expected: `Preparing worktree (new branch 'worktree/go-live-readiness')` followed by `HEAD is now at <sha> <subject>`. The branch should fork from a commit that includes the spec at `docs/superpowers/specs/2026-05-06-go-live-readiness-design.md`.

- [ ] **Step 3: Pre-approve worktree paths in `.claude/settings.local.json`**

Per the project memory `feedback_subagent_worktree_perms`, subagents auto-deny Edit/Write on additional-directory paths. Add the worktree path to the local settings so subagents (or this session) can edit files without prompts.

Open `.claude/settings.local.json` (in the **main checkout**, not the worktree) and ensure it contains permission for the worktree path. Example pattern (merge with existing settings — don't overwrite other entries):

```json
{
  "permissions": {
    "additionalDirectories": [
      "../fantasy-platform-go-live-readiness"
    ]
  }
}
```

If the file already has `additionalDirectories`, append the new entry. If it doesn't exist, create it with the structure above.

- [ ] **Step 4: Switch to the worktree for all subsequent tasks**

```bash
cd ../fantasy-platform-go-live-readiness
pwd
```

Expected: `/Users/bhagstrom/fantasy-platform-go-live-readiness`

All later tasks run in this directory unless explicitly noted.

- [ ] **Step 5: Verify the spec is present at the worktree HEAD**

```bash
ls -la docs/superpowers/specs/2026-05-06-go-live-readiness-design.md
```

Expected: file exists with the size of the committed spec (~12 KB). If missing, the worktree forked from a pre-spec commit — abort and fix.

---

## Task 2: Audit the deployment plan (six in-place edits)

**Files:**
- Modify: `docs/superpowers/plans/2026-04-21-production-deployment.md`

All six edits are made with the `Edit` tool (exact `old_string` / `new_string`) and committed together. Spec §3 is the source of truth.

### Edit 2.1 — Sequencing note (spec §3.1, plan lines 16–27)

- [ ] **Step 1: Apply the sequencing-note replacement**

Use `Edit` with the following `old_string`:

```markdown
## Sequencing note (added 2026-04-28, post-pause)

Brad paused this plan after completing Phase 2 Task 10. Resume sequence:

1. Finish **Spec B — CCC home redesign** (`docs/superpowers/specs/2026-04-28-ccc-home-redesign-design.md`) and merge to `main`.
2. Finish **Spec C — World Cup reskin** (next brainstorm) and merge to `main`.
3. Source / build a sports-data API integration for live World Cup scores (out of scope for B and C).
4. Resume this plan at **Task 11** and continue through Task 27.

Spec B adds one new cron entry (`flask worldcup snapshot-ranks`) which has been **already woven into Task 25's cron schedule below** — no separate task needed. If Spec C or the API work introduces additional infra requirements, append them to the appropriate task here at that time.

**Snapshot timing tradeoff to know about:** the snapshot infra collects rank-history daily once the production cron is live. If this plan resumes only shortly before WC kickoff (June 11), the live-state sparkline on the home page will start with an empty/flat line and accumulate real data from the first cron run forward. The dossier copy handles this honestly ("tracking starts {date}") so the launch-day experience is acceptable either way — but earlier production resume = richer sparkline at launch.
```

`new_string`:

```markdown
## Resume status as of 2026-05-06

Brad paused this plan after completing Phase 2 Task 10. Resume status:

- **Specs A, B, and C Plans 1–5 all merged.** `main` at `890bf66` (or later); 264/264 tests; pyright clean.
- **Sports-data API integration deferred to post-launch.** Manual admin match entry powers tournament scoring at launch — adequate for the small private cup audience.
- **Snapshot-ranks cron** is already woven into Task 25 below — no further infra changes from any of the three specs.
- **Resume at Task 11** and continue through Task 27.
- **Then immediately** run the new `docs/production-launch-test-script.md` against the live URL before announcing launch (see Phase 5.5 callout below Task 25).

**Snapshot timing tradeoff to know about:** the snapshot infra collects rank-history daily once the production cron is live. If this plan resumes only shortly before WC kickoff (June 11), the live-state sparkline on the home page will start with an empty/flat line and accumulate real data from the first cron run forward. The dossier copy handles this honestly ("tracking starts {date}") so the launch-day experience is acceptable either way — but earlier production resume = richer sparkline at launch.
```

- [ ] **Step 2: Verify the replacement landed**

```bash
grep -n "Resume status as of 2026-05-06" docs/superpowers/plans/2026-04-21-production-deployment.md
```

Expected: one match around line 16. The phrase "next brainstorm" should no longer appear:

```bash
grep -c "next brainstorm" docs/superpowers/plans/2026-04-21-production-deployment.md
```

Expected: `0`.

### Edit 2.2 — Test-count drift (spec §3.2, three locations)

The plan says "all tests pass (119 tests)" three times. Replace each with a future-proof phrasing.

- [ ] **Step 1: Find all three occurrences**

```bash
grep -n "119 tests" docs/superpowers/plans/2026-04-21-production-deployment.md
```

Expected: 3 line matches (around lines 131, 269, 445).

- [ ] **Step 2: Apply `Edit` with `replace_all: true`**

Use `Edit` with `replace_all: true`:

`old_string`:

```
Expected: all tests pass (119 tests).
```

`new_string`:

```
Expected: all tests pass — current baseline is 264 on `main`. Verify pytest's reported count matches the count on `main` at deploy time.
```

- [ ] **Step 3: Verify all three updated**

```bash
grep -c "current baseline is 264" docs/superpowers/plans/2026-04-21-production-deployment.md
grep -c "119 tests" docs/superpowers/plans/2026-04-21-production-deployment.md
```

Expected: `3` and `0` respectively.

### Edit 2.3 — Drop Task 20.5, expand Task 20 (spec §3.3)

Task 20 already runs `flask db upgrade`. Task 20.5 duplicates it. Preserve the table-inspection check by folding it into Task 20 as a new Step 4.

- [ ] **Step 1: Add Step 4 to Task 20**

Use `Edit`:

`old_string`:

```markdown
- [ ] **Step 3: Create your admin user**

```bash
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask create-admin
```

You'll be prompted for username, email, and password. This is your platform admin account.

---

### Task 20.5: Initialize the production database schema

- [ ] **Step 1: Run migrations against the production database**

```bash
cd /home/deploy/fantasy-platform
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db upgrade
```

Expected: Alembic applies all migrations in order. You will see output like `Running upgrade -> abc123, ...` for each migration. No errors.

- [ ] **Step 2: Verify the tables exist**

```bash
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask shell
```

Then in the shell:

```python
from extensions import db
from sqlalchemy import inspect
print(inspect(db.engine).get_table_names())
exit()
```

Expected: a list of table names including `user`, `golf_enrollment`, `cfb_enrollment`, `worldcup_enrollment`, and others. If you see an empty list, something is wrong with `DATABASE_URL` in your `.env`.
```

`new_string`:

```markdown
- [ ] **Step 3: Create your admin user**

```bash
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask create-admin
```

You'll be prompted for username, email, and password. This is your platform admin account.

- [ ] **Step 4: Verify migrations created the expected tables**

```bash
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask shell
```

Then in the shell:

```python
from extensions import db
from sqlalchemy import inspect
sorted(inspect(db.engine).get_table_names())
```

Expected: a list including `user`, `golf_enrollment`, `cfb_enrollment`, `worldcup_enrollment`, `worldcup_pick`, `worldcup_match`, `worldcup_team`, `worldcup_rank_snapshot`, and others. If empty, `DATABASE_URL` in `.env` is wrong — re-check it before continuing.

```python
exit()
```
```

- [ ] **Step 2: Verify Task 20.5 is gone and Task 20 has Step 4**

```bash
grep -c "### Task 20.5" docs/superpowers/plans/2026-04-21-production-deployment.md
grep -n "Step 4: Verify migrations created" docs/superpowers/plans/2026-04-21-production-deployment.md
```

Expected: `0` and one match respectively.

### Edit 2.4 — Pool-pre-ping callout in Task 2 (spec §3.4)

`ProductionConfig` now also has `SQLALCHEMY_ENGINE_OPTIONS` for DO Managed Postgres. Update Task 2 Step 2's expected diff so re-runners end up with matching hardening.

- [ ] **Step 1: Apply the Task 2 Step 2 update**

Use `Edit`:

`old_string`:

```markdown
- [ ] **Step 2: Add session cookie security flags**

Replace the existing `ProductionConfig` block with:

```python
class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
```
```

`new_string`:

```markdown
- [ ] **Step 2: Add session cookie security flags + DO Managed Postgres connection hygiene**

Replace the existing `ProductionConfig` block with:

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
```

- [ ] **Step 2: Update Task 2 Step 3's expected output**

Use `Edit`:

`old_string`:

```markdown
- [ ] **Step 3: Verify the change looks correct**

```bash
grep -A 5 "class ProductionConfig" config.py
```

Expected output:
```
class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
```
```

`new_string`:

```markdown
- [ ] **Step 3: Verify the change looks correct**

```bash
grep -A 8 "class ProductionConfig" config.py
```

Expected output includes both the cookie flags and the engine options:
```
class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # DO Managed Postgres closes idle connections; ...
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 280}
```
```

### Edit 2.5 — Soften Task 5 expected-diff (spec §3.5)

Task 5 Step 1 shows the exact import block. Three specs of churn likely added imports. Soften to a behavior-level assertion.

- [ ] **Step 1: Apply the Task 5 Step 1 softening**

Use `Edit`:

`old_string`:

```markdown
- [ ] **Step 1: Add the import**

In `app.py`, add `ProxyFix` to the import block (after the existing imports, before `from config import config`):

```python
from werkzeug.middleware.proxy_fix import ProxyFix
```

The import block should look like:

```python
import logging
import os

import click
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config
from extensions import db, migrate, login_manager, csrf, limiter
```
```

`new_string`:

```markdown
- [ ] **Step 1: Add the import**

In `app.py`, add `ProxyFix` to the import block (alongside the existing `werkzeug` / `flask` imports):

```python
from werkzeug.middleware.proxy_fix import ProxyFix
```

Expected after this edit: `ProxyFix` is imported from `werkzeug.middleware.proxy_fix` somewhere in the top-of-file import block, and the rest of the existing imports remain untouched. (Don't worry about exact line ordering — the file may have grown additional imports since this plan was authored.)
```

### Edit 2.6 — Add Phase 5.5 cross-reference (spec §3.6)

Insert a callout between Task 25 (cron) and Task 26 (UptimeRobot) pointing at the new test script.

- [ ] **Step 1: Apply the cross-reference insertion**

Use `Edit`:

`old_string`:

```markdown
> **Tip:** When a game's season is over (e.g., World Cup ends), open `crontab -e` and add a `#` at the start of that job's line to disable it. Remove the `#` when the season begins again.

---

## Phase 6: Monitoring (Brad)

### Task 26: Set up UptimeRobot
```

`new_string`:

```markdown
> **Tip:** When a game's season is over (e.g., World Cup ends), open `crontab -e` and add a `#` at the start of that job's line to disable it. Remove the `#` when the season begins again.

---

## Phase 5.5: Production Launch Test (Brad)

> **Before configuring monitoring (Task 26), run the full Production Launch Test Script (`docs/production-launch-test-script.md`).** UptimeRobot creates real alerts for real outages — you don't want it firing on test-induced systemd restarts during the tournament simulation. The test script registers two test users, simulates a complete World Cup with admin-entered match results, then resets the database to a clean launch baseline before any real player is invited in.

---

## Phase 6: Monitoring (Brad)

### Task 26: Set up UptimeRobot
```

### Commit step for Task 2

- [ ] **Step C: Stage and commit all six edits**

```bash
git add docs/superpowers/plans/2026-04-21-production-deployment.md
git diff --cached --stat
```

Expected: 1 file changed, ~50 insertions / ~40 deletions (rough — exact counts will vary).

```bash
git commit -m "$(cat <<'EOF'
docs(plans): refresh production deployment plan post-redesign

- Replace stale "next brainstorm" sequencing note with 2026-05-06 resume status (Specs A/B/C Plans 1-5 merged, sports-data API deferred)
- Future-proof test-count assertions (264 baseline, verify against main at deploy time)
- Drop redundant Task 20.5; fold its table-inspection check into Task 20 Step 4
- Reflect post-pause ProductionConfig hardening (SQLALCHEMY_ENGINE_OPTIONS pool_pre_ping/recycle) in Task 2
- Soften Task 5 line-anchored import-block expectation to a behavior assertion
- Add Phase 5.5 callout pointing at the new Production Launch Test Script

Implements spec §3 of docs/superpowers/specs/2026-05-06-go-live-readiness-design.md.
EOF
)"
```

Expected: commit succeeds, no pre-commit hook failures.

---

## Task 3: Archive the old test script

**Files:**
- Move: `docs/Human End-to-End Test Script.md` → `docs/archive/2026-04-11-human-e2e-test-script.md`

- [ ] **Step 1: Confirm the old file exists**

```bash
ls -la "docs/Human End-to-End Test Script.md"
```

Expected: file present, ~16 KB.

- [ ] **Step 2: Create the archive directory if missing**

```bash
mkdir -p docs/archive
```

- [ ] **Step 3: Move with `git mv` so history is preserved**

```bash
git mv "docs/Human End-to-End Test Script.md" "docs/archive/2026-04-11-human-e2e-test-script.md"
```

Expected: no output (silent success).

- [ ] **Step 4: Verify the move**

```bash
ls docs/Human* 2>&1 | head
ls -la docs/archive/2026-04-11-human-e2e-test-script.md
git status --short
```

Expected: first `ls` returns "No such file or directory"; second shows the archived file present; `git status` shows `R  docs/Human End-to-End Test Script.md -> docs/archive/2026-04-11-human-e2e-test-script.md`.

- [ ] **Step 5: Commit the archive**

```bash
git commit -m "$(cat <<'EOF'
docs(archive): move pre-redesign Human E2E test script to docs/archive

The April-11 test script predates Specs A, B, and C Plans 1-5 and is
replaced by docs/production-launch-test-script.md (next commit). Archived
for historical record only.
EOF
)"
```

Expected: commit succeeds.

---

## Task 4: Write the new Production Launch Test Script

**Files:**
- Create: `docs/production-launch-test-script.md`

This is a single `Write` tool call producing the complete file. The structure is fixed by spec §4.2 (15 sections), front matter from §4.1, and section template from §4.3. Score-math expected values for §9 must be verified against `games/worldcup/services/scoring.py` before the file is written (see sub-step 1).

### 4.1 Pre-write fact-finding

- [ ] **Step 1: Pull the live tier multipliers from `scoring.py`**

The §9 score-math assertions need to reflect the actual multipliers in code. Run:

```bash
grep -n "TIER_MULTIPLIER\|MULTIPLIER\|multiplier" games/worldcup/services/scoring.py | head -20
grep -n "GROUP_WIN_POINTS\|GROUP_DRAW_POINTS\|base_points" games/worldcup/services/scoring.py | head -20
```

Expected: surface the exact constants. Record the values for use in §9 of the test script:

- Tier 1 multiplier (Favorites): _____
- Tier 2 multiplier (Contenders): _____
- Tier 3 multiplier (Dark Horses): _____
- Tier 4 multiplier (Underdogs): _____
- Tier 5 multiplier (Wildcards): _____
- Group-stage win base points: _____
- Group-stage draw base points: _____

These flow into the §9 expected-value pins (e.g., "Tier 4 win = 3 × <T4_mult> = X.X").

- [ ] **Step 2: Pull the actual deadline value from `constants.py`**

```bash
grep -A 1 "TOURNAMENT_DEADLINE_UTC\s*=" games/worldcup/constants.py
```

Expected: `datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))` — record the literal for use in §14 / §15 of the test script.

- [ ] **Step 3: Confirm the Tier 4 underdog roster (any 2026 World Cup Tier 4 team)**

```bash
grep -B 1 -A 3 "Tier 4\|TIER_4\|tier=4" games/worldcup/world_cup_countries.py 2>/dev/null | head -30
```

Or, if that file doesn't expose tiers directly, query a running dev server:

```bash
FLASK_APP=app.py venv/bin/flask shell -c "from games.worldcup.models import WorldCupTeam; print([(t.name, t.tier) for t in WorldCupTeam.query.filter_by(tier=4).all()])"
```

Expected: a list of Tier 4 team names. Record one (e.g., "Senegal" — exact value depends on your seed) for use in the §9 script copy as the concrete "underdog upset" example.

### 4.2 Write the test script file

- [ ] **Step 1: Write the file in one `Write` tool call**

Path: `docs/production-launch-test-script.md`

The file structure must match this exact outline. Each `## Section N` heading uses the title and risk marker from spec §4.2's table verbatim. Each section follows the template from spec §4.3:

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

The complete file content is below. Substitute the recorded values from §4.1 fact-finding (`<T1_MULT>`, `<T4_MULT>`, `<T4_TEAM>`, etc.) inline before writing.

````markdown
# Production Launch Test Script
## Fantasy Platform — Post-Redesign Go-Live

**Date authored:** 2026-05-06
**Tester:** Brad
**Target URL:** `https://<your-live-domain>`
**Estimated time:** ~3.5 hours including tournament simulation + DB reset
**Prerequisites:** Deployment plan Tasks 11–25 complete (Postgres provisioned, domain registered, server set up, app deployed, cron jobs loaded)

This script walks the production environment end-to-end against the live codebase. It registers two test users, simulates a full World Cup tournament with admin-entered match results, verifies every redesigned surface from Specs A/B/C, then resets the database to a clean launch baseline (admin user only, no test data, no entered results) before real players are invited in.

🔴 = go/no-go blocker for launch. Fix before announcing.
⚪ = regression check. Note and triage post-launch.
✅ / ❌ / ⚠️ — mark each item as you go.

---

## How to use this script

- Work through sections in order — later sections depend on earlier ones (especially §8–§14).
- Mark each item ✅ (pass), ❌ (fail), or ⚠️ (unexpected but not blocking).
- When something fails, capture what you saw in the section's `Notes:` block.
- **Stop and triage 🔴 blockers before continuing** — see the "If anything goes red" box at the bottom for rollback commands.
- **Do not skip §14 or §15.** The deadline edit and DB reset are mandatory before you announce launch.

---

## Section 0: Pre-flight (prod-side, no browser yet) 🔴

> Before touching the live URL in a browser, confirm the box itself is healthy. Cheap to run, expensive to skip — a stale systemd unit or a near-full disk will make every later section unreliable.

```bash
ssh deploy@<your-droplet-ip>

sudo systemctl status nginx fantasy-platform --no-pager | head -30
journalctl -u fantasy-platform -n 50 --no-pager
df -h /
free -h
cd /home/deploy/fantasy-platform && ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup status
curl -I https://<your-live-domain>
```

- [ ] `nginx` shows `active (running)`
- [ ] `fantasy-platform` shows `active (running)`
- [ ] `journalctl` shows no recent Python tracebacks
- [ ] Disk usage on `/` is below 80% (matches DO alert threshold)
- [ ] Memory is below 85% (matches DO alert threshold)
- [ ] `flask worldcup status` prints: 48 teams, 104 matches, 0 completed, 0 enrolled (or your admin enrollment if you joined yourself during prior tasks)
- [ ] `curl -I` returns `HTTP/2 200` and a `server: cloudflare` header

**Notes:**

---

## Section 1: Out state — logged-out chrome 🔴

> Verifies the CCC brand foundation (Spec A) and the `_home_out` partial (Spec B/C Plan 4) render correctly to a brand-new visitor, plus core HTTPS/redirect/static-asset hygiene.

Open a fresh **incognito** window. Navigate to `https://<your-live-domain>`.

- [ ] Browser shows a green padlock (HTTPS, no certificate warnings)
- [ ] Visiting `http://<your-live-domain>` (plain HTTP) 301-redirects to `https://`
- [ ] Page renders the CCC brand mark in the navbar (gold accent, voice label)
- [ ] Footer renders with voice strip + utility strip
- [ ] No mixed-content warnings in the browser console
- [ ] Open DevTools → Network → reload the page → `/static/css/style.css` returns `200` with `Cache-Control: public, immutable, max-age=...` (Nginx serving directly)
- [ ] Open DevTools → Network → `/static/css/tokens.css` returns `200` (loaded **before** style.css per CLAUDE.md)
- [ ] No `404`s on any static asset

**Notes:**

---

## Section 2: Registration + auth 🔴

> Verifies the auth-page pattern (Spec A: login, register, forgot, reset, change, profile), avatar picker integration, and — critically — that real password-reset emails arrive from the production Gmail SMTP.

> **Email aliasing tip:** Use Gmail's `+alias` form so password-reset emails land in *your* real inbox: `bhagstrom0+test1@gmail.com` and `bhagstrom0+test2@gmail.com`. Do **not** use throwaway domains — you must observe these emails in the next sub-step.

### 2A: Register two test users

In the incognito window:

- [ ] `/register` renders the auth-page pattern (CCC palette, brand mark, gold accents)
- [ ] Register `testplayer1` with email `bhagstrom0+test1@gmail.com`, strong password
- [ ] Submit → redirects to home, logged in, username in navbar
- [ ] Log out
- [ ] Register `testplayer2` with email `bhagstrom0+test2@gmail.com`, strong password
- [ ] Submit → redirects to home, logged in
- [ ] Log out

### 2B: Validation

- [ ] Try registering `testplayer1` again → inline error, not 500; form repopulates
- [ ] Try registering with mismatched passwords → inline error
- [ ] Try empty form → required-field errors, not 500

### 2C: Login flow + `?next=` redirect

- [ ] Visit `/worldcup/picks` while logged out → redirected to `/login?next=/worldcup/picks`
- [ ] Log in as `testplayer1` → redirects back to `/worldcup/picks` (the `next` param survives the GET → POST round-trip — locked in commit `02599f3` per archived script)

### 2D: Login validation

- [ ] Wrong password → "Invalid credentials" (or equivalent), not 500
- [ ] Non-existent username → identical message (no user enumeration)

### 2E: Profile + avatar picker

Logged in as `testplayer1`:

- [ ] `/profile` renders auth-page pattern; shows username + email
- [ ] Avatar picker visible; pick an emoji other than ⚽ (default); save → confirmation
- [ ] Pick a different one to confirm it's persistent

### 2F: Change password

- [ ] `/change-password` renders auth-page pattern
- [ ] Wrong current password → inline error, not 500
- [ ] Successful change → confirmation; log out, log back in with new password
- [ ] Change back to original (optional, for cleanliness)

### 2G: Forgot/reset password — real email send

- [ ] Log out
- [ ] `/forgot-password` → enter `bhagstrom0+test1@gmail.com` → submit
- [ ] Flash message is intentionally ambiguous (anti-enumeration: "If that email is in our system, a reset link has been sent")
- [ ] **Real email arrives** in your Gmail within 2 minutes, from-name **"Corrupt Commish Club"**, with a reset link
- [ ] Click the link → reset form renders the auth-page pattern → set new password → submit → success
- [ ] Log in with new password → works

### 2H: Anti-enumeration on a non-existent email

- [ ] `/forgot-password` → enter `nope-not-real@example.com` → submit
- [ ] Identical flash message as 2G (no leak that the address doesn't exist)
- [ ] No email arrives at any inbox

**Notes:**

---

## Section 3: WC enrollment + picks + pre-deadline surfaces 🔴

> Verifies the per-game enrollment flow (Plan: 2026-04-17), the new picks foundation (Spec C Plan 1), the leaderboard reskin (Plan 3), the new `team_detail` route with D11 ownership privacy (Plan 2), and the schedule/groups/rules content pages.

Logged in as `testplayer1`:

### 3A: Join

- [ ] `/worldcup/join` loads (`game_must_be_open` decorator allows it)
- [ ] Page renders with page-hero, how-it-works card, btn-game submit (Spec C Plan 1 pattern)
- [ ] Submit enrollment → redirects to `/worldcup/picks`
- [ ] Sub-nav now shows the WC pill set with red accent (`subnav-worldcup` per CLAUDE.md)

### 3B: Submit picks (testplayer1)

- [ ] `/worldcup/picks` renders the new picks foundation: 5 tier sections (Favorites, Contenders, Dark Horses, Underdogs, Wildcards)
- [ ] Each tier shows correct pick-count requirement (T1: 2, T2: 1, T3: 2, T4: 2, T5: 2 = 9 total)
- [ ] USA goals tiebreaker field visible
- [ ] Validation guards work (cannot submit without 9 picks; submit button disabled or rejects)
- [ ] Select 2 T1, 1 T2, 2 T3, 2 T4, 2 T5; tiebreaker `4`; submit → success
- [ ] After submit, page shows read-only summary with "Edit My Picks" button (per archived script `02599f3` lock-in)

### 3C: Edit picks (still pre-deadline)

- [ ] Click Edit; existing picks are pre-selected (not blank)
- [ ] Change 2–3 picks; submit → confirms saved
- [ ] Reload `/worldcup/picks` → new picks visible

### 3D: Enroll testplayer2 + submit different picks

- [ ] Log out, log in as `testplayer2`
- [ ] Enroll via `/worldcup/join`
- [ ] Submit a **different** set of 9 picks (overlap with testplayer1 in some tiers, divergent in others) — this matters for §10 ownership-reveal verification
- [ ] Tiebreaker `2` (different from testplayer1)

### 3E: Leaderboard pre-deadline (logged-out, public per ADR-026)

- [ ] Log out completely
- [ ] `/worldcup/leaderboard` loads — **no redirect to login**
- [ ] Both `testplayer1` and `testplayer2` rows appear
- [ ] Both rows show score 0.0 (no matches played); rank shows dense rank
- [ ] **Rivals' picks are NOT shown anywhere on the leaderboard pre-deadline** (privacy enforced server-side)
- [ ] Each row has the player's avatar emoji rendered before the display name
- [ ] Tiebreaker column is **hidden** pre-deadline (per archived-script `c5e4149` / `49821a3`)
- [ ] **Trend column is NOT visible** (gated at ≥7 snapshots; we have 0 right now)
- [ ] Click a player row → `/worldcup/leaderboard/<id>` (player_detail) loads

### 3F: Player detail pre-deadline

- [ ] `/worldcup/leaderboard/<testplayer2_id>` (logged out)
- [ ] Page renders the Plan 2 player_detail reskin (page-hero, player chip with avatar)
- [ ] **testplayer2's individual picks are NOT shown** (only aggregate score, no roster reveal)
- [ ] Per-pick accordion drill-down is empty / hidden pre-deadline

### 3G: Team detail pre-deadline — **D11 ownership privacy invariant** 🔴

This is the most important privacy invariant in the codebase right now. Per CLAUDE.md and the spec memory `project_ccc_team_detail_privacy`: ownership count, percent, and picker_names must be hidden from **ALL viewers including the team's own picker** pre-deadline.

Pick any team that testplayer1 picked (e.g., a Tier 1 team). Note the team_id from the picks page or from the schedule.

- [ ] `/worldcup/team/<team_id>` loads (logged out)
- [ ] Page renders Plan 2 team_detail (hero, fixtures, ownership ribbon section)
- [ ] **Ownership count is hidden** — no "X players picked this team" display
- [ ] **Picker names are NOT shown**
- [ ] **Percent is NOT shown**

Now log in as `testplayer1` (the team's own picker):

- [ ] `/worldcup/team/<team_id>` while logged in as picker
- [ ] **Ownership count is STILL hidden** even from the team's own picker (this is the D11 invariant — do NOT "fix" the absent-count branch)
- [ ] No leak of "you and N others picked this team"

### 3H: Content pages

Logged in as `testplayer1`:

- [ ] `/worldcup/schedule` — renders matches in CT timestamps, has "All kickoff times shown in Central Time" caption (per archived-script `566128b`)
- [ ] `/worldcup/groups` — 12 group tables (A–L), all 0 points / 0 played
- [ ] `/worldcup/rules` — scoring matrix renders without redundant "Base" column

**Notes:**

---

## Section 4: Stats Hub (pre-tournament) ⚪

> Verifies Spec C Plan 3's public stats hub. Pre-tournament data is sparse but the page must render cleanly.

- [ ] `/worldcup/stats` loads (publicly accessible, logged out is fine)
- [ ] Phase chip reads "Pre-Tournament" (per CLAUDE.md `current_phase` derivation, **not** mangled by `|title`)
- [ ] Country / tier KPIs render with empty / zero-baseline data
- [ ] Tier combos table renders (may be sparse with only 2 enrolled players)

**Notes:**

---

## Section 5: Home state machine — `out` + `pre` 🔴

> Verifies Spec B's `build_home_context` dispatcher and the `_home_out` / `_home_pre` partials. `live` and `post` are exercised in §9 and §11.

### 5A: Logged-out home → `_home_out` partial

Incognito window:

- [ ] `/` renders the `_home_out` partial (CCC bone-paper hero, login + register CTAs, no enrolled-player content)
- [ ] Hero typography uses `.hero-headline` / `.hero-subhead` (Plan 5 visual polish — distinct subordinate weights)

### 5B: Logged-in pre-deadline, **not enrolled in WC** — join CTA

- [ ] Register a third throwaway user **without** enrolling in WC (or use testplayer1 after un-enrolling — just need a logged-in non-enrolled state)
- [ ] `/` shows the join-the-cup treatment (not the enrolled `_home_pre` content)

### 5C: Logged-in pre-deadline, **enrolled** — `_home_pre` partial

Logged in as `testplayer1` (already enrolled):

- [ ] `/` renders `_home_pre` partial
- [ ] Picks summary card renders with all 9 picks listed
- [ ] "Tracking starts {date}" copy present (sparkline/dossier section is honest about empty pre-tournament data)
- [ ] Recent-results section either absent or empty (correct pre-tournament)

**Notes:**

---

## Section 6: Game switcher + Golf/CFB regression ⚪

> Quick smoke check that Spec A's brand foundation didn't break Golf or CFB blueprints, and the game switcher in the navbar wires up correctly.

- [ ] Navbar game switcher dropdown shows: Golf Pick 'Em, CFB Survivor, World Cup Fantasy
- [ ] `/golf/` loads — no 500; sub-nav swaps to Golf theme (Augusta green / gold accents)
- [ ] `/cfb/` loads — no 500; sub-nav swaps to CFB theme (crimson / midnight)
- [ ] `body.game-golf` / `body.game-cfb` CSS class injected (inspect via DevTools)
- [ ] Switching back to `/worldcup/` restores the WC theme

**Notes:**

---

## Section 7: Admin two-tier scoping 🔴

> Verifies the two-tier admin invariant from CLAUDE.md: platform admin (`User.is_admin`) is universal override; enrollment-scoped admin works for delegated game admin; non-admins are blocked.

### 7A: Platform admin universal override

Log in as your platform admin account (the user created via `flask create-admin`):

- [ ] `/worldcup/admin/` — admin dashboard loads
- [ ] `/golf/admin` — golf admin loads (even without golf enrollment, because platform admin overrides)
- [ ] `/cfb/admin` — same

### 7B: Non-admin blocked

Log in as `testplayer1`:

- [ ] `/worldcup/admin/` → flash error + redirect (NOT a 500, NOT a silent allow)
- [ ] `/worldcup/admin/match/1` → blocked
- [ ] `/golf/admin` → blocked
- [ ] `/cfb/admin` → blocked

**Notes:**

---

## Section 8: Tournament prep — flip the deadline

> The next sections (§9–§11) require `worldcup_state()` to return `'pre'` no longer — they need `'live'` and eventually `'post'`. On production, `WC_FAKE_NOW` is silently ignored (`ENVIRONMENT=production`), so the only path is to set the deadline to a past datetime in the canonical definition site, restart the service, and **revert before §14's DB reset.**
>
> ⚠️ **REVERT REMINDER:** Section 14 starts by reverting this edit. If you stop testing partway through and forget to revert, you will ship a yesterday-deadline to real players. Set a phone reminder.

### 8A: SSH and edit the deadline

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
sudo nano games/worldcup/constants.py
```

- [ ] Find the line: `TOURNAMENT_DEADLINE_UTC = datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))`
- [ ] Change it to: `TOURNAMENT_DEADLINE_UTC = datetime(2026, 5, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))` (or any clearly-past date)
- [ ] Save (`Ctrl+X`, `Y`, Enter)

```bash
sudo systemctl restart fantasy-platform
sudo systemctl status fantasy-platform --no-pager | head -10
```

- [ ] Service is `active (running)` after restart

### 8B: Verify the deadline took effect

In a browser logged in as `testplayer1`:

- [ ] `/worldcup/picks` is now **read-only** (no edit form, no submit button)
- [ ] A flash / banner indicates picks are locked / deadline has passed

Try to bypass via direct POST:

```bash
# From your Mac terminal — replace SESSION_COOKIE with the value from your browser DevTools
curl -X POST https://<your-live-domain>/worldcup/picks \
  -H "Cookie: session=<SESSION_COOKIE>" \
  -d "csrf_token=fake" \
  --verbose 2>&1 | grep "< HTTP"
```

- [ ] Server returns a 3xx redirect or 4xx error — **NOT** a 200 / silent save

### 8C: Verify rivals' picks are now visible (post-deadline reveal)

Log in as `testplayer1`:

- [ ] `/worldcup/leaderboard/<testplayer2_id>` (player_detail) — testplayer2's picks ARE now visible (deadline_passed gate flipped)
- [ ] Per-pick accordion drill-down works on player_detail

**Notes:**

---

## Section 9: Live state — group stage simulation 🔴

> Drives `worldcup_state()` to `'live'` by entering 4 group-stage match results that exercise every multiplier path. Verifies the `_home_live` partial renders the dossier sparkline (after a manual snapshot backfill) and the recent-results card highlights `.is-roster-match` on testplayer1's picked teams.

> **Score-math expected values** (from `games/worldcup/services/scoring.py` — verified during plan-writing fact-finding):
> - Group win = `<GROUP_WIN_POINTS>` base × tier multiplier
> - Group draw = `<GROUP_DRAW_POINTS>` base × tier multiplier
> - Tier multipliers: T1=`<T1_MULT>`, T2=`<T2_MULT>`, T3=`<T3_MULT>`, T4=`<T4_MULT>`, T5=`<T5_MULT>`

### 9A: Backfill the snapshot table for the trend column

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks --backfill 7
```

- [ ] Command prints "Backfilled 7 days" (or equivalent); no errors
- [ ] (Note: all 7 backfilled days will share the current rank/score since we have no historical data — real differentiation accumulates only after live cron runs)

### 9B: Enter 4 group-stage results via admin

Log in as platform admin. Pick 4 specific matches that exercise each multiplier path:

| # | Match | Tier of winner / drawn team | Result | Expected score impact |
|---|---|---|---|---|
| 1 | Pick a match where one of testplayer1's **Tier 1 picks** plays | T1 | T1 wins, e.g., 2–0 | testplayer1: `<GROUP_WIN_POINTS> × <T1_MULT>` = X.X added |
| 2 | Pick a match where two **Tier 3** teams play, one of testplayer1's T3 picks involved | T3 | Draw, e.g., 1–1 | testplayer1: `<GROUP_DRAW_POINTS> × <T3_MULT>` = X.X added |
| 3 | A match where one of testplayer1's **Tier 4 (`<T4_TEAM>`)** picks plays | T4 | T4 wins (upset), e.g., 1–0 | testplayer1: `<GROUP_WIN_POINTS> × <T4_MULT>` = X.X added |
| 4 | A match where one of testplayer1's **Tier 5** picks plays | T5 | T5 wins, e.g., 2–1 | testplayer1: `<GROUP_WIN_POINTS> × <T5_MULT>` = X.X added |

For each match:

- [ ] Navigate to `/worldcup/admin/match/<match_id>`
- [ ] Enter the score
- [ ] Page auto-derives winner from score with aria-live confirmation (per archived-script `bf3ea6d`/`25cd5af`)
- [ ] Submit → success

After all 4:

- [ ] Click admin Recalc button (POST to `/worldcup/admin/recalc`) — instant; verifies the route works
- [ ] testplayer1's leaderboard total = sum of all 4 expected impacts
- [ ] testplayer2's leaderboard total reflects whichever subset of those 4 matches involved their picks
- [ ] Schedule page shows per-team attribution chips on completed matches (e.g., `MEX +3 base` per archived-script `b5a7b07`/`90833ca`)

### 9C: Group advancement form

Pick one group where you've entered enough results to call advancement:

- [ ] `/worldcup/admin/advancement` loads
- [ ] Submit advancement for that group (winner, runner-up, possibly best-3rd)
- [ ] Confirm submission persists (re-load page, values pre-filled)

### 9D: `_home_live` partial renders correctly

Log in as `testplayer1`, navigate to `/`:

- [ ] Home page now renders `_home_live` partial (NOT `_home_pre`)
- [ ] Dossier card visible with sparkline (will be flat — backfill produced 7 identical days, real movement only after future cron runs)
- [ ] Week-delta is shown (gated at ≥7 snapshots — backfill made this pass)
- [ ] Recent-results card lists the 4 entered matches
- [ ] Matches involving testplayer1's picks have the `.is-roster-match` highlight (subtle border/tint per Plan 5)

### 9E: Stats Hub during live state

- [ ] `/worldcup/stats` — phase chip reads "Group Stage" or similar (NOT "Pre-Tournament")
- [ ] Country / tier KPIs reflect the 4 entered matches

**Notes:**

---

## Section 10: Knockout simulation 🔴

> Drives the bracket from R32 to final. Verifies `/worldcup/admin/set-knockout` team assignment, the clear-team-assignment guard (locked when result entered), knockout scoring math, and the post-deadline ownership reveal on team_detail.

### 10A: Assign teams to one R32 match

- [ ] `/worldcup/admin/set-knockout/<R32_match_id>` loads
- [ ] "Edit Teams" button on knockout-stage rows of "Matches Needing Scores" (per archived-script `06781e4`)
- [ ] Assign two teams to the R32 match → save → page shows the assignment
- [ ] "Clear Team Assignment" button is now visible (per archived-script `359c278`)

### 10B: Enter R32 result + verify guard

- [ ] `/worldcup/admin/match/<R32_match_id>` — enter a result (e.g., 2–1)
- [ ] Submit → success
- [ ] Return to `/worldcup/admin/set-knockout/<R32_match_id>` — "Clear Team Assignment" is now **locked** with a hint to clear the result first
- [ ] Click admin Recalc → leaderboard updates with knockout points (use `points_for_pick_on_match` per CLAUDE.md — already-multiplied)

### 10C: Drive the bracket to a champion (~5 more matches)

Enter results for one path through the bracket:

- [ ] One R16 match (assign teams via set-knockout, enter result, recalc)
- [ ] One QF match (same)
- [ ] One SF match (same)
- [ ] The Final (same)
- [ ] The Third-Place Match (same)

Verify after each:

- [ ] Leaderboard math is internally consistent (totals only ever increase with each new match)
- [ ] Stage labels render correctly via `stage_label()` (e.g., "Semifinals", "Third-Place Match", **NOT** "Sf" / "Third_Place" — `|title` filter must NOT be in use per CLAUDE.md)

### 10D: Post-deadline ownership reveal on team_detail 🔴

Pick any team that testplayer1 picked. Log out (or stay logged in — D11 says hidden pre-deadline for everyone, but reveal post-deadline is for everyone too):

- [ ] `/worldcup/team/<team_id>` (logged out)
- [ ] Ownership count is now **visible** (e.g., "1 player picked this team" or "2 players picked this team")
- [ ] Percent is shown
- [ ] Picker names list shows `testplayer1` (and testplayer2 if they also picked it)

**Notes:**

---

## Section 11: Post state — champion crowned 🔴

> After the final + third-place results are entered in §10, the tournament `current_phase` flips to `'completed'` and `worldcup_state()` returns `'post'`. Verifies `_home_post` renders the champion banner, final roster recap, and `team.best_finish` labels render literally.

Log in as `testplayer1`, navigate to `/`:

- [ ] Home page renders `_home_post` partial (NOT `_home_live`)
- [ ] Champion banner card renders (`.card.wc-card.wc-hero-grad`) with the champion's name + `.champion-flag` emoji
- [ ] Hero typography (`.hero-headline` / `.hero-subhead`) renders with high contrast (Plan 5 dark-surface override applied)
- [ ] Final roster recap lists all 9 of testplayer1's picks
- [ ] If testplayer1 picked the champion, that row has the `.row-champion-pick` highlight (translucent overlay per Plan 5 lock)
- [ ] `team.best_finish` labels render literally — "Champion", "Round of 16", "Group Stage" — **NOT** raw codes like `'champion'` or `'r16'` (per CLAUDE.md `_BEST_FINISH_LABELS`)

Public surfaces:

- [ ] `/worldcup/leaderboard` — final ranks render with dense rank
- [ ] `/worldcup/stats` — phase chip flips to "Completed"

**Notes:**

---

## Section 12: Cron + email + monitoring smoke 🔴

> Verifies cron jobs are actually running on the live server, the SMTP path produces real email, and monitoring is configured before the announcement.

### 12A: Cron logs (current state)

```bash
ssh deploy@<your-droplet-ip>
ls -la /var/log/fantasy/
tail -n 20 /var/log/fantasy/worldcup-recalc.log
tail -n 20 /var/log/fantasy/worldcup-snapshot.log
tail -n 20 /var/log/fantasy/golf-live.log
tail -n 20 /var/log/fantasy/cfb-scores.log
```

- [ ] All log files exist (created by cron jobs already running) — if any are empty, cron may have never fired for that job
- [ ] Recent timestamps in `worldcup-recalc.log` (cron runs every 10 min)
- [ ] No Python tracebacks in any log

### 12B: Verify the cron actually fires (~12-min passive wait)

- [ ] Note the latest timestamp in `worldcup-recalc.log`
- [ ] Leave the SSH session open, work on §13 mobile pass for ~12 min
- [ ] Re-tail `worldcup-recalc.log` — a new entry appeared (cron windows that fire every 10 min must have triggered at least one new run)

### 12C: Email — second password reset

- [ ] Log out, `/forgot-password` for `bhagstrom0+test1@gmail.com`
- [ ] Email arrives within 2 minutes from "Corrupt Commish Club"
- [ ] Reset link works (don't actually need to reset again — just verify the click loads the page)

### 12D: Monitoring

- [ ] UptimeRobot dashboard shows the Fantasy Platform monitor as **Up** (green) with a recent successful check
- [ ] DigitalOcean Monitoring → Alerts shows the three resource alerts configured (CPU > 80%, Memory > 85%, Disk > 80%)
- [ ] (Optional) Trigger a synthetic outage check: `sudo systemctl stop nginx`, wait 5 min, see UptimeRobot fire, then `sudo systemctl start nginx`. Skip if you don't want the noise.

**Notes:**

---

## Section 13: Mobile pass — real device ⚪

> Re-walks the visually-redesigned surfaces on a real phone (not Chrome DevTools emulation). DevTools won't catch real touch-target issues or actual font rendering at the device DPI.

On your iPhone or Android (connect to the live URL via Cloudflare):

- [ ] `/` (home, currently in `_home_post` after §11) — champion banner readable, hero typography distinct, no horizontal scroll
- [ ] `/worldcup/picks` (read-only post-deadline) — tier cards stack, no truncation
- [ ] `/worldcup/leaderboard` — table either scrolls horizontally with indicator OR uses card layout; nothing truncated
- [ ] `/worldcup/team/<team_id>` — Plan 2 team_detail page renders cleanly, ownership ribbon legible
- [ ] `/worldcup/leaderboard/<testplayer2_id>` (player_detail) — accordion drill-down tappable
- [ ] `/worldcup/stats` — KPI cards stack, charts/tables not cut off
- [ ] `/worldcup/schedule` — match list readable, CT timestamps visible
- [ ] Sub-nav scrolls horizontally with the scroll indicator (per archived-script Group C2)
- [ ] Hero typography legibility on dark surfaces (Plan 5 contrast lock — `.text-success` / `.text-danger` and `.text-muted` overrides on `.card.wc-card`)

**Notes:**

---

## Section 14: Cleanup — restore deadline + reset DB 🔴

> ⚠️ **Two destructive operations.** Both must complete before launch announcement.
>
> Step 1 reverts the deadline edit from §8. Step 2 wipes ALL test data (test users, all entered match results, all snapshot rows) and re-seeds the WC tournament shells. Both use `sudo systemctl restart fantasy-platform` to pick up changes.

### 14A: Restore the deadline

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
sudo nano games/worldcup/constants.py
```

- [ ] Find the modified `TOURNAMENT_DEADLINE_UTC` line (set in §8 to yesterday)
- [ ] Restore it to: `TOURNAMENT_DEADLINE_UTC = datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))`
- [ ] Save (`Ctrl+X`, `Y`, Enter)

```bash
sudo systemctl restart fantasy-platform
```

- [ ] Service restarts cleanly

### 14B: Verify-on-prod guard before any destructive command

Inside the SSH session:

```bash
cat .env | grep DATABASE_URL
```

- [ ] **Connection string contains `db.ondigitalocean.com`** — this confirms you're about to wipe the production Postgres, not a local SQLite
- [ ] If the URL does NOT match, **STOP** — investigate before running any `db downgrade`

### 14C: Wipe + reseed

```bash
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db downgrade base
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db upgrade
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup init
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask create-admin
```

- [ ] `db downgrade base` — drops all tables; outputs Alembic "Running downgrade" lines
- [ ] `db upgrade` — re-applies all migrations; outputs Alembic "Running upgrade" lines
- [ ] `worldcup init` — seeds 48 teams + 104 match shells
- [ ] `create-admin` — prompts for username, email, password — use **your real admin credentials** (this is the production launch admin user)
- [ ] `flask worldcup status` — prints **48 teams, 104 matches, 0 completed, 0 enrolled**

**Notes:**

---

## Section 15: Post-reset sanity — the launch baseline 🔴

> Final pre-announcement sanity. Confirm the world is clean and the freshly-recreated admin can do what every real player will do first.

### 15A: Re-verify the deadline value

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask shell
```

In the shell:

```python
from games.worldcup.constants import TOURNAMENT_DEADLINE_UTC
print(TOURNAMENT_DEADLINE_UTC)
exit()
```

- [ ] Printed value: `2026-06-11 19:00:00+00:00` — **NOT** any other date

### 15B: Admin user state

In a browser, log in as the freshly-created admin:

- [ ] `/worldcup/admin/users` shows **only the admin** — no `testplayer1`, no `testplayer2`, no third throwaway user
- [ ] `/worldcup/admin/` dashboard: 0 enrolled players, 0 completed matches

### 15C: First-touch flow (mirror what every real player does)

Still as admin (or register a fresh real user):

- [ ] `/worldcup/picks` loads with the **empty pick form** (no pre-selected picks)
- [ ] All 5 tier sections render with their full team rosters
- [ ] Submit button is disabled until 9 valid picks chosen
- [ ] (Don't actually submit picks unless you want them locked-in for the real cup)

### 15D: Public surfaces are production-ready

Logged out:

- [ ] `/` renders `_home_out` partial with brand mark + login/register CTAs
- [ ] `/worldcup/leaderboard` is empty (or shows only the admin if they enrolled)
- [ ] `/worldcup/stats` phase chip back to "Pre-Tournament"
- [ ] `/worldcup/schedule` shows all 104 matches with CT timestamps, none completed

### 15E: Announcement gate

- [ ] All 🔴 sections (0, 1, 2, 3, 5, 7, 8, 9, 10, 11, 12, 14, 15) are 100% ✅
- [ ] All ⚪ sections noted, blockers triaged or post-launch tickets filed
- [ ] **Only now** announce launch to real players

**Notes:**

---

## If anything goes red

Use these to recover from a failed section without abandoning the launch.

**Restore the deadline (if §14 was skipped or failed):**

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
sudo nano games/worldcup/constants.py
# Set TOURNAMENT_DEADLINE_UTC back to: datetime(2026, 6, 11, 19, 0, 0, tzinfo=ZoneInfo("UTC"))
sudo systemctl restart fantasy-platform
```

**Roll back code to a known-good `main` SHA:**

```bash
ssh deploy@<your-droplet-ip>
cd /home/deploy/fantasy-platform
git fetch origin
git reset --hard origin/main
./deploy.sh
```

(Resets the local checkout to the latest `main` from GitHub, including reverting any §8 hand-edit since the SSH edit was never committed.)

**Roll back DB to a prior migration:**

```bash
cd /home/deploy/fantasy-platform
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask db downgrade <prior-revision-sha>
```

(Use `flask db history` to find the target revision.)

**Stop the world (full outage, intentional):**

```bash
sudo systemctl stop fantasy-platform nginx
```

UptimeRobot will fire within 5 minutes. Re-start with `sudo systemctl start nginx fantasy-platform` after the issue is resolved.

---

*End of script.*
````

- [ ] **Step 2: Verify the file was written correctly**

```bash
wc -l "docs/production-launch-test-script.md"
grep -c "^## Section" "docs/production-launch-test-script.md"
grep -c "^- \[ \]" "docs/production-launch-test-script.md"
```

Expected: ~750+ lines; **15** section headings (Sections 0–15 = 16 actually, including the "How to use" preamble — but `## Section ` matches only the numbered ones); 100+ checkboxes.

- [ ] **Step 3: Spot-check the substituted values**

```bash
grep -n "<T1_MULT>\|<T4_MULT>\|<T4_TEAM>\|<GROUP_WIN_POINTS>\|<GROUP_DRAW_POINTS>" "docs/production-launch-test-script.md"
```

Expected: **zero matches.** If any placeholder remains, the §4.1 fact-finding values weren't substituted. Fix inline before commit.

### 4.3 Commit

- [ ] **Step 1: Stage and commit the new test script + the archive move (if not already)**

```bash
git add "docs/production-launch-test-script.md"
git status --short
```

Expected: `A  docs/production-launch-test-script.md` (and the rename from Task 3 should already be committed).

```bash
git commit -m "$(cat <<'EOF'
docs: add Production Launch Test Script for post-redesign go-live

Walks the live URL through pre-flight, out/pre home states, registration +
auth (with real password-reset email verification), WC enrollment + picks +
pre-deadline privacy invariants (D11 ownership), Stats Hub, Spec A chrome
checks, two-tier admin scoping, then a full tournament simulation:
SSH-edit TOURNAMENT_DEADLINE_UTC to past, enter 4 group results + 6 KO
results to crown a champion, verify _home_live + _home_post partials,
post-deadline ownership reveal, cron + email + monitoring smoke, real-
device mobile pass. Ends with deadline restoration + DB reset to clean
launch baseline (48 teams, 104 matches, 0 completed, 0 enrolled, admin-
only user).

Replaces archived docs/archive/2026-04-11-human-e2e-test-script.md.
Implements spec §4 of docs/superpowers/specs/2026-05-06-go-live-readiness-design.md.
EOF
)"
```

Expected: commit succeeds.

---

## Task 5: Push branch + open PR for CodeRabbit review

**Files:** None — this task pushes the worktree branch and creates a GitHub PR.

- [ ] **Step 1: Confirm branch state**

```bash
git log --oneline main..HEAD
```

Expected: 3 commits on `worktree/go-live-readiness`:
1. `docs(plans): refresh production deployment plan post-redesign` (Task 2)
2. `docs(archive): move pre-redesign Human E2E test script to docs/archive` (Task 3)
3. `docs: add Production Launch Test Script for post-redesign go-live` (Task 4)

- [ ] **Step 2: Push the branch**

```bash
git push -u origin worktree/go-live-readiness
```

Expected: `Branch 'worktree/go-live-readiness' set up to track 'origin/worktree/go-live-readiness'.`

- [ ] **Step 3: Open the PR**

```bash
gh pr create --title "Go-live readiness — deployment plan refresh + new Production Launch Test Script" --body "$(cat <<'EOF'
## Summary
- Refreshes `docs/superpowers/plans/2026-04-21-production-deployment.md` with six in-place edits reflecting post-redesign reality (Specs A, B, and C Plans 1–5 merged; sports-data API deferred; Task 20.5 dropped; pool-pre-ping callout; Task 5 expected-diff softened; Phase 5.5 cross-reference)
- Archives the April-11 Human E2E test script to `docs/archive/`
- Adds a new `docs/production-launch-test-script.md` for post-redesign go-live: full World Cup simulation on production via SSH-edited deadline + admin-entered match results, then DB reset to clean launch baseline

## Driver spec
`docs/superpowers/specs/2026-05-06-go-live-readiness-design.md`

## Test plan
- [ ] CodeRabbit review of the two doc changes
- [ ] Brad reads `docs/production-launch-test-script.md` end-to-end and flags any section that's unclear before executing it against the live URL
- [ ] Brad reads the deployment-plan diff and confirms the edits don't break any in-flight task he was about to run

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed. Save it for CodeRabbit to find.

- [ ] **Step 4: Confirm the PR is up**

```bash
gh pr view --web
```

(Or paste the URL in a browser.) Expected: PR page shows 3 commits, 3 files changed, +X / -Y diff. CodeRabbit's review will land within ~5 minutes of PR creation per project memory `feedback_coderabbit_timing`.

---

## Self-review checklist (run before declaring the plan complete)

**1. Spec coverage (§3 + §4):**
- §3.1 sequencing note → Edit 2.1 ✅
- §3.2 test-count drift → Edit 2.2 ✅
- §3.3 Task 20.5 drop + fold to Task 20 → Edit 2.3 ✅
- §3.4 pool-pre-ping callout → Edit 2.4 ✅
- §3.5 soften Task 5 → Edit 2.5 ✅
- §3.6 Phase 5.5 cross-reference → Edit 2.6 ✅
- §4.1 front matter → Task 4 file content ✅
- §4.2 15 sections → Task 4 file content ✅
- §4.3 per-section template → Task 4 file content (every section follows the same shape) ✅
- §4.4 score-math expected values → Task 4.1 fact-finding + 4.2 §9 substitution ✅
- §4.5 production safeguards (df/free, +alias, deadline-revert callouts, DATABASE_URL guard, rollback box) → Task 4 file content ✅
- §4.6 dropped content (changelog, wrong file path, pre-completed checkboxes, 127.0.0.1) → Task 4 file content (none of those remain) ✅

**2. Placeholder scan:**
- Task 4.2 explicitly lists `<T1_MULT>` etc. as substitution markers, with a verification step that grep returns zero. No other placeholders.
- Task 4 commit instructions show the literal commit body via heredoc.

**3. Type / path consistency:**
- All references to the deadline constant use `games/worldcup/constants.py` (the canonical site).
- All references to the test script use the new path `docs/production-launch-test-script.md`.
- All references to the spec use the committed spec path.

---

## Done definition

- 3 commits land on `worktree/go-live-readiness`: deployment plan refresh, archive move, new test script.
- Branch pushed; PR open; CodeRabbit review requested.
- After CodeRabbit + Brad review the PR and approve, the worktree merges into `main` (squash). Brad then resumes deployment-plan Task 11 and the new test script becomes the launch signoff record.
