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

Regression cover for this surface: `tests/test-deploy-guards.sh` (**132** assertions as of
2026-08-13, up from 102 when cases V–Z added the preset path in ADR-044; run it with
`USE_REAL_FLOCK=1` on the droplet, where it is **127** — case L needs the shim). Extend it
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

**Recorded hazard — rewritten twice, both times because the guess was wrong and the box
was right.** `golf-*.timer` files now exist in `/etc` while Golf still runs on
PythonAnywhere, so enabling them would double-run those syncs (double API spend, double
writes). Three mechanisms, in the order they were understood:

1. `systemctl enable --now golf-*.timer` — **not reachable.** systemd rejects it outright
   (*"Glob pattern passed to enable, but globs are not supported for this"*), and
   `systemctl`'s globbing elsewhere matches only units already in memory, which a disabled
   timer is not. This was the originally-stated hazard, and it was wrong.
2. Shell-expanded globs — **reachable.** A `for` loop over
   `/etc/systemd/system/golf-*.timer`, or the same glob typed while `cd`'d into that
   directory, hands `systemctl` real paths and works.
3. **`systemctl preset-all` — reachable, and the one that actually matters.** No glob is
   involved and no game is named: it would enable **all fourteen** timers at once. Found by
   reading `systemctl list-unit-files` after the first real deploy, which reports every
   timer `disabled` with **`PRESET enabled`**. Cause: the droplet carries exactly one preset
   file, `/usr/lib/systemd/system-preset/90-systemd.preset`, with **no catch-all rule**, so
   unmatched units fall through to systemd's built-in *enable* default. The `.service`
   units are immune — all fourteen are `static` (no `[Install]` section), so preset cannot
   touch them. Only the timers are exposed.

   **Fourteen, not ten** — the four archived `worldcup-*` timers carry
   `WantedBy=timers.target` too, and are the worst of the set: `worldcup-digest.timer` and
   `worldcup-digest-player.timer` mail **real players** about a tournament that concluded
   2026-07-19, and `worldcup-sync.timer` would resume scoring against archived data. That
   exposure is **not new** — those units were installed 2026-06-02 and mothballed
   2026-07-20, so `preset-all` could have re-enabled them for weeks before PR #123. The
   mirror policy did not create it; looking at the preset column is what surfaced it.

Enable by explicit unit name (transition plan §6F) to avoid the glob paths — but note that
does **not** address `preset-all`, which is independent of how anything was enabled.
`deploy.sh` prints an explicit `NOT enabled` note on any first install. The only mechanical
defence is a preset file — see 2.4, whose case the `worldcup-*` finding strengthened.

> **Closed 2026-08-13 (ADR-044).** The preset file shipped. Also: "fourteen" is now
> **nineteen** unit files, of which fifteen are disabled — five `docket-*` pairs landed in
> PR #142 after this was written. The count reached nineteen the same way it reached
> fourteen, by silent inheritance, which is why `tests/test_systemd_preset.py` now fails CI
> on any `deploy/*.timer` prefix with no preset rule.

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

### 2.1 Flask-Limiter `memory://` with 3 workers ✅ SHIPPED (PR #128)

**Resolution (2026-07-30):** storage is config-driven via `RATELIMIT_STORAGE_URI`
(`extensions.py` no longer passes a constructor `storage_uri`, which would override the
config key). Production defaults to `redis://localhost:6379/0` with
`RATELIMIT_IN_MEMORY_FALLBACK_ENABLED = True` (a Redis outage degrades to per-worker
limiting, never a 500); dev stays `memory://`; TestingConfig pins `memory://` regardless
of ambient env. `redis==8.1.0` pinned in `requirements.txt` (zero transitives — no
`constraints.txt` change). Locks in `tests/test_rate_limit_storage.py`. Droplet needs a
one-time `apt install redis-server` before the deploy — see the PR body for the runbook.
Note the `limits` backend survey (2026-07-30): no Postgres storage exists in `limits`
5.8.0, so the "reuse existing infrastructure" option below was never real.

Original item as written 2026-07-21:

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

### 2.4 `preset-all` timer hazard — closed by a scoped preset policy ✅

**✅ SHIPPED 2026-08-13 (ADR-044).** `deploy/10-fantasy-platform.preset` → `/etc/systemd/system-preset/`,
installed by a dedicated `sync_preset` path in `deploy.sh` gated on a bash shape lint
(`systemd-analyze verify` rejects preset files outright). `disable worldcup-*.timer`;
`ignore` for `cfb-*`/`docket-*`/`golf-*`, which makes `preset-all` a no-op for
hand-managed families in **both** directions and needs no flip at any milestone —
that is the answer to the open judgement call at the end of this item. Covered by
`tests/test_systemd_preset.py` (17) and cases V–Z of `tests/test-deploy-guards.sh`
(102 → 132 assertions locally, 97 → 127 on the droplet). The World Cup units stay in
`deploy/` — see ADR-044 for why removing them would have reduced exposure by zero.

**The numbers below were stale by the time this shipped — re-verified on the droplet
2026-08-13.** There are **19** game timer unit files, not 14 (five `docket-*` landed in PR
#142); **15** are `disabled` with `PRESET enabled` (the four live docket timers are
`enabled`); box-wide the count is **21**, and the repo carries **39** units, not 29. The
19 `.service` units are all still `static`/immune. This item's own warning at the top of
the document came due on the item itself; the original text is kept below unedited as the
record of what was believed on 2026-07-21.

**Evidence (verified 2026-07-21, on the droplet after the 1.2 deploy):**
`systemctl list-unit-files 'cfb-*' 'golf-*' 'worldcup-*'` reports **14 timers** as
`disabled` with **`PRESET enabled`**; the 14 `.service` units are `static` and immune. The
droplet carries one preset file, `/usr/lib/systemd/system-preset/90-systemd.preset`, with
no catch-all rule, so unmatched units inherit systemd's built-in *enable* default.
`systemctl preset-all` would enable all 14 at once.

**Consequence, worst first:** `worldcup-digest.timer` and `worldcup-digest-player.timer`
send **email to real players** about a tournament that concluded 2026-07-19.
`worldcup-sync.timer` would resume scoring against archived data. The five `golf-*` timers
would double-run syncs that PythonAnywhere still owns. The five `cfb-*` timers would start
a season early.

**Not caused by PR #123.** The four WC units were installed 2026-06-02 and mothballed
2026-07-20 — `preset-all` could have re-enabled them for weeks beforehand. #123 added ten
more units to an existing exposure and, by prompting a look at the preset column,
surfaced it.

**This item was first written as a deliberate deferral (as 4.3) and is promoted here,
because the reasoning that justified deferring it was wrong.** That argument rested on the
exposure being finite and self-closing: Golf's ends at the ~Jan 2027 migration, CFB's at
launch. It does not hold for `worldcup-*`. WC is archived indefinitely with no migration
date, so **that portion of the risk never expires** — and it is simultaneously the
highest-consequence portion, being the only one that mails real people. A low annual
probability against an indefinite horizon is a different bet from one against a
twelve-month window.

A second objection also weakens: "it creates a second source of truth needing a flip at
each milestone." True for `cfb-*`/`golf-*`, **false for `worldcup-*`** — `disable
worldcup-*.timer` is permanent and never needs touching. A minimal preset file covering
only WC carries none of that cost.

**Approach:** `deploy/10-fantasy-platform.preset` → `/etc/systemd/system-preset/`, with
`disable worldcup-*.timer` at minimum. Preset files **do** accept globs, unlike `systemctl
enable` — a real asymmetry, and why this is a few lines rather than fourteen. Whether to
also list `cfb-*`/`golf-*` is a judgement call: it protects them until their milestones but
adds the flip-at-milestone cost above.

**The real work is not the file, it is the install path.** Preset files are not units, so
#123's `sync_unit` loop does not carry them — this needs its own path in `deploy.sh`, its
own validation, and its own `tests/test-deploy-guards.sh` cases. Do it as its own scoped
PR with droplet verification, not as a bolt-on. That is the *only* reason it was not done
in #124, which was docs-only and opened before this was understood.

**Interim mitigation:** do not run `systemctl preset-all` on the droplet. Note this is
exactly the "remember not to do the thing" posture that ADR-040 and ADR-041 exist to
replace, which is itself the argument for building the file.

**~~Interim mitigation~~ superseded 2026-08-13.** The preset file is the mechanical
defence, so `preset-all` is no longer a command that must be remembered-not-to-be-run:
it now leaves every game timer exactly as it found it, except that it would switch a
stray `worldcup-*` back off. `sudo systemctl preset-all --dry-run` prints what it would
do without doing it, and is the verification used in the shipping PR.

### 2.5 Rate-limit keys are Cloudflare edge IPs (`ProxyFix x_for=1`) ✅ SHIPPED (PR #129)

**Resolution (2026-07-30):** fixed at the nginx layer, not in the app. The 443 server
block in `deploy/nginx.conf` now carries `ngx_http_realip_module` directives: one
`set_real_ip_from` per published Cloudflare range (15 v4 + 7 v6, fetched 2026-07-30)
plus `real_ip_header CF-Connecting-IP;`. When — and only when — the TCP peer is a
Cloudflare address, nginx rewrites `$remote_addr` from `CF-Connecting-IP` (which
Cloudflare itself sets and overwrites; unforgeable through the proxy), so
`$proxy_add_x_forwarded_for` appends the **real client** as the last XFF entry and
`ProxyFix(x_for=1)` selects it. The app is untouched (`x_for` stays 1 — raising it
would trust a client-supplied XFF entry on direct-to-origin requests, which is why the
`x_for=2` sketch below lost: its firewall is load-bearing and fails hard on stale
ranges, while realip fails soft in every direction — stale range → that slice degrades
to edge-IP keying, never a block; grey-clouded DNS → peers aren't CF → correct IPs
anyway; direct-to-origin → headers ignored, keyed by true peer IP). Locks in
`tests/test_client_ip_keying.py` (ProxyFix hop contract + limiter wiring + nginx
source lock mirroring the range list). **`deploy/nginx.conf` is NOT synced by
`deploy.sh`** — install manually per the file's header comment (runbook in the PR
body); range-refresh recipe lives in the realip comment block. nginx-sync automation
deliberately deferred (needs its own SED anchors + sudo-shim allowances in
`tests/test-deploy-guards.sh`). Origin cloaking spun off as 2.6.

Original item as written 2026-07-30:

**Found 2026-07-30 while shipping 2.1.** `app.py:142` wraps the app in
`ProxyFix(x_for=1, ...)`. Behind the live chain (client → Cloudflare → nginx), nginx's
`$proxy_add_x_forwarded_for` produces `X-Forwarded-For: <client>, <cf-edge>`, and
`x_for=1` takes the **last** entry — so `request.remote_addr`, and therefore
`get_remote_address()` rate-limit keys, is the **Cloudflare edge IP**, not the client.

**Consequence:** rate-limit buckets are shared per CF edge IP. Pre-2.1 this was masked by
the per-worker-triple-limit bug; with shared Redis storage the "10 per minute" `/login`
guard becomes a single bucket for every user routed through the same edge IP. During a
launch-week signup rush (~26 people invited at once, many in the same metro hitting the
same PoP), legitimate 429s are plausible. It also weakens the brute-force guard in the
other direction: an attacker's key rotates with the edge IP.

**Fix sketch (decide before the ~Aug 17 signup push):** `x_for=2` trusts both hops and
yields the real client IP — with the caveat that a direct-to-origin request (bypassing
Cloudflare) could then spoof `X-Forwarded-For`; mitigations are restricting nginx to
Cloudflare IP ranges or keying off `CF-Connecting-IP` instead. Small diff, but it is
proxy-security semantics — its own scoped PR with a test that pins the header→key
behavior, not a bolt-on.

### 2.6 Origin not cloaked — direct-to-origin traffic bypasses Cloudflare ✅ SHIPPED (PR #130)

**Resolution (2026-07-30, ADR-043):** DO Cloud Firewall `fantasy-platform-fw` attached to
the droplet — inbound TCP 22 from anywhere (lockout guard) + 80/443 from Cloudflare's 22
published ranges only; default allow-all outbound kept; **ufw deliberately untouched**
(`ufw status` showing `Nginx Full ALLOW Anywhere` is expected forever — the cloud
firewall is the narrower outer gate, and rollback relies on ufw still allowing
everything underneath). Runbook with click-through, safety model, and the four-place
range-refresh recipe: `docs/superpowers/plans/2026-07-30-origin-cloak-do-firewall.md`;
the runbook's paste block is equality-locked to `CLOUDFLARE_RANGES` and (transitively)
`deploy/nginx.conf` by `tests/test_client_ip_keying.py::TestFirewallRunbookRangeSync` —
the live firewall is the one mirror no test can see (no DO API token, by design).
**Verified live 2026-07-30 (all timestamps UTC):** rules enforced at 20:46:32 — bare-IP
http flipped from `301` to timeout/exit-28 (dropped at DO's network layer, not
refused); bare-IP https likewise; `https://cccfantasy.com` stayed `HTTP/2 200`;
BatchMode SSH stayed alive; two established outbound connections to Managed Postgres
:25060 confirmed post-attach. **Rollback drill executed:** detach restored bare-IP
traffic in **~55s** (the propagation number DO doesn't publish); re-attach re-cloaked
within seconds (20:53:59), domain 200 + SSH re-verified. Detection story for the
accepted stale-allowlist risk: UptimeRobot red while the droplet is healthy ⇒ detach
first, debug second.

Original item as written 2026-07-30:

**Spun off from 2.5 (2026-07-30).** ufw on the droplet allows `'Nginx Full'` from
Anywhere (set up in the 2026-04-21 deployment plan, Task 14) and no DO cloud firewall
exists, so anyone who discovers the origin IP can hit nginx directly, bypassing
Cloudflare's WAF/DDoS layer entirely. **Not** a rate-limit-correctness gap — 2.5's
realip config keys direct traffic by its true peer IP (the CF headers are ignored when
the peer isn't a Cloudflare range) — this is defense-in-depth for the origin itself.
Mitigation: restrict 80/443 to Cloudflare's published ranges (ufw or, better, a DO
cloud firewall — editable without touching the droplet). **Needs its own PR with a
range-refresh story first**: unlike realip's fail-soft behavior, a stale allowlist
here hard-blocks legitimate CF traffic, which is exactly why it lost as the 2.5 fix
and must not ship as a casual bolt-on.

### 2.7 CFB reminder double-send debt — no per-window sent-flag 🟡

**Added 2026-08-11 (Docket eng review, outside-voice finding).** `deploy/cfb-remind.timer`
documents its own hazard: "Never schedule this more often than once per ~70-minute window:
there is no per-window sent-flag, so a faster cadence double-sends (audit §6)." Reminder
correctness depends on timer cadence discipline — one `Persistent=true` catch-up firing
after droplet downtime, or a hand-run during debugging, double-emails the pool. The fixed
pattern already exists in-repo: Golf's remind mode is de-duped via `last_reminder_type`
(API-key-free, idempotent). The Docket's reminders are being built on the sent-flag pattern
from day one (eng-review ruling D24, 2026-08-11); this item is the **retrofit of CFB
Survivor's** reminders to match. Small change (`games/cfb/services/reminders.py` + a
no-double-send lock test), but it touches the live game — **own PR, post-launch**, not
part of the Docket build.

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
| `main` | PR #130 (2026-07-30; 2.1/2.5/2.6 all shipped 2026-07-30 via #128/#129/#130) |
| Tests | **1764 passing**, ruff clean; plus `tests/test-deploy-guards.sh` at 102 (97 on the droplet) — *stale; 2026-08-13 reads 2216 passing and 132 (127 on the droplet)* |
| Production | deployed and verified — 29 units in sync; rate limits on shared Redis keyed by real client IP (realip, PR #129); origin cloaked by `fantasy-platform-fw` (80/443 CF-only, rollback drill measured ~55s); site 200 — *stale; 2026-08-13 reads 39 units + 1 preset file* |
| Prod ↔ repo pins | converged under `constraints.txt` (ADR-042; `click` 8.4.2, `urllib3` 2.7.0, `redis` 8.1.0) |
| Active era | CFB Survivor launch prep; WC archived; Golf UI phase ~Jan 2027 |
