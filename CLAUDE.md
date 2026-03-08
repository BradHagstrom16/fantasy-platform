# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Fantasy Sports Platform — modular monolith Flask app hosting multiple fantasy sports games under one domain with shared authentication. Games are Flask blueprints in `games/`.

**Current games:** Golf Pick 'Em (Phase 1 COMPLETE), CFB Survivor Pool (Phase 2 COMPLETE)
**Planned:** Masters Fantasy, Olympics Pool

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
- `games/golf/` — Golf Pick 'Em (Phase 1 COMPLETE)
  - `__init__.py` — Blueprint definition with route imports
  - `models.py` — 7 models (GolfEnrollment, GolfPlayer, GolfTournament, etc.)
  - `utils.py` — Score formatting, payout calculations, timezone
  - `constants.py` — Excluded tournaments, purse estimates
  - `routes.py` — All route handlers (~15 routes: standings, schedule, pick, admin)
  - `services/sync.py` — SlashGolfAPI + TournamentSync
  - `services/reminders.py` — Email notifications
  - `cli.py` — All `flask golf *` CLI commands
  - `templates/golf/` — All golf UI templates (index, schedule, make_pick, my_picks,
                          tournament_detail, admin/dashboard, admin/tournaments, etc.)
- `games/cfb/` — CFB Survivor Pool (Phase 2 COMPLETE)
  - `__init__.py` — Blueprint definition with route imports
  - `models.py` — 5 models (CfbEnrollment, CfbTeam, CfbWeek, CfbGame, CfbPick)
  - `utils.py` — Timezone helpers, week display names, CFP tracking
  - `constants.py` — FBS master teams, conferences, dev seed data
  - `routes.py` — All route handlers (~20 routes: standings, pick, results, admin)
  - `services/game_logic.py` — Pick processing, autopicks, spread calculation
  - `services/score_fetcher.py` — The Odds API score fetching
  - `services/automation.py` — Automated sync tasks
  - `services/reminders.py` — Pick reminder emails
  - `cli.py` — All `flask cfb *` CLI commands
  - `templates/cfb/` — All CFB UI templates (index, pick, my_picks, weekly_results,
                         admin/dashboard, admin/create_week, admin/manage_games, etc.)
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
- Platform admin routes use `@admin_required` decorator from `core/admin/routes.py`
- CFB admin routes use `@cfb_admin_required` in `games/cfb/routes.py` (checks `CfbEnrollment.is_admin`, NOT `User.is_admin`)
- CFB tables use `cfb_` prefix (e.g., `cfb_week`, `cfb_pick`)
- CFB-specific user data lives in `CfbEnrollment`, NOT on the shared User model
- CFB pick eligibility: 5 rules (used teams, 16.5-pt spread cap, game started, CFP eliminated, no game scheduled)
- CFB team usage resets for College Football Playoff (CFP) phase
- CFB pool timezone: `games.cfb.utils` (America/Chicago)
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

## CFB CLI Commands

```bash
# Unified sync (most common — used by scheduled tasks)
FLASK_APP=app.py venv/bin/flask cfb sync --mode setup       # Create next week + import games
FLASK_APP=app.py venv/bin/flask cfb sync --mode spreads     # Update spreads from The Odds API
FLASK_APP=app.py venv/bin/flask cfb sync --mode scores      # Fetch scores + auto-process
FLASK_APP=app.py venv/bin/flask cfb sync --mode autopick    # Process missed-deadline auto-picks
FLASK_APP=app.py venv/bin/flask cfb sync --mode remind      # Send pick reminders
FLASK_APP=app.py venv/bin/flask cfb sync --mode status      # Print season summary

# Individual commands
FLASK_APP=app.py venv/bin/flask cfb populate-teams           # Seed dev teams
FLASK_APP=app.py venv/bin/flask cfb setup
FLASK_APP=app.py venv/bin/flask cfb scores
FLASK_APP=app.py venv/bin/flask cfb spreads
FLASK_APP=app.py venv/bin/flask cfb autopick
FLASK_APP=app.py venv/bin/flask cfb remind
FLASK_APP=app.py venv/bin/flask cfb status
```

## CFB URL Map

| URL | Endpoint | Auth | Description |
|-----|----------|------|-------------|
| `/cfb/` | `cfb.index` | Public | Season standings |
| `/cfb/results` | `cfb.weekly_results` | Public | Weekly results (latest or by week) |
| `/cfb/results/<week>` | `cfb.weekly_results` | Public | Results for specific week |
| `/cfb/pick/<week>` | `cfb.make_pick` | Login | Submit/edit weekly pick |
| `/cfb/my-picks` | `cfb.my_picks` | Login | User's pick history |
| `/cfb/admin/` | `cfb.admin_dashboard` | CFB Admin | Admin overview + week management |
| `/cfb/admin/week/new` | `cfb.admin_create_week` | CFB Admin | Create new week |
| `/cfb/admin/week/<id>/activate` | `cfb.admin_activate_week` | CFB Admin | Activate a week |
| `/cfb/admin/week/<id>/complete` | `cfb.admin_complete_week` | CFB Admin | Mark week complete |
| `/cfb/admin/week/<id>/games` | `cfb.admin_manage_games` | CFB Admin | Add/manage games |
| `/cfb/admin/week/<id>/mark-results` | `cfb.admin_mark_results` | CFB Admin | Mark game winners |
| `/cfb/admin/week/<id>/fetch-scores` | `cfb.admin_fetch_scores` | CFB Admin | Fetch API scores |
| `/cfb/admin/week/<id>/apply-scores` | `cfb.admin_apply_scores` | CFB Admin | Apply fetched scores |
| `/cfb/admin/process-autopicks/<id>` | `cfb.admin_process_autopicks` | CFB Admin | Trigger auto-picks |
| `/cfb/admin/users` | `cfb.admin_users` | CFB Admin | User management |
| `/cfb/admin/payments` | `cfb.admin_payments` | CFB Admin | Payment tracking |
| `/cfb/admin/manage-teams` | `cfb.admin_manage_teams` | CFB Admin | FBS team selection |

## Golf URL Map

| URL | Endpoint | Auth | Description |
|-----|----------|------|-------------|
| `/golf/` | `golf.index` | Public | Season standings |
| `/golf/schedule` | `golf.schedule` | Public | Tournament schedule |
| `/golf/tournament/<id>` | `golf.tournament_detail` | Public | Tournament detail/results |
| `/golf/results` | `golf.results` | Public | Redirect to latest results |
| `/golf/pick/<id>` | `golf.make_pick` | Login | Submit/edit pick |
| `/golf/my-picks` | `golf.my_picks` | Login | User's pick history |
| `/golf/admin/` | `golf.admin_dashboard` | Admin | Golf admin overview |
| `/golf/admin/tournaments` | `golf.admin_tournaments` | Admin | Manage tournaments |
| `/golf/admin/users` | `golf.admin_users` | Admin | User management |
| `/golf/admin/payments` | `golf.admin_payments` | Admin | Payment tracking |
| `/golf/admin/override-pick` | `golf.admin_override_pick` | Admin | Override picks |
| `/golf/admin/process-results/<id>` | `golf.admin_process_results` | Admin | Process results |

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
CFB_SEASON_YEAR=2026
CFB_ENTRY_FEE=25
THE_ODDS_API_KEY=...
```
