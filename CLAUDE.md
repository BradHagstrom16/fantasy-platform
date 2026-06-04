# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

A unified fantasy sports platform consolidating multiple games under one domain, one login, and one codebase. Flask modular monolith using blueprints. Each game lives in `games/<game>/` with its own models, routes, services, templates, and CLI commands.

**Games** (status lives in `games/registry.py`):
- `games/worldcup/` — World Cup Fantasy Pool — **live** (`status='open'`)
- `games/cfb/` — CFB Survivor Pool — `coming_soon` (launches ~Aug 2026)
- `games/golf/` — Golf Pick 'Em — `coming_soon`

**Production:** Live at `cccfantasy.com`. CCC design system shipped at tag `impeccable-v1`; every WC tab body sits on the Casual-Light pattern. Product/design spine: `PRODUCT.md` + `DESIGN.md` (repo root); per-game specialization in `games/<slug>/DESIGN.md`. Any UI work invokes the `impeccable` skill, but its stock loader reads only the top-level docs — **hard rule: when working any UI surface under `games/<slug>/`, read `games/<slug>/DESIGN.md` alongside the top-level `DESIGN.md` before producing design output** (top-level owns cross-game/platform-foundation concerns; the per-game file owns that game's palette/accent-rank/register/named primitives; see `docs/impeccable-loader-customization.md`). Update impeccable **only via `/update-plugins`** — never `npx impeccable skills update` from a repo root (drops a stray project-local copy; a guardrail hook blocks it). Before adding new polish, check the two ship-as-is backlogs: `docs/superpowers/specs/2026-05-12-impeccable-design-improvement-scorecard.md` + `docs/superpowers/specs/2026-05-13-worldcup-tab-unification-scorecard.md`.

**Architecture: lounge vs rooms.** Platform `/` is the **club lounge** — dark CCC purple+gold atmosphere, dominated by whichever single game is currently live. Each game has its own **room** with specialized identity (WC: bone substrate + navy hero + WC red accents). **Substrate distinction between dark lounge and game-specific body is by-design architectural separation, not whiplash** — don't try to converge substrates (small handoff polish like a navy bridge band is fine). The lounge stays WC-flavored until CFB Survivor launches (~Aug 2026); then the four lounge state-shells in `core/main/templates/main/_home_*.html` must generalize off WC-specific concepts and cross-game lounge work begins.

---

## Commands

```bash
# Run development server
FLASK_APP=app.py venv/bin/flask run
# Parallel worktree dev server (avoid colliding with main checkout; debug flag auto-reloads Jinja)
FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
# To exercise WC_FAKE_NOW (e.g., flip pre/post deadline for visual smoke), prepend ENVIRONMENT=development:
# ENVIRONMENT=development WC_FAKE_NOW='2026-06-15T12:00:00+00:00' FLASK_APP=app.py FLASK_DEBUG=1 venv/bin/flask run --port 5099
# Without ENVIRONMENT=development|testing, now_utc() ignores WC_FAKE_NOW and serves real time silently.

# Database
FLASK_APP=app.py venv/bin/flask db upgrade          # Apply migrations
FLASK_APP=app.py venv/bin/flask db migrate -m "..."  # Generate new migration
FLASK_APP=app.py venv/bin/flask create-admin        # Create platform admin user

# Golf CLI
FLASK_APP=app.py venv/bin/flask golf sync-run --mode schedule   # Import season schedule
FLASK_APP=app.py venv/bin/flask golf sync-run --mode field      # Sync tournament field
FLASK_APP=app.py venv/bin/flask golf sync-run --mode live       # Update live leaderboard
FLASK_APP=app.py venv/bin/flask golf sync-run --mode results    # Finalize results + process picks

# CFB CLI
FLASK_APP=app.py venv/bin/flask cfb sync --mode setup       # Create next week, import games, activate
FLASK_APP=app.py venv/bin/flask cfb sync --mode spreads     # Lock spreads with latest odds
FLASK_APP=app.py venv/bin/flask cfb sync --mode scores      # Fetch scores, auto-process completed weeks
FLASK_APP=app.py venv/bin/flask cfb sync --mode autopick    # Process auto-picks for past-deadline weeks
FLASK_APP=app.py venv/bin/flask cfb sync --mode remind      # Send email reminders (Fri/Sat only)
FLASK_APP=app.py venv/bin/flask cfb sync --mode status      # Print season summary

# World Cup CLI
FLASK_APP=app.py venv/bin/flask worldcup seed-teams      # Populate teams from world_cup_countries.py
FLASK_APP=app.py venv/bin/flask worldcup seed-matches    # Seed all 104 match shells
FLASK_APP=app.py venv/bin/flask worldcup init            # Seed teams + matches (fresh setup)
FLASK_APP=app.py venv/bin/flask worldcup recalc          # Recalculate all scores (idempotent)
FLASK_APP=app.py venv/bin/flask worldcup status          # Print tournament state summary
FLASK_APP=app.py venv/bin/flask worldcup process-match   # Enter match result (dev/testing)
FLASK_APP=app.py venv/bin/flask worldcup simulate-group-stage  # Bulk-fill all 72 group results (--dry-run to preview); testing aid for advancement
FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks  # Capture daily rank+score snapshot (cron; --backfill N for historical seed)
FLASK_APP=app.py venv/bin/flask worldcup sync --mode link|scores|advancement|digest|status  # football-data.org results sync (link maps fixtures→shells; scores auto-applies finals)
FLASK_APP=app.py venv/bin/flask worldcup send-digest    # Send player match-result digest emails (cron; 5am CT, only when picks scored)

# Tests
ENVIRONMENT=testing venv/bin/python -m pytest tests/      # Run all tests (env var enables WC_FAKE_NOW seam in state-detection tests)
venv/bin/python -m pytest tests/test_worldcup_scoring.py  # Scoring engine tests
venv/bin/python -m pytest tests/test_worldcup_admin.py    # Admin + public route tests
venv/bin/python -m pytest tests/test_worldcup_stats.py    # Stats Hub service + route tests
venv/bin/python -m pytest tests/test_worldcup_leaderboard.py  # Leaderboard route + Your Standing + Trend gate
venv/bin/python -m pytest tests/test_worldcup_stage.py    # Stage-label SSoT (services/stage.py)
venv/bin/python -m pytest tests/test_worldcup_trends.py   # Trend helpers (services/trends.py)
# Single test by name (the gotchas below cite ::test_... regression locks)
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_scoring.py::test_points_for_pick_on_match_parity_with_compute_team_score_events -q
```

No linter configured. No pyright either — verify code with pytest.

---

## Key Conventions

### Design system & CSS

- **Design system:** "Corrupt Commish Club" (CCC) — CCC purple/gold tokens in `static/css/tokens.css` + per-game palettes via `body.game-<game>` CSS class. See `docs/superpowers/specs/2026-04-28-ccc-brand-foundation-design.md`.
- **CSS layering:** `static/css/tokens.css` (CCC house tokens) loads BEFORE `static/css/style.css` (platform aliases + components); both linked from `templates/base.html` head. New tokens go in tokens.css; components consume them via `var(--purple-700)` etc. in style.css.
- **CSS specificity for utility classes:** Single-class utilities (e.g., `.wc-hero-grad`) defined earlier in `style.css` lose cascade to later base rules of equal specificity (`.page-hero`). Scope new utilities as `.base.utility` (e.g., `.page-hero.wc-hero-grad`) to win on (0,0,2,0). The foundation `.wc-*` block already follows this pattern; extend it for any new `.wc-*` that overlaps a later base rule rather than relying on source order.
- **WC body sits on the Casual-Light pattern; `.wc-champion-banner` is the only dark surface left:** Every WC tab body uses white `.card` / `.wc-stat-card` on the bone page substrate; the dark navy `.page-hero.wc-hero-grad` atop each tab is WC's signature identity moment. `.wc-champion-banner` (post-tournament champion banner in the WC-room `games/worldcup/templates/worldcup/_home_post.html`, plus its "Tournament Complete" fallback) is the only remaining body-area dark surface — default new WC surfaces to the light pattern (the generic `.card.wc-card` substrate is retired); reach for `.wc-champion-banner` only for the existing ceremonial slot. **Two parallel `_home_<state>.html` trees exist** — WC room under `games/worldcup/templates/worldcup/`, lounge under `core/main/templates/main/` — and the lounge's post-state banner is a *distinct* primitive, `.champion-banner` (via `_champion_banner.html`), **not** `.wc-champion-banner`. Banner foreground carve-outs needing a bone lift scope as `.wc-champion-banner .<surface>` (currently `.text-muted` and `.wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)`).
- **Bootstrap `.text-muted` override is global, not local:** the canonical CCC override is the `:root { --bs-secondary-color: var(--text-secondary) }` redirect in `style.css`, lifting every bone-canvas instance from `#6c757d` (~3.5:1, sub-AA) to `--text-secondary` (`#5A5470`, ~6.9:1) without specificity wars — don't add new `!important` rules on bone substrates. Dark substrates flip the contrast equation and DO need their own scoped `!important` lifts (`.wc-champion-banner .text-muted`, `.page-hero.wc-hero-grad .hero-subhead.text-muted`); new dark surfaces get their own scoped lift, never another `:root` override.
- **Raw `color: var(--text-muted)` MUST NOT appear on bone/white substrates:** the token (`#8A849B`, ~3.6:1 on white) is calibrated for *dark* substrates only and bypasses the `--bs-secondary-color` redirect that protects the `.text-muted` *class*. On bone/white use `--text-secondary`. Codebase invariant: zero raw `color: var(--text-muted)` in `style.css` outside dark-substrate scopes.
- **Gradient text is fully retired:** zero `background-clip: text` rules in `style.css` (locked by `tests/test_design_p6_s6_1_1.py`). Don't reintroduce it for ceremonial emphasis — use flat gold (`.home-metal-text` precedent: solid `var(--gold-light)` on dark, `var(--gold-dark)` on cream) or DESIGN.md §3 weight/size hierarchy.
- **Navbar lockup + solo-game hoist + auth bust:** the navbar brand pairs the head mark with `wordmark-bone.svg` at **every** width (CSS hides the wordmark only ≤350px; the `<a class="navbar-brand">` carries `aria-label="Corrupt Commish Club"` for the accessible name there). When a user's joined-game count == 1, that game's link hoists out of the hamburger into the bar itself (`.navbar-solo-game`, `d-lg-none`, right of brand) and its collapse copy hides below lg — exactly one rendered link per breakpoint; 0 or 2+ joined games fall back to collapse-only. The auth desktop brand panel leads with `mascot-bust.svg` via the shared `core/auth/templates/auth/_brand_logo.html` partial. Wordmark kit: `static/img/logo/wordmark-{bone,gold,purple}.svg`; unwired brand-kit assets stay in the gitignored `CCC-final/`. Locks: hoist + wordmark gating in `tests/test_navbar_solo_game.py`; asset existence + auth/footer surfaces in `tests/test_logo_assets.py`; versioned URLs + accessible name in `tests/test_asset_versioning.py`.
- **Eyebrow glyph reservation:** `◈` is reserved for *ceremonial* moments (decree countdown, champion banner *with* `champion_team` set, locked seal/oath); `◇` is the *informational* register (sec-heads, roster spine, "Open Court", "Awaiting Decree", rules teaser). Keep `◈` rare so it carries weight. WC body eyebrows have no glyphs (the `.wc-eyebrow` primitive never carries `◈`/`◇`).
- **WC hub state-shell primitives** (extend the WC body doctrine across the live + out states):
  - `_home_out.html` editorial **rules teaser** (`.wc-rules-*` family): eyebrow + Newsreader prose lead + tier-row list with Teko multiplier numerals + Tribune kicker, on the anonymous marketing surface. Replaced the 4-up `.stat-block` strip — never reintroduce it (DESIGN.md §6 Don't #8 ban).
  - `_home_live.html` **Leverage Board** (`.wc-leverage-*` family + `.wc-lk`/`.wc-lk--alert`; rows carry `.is-scoring`/`.is-dormant`/`.is-out`): the hub's **differentiated** live standing hero. Each pick is one row — team + `.wc-multiplier-chip` + realized-points bar painted `--wc-red` + points or "Out" — sorted carriers-first by realized points, then the dormant tail by descending multiplier; `.wc-leverage-summary` states survival (`alive_count`) + highest-multiplier dormant upside. It replaced BOTH the parity-dossier embed AND the separate 9-row roster table, so `.wc-standing-card.is-lead` is the single focal point; `_context_live` returns `leverage` + `leverage_summary` + a slim `dossier` (`alive_count`, `week_delta_points`). The hub deliberately carries **no** rank sparkline — that's the lounge's signature. Retired: `.wc-dossier-*`/`.wc-ledger-*`/`.wc-lk--gold`/`.wc-lk--red` (the latter resolved to navy `--game-primary` — the accent bug this redesign fixed; don't reintroduce it).
  - `_home_live.html` **`.wc-results-strip`** (sibling to `.wc-fixtures-strip`): Recent Results as an inline editorial strip, not a full `.wc-stat-card`. Reuses `.wc-fixtures-strip-head` + `.wc-fixture-side`/`-flag`/`-name`; adds `.wc-result-row` (+ `.is-roster-match` points-earned highlight; `.wc-result-meta`/`.wc-result-pts` carry `white-space: nowrap` so the `+pts` chip never wraps). Keep the lead → strip → preview crescendo when editing live-state.
- **Game theming:** Platform components (`.page-hero`, `.stat-block`, `.btn-game`) consume `--game-primary`/`--game-accent` automatically — game CSS must NOT duplicate this
- **Game CSS sections:** Each game has its own section in `style.css` (e.g., `/* === CFB SURVIVOR POOL === */`) with game-specific component classes
- **Game sub-nav:** Each game needs a `.subnav-<game>` class in the `/* === GAME SUB-NAV === */` section of `style.css` setting `background`, `--subnav-accent` (hex), and `--subnav-accent-rgb` (comma-separated R,G,B) — the shared pill `.active` rule consumes these variables
- **Game palettes:** Golf: Augusta green `#006747` + gold `#b8993e`; CFB: crimson `#C5050C` + midnight `#0f0f1a`; World Cup: navy `#001A4D` + red `#BF0A30` (matches `--wc-navy` / `--wc-red` in tokens.css)
- **Country flags are self-hosted SVG, never emoji:** render via `{% from '_flag.html' import flag with context %}` + `{{ flag(team.iso_code) }}`. `WorldCupTeam.iso_code` (lowercase ISO-2) is the SSoT key into `static/flags/<iso>.svg` (vendored flag-icons 4×3 + `_tbd.svg` for empty KO shells); `flag_emoji` is **legacy fallback only** (Windows ships no emoji flag glyphs — they render as bare "GB"/"MX" letters). `.ccc-flag` is `height:1em`, so the wrapper's `font-size` drives flag size; hairline is ink-tinted on light substrates, bone-tinted on dark. JS-built rows mirror the macro via `flagImg(iso)` + `FLAG_BASE`/`ASSET_V` template constants. Locked by `tests/test_worldcup_flag_emoji.py`.

### Platform integration

- **Emails:** All outbound email routes through `utils/email.py` → `send_platform_email()`; From-name "Corrupt Commish Club"; game-specific content assembly in `games/<game>/services/reminders.py`; HTML emails use table layout + inline styles for Gmail. **Prod sends via Brevo SMTP relay** (`smtp-relay.brevo.com:2525` — DO blocks 25/465/587); `EMAIL_ADDRESS`/`EMAIL_PASSWORD` are the Brevo login+key; visible From is `MAIL_FROM_ADDRESS` = `commish@cccfantasy.com`, the DKIM-authenticated domain sender (**Gmail silently drops mail From the bare SMTP-login address**). Replies to `commish@` forward via Cloudflare Email Routing. **Config-plumbing gotcha:** any env var read via `current_app.config.get()` needs a matching `os.environ.get()` line in `config.py`'s base `Config` class or it's silently `None` (caused the `MAIL_FROM_ADDRESS` prod bug; smoke tests that set `app.config` by hand bypass `config.py` and won't catch it).
- **Avatars:** All game standings must display `user.get_avatar()` inline before the player display name (required integration point for every game blueprint). `User.avatar_emoji` is nullable String(4); default ⚽. **The crown emoji is reserved for platform admins:** `get_avatar()` returns it for any `is_admin` user and substitutes ⚽ for non-admins who have it stored — enforced at every call site, not just the picker (excluded from `AVATAR_CATEGORIES` in `core/auth/routes.py`; `profile.html` shows admins a note instead of the picker). Store the crown as the `'\U0001F451'` escape (`User.ADMIN_AVATAR` in `models/user.py`), never a literal char — literal non-BMP emoji in `.py` source can break import as invalid surrogate pairs.
- **Phone (optional contact):** `User.phone` is nullable String(20), collected at signup, editable on `/profile`. Every phone input MUST normalize through `utils/phone.normalize_us_phone(raw) -> (normalized, error)` (NANP only, stored as `(212) 555-0123`; blank ⇒ `(None, None)`, non-blank invalid ⇒ rejected). Reuse for any new phone surface — don't re-validate inline.

### Code conventions (time, ORM, templates, schema, security)

- **Timestamps:** `datetime.now(timezone.utc)` — never `utcnow()`
- **Time test seam:** `games/worldcup/services/state.now_utc()` is the canonical "now" reader for **all WC application code** — state detection, `_context_*()` builders, routes computing `deadline_passed`, CLI commands deriving "today". It honors `WC_FAKE_NOW` (ISO 8601) when `ENVIRONMENT` is `development`/`testing`, so a faked tournament moment applies consistently across the whole WC surface. Never call `datetime.now()` directly in WC application paths. Exception: SQLAlchemy `default=lambda: datetime.now(timezone.utc)` audit-timestamp lambdas (`created_at`/`updated_at`) record real wall-clock time, not faked time.
- **Mocking the time/deadline seam:** patch `now_utc()` / `TOURNAMENT_DEADLINE_UTC` at the **read-site** — `games.worldcup.services.state` for hub-state resolution (`worldcup_state`/`worldcup_hub_state`); `games.worldcup.routes` only for legacy admin/leaderboard call sites that import the constant directly. Patching `routes.TOURNAMENT_DEADLINE_UTC` does NOT affect `worldcup_hub_state()` (it reads `services.state`'s own import) — patches against the wrong module become silent no-ops, so if a deadline test stops gating behavior after a service extraction, check the patch target before changing the assertion. Every `patch.dict(os.environ, {...})` setting `WC_FAKE_NOW` must also set `'ENVIRONMENT': 'testing'` in the same dict — the seam only activates in dev/testing, and the outside-process env var doesn't propagate when a test file runs without the `ENVIRONMENT=testing` prefix.
- **Timezones:** `zoneinfo.ZoneInfo` — `.replace(tzinfo=tz)`, never pytz
- **ORM:** SQLAlchemy 2.0 style — `db.session.get(Model, id)`, `db.get_or_404()`
- **ORM safety:** Never mutate ORM attributes for display — use transient attributes
- **Jinja2 sorting:** Never use `sort(attribute='method_name')` — Jinja2 retrieves the bound method, not its return value. Sort in the route instead.
- **Jinja macros that read context-processor vars must be imported `with context`:** e.g. `_flag.html`'s `flag()` uses `asset_version`, so callers do `{% from '_flag.html' import flag with context %}` — a plain `import` leaves it undefined inside the macro (silent, no error; `url_for` is a global and works either way). Corollary: template-source tests checking the "first rendered element" must strip `{% ... %}` tags, not just comments, or a top-of-file import trips them.
- **Template restyling:** When restyling templates with JavaScript, audit all `querySelector`/`querySelectorAll`/`getElementById` calls first. Add CSS classes alongside JS-critical ones — never rename or remove them.
- **Schema changes:** Flask-Migrate (Alembic) only — never raw SQL
- **CSRF:** All POST forms include CSRF token; AJAX includes `X-CSRFToken` header
- **POST-only:** All state-mutating operations use POST — no GET routes that change data

### Auth, admin, enrollment

- **Admin scoping:** Two-tier game admin — platform admin (`User.is_admin`) always has access to every game's admin routes. Game-specific admin (`<Game>Enrollment.is_admin`) allows delegating admin to enrolled non-platform-admins. All `<game>_admin_required` decorators must check platform admin first, enrollment admin second.
- **Session identity is `User.auth_id`, NOT the integer PK:** `User.get_id()` returns the random, never-reused `auth_id` token (`models/user.py`), and the Flask-Login `user_loader` (`app.py`) resolves by `auth_id`. **Security invariant** — do NOT revert to the integer `id`. Reason (2026-06-01 prod incident): a DB wipe restarts the `users` id sequence, and a pre-wipe remember-me cookie (still validly signed) cross-authenticated a recycled PK as a different person; a random `auth_id` makes stale cookies match nothing. Locked by `tests/test_auth_session_identity.py`. Corollary: any destructive DB reset must also rotate `SECRET_KEY` (see `docs/production-launch-test-script.md` §14C).
- **Authenticated responses are `Cache-Control: private, no-store`:** stamped by an `@app.after_request` hook in `app.py` when `current_user.is_authenticated` (static endpoint excepted). **Security invariant** — a shared cache that ignores `Vary: Cookie` (e.g. a Cloudflare "Cache Everything" rule) could serve one user's rendered page to another. Anonymous responses stay cacheable on purpose (CDN fronts the public surfaces) — never blanket `no-store` onto them. Locked by `tests/test_response_cache_headers.py`.
- **Password reset tokens:** `core/auth/tokens.py` uses `itsdangerous.URLSafeTimedSerializer` with 1-hour expiry. Forgot-password route uses anti-enumeration pattern (identical flash message regardless of email existence).
- **Game registry:** `games/registry.py` is the SSoT — one `GameRegistryEntry` per game (slug, status, is_featured, endpoints, `get_enrollment` + `admin_enroll` callables); its helpers drive homepage, navbar, and admin add-user page. Flip `status` from `'coming_soon'` to `'open'` at launch.
- **Enrollment is explicit:** users reach a game's interior routes only via `/<game>/join` (guarded by `@game_must_be_open(slug)` in `games/common.py`). Interior pick routes carry `@enrollment_required(slug)`, which redirects unenrolled users to `/<game>/join?next=<current>`. **Never** create `<Game>Enrollment` rows from pick or admin paths — platform admins enroll users via `/admin/enrollments`.
- **Admin destructive actions:** destructive admin POST handlers branch on `request.form.get('action')` — `action=clear` is a distinct, guarded path that short-circuits before the main mutation. Keep this pattern for new admin routes that both mutate and reset.

### World Cup scoring & ranking

- **Results automation:** `games/worldcup/services/sync.py` (`flask worldcup sync`, football-data.org free tier, 30-min systemd timer) auto-applies completed-match results through `process_match_result` — match data stays SSoT. Group advancement + KO bracket are **admin-confirmed** via the "Load from API" pre-fill on `/worldcup/admin/advancement`, never auto-written. Don't add a parallel results-entry or scoring path. Player daily digest (`flask worldcup send-digest`, `services/notifications.py`) fires 5am CT via `worldcup-digest-player.timer` — one email per player per day, only when picks scored the previous CT calendar day. Specs: `docs/superpowers/specs/2026-06-02-worldcup-results-automation-design.md` + `2026-06-02-worldcup-daily-digest-design.md`.
- **Scoring attribution:** `games/worldcup/services/scoring.compute_team_score_events` (per-team), `compute_match_attribution` (per-match), and `points_for_pick_on_match` (per-pick-per-match) are the SSoT for scoring breakdowns; stored `total_score` must equal the sum of those ScoreEvents, and any new UI surfacing scoring detail must derive from these helpers, not recompute. The per-pick helper guards participation and routes knockout points via `_apply_knockout_points()` to stay in lockstep with the per-team helper (parity test in `tests/test_worldcup_scoring.py`).
- **Team "out of tournament" = `games/worldcup/services/elimination.eliminated_team_ids()`** (group exit OR completed-knockout loss; one N+1-free set). `WorldCupTeam.is_eliminated` is **group-stage-only** — correct only in group-scoped surfaces like `groups.html`; every "is this pick still alive" read-site routes through the helper. Locked by `tests/test_worldcup_elimination.py`.
- **Per-match scoring display unit:** `compute_team_score_events()` keeps **base points** as SSoT (multiplier not applied in the helper); the `team_detail` route builds `points_by_match[match_id]` from base points and the template applies `* team.multiplier` at render time so the per-match column matches the hero's "Scored" unit. New per-match displays must multiply at template time — never store multiplied values in `points_by_match` (lock: `tests/test_worldcup_team_detail.py::test_team_detail_fixture_pts_apply_multiplier`). By contrast, `points_for_pick_on_match` returns *already-multiplied* points by contract — deliberately parallel SSoTs with different output units (lock: `tests/test_worldcup_scoring.py::test_points_for_pick_on_match_parity_with_compute_team_score_events`, asserts `sum == multiplier × base`). Pass per-pick output to UI unchanged; don't refactor the helper to base.
- **Dense rank everywhere:** `routes.leaderboard()` and `services/ranking.compute_rank_neighbors()` both use dense rank — tied scores share a rank, next distinct score is `rank + 1` (no gap). Never reintroduce competition rank (`1, 2, 2, 4`); a tied player's leaderboard rank must equal their `/worldcup/leaderboard/<id>` detail rank ("Your Standing" reuses `compute_rank_neighbors` and depends on this parity). Jinja idiom for top-N preview tables: `{% set ns = namespace(rank=0, prev_score=None) %}` then `{% if e.total_score != ns.prev_score %}{% set ns.rank = ns.rank + 1 %}{% endif %}` — never `ns.rank = loop.index` (competition rank).
- **Home-page state shell:** `core/main/home_context.build_home_context(user, state)` dispatches to four per-state builders (`_context_out` / `_pre` / `_live` / `_post`); the home route resolves `state` from `worldcup_state()` and renders the matching `_home_<state>.html` partial inside `home_shell.html`. New home-page work goes through these builders — never recompute scoring or rank in the template. The **lounge** (`/`) live-state dossier sparkline + week-delta read `WorldCupRankSnapshot` rows captured nightly by `flask worldcup snapshot-ranks` (idempotent; `--backfill N` seeds history). Week-delta is gated behind `len(snapshots) >= 7` to avoid overstating early trends; the sparkline SVG is `aria-hidden` (cap text, rank-movement block, and Ledger prose carry the data) with a `.sparkline-flat-note` backstop in the 2-6 snapshot window. **The WC hub live state is deliberately differentiated from the lounge:** the lounge keeps the rank-trend dossier as the canonical rich surface; the hub leads with the Leverage Board (see WC hub state-shell primitives above; `games/worldcup/services/home_context._context_live`) and leans into the multiplier system — it does **not** mirror the lounge's rank chart, and the retired lounge-parity dossier embed must not come back. `week_delta_points` keeps the ≥7-snapshot gate.
- **`WorldCupRankSnapshot` aggregates must be season-scoped:** the snapshot row has no `season_year` column — season is reachable only via `enrollment.season_year`, so every aggregate query MUST `.join(WorldCupEnrollment, WorldCupEnrollment.id == WorldCupRankSnapshot.enrollment_id).filter(WorldCupEnrollment.season_year == SEASON_YEAR)` or prior-cup snapshots contaminate current-cup aggregates. Lock: `tests/test_worldcup_leaderboard.py::test_trend_column_gate_scoped_to_active_season`.

### World Cup labels, analytics, & privacy

- **Stage labels:** `games/worldcup/services/stage.stage_label(stage)` is the SSoT for display labels of `WorldCupMatch.stage` (`'SF'` → `'Semifinals'`, etc.); `core/main/home_context` re-imports it as `_stage_label`. Templates must NOT use `match.stage|title` — `|title` mangles ALL-CAPS codes (`'SF'` → `'Sf'`) and underscored values (`'third_place'` → `'Third_Place'`). Plumb `stage_label` through the context dict instead.
- **`team.best_finish` labels:** `games/worldcup/services/stage.best_finish_label(code)` is the SSoT mapping `WorldCupTeam.best_finish` codes to display strings — a **different value space** from `stage_label` (drops `final`/`third_place`, adds podium codes `3rd`/`runner_up`/`champion`). **BOTH** post-state roster recaps consume it — lounge (`core/main/home_context`) and WC room (`games/worldcup/services/home_context`) — so they can't diverge. Two enforced rules: (1) empty/`None` ⇒ `'Round of 32'` (advanced from group, lost in R32) — **distinct** from `'group'` ⇒ `'Group Stage'` (group-stage exit); collapsing both to "Group" mislabels a group winner as a group exit. (2) Unknown codes fall back to the **raw code**, never `'Group'`, so a new scoring code surfaces as the bug it is. Locked by `tests/test_worldcup_stage.py`. Don't reintroduce a per-builder label map.
- **Tournament `current_phase` ≠ `WorldCupMatch.stage`:** different value spaces. `current_phase` is the *tournament-level* code (`'pre_tournament'`/`'group_stage'`/`'knockout'`/`'completed'`), derived by `_derive_tournament_phase()` and rendered via inline `{% if %}/{% elif %}`. Don't pipe it through `_stage_label` (no entries for those keys — silently falls back to "Group Stage").
- **Stats analytics layer:** `games/worldcup/services/stats.py` exposes 4 public functions consumed by the public `/worldcup/stats` route. Public analytics routes must NOT use `@login_required`; build `my_picks` via `WorldCupPick.query.join(WorldCupTeam)` (never `enrollment.picks` — N+1).
- **Pre-deadline ownership privacy (D11):** `games/worldcup/services/team_detail.compute_team_ownership(team_id, deadline_passed=False)` returns `count=0, percent=0.0, picker_names=None` for **all viewers, including the team's own picker**. The `team_detail.html` ownership count/percent block is gated on `deadline_passed` only — do NOT add `or user_owns` to that inner guard (a non-zero count visible to the owner pre-lock leaks third-party roster info). Locks: `test_team_detail_user_owns_ribbon_pre_deadline` + `test_team_detail_ownership_hidden_pre_deadline`. Any future ownership/roster-overlap UI: hide counts from everyone pre-deadline, not just non-owners.

### Production ops

- **Production environment selection:** `ENVIRONMENT=production` is set in three places as defense-in-depth — the server's `.env`, the systemd unit's `Environment=` override, and every flask line in `deploy.sh` + crontab; keep all three in sync when adding cron entries or deploy steps. `migrations/env.py` reads the DB engine from `create_app()`'s config, so a stray `ENVIRONMENT=development` silently migrates against SQLite instead of Postgres.
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
- `/<game>/join` route + `games/<game>/templates/<game>/join.html` following the World Cup shape (`page-hero` + how-it-works card + form + `btn-game`), decorated with `@game_must_be_open('<game>')`
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

Live architecture: DO Droplet (Ubuntu 24.04) running Nginx → Gunicorn (unix socket) → Flask; DO Managed Postgres over private VPC; Cloudflare proxy + Origin Certificate for TLS. Cron jobs run sync commands on the Droplet.

Deploy files live in `deploy/`:
- `deploy/nginx.conf` — site config (HTTPS, HTTP/2, gzip, HSTS, security headers)
- `deploy/fantasy-platform.service` — systemd unit for Gunicorn (3 workers, `RuntimeDirectory=fantasy-platform`, socket at `/run/fantasy-platform/gunicorn.sock`)
- `deploy.sh` — one-command deploy on the server: `git pull` → `pip install` → `flask db upgrade` → `systemctl restart`

To ship an update from local:
```bash
git push origin main                     # local
ssh deploy@<droplet-ip>                  # server
./deploy.sh                              # runs inside /home/deploy/fantasy-platform
```

First-time setup: `docs/superpowers/plans/2026-04-21-production-deployment.md`.
Production re-verification: `docs/production-launch-test-script.md` (full WC simulation on prod — out → pre → live → post — then DB reset to a clean baseline).

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
ODDS_API_KEY=...         # The Odds API (CFB scores/spreads)
FOOTBALL_DATA_API_KEY=...  # football-data.org (World Cup results sync; free tier covers WC 2026 — API-Football free does NOT)
SLASHGOLF_API_KEY=...    # SlashGolf API (Golf leaderboards)
EMAIL_ADDRESS=...        # SMTP auth login (prod: Brevo SMTP login, e.g. ad34xxxxx@smtp-brevo.com)
EMAIL_PASSWORD=...       # SMTP key/password (prod: Brevo SMTP key)
MAIL_FROM_ADDRESS=...    # Visible From; prod: commish@cccfantasy.com. Falls back to EMAIL_ADDRESS if unset
SMTP_SERVER=...          # Dev default smtp.gmail.com; prod smtp-relay.brevo.com
SMTP_PORT=...            # Dev default 587; prod 2525 (DO blocks 587)
```
