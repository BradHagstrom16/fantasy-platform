# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

A unified fantasy sports platform consolidating multiple games under one domain, one login, and one codebase. Flask modular monolith using blueprints. Each game lives in `games/<game>/` with its own models, routes, services, templates, and CLI commands.

**Active games:**
- `games/golf/` — Golf Pick 'Em (live)
- `games/cfb/` — CFB Survivor Pool (live)
- `games/worldcup/` — World Cup Fantasy Pool (live)

**Production:** Live at `cccfantasy.com`. CCC design system shipped at tag `impeccable-v1` (2026-05-12, PR #17); WC Tab Unification closed 2026-05-14 (PR #28) putting every WC tab body on the Casual-Light pattern. See `PRODUCT.md` + `DESIGN.md` (repo root) for the product/design spine; per-game specialization lives in `games/<slug>/DESIGN.md` (currently `games/worldcup/DESIGN.md`). Any UI work invokes the `impeccable` skill which preflight-loads both — the local impeccable loader is customized to discover per-game files; see `docs/impeccable-loader-customization.md` for the re-apply snippet if an impeccable upgrade ever overwrites it. Two ship-as-is backlogs predate new polish work: `docs/superpowers/specs/2026-05-12-impeccable-design-improvement-scorecard.md` (22 deferred items) and `docs/superpowers/specs/2026-05-13-worldcup-tab-unification-scorecard.md` (per-tab finals + WC-specific debt) — check both before adding new polish.

**Architecture: lounge vs rooms.** Platform `/` is the **club lounge** — dark CCC purple+gold atmosphere, dominated by whichever single game is currently live. Each game has its own **room** with specialized identity (WC: bone substrate + navy hero + WC red accents; future CFB/Golf each their own). The lounge is *always* single-game-flavored by the active game; cross-game lounge work only begins when ≥2 games run simultaneously. **Substrate distinction between dark lounge and game-specific body is by-design architectural separation, not whiplash.** WC content on `/` is correct through ~2026-07-19; transitions to CFB-flavored when WC closes and CFB Survivor launches (~Aug 2026). When that happens, the four lounge state-shells in `core/main/templates/main/_home_*.html` will need to generalize off WC-specific concepts. Don't try to converge substrates; small handoff polish (e.g., navy bridge band between dark navbar and bone WC body) is acceptable polish-tier work.

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
FLASK_APP=app.py venv/bin/flask worldcup snapshot-ranks  # Capture daily rank+score snapshot (cron; --backfill N for historical seed)

# Tests (this project verifies via pytest only — pyright is not part of the workflow)
ENVIRONMENT=testing venv/bin/python -m pytest tests/      # Run all tests (env var enables WC_FAKE_NOW seam in state-detection tests)
venv/bin/python -m pytest tests/test_worldcup_scoring.py  # Scoring engine tests
venv/bin/python -m pytest tests/test_worldcup_admin.py    # Admin + public route tests
venv/bin/python -m pytest tests/test_worldcup_stats.py    # Stats Hub service + route tests
venv/bin/python -m pytest tests/test_worldcup_leaderboard.py  # Leaderboard route + Your Standing + Trend gate
venv/bin/python -m pytest tests/test_worldcup_stage.py    # Stage-label SSoT (services/stage.py)
venv/bin/python -m pytest tests/test_worldcup_trends.py   # Trend helpers (services/trends.py)
```

No linter configured. No pyright either — verify code with pytest.

---

## Key Conventions

### Design system & CSS

- **Design system:** "Corrupt Commish Club" (CCC) — CCC purple/gold tokens in `static/css/tokens.css` + per-game palettes via `body.game-<game>` CSS class. See `docs/superpowers/specs/2026-04-28-ccc-brand-foundation-design.md`.
- **CSS layering:** Layer 1 (`static/css/tokens.css` — CCC house tokens: purples, golds, bone, gradients, fonts) loads BEFORE Layer 2 (`static/css/style.css` — platform aliases + components). New design tokens go in tokens.css; component styles consume them via `var(--purple-700)` etc. in style.css. Both linked from `templates/base.html` head.
- **CSS specificity for utility classes:** Single-class utilities (e.g., `.wc-hero-grad`) defined earlier in `style.css` lose cascade to later base rules of equal specificity (`.page-hero`). Scope new utilities as `.base.utility` (e.g., `.page-hero.wc-hero-grad`) to win on (0,0,2,0). Foundation `.wc-*` block already follows this pattern after PR #5; extend it for any new `.wc-*` that overlaps with a later base rule rather than relying on source order.
- **WC body sits on the Casual-Light pattern; `.wc-champion-banner` is the only dark surface left:** Every WC tab body (HUB / ROSTER / BOARD / SCHEDULE / STATS / RULES) uses white `.card` / `.wc-stat-card` on the bone page substrate. The dark navy `.page-hero.wc-hero-grad` (top of each tab) stays as WC's signature identity moment; the dedicated `.wc-champion-banner` primitive (rendered only on the post-tournament champion banner in `_home_post.html` when a winner is declared, or as the defensive "Tournament Complete" fallback) is the only remaining body-area dark surface. The prior generic `.card.wc-card` substrate retired in WC tab unification P5 — when adding new WC surfaces, default to the light pattern; reach for `.wc-champion-banner` only for the existing ceremonial slot. Foreground-color carve-outs that need a bone lift on the banner scope as `.wc-champion-banner .<surface>` (currently `.text-muted` and `.wc-eyebrow:not(.wc-eyebrow-red):not(.wc-eyebrow-gold)`).
- **Bootstrap `.text-muted` override is global, not local:** Don't add new `!important` rules to override `.text-muted` color on bone substrates. Bootstrap 5.3 resolves `.text-muted` via `var(--bs-secondary-color)`; the canonical CCC override is the `:root { --bs-secondary-color: var(--text-secondary) }` redirect in `style.css` (S6.1.1 PI-2) which lifts every bone-canvas instance from `#6c757d` (~3.5:1 on bone, sub-AA) to `--text-secondary` (`#5A5470`, ~6.9:1) without specificity wars. Dark substrates still need their own scoped `!important` rules — `.wc-champion-banner .text-muted` and `.page-hero.wc-hero-grad .hero-subhead.text-muted` — because the substrate flip changes the contrast equation. New dark surfaces adopting `.text-muted` need their own scoped lift, not another `:root` override.
- **Raw `color: var(--text-muted)` MUST NOT appear on bone/white substrates.** The `--text-muted` token (`#8A849B`, ~3.6:1 on white) is calibrated for *dark* substrates only; using it directly in custom rules bypasses the `--bs-secondary-color` redirect that protects the `.text-muted` *class*. On bone/white, use `--text-secondary` (`#5A5470`, ~6.9:1 AA). PR #33 cleaned up 13 CSS rules + 2 inline-style usages; the codebase invariant is now zero raw `color: var(--text-muted)` in `style.css` outside dark-substrate scopes.
- **Gradient text is fully retired:** zero `background-clip: text` rules remain in `style.css` (locked by `tests/test_design_p6_s6_1_1.py`). The retire happened at S6.1.1 PI-3 — three rules collapsed to solid `var(--gold-light)` on dark substrates and `var(--gold-dark)` on cream. Don't reintroduce gradient-text for ceremonial emphasis; the precedent is `.home-metal-text` (style.css :461, flat gold-light) or DESIGN.md §3 weight/size hierarchy.
- **Eyebrow glyph reservation:** `◈` is reserved for *ceremonial* moments (decree countdown, champion banner *with* `champion_team` set, locked seal/oath). `◇` is the *informational* register (sec-heads, roster spine, "Open Court" labels, "Awaiting Decree" pending state, "How Scoring Works" rules teaser). Per-state state-shell eyebrows on the lounge accumulate at md+ viewports — keep `◈` rare so it carries weight. WC body eyebrows have no glyphs (WC chrome convention; the `.wc-eyebrow` primitive doesn't carry `◈`/`◇` anywhere).
- **WC hub state-shell primitives:** small primitives that extend the WC body doctrine across the live + out states.
  - `_home_out.html` editorial **rules teaser** (`.wc-rules-teaser` / `.wc-rules-row` / `.wc-rules-name` / `.wc-rules-picks` / `.wc-rules-mult` / `.wc-rules-lead` / `.wc-rules-kicker`): replaces the prior 4-up `.stat-block` strip on the anonymous marketing surface. Pattern is eyebrow + Newsreader prose lead + tier-row list with Teko multiplier numerals + Tribune kicker. Activation surface; never reintroduce the stat-block strip (DESIGN.md §6 Don't #8 ban).
  - `_home_live.html` **Leverage Board** (`.wc-standing-pts-line`; `.wc-leverage` / `.wc-leverage-eyebrow` / `.wc-leverage-list` / `.wc-leverage-row` + `.is-scoring`/`.is-dormant`/`.is-out` / `.wc-leverage-team` / `.wc-leverage-flag` / `.wc-leverage-code` / `.wc-leverage-bar` + `.wc-leverage-bar-fill` / `.wc-leverage-pts` / `.wc-leverage-status` / `.wc-leverage-summary` / `.wc-lk` + `.wc-lk--alert`): the hub's **differentiated** live standing hero ($impeccable critique 2026-05-24, "differentiate the hub" direction). Each pick is one leverage row — team + `.wc-multiplier-chip` + a realized-points bar painted `--wc-red` (WC primary accent, the correct semantic role for "where the points are") + points or an "Out" status label — sorted carriers-first by realized points (biggest bar on top), then the dormant tail by descending multiplier (so the highest-upside dormant picks lead it); a `.wc-leverage-summary` line states survival (`alive_count`) and the highest-multiplier dormant "upside". It replaces BOTH the prior parity-dossier embed AND the separate 9-row roster table, so the `.wc-standing-card.is-lead` lead card is the single focal point. `_context_live` returns `leverage` (list) + `leverage_summary` (dict) + a slim `dossier` (`alive_count`, `week_delta_points`). The hub deliberately carries **no** rank sparkline — that's the lounge's signature (see Home-page state shell below). The retired `.wc-dossier-*`/`.wc-ledger-*`/`.wc-lk--gold`/`.wc-lk--red` classes are gone; `.wc-lk--red` resolved to navy (`--game-primary`) and was the accent bug this redesign fixed, so don't reintroduce it.
  - `_home_live.html` **`.wc-results-strip`** (sibling to `.wc-fixtures-strip`): demotes Recent Results from a full `.wc-stat-card` to an inline editorial strip. Reuses `.wc-fixtures-strip-head` + `.wc-fixture-side`/`-flag`/`-name`; adds `.wc-result-row` with `.wc-result-row.is-roster-match` for the points-earned roster highlight (`.wc-result-meta` / `.wc-result-pts` carry `white-space: nowrap` so the `+pts` chip never wraps the row). Keep the lead → strip → preview crescendo when editing live-state (the roster table folded into the Leverage Board lead).
- **Game theming:** Platform components (`.page-hero`, `.stat-block`, `.btn-game`) consume `--game-primary`/`--game-accent` automatically — game CSS must NOT duplicate this
- **Game CSS sections:** Each game has its own section in `style.css` (e.g., `/* === CFB SURVIVOR POOL === */`) with game-specific component classes
- **Game sub-nav:** Each game needs a `.subnav-<game>` class in the `/* === GAME SUB-NAV === */` section of `style.css` setting `background`, `--subnav-accent` (hex), and `--subnav-accent-rgb` (comma-separated R,G,B) — the shared pill `.active` rule consumes these variables
- **Game palettes:** Golf: Augusta green `#006747` + gold `#b8993e`; CFB: crimson `#C5050C` + midnight `#0f0f1a`; World Cup: navy `#001A4D` + red `#BF0A30` (matches `--wc-navy` / `--wc-red` in tokens.css)

### Platform integration

- **Emails:** All outbound email routes through `utils/email.py` → `send_platform_email()`. From-name: "Corrupt Commish Club". Game-specific content assembly stays in `games/<game>/services/reminders.py`. HTML emails: table layout + inline styles for Gmail compatibility.
- **Avatars:** All game standings must display `user.get_avatar()` inline before the player display name. `User.avatar_emoji` is nullable String(4); default is ⚽. Required integration point for every game blueprint. **The crown emoji is reserved for platform admins:** `get_avatar()` returns it for any `is_admin` user (ignoring their stored `avatar_emoji`) and substitutes ⚽ for any non-admin who has it stored — so the reservation is enforced at every call site, not just the picker. It is excluded from `AVATAR_CATEGORIES` (`core/auth/routes.py`), and `profile.html` replaces the picker with a note for admins. The crown is stored as the `'\U0001F451'` escape (`User.ADMIN_AVATAR` in `models/user.py`), never a literal char — literal non-BMP emoji in `.py` source can be written as invalid surrogate pairs and break import.
- **Phone (optional contact):** `User.phone` is nullable String(20), collected at signup and editable on `/profile`. Every phone input MUST validate + normalize through `utils/phone.normalize_us_phone(raw) -> (normalized, error)` (US/Canada NANP only, stored as `(555) 123-4567`). Blank returns `(None, None)` (the field is optional); a non-blank invalid value is rejected. Reuse this helper for any new phone surface — don't re-validate inline.

### Code conventions (time, ORM, templates, schema, security)

- **Timestamps:** `datetime.now(timezone.utc)` — never `utcnow()`
- **Time test seam:** `games/worldcup/services/state.now_utc()` is the canonical "now" reader for **any World Cup application code that reads current time** — home-page state detection, `_context_*()` builders, World Cup routes that compute `deadline_passed`, and CLI commands that derive "today" (e.g., `snapshot-ranks`). It honors `WC_FAKE_NOW` (ISO 8601) when `ENVIRONMENT` is `development` or `testing`, so a developer can fake any tournament moment in dev/test by setting that env var and have it apply consistently across the whole WC surface. Never reach for `datetime.now()` directly in WC application paths. Exception: SQLAlchemy `default=lambda: datetime.now(timezone.utc)` column lambdas for audit timestamps (`created_at`, `updated_at`) — those should record actual wall-clock time, not faked time.
- **Mocking the time/deadline seam:** `now_utc()` and `TOURNAMENT_DEADLINE_UTC` must be patched at the **read-site**, which is `games.worldcup.services.state` for hub-state resolution (`worldcup_state` / `worldcup_hub_state`) and `games.worldcup.routes` only for the legacy admin/leaderboard call sites that still import the constant directly. A `mock.patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', …)` does NOT affect `worldcup_hub_state(user)` — that resolver reads from `services.state`'s own import. Tests written against the pre-Plan-4 surface were silently broken this way (their patches became no-ops; assertions passed/failed against unpatched real-time behavior). If a deadline-controlling test stops gating behavior after a service extraction, check the patch target before changing the assertion. Every `patch.dict(os.environ, {...})` that sets `WC_FAKE_NOW` must also set `'ENVIRONMENT': 'testing'` in the same dict — `now_utc()` only activates the seam when `ENVIRONMENT` is `development` or `testing`, and the outside-process env var doesn't propagate when tests run in isolation (e.g., `pytest tests/<file>.py` without the `ENVIRONMENT=testing` prefix).
- **Timezones:** `zoneinfo.ZoneInfo` — `.replace(tzinfo=tz)`, never pytz
- **ORM:** SQLAlchemy 2.0 style — `db.session.get(Model, id)`, `db.get_or_404()`
- **ORM safety:** Never mutate ORM attributes for display — use transient attributes
- **Jinja2 sorting:** Never use `sort(attribute='method_name')` — Jinja2 retrieves the bound method, not its return value. Sort in the route instead.
- **Template restyling:** When restyling templates with JavaScript, audit all `querySelector`/`querySelectorAll`/`getElementById` calls first. Add CSS classes alongside JS-critical ones — never rename or remove them.
- **Schema changes:** Flask-Migrate (Alembic) only — never raw SQL
- **CSRF:** All POST forms include CSRF token; AJAX includes `X-CSRFToken` header
- **POST-only:** All state-mutating operations use POST — no GET routes that change data

### Auth, admin, enrollment

- **Admin scoping:** Two-tier game admin — platform admin (`User.is_admin`) always has access to every game's admin routes. Game-specific admin (`<Game>Enrollment.is_admin`) allows delegating admin to enrolled non-platform-admins. All `<game>_admin_required` decorators must check platform admin first, enrollment admin second.
- **Password reset tokens:** `core/auth/tokens.py` uses `itsdangerous.URLSafeTimedSerializer` with 1-hour expiry. Forgot-password route uses anti-enumeration pattern (identical flash message regardless of email existence).
- **Game registry:** `games/registry.py` is the single source of truth — every game has one `GameRegistryEntry` (slug, status, is_featured, blueprint_index/join endpoints, `get_enrollment` + `admin_enroll` callables). Helpers `joined_games`/`available_games`/`coming_soon_games`/`featured_games`/`get_entry` drive homepage, navbar, and admin add-user page. Flip `status` from `'coming_soon'` to `'open'` at launch.
- **Enrollment is explicit:** users reach a game's interior routes only via `/<game>/join` (guarded by `@game_must_be_open(slug)` in `games/common.py`). Interior pick routes carry `@enrollment_required(slug)`, which redirects unenrolled users to `/<game>/join?next=<current>`. **Never** create `<Game>Enrollment` rows from pick or admin paths — platform admins enroll users via `/admin/enrollments`.
- **Admin destructive actions:** Destructive admin POST handlers (e.g., `admin_match_result`, `admin_set_knockout`) branch on `request.form.get('action')` — `action=clear` is a distinct, guarded path that short-circuits before the main mutation. Keep this pattern for new admin routes that both mutate and reset.

### World Cup scoring & ranking

- **Scoring attribution:** `games/worldcup/services/scoring.compute_team_score_events` (per-team), `compute_match_attribution` (per-match), and `points_for_pick_on_match` (per-pick-per-match) are the single source of truth for scoring breakdowns. Stored `total_score` must equal the sum of those ScoreEvents. Any new UI that surfaces scoring detail must derive from these helpers, not recompute. The per-pick helper guards participation (`pick.team_id in (home, away)`) and routes knockout points via `_apply_knockout_points()` so it stays in lockstep with the per-team helper — a parity invariant test in `tests/test_worldcup_scoring.py` locks this.
- **Per-match scoring display unit:** `compute_team_score_events()` keeps base points as the SSoT (per-event `base_points` field; multiplier is *not* applied in the helper). The `team_detail` route builds `points_by_match[match_id] = sum of base_points` from those events, and the template applies `* team.multiplier` at render time so the per-match column reads in the same unit as the hero's "Scored" stat. When adding a new per-match scoring display, multiply at template time — never store multiplied values in `points_by_match` or pass raw base to a column that sits next to multiplied totals. Regression lock: `tests/test_worldcup_team_detail.py::test_team_detail_fixture_pts_apply_multiplier`. By contrast, `points_for_pick_on_match` returns *already-multiplied* points by contract — the per-team and per-pick helpers are deliberately parallel SSoTs with different output units. Locked by `tests/test_worldcup_scoring.py::test_points_for_pick_on_match_parity_with_compute_team_score_events` (asserts `sum == multiplier × base`). Pass per-pick output to UI surfaces unchanged; don't refactor the helper to base.
- **Dense rank everywhere:** Both `routes.leaderboard()` and `games/worldcup/services/ranking.compute_rank_neighbors()` use dense rank — tied scores share a rank and the next distinct score is `rank + 1` (no gap). Don't reintroduce competition rank (`1, 2, 2, 4` gap pattern); a tied player's leaderboard rank must equal the rank shown on their `/worldcup/leaderboard/<id>` detail page. Plan 3's "Your Standing" reuses `compute_rank_neighbors` and depends on this parity. Canonical Jinja idiom for top-N preview tables: `{% set ns = namespace(rank=0, prev_score=None) %}` then `{% if e.total_score != ns.prev_score %}{% set ns.rank = ns.rank + 1 %}{% endif %}` — never `{% set ns.rank = loop.index %}` (that's competition rank).
- **Home-page state shell:** `core/main/home_context.build_home_context(user, state)` dispatches to one of four per-state builders (`_context_out` / `_pre` / `_live` / `_post`); the home route resolves `state` from `worldcup_state()` and renders the matching `_home_<state>.html` partial inside `home_shell.html`. New home-page work goes through these builders — never recompute scoring or rank in the template. The **lounge** (`/`) live-state dossier sparkline + week-delta read from `WorldCupRankSnapshot` rows captured nightly by `flask worldcup snapshot-ranks` (idempotent; `--backfill N` seeds historical days). Week-delta is gated behind `len(snapshots) >= 7` to avoid overstating early-deploy trends; the lounge sparkline SVG is `aria-hidden` (the cap text, rank-movement block, and Ledger prose carry the data) and a `.sparkline-flat-note` worded line backstops the dashed flat-line render in the 2-6 snapshot window. **The WC hub live state is deliberately differentiated from the lounge dossier ($impeccable critique 2026-05-24, "differentiate the hub").** The lounge `/` keeps the rank-trend dossier as the canonical rich surface (per the lounge/room architecture above); the WC hub leads with the **Leverage Board** instead — `games/worldcup/services/home_context._context_live` returns `leverage` (per-pick multiplier/realized-points rows) + `leverage_summary` (survival + dormant-upside) + a slim `dossier` (`alive_count`, `week_delta_points`), and `_home_live.html` renders the board inside `.wc-standing-card.is-lead`. The hub leans into the multiplier system (the WC custom-game identity); it does **not** mirror the lounge's rank chart. The earlier PR #33 parity embed (sparkline + Newsreader ledger + top-earner) was retired in this differentiation — don't reintroduce a lounge-parity dossier on the hub. `week_delta_points` keeps the ≥7-snapshot gate for the standing points-line trend clause.
- **`WorldCupRankSnapshot` aggregates must be season-scoped:** the snapshot row has no `season_year` column — season is reachable only via `enrollment.season_year`. Any aggregate query (gates, totals, week-deltas, distinct-day counts) MUST `.join(WorldCupEnrollment, WorldCupEnrollment.id == WorldCupRankSnapshot.enrollment_id).filter(WorldCupEnrollment.season_year == SEASON_YEAR)`. Without scoping, prior-cup snapshots contaminate current-cup aggregates (the trend-column gate had this bug — fixed in PR #7; locked by `tests/test_worldcup_leaderboard.py::test_trend_column_gate_scoped_to_active_season`).

### World Cup labels, analytics, & privacy

- **Stage labels:** `games/worldcup/services/stage.stage_label(stage)` is the single source of truth for display labels of `WorldCupMatch.stage` (`'SF'` → `'Semifinals'`, `'third_place'` → `'Third-Place Match'`, etc.). `core/main/home_context` re-imports it as `_stage_label` to preserve legacy call sites. Templates must NOT use `match.stage|title` — Jinja's `|title` filter mangles ALL-CAPS knockout codes (`'SF'` → `'Sf'`, `'QF'` → `'Qf'`) and underscored values (`'third_place'` → `'Third_Place'`). Plumb `stage_label` through the context dict instead.
- **`team.best_finish` labels:** `games/worldcup/services/home_context._BEST_FINISH_LABELS` maps canonical `WorldCupTeam.best_finish` codes (per `scoring.STAGE_ORDER`) to display strings ("Champion", "Round of 16", etc.) for the post-state roster recap. The lookup uses `_BEST_FINISH_LABELS.get(finish_code, finish_code)` — fall back to the raw code, NOT to `'Group'`, so a future unmapped code surfaces as the bug it is rather than silently mislabeling a deep run as a group-stage exit.
- **Tournament `current_phase` ≠ `WorldCupMatch.stage`:** two different value spaces. `current_phase` is the *tournament-level* state code (`'pre_tournament'` / `'group_stage'` / `'knockout'` / `'completed'`), derived by `_derive_tournament_phase()` and rendered via inline `{% if %}/{% elif %}` (see `stats.html` phase chip and `home_shell.html`). `_stage_label` is **only** for `WorldCupMatch.stage` codes. Don't pipe `current_phase` through `_stage_label` (it has no entries for those keys and would silently fall back to "Group Stage").
- **Stats analytics layer:** `games/worldcup/services/stats.py` exposes 4 public functions (`get_country_stats`, `get_tier_stats`, `get_overview_kpis`, `get_tier_combos`) consumed by the public `/worldcup/stats` route. Public analytics routes must NOT use `@login_required`; build `my_picks` via `WorldCupPick.query.join(WorldCupTeam)` (never `enrollment.picks` — N+1).
- **Pre-deadline ownership privacy (D11):** `games/worldcup/services/team_detail.compute_team_ownership(team_id, deadline_passed=False)` returns `count=0, percent=0.0, picker_names=None` for **all viewers**, including the team's own picker. The `team_detail.html` ownership ribbon's count/percent block is correctly gated on `deadline_passed` only — do NOT add `or user_owns` to that inner guard, even though the outer ribbon-visibility branch does. A non-zero count visible to the owner pre-lock leaks roster info about a third party. Regression locks: `test_team_detail_user_owns_ribbon_pre_deadline` + `test_team_detail_ownership_hidden_pre_deadline`. Same pattern applies to any future ownership/roster-overlap UI: hide counts from everyone pre-deadline, not just non-owners.

### Production ops

- **Production environment selection:** `ENVIRONMENT=production` is set in three places as defense-in-depth — the server's `.env`, the systemd unit's `Environment=ENVIRONMENT=production` override, and every flask-command line in `deploy.sh` and the crontab. `migrations/env.py` reads the DB engine from `create_app()`'s loaded config, so a stray `ENVIRONMENT=development` would silently migrate against SQLite instead of Postgres. Keep all three layers in sync when adding new cron entries or deploy steps.
- **Postgres connection hygiene:** `ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 280}` — DO Managed Postgres closes idle connections; without this, long-lived Gunicorn workers throw `OperationalError` on first request after an idle gap. Do not remove.
- **Static asset cache-busting:** Every `<link>` or `<script>` referencing `/static/css/*` or `/static/js/*` in templates appends `?v={{ asset_version }}` (git short SHA, resolved at app boot in `core/context.py::_compute_asset_version`). Required because nginx serves `/static/` with `expires 30d; "public, immutable"` — without the cache-bust, Cloudflare's edge swallows post-deploy CSS/JS changes for up to 30 days (PR #18 fallout, fixed in PR #19). Images (favicons, brand-mark) skip the param (content-stable; rename the file to cache-bust if ever swapped). Locked by `tests/test_asset_versioning.py`. Debug recipe if you ever see post-deploy stale assets on cccfantasy.com: `curl -sI https://cccfantasy.com/static/css/style.css | grep -iE 'cf-cache-status|age'` — long `age` + `HIT` means an unversioned link slipped through; fix the template, don't reach for the CF purge button.

---

## Blueprint Pattern (required for all games)

- Blueprint in `games/<game>/` with `<game>_` table prefix on all models
- `<Game>Enrollment` model for game-specific user data, FK to shared `User`
- `@<game>_admin_required` decorator — two-tier: platform admin override first, then enrollment-scoped admin
- Templates extend `templates/base.html`, rendered under `<game>/` prefix
- Body class: game blueprints inject `body_class` via context processor (e.g., `'body_class': 'game-golf'`); platform/chrome templates can override via `{% block body_class %}<class>{% endblock %}` (e.g., `auth-page`). `base.html` resolves both via `<body class="{% block body_class %}{{ body_class|default('') }}{% endblock %}">`.
- Add a game switcher `<li class="nav-item">` to `<ul class="navbar-nav me-auto">` in `base.html`; also add a `{% elif request.blueprint == '<game>' %}` branch in the game sub-nav block (below `</nav>`) with `.game-subnav .subnav-<game>` div, game label, and pill links
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

Always use Flask-Migrate. Never raw SQL.

```bash
# After editing models:
FLASK_APP=app.py venv/bin/flask db migrate -m "descriptive message"
# Review the generated file in migrations/versions/
FLASK_APP=app.py venv/bin/flask db upgrade
# Commit the migration file with the model changes
```

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
admin_id = _make_admin_user(app)  # creates User with is_admin=True
with client.session_transaction() as sess:
    sess['_user_id'] = str(admin_id)
    sess['_fresh'] = True
resp = client.post('/worldcup/admin/...', data={...})
```

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
Pre-launch verification: `docs/production-launch-test-script.md` — full World Cup simulation on production (out → pre → live → post via SSH-edited deadline + admin match entry) then DB reset to a clean launch baseline. Run after Task 25 (cron) and before Task 26 (UptimeRobot).

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
SLASHGOLF_API_KEY=...    # SlashGolf API (Golf leaderboards)
EMAIL_ADDRESS=...        # Platform "from" address (send_platform_email)
EMAIL_PASSWORD=...       # SMTP app password
SMTP_SERVER=...          # Default: smtp.gmail.com
SMTP_PORT=...            # Default: 587
```
