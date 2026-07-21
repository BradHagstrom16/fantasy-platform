# Engineering Backlog & Session Handoff — 2026-07-21

**Purpose:** the standing list of known-but-unfixed work, with enough context that a
cold session can pick any item up without re-deriving it. Written after PR #120
(dependency pins + deploy hardening).

**How to use this doc:** pick an item, read its *Evidence* line, re-verify the numbers
before quoting them (see [Why re-verify](#why-re-verify)), then work it as its own PR
per repo practice — one scoped surface, CodeRabbit cycle, merge in the same session.

**Status key:** 🔴 blocks a dated milestone · 🟠 real bug, undated · 🟡 tech debt · ✅ verified stale, no action

---

## Why re-verify

Two of the six items inherited from the earlier audit turned out to be **wrong when
checked against the code** — one badly. In the same session, a "291 lines / 34 files"
figure that had been copied into two documents was off by ~40%. Numbers in a backlog
rot faster than the code they describe.

Every item below carries a *verified 2026-07-21* line with the command that produced
it. Re-run it. Don't quote a number you haven't reproduced.

---

## Priority 1 — Deploy script hardening ✅ COMPLETE

All three surfaced during PR #120 and are the same surface. **1.1 and 1.3 shipped in
PR #121**, **1.2 in PR #123** (all merged 2026-07-21) and all are verified on the droplet.
**Priority 1 is closed.**

Regression cover for this surface: `tests/test-deploy-guards.sh` (95 assertions; run it
with `USE_REAL_FLOCK=1` on the droplet, where it is 90 — case L needs the shim). Extend it
rather than hand-testing anything on this surface.

### 1.1 `deploy.sh` must re-exec itself after a self-update ✅ SHIPPED (PR #121)

**Resolved 2026-07-21.** Hashes the script either side of `git pull` and re-execs when it
changed, bounded to one restart by `DEPLOY_REEXECED`. Verified on the droplet: Brad's
proof-line deploy re-executed and ran the pulled version in the same run, and the harness
passes the re-exec cases against the deployed script with the real `flock(1)`. Original
write-up kept below for context.

**The bug, observed live 2026-07-21.** `deploy.sh` runs `git pull` as step 1 — which can
replace `deploy.sh` itself — but the already-running bash process continues executing the
*old* script it loaded at startup. The first post-#120 deploy therefore pulled a script
containing the systemd-unit sync and then **did not run it**, printing `==> Done. App is
live.` and exiting 0. The unit stayed stale; only a second `./deploy.sh` applied it.

**Why it matters:** every future change to `deploy.sh` silently takes effect one deploy
late. This is ADR-040's failure shape recurring — a repo file assumed live that isn't —
and it defeats the warning-gating added in #120, because the *old* script has no gating.

**Missed by:** six CodeRabbit rounds, four specialist review agents, and the author. All
reviewed the script as text; none asked what happens when it rewrites itself mid-run.
Only reading the running process args (`ps -o args= -C gunicorn`) exposed it.

**Approach:** after `git pull`, compare the script's pre-pull hash to its post-pull hash;
if changed, `exec "$0" "$@"` with a guard env var (e.g. `DEPLOY_REEXECED=1`) so it can
re-exec at most once. Announce it (`==> deploy.sh updated; restarting with new version`)
so the operator sees why the output repeats.

**Verify the fix by:** committing a trivial `echo` to `deploy.sh`, deploying once, and
confirming the new echo appears on that *same* run.

### 1.2 Generalize the unit sync to all of `deploy/` ✅ SHIPPED (PR #123)

**Resolved 2026-07-21.** `deploy.sh` now loops every `deploy/*.service` and
`deploy/*.timer` through a `sync_unit` function carrying #120's per-unit logic intact
(validate the repo file → compare content *and* mode/owner → install to temp → atomic
rename), with one `daemon-reload` after the loop. Each unit gets its own verdict, so one
failure warns and counts without aborting the others; `deploy_warnings` still gates the
exit code. Policy recorded as **ADR-041**.

**This item's own evidence line was wrong, and is corrected here.** It claimed **21**
units, citing `ls deploy/*.service deploy/*.timer | wc -l`. That command returns **29** —
1 `fantasy-platform`, 10 `cfb-*`, 10 `golf-*`, 8 `worldcup-*`. It undercounted by exactly
the 8 `worldcup-*` files, and was wrong when written (all unit files predate the doc), not
stale since. Third bad figure this document has produced; see *Why re-verify* above.

**Absent-unit policy: mirror, not skip-with-notice.** The original recommendation here was
skip-with-notice; it was **rejected** during implementation. Reasoning in ADR-041 —
briefly: every alternative (a flag, a manifest) still requires a human at launch week to
remember a second step, which is the same shape as the `sudo cp` that cost five weeks;
installing is not enabling, as the eight `worldcup-*` units sitting in `/etc` `disabled`
already demonstrate; and skip-with-notice would print "20 units skipped" on every deploy
until Golf migrates (~Jan 2027), which trains the operator to ignore deploy output.

**Verified on the droplet (read-only, 2026-07-21), before deploying:**

- All 29 repo units pass `systemd-analyze verify`, including every `.timer` whose
  `.service` is not installed — `verify` adds the file's own directory to the unit search
  path and resolves the sibling in `deploy/`. This had been an open design question; it
  needed no design work.
- Of the 9 units already installed, all 9 were byte-identical to the repo at `644
  root:root`, so the change was a no-op for everything present.
- Dry-run prediction: `9 in sync, 0 updated, 20 installed, 0 failed` — matched the real
  deploy exactly.

**Recorded hazard — narrower than first written, corrected after checking the box.**
`golf-*.timer` files now exist in `/etc` while Golf still runs on PythonAnywhere, so
enabling them would double-run those syncs (double API spend, double writes). The obvious
misfire is *not* reachable: `systemctl enable --now golf-*.timer` is rejected by systemd
outright — *"Glob pattern passed to enable, but globs are not supported for this"* — and
`systemctl`'s glob expansion elsewhere only matches units already in memory, which a
disabled timer is not. What **is** reachable is any form where the **shell** does the
expanding: a `for` loop over `/etc/systemd/system/golf-*.timer`, or the same glob typed
while `cd`'d into that directory, both of which hand `systemctl` real paths. Enable CFB's
timers by explicit name (transition plan §6F) and the question never arises. `deploy.sh`
prints an explicit `NOT enabled` note on any first install.

**Known gap, accepted.** Orphans are not handled: a unit deleted or renamed in `deploy/`
leaves its old copy in `/etc` untouched and unreported. Detecting "ours" would need either
game-name knowledge in `deploy.sh` or persisted state, and auto-removing units is
dangerous. Remove them by hand if a unit is ever retired.

### 1.3 `flock` guard against concurrent deploys ✅ SHIPPED (PR #121)

Two overlapping `./deploy.sh` runs would execute concurrent `flask db upgrade` against
Postgres. #120 added `concurrency:` groups to both CI workflows but left the deploy
script itself unguarded. `flock -n` on a lockfile, exiting with a clear message if held.

**Resolved 2026-07-21.** `flock -n` on fd 200 against
`/home/deploy/.fantasy-platform-deploy.lock`, taken before the pull. Verified live on the
droplet: with the lock held, `./deploy.sh` aborted with exit 1 naming the holder's PID and
never reached migrations. Two things worth knowing before touching this code:

- The lock is acquired **once** and inherited across the 1.1 re-exec via fd 200. It must
  not be re-acquired — `flock(2)` denies a second lock taken through a fresh `open()` in
  the same process, so a re-acquire would deadlock the deploy against itself.
- `flock -n` exit **1** means contention specifically; other failures use `sysexits.h`
  codes and are treated as errors (warn, continue unlocked), so a filesystem with limited
  `flock(2)` support cannot masquerade as a competing deploy. `/home/deploy` is `ext4` on
  `/dev/vda1` — confirmed 2026-07-21, not assumed.

---

## Priority 2 — Correctness bugs 🟠

### 2.1 Flask-Limiter `memory://` with 3 workers 🟠

**Evidence (verified 2026-07-21):** `extensions.py:26` → `storage_uri="memory://"`;
`deploy/fantasy-platform.service` → `--workers 3`.

Each Gunicorn worker keeps its **own** in-process counters, so a limit configured as
10/min is effectively **~30/min** in production, non-deterministically (depends which
worker the request lands on). Pre-existing, not an upgrade regression.

**Security-relevant:** the rate limiter is what protects `/login` and `/forgot-password`
from credential stuffing and enumeration. The anti-enumeration design of the
forgot-password route (CLAUDE.md, Auth section) implicitly assumes the limiter works.

**Approach:** shared storage backend — Redis is the standard answer, but adds a service
to the droplet. Postgres-backed storage via `limits` is possible and reuses existing
infrastructure. **Decide the backend before writing code**; that choice is the whole PR.
Note the local dev/test path should stay `memory://` (tests must not need a service).

### 2.2 `Model.query` migration blocks Flask-SQLAlchemy 4 🟡

**Evidence (verified 2026-07-21):**
```bash
git ls-files '*.py' | xargs grep -cE '\b[A-Z][A-Za-z0-9_]*\.query\b' | awk -F: '{s+=$2} END {print s}'
```
→ **495 lines / 64 files** repo-wide; **356 lines / 35 files** of app code, remainder in
`tests/` (which must migrate too).

⚠️ **The "291 lines / 34 files" figure in the earlier plan is wrong** — off by ~40%, and a
separate "~305" had propagated into CLAUDE.md. Both were corrected in ADR-039 and
CLAUDE.md during PR #120. If you see either number anywhere else, it is stale.

Fine today: `Model.query` is fully supported with zero deprecation warnings on the pinned
SQLAlchemy 2.0.51 / Flask-SQLAlchemy 3.1.1. It is **only** a blocker for Flask-SQLAlchemy
4.0, which removes it — and #120 pins that away deliberately (ADR-039).

**Standing rule (CLAUDE.md): do not mass-migrate.** Fix only `.query` lines already in the
current diff. `.delete()` / `.count()` / `scalar↔scalars` transforms carry uneven semantic
risk. A full migration is its own dedicated project, and **1.4 below is its prerequisite**.

### 2.3 `except Exception` conflates failure modes 🟡

The earlier plan listed "uncaught `.json()` decode" at `games/cfb/services/automation.py:173,392`
and `score_fetcher.py:61`. ✅ **Verified stale — all three are inside `try/except Exception`
blocks** and a malformed 200 body is caught, returning `0` or an error dict.

The residual, smaller point: `except Exception` cannot distinguish a network failure from
a malformed body, so both surface as `API request failed`. Worth narrowing when those
files are next touched for another reason. **Not worth its own PR.**

---

## Priority 3 — Test-suite leverage 🟡

### 3.1 No `tests/conftest.py` — highest-leverage prep work available 🟡

**Evidence (verified 2026-07-21):** `tests/conftest.py` **absent**; **120** test files
carrying **132** inline `@pytest.fixture` definitions, overwhelmingly the same
`app` / `client` pair re-declared.

**Why it is the best-value item on this list:** it is not cleanup, it is *blast-radius
reduction*. Every future framework upgrade — Flask-SQLAlchemy 4, SQLAlchemy 2.1, Werkzeug
3.2, Python 3.14 — currently means touching up to 132 fixture sites. Extracting a shared
conftest converts each of those migrations from a sweep into a handful of edits. Do this
**before** 2.2 or the 3.14 pass, not after.

**Approach:** additive, not a rewrite. Add `tests/conftest.py` with the canonical
`app`/`client` fixtures; delete inline duplicates file-by-file, running the suite after
each batch. Fixtures that genuinely differ (the `*_FAKE_NOW` seam variants, admin-session
setups) stay local — do not force them into the shared file. Note `tests/__init__.py`
exists and is what puts the repo root on `sys.path`; **do not delete it** — CI would break
while `python -m pytest` kept passing locally.

**Baseline:** 1749 tests passing as of `c5e5b3b`. Any conftest work must end at 1749.

### 3.2 Legacy SQLAlchemy relationship patterns 🟡

**Evidence (verified 2026-07-21):** `lazy='dynamic'` × **7** (all in
`games/golf/models.py`); `backref` × **22**; `back_populates` × **0**.

Both are legacy-but-supported in SQLAlchemy 2.0. `lazy='dynamic'` is soft-deprecated in
favour of `WriteOnlyMapped`. Bundle with Golf's Phase U (UI, ~Jan 2027) rather than doing
it standalone — the `lazy='dynamic'` uses are entirely in Golf, and that phase will be
touching those models anyway.

### 3.3 Nine `# noqa: E712` filters 🟡

**Evidence (verified 2026-07-21):** 9 occurrences across `games/cfb/services/game_logic.py`,
`games/worldcup/routes.py`, `games/worldcup/services/{home_context,notifications,scoring}.py`.

⚠️ **Read CLAUDE.md before touching these.** The convention is `.is_(True)` / `.is_(False)` /
`.is_not(None)` — and it explicitly warns that the naive Python-idiom rewrite
(`if x:` / `if not x:`) **silently breaks the query**. These are SQLAlchemy filter
expressions, not booleans. Five of the nine are in **frozen WC surfaces** (see the World
Cup section of CLAUDE.md) — leave those alone outside a revival.

Lowest priority on this list. Genuinely cosmetic.

---

## Priority 4 — Scheduled / dated work

### 4.1 Python 3.14.6 upgrade — "Pass 2" 🟡

Deliberately held out of #120 so a regression stays attributable to one change.
Pre-verified at the time: cp314 wheels exist on macOS *and* manylinux for every compiled
dependency; `python3.14-venv 3.14.6-1+noble1` available on the droplet's deadsnakes PPA;
no 3.14 stdlib landmines in the codebase.

Two couplings to update in the same PR: `.github/workflows/test.yml` pins
`python-version: "3.13"` with a comment saying to bump it alongside the droplet, and
`ruff.toml` sets `target-version = "py313"`. Nothing enforces either — they will not fail
loudly if missed. Do **3.1 first**; a 132-fixture suite is the wrong thing to debug a
runtime upgrade against.

### 4.2 CFB era changeover — Phase 5 🔴 (~Aug 17–24, 2026)

Not backlog — scheduled work with its own SSoT. See
`docs/superpowers/plans/2026-07-20-cfb-era-transition-plan.md` and the
`project_cfb_era_transition` memory. Phases 0–4 complete (PRs #117–#119); Phase 5 is the
two-line atomic registry flip plus changeover copy. Listed here only so a cold session
does not mistake this backlog for the whole picture.

---

## Operational learnings from PR #120

Recorded because both were paid for the hard way.

**1. Review artifacts by what they *do*, not what they *say*.** The self-modifying-script
bug (1.1) survived six CodeRabbit rounds and four specialist agents because everyone read
`deploy.sh` as text. The one check that caught it read the **running process**. When
reviewing anything that executes — deploy scripts, systemd units, CI workflows — ask what
happens at runtime, not whether the source looks right.

**2. Pinning creates an obligation.** #120 converted `>=` floors to `==` pins, then pinned
`click` at the locally-installed 8.3.1 — which sits inside PYSEC-2026-2132's affected
range. **Production had already drifted onto the patched 8.3.3**, so merging as-written
would have *downgraded prod onto a CVE*. Floors bought accidental patching at the cost of
silent divergence; pins buy convergence at the cost of watching advisories.
**Run `pip-audit -r requirements.txt` in any future dependency pass.** (Recorded in ADR-037.)

**3. `gh pr checks` is not a merge signal on this repo.** The "CodeRabbit — Review
completed" check reports only that a run finished; it stays green while the underlying
review says `CHANGES_REQUESTED`, and does not re-verify on push. Twice during #120 it
would have justified merging an unreviewed commit. Map reviews to commits instead:
```bash
gh api repos/BradHagstrom16/fantasy-platform/pulls/<N>/reviews \
  --jq '.[] | "\(.submitted_at) \(.state) commit=\(.commit_id[0:8])"'
```
and compare the last row to `git rev-parse --short HEAD`.

**4. Post-deploy verification is mandatory and is now in CLAUDE.md.** `deploy.sh` exiting 0
proves the script ran, not that the config is live. The load-bearing check is
`ps -o args= -C gunicorn` — it reads what is actually running rather than what a file
claims. It is what caught 1.1.

---

## Current state at time of writing

| | |
|---|---|
| `main` | `c5e5b3b` (PR #120 merged 2026-07-21 17:57Z) |
| Tests | **1749 passing**, ruff clean, `pip-audit` clean |
| Production | deployed and verified — unit in sync, `--timeout 120` + `--no-control-socket` live on the running process, gunicorn 26.0.0 `sync` worker, 3 workers, site 200 |
| Prod ↔ repo pins | converged (`requests` 2.34.2, `SQLAlchemy` 2.0.51, `click` 8.3.3) |
| Active era | CFB Survivor launch prep; WC archived; Golf UI phase ~Jan 2027 |
