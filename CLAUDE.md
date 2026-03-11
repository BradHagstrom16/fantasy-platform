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
- `games/masters/` — Masters Fantasy (Phase 3, not started)

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

# Type checking
venv/bin/pyright                                  # Full project (target: 0 errors)
venv/bin/pyright games/golf/services/sync.py      # Check specific file
```

No test suite. No linter configured.

---

## Key Conventions

- **Timestamps:** `datetime.now(timezone.utc)` — never `utcnow()`
- **Timezones:** `zoneinfo.ZoneInfo` — `.replace(tzinfo=tz)`, never pytz
- **ORM:** SQLAlchemy 2.0 style — `db.session.get(Model, id)`, `db.get_or_404()`
- **ORM safety:** Never mutate ORM attributes for display — use transient attributes
- **Schema changes:** Flask-Migrate (Alembic) only — never raw SQL
- **CSRF:** All POST forms include CSRF token; AJAX includes `X-CSRFToken` header
- **POST-only:** All state-mutating operations use POST — no GET routes that change data
- **Admin scoping:** Game admin is scoped to enrolled users only; game admin ≠ platform admin

---

## Blueprint Pattern (required for all games)

- Blueprint in `games/<game>/` with `<game>_` table prefix on all models
- `<Game>Enrollment` model for game-specific user data, FK to shared `User`
- `@<game>_admin_required` decorator scoped to enrolled users
- Templates extend `templates/base.html`, rendered under `<game>/` prefix
- Games dropdown in `base.html` gets a new `<li>` per game
- CLI commands under `flask <game> *` namespace using `AppGroup`
- Context processor on the blueprint for game-specific template variables
- `before_request` hook for auto-refresh logic

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
├── core/
│   ├── auth/               # Login, register, logout, change password
│   ├── admin/              # Platform-level admin
│   └── main/               # Home page
├── games/
│   ├── golf/               # Golf Pick 'Em blueprint
│   └── cfb/                # CFB Survivor Pool blueprint
├── templates/
│   ├── base.html           # Platform base template
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
MAIL_USERNAME=...
MAIL_PASSWORD=...
```
