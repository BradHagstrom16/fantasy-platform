# Architecture Decision Log — Fantasy Sports Platform

**Last Updated:** March 4, 2026  
**Status:** Active — Pre-Phase 0 complete, ready for Phase 0

---

## Decisions

| # | Decision | Options Considered | Choice | Rationale | Date | Reversible? |
|---|----------|--------------------|--------|-----------|------|-------------|
| ADR-001 | Architecture pattern | Microservices, Monolith, Modular Monolith | **Modular Monolith** (Flask + Blueprints) | Right-sized for 20-30 users. Single deployment. Shared auth. Easy to add games. CFB already proves the pattern. | 2026-03-04 | Yes |
| ADR-002 | Starting point | Fresh repo, Fork CFB, Fork Golf | **Fresh repo** (`fantasy-platform`) | Clean architecture from day one. Both live apps keep running during build. Port code, don't inherit debt. | 2026-03-04 | N/A |
| ADR-003 | Framework | Flask, Django, FastAPI | **Flask** | Both apps already use it. Huge ecosystem. Django overkill. FastAPI lacks template rendering. | 2026-03-04 | Hard |
| ADR-004 | Database (Phase 1) | SQLite, PostgreSQL, MySQL | **SQLite** (for now) | Works at current scale. Upgrade to PostgreSQL in Phase 5. | 2026-03-04 | Yes |
| ADR-005 | Hosting (Phase 1) | PythonAnywhere, Railway, Render, VPS | **PythonAnywhere — reuse B1G Brad account** | Familiar workflow. Account already paid. Wipe and deploy fresh monolith there. Second account (GolfPickEm) stays live until Golf season ends. | 2026-03-04 | Yes |
| ADR-006 | Migration tooling | Manual SQL, Alembic, raw scripts | **Alembic (via Flask-Migrate)** | No-regret move. Immediate action: add to both live apps first, then bake into new platform from day one. | 2026-03-04 | No |
| ADR-007 | Frontend (Phase 1) | Bootstrap + Jinja2, React SPA, HTMX | **Bootstrap 5.3 + Jinja2** | Works well. Mobile-friendly. No build step. Revisit for mobile app. | 2026-03-04 | Yes |
| ADR-008 | Golf Pick 'Em migration strategy | Mid-season cutover, Parallel build + off-season switch | **Parallel build + off-season switch** | Build golf blueprint in new platform during season. Keep GolfPickEm PA account live. Drop .db file after BMW Championship (Aug). Zero disruption to 19 active players. | 2026-03-04 | N/A |
| ADR-009 | Masters Fantasy 2026 | Build web app for April, Run on Sheets | **Google Sheets for 2026** | April 9 deadline is too close. Build a reusable "Major Fantasy" blueprint later for all 4 majors. Target late-2026 major or 2027 Masters for web debut. | 2026-03-04 | N/A |
| ADR-010 | User merge strategy | Merge by email, Separate accounts, Manual linking | **TBD — designed for merge-by-email** | Build shared User model with email as the unique key. When migrating data, match on email. Different display names per game allowed via game-specific profile data. Full plan to be designed in Phase 2. | 2026-03-04 | Yes |
| ADR-011 | Domain name | Custom domain, PythonAnywhere subdomain | **TBD — revisit in Phase 1** | Start with PA subdomain. Brad to think about a custom domain name. ~$10-15/year when ready. | 2026-03-04 | Yes |
| ADR-012 | Golf Pick 'Em virtualenv | Dual envs (.virtualenvs/golfpickem + venv/), Single env | **Single env: `/home/GolfPickEm/Golf_Pick_Em/venv`** | Removed unused `.virtualenvs/golfpickem` to eliminate confusion. Updated `.bashrc` to auto-activate correct env. Updated `run_sync.sh`, `run_reminders.sh`, and `CLAUDE.md` with correct paths. | 2026-03-04 | No |

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
| Architecture Decision Log created | ✅ Done | This document |

---

## Timeline Summary

| Phase | Goal | Target Window | Status |
|-------|------|--------------|--------|
| Pre-0 | Add Alembic to both live apps, clean up tech debt | March 2026 | ✅ **Complete** |
| 0 | Scaffold new platform (fresh repo, shared models, auth) | March 2026 | ⬜ **Up next** |
| 1 | Build Golf Pick 'Em blueprint (parallel, not live) | April–May 2026 | ⬜ Not started |
| 2 | Build CFB Survivor blueprint + merge users | June–July 2026 | ⬜ Not started |
| — | **Golf season ends → cutover to unified platform** | **August 2026** | ⬜ |
| — | **CFB season starts on unified platform** | **September 1, 2026** | ⬜ |
| 3 | Build Major Fantasy blueprint (reusable for all 4 majors) | Oct–Nov 2026 | ⬜ Not started |
| 4 | Mobile-friendly UI overhaul | Dec 2026–Jan 2027 | ⬜ Not started |
| 5 | PostgreSQL migration + REST API + Railway/Render | Feb–Mar 2027 | ⬜ Not started |
| 6 | Olympics/World Cup event template | Q2 2027 | ⬜ Not started |

---

## Immediate Next Actions

1. ⬜ Create `fantasy-platform` GitHub repo
2. ⬜ Scaffold Phase 0 (app factory, extensions, shared User model, Alembic, auth blueprint, base templates)
3. ⬜ Deploy skeleton to B1G Brad PA account (wipe and replace)

---

## Key Constraints

- Golf Pick 'Em stays live on GolfPickEm PA account through August 2026
- CFB Survivor must be live on new platform by September 1, 2026
- Masters 2026 runs on Google Sheets (web app deferred)
- Budget: ~$5/mo for hosting
- Task files (.md) are the preferred handoff format for Claude Code work
