# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

A unified fantasy sports platform consolidating multiple games under one domain, one login, and one codebase. Flask modular monolith using blueprints. Each game lives in `games/<game>/` with its own models, routes, services, templates, and CLI commands.

**Games** (status lives in `games/registry.py`):
- `games/cfb/` — CFB Survivor Pool — **active focus**; registry `open` + featured since the 2026-08-11 changeover (season starts Thu Sep 3). Dark-first room + admin cluster shipped; design doctrine in `games/cfb/DESIGN.md`.
- `games/worldcup/` — World Cup Fantasy Pool — **archived** (2026 tournament concluded 2026-07-19; permanent post-state). Registry `'completed'` since the 2026-08-11 changeover.
- `games/golf/` — Golf Pick 'Em — `coming_soon` (launches ~Jan 2027; backend hardened, UI phase pending)

**Transition plan (SSoT for the WC→CFB handover):** `docs/superpowers/plans/2026-07-20-cfb-era-transition-plan.md` — WC live-ops mothball (executed 2026-07-20), `'completed'` status handling, the lounge generalization approach, the atomic registry changeover, the CFB launch-ops runbook, and Brad's recorded rulings. Read it before any transition-adjacent work.

**Engineering backlog (known-but-unfixed work):** `docs/engineering-backlog-2026-07-21.md` — the `preset-all` timer hazard (2.4), the CF-edge-IP rate-limit-key gap (2.5, decide before ~Aug 17 signups), the `tests/conftest.py` extraction that would shrink every future framework migration, and the Python 3.14 pass. (Deploy-script hardening and the Flask-Limiter `memory://` multi-worker bug are ✅ shipped — see the doc.) Check it before starting infrastructure work, and **re-verify any number it quotes** — two items inherited from an earlier audit turned out stale, one by ~40%.

**Production:** Live at `cccfantasy.com`. CCC design system shipped at tag `impeccable-v1`. Product/design spine: `PRODUCT.md` + `DESIGN.md` (repo root); per-game specialization in `games/<slug>/DESIGN.md`. Any UI work invokes the `impeccable` skill (content v4.x). Its loader resolves **exactly one** `DESIGN.md`, never both — with `--target` it walks up from the target to the nearest dir holding `PRODUCT.md` *or* `DESIGN.md` and resolves each doc there, falling back to the root only for what that dir lacks. So `--target games/<slug>/…` picks up `games/<slug>/DESIGN.md`, **drops** the top-level one, and still gets the root `PRODUCT.md` (the only copy); no `--target` loads only the top-level pair. Adding a `PRODUCT.md`/`DESIGN.md` anywhere between a target and the root would re-point this walk. **Hard rule: when working any UI surface under `games/<slug>/`, read `games/<slug>/DESIGN.md` alongside the top-level `DESIGN.md` before producing design output** — whichever you don't target is the one you lose (top-level owns cross-game/platform-foundation concerns; the per-game file owns that game's palette/accent-rank/register/named primitives; see `docs/per-game-design-doc-convention.md`). Update impeccable **only via `/update-plugins`** — never any `npx impeccable update` (or legacy `skills update`) from a repo root; the hazard is the *working directory*, not the spelling (drops a stray project-local copy; a guardrail hook blocks both).

**Architecture: lounge vs rooms.** Platform `/` is the **club lounge** — dark CCC purple+gold atmosphere, dominated by whichever single game is currently live. Each game has its own **room** with specialized identity (WC: light Casual-Light body; CFB: dark-first midnight room). **Substrate distinction between the lounge and a game body is by-design architectural separation, not whiplash** — don't try to converge substrates (small handoff polish is fine). The lounge dispatches entirely through the registry's featured-game seam (C2 slices 1–2, shipped): `games.registry.lounge_game()` returns the single featured-open entry carrying **both** lounge callables (`lounge_state` resolver + `lounge_context` builder — an entry missing either never owns the lounge), and `core/main/routes.py` routes state, per-state data, and the per-game partial tree (`'<slug>/lounge'` by convention) through it — the atomic changeover flip re-points the lounge by itself once a game's lounge set exists. `core/main/home_context.build_home_context` is the thin core dispatcher: it assembles the registry-generic keys (available/joined/coming-soon games) + the commish note and overlays the featured game's `lounge_context` dict; it must never import a game module directly (locked in `tests/test_registry_seam.py`). CFB's lounge set is shipped and featured — the lounge dispatches to CFB through the seam (`games/cfb/services/lounge.py` + `games/cfb/templates/cfb/lounge/`, designed in the transition plan §5 + the C1 lounge spec). The WC lounge set remains archived behind the seam — `games/worldcup/services/lounge.py` + `games/worldcup/templates/worldcup/lounge/_*.html`, moved intact for archive/revival.

---

## Commands

```bash
# Run development server
FLASK_APP=app.py venv/bin/flask run
# Parallel worktree dev server (avoid colliding with main checkout; debug flag auto-reloads Jinja)
FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
# To exercise a game's fake clock (flip pre/post deadline for visual smoke), prepend ENVIRONMENT=development:
# ENVIRONMENT=development CFB_FAKE_NOW='2026-09-24T12:00:00' FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
# (WC_FAKE_NOW works identically for archive smoke.) Without ENVIRONMENT=development|testing the seams silently serve real time.

# Database
FLASK_APP=app.py venv/bin/flask db upgrade          # Apply migrations
FLASK_APP=app.py venv/bin/flask db migrate -m "..."  # Generate new migration
FLASK_APP=app.py venv/bin/flask create-admin        # Create platform admin user

# Golf CLI (prod runs these via the deploy/golf-*.timer systemd units)
FLASK_APP=app.py venv/bin/flask golf seed-schedule              # Seed the locked season schedule (one-off; sync_schedule only *updates*)
FLASK_APP=app.py venv/bin/flask golf force-schedule-sync        # Run sync_schedule now, bypassing the Monday gate (link seeded rows / refresh purse)
FLASK_APP=app.py venv/bin/flask golf sync-run --mode schedule   # Link seeded rows to real ids + refresh purses (Monday-gated internally)
FLASK_APP=app.py venv/bin/flask golf sync-run --mode field      # Sync tournament field + tee times (Tue/Wed) + picks-open email
FLASK_APP=app.py venv/bin/flask golf sync-run --mode live       # Update live leaderboard/projections (+ live major penalty refresh)
FLASK_APP=app.py venv/bin/flask golf sync-run --mode results    # Finalize results + process picks (Sun night/Mon)
FLASK_APP=app.py venv/bin/flask golf sync-run --mode remind     # Send deadline reminders (hourly; API-key-free, de-duped via last_reminder_type) — same as `flask golf remind`
FLASK_APP=app.py venv/bin/flask golf refresh-live-penalties     # Manually re-derive major cut/DQ penalty flags (ADR-034)
# --mode all chains every mode (dev/manual only — refuses to run when ENVIRONMENT=production)

# CFB CLI
FLASK_APP=app.py venv/bin/flask cfb sync --mode setup       # Create next week, import games, activate
FLASK_APP=app.py venv/bin/flask cfb sync --mode spreads     # Lock spreads at first fetch (Tue); later runs fill gaps only (DQ-6)
FLASK_APP=app.py venv/bin/flask cfb sync --mode scores      # Fetch scores, auto-process completed weeks
FLASK_APP=app.py venv/bin/flask cfb sync --mode autopick    # Process auto-picks for past-deadline weeks
FLASK_APP=app.py venv/bin/flask cfb sync --mode remind      # Send email reminders (Fri/Sat only)
FLASK_APP=app.py venv/bin/flask cfb sync --mode status      # Print season summary

# World Cup CLI (game archived; ops mothballed 2026-07-20 — commands retained for the archive + a future revival)
FLASK_APP=app.py venv/bin/flask worldcup status          # Print tournament state summary
FLASK_APP=app.py venv/bin/flask worldcup recalc          # Recalculate all scores (idempotent)
# Full CLI surface (seeding, sync, digests, snapshots) lives in games/worldcup/cli.py + the results-automation specs.

# Tests
ENVIRONMENT=testing venv/bin/python -m pytest tests/      # Run all tests (env var enables the *_FAKE_NOW seams in state-detection tests)
# Per-area suites are tests/test_<game>_*.py + tests/test_design_*.py; single test by name (gotchas below cite ::test_... locks):
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_scoring.py::test_points_for_pick_on_match_parity_with_compute_team_score_events -q
# deploy.sh has its own harness (bash, not pytest — invisible to collection). Run it after
# ANY deploy.sh edit; on the droplet add USE_REAL_FLOCK=1 to exercise the real flock(1):
bash tests/test-deploy-guards.sh
```

**Linting: Ruff** (pinned in `requirements-dev.txt`, config in `ruff.toml` — curated ruleset; no E501, no formatter). `venv/bin/ruff check .` must exit clean; `venv/bin/ruff check --fix .` applies safe autofixes. Enforced by `.github/workflows/lint.yml` (PRs + main) and a check-only PostToolUse hook on `*.py` edits. **Ruff's version is pinned in two places — `requirements-dev.txt` and `lint.yml` — bump both together or CI silently diverges from local.** The other workflow is `.github/workflows/test.yml`, which runs the full suite (`ENVIRONMENT=testing`, in-memory SQLite, no DB service) on PRs + main; note it therefore cannot catch a Postgres-only regression. Two conventions: SQLAlchemy boolean filters use `.is_(True)`/`.is_(False)`/`.is_not(None)` — never `== True` (E712) and never the Python-idiom rewrite, which silently breaks the query; `__init__.py` re-exports are covered by a per-file-ignore (F401), not `noqa` comments. No pyright — verify behavior with pytest.

**Dependencies: exact `==` pins on direct deps, never `>=` floors** (ADR-037). A floor never pulls an environment forward, so each machine freezes at whatever pip resolved on its install date — that is how local and prod silently diverged across 16 packages, prod reaching gunicorn 26.0.0 unvetted. Upgrades are deliberate: bump the pin, run the suite, smoke, deploy. **Anything imported directly by app code is a direct dep and gets a pin**, even when pip would install it anyway as a transitive (`itsdangerous`, `click`, `MarkupSafe` arrive via Flask but are imported by name). **Transitives are pinned too, in `constraints.txt`** (ADR-042, amending ADR-037). They used to float on the stated grounds that floating keeps certifi/urllib3 patched — **it does not**: `pip install -r requirements.txt`, even with `--upgrade`, reports an already-satisfied transitive as satisfied and never moves it. Prod sat on urllib3 2.6.3 across every deploy while 2.7.0 fixed two CVEs. `deploy.sh` and CI both install with `-c constraints.txt`, so both trees are deterministic. Constraints are resolved from **`requirements-dev.txt`** (the superset — it is `-r requirements.txt` plus tooling), so CI's own test-runner dependencies are pinned too; generating from `requirements.txt` alone would leave pytest's graph floating in the job that gates every PR. **Refreshing it is deliberate**: resolve in a clean venv with `--upgrade --upgrade-strategy eager` (the eager flag is load-bearing — nothing moves without it), run the suite, run `pip-audit`, deploy, verify. Full recipe in `constraints.txt`'s own header. One pin per package, one file: direct deps live in `requirements.txt` and are never repeated in constraints. Deliberately held back: Werkzeug 3.2 (`redirect()` 302→303), SQLAlchemy 2.1 (beta), Flask-SQLAlchemy 4 (removes `Model.query`) — see ADR-039.

---

## gstack

This machine has the [gstack](https://github.com/garrytan/gstack) skill suite installed globally at `~/.claude/skills/gstack` — not part of this repo (see the teammate note below).

- **Browser automation: always use `/browse`, never `mcp__claude-in-chrome__*` tools.** Applies to smoke-testing UI changes, visual QA, scraping, and any other in-repo browser automation. If a session doesn't have `/browse` available (gstack not installed on that machine), say so rather than silently falling back to `mcp__claude-in-chrome__*`.

Other gstack skills available in this project:

- `/office-hours` — YC Office Hours — two modes
- `/plan-ceo-review` — CEO/founder-mode plan review
- `/plan-eng-review` — Eng manager-mode plan review
- `/plan-design-review` — Designer's-eye plan review, interactive like CEO/Eng review
- `/design-consultation` — Proposes a complete design system (aesthetic, type, color, layout, motion) from product understanding
- `/design-shotgun` — Generates multiple AI design variants, opens a comparison board, collects structured feedback
- `/design-html` — Design finalization: production-quality HTML/CSS
- `/review` — Pre-landing PR review
- `/ship` — Full ship workflow: merge base branch, run tests, review diff, bump VERSION, update CHANGELOG, commit, push, PR
- `/land-and-deploy` — Land and deploy workflow
- `/canary` — Post-deploy canary monitoring
- `/benchmark` — Performance regression detection via the browse daemon
- `/browse` — Fast headless browser for QA testing and site dogfooding — see above
- `/connect-chrome` — Launches AI-controlled Chromium with the sidebar extension baked in
- `/qa` — Systematically QA tests a web app and fixes bugs found
- `/qa-only` — Report-only QA testing
- `/design-review` — Designer's-eye visual QA: inconsistency, spacing, hierarchy, AI-slop patterns, slow interactions
- `/setup-browser-cookies` — Imports cookies from a real Chromium browser into the headless browse session
- `/setup-deploy` — Configures deployment settings for `/land-and-deploy`
- `/setup-gbrain` — Sets up gbrain (persistent agent memory) for this coding agent
- `/retro` — Weekly engineering retrospective
- `/investigate` — Systematic debugging with root-cause investigation
- `/document-release` — Post-ship documentation update
- `/document-generate` — Generates missing documentation from scratch for a feature, module, or project
- `/codex` — OpenAI Codex CLI wrapper, three modes
- `/cso` — Chief Security Officer mode
- `/autoplan` — Auto-review pipeline: runs CEO, design, eng, and DX review skills sequentially with auto-decisions
- `/plan-devex-review` — Interactive developer-experience plan review
- `/devex-review` — Live developer-experience audit
- `/careful` — Safety guardrails for destructive commands
- `/freeze` — Restricts file edits to a specific directory for the session
- `/guard` — Full safety mode: destructive-command warnings + directory-scoped edits
- `/unfreeze` — Clears the boundary set by `/freeze`
- `/gstack-upgrade` — Upgrades gstack to the latest version
- `/learn` — Manages project learnings

**Not yet added to this repo** — gstack is currently a personal global install, not committed here, so a teammate's Claude Code session won't have `/browse` or any of the above until gstack is added at the project level.

## GBrain Configuration (configured by /setup-gbrain)
- Mode: local-stdio
- Engine: pglite
- Config file: ~/.gbrain/config.json (mode 0600)
- Setup date: 2026-08-09
- MCP registered: yes (user scope)
- Repo policy for fantasy-platform: read-write
- Artifacts sync: artifacts-only (private repo: `github.com/BradHagstrom16/gstack-artifacts-bhagstrom`)
- Transcript ingest: this repo, last 90 days on first run; incremental going forward

## GBrain Search Guidance (configured by /sync-gbrain)
<!-- gstack-gbrain-search-guidance:start -->

GBrain is set up and synced on this machine. Prefer gbrain over Grep when the question is semantic or the exact identifier isn't known yet. Two indexed corpora via the `gbrain` CLI:
- This repo's docs/specs (registered from `/Users/bhagstrom/fantasy-platform`, markdown-only — code files are not yet imported).
- `~/.gstack/` curated artifacts (federated source `gstack-artifacts-bhagstrom`) + this repo's session transcripts (last 90 days, incremental going forward).

Prefer gbrain when:
- "Where is X handled?" / semantic intent, no exact string yet: `gbrain search "<terms>"` or `gbrain query "<question>"`
- "What did we decide last time?" / past plans, retros, learnings: `gbrain search "<terms>" --source gstack-artifacts-bhagstrom`

Grep is still right for known exact strings, regex, multiline patterns, file globs, and code symbol lookups (code isn't imported into gbrain yet — only markdown). Run `/sync-gbrain` to force-refresh, `/sync-gbrain --full` for full reindex.

<!-- gstack-gbrain-search-guidance:end -->

---

## Key Conventions

### Design system & CSS

- **Design system:** "Corrupt Commish Club" (CCC) — CCC purple/gold tokens in `static/css/tokens.css` + per-game palettes via `body.game-<game>` CSS class. See `docs/superpowers/specs/2026-04-28-ccc-brand-foundation-design.md`.
- **CSS layering:** `static/css/tokens.css` (CCC house tokens) loads BEFORE `static/css/style.css` (platform aliases + components); both linked from `templates/base.html` head. New tokens go in tokens.css; components consume them via `var(--purple-700)` etc. in style.css.
- **CSS specificity for utility classes:** Single-class utilities (e.g., `.wc-hero-grad`) defined earlier in `style.css` lose cascade to later base rules of equal specificity (`.page-hero`). Scope new utilities as `.base.utility` (e.g., `.page-hero.wc-hero-grad`) to win on (0,0,2,0). The foundation `.wc-*` block already follows this pattern; extend it for any new `.wc-*` that overlaps a later base rule rather than relying on source order.
- **Two parallel `_home_<state>.html` trees exist** — the game room's under `games/<slug>/templates/<slug>/`, the *lounge's* per-game set under `games/<slug>/templates/<slug>/lounge/` (WC's moved there in C2 slice 2; registry-generic lounge partials — `_game_tiles_compact`, `_commish_note`, `_dispatches`, `index` — stay shared in `core/main/templates/main/`) — with *distinct* primitives (e.g., the WC room's post banner is `.wc-champion-banner`; the lounge's is `.champion-banner` via `lounge/_champion_banner.html`). Don't cross-apply them. WC-room substrate doctrine (Casual-Light body, the champion banner as its only dark surface, scoped foreground carve-outs) lives in `games/worldcup/DESIGN.md`; the WC surfaces themselves are frozen (see World Cup section below).
- **Bootstrap `.text-muted` override is global, not local:** the canonical CCC override is the `:root { --bs-secondary-color: var(--text-secondary) }` redirect in `style.css`, lifting every bone-canvas instance from `#6c757d` (~3.5:1, sub-AA) to `--text-secondary` (`#5A5470`, ~6.9:1) without specificity wars — don't add new `!important` rules on bone substrates. Dark substrates flip the contrast equation and DO need their own scoped `!important` lifts (`.wc-champion-banner .text-muted`, `.page-hero.wc-hero-grad .hero-subhead.text-muted`); new dark surfaces get their own scoped lift, never another `:root` override.
- **Raw `color: var(--text-muted)` MUST NOT appear on bone/white substrates:** the token (`#8A849B`, ~3.6:1 on white) is calibrated for *dark* substrates only and bypasses the `--bs-secondary-color` redirect that protects the `.text-muted` *class*. On bone/white use `--text-secondary`. Codebase invariant: zero raw `color: var(--text-muted)` in `style.css` outside dark-substrate scopes.
- **Gradient text is fully retired:** zero `background-clip: text` rules in `style.css` (locked by `tests/test_design_p6_s6_1_1.py`). Don't reintroduce it for ceremonial emphasis — use flat gold (`.home-metal-text` precedent: solid `var(--gold-light)` on dark, `var(--gold-dark)` on cream) or DESIGN.md §3 weight/size hierarchy.
- **Navbar lockup + solo-game hoist + auth bust:** the navbar brand pairs the head mark with `wordmark-bone.svg` at **every** width (CSS hides the wordmark only ≤350px; the `<a class="navbar-brand">` carries `aria-label="Corrupt Commish Club"` for the accessible name there). When a user's joined-game count == 1, that game's link hoists out of the hamburger into the bar itself (`.navbar-solo-game`, `d-lg-none`, right of brand) and its collapse copy hides below lg — exactly one rendered link per breakpoint; 0 or 2+ joined games fall back to collapse-only. The auth desktop brand panel leads with `mascot-bust.svg` via the shared `core/auth/templates/auth/_brand_logo.html` partial. Wordmark kit: `static/img/logo/wordmark-{bone,gold,purple}.svg`; unwired brand-kit assets stay in the gitignored `CCC-final/`. Locks: hoist + wordmark gating in `tests/test_navbar_solo_game.py`; asset existence + auth/footer surfaces in `tests/test_logo_assets.py`; versioned URLs + accessible name in `tests/test_asset_versioning.py`.
- **Eyebrow glyph reservation:** `◈` is reserved for *ceremonial* moments (decree countdown, champion banner *with* `champion_team` set, locked seal/oath); `◇` is the *informational* register (sec-heads, roster spine, "Open Court", "Awaiting Decree", rules teaser). Keep `◈` rare so it carries weight. Game-body eyebrow primitives (`.wc-eyebrow`, `.cfb-eyebrow`) never carry glyphs.
- **Game theming:** Platform components (`.page-hero`, `.stat-block`, `.btn-game`) consume `--game-primary`/`--game-accent` automatically — game CSS must NOT duplicate this
- **Game CSS sections:** Each game has its own section in `style.css` (e.g., `/* === CFB SURVIVOR POOL === */`) with game-specific component classes
- **Game sub-nav:** Each game needs a `.subnav-<game>` class in the `/* === GAME SUB-NAV === */` section of `style.css` setting `background`, `--subnav-accent` (hex), and `--subnav-accent-rgb` (comma-separated R,G,B) — the shared pill `.active` rule consumes these variables
- **Game palettes:** Golf: Augusta green `#006747` + gold `#b8993e`; CFB: crimson `#C5050C` + warm midnight canvas `#0E0A0C` (dark-first room; full ramp in `games/cfb/DESIGN.md`); World Cup: navy `#001A4D` + red `#BF0A30` (matches `--wc-navy` / `--wc-red` in tokens.css; the WC *game-slot* `--game-primary` is a second navy, `#002868` — both frozen)
- **Country flags are self-hosted SVG, never emoji** (emoji flags render as bare letters on Windows): `{% from '_flag.html' import flag with context %}` + `{{ flag(team.iso_code) }}`; lowercase ISO-2 keys into `static/flags/<iso>.svg`; `.ccc-flag` is `height:1em` (wrapper font-size drives size); JS-built rows mirror via `flagImg(iso)`. Locked by `tests/test_worldcup_flag_emoji.py`.

### Platform integration

- **Emails:** All outbound email routes through `utils/email.py` → `send_platform_email()`; From-name "Corrupt Commish Club"; game-specific content assembly in `games/<game>/services/reminders.py`; HTML emails use table layout + inline styles for Gmail. **Prod sends via Brevo SMTP relay** (`smtp-relay.brevo.com:2525` — DO blocks 25/465/587); `EMAIL_ADDRESS`/`EMAIL_PASSWORD` are the Brevo login+key; visible From is `MAIL_FROM_ADDRESS` = `commish@cccfantasy.com`, the DKIM-authenticated domain sender (**Gmail silently drops mail From the bare SMTP-login address**). Replies to `commish@` forward via Cloudflare Email Routing. **Config-plumbing gotcha:** any env var read via `current_app.config.get()` needs a matching `os.environ.get()` line in `config.py`'s base `Config` class or it's silently `None` (caused the `MAIL_FROM_ADDRESS` prod bug; smoke tests that set `app.config` by hand bypass `config.py` and won't catch it).
- **Avatars:** All game standings must display `user.get_avatar()` inline before the player display name (required integration point for every game blueprint). `User.avatar_emoji` is nullable String(4); default ⚽. **The crown emoji is reserved for platform admins:** `get_avatar()` returns it for any `is_admin` user and substitutes ⚽ for non-admins who have it stored — enforced at every call site, not just the picker (excluded from `AVATAR_CATEGORIES` in `core/auth/routes.py`; `profile.html` shows admins a note instead of the picker). Store the crown as the `'\U0001F451'` escape (`User.ADMIN_AVATAR` in `models/user.py`), never a literal char — literal non-BMP emoji in `.py` source can break import as invalid surrogate pairs.
- **Phone (optional contact):** `User.phone` is nullable String(20), collected at signup, editable on `/profile`. Every phone input MUST normalize through `utils/phone.normalize_us_phone(raw) -> (normalized, error)` (NANP only, stored as `(212) 555-0123`; blank ⇒ `(None, None)`, non-blank invalid ⇒ rejected). Reuse for any new phone surface — don't re-validate inline.

### Code conventions (time, ORM, templates, schema, security)

- **Timestamps:** `datetime.now(UTC)` (`from datetime import UTC`; Ruff UP017 enforces over `timezone.utc`) — never `utcnow()`
- **Time test seam:** every game exposes a canonical "now" reader honoring a `<GAME>_FAKE_NOW` env var when `ENVIRONMENT` is `development`/`testing` — CFB: `games/cfb/utils.get_current_time()`/`get_utc_time()` (`CFB_FAKE_NOW`, naive ISO ⇒ UTC; locked by `tests/test_cfb_time_seam.py`); WC: `games/worldcup/services/state.now_utc()` (`WC_FAKE_NOW`). Never call `datetime.now()` directly in game application paths (exception: SQLAlchemy `default=lambda: datetime.now(UTC)` audit-timestamp lambdas record real wall-clock time, not faked time). CFB datetime **columns** are stored naive with a split contract — `deadline`/`start_date`/`game_time` are pool-tz wall clock (read via `make_aware`), `created_at`/`spread_locked_at` are UTC (read via `to_pool_time`) — documented in `games/cfb/models.py`; using `make_aware` on a UTC column shifts it +5/6h (the recap-AUTOPICK mislabel bug).
- **Mocking the time/deadline seam:** patch the "now" reader / deadline constant at the **read-site module** (the service module that owns it, e.g. `games.worldcup.services.state` — not a route module that re-imported the constant). Patches against the wrong module become silent no-ops; if a deadline test stops gating behavior after a service extraction, check the patch target before changing the assertion. Every `patch.dict(os.environ, {...})` setting a `*_FAKE_NOW` must also set `'ENVIRONMENT': 'testing'` in the same dict — the seam only activates in dev/testing, and the outside-process env var doesn't propagate when a test file runs without the `ENVIRONMENT=testing` prefix.
- **Timezones:** `zoneinfo.ZoneInfo` — `.replace(tzinfo=tz)`, never pytz
- **ORM:** SQLAlchemy 2.0 style — `db.session.get(Model, id)`, `db.get_or_404()` — for **new/changed code only**. Never mass-migrate the legacy `Model.query` sites (495 lines / 64 files repo-wide as of 2026-07-21 — 356 lines / 35 files of app code plus the rest in `tests/`; ADR-039 cites the same figures) (fully supported, zero deprecation warnings; `.delete()`/`.count()`/`scalar↔scalars` transforms carry uneven semantic risk). Fix only `.query` lines already in the current diff; a full migration would be its own dedicated PR.
- **ORM safety:** Never mutate ORM attributes for display — use transient attributes
- **Jinja2 sorting:** Never use `sort(attribute='method_name')` — Jinja2 retrieves the bound method, not its return value. Sort in the route instead.
- **Jinja macros that read context-processor vars must be imported `with context`:** e.g. `_flag.html`'s `flag()` uses `asset_version`, so callers do `{% from '_flag.html' import flag with context %}` — a plain `import` leaves it undefined inside the macro (silent, no error; `url_for` is a global and works either way). Corollary: template-source tests checking the "first rendered element" must strip `{% ... %}` tags, not just comments, or a top-of-file import trips them.
- **Template restyling:** When restyling templates with JavaScript, audit all `querySelector`/`querySelectorAll`/`getElementById` calls first. Add CSS classes alongside JS-critical ones — never rename or remove them.
- **Schema changes:** Flask-Migrate (Alembic) only — never raw SQL
- **CSRF:** All POST forms include CSRF token; AJAX includes `X-CSRFToken` header
- **POST-only:** All state-mutating operations use POST — no GET routes that change data

### Auth, admin, enrollment

- **Admin scoping:** Two-tier game admin — platform admin (`User.is_admin`) always has access to every game's admin routes. Game-specific admin (`<Game>Enrollment.is_admin`) allows delegating admin to enrolled non-platform-admins. All `<game>_admin_required` decorators must check platform admin first, enrollment admin second.
- **Session identity is `User.auth_id`, NOT the integer PK:** `User.get_id()` returns the random, never-reused `auth_id` token (`models/user.py`), and the Flask-Login `user_loader` (`app.py`) resolves by `auth_id`. **Security invariant** — do NOT revert to the integer `id`. Reason (2026-06-01 prod incident): a DB wipe restarts the `users` id sequence, and a pre-wipe remember-me cookie (still validly signed) cross-authenticated a recycled PK as a different person; a random `auth_id` makes stale cookies match nothing. Locked by `tests/test_auth_session_identity.py`. Corollary: any destructive DB reset must also rotate `SECRET_KEY` (see `docs/archive/production-launch-test-script.md` §14C).
- **Authenticated responses are `Cache-Control: private, no-store`:** stamped by an `@app.after_request` hook in `app.py` when `current_user.is_authenticated` (static endpoint excepted). **Security invariant** — a shared cache that ignores `Vary: Cookie` (e.g. a Cloudflare "Cache Everything" rule) could serve one user's rendered page to another. Anonymous responses stay cacheable on purpose (CDN fronts the public surfaces) — never blanket `no-store` onto them. Locked by `tests/test_response_cache_headers.py`.
- **Password reset tokens:** `core/auth/tokens.py` uses `itsdangerous.URLSafeTimedSerializer` with 1-hour expiry. Forgot-password route uses anti-enumeration pattern (identical flash message regardless of email existence).
- **Game registry:** `games/registry.py` is the SSoT — one `GameRegistryEntry` per game (slug, status, is_featured, endpoints, `get_enrollment` + `admin_enroll` callables); its helpers drive homepage, navbar, and admin add-user page. Flip `status` from `'coming_soon'` to `'open'` at launch.
- **Enrollment is explicit:** users reach a game's interior routes only via `/<game>/join` (guarded by `@game_must_be_open(slug)` in `games/common.py`). Interior pick routes carry `@enrollment_required(slug)`, which redirects unenrolled users to `/<game>/join?next=<current>`. **Never** create `<Game>Enrollment` rows from pick or admin paths — platform admins enroll users via `/admin/enrollments`.
- **Admin destructive actions:** destructive admin POST handlers branch on `request.form.get('action')` — `action=clear` is a distinct, guarded path that short-circuits before the main mutation. Keep this pattern for new admin routes that both mutate and reset.

### World Cup (archived — 2026 tournament complete)

The 2026 tournament concluded 2026-07-19; the game sits in a permanent `'post'` state (a one-way latch on final match #104 `is_completed`) rendering the archive. Registry status is `'completed'` (joins closed, archive reachable for enrolled members) since the 2026-08-11 changeover. Live-ops were mothballed 2026-07-20: the four `worldcup-*` timers are disabled and the snapshot cron is commented on the droplet — unit files, sync code, and `FOOTBALL_DATA_API_KEY` are all retained for a possible future revival (shape deliberately undecided; transition plan §4/§7). **WC surfaces are frozen**: don't restyle, refactor, or "clean up" WC code outside (a) the lounge extraction planned in the transition plan and (b) an actual revival. The WC half of the test suite stays green on every PR and is the regression net under the lounge refactor.

Invariants that still bind (live code + test locks; several get *moved, not rewritten* during the lounge extraction):

- **Scoring SSoT:** `games/worldcup/services/scoring.py` helpers are the only source of scoring breakdowns — never recompute in UI. Deliberately parallel output units: `compute_team_score_events` returns **base** points (templates multiply by the tier multiplier at render time); `points_for_pick_on_match` returns **already-multiplied** points by contract (parity lock: `tests/test_worldcup_scoring.py::test_points_for_pick_on_match_parity_with_compute_team_score_events`). Podium bonuses are non-match ScoreEvents (`match_id=None`) attributed to their deciding match only via the `display_*` helpers — never fold podium into `points_for_pick_on_match`, never render a won final/bronze as 0 pts (the 2026-07-19 "NO POINTS" incident).
- **Competition rank, never dense rank** — `rank = 1 + (count scoring strictly higher)`, so ties share and gap (`1, 1, 3, 4`). This is the platform convention for any tied-score leaderboard, future games included. The WC loop is mirrored across `routes.leaderboard`/`rosters`, `services/ranking.compute_rank_neighbors`, both home-context builders, `notifications._competition_rank`, and snapshot capture — keep every site in lockstep. Jinja idiom: `namespace(rank=0, prev_score=None)` + `{% if e.total_score != ns.prev_score %}{% set ns.rank = loop.index %}{% endif %}` — never `ns.rank = ns.rank + 1`.
- **"Still alive" = `services/elimination.eliminated_team_ids()`** (group exit OR completed-KO loss), never `WorldCupTeam.is_eliminated` (a group-stage-only flag). Locked by `tests/test_worldcup_elimination.py`.
- **Label SSoTs:** `services/stage.stage_label` (match stages) + `best_finish_label` (podium/finish codes — a different value space; empty ⇒ `'Round of 32'`, `'group'` ⇒ group-stage exit, unknown codes surface raw). Templates never use `match.stage|title` (`|title` mangles `'SF'` → `'Sf'`). Locked by `tests/test_worldcup_stage.py`.
- **`WorldCupRankSnapshot` aggregates must be season-scoped** via `.join(WorldCupEnrollment)...filter(season_year == SEASON_YEAR)` — the snapshot row has no season column. Lock: `tests/test_worldcup_leaderboard.py::test_trend_column_gate_scoped_to_active_season`.
- **Pre-deadline ownership privacy (D11):** ownership counts/percent hidden from **everyone** pre-deadline, including the team's own picker — never add an owner carve-out. Locks in `tests/test_worldcup_team_detail.py`.
- **Lounge builders (extracted 2026-07-20, C2 slice 2):** `games/worldcup/services/lounge.build_lounge_context(user, state)` dispatches the four WC lounge builders behind the registry seam — moved intact, and *distinct from* the WC room's `games/worldcup/services/home_context.py` (the parallel-trees convention above). Never recompute scoring/rank in the lounge templates; the core dispatcher supplies the registry-generic keys + commish note.
- Dormant-code doctrine (results automation, per-side bracket autofill, digests, bulk bracket populate, stats layer): specs `2026-06-02-worldcup-results-automation-design.md`, `2026-06-02-worldcup-daily-digest-design.md`, `2026-06-28-worldcup-knockout-bracket-autofill-design.md`; WC-era polish scorecards `2026-05-12-impeccable-design-improvement-scorecard.md` + `2026-05-13-worldcup-tab-unification-scorecard.md` (all under `docs/superpowers/specs/`).

### Production ops

- **Scheduled-jobs state (as of 2026-07-20):** all `worldcup-*` timers disabled + snapshot cron commented (WC archived); Golf jobs disabled (Golf runs on its separate PythonAnywhere box until migration); CFB timers (`deploy/cfb-*`, five pairs) get installed + enabled at launch — runbook in the transition plan §6F. Systemd timers are the canonical scheduling mechanism; the legacy crontab lines stay commented as history.
- **Production environment selection:** `ENVIRONMENT=production` is set in three places as defense-in-depth — the server's `.env`, the systemd unit's `Environment=` override, and every flask line in `deploy.sh` + crontab; keep all three in sync when adding cron entries or deploy steps. `migrations/env.py` reads the DB engine from `create_app()`'s config, so a stray `ENVIRONMENT=development` silently migrates against SQLite instead of Postgres.
- **Client-IP rate-limit keying flows through nginx realip:** the 443 block in `deploy/nginx.conf` trusts `CF-Connecting-IP` only when the TCP peer is a published Cloudflare range (`set_real_ip_from` list + `real_ip_header`), so the last `X-Forwarded-For` entry nginx appends is the real client and `ProxyFix(x_for=1)` in `app.py` selects it. **Keep `x_for=1`** — raising it would trust client-supplied XFF on direct-to-origin requests. The CF range list is mirrored in `tests/test_client_ip_keying.py` AND the origin-cloak runbook's marker block (refresh recipe in the nginx.conf realip comment; update all three together, plus the live firewall — see the origin-cloak bullet below). **`deploy/nginx.conf` is NOT synced by `deploy.sh`** — editing it does nothing in prod until the manual install in its header comment is re-run (sed the domain → `sudo cp` → `nginx -t` → reload).
- **Origin is cloaked by a DO Cloud Firewall (`fantasy-platform-fw`, ADR-043):** inbound 80/443 allowed only from Cloudflare's published ranges; TCP 22 stays open from anywhere (lockout guard); outbound rules and droplet ufw deliberately untouched — **`ufw status` showing `Nginx Full ALLOW Anywhere` is expected, not drift** (the cloud firewall is the narrower outer gate). The CF range list lives in three repo places (nginx.conf, the test frozenset, the runbook marker block — CI-locked to each other) **plus the dashboard rules, which no test can see** — a stale allowlist hard-blocks real users (UptimeRobot red while the droplet looks healthy = suspect the allowlist; rollback = detach the droplet from the firewall in the DO dashboard, no SSH needed). Full procedure + refresh recipe: `docs/superpowers/plans/2026-07-30-origin-cloak-do-firewall.md`.
- **Postgres connection hygiene:** `ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 280}` — DO Managed Postgres closes idle connections; without this, long-lived Gunicorn workers throw `OperationalError` on first request after an idle gap. Do not remove.
- **Static asset cache-busting:** Every `<link>`/`<script>`/brand-`<img>` referencing `/static/*` in templates appends `?v={{ asset_version }}` (git short SHA, resolved at boot in `core/context.py::_compute_asset_version`) — nginx serves `/static/` with `expires 30d; "public, immutable"`, so an unversioned URL stays frozen at Cloudflare's edge for up to 30 days. **This includes brand images** (favicon `<link>`s, navbar mark, footer seal, reset-email `seal_url`): swapping image bytes in place under the same filename does NOT bust the edge (PR #48 fallout). Locked by `tests/test_asset_versioning.py`. Stale-asset debug: `curl -sI https://cccfantasy.com/static/css/style.css | grep -iE 'cf-cache-status|age'` — long `age` + `HIT` means an unversioned link slipped through; fix the template, don't reach for the CF purge button. To distinguish a stale edge from a failed deploy, hash origin bytes past Cloudflare with a throwaway query key: `curl -s "https://cccfantasy.com/static/img/logo/favicon.svg?cb=$(date +%s)" | shasum -a 256` vs `git show HEAD:static/img/logo/favicon.svg | shasum -a 256`.

---

## Blueprint Pattern (required for all games)

- Blueprint in `games/<game>/` with `<game>_` table prefix on all models
- `<Game>Enrollment` model for game-specific user data, FK to shared `User`
- `@<game>_admin_required` decorator — two-tier: platform admin override first, then enrollment-scoped admin
- Templates extend `templates/base.html`, rendered under `<game>/` prefix
- Body class: game blueprints inject `body_class` via context processor (e.g. `'game-golf'`); chrome templates override via `{% block body_class %}` (e.g. `auth-page`); `base.html` resolves both via `<body class="{% block body_class %}{{ body_class|default('') }}{% endblock %}">`.
- Add a game switcher `<li class="nav-item">` to the navbar in `base.html`, plus a `{% elif request.blueprint == '<game>' %}` branch in the game sub-nav block with `.game-subnav .subnav-<game>` div, game label, and pill links
- CLI commands under `flask <game> *` namespace using `AppGroup`
- Context processor on the blueprint for game-specific template variables
- `before_request` hook for auto-refresh logic
- `games/<game>/services/enrollment.py` exposing `get_enrollment(user_id)` + `admin_enroll(user_id)` (idempotent), wired into `games/registry.py` as a new `GameRegistryEntry`
- `/<game>/join` route + `games/<game>/templates/<game>/join.html` following the established join-page shape (`page-hero` + how-it-works card + form + `btn-game`; `games/cfb/templates/cfb/join.html` is the newest reference), decorated with `@game_must_be_open('<game>')`
- `@enrollment_required('<game>')` on every interior pick/mutation route (not on leaderboards or public standings)

---

## Project Structure

```
fantasy-platform/
├── app.py                  # App factory (create_app)
├── wsgi.py                 # WSGI entry (Gunicorn loads `wsgi:application`)
├── config.py               # Environment-based config classes
├── extensions.py           # db, migrate, login_manager, csrf, limiter
├── models/
│   ├── __init__.py         # Re-exports all models for Alembic
│   └── user.py             # Shared User model
├── utils/
│   └── email.py            # Shared platform email helper (send_platform_email)
├── core/
│   ├── auth/               # Login, register, logout, change/forgot/reset password
│   │   └── tokens.py       # Password reset token generation/verification
│   ├── admin/              # Platform-level admin
│   └── main/               # Home page
├── games/
│   ├── registry.py         # GameRegistryEntry + joined/available/coming_soon/featured helpers
│   ├── common.py           # @game_must_be_open, @enrollment_required decorators
│   ├── golf/               # Golf Pick 'Em blueprint
│   ├── cfb/                # CFB Survivor Pool blueprint
│   └── worldcup/           # World Cup Fantasy Pool blueprint
├── tests/                   # pytest test suite
├── templates/
│   ├── base.html           # Platform base template
│   ├── email/              # Platform email templates (reset password)
│   └── errors/             # 404, 500
├── static/css/style.css    # Platform styles (CSS custom properties)
├── migrations/             # Alembic history
├── deploy/                 # Production deploy artifacts
│   ├── nginx.conf
│   └── fantasy-platform.service
├── deploy.sh               # One-command deploy (runs on server)
└── .claude/
    ├── settings.json       # Hooks (.env protection, smoke tests)
    └── skills/
        └── add-game/SKILL.md   # Project skill: scaffold a new game
```

---

## Database Migrations

Flask-Migrate only, never raw SQL (commands in the Commands block above). Workflow after editing models: `db migrate -m "..."` → **review the generated file in `migrations/versions/`** → `db upgrade` → commit the migration file *with* the model changes.

---

## Smoke Test Standard

Smoke-test snippets that use `ENVIRONMENT=testing` with in-memory SQLite must include `db.create_all()`:

```python
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    print('Smoke test OK')
```

Auth routes have **no URL prefix** — login is at `/login`, not `/auth/login`. Same for `/register`, `/forgot-password`, `/reset-password/<token>`, `/change-password`, `/profile`.

---

## Admin Route Testing

Auth-gated admin routes use this pattern (see `tests/test_worldcup_admin.py`):

```python
admin_auth_id = _make_admin_user(app)  # creates is_admin=True; returns User.auth_id
with client.session_transaction() as sess:
    sess['_user_id'] = admin_auth_id   # session identity is auth_id, NOT str(user.id)
    sess['_fresh'] = True
resp = client.post('/worldcup/admin/...', data={...})
```

**`sess['_user_id']` must be the user's `auth_id` (= `user.get_id()`), never `str(user.id)`** — see the auth_id invariant above. Seeding `str(user.id)` silently fails to authenticate (302 to login). When only an int id is in scope: `db.session.get(User, uid).auth_id`.

Testing config sets `WTF_CSRF_ENABLED=False`, so form data may include a placeholder `csrf_token`.

---

## Production Deployment (DigitalOcean)

Live architecture: DO Droplet (Ubuntu 24.04) running Nginx → Gunicorn (unix socket) → Flask; DO Managed Postgres over private VPC; Cloudflare proxy + Origin Certificate for TLS. Scheduled sync jobs run on the Droplet via systemd timers from `deploy/` (see Production ops: scheduled-jobs state).

Deploy files live in `deploy/`:
- `deploy/nginx.conf` — site config (HTTPS, HTTP/2, gzip, HSTS, security headers, realip client-IP restoration; **manual install — not synced by deploy.sh**)
- `deploy/fantasy-platform.service` — systemd unit for Gunicorn (3 workers, `RuntimeDirectory=fantasy-platform`, socket at `/run/fantasy-platform/gunicorn.sock`)
- `deploy.sh` — one-command deploy on the server: `git pull` → `pip install` → `flask db upgrade` → **sync every `deploy/*.service` + `deploy/*.timer` into `/etc/systemd/system/`** → `daemon-reload` → `systemctl restart` → verify `is-active`. The unit sync (ADR-040, generalized to all units by ADR-041) means **editing a unit file in the repo IS the deploy** — never `sudo cp` one by hand. Each unit is validated with `systemd-analyze verify` before it lands, so a broken unit is refused rather than installed, and gets its own verdict: one bad unit warns without aborting the rest. Units with no `/etc` counterpart are **installed, not skipped** — installing is not enabling, and this is what keeps the CFB timer install from depending on someone remembering a manual step; `systemctl enable` stays a deliberate, separate act. The script exits **non-zero** if any non-fatal step warned or if the service fails to come up — a warning plus "App is live" is not a state it can end in.

To ship an update from local:
```bash
git push origin main                     # local
ssh deploy@<droplet-ip>                  # server
./deploy.sh                              # runs inside /home/deploy/fantasy-platform
```

**Post-deploy verification is mandatory — `deploy.sh` exiting 0 proves the script ran, not that the config is live.** This is the lesson of ADR-040: the `--timeout 120` fix sat unshipped for five weeks while every signal said the deploy had succeeded. After every deploy, check the droplet read-only:

```bash
# 1. Active, and the restart timestamp must be RECENT (a stale one = no restart)
systemctl status fantasy-platform --no-pager | head -20
# 2. No boot errors/tracebacks (may need sudo; if so, run it at your own TTY)
sudo journalctl -u fantasy-platform -n 50 --no-pager
# 3. Unit diff — must be identical (the unit is 644, so no sudo needed)
diff /home/deploy/fantasy-platform/deploy/fantasy-platform.service \
     /etc/systemd/system/fantasy-platform.service && echo "unit in sync"
# 4. The check that would have caught ADR-040: read the RUNNING process args,
#    not any file. Expect --timeout 120, --no-control-socket, 3 workers.
ps -o args= -C gunicorn | head -3
```

Check 4 is the load-bearing one — it reads what gunicorn is actually running rather than what some file claims. A unit can be in sync on disk while systemd still serves an older in-memory definition.

First-time setup: `docs/superpowers/plans/2026-04-21-production-deployment.md`.
Production re-verification: `docs/archive/production-launch-test-script.md` (WC-era full prod simulation — out → pre → live → post — then DB reset to a clean baseline; archived with the WC sunset, kept as the template for a CFB-era equivalent).

---

## Environment Variables

```
FLASK_APP=app.py
ENVIRONMENT=development|testing|production
SECRET_KEY=...
# Dev (default): SQLite
DATABASE_URL=sqlite:///instance/fantasy_platform.db
# Prod: DO Managed Postgres connection string (requires ?sslmode=require)
# DATABASE_URL=postgresql://doadmin:<pw>@<host>.db.ondigitalocean.com:25060/defaultdb?sslmode=require
SITE_URL=...             # Used in password-reset and reminder email links (https://<domain> in prod)
PLATFORM_TIMEZONE=...    # Default: America/Chicago
RATELIMIT_STORAGE_URI=...  # Rate-limit store. Leave unset: dev/test default memory://; prod defaults to redis://localhost:6379/0 (ProductionConfig; local Redis on the droplet). Set only to override.
ODDS_API_KEY=...         # The Odds API (CFB scores/spreads)
FOOTBALL_DATA_API_KEY=...  # football-data.org (WC results sync — archived; key retained for a future revival. Free tier covered WC 2026; API-Football free did NOT)
SLASHGOLF_API_KEY=...    # SlashGolf API (Golf leaderboards)
EMAIL_ADDRESS=...        # SMTP auth login (prod: Brevo SMTP login, e.g. ad34xxxxx@smtp-brevo.com)
EMAIL_PASSWORD=...       # SMTP key/password (prod: Brevo SMTP key)
MAIL_FROM_ADDRESS=...    # Visible From; prod: commish@cccfantasy.com. Falls back to EMAIL_ADDRESS if unset
ADMIN_EMAIL=...          # Game-admin alert inbox (score-sync/setup alerts). MUST be a real mailbox in prod — EMAIL_ADDRESS there is the Brevo SMTP login, not an inbox. Falls back to EMAIL_ADDRESS if unset (fine in dev)
SMTP_SERVER=...          # Dev default smtp.gmail.com; prod smtp-relay.brevo.com
SMTP_PORT=...            # Dev default 587; prod 2525 (DO blocks 587)
```
