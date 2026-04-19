# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Available Tools & Plugins

### How to Use Plugins and Skills

Two distinct mechanisms — use them correctly:

- **Plugins** are invoked by **mentioning the plugin name** in task instructions (e.g., "run `pyright-lsp`", "use `commit-commands`"). Claude Code activates the plugin's behavior when it sees the name.
- **Skills** are invoked by **skill name** using the `/skills` command or by referencing the skill name in instructions (e.g., "invoke `executing-plans`", "use `brainstorming`"). Skills appear in `/skills` and teach Claude Code domain expertise or workflows.

Some plugins contribute skills; others extend behavior directly without appearing in `/skills`.

---

### Installed Plugins (13)

Invoke by plugin name in task instructions.

| Plugin | Purpose |
|--------|---------|
| `claude-code-setup` | Environment and project setup management |
| `claude-md-management` | Markdown file handling and organization |
| `code-review` | Automated code review and quality checks |
| `code-simplifier` | Code refactoring and simplification |
| `coderabbit` | AI-powered holistic code analysis |
| `commit-commands` | Git commit management and automation |
| `context7` | Upstream library/framework docs awareness (MCP-connected) |
| `feature-dev` | Feature development scaffolding workflows |
| `frontend-design` | Design-forward UI/UX implementation |
| `playwright` | Browser automation and testing (MCP-connected) |
| `pr-review-toolkit` | Pull request review utilities |
| `pyright-lsp` | Python type checking via language server |
| `superpowers` | Advanced multi-file analysis and development capabilities |

---

### Available Skills (19)

Invoke by skill name. Skills from `superpowers` are the most commonly used.

**Project skills** (`.claude/skills`)
| Skill | Purpose |
|-------|---------|
| `add-game` | Scaffold a new game blueprint |

**`superpowers` plugin skills**
| Skill | Purpose |
|-------|---------|
| `brainstorming` | Explore requirements and design before building anything |
| `writing-plans` | Draft implementation plans before executing |
| `executing-plans` | Work through a structured plan step-by-step |
| `systematic-debugging` | Methodical debugging across multiple files |
| `test-driven-development` | TDD workflow — write tests before implementation |
| `verification-before-completion` | Verify correctness before marking work done |
| `receiving-code-review` | Respond to and incorporate code review feedback |
| `requesting-code-review` | Prepare code for review |
| `finishing-a-development-branch` | Complete and close out a development branch |
| `using-git-worktrees` | Manage parallel work with git worktrees |
| `using-superpowers` | Meta-skill: use superpowers effectively |
| `dispatching-parallel-agents` | Run multiple agents in parallel |
| `subagent-driven-development` | Delegate work to subagents |
| `writing-skills` | Write and improve Claude Code skills |

**`coderabbit` plugin skill**
| Skill | Purpose |
|-------|---------|
| `code-review` | Holistic multi-file code review |

**`claude-code-setup` plugin skill**
| Skill | Purpose |
|-------|---------|
| `claude-automation-recommender` | Recommend automation improvements |

**`claude-md-management` plugin skill**
| Skill | Purpose |
|-------|---------|
| `claude-md-improver` | Review and improve CLAUDE.md files |

**`frontend-design` plugin skill**
| Skill | Purpose |
|-------|---------|
| `frontend-design` | Design-forward UI implementation |

---

### Plugin Prescription Reference

Use this table to prescribe the right tool at the right step.

| When to prescribe | Plugin or Skill |
|-------------------|----------------|
| Any new feature or component — before writing code | `brainstorming` skill |
| Implementing any feature or bugfix | `test-driven-development` skill |
| After implementing any route/model change | `code-review` (coderabbit) |
| After modifying `.py` files | `pyright-lsp` |
| After completing a feature — reduce complexity | `code-simplifier` |
| Multi-file holistic analysis | `coderabbit` |
| UI changes needing browser verification | `playwright` |
| Needs awareness of library/framework APIs | `context7` |
| End of each logical unit of work | `commit-commands` |
| Before merging any branch to main | `pr-review-toolkit` |
| Scaffolding a new feature end-to-end | `feature-dev` |
| Modifying templates or CSS | `frontend-design` skill |
| Environment/dependency setup | `claude-code-setup` |
| Organizing project documentation | `claude-md-management` |
| Complex multi-file tasks | `superpowers` + `executing-plans` skill |

---

## Project Overview

A unified fantasy sports platform consolidating multiple games under one domain, one login, and one codebase. Flask modular monolith using blueprints. Each game lives in `games/<game>/` with its own models, routes, services, templates, and CLI commands.

**Active games:**
- `games/golf/` — Golf Pick 'Em (Phase 1 ✅)
- `games/cfb/` — CFB Survivor Pool (Phase 2 ✅)
- `games/worldcup/` — World Cup Fantasy Pool (Phase 4 ✅)

---

## Commands

```bash
# Run development server
FLASK_APP=app.py venv/bin/flask run

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
FLASK_APP=app.py venv/bin/flask worldcup seed-teams    # Populate teams from world_cup_countries.py
FLASK_APP=app.py venv/bin/flask worldcup seed-matches   # Seed all 104 match shells
FLASK_APP=app.py venv/bin/flask worldcup init            # Seed teams + matches (fresh setup)
FLASK_APP=app.py venv/bin/flask worldcup recalc          # Recalculate all scores (idempotent)
FLASK_APP=app.py venv/bin/flask worldcup status          # Print tournament state summary
FLASK_APP=app.py venv/bin/flask worldcup process-match   # Enter match result (dev/testing)

# Type checking
venv/bin/pyright                                  # Full project (target: 0 errors)
venv/bin/pyright games/golf/services/sync.py      # Check specific file

# Tests
venv/bin/python -m pytest tests/                          # Run all tests
venv/bin/python -m pytest tests/test_worldcup_scoring.py  # Scoring engine tests
venv/bin/python -m pytest tests/test_worldcup_admin.py    # Admin + public route tests
venv/bin/python -m pytest tests/test_post_deadline_ui.py  # Post-deadline UI tests
```

No linter configured.

---

## Key Conventions

- **Design system:** "The Commissioner's Club" — platform purple/gold + per-game palettes via `body.game-<game>` CSS class
- **Game theming:** Platform components (`.page-hero`, `.stat-block`, `.btn-game`) consume `--game-primary`/`--game-accent` automatically — game CSS must NOT duplicate this
- **Game CSS sections:** Each game has its own section in `style.css` (e.g., `/* === CFB SURVIVOR POOL === */`) with game-specific component classes
- **Game sub-nav:** Each game needs a `.subnav-<game>` class in the `/* === GAME SUB-NAV === */` section of `style.css` setting `background`, `--subnav-accent` (hex), and `--subnav-accent-rgb` (comma-separated R,G,B) — the shared pill `.active` rule consumes these variables
- **Game palettes:** Golf: Augusta green `#006747` + gold `#b8993e`; CFB: crimson `#C5050C` + midnight `#0f0f1a`; World Cup: Old Glory blue `#002868` + red `#BF0A30`
- **Emails:** All outbound email routes through `utils/email.py` → `send_platform_email()`. From-name: "The Commissioner's Club". Game-specific content assembly stays in `games/<game>/services/reminders.py`. HTML emails: table layout + inline styles for Gmail compatibility.
- **Avatars:** All game standings must display `user.get_avatar()` inline before the player display name. `User.avatar_emoji` is nullable String(4); default is ⚽. Required integration point for every game blueprint.
- **Timestamps:** `datetime.now(timezone.utc)` — never `utcnow()`
- **Timezones:** `zoneinfo.ZoneInfo` — `.replace(tzinfo=tz)`, never pytz
- **ORM:** SQLAlchemy 2.0 style — `db.session.get(Model, id)`, `db.get_or_404()`
- **ORM safety:** Never mutate ORM attributes for display — use transient attributes
- **Jinja2 sorting:** Never use `sort(attribute='method_name')` — Jinja2 retrieves the bound method, not its return value. Sort in the route instead.
- **Template restyling:** When restyling templates with JavaScript, audit all `querySelector`/`querySelectorAll`/`getElementById` calls first. Add CSS classes alongside JS-critical ones — never rename or remove them.
- **Schema changes:** Flask-Migrate (Alembic) only — never raw SQL
- **CSRF:** All POST forms include CSRF token; AJAX includes `X-CSRFToken` header
- **POST-only:** All state-mutating operations use POST — no GET routes that change data
- **Admin scoping:** Two-tier game admin — platform admin (`User.is_admin`) always has access to every game's admin routes. Game-specific admin (`<Game>Enrollment.is_admin`) allows delegating admin to enrolled non-platform-admins. All `<game>_admin_required` decorators must check platform admin first, enrollment admin second.
- **Password reset tokens:** `core/auth/tokens.py` uses `itsdangerous.URLSafeTimedSerializer` with 1-hour expiry. Forgot-password route uses anti-enumeration pattern (identical flash message regardless of email existence).
- **Game registry:** `games/registry.py` is the single source of truth — every game has one `GameRegistryEntry` (slug, status, is_featured, blueprint_index/join endpoints, `get_enrollment` + `admin_enroll` callables). Helpers `joined_games`/`available_games`/`coming_soon_games`/`featured_games`/`get_entry` drive homepage, navbar, and admin add-user page. Flip `status` from `'coming_soon'` to `'open'` at launch.
- **Enrollment is explicit:** users reach a game's interior routes only via `/<game>/join` (guarded by `@game_must_be_open(slug)` in `games/common.py`). Interior pick routes carry `@enrollment_required(slug)`, which redirects unenrolled users to `/<game>/join?next=<current>`. **Never** create `<Game>Enrollment` rows from pick or admin paths — platform admins enroll users via `/admin/enrollments`.
- **Admin destructive actions:** Destructive admin POST handlers (e.g., `admin_match_result`, `admin_set_knockout`) branch on `request.form.get('action')` — `action=clear` is a distinct, guarded path that short-circuits before the main mutation. Keep this pattern for new admin routes that both mutate and reset.
- **Scoring attribution:** `games/worldcup/services/scoring.compute_team_score_events` (per-team) and `compute_match_attribution` (per-match) are the single source of truth for scoring breakdowns. Stored `total_score` must equal the sum of those ScoreEvents. Any new UI that surfaces scoring detail must derive from these helpers, not recompute.

---

## Blueprint Pattern (required for all games)

- Blueprint in `games/<game>/` with `<game>_` table prefix on all models
- `<Game>Enrollment` model for game-specific user data, FK to shared `User`
- `@<game>_admin_required` decorator — two-tier: platform admin override first, then enrollment-scoped admin
- Templates extend `templates/base.html`, rendered under `<game>/` prefix
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
├── wsgi.py                 # WSGI entry for PythonAnywhere
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

All smoke test snippets in handoff files must include `db.create_all()` when using `ENVIRONMENT=testing` with in-memory SQLite:

```python
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
    print('Smoke test OK')
```

Auth routes have **no URL prefix** — login is at `/login`, not `/auth/login`.

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

## Deploy to PythonAnywhere

1. Open Bash console (auto-activates venv, auto-cds to project)
2. `git pull`
3. `pip install -r requirements.txt` (if deps changed)
4. `flask db upgrade` (if migrations added)
5. Reload web app from the Web tab

---

## Environment Variables

```
FLASK_APP=app.py
ENVIRONMENT=development|testing|production
SECRET_KEY=...
DATABASE_URL=sqlite:///instance/fantasy.db
ODDS_API_KEY=...          # The Odds API (CFB scores/spreads)
SLASHGOLF_API_KEY=...     # SlashGolf API (Golf leaderboards)
EMAIL_ADDRESS=...         # Platform "from" address (send_platform_email)
EMAIL_PASSWORD=...        # SMTP app password
SMTP_SERVER=...           # Default: smtp.gmail.com
SMTP_PORT=...             # Default: 587
```

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
