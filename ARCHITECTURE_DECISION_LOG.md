# Architecture Decision Log — Fantasy Sports Platform

**Last Updated:** March 6, 2026
**Status:** Active — Phase 1 complete, Phase 2 planning

---

## Decisions

| # | Decision | Options Considered | Choice | Rationale | Date | Reversible? |
|---|----------|--------------------|--------|-----------|------|-------------|
| ADR-001 | Architecture pattern | Microservices, Monolith, Modular Monolith | **Modular Monolith** (Flask + Blueprints) | Right-sized for 20-30 users. Single deployment. Shared auth. Easy to add games. CFB already proves the pattern. | 2026-03-04 | Yes |
| ADR-002 | Starting point | Fresh repo, Fork CFB, Fork Golf | **Fresh repo** (`fantasy-platform`) | Clean architecture from day one. Both live apps keep running during build. Port code, don't inherit debt. | 2026-03-04 | N/A |
| ADR-003 | Framework | Flask, Django, FastAPI | **Flask** | Both apps already use it. Huge ecosystem. Django overkill. FastAPI lacks template rendering. | 2026-03-04 | Hard |
| ADR-004 | Database (Phase 1) | SQLite, PostgreSQL, MySQL | **SQLite** (for now) | Works at current scale. Upgrade to PostgreSQL in Phase 5. | 2026-03-04 | Yes |
| ADR-005 | Hosting (Phase 1) | PythonAnywhere, Railway, Render, VPS | **PythonAnywhere — reuse B1G Brad account** | Familiar workflow. Account already paid. Wipe and deploy fresh monolith there. GolfPickEm account stays live until Golf season ends in August. | 2026-03-04 | Yes |
| ADR-006 | Migration tooling | Manual SQL, Alembic, raw scripts | **Alembic (via Flask-Migrate)** | No-regret move. Added to both live apps and baked into new platform from day one. | 2026-03-04 | No |
| ADR-007 | Frontend (Phase 1) | Bootstrap + Jinja2, React SPA, HTMX | **Bootstrap 5.3 + Jinja2** | Works well. Mobile-friendly. No build step. Revisit for mobile app. | 2026-03-04 | Yes |
| ADR-008 | Golf Pick 'Em migration strategy | Mid-season cutover, Parallel build + off-season switch | **Parallel build + off-season switch** | Build golf blueprint in new platform during season. Keep GolfPickEm PA account live. Drop .db file after BMW Championship (Aug). Zero disruption to 19 active players. | 2026-03-04 | N/A |
| ADR-009 | Masters Fantasy 2026 | Build web app for April, Run on Sheets | **Google Sheets for 2026** | April 9 deadline is too close. Build a reusable "Major Fantasy" blueprint later for all 4 majors. Target late-2026 major or 2027 Masters for web debut. | 2026-03-04 | N/A |
| ADR-010 | User merge strategy | Merge by email, Separate accounts, Manual linking | **TBD — designed for merge-by-email** | Build shared User model with email as unique key. When migrating data, match on email. Different display names per game allowed via game-specific profile data. Full plan in Phase 2. | 2026-03-04 | Yes |
| ADR-011 | Domain name | Custom domain, PythonAnywhere subdomain | **TBD — revisit in Phase 1** | Start with PA subdomain. Brad to think about a custom domain name. ~$10-15/year when ready. | 2026-03-04 | Yes |
| ADR-012 | Golf Pick 'Em virtualenv | Dual envs, Single env | **Single env** | Removed unused `.virtualenvs/golfpickem`. | 2026-03-04 | No |
| ADR-013 | UI/Design upgrade timing | Now (Phase 0), After Phase 1, After Phase 2 | **After Phase 1 (Golf blueprint ported)** | Designing placeholder pages is wasted effort. Wait until Golf's data surfaces are in the platform. | 2026-03-04 | Yes |
| ADR-014 | Golf table naming | Original names, golf_ prefix | **golf_ prefix** (e.g., `golf_tournament`, `golf_pick`) | Avoids collision if future games share concepts like "tournament" or "player". Small cost, full protection. | 2026-03-06 | Hard |
| ADR-015 | Golf-specific user data | GolfPlayerProfile (1:1), GolfEnrollment (seasonal) | **GolfEnrollment** (keyed on user_id + season_year) | Naturally answers "who's playing golf?" and supports multi-season data. Pattern reusable for CFBEnrollment. | 2026-03-06 | Yes |
| ADR-016 | Email notifications | Shared service, Game-specific | **Game-specific for now** (golf in `games/golf/services/reminders.py`) | Premature to generalize without seeing CFB's needs. Refactor to shared service after Phase 2 when both implementations exist. | 2026-03-06 | Yes |
| ADR-017 | Handoff file improvements | Based on Phase 1 Claude Code feedback | **Incorporated for Phase 2** | See "Phase 1 Lessons Learned" section below. | 2026-03-06 | N/A |

---

## Completed Work

### Pre-Phase 0 (March 4, 2026) ✅

| Task | Status | Notes |
|------|--------|-------|
| Full audit of all 5 games/apps | ✅ Done | Documented in PLATFORM_AUDIT_AND_ROADMAP.md |
| Consolidation assessment & architecture recommendation | ✅ Done | Modular monolith selected |
| Phased roadmap created | ✅ Done | 7 phases through Q2 2027 |
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

---

## Phase 1 Lessons Learned (from Claude Code feedback)

These improvements will be applied to all Phase 2+ task files:

| # | Issue | Fix for Phase 2 |
|---|-------|-----------------|
| 1 | Smoke tests assumed tables exist in in-memory SQLite | All test snippets must include `db.create_all()` setup inside `app.app_context()` |
| 2 | Auth routes have no URL prefix (`/login`, not `/auth/login`) | Use correct raw URL paths in curl/test snippets; `url_for('auth.login')` in templates is fine |
| 3 | Source files referenced but not available in repo | Embed ALL critical logic directly in the task file; don't reference external files Claude Code can't access |
| 4 | `before_request` DB query pattern not documented | Document the pattern in task file context so CFB can follow the same approach |

---

## Phase 2 Planning — CFB Survivor Pool

### Established Patterns (from Phase 1)

These patterns are now proven and should be followed exactly:

- Blueprint in `games/cfb/` with `cfb_` table prefix
- `CfbEnrollment` model for game-specific user data (lives, cumulative_spread, is_eliminated, has_paid)
- `@cfb_admin_required` decorator in routes.py
- Templates extend `templates/base.html`, render as `cfb/` prefix
- Games dropdown in `base.html` gets another `<li>` entry
- Game-specific `before_request` hook for auto-refresh (CFB: deadline-based, not tournament-based)
- CLI commands under `flask cfb *` namespace
- Context processor on the cfb blueprint for game-specific template vars
- Services layer for API integration (The Odds API, not SlashGolf)

### Key Differences from Golf

| Aspect | Golf | CFB |
|--------|------|-----|
| Season structure | 32 named tournaments | ~17 weeks (regular + playoffs) |
| Pick model | Primary + backup per tournament | One team per week |
| Elimination | None — cumulative scoring | 2-life system with spread tiebreaker |
| Player reuse | Each golfer once per season | Each team once per regular season (resets for playoffs) |
| External API | SlashGolf (RapidAPI) | The Odds API (spreads + scores) |
| Status model | Tournament: upcoming/active/complete | Week: future/active/locked/complete |
| Special rules | Majors 1.5x, team events ÷2 | 16-pt spread cap, auto-picks, CFP revival rule |
| Admin workflow | Tournament + field management | Week + game creation, result marking |

### CFB Source Structure (already has blueprints!)

The CFB Survivor app already uses app factory + blueprints, making the port cleaner than Golf was:
- `routes/main.py` → `games/cfb/routes.py`
- `routes/admin.py` → admin routes in `games/cfb/routes.py`
- `routes/auth.py` → skip (shared platform auth handles this)
- `models.py` → `games/cfb/models.py` (User fields → CfbEnrollment)
- `services/game_logic.py` → `games/cfb/services/game_logic.py`
- `services/automation.py` → `games/cfb/services/automation.py`
- `services/score_fetcher.py` → `games/cfb/services/score_fetcher.py`
- `constants.py` + `fbs_master_teams.py` → `games/cfb/constants.py`
- `timezone_utils.py` → shared or `games/cfb/utils.py`
- `display_utils.py` → `games/cfb/utils.py` (week display names, CFP helpers)

---

## Timeline Summary

| Phase | Goal | Target Window | Status |
|-------|------|--------------|--------|
| Pre-0 | Alembic + tech debt cleanup on live apps | March 2026 | ✅ **Complete** |
| 0 | Scaffold new platform | March 2026 | ✅ **Complete** |
| 1 | Port Golf Pick 'Em blueprint | March 2026 | ✅ **Complete** |
| — | UI/Design upgrade (full platform + golf surfaces) | April 2026 | ⬜ **Up next** |
| 2 | Port CFB Survivor blueprint + user merge | June–July 2026 | ⬜ Planned |
| — | **Golf season ends → cutover to unified platform** | **August 2026** | ⬜ |
| — | **CFB season starts on unified platform** | **September 1, 2026** | ⬜ |
| 3 | Build Major Fantasy blueprint | Oct–Nov 2026 | ⬜ Not started |
| 4 | Mobile-friendly UI overhaul | Dec 2026–Jan 2027 | ⬜ Not started |
| 5 | PostgreSQL + REST API + Railway/Render | Feb–Mar 2027 | ⬜ Not started |
| 6 | Olympics/World Cup event template | Q2 2027 | ⬜ Not started |

---

## Immediate Next Actions

1. ⬜ **UI/Design upgrade** — One cohesive design pass across platform + golf surfaces (Brad has existing UI upgrade .md files to adapt)
2. ⬜ **Deploy platform to B1G Brad PA account** — Currently local only
3. ⬜ **Phase 2: Port CFB Survivor Pool** — June-July 2026 timeline

---

## Key Constraints

- Golf Pick 'Em stays live on GolfPickEm PA account through August 2026
- CFB Survivor must be live on new platform by September 1, 2026
- Masters 2026 runs on Google Sheets (web app deferred)
- Budget: ~$5/mo for hosting
- Task files (.md) are the preferred handoff format for Claude Code work