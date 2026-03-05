# Fantasy Sports Platform

A modular monolith Flask application hosting multiple fantasy sports games under a single domain with shared authentication. Games are implemented as Flask blueprints and plug into a shared platform foundation.

## Tech Stack

- **Backend:** Python 3.13, Flask 3.1, Flask-SQLAlchemy, Flask-Migrate (Alembic)
- **Auth:** Flask-Login, Flask-WTF (CSRF), Flask-Limiter
- **Database:** SQLite (dev) / configurable via `DATABASE_URL`
- **Frontend:** Bootstrap 5.3, Bootstrap Icons, Barlow Condensed (Google Fonts)
- **Hosting:** PythonAnywhere (WSGI via `wsgi.py`)

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd fantasy-platform

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and set SECRET_KEY at minimum

# 5. Apply database migrations
mkdir -p instance
FLASK_APP=app.py flask db upgrade

# 6. Create an admin user
FLASK_APP=app.py flask create-admin

# 7. Run the development server
FLASK_APP=app.py flask run
```

Visit `http://localhost:5000` — the platform home page shows available games.

## Project Structure

```
fantasy-platform/
├── app.py              # App factory (create_app)
├── wsgi.py             # WSGI entry point for PythonAnywhere
├── config.py           # Environment-based config classes
├── extensions.py       # db, migrate, login_manager, csrf, limiter
├── models/
│   ├── __init__.py     # Re-exports all models for Alembic
│   └── user.py         # Shared User model
├── core/
│   ├── auth/           # Login, register, logout, profile, change password
│   ├── admin/          # Platform-level admin (user management)
│   └── main/           # Home page
├── games/              # Game blueprints go here (Phase 1+)
├── templates/
│   ├── base.html       # Platform-wide base template
│   └── errors/         # 404, 500 error pages
├── static/css/
│   └── style.css       # Platform styles (CSS variables, animations)
├── migrations/         # Alembic migration history
├── requirements.txt
└── .env.example
```

## Adding a New Game

See `CLAUDE.md` for the full step-by-step process. In brief:

1. Create `games/your_game/` with `__init__.py`, `models.py`, `routes.py`
2. Import game models in `models/__init__.py`
3. Register the blueprint in `app.py`
4. Run `flask db migrate` + `flask db upgrade`

## Planned Games

| Game | Status |
|---|---|
| Golf Pick 'Em | Phase 1 |
| CFB Survivor Pool | Phase 2 |
| Masters Fantasy | Phase 3 |
| Olympics Pool | TBD |

## Reference

- [Architecture Decision Log](ARCHITECTURE_DECISION_LOG.md)
- [Platform Audit & Roadmap](PLATFORM_AUDIT_AND_ROADMAP.md)
