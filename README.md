# Fantasy Sports Platform

A modular monolith Flask application hosting multiple fantasy sports games — **Corrupt Commish Club (CCC)** — under a single domain with shared authentication. Each game is a Flask blueprint that plugs into a shared platform foundation (auth, admin, registry, email). Live at **[cccfantasy.com](https://cccfantasy.com)**.

## Tech Stack

- **Backend:** Python 3.13, Flask 3.1, Flask-SQLAlchemy, Flask-Migrate (Alembic)
- **Auth:** Flask-Login, Flask-WTF (CSRF), Flask-Limiter
- **Database:** SQLite (dev) / PostgreSQL (prod) — configurable via `DATABASE_URL`
- **Frontend:** Bootstrap 5.3, Bootstrap Icons; Teko (display) + Newsreader (body) via Google Fonts
- **Hosting:** DigitalOcean Droplet → Nginx → Gunicorn (unix socket) → Flask; DO Managed Postgres over private VPC; Cloudflare proxy with Origin Certificate

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
# Edit .env — set SECRET_KEY at minimum

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
├── app.py                  # App factory (create_app)
├── wsgi.py                 # WSGI entry (Gunicorn loads `wsgi:application`)
├── config.py               # Environment-based config classes
├── extensions.py           # db, migrate, login_manager, csrf, limiter
├── models/user.py          # Shared User model
├── utils/email.py          # Shared platform email helper
├── core/                   # Platform layer (auth, admin, home)
├── games/                  # Game blueprints (Golf, CFB, World Cup) + registry/common
├── templates/              # Platform-wide base + email + errors
├── static/css/             # tokens.css (Layer 1) + style.css (Layer 2)
├── migrations/             # Alembic migration history
├── tests/                  # pytest suite
├── deploy/                 # Production deploy artifacts (nginx.conf, systemd unit)
├── deploy.sh               # One-command server-side deploy
├── CLAUDE.md               # Conventions, gotchas, blueprint pattern (read first)
└── ARCHITECTURE_DECISION_LOG.md
```

## Games

| Game | Status |
|---|---|
| Golf Pick 'Em | ✅ Live |
| CFB Survivor Pool | ✅ Live |
| World Cup Fantasy Pool | ✅ Live |

## Adding a New Game

See `CLAUDE.md` § *Blueprint Pattern* for the full required pattern (table-prefixed models, two-tier admin, enrollment flow, registry entry, sub-nav class, CLI namespace, etc.).

## Reference

- [PRODUCT.md](PRODUCT.md) — product spine (audience, voice, what we're building)
- [DESIGN.md](DESIGN.md) — platform-foundation design system (CCC palette, typography, primitives)
- `games/<slug>/DESIGN.md` — per-game design specialization (currently `games/worldcup/DESIGN.md`)
- [CLAUDE.md](CLAUDE.md) — operational conventions, gotchas, blueprint pattern
- [ARCHITECTURE_DECISION_LOG.md](ARCHITECTURE_DECISION_LOG.md) — historical decisions
- ![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/BradHagstrom16/fantasy-platform?utm_source=oss&utm_medium=github&utm_campaign=BradHagstrom16%2Ffantasy-platform&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)
