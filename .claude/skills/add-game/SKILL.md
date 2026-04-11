---
name: add-game
description: Scaffold a new game blueprint following the fantasy-platform conventions in CLAUDE.md
invocation: user-only
---

# Add Game Skill

When invoked, scaffold a new game blueprint following the established platform pattern exactly.
Ask for the game name if not provided (e.g. "cfb", "masters", "worldcup").

## Steps (execute in order, do not skip)

1. **Create blueprint directory structure:**
   ```
   games/<name>/
   games/<name>/__init__.py
   games/<name>/models.py
   games/<name>/routes.py
   games/<name>/services.py
   games/<name>/cli.py
   games/<name>/templates/<name>/
   ```

2. **Define blueprint in `games/<name>/__init__.py`:**
   - Blueprint name: `<name>`
   - url_prefix: `/<name>`
   - Import routes at bottom of file (avoid circular imports)

3. **Scaffold models.py with `<Name>Enrollment` model:**
   - Table prefix: `<name>_` on ALL models in this game
   - FK to `User` via `user_id = db.Column(db.Integer, db.ForeignKey('user.id'))`
   - Follow SQLAlchemy 2.0 style throughout

4. **Scaffold routes.py with:**
   - `@<name>_admin_required` decorator — **must use the two-tier pattern:**
     ```python
     def <name>_admin_required(f):
         """Two-tier admin: platform admin (User.is_admin) always passes,
         otherwise requires <Name>Enrollment.is_admin."""
         @wraps(f)
         @login_required
         def decorated_function(*args, **kwargs):
             if current_user.is_admin:
                 return f(*args, **kwargs)
             enrollment = <Name>Enrollment.query.filter_by(
                 user_id=current_user.id, season_year=SEASON_YEAR
             ).first()
             if not enrollment or not enrollment.is_admin:
                 flash('<Game> admin access required.', 'error')
                 return redirect(url_for('<name>.index'))
             return f(*args, **kwargs)
         return decorated_function
     ```
   - `before_request` hook for auto-refresh logic
   - Context processor for game-specific template variables
   - Placeholder routes: index, admin dashboard

5. **Register models in `models/__init__.py`:**
   - Add import so Alembic discovers the new models

6. **Register blueprint in `app.py`:**
   - Import and register with `url_prefix='/<name>'`
   - Add CLI group import

7. **Add nav entry in `templates/base.html`:**
   - Add `<li>` entry to the Games dropdown

8. **Run migrations:**
   ```bash
   mkdir -p instance/
   FLASK_APP=app.py venv/bin/flask db migrate -m "add <name> models"
   # Review the generated migration file before proceeding
   FLASK_APP=app.py venv/bin/flask db upgrade
   ```

9. **Run smoke test to verify blueprint loads:**
   ```bash
   FLASK_APP=app.py ENVIRONMENT=testing venv/bin/python -c "
   from app import create_app
   app = create_app('testing')
   with app.app_context():
       from extensions import db
       db.create_all()
   with app.test_client() as c:
       r = c.get('/<name>/')
       print(f'Blueprint response: {r.status_code}')
   print('OK')
   "
   ```

## Critical Conventions (never deviate)

- All table names prefixed: `<name>_enrollment`, `<name>_player`, etc.
- Timestamps use `datetime.now(timezone.utc)` — never `utcnow()`
- Timezone: `zoneinfo.ZoneInfo` — never pytz
- ORM: SQLAlchemy 2.0 style — `db.session.get(Model, id)`, `db.get_or_404(Model, id)`
- CSRF on all forms
- Templates extend `templates/base.html` and render under `<name>/` prefix
- CLI commands under `flask <name>-*` namespace using `AppGroup`
- Never use raw SQL for schema changes — always Flask-Migrate
