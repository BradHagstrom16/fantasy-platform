# Architecture Decision Log — Fantasy Sports Platform

**Last Updated:** March 4, 2026  
**Status:** Active — Phase 0 complete, Phase 1 up next

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
| ADR-012 | Golf Pick 'Em virtualenv | Dual envs, Single env | **Single env: `/home/GolfPickEm/Golf_Pick_Em/venv`** | Removed unused `.virtualenvs/golfpickem`. Updated `.bashrc`, shell scripts, and `CLAUDE.md`. | 2026-03-04 | No |
| ADR-013 | UI/Design upgrade timing | Now (Phase 0), After Phase 1, After Phase 2 | **After Phase 1 (Golf blueprint ported)** | Designing placeholder pages is wasted effort. Wait until Golf's data surfaces (standings, tournaments, picks) are in the platform, then do one cohesive design pass across everything. | 2026-03-04 | Yes |

---

## Completed Work

### Pre-Phase 0 (March 4, 2026) ✅

| Task | Status | Notes |
|------|--------|-------|
| Full audit of all 5 games/apps | ✅ Done | Documented in PLATFORM_AUDIT_AND_ROADMAP.md |
| Consolidation assessment & architecture recommendation | ✅ Done | Modular monolith selected |
| Phased roadmap created | ✅ Done | 7 phases through Q2 2027 |
| Alembic added to CF Survivor | ✅ Done | Baseline migration generated and stamped |
| Alembic added to Golf Pick 'Em | ✅ Done | Baseline `aba1c0314b71` stamped on production |
| Golf Pick 'Em dual virtualenv cleanup | ✅ Done | Old env removed, .bashrc updated, shell scripts fixed |
| Golf Pick 'Em CLAUDE.md updated | ✅ Done | Correct paths, Alembic docs, deployment notes |

### Phase 0 (March 4, 2026) ✅

| Task | Status | Notes |
|------|--------|-------|
| Created `fantasy-platform` GitHub repo | ✅ Done | https://github.com/BradHagstrom16/fantasy-platform |
| App factory + extensions + config | ✅ Done | Modeled after CF Survivor's app factory pattern |
| Shared User model (`models/user.py`) | ✅ Done | Game-agnostic; game-specific data via FK |
| Alembic initialized with baseline migration | ✅ Done | `users` table created |
| Auth blueprint (login, register, logout, change password, profile) | ✅ Done | Ported from CF Survivor patterns |
| Main blueprint (home page with game cards) | ✅ Done | 3 "Coming Soon" game cards |
| Admin blueprint (dashboard, user management) | ✅ Done | Toggle admin, reset password |
| Base template (Bootstrap 5.3, navbar, footer) | ✅ Done | Mobile-responsive, dark navbar |
| Error pages (404, 500) | ✅ Done | Styled to match platform |
| WSGI entry point for PythonAnywhere | ✅ Done | `wsgi.py` |
| CLAUDE.md for the new repo | ✅ Done | Full architecture docs |
| Verified: all auth flows, admin, migrations working | ✅ Done | Brad confirmed |

---

## Timeline Summary

| Phase | Goal | Target Window | Status |
|-------|------|--------------|--------|
| Pre-0 | Alembic + tech debt cleanup on live apps | March 2026 | ✅ **Complete** |
| 0 | Scaffold new platform | March 2026 | ✅ **Complete** |
| 1 | Port Golf Pick 'Em blueprint (parallel, not live) | April–May 2026 | ⬜ **Up next** |
| — | UI/Design upgrade (full platform + golf surfaces) | After Phase 1 | ⬜ Planned |
| 2 | Port CFB Survivor blueprint + merge users | June–July 2026 | ⬜ Not started |
| — | **Golf season ends → cutover to unified platform** | **August 2026** | ⬜ |
| — | **CFB season starts on unified platform** | **September 1, 2026** | ⬜ |
| 3 | Build Major Fantasy blueprint (reusable for all 4 majors) | Oct–Nov 2026 | ⬜ Not started |
| 4 | Mobile-friendly UI overhaul | Dec 2026–Jan 2027 | ⬜ Not started |
| 5 | PostgreSQL + REST API + Railway/Render | Feb–Mar 2027 | ⬜ Not started |
| 6 | Olympics/World Cup event template | Q2 2027 | ⬜ Not started |

---

## Immediate Next Actions

1. ⬜ **Phase 1: Port Golf Pick 'Em blueprint into fantasy-platform**
   - Port models (Tournament, Player, TournamentField, TournamentResult, Pick, SeasonPlayerUsage)
   - Port routes under `/golf/` URL prefix
   - Port sync_api.py as `games/golf/services.py`
   - Port email reminders into shared notification system
   - Port all Golf templates into `games/golf/templates/golf/`
   - Recommend: break into 2-3 sub-tasks; use Opus for task generation
2. ⬜ Deploy platform skeleton to B1G Brad PA account
3. ⬜ UI/Design upgrade across entire platform (after Phase 1)

---

## Key Constraints

- Golf Pick 'Em stays live on GolfPickEm PA account through August 2026
- CFB Survivor must be live on new platform by September 1, 2026
- Masters 2026 runs on Google Sheets (web app deferred)
- Budget: ~$5/mo for hosting
- Task files (.md) are the preferred handoff format for Claude Code work
- Brad has UI upgrade `.md` files from both Golf and CFB redesigns — to be adapted for unified platform design pass after Phase 1
