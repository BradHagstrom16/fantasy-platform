# Architecture Decision Log — Fantasy Sports Platform

**Last Updated:** March 18, 2026
**Status:** Active — Phases 0–3 complete; Phase 4 (World Cup Fantasy) in design

---

## Decisions

| # | Decision | Options Considered | Choice | Rationale | Date | Reversible? |
|---|----------|--------------------|--------|-----------|------|-------------|
| ADR-001 | Architecture pattern | Microservices, Monolith, Modular Monolith | **Modular Monolith** (Flask + Blueprints) | Right-sized for 20-30 users. Single deployment. Shared auth. Easy to add games. CFB already proves the pattern. | 2026-03-04 | Yes |
| ADR-002 | Starting point | Fresh repo, Fork CFB, Fork Golf | **Fresh repo** (`fantasy-platform`) | Clean architecture from day one. Both live apps keep running during build. Port code, don't inherit debt. | 2026-03-04 | N/A |
| ADR-003 | Framework | Flask, Django, FastAPI | **Flask** | Both apps already use it. Huge ecosystem. Django overkill. FastAPI lacks template rendering. | 2026-03-04 | Hard |
| ADR-004 | Database (Phase 1) | SQLite, PostgreSQL, MySQL | **SQLite** (for now) | Works at current scale. Upgrade to PostgreSQL in a future phase. | 2026-03-04 | Yes |
| ADR-005 | Hosting (Phase 1) | PythonAnywhere, Railway, Render, VPS | **PythonAnywhere — reuse B1G Brad account** | Familiar workflow. Account already paid. Wipe and deploy fresh monolith there. GolfPickEm account stays live until Golf season ends in August. | 2026-03-04 | Yes |
| ADR-006 | Migration tooling | Manual SQL, Alembic, raw scripts | **Alembic (via Flask-Migrate)** | No-regret move. Added to both live apps and baked into new platform from day one. | 2026-03-04 | No |
| ADR-007 | Frontend (Phase 1) | Bootstrap + Jinja2, React SPA, HTMX | **Bootstrap 5.3 + Jinja2** | Works well. Mobile-friendly. No build step. Revisit for mobile app. | 2026-03-04 | Yes |
| ADR-008 | Golf Pick 'Em migration strategy | Mid-season cutover, Parallel build + off-season switch | **Parallel build + off-season switch** | Build golf blueprint in new platform during season. Keep GolfPickEm PA account live. Drop .db file after BMW Championship (Aug). Zero disruption to 19 active players. | 2026-03-04 | N/A |
| ADR-009 | Masters Fantasy 2026 | Build web app for April, Run on Sheets | **Google Sheets for 2026** | April 9 deadline is too close. Build a reusable "Major Fantasy" blueprint later for all 4 majors. Target late-2026 major or 2027 Masters for web debut. | 2026-03-04 | N/A |
| ADR-010 | User merge strategy | Merge by email, Separate accounts, Manual linking | **TBD — designed for merge-by-email** | Build shared User model with email as unique key. When migrating data, match on email. Different display names per game allowed via game-specific profile data. Full plan deferred until go-live phase. | 2026-03-04 | Yes |
| ADR-011 | Domain name | Custom domain, PythonAnywhere subdomain | **TBD — revisit at go-live** | Start with PA subdomain. Brad to decide on a custom domain name. ~$10-15/year when ready. | 2026-03-04 | Yes |
| ADR-012 | Golf Pick 'Em virtualenv | Dual envs, Single env | **Single env** | Removed unused `.virtualenvs/golfpickem`. | 2026-03-04 | No |
| ADR-013 | UI/Design upgrade timing | Now (Phase 0), After Phase 1, After Phase 2 | **After Phase 2 (both games ported)** | Designing against one game's templates produces worse decisions than designing with full context of both games present. | 2026-03-04 | Yes |
| ADR-014 | Golf table naming | Original names, golf_ prefix | **golf_ prefix** (e.g., `golf_tournament`, `golf_pick`) | Avoids collision if future games share concepts like "tournament" or "player". Small cost, full protection. | 2026-03-06 | Hard |
| ADR-015 | Golf-specific user data | GolfPlayerProfile (1:1), GolfEnrollment (seasonal) | **GolfEnrollment** (keyed on user_id + season_year) | Naturally answers "who's playing golf?" and supports multi-season data. Pattern reusable for CFBEnrollment. | 2026-03-06 | Yes |
| ADR-016 | Email notifications | Shared service, Game-specific | **Game-specific for now** (golf in `games/golf/services/reminders.py`) | Premature to generalize without seeing CFB's needs. Refactor to shared service after Phase 2 when both implementations exist. | 2026-03-06 | Yes |
| ADR-017 | Handoff file improvements | Based on Phase 1 Claude Code feedback | **Incorporated for Phase 2** | See "Phase 1 Lessons Learned" section below. | 2026-03-06 | N/A |
| ADR-018 | CFB admin authorization | Use platform `User.is_admin`, Use `CfbEnrollment.is_admin` | **`CfbEnrollment.is_admin`** | Game-level admin is separate from platform admin. CFB admins manage their pool; platform admins manage users. Password reset scoped to enrolled users only. | 2026-03-08 | Yes |
| ADR-019 | CFB state-changing routes | GET links, POST forms | **POST with CSRF** | All state-mutating operations (autopicks, score apply, results) use POST with CSRF tokens. GET only for read-only pages. Consistent with OWASP best practices. | 2026-03-08 | No |
| ADR-020 | CFB spread cap enforcement | UI-only filtering, Server + UI | **Server + UI with matching thresholds** | POST validation and GET display use identical `> -16.5` threshold. Null-spread teams rejected by POST and hidden in UI. No gap for crafted form submissions. | 2026-03-08 | Yes |
| ADR-021 | Mobile UI overhaul timing | Phase 3b (dedicated pass), Baked into Phase 3a | **Baked into Phase 3a** | Phase 3a handoff files included comprehensive mobile directives (dual-render tables, 44px touch targets, no horizontal scroll, card-based pick submission). Treated as complete. Dedicated mobile polish deferred indefinitely — revisit if user feedback surfaces specific issues. | 2026-03-18 | Yes |
| ADR-022 | Platform go-live trigger | After Golf/CFB polish, After World Cup game build | **World Cup Fantasy game as go-live target** | Rather than deploying Golf + CFB to PA and migrating users twice, build the World Cup game first, deploy everything together, and use the 2026 World Cup (June–July) as the platform launch event. Gives a clean go-live moment with a new game none of Brad's users have played before. | 2026-03-18 | Yes |
| ADR-023 | World Cup Fantasy game design | Design inline with build, Design-first in separate session | **Design-first in a dedicated game design chat** | Game mechanics must be locked before a handoff file can be written. A separate chat avoids mixing exploratory game design with implementation context. Game spec produced there becomes input to the Phase 4 implementation chat. | 2026-03-18 | N/A |
| ADR-024 | World Cup score storage | Separate TeamResult/Score tables, Denormalized on team + pick | **Denormalized on team + pick (4 tables, not 6)** | 48 teams and ≤50 players. Separate TeamResult and Score tables add complexity without performance benefit. Every number rebuildable via `flask worldcup recalc`. | 2026-04-03 | Yes |
| ADR-025 | World Cup match pre-seeding | Create matches as played, All 104 matches seeded at init | **All 104 matches seeded at init, knockouts as shells** | Reduces admin work during tournament. Admin enters scores for existing records instead of creating each match. Knockout teams filled in as bracket resolves. | 2026-04-03 | Yes |
| ADR-026 | World Cup leaderboard access | Login required, Public | **Public (no login required)** | Doubles as marketing — players share link with friends. Enrollment required only for pick submission. | 2026-04-03 | Yes |
| ADR-027 | World Cup admin scoping | Platform admin, Enrollment-scoped | **Enrollment-scoped (CFB pattern)** | `WorldCupEnrollment.is_admin`, not `User.is_admin`. Consistent with CFB and the platform's game admin ≠ platform admin principle. | 2026-04-03 | Yes |

---

## Completed Work

### Pre-Phase 0 (March 4, 2026) ✅

| Task | Status | Notes |
|------|--------|-------|
| Full audit of all 5 games/apps | ✅ Done | Documented in PLATFORM_AUDIT_AND_ROADMAP.md |
| Consolidation assessment & architecture recommendation | ✅ Done | Modular monolith selected |
| Phased roadmap created | ✅ Done | Phases defined through Q2 2027 |
| Alembic added to CF Survivor | ✅ Done | Baseline migration generated and stamped |
| Alembic added to Golf Pick 'Em | ✅ Done | Baseline stamped on production |
| Golf Pick 'Em dual virtualenv cleanup | ✅ Done | Old env removed |
| Golf Pick 'Em CLAUDE.md updated | ✅ Done | Correct paths, Alembic docs |

### Phase 0 — Platform Scaffold (March 5, 2026) ✅

| Task | Status | Notes |
|------|--------|-------|
| App factory + extensions + config | ✅ Done | `create_app()` in `app.py` |
| Shared User model | ✅ Done | `models/user.py`, table: `users` |
| Alembic baseline migration | ✅ Done | `a6bd9748bf4d` |
| Auth blueprint | ✅ Done | Login, register, logout, change password, profile |
| Main + Admin blueprints | ✅ Done | Home page, user management |
| Base template + error pages | ✅ Done | Bootstrap 5.3, Barlow Condensed |
| WSGI entry point | ✅ Done | `wsgi.py` |

### Phase 1 — Golf Pick 'Em Blueprint (March 5-6, 2026) ✅

| Sub-task | Status | Commit | Key Files |
|----------|--------|--------|-----------|
| **1A: Models + Migration** | ✅ Done | `9744be4c108a` | `games/golf/models.py` (7 models), `games/golf/utils.py`, migration |
| **1B: Services + CLI** | ✅ Done | `ced489d` | `games/golf/services/sync.py`, `reminders.py`, `cli.py`, `constants.py` |
| **1C: Routes + Templates** | ✅ Done | (latest) | `games/golf/routes.py` (~15 routes), 12 template files, nav link |

**Phase 1 delivers:** Complete Golf Pick 'Em as a blueprint under `/golf/` with standings, schedule, pick submission, tournament detail, admin dashboard, payments, override picks, API sync CLI, and email reminders.

### Phase 2 — CFB Survivor Pool Blueprint (March 7-8, 2026) ✅

| Sub-task | Status | Commit | Key Files |
|----------|--------|--------|-----------|
| **2A: Models + Constants + Utils + Migration** | ✅ Done | `42f0ac5` | `games/cfb/models.py` (5 models), `constants.py`, `utils.py`, migration |
| **2B: Services + CLI + Config** | ✅ Done | `a09d354` | `services/game_logic.py`, `score_fetcher.py`, `automation.py`, `reminders.py`, `cli.py` |
| **2C: Routes + Templates + Nav** | ✅ Done | `da301fb` | `routes.py` (~20 routes), 13 templates, `base.html` nav integration |

**Phase 2 delivers:** Complete CFB Survivor Pool as a blueprint under `/cfb/` with standings, weekly pick submission, results tracking, 2-life elimination system, cumulative spread tiebreaker, team usage tracking (with CFP reset), admin dashboard, week/game management, score fetching via The Odds API, auto-picks, payment tracking, team management, and CLI automation.

### Phase 3 — UI/Design Upgrade (March 11-18, 2026) ✅

| Sub-task | Status | Key Files |
|----------|--------|-----------|
| **3a: Platform foundation + all game surfaces + HTML emails** | ✅ Done | `static/css/style.css`, `templates/base.html`, all Golf + CFB templates, email infrastructure |
| **3b: Mobile-friendly UI** | ✅ Done | Mobile directives baked into Phase 3a handoff files — dual-render tables, 44px touch targets, card-based pick submission, no horizontal scroll (see ADR-021) |

**Phase 3 delivers:** "The Commissioner's Club" design system — platform purple/gold identity with game-specific palettes (Golf: Augusta green/gold, CFB: Badger crimson/midnight). CSS custom properties with `body.game-<game>` auto-theming. Gmail-compatible HTML emails with game-branded wrappers for both games. Weekly Results Recap emails for both games. All templates restyled. Mobile-first responsive layout throughout.

---

## Timeline Summary

| Phase | Goal | Target Window | Status |
|-------|------|--------------|--------|
| Pre-0 | Alembic + tech debt cleanup on live apps | March 2026 | ✅ **Complete** |
| 0 | Scaffold platform | March 2026 | ✅ **Complete** |
| 1 | Port Golf Pick 'Em blueprint | March 2026 | ✅ **Complete** |
| 2 | Port CFB Survivor blueprint | March 2026 | ✅ **Complete** |
| 3 | UI/Design upgrade + mobile | March 2026 | ✅ **Complete** |
| 4 | Design + build World Cup Fantasy game | April–May 2026 | 🔄 **In progress — 4A foundation** |
| 5 | Go live on PythonAnywhere — World Cup launch | June 2026 | ⬜ Not started |
| 6 | Golf cutover to unified platform | August 2026 | ⬜ Not started |
| 7 | CFB Survivor on unified platform | September 1, 2026 | ⬜ Not started |
| 8 | Masters Fantasy blueprint | Oct–Nov 2026 | ⬜ Not started |
| 9 | PostgreSQL + REST API + Railway/Render | Feb–Mar 2027 | ⬜ Not started |
| 10 | Olympics/World Cup event template (reusable) | Q2 2027 | ⬜ Not started |

| — | **Golf season ends → cutover to unified platform** | **August 2026** | ⬜ |
| — | **CFB season starts on unified platform** | **September 1, 2026** | ⬜ |
| — | **2026 FIFA World Cup** | **June 11 – July 19, 2026** | ⬜ |

---

## Immediate Next Actions

1. ✅ ~~UI/Design upgrade~~ — Complete (Phase 3)
2. 🔄 **Design World Cup Fantasy game** — Game mechanics, scoring, tiers, pick rules, admin workflow. Run in a dedicated game design chat; output is a complete game spec.
3. ⬜ **Build World Cup Fantasy blueprint** — New implementation chat, takes game spec as input. Follows established blueprint pattern.
4. ⬜ **End-to-end local testing** — All three games working together before any PA deployment.
5. ⬜ **Go live on PythonAnywhere** — Deploy unified platform to B1G Brad PA account. World Cup as launch event.
6. ⬜ **User onboarding** — New user registration flow. User merge strategy (ADR-010) for Golf/CFB players who join the platform.

---

## Key Constraints

- Golf Pick 'Em stays live on GolfPickEm PA account through August 2026
- CFB Survivor must be live on unified platform by September 1, 2026
- 2026 World Cup runs June 11 – July 19 — platform must be live before June 11
- Masters 2026 runs on Google Sheets (web app deferred)
- Handoff files (`.md`) are the preferred format for Claude Code work
- No JavaScript build step — vanilla JS or CDN-loaded libraries only
- Bootstrap 5.3 CDN stays

---

## Phase 3 Lessons Learned

| # | Issue | Lesson |
|---|-------|--------|
| 1 | Mobile directives embedded in design handoff vs. separate phase | Mobile-first directives baked directly into game template handoffs are more effective than a separate mobile pass — the context is already there when the template is being written |
| 2 | Design after all games are ported | Designing against one game's templates produces worse decisions than designing with full context of both games present (confirmed ADR-013) |

---

## Phase 2 Lessons Learned

| # | Issue | Lesson |
|---|-------|--------|
| 1 | Spread cap threshold mismatch between GET display and POST validation | Always use identical thresholds in UI filtering and server-side validation — test both paths |
| 2 | GET routes for state-changing operations (autopicks) | All state-mutating operations must be POST with CSRF, even behind admin auth — no exceptions |
| 3 | Game-level admin could reset any platform user's password | Scope game-admin actions to game-enrolled users only — game admin ≠ platform admin |
| 4 | `is_complete` committed before `process_week_results` — orphan on failure | Let the processing function own the completion flag — don't commit it prematurely |

---

## Phase 1 Lessons Learned

| # | Issue | Fix Applied in Phase 2+ |
|---|-------|-----------------|
| 1 | Smoke tests assumed tables exist in in-memory SQLite | All test snippets include `db.create_all()` inside `ENVIRONMENT=testing` context |
| 2 | Auth routes have no URL prefix | Explicitly documented in all handoff files — login is at `/login`, not `/auth/login` |
| 3 | Cross-game patterns (before_request hooks) not documented | Document in handoff context block so future games follow the same approach |
| 4 | Handoff files referenced source code inline | All source files staged in `_migration_source/` and referenced by path |
