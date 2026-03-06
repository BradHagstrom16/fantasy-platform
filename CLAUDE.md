# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Fantasy Sports Platform — modular monolith Flask app hosting multiple fantasy sports games under one domain with shared authentication. Games are Flask blueprints in `games/`.

**Current games:** Golf Pick 'Em (Phase 1B — models + services complete, routes/templates pending)
**Planned:** CFB Survivor Pool, Masters Fantasy, Olympics Pool

## Environment

- Python 3.13 via pyenv. Always use `venv/bin/python` and `venv/bin/flask` — do not rely on system Python.
- Set `FLASK_APP=app.py` for all `flask` CLI commands.
- `instance/` must exist before running `flask db migrate` (SQLite can't create its own parent dir). Run `mkdir -p instance/` if missing.
- Use `ENVIRONMENT=testing` for in-memory SQLite during smoke tests.

## Commands

```bash
# Run dev server
FLASK_APP=app.py venv/bin/flask run

# Database
FLASK_APP=app.py venv/bin/flask db migrate -m "description"
FLASK_APP=app.py venv/bin/flask db upgrade
FLASK_APP=app.py venv/bin/flask db downgrade
FLASK_APP=app.py venv/bin/flask db current

# Utilities
FLASK_APP=app.py venv/bin/flask init-db        # Direct table create (use migrations instead)
FLASK_APP=app.py venv/bin/flask create-admin   # Interactive admin user creation

# Smoke test (no server needed)
FLASK_APP=app.py ENVIRONMENT=testing venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.test_client() as c:
    assert c.get('/').status_code == 200
print('OK')
"
```

## Architecture

Modular monolith using `create_app()` in `app.py` with blueprints.

### Core Files
- `app.py` — app factory, CLI commands, error handlers
- `wsgi.py` — WSGI entry point for PythonAnywhere
- `config.py` — dev/prod/test config classes
- `extensions.py` — db, migrate, login_manager, csrf, limiter

### Models
- `models/user.py` — shared User model (all games reference this)
- `models/__init__.py` — re-exports all models for Alembic discovery

### Core Blueprints
- `core/auth/` — login, register, logout, change password, profile
- `core/main/` — platform home page
- `core/admin/` — platform-level admin (user management)

### Game Blueprints
- `games/golf/` — Golf Pick 'Em (Phase 1B complete — models + services done, routes pending)
  - `models.py` — GolfEnrollment, GolfPlayer, GolfTournament, GolfTournamentField,
                   GolfTournamentResult, GolfPick, GolfSeasonPlayerUsage
  - `utils.py` — format_score_to_par(), parse_score_to_par(), calculate_projected_earnings(),
                  PAYOUT_PERCENTAGES, GOLF_LEAGUE_TZ
  - `constants.py` — EXCLUDED_TOURNAMENTS, SEASON_CUTOFF_DATE, PURSE_ESTIMATES, MIN_FIELD_SIZE
  - `services/sync.py` — SlashGolfAPI client, TournamentSync orchestrator, tournament helper functions
  - `services/reminders.py` — Email notifications (picks open, deadline reminders, admin alerts)
  - `cli.py` — All `flask golf *` commands (sync-run, sync-schedule, sync-field, etc.)
  - `templates/golf/` — placeholder (Phase 1C: all golf UI templates)
- `games/cfb/` — CFB Survivor Pool (Phase 2)
- `games/masters/` — Masters Fantasy (Phase 3)

### Templates
- `templates/base.html` — platform base (Bootstrap 5.3 + Barlow Condensed font)
- Each blueprint has its own `templates/<blueprint>/` subdirectory
- CSS variables in `static/css/style.css` — edit `--navy`, `--gold`, etc. for brand changes

## Key Conventions

- All timestamps: `datetime.now(timezone.utc)` (never `utcnow()`)
- Platform timezone: `America/Chicago` (Central), configured in `config.py`
- Game-specific data goes in game-specific models linked by `user_id` FK — never cram into User
- All schema changes via Alembic — never raw SQL or `db.create_all()` in production
- Admin routes use `@admin_required` decorator from `core/admin/routes.py`
- CSRF via Flask-WTF on all POST forms: `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>`
- Login rate-limited to 10/min via Flask-Limiter
- Open redirect prevention on login `next` param via `urlparse(...).netloc == ''` check
- Golf tables use `golf_` prefix (e.g., `golf_tournament`, `golf_pick`)
- Golf-specific user data lives in `GolfEnrollment`, NOT on the shared User model
- `GolfPick.resolve_pick()` is the core pick resolution logic — do not simplify
- Golf league timezone: `games.golf.utils.GOLF_LEAGUE_TZ` (America/Chicago)

## Adding a New Game

1. Create `games/your_game/` with `__init__.py`, `models.py`, `routes.py`, `services.py`
2. Define blueprint in `__init__.py`
3. Import game models in `models/__init__.py`
4. Register blueprint in `app.py` with URL prefix
5. `mkdir -p instance/ && FLASK_APP=app.py venv/bin/flask db migrate -m "add your_game models"`
6. `FLASK_APP=app.py venv/bin/flask db upgrade`
7. Create templates in `games/your_game/templates/your_game/`
8. Uncomment/add nav link in `templates/base.html`

## Golf CLI Commands

```bash
# Unified sync (most common — used by scheduled tasks)
FLASK_APP=app.py venv/bin/flask golf sync-run --mode schedule    # Mon: refresh schedule
FLASK_APP=app.py venv/bin/flask golf sync-run --mode field       # Tue/Wed: sync tournament field
FLASK_APP=app.py venv/bin/flask golf sync-run --mode live        # Thu-Sun: update leaderboard
FLASK_APP=app.py venv/bin/flask golf sync-run --mode live-with-wd # Fri 8PM: live + withdrawals
FLASK_APP=app.py venv/bin/flask golf sync-run --mode results     # Sun/Mon: finalize results
FLASK_APP=app.py venv/bin/flask golf sync-run --mode earnings    # Mon: retry pending earnings
FLASK_APP=app.py venv/bin/flask golf sync-run --mode all         # Full sync cycle

# Individual commands
FLASK_APP=app.py venv/bin/flask golf sync-schedule
FLASK_APP=app.py venv/bin/flask golf sync-field
FLASK_APP=app.py venv/bin/flask golf sync-results
FLASK_APP=app.py venv/bin/flask golf sync-earnings
FLASK_APP=app.py venv/bin/flask golf check-wd
FLASK_APP=app.py venv/bin/flask golf remind
```

## Environment Variables

```
ENVIRONMENT=development|production|testing
SECRET_KEY=...
DATABASE_URL=sqlite:///instance/fantasy_platform.db
PLATFORM_TIMEZONE=America/Chicago
EMAIL_ADDRESS=...
EMAIL_PASSWORD=...
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SITE_URL=http://localhost:5000
SEASON_YEAR=2026
ENTRY_FEE=25
SYNC_MODE=standard
FIXED_DEADLINE_HOUR_CT=7
SLASHGOLF_API_KEY=...
```
