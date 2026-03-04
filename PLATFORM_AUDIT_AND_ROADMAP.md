# Fantasy Sports Platform — Technical Audit & Consolidation Roadmap

**Date:** March 4, 2026  
**Author:** Claude (Technical Co-Pilot)  
**Status:** Initial Assessment — Ready for Review

---

## STEP 1 — AUDIT OF EXISTING APPS

### App 1: Golf Pick 'Em (LIVE — Primary)

**URL:** https://golfpickem.pythonanywhere.com/  
**Repo:** https://github.com/BradHagstrom16/Golf_Pick_Em  
**Account:** GolfPickEm @ PythonAnywhere  
**Status:** Active, mid-season (7 of 32 tournaments complete, 19 players)

#### Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.x |
| Framework | Flask (single-file app, NO blueprints) |
| Database | SQLite (`golf_pickem.db`) |
| ORM | SQLAlchemy 2.0+ via Flask-SQLAlchemy |
| Auth | Flask-Login + Werkzeug password hashing |
| Forms/Security | Flask-WTF (CSRF), Flask-Limiter (rate limiting) |
| Frontend | Jinja2 templates + Bootstrap 5 + Tom Select (dropdowns) |
| External API | SlashGolf (via RapidAPI) — schedule, fields, leaderboard, earnings |
| Email | Gmail SMTP for pick reminders (send_reminders.py) |
| Hosting | PythonAnywhere (free/paid tier) |

#### Core Features Working

- User registration/login with password hashing
- Season-long standings with cumulative prize money and score-to-par tracking
- Per-tournament pick submission (primary + backup golfer)
- Backup activation logic (WD before/after R2)
- Each golfer single-use per season (SeasonPlayerUsage tracking)
- Real-time tournament field sync from SlashGolf API
- Automated tournament status transitions (upcoming → active → complete)
- Admin dashboard (tournament management, user management, payment tracking)
- Scheduled CLI tasks for data sync (schedule, field, live, results, earnings)
- Email reminders (24h, 12h, 1h before deadline)
- Majors 1.5x multiplier, team event earnings/2

#### Authentication

- Flask-Login with `@login_required` decorator
- Werkzeug `generate_password_hash` / `check_password_hash`
- Login rate-limited to 10/min via Flask-Limiter
- Open redirect prevention on login `next` param
- CSRF on all forms via Flask-WTF
- No OAuth/social login
- No email verification on registration
- No password reset flow

#### Data Storage

- SQLite single file (`golf_pickem.db`)
- Models: User, Player, Tournament, TournamentField, TournamentResult, Pick, SeasonPlayerUsage
- No migrations tool (no Alembic) — manual schema management
- Pick deadlines stored as naive datetimes in CT timezone

#### Technical Debt & Issues

1. **No blueprints** — all routes in single `app.py` (~500+ lines). Hard to maintain.
2. **No migration system** — schema changes require manual SQL. Risky for production.
3. **No test suite** — zero tests, zero linter. Changes are deployed blind.
4. **SQLite in production** — works fine at 19 users but doesn't support concurrent writes well. Not a problem today but will be when consolidating.
5. **Naive datetime storage** — deadlines stored without timezone info in SQLite. Works because the app is consistent, but fragile.
6. **No password reset** — users must contact admin to reset passwords.
7. **No email verification** — anyone can register with a fake email.
8. **API key management** — relies on env vars and a gitignored shell script. Fine for now.

---

### App 2: CFB Survivor Pool (LIVE — Seasonal)

**URL:** https://b1gbrad.pythonanywhere.com/  
**Repo:** https://github.com/BradHagstrom16/CF_Survivor  
**Account:** b1gbrad @ PythonAnywhere  
**Status:** Season complete (2024-25 finished, champion crowned: "Fourth & Pine")

#### Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.13 |
| Framework | Flask 3.1 with **Blueprints** |
| Database | SQLite (`instance/picks.db`) |
| ORM | SQLAlchemy 2.0+ via Flask-SQLAlchemy |
| Auth | Flask-Login + Werkzeug |
| Forms/Security | Flask-WTF (CSRF), Flask-Limiter |
| Frontend | Jinja2 templates + Bootstrap 5.3 |
| External API | The Odds API — game spreads and championship odds |
| Email | Gmail SMTP for reminders |
| Hosting | PythonAnywhere |

#### Core Features Working

- User registration/login
- Weekly pick submission (one team per week)
- 2-life elimination system with cumulative spread tiebreaker
- 16-point spread cap on eligible teams
- Auto-pick system (missed deadline → biggest available favorite)
- Full College Football Playoff support (team reset, revival rule, CFP elimination tracking)
- Admin dashboard (week creation, game management, result marking, user management)
- Automated CLI tasks (`cfb-sync` with modes: setup, spreads, scores, autopick, remind, status)
- End-of-season champion display page
- Payment tracking

#### Authentication

- Same pattern as Golf Pick 'Em: Flask-Login + Werkzeug
- Login rate-limited
- CSRF protection
- No OAuth, no email verification, no password reset

#### Data Storage

- SQLite (`instance/picks.db`)
- Models: User, Team, Week, Game, Pick
- `db_maintenance.py` for schema migrations (raw SQL, no Alembic) — idempotent column additions
- Conference data in `fbs_master_teams.py` / `constants.py`

#### Technical Debt & Issues

1. **Better structured than Golf** — uses app factory pattern (`create_app()`) and blueprints (auth, main, admin). This is the more mature codebase.
2. **No migration system** — same as Golf, but `db_maintenance.py` with `ensure_*_column()` helpers is a reasonable workaround.
3. **No test suite** — same problem.
4. **SQLite in production** — same situation.
5. **Password stored as `password` column** — field name is `password` not `password_hash`. Functionally identical (still hashed), but inconsistent naming with Golf app.
6. **Seasonal usage** — only runs Aug–Jan. Sits idle for 7 months.
7. **`datetime.utcnow()`** — Olympics model still uses deprecated `datetime.utcnow()` (Golf app has been updated to `datetime.now(timezone.utc)`).

---

### App 3: Winter Olympics Fantasy Pool (COMPLETED)

**Repo:** Part of Masters_Fantasy repo / standalone  
**Status:** Completed event (Feb 6–22, 2026). Excel/Google Sheets based.

#### Tech Stack

- Google Forms for pick collection
- Excel workbook (10 sheets) with formulas for scoring
- Google Sheets for distribution (view-only to players)
- Wikipedia for medal data (manual import)
- Also has a Flask web app version (same stack as Golf/CFB)

#### Key Observations

- Fully functional as a web app AND as a spreadsheet
- Tier-based country selection (6 tiers, 8 picks)
- Medal points × tier multiplier scoring
- The Flask version follows the Golf Pick 'Em pattern (single app.py, no blueprints)
- Shares identical auth pattern (Flask-Login + Werkzeug)

---

### App 4: Masters Fantasy (IN DEVELOPMENT)

**Repo:** https://github.com/BradHagstrom16/Masters_Fantasy  
**Status:** Specification locked (v2.0, Feb 25, 2026). Google Sheets build phase.

#### Key Details

- 10 golfers across 6 tiers (based on betting odds)
- Scoring: actual strokes to par + finish bonuses − missed cut penalties
- Lowest total wins (like real golf)
- Tiebreaker: predicted winning score
- Currently planned as Google Forms → Google Sheets
- Specification mentions future automated scoring via PythonAnywhere/Golf_Pick_Em API
- 200K Monte Carlo simulations validating the tier structure

#### Important Note for Consolidation

The Masters spec explicitly calls out integration with the Golf Pick 'Em infrastructure for live scoring. This is a natural first candidate for the unified platform.

---

### App 5: World Cup Fantasy (PLANNED)

**Status:** Concept only, modeled on Olympics structure  
No repo, no spec yet. Will follow the tier-based pick + multiplier pattern.

---

## STEP 2 — CONSOLIDATION ASSESSMENT

### 2.1 How Similar Are the Two Flask Apps?

**Very similar.** Here's the overlap:

| Feature | Golf Pick 'Em | CFB Survivor | Shared? |
|---------|--------------|--------------|---------|
| Framework | Flask | Flask | ✅ |
| Database | SQLite + SQLAlchemy | SQLite + SQLAlchemy | ✅ |
| Auth system | Flask-Login + Werkzeug | Flask-Login + Werkzeug | ✅ |
| CSRF | Flask-WTF | Flask-WTF | ✅ |
| Rate limiting | Flask-Limiter | Flask-Limiter | ✅ |
| Frontend | Bootstrap 5 + Jinja2 | Bootstrap 5.3 + Jinja2 | ✅ |
| Email | Gmail SMTP | Gmail SMTP | ✅ |
| User model | id, username, email, password_hash, display_name, is_admin, has_paid | Same fields + lives_remaining, is_eliminated, cumulative_spread | ✅ (core) |
| Admin pattern | `@admin_required` decorator | `@admin_required` decorator | ✅ |
| CLI automation | `flask sync-run --mode X` | `flask cfb-sync --mode X` | ✅ (pattern) |
| App structure | Single file (no blueprints) | App factory + blueprints | ❌ (CFB is better) |
| External API | SlashGolf (RapidAPI) | The Odds API | ❌ (different) |

**Conclusion:** These apps share ~80% of their infrastructure. The CFB Survivor's app factory + blueprints pattern is the better foundation. The game-specific logic (pick rules, scoring, elimination) is the 20% that differs.

### 2.2 Recommended Architecture Pattern

**Recommendation: Modular Monolith (one app with game plugins)**

I considered three options:

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A. Microservices** | Separate apps per game, shared auth service | Independent scaling, isolation | Way over-engineered for 20-30 users. Expensive. Complex. |
| **B. Monolith** | One big app.py with everything | Simple to deploy | Becomes unmaintainable as games grow. What Golf Pick 'Em is already becoming. |
| **C. Modular Monolith** ⭐ | One Flask app with blueprints per game, shared core | Single deployment, shared auth/users, easy to add games, clean separation | Requires upfront restructuring |

**Why Option C wins for you:**

1. **Single deployment** — one PythonAnywhere account, one domain, one database
2. **Shared user system** — players register once, see all their games
3. **Blueprint isolation** — each game is a self-contained module (`/golf/`, `/cfb/`, `/masters/`, etc.)
4. **Easy to add games** — create a new blueprint folder, register it, done
5. **CFB Survivor already uses this pattern** — you've already proven it works
6. **Future mobile app** — add a REST API blueprint alongside the web blueprints

**Proposed Structure:**

```
fantasy-platform/
├── app.py                      # App factory (create_app)
├── config.py                   # Unified config
├── extensions.py               # db, login_manager, csrf, limiter
├── models/
│   ├── __init__.py
│   ├── user.py                 # Shared User model
│   └── base.py                 # Base model utilities
├── core/
│   ├── auth/                   # Shared auth blueprint (login, register, profile)
│   ├── admin/                  # Platform-level admin
│   └── templates/core/         # Shared base templates
├── games/
│   ├── golf/
│   │   ├── __init__.py         # Blueprint registration
│   │   ├── models.py           # Tournament, Pick, Player, etc.
│   │   ├── routes.py           # Golf-specific routes
│   │   ├── services.py         # Sync API, pick resolution
│   │   └── templates/golf/     # Golf templates
│   ├── cfb/
│   │   ├── __init__.py
│   │   ├── models.py           # Team, Week, Game, Pick
│   │   ├── routes.py
│   │   ├── services.py         # Odds API, auto-picks, game logic
│   │   └── templates/cfb/
│   ├── masters/
│   │   └── ...
│   └── olympics/
│       └── ...
├── static/
│   ├── css/
│   └── js/
├── templates/
│   └── base.html               # Platform-wide base template
├── migrations/                  # Alembic migrations
└── requirements.txt
```

### 2.3 Hosting Options

| Option | Cost | Supports Multi-Game? | Database | Future Mobile App? | My Take |
|--------|------|---------------------|----------|-------------------|---------|
| **PythonAnywhere (single paid account)** ⭐ | $5–12/mo | Yes (one WSGI app) | SQLite or MySQL included | REST API possible | Best near-term option. Familiar to you. |
| **Railway.app** | Free tier → $5/mo | Yes | PostgreSQL included | Yes | Good alternative, Docker-based. Slightly more complex. |
| **Render** | Free tier → $7/mo | Yes | PostgreSQL free 90 days, then $7/mo | Yes | Popular, but free tier sleeps after inactivity. |
| **Fly.io** | Free tier → $5/mo | Yes | Needs separate DB setup | Yes | More DevOps required. |
| **VPS (DigitalOcean/Linode)** | $4–6/mo | Yes | Whatever you install | Full control | Most flexible but most maintenance. |
| **Vercel/Netlify** | Free | Frontend only | Need separate backend | For frontend only | Not suitable as primary host for Flask apps. |

**Recommendation: Start with PythonAnywhere paid ($5/mo), migrate to Railway or Render when ready for PostgreSQL.**

Why:
- You already know PythonAnywhere's deployment workflow
- $5/mo gets you one web app (enough for the monolith), scheduled tasks, and MySQL
- Eliminates the second PythonAnywhere account immediately
- When you're ready for PostgreSQL (Phase 3+), Railway or Render are easy migrations
- For a mobile app backend later, you'll want Railway/Render anyway

### 2.4 Database Recommendation

**Phase 1 (now):** Stay on SQLite. It handles 20-30 concurrent users with no problem. Don't add database complexity until the codebase is consolidated.

**Phase 2 (consolidation complete):** Switch to PostgreSQL. Here's why:

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| Concurrent writes | Single writer lock | Full concurrency |
| Hosted options | File on disk only | Railway, Render, Supabase (free tiers) |
| Alembic migrations | Works but fragile | First-class support |
| JSON columns | Limited | Native JSONB |
| Full-text search | Basic | Advanced |
| Mobile app backend | Awkward | Standard |
| Cost | Free | Free tiers available |

**Critical: Add Alembic now regardless of database choice.** Your biggest pain point is manual schema changes. Alembic works with both SQLite and PostgreSQL, so adding it is a no-regret move.

---

## STEP 3 — CONSOLIDATION ROADMAP

### Phase 0: Foundation (Week 1-2)
**Goal:** Set up the unified project structure without breaking anything live.

| Step | Task | Complexity |
|------|------|-----------|
| 0.1 | Create new GitHub repo: `fantasy-platform` | Easy |
| 0.2 | Set up project structure (app factory, extensions, core blueprints) | Medium |
| 0.3 | Build shared User model with all fields needed across games | Medium |
| 0.4 | Set up Alembic for database migrations | Medium |
| 0.5 | Create shared auth blueprint (login, register, change password) | Easy |
| 0.6 | Create platform base template with Bootstrap 5.3 + game navigation | Easy |
| 0.7 | Create shared admin base (user management, payment tracking) | Easy |

**What you'll have:** An empty platform shell with working auth, a shared user model, and proper migrations. No games yet — just the skeleton.

**Decision needed:** Domain name. Do you want a custom domain (e.g., `bradfantasy.com`, `pickemplatform.com`)? Or stick with `username.pythonanywhere.com`?

---

### Phase 1: Migrate Golf Pick 'Em (Weeks 3-5)
**Goal:** Move your most active game into the new platform. This is the hardest phase because it's live mid-season.

| Step | Task | Complexity |
|------|------|-----------|
| 1.1 | Create `games/golf/` blueprint from existing Golf code | Hard |
| 1.2 | Refactor Golf models into `games/golf/models.py` | Medium |
| 1.3 | Refactor Golf routes to use blueprint URL prefixes (`/golf/...`) | Medium |
| 1.4 | Port `sync_api.py` → `games/golf/services.py` | Medium |
| 1.5 | Port `send_reminders.py` into shared notification system | Medium |
| 1.6 | Write SQLite → SQLite migration script for existing user/pick data | Hard |
| 1.7 | Test everything locally against a copy of production data | Hard |
| 1.8 | Deploy to new PythonAnywhere account and verify | Medium |
| 1.9 | Set up scheduled tasks on new account | Easy |
| 1.10 | Redirect old domain → new (or switch DNS) | Easy |

**What you'll have:** Golf Pick 'Em running on the new platform at a single domain. Old PythonAnywhere account can be retired.

**Decision needed:** Do you migrate mid-season (risky but gets it done) or wait until after BMW Championship in August (safe but delays everything)?

**My recommendation:** Wait until a week with no active tournament (like a bye week) and do a quick cutover. The actual migration can be prepared fully in advance and executed in an hour.

---

### Phase 2: Migrate CFB Survivor Pool (Weeks 6-8)
**Goal:** Bring the second live game into the platform. Easier because it's in the off-season.

| Step | Task | Complexity |
|------|------|-----------|
| 2.1 | Create `games/cfb/` blueprint from CFB Survivor code | Medium |
| 2.2 | Refactor CFB models (adapt User fields into shared model) | Medium |
| 2.3 | Port game logic service (`services/game_logic.py`) | Easy |
| 2.4 | Port CFB automation CLI commands | Easy |
| 2.5 | Merge user accounts (same email = same account) | Medium |
| 2.6 | Port CFB templates with updated nav/branding | Easy |
| 2.7 | Retire second PythonAnywhere account | Easy |

**What you'll have:** Both live games under one roof. Single login. Shared user base. One PythonAnywhere account.

**Decision needed:** How to handle users who exist in both games with different usernames? Merge by email? Let them choose?

---

### Phase 3: Build Masters Fantasy as First "New" Game (Weeks 9-12)
**Goal:** Prove the platform works for new games by building Masters Fantasy natively.

| Step | Task | Complexity |
|------|------|-----------|
| 3.1 | Create `games/masters/` blueprint | Easy |
| 3.2 | Build Masters models (Golfer tiers, picks, scoring) from spec | Medium |
| 3.3 | Build pick submission form (replaces Google Forms) | Medium |
| 3.4 | Build scoring engine (strokes to par + bonuses − MC penalties) | Medium |
| 3.5 | Build leaderboard with live scoring display | Medium |
| 3.6 | Integrate with Golf Pick 'Em's SlashGolf API for live scores | Medium |
| 3.7 | Add tiebreaker system | Easy |
| 3.8 | Admin tools for manual score entry/override | Easy |

**What you'll have:** Masters Fantasy as a proper web app instead of a spreadsheet. Live scoring. Shared user base.

**Timeline note:** Masters is April 9-12, 2026. If you want this ready, Phase 3 needs to start by mid-March. Otherwise, run the Masters on Google Sheets this year and migrate it for 2027.

---

### Phase 4: Mobile-Friendly UI Overhaul (Weeks 13-16)
**Goal:** Make everything look great on phones. This is where your players will notice the upgrade.

| Step | Task | Complexity |
|------|------|-----------|
| 4.1 | Audit all templates for mobile responsiveness | Easy |
| 4.2 | Design unified platform home page (game cards, standings) | Medium |
| 4.3 | Improve pick submission UX (larger touch targets, confirmation) | Medium |
| 4.4 | Add push notification support (web push for deadlines) | Hard |
| 4.5 | Optimize page load times (minimize queries, add caching) | Medium |

**What you'll have:** A platform your players actually enjoy using on their phones.

---

### Phase 5: Database Upgrade & API Layer (Weeks 17-20)
**Goal:** Prepare the infrastructure for a mobile app and scale.

| Step | Task | Complexity |
|------|------|-----------|
| 5.1 | Migrate from SQLite to PostgreSQL | Medium |
| 5.2 | Move hosting to Railway or Render | Medium |
| 5.3 | Build REST API blueprint (`/api/v1/`) for mobile app | Hard |
| 5.4 | Add JWT or token-based auth for API | Medium |
| 5.5 | Add proper email service (SendGrid/Resend free tier) | Easy |

**What you'll have:** Production-grade infrastructure ready for a mobile app.

---

### Phase 6: Olympics / World Cup Template (Weeks 21-24)
**Goal:** Build a reusable "event pool" template for one-off events.

| Step | Task | Complexity |
|------|------|-----------|
| 6.1 | Abstract Olympics model into a generic "Tier Pick Event" | Medium |
| 6.2 | Build World Cup Fantasy using the template | Easy |
| 6.3 | Make it admin-configurable (tiers, multipliers, scoring rules) | Hard |

**What you'll have:** The ability to spin up a new fantasy game for any event in hours, not weeks.

---

## STEP 4 — FIRST DECISION

### The single most important decision right now:

**"Should I build the new platform from scratch using the modular monolith pattern, or try to incrementally refactor one of the existing apps?"**

#### Option A: Start Fresh (New Repo, Clean Architecture)
- Create `fantasy-platform` repo from scratch
- Port code from both existing repos into the new structure
- Takes longer upfront but results in clean, maintainable code

#### Option B: Evolve CFB Survivor (Already Has Blueprints)
- Fork the CFB Survivor repo (it already uses app factory + blueprints)
- Add Golf as a second blueprint into the existing structure
- Faster to start but carries forward existing technical debt

#### Option C: Evolve Golf Pick 'Em (Most Active, Most Features)
- Refactor Golf Pick 'Em to use blueprints first
- Add CFB as a second game
- Keeps the live app running but is the riskiest refactor

### My Recommendation: Option A — Start Fresh

**Here's why:**

1. **Clean separation of concerns from day one.** You won't inherit the "everything in app.py" pattern from Golf or the CFB-specific assumptions baked into the Survivor code.

2. **Shared User model designed right.** Right now, Golf users have `total_points` and CFB users have `lives_remaining`. A fresh start lets you design a User model with game-specific data stored in game-specific tables (via foreign keys), not crammed into the User table.

3. **Migration path is the same regardless.** Whether you start fresh or fork, you still need to port all the game logic and migrate data. Starting fresh adds maybe 2-3 hours of initial setup but saves you from untangling two slightly-different codebases.

4. **You won't break anything live.** Both existing sites keep running untouched while you build the new platform. When it's ready, you do a clean cutover.

5. **It's what professional teams would do.** This is a small enough codebase (~4 files per app) that a rewrite is realistic and beneficial. This would NOT be my advice for a large legacy system.

**The risk:** Starting fresh feels slower at first. You'll want to copy-paste liberally from both existing apps (which you should!). The goal isn't to reinvent — it's to reorganize.

---

## ARCHITECTURE DECISION LOG

| # | Decision | Options Considered | Choice | Rationale | Date | Reversible? |
|---|----------|--------------------|--------|-----------|------|-------------|
| ADR-001 | Architecture pattern | Microservices, Monolith, Modular Monolith | **Modular Monolith** (Flask + Blueprints) | Right-sized for 20-30 users. Single deployment. Shared auth. Easy to add games. CFB already proves the pattern. | 2026-03-04 | Yes (can extract to microservices later) |
| ADR-002 | Starting point | Fresh repo, Fork CFB, Fork Golf | **Fresh repo** (`fantasy-platform`) | Clean architecture from day one. Both live apps keep running during build. Port code, don't inherit debt. | 2026-03-04 | N/A |
| ADR-003 | Framework | Flask, Django, FastAPI | **Flask** | You know it. Both apps use it. Huge ecosystem. Django is overkill. FastAPI lacks template rendering. | 2026-03-04 | Hard to reverse |
| ADR-004 | Database (Phase 1) | SQLite, PostgreSQL, MySQL | **SQLite** (for now) | Works fine at current scale. Avoids adding complexity during migration. Upgrade to PostgreSQL in Phase 5. | 2026-03-04 | Yes (easy migration path) |
| ADR-005 | Hosting (Phase 1) | PythonAnywhere, Railway, Render, VPS | **PythonAnywhere (single paid account, ~$5/mo)** | Familiar workflow. Consolidates two accounts into one. Move to Railway/Render for PostgreSQL later. | 2026-03-04 | Yes |
| ADR-006 | Migration tooling | Manual SQL, Alembic, raw scripts | **Alembic** | No-regret move. Works with SQLite and PostgreSQL. Eliminates manual schema management pain. | 2026-03-04 | No (but why would you?) |
| ADR-007 | Frontend (Phase 1) | Bootstrap + Jinja2, React SPA, HTMX | **Bootstrap 5.3 + Jinja2** (keep current stack) | Works well. Mobile-friendly out of the box. No build step. Revisit for mobile app in Phase 5. | 2026-03-04 | Yes |

---

## OPEN QUESTIONS (Need Your Input)

1. **Domain name** — Do you want a custom domain? If so, what name? (~$10-15/year)
2. **Golf migration timing** — Mid-season cutover (risky) or wait until August off-season (safe)?
3. **Masters Fantasy timeline** — Build as a web app for April 2026, or run on Sheets this year and web-ify for 2027?
4. **User merge strategy** — When consolidating, how should we handle players who exist in both Golf and CFB with different usernames?
5. **Budget confirmation** — Are you okay with ~$5/mo for PythonAnywhere paid tier? Any budget for a domain?

---

## NEXT STEPS

Once you've reviewed this document and answered the open questions, the immediate next actions are:

1. Create the `fantasy-platform` GitHub repo
2. Scaffold the project structure (Phase 0, Steps 0.1–0.3)
3. Set up Alembic with the shared User model
4. Build the auth blueprint (copy-paste from CFB Survivor, clean up)

This entire Phase 0 can be done in a single Claude Code session.

---

*This document will be maintained and updated as we make decisions and progress through phases.*
