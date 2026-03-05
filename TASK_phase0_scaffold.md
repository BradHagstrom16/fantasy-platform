# TASK: Phase 0 — Scaffold the Fantasy Sports Platform

## Available Tools & Plugins

The following Claude Code plugins are installed and enabled. Use them proactively to enhance development workflows and code quality rather than relying solely on training knowledge:

- **claude-code-setup** - Environment and project setup management
- **claude-md-management** - Markdown file handling and organization
- **code-review** - Automated code review and quality checks
- **code-simplifier** - Code refactoring and simplification
- **coderabbit** - AI-powered code analysis
- **commit-commands** - Git commit management and automation
- **context7** - Enhanced contextual awareness (includes MCP)
- **feature-dev** - Feature development workflows
- **frontend-design** - UI/UX design and styling assistance
- **playwright** - Browser automation and testing (includes MCP)
- **pr-review-toolkit** - Pull request review utilities
- **pyright-lsp** - Python language server and type checking
- **superpowers** - Advanced development capabilities

Claude code setup could be good to start with since this project is in its initial phase.
Superpowers can help with this initial phase 0 task.
front end design should be used when building HTML and UIs.
pyright-lsp can be used when you code .py files.

These are here for your benefit, use any when you see fit.

## Context

This is a Claude Code task file for a brand new repo: `fantasy-platform`. The repo currently contains only `ARCHITECTURE_DECISION_LOG.md` and `PLATFORM_AUDIT_AND_ROADMAP.md`. We are building a modular monolith Flask app that will host multiple fantasy sports games (Golf Pick 'Em, CFB Survivor Pool, Masters Fantasy, Olympics Pool, etc.) under a single domain with shared authentication.

This task creates the entire project skeleton: app factory, extensions, config, shared User model, Alembic migrations, auth blueprint, platform admin blueprint, base templates, and a working home page. No game-specific code yet — just the platform foundation that games will plug into.

## Reference Architecture

The two existing apps we'll eventually port into this platform:
- **CF Survivor** (https://github.com/BradHagstrom16/CF_Survivor) — Flask app factory + blueprints. **Use this as the primary structural reference.**
- **Golf Pick 'Em** (https://github.com/BradHagstrom16/Golf_Pick_Em) — Single-file Flask app. Good domain logic, worse structure.

We're taking the best patterns from both and starting clean.

## Target Project Structure

```
fantasy-platform/
├── app.py                          # App factory (create_app)
├── wsgi.py                         # WSGI entry point for PythonAnywhere
├── config.py                       # Environment-based config classes
├── extensions.py                   # db, migrate, login_manager, csrf, limiter
├── models/
│   ├── __init__.py                 # Re-exports all models for Alembic
│   └── user.py                     # Shared User model
├── core/
│   ├── __init__.py
│   ├── auth/
│   │   ├── __init__.py             # auth_bp blueprint
│   │   ├── routes.py               # login, register, logout, change_password, profile
│   │   └── templates/
│   │       └── auth/
│   │           ├── login.html
│   │           ├── register.html
│   │           ├── change_password.html
│   │           └── profile.html
│   ├── admin/
│   │   ├── __init__.py             # admin_bp blueprint
│   │   ├── routes.py               # Platform-level admin (users, payments)
│   │   └── templates/
│   │       └── admin/
│   │           ├── dashboard.html
│   │           └── users.html
│   └── main/
│       ├── __init__.py             # main_bp blueprint
│       ├── routes.py               # Home page, about/rules
│       └── templates/
│           └── main/
│               └── index.html      # Platform home (game cards)
├── games/                          # Empty — game blueprints go here later
│   └── __init__.py
├── templates/
│   ├── base.html                   # Platform-wide base template
│   └── errors/
│       ├── 404.html
│       └── 500.html
├── static/
│   └── css/
│       └── style.css               # Platform styles
├── migrations/                     # Created by flask db init
├── requirements.txt
├── .env.example
├── .gitignore
├── CLAUDE.md
└── README.md
```

---

## Step-by-Step Instructions

### Step 1: Create initial requirements.txt. Using most up to date version of everything. Use Context 7 plugin tool if helpful.

```
Flask>=3.1.3
Flask-SQLAlchemy>=3.1.1
Flask-Login>=0.6.3
Flask-WTF>=1.2.2
Flask-Limiter>=4.1.1
Flask-Migrate>=4.1.0
SQLAlchemy>=2.0.47
Werkzeug>=3.1.6
python-dotenv>=1.2.1
email-validator>=2.3.0
pytz>=2025.2
```

Then run `pip install -r requirements.txt` to verify everything installs cleanly.
Once install completes, run pip freeze to lock in requirements.txt with == instead of >=.

### Step 2: Create .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
*.egg

# Virtual environment
venv/
.venv/

# Database
instance/
*.db

# Environment
.env
env_config.sh
email_config.py

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# DO NOT ignore migrations/ — these must be committed
```

### Step 3: Create .env.example

```bash
# Flask
SECRET_KEY=change-this-to-a-random-secret
ENVIRONMENT=development

# Database (default: SQLite in instance/)
# DATABASE_URL=sqlite:///instance/fantasy_platform.db

# Timezone
PLATFORM_TIMEZONE=America/Chicago

# Email (Gmail SMTP for reminders)
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Site URL (for email links)
SITE_URL=http://localhost:5000
```

### Step 4: Create config.py

Model this after CF Survivor's config.py but generalized for the platform:

```python
"""
Fantasy Sports Platform - Configuration
=========================================
Environment-based configuration classes.
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'fantasy_platform.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    PLATFORM_TIMEZONE = os.environ.get('PLATFORM_TIMEZONE', 'America/Chicago')

    # Email
    EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS', '')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
    SITE_URL = os.environ.get('SITE_URL', 'http://localhost:5000')

    # CSRF
    WTF_CSRF_ENABLED = True


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
```

### Step 5: Create extensions.py

```python
"""
Fantasy Sports Platform - Flask Extensions
============================================
Centralized extension instances, initialized in the app factory.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

csrf = CSRFProtect()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://",
)
```

### Step 6: Create models/user.py

This is the shared User model. It must support all games without game-specific fields crammed in. Game-specific data (lives_remaining, total_points, cumulative_spread) will live in game-specific models that reference User via foreign key.

```python
"""
Fantasy Sports Platform - User Model
======================================
Shared user model for all games. Game-specific player data
lives in game-specific models linked by user_id foreign key.
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


class User(UserMixin, db.Model):
    """A player on the platform. One account across all games."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(100), nullable=True)

    # Platform role
    is_admin = db.Column(db.Boolean, default=False)

    # Payment tracking (platform-level, games can also track per-game payments)
    has_paid = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        """Hash and store password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against hash."""
        return check_password_hash(self.password_hash, password)

    def get_display_name(self):
        """Return display name, falling back to username."""
        return self.display_name or self.username

    def __repr__(self):
        return f'<User {self.username}>'
```

### Step 7: Create models/__init__.py

This file re-exports all models so Alembic can discover them:

```python
"""
Fantasy Sports Platform - Models
==================================
Import all models here so Alembic can discover them.
When adding a new game, import its models here too.
"""
from models.user import User

__all__ = ['User']
```

### Step 8: Create app.py (App Factory)

```python
"""
Fantasy Sports Platform - Application Factory
===============================================
Creates and configures the Flask application.
"""
import logging
import os

import click
from flask import Flask, render_template

from config import config
from extensions import db, migrate, login_manager, csrf, limiter


def create_app(config_name=None):
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.environ.get('ENVIRONMENT', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Import models so Alembic sees them
    from models import User  # noqa: F401

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from core.auth import auth_bp
    from core.main import main_bp
    from core.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # Future: register game blueprints here
    # from games.golf import golf_bp
    # app.register_blueprint(golf_bp, url_prefix='/golf')

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    # CLI commands
    @app.cli.command('init-db')
    def init_db():
        """Create database tables."""
        db.create_all()
        click.echo('Database tables created.')

    @app.cli.command('create-admin')
    def create_admin():
        """Create an admin user interactively."""
        import getpass
        from sqlalchemy import func

        username = input('Admin username: ').strip()
        email = input('Admin email: ').strip()
        password = getpass.getpass('Admin password: ')

        if User.query.filter(func.lower(User.username) == username.lower()).first():
            click.echo(f'User "{username}" already exists.')
            return

        user = User(username=username, email=email, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'Admin user "{username}" created.')

    return app


# Allow `python app.py` for local development
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
```

### Step 9: Create wsgi.py

```python
"""
Fantasy Sports Platform - WSGI Entry Point
============================================
Used by PythonAnywhere (and other WSGI servers).
"""
from app import create_app

application = create_app()
```

### Step 10: Create core/__init__.py

```python
# Core platform modules (auth, admin, main)
```

### Step 11: Create core/auth/__init__.py and routes.py

**core/auth/__init__.py:**
```python
from flask import Blueprint

auth_bp = Blueprint('auth', __name__, template_folder='templates')

from core.auth import routes  # noqa: E402, F401
```

**core/auth/routes.py:**

Port auth logic from CF Survivor's `routes/auth.py`, adapted for the platform. Include: login, register, logout, change_password, and a new profile page.

```python
"""
Fantasy Sports Platform - Authentication Routes
=================================================
Login, register, logout, change password, profile.
"""
import re

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func
from urllib.parse import urlparse

from extensions import db, limiter
from models.user import User
from core.auth import auth_bp


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter(
            func.lower(User.username) == username.casefold()
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            if next_page and urlparse(next_page).netloc == '':
                return redirect(next_page)
            return redirect(url_for('main.index'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        display_name = request.form.get('display_name', '').strip() or None
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        errors = []
        if len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errors.append('Please enter a valid email address.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        if User.query.filter(func.lower(User.username) == username.casefold()).first():
            errors.append('That username is already taken.')
        if User.query.filter(func.lower(User.email) == email.casefold()).first():
            errors.append('That email is already registered.')

        if errors:
            for err in errors:
                flash(err, 'error')
            return render_template('auth/register.html')

        user = User(username=username, email=email, display_name=display_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)
        flash('Account created! Welcome to the platform.', 'success')
        return redirect(url_for('main.index'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
        elif len(new_password) < 6:
            flash('New password must be at least 6 characters.', 'error')
        elif new_password != confirm_password:
            flash('New passwords do not match.', 'error')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('main.index'))

    return render_template('auth/change_password.html')


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip() or None
        email = request.form.get('email', '').strip().lower()

        if email != current_user.email:
            if User.query.filter(func.lower(User.email) == email.casefold()).first():
                flash('That email is already registered.', 'error')
                return render_template('auth/profile.html')
            current_user.email = email

        current_user.display_name = display_name
        db.session.commit()
        flash('Profile updated.', 'success')

    return render_template('auth/profile.html')
```

### Step 12: Create core/main/__init__.py and routes.py

**core/main/__init__.py:**
```python
from flask import Blueprint

main_bp = Blueprint('main', __name__, template_folder='templates')

from core.main import routes  # noqa: E402, F401
```

**core/main/routes.py:**
```python
"""
Fantasy Sports Platform - Main Routes
=======================================
Home page and platform-level pages.
"""
from flask import render_template
from flask_login import current_user

from core.main import main_bp


@main_bp.route('/')
def index():
    """Platform home page — shows available games."""
    # Later, this will query for active games and show cards
    games = [
        {
            'name': 'Golf Pick \'Em',
            'slug': 'golf',
            'description': 'Season-long PGA Tour fantasy. Pick one golfer per tournament. Points = prize money.',
            'status': 'Coming Soon',
            'emoji': '⛳',
            'color': 'success',
        },
        {
            'name': 'CFB Survivor Pool',
            'slug': 'cfb',
            'description': 'Weekly college football picks against the spread. Two lives. Last survivor wins.',
            'status': 'Coming Soon',
            'emoji': '🏈',
            'color': 'danger',
        },
        {
            'name': 'Masters Fantasy',
            'slug': 'masters',
            'description': 'Build your 10-golfer lineup across 6 tiers. Lowest total score wins.',
            'status': 'Coming Soon',
            'emoji': '🏆',
            'color': 'warning',
        },
    ]
    return render_template('main/index.html', games=games)
```

### Step 13: Create core/admin/__init__.py and routes.py

**core/admin/__init__.py:**
```python
from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='templates')

from core.admin import routes  # noqa: E402, F401
```

**core/admin/routes.py:**
```python
"""
Fantasy Sports Platform - Admin Routes
========================================
Platform-level admin: user management, overview.
"""
from functools import wraps

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db
from models.user import User
from core.admin import admin_bp


def admin_required(f):
    """Decorator to require admin access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in first.', 'error')
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@admin_required
def dashboard():
    total_users = User.query.count()
    return render_template('admin/dashboard.html', total_users=total_users)


@admin_bp.route('/users')
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash('You cannot change your own admin status.', 'error')
    else:
        user.is_admin = not user.is_admin
        db.session.commit()
        status = 'admin' if user.is_admin else 'regular user'
        flash(f'{user.get_display_name()} is now a {status}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_password(user_id):
    user = db.get_or_404(User, user_id)
    temp_password = 'changeme123'
    user.set_password(temp_password)
    db.session.commit()
    flash(f'Password for {user.get_display_name()} reset to: {temp_password}', 'warning')
    return redirect(url_for('admin.users'))
```

### Step 14: Create games/__init__.py

```python
# Game blueprints are registered here.
# Each game lives in its own subdirectory (e.g., games/golf/, games/cfb/).
```

### Step 15: Create templates/base.html

This is the platform-wide base template. Use Bootstrap 5.3. Design it to be clean, mobile-first, and neutral (not themed to any one game). Include a navbar with platform name, game links (dropdown), auth links, and admin link.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>{% block title %}Fantasy Sports Platform{% endblock %}</title>

    <!-- Bootstrap 5.3 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Bootstrap Icons -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">

    <!-- Platform CSS -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">

    {% block head %}{% endblock %}
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand fw-bold" href="{{ url_for('main.index') }}">
                🎯 Fantasy Platform
            </a>

            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>

            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('main.index') }}">Home</a>
                    </li>
                    <!-- Game links will be added here as blueprints are registered -->
                    <!--
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                            Games
                        </a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="/golf">⛳ Golf Pick 'Em</a></li>
                            <li><a class="dropdown-item" href="/cfb">🏈 CFB Survivor</a></li>
                        </ul>
                    </li>
                    -->
                </ul>

                <ul class="navbar-nav">
                    {% if current_user.is_authenticated %}
                        {% if current_user.is_admin %}
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('admin.dashboard') }}">
                                <i class="bi bi-gear"></i> Admin
                            </a>
                        </li>
                        {% endif %}
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                                <i class="bi bi-person-circle"></i> {{ current_user.get_display_name() }}
                            </a>
                            <ul class="dropdown-menu dropdown-menu-end">
                                <li><a class="dropdown-item" href="{{ url_for('auth.profile') }}">
                                    <i class="bi bi-person"></i> Profile
                                </a></li>
                                <li><a class="dropdown-item" href="{{ url_for('auth.change_password') }}">
                                    <i class="bi bi-key"></i> Change Password
                                </a></li>
                                <li><hr class="dropdown-divider"></li>
                                <li><a class="dropdown-item" href="{{ url_for('auth.logout') }}">
                                    <i class="bi bi-box-arrow-right"></i> Logout
                                </a></li>
                            </ul>
                        </li>
                    {% else %}
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('auth.login') }}">Login</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('auth.register') }}">Register</a>
                        </li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <!-- Flash Messages -->
    <div class="container mt-3">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </div>

    <!-- Main Content -->
    <main class="container my-4">
        {% block content %}{% endblock %}
    </main>

    <!-- Footer -->
    <footer class="text-center text-muted py-4 mt-5 border-top">
        <small>&copy; 2026 Fantasy Sports Platform</small>
    </footer>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>

    {% block scripts %}{% endblock %}
</body>
</html>
```

### Step 16: Create auth templates

Create these 4 templates in `core/auth/templates/auth/`. Each extends `base.html`. Model them after the existing CFB Survivor and Golf Pick 'Em templates — Bootstrap card layout, centered on page, CSRF token, proper form validation. Include:

- **login.html** — Username + password form. Link to register. "Forgot password? Contact the commissioner" modal.
- **register.html** — Username, email, display name (optional), password, confirm password. Link to login.
- **change_password.html** — Current password, new password, confirm new password.
- **profile.html** — Display name (editable), email (editable), username (read-only), member since date.

All forms must include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>`.

### Step 17: Create admin templates

Create in `core/admin/templates/admin/`:

- **dashboard.html** — Simple stats: total users, link to user management. Placeholder for future game-specific admin panels.
- **users.html** — Table of all users with: username, display name, email, admin badge, created date, actions (toggle admin, reset password).

### Step 18: Create main/index.html (Home Page)

Create in `core/main/templates/main/`:

```html
{% extends "base.html" %}

{% block title %}Fantasy Sports Platform{% endblock %}

{% block content %}
<div class="text-center mb-5">
    <h1 class="display-5 fw-bold">🎯 Fantasy Sports Platform</h1>
    <p class="lead text-muted">All your fantasy games in one place.</p>
    {% if not current_user.is_authenticated %}
        <a href="{{ url_for('auth.register') }}" class="btn btn-primary btn-lg me-2">Join Now</a>
        <a href="{{ url_for('auth.login') }}" class="btn btn-outline-secondary btn-lg">Login</a>
    {% endif %}
</div>

<div class="row g-4">
    {% for game in games %}
    <div class="col-md-4">
        <div class="card h-100 border-{{ game.color }}">
            <div class="card-body text-center">
                <div class="display-4 mb-3">{{ game.emoji }}</div>
                <h5 class="card-title">{{ game.name }}</h5>
                <p class="card-text text-muted">{{ game.description }}</p>
            </div>
            <div class="card-footer text-center bg-transparent">
                <span class="badge bg-secondary">{{ game.status }}</span>
            </div>
        </div>
    </div>
    {% endfor %}
</div>
{% endblock %}
```

### Step 19: Create error templates

**templates/errors/404.html:**
```html
{% extends "base.html" %}
{% block title %}Page Not Found{% endblock %}
{% block content %}
<div class="text-center py-5">
    <h1 class="display-1 text-muted">404</h1>
    <p class="lead">Page not found.</p>
    <a href="{{ url_for('main.index') }}" class="btn btn-primary">Go Home</a>
</div>
{% endblock %}
```

**templates/errors/500.html:**
```html
{% extends "base.html" %}
{% block title %}Server Error{% endblock %}
{% block content %}
<div class="text-center py-5">
    <h1 class="display-1 text-muted">500</h1>
    <p class="lead">Something went wrong. Please try again.</p>
    <a href="{{ url_for('main.index') }}" class="btn btn-primary">Go Home</a>
</div>
{% endblock %}
```

### Step 20: Create static/css/style.css

Keep it minimal — just a few platform-level overrides:

```css
/* Fantasy Sports Platform - Base Styles */

body {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

main {
    flex: 1;
}

/* Card hover effect for game cards */
.card {
    transition: transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
}

.card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* Mobile-friendly adjustments */
@media (max-width: 768px) {
    .display-5 {
        font-size: 1.75rem;
    }
}
```

### Step 21: Initialize Alembic

```bash
flask db init
flask db migrate -m "initial: shared User model"
```

Review the generated migration in `migrations/versions/`. It should create the `users` table with all columns from the User model. Then apply it:

```bash
flask db upgrade
```

### Step 22: Create CLAUDE.md USE the claude.md plugin tool here to improve and proofread this.

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fantasy Sports Platform is a modular monolith Flask application that hosts multiple fantasy sports games under a single domain with shared authentication. Games are implemented as Flask blueprints in the `games/` directory.

**Current games:** None yet (platform skeleton only)
**Planned games:** Golf Pick 'Em, CFB Survivor Pool, Masters Fantasy, Olympics Pool

## Commands

```bash
# Run development server
flask run

# Database
flask db init          # One-time Alembic setup (already done)
flask db migrate -m "description"   # Generate migration after model changes
flask db upgrade       # Apply pending migrations
flask db downgrade     # Rollback one migration
flask db current       # Show current migration version
flask init-db          # Create tables directly (use migrations instead)
flask create-admin     # Interactive admin user creation
```

## Architecture

**Modular monolith** using Flask app factory (`create_app()` in `app.py`) with blueprints:

### Core Files
- `app.py` — App factory, extension init, CLI commands, error handlers
- `wsgi.py` — WSGI entry point for PythonAnywhere
- `config.py` — Environment-based config classes (dev/prod/test)
- `extensions.py` — Centralized extensions: db, migrate, login_manager, csrf, limiter

### Models
- `models/user.py` — Shared User model (all games reference this)
- `models/__init__.py` — Re-exports all models for Alembic discovery

### Core Blueprints
- `core/auth/` — Login, register, logout, change password, profile
- `core/main/` — Platform home page
- `core/admin/` — Platform-level admin (user management)

### Game Blueprints (future)
- `games/golf/` — Golf Pick 'Em (Phase 1)
- `games/cfb/` — CFB Survivor Pool (Phase 2)
- `games/masters/` — Masters Fantasy (Phase 3)

### Templates
- `templates/base.html` — Platform-wide base template (Bootstrap 5.3)
- Each blueprint has its own `templates/` subdirectory

## Key Conventions

- All timestamps use `datetime.now(timezone.utc)` (never deprecated `utcnow()`)
- Platform timezone is `America/Chicago` (Central Time), configured in `config.py`
- User model is shared; game-specific data goes in game-specific models linked by `user_id`
- Alembic for ALL schema changes — never raw SQL
- Flask-Login with `@login_required` for authenticated routes
- Admin routes use custom `@admin_required` decorator
- CSRF via Flask-WTF on all forms
- Login rate-limited to 10/min via Flask-Limiter
- Open redirect prevention on login `next` param

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
```

## Adding a New Game

1. Create `games/your_game/` directory with `__init__.py`, `models.py`, `routes.py`, `services.py`
2. Define blueprint in `__init__.py`
3. Import game models in `models/__init__.py`
4. Register blueprint in `app.py` with URL prefix
5. Run `flask db migrate -m "add your_game models"` then `flask db upgrade`
6. Create templates in `games/your_game/templates/your_game/`
```

### Step 23: Create README.md

Create a clean README with: project description, tech stack summary, quick start instructions (clone, venv, pip install, flask db upgrade, flask create-admin, flask run), project structure overview, and links to the Architecture Decision Log.

### Step 24: Verify Everything Works

Run the full verification sequence:

```bash
# Start the app
flask run

# In another terminal (or after stopping):
# 1. Home page loads at http://localhost:5000/
# 2. Register a new user
# 3. Log in with that user
# 4. Visit /profile and update display name
# 5. Visit /change-password
# 6. Log out
# 7. Create admin: flask create-admin
# 8. Log in as admin
# 9. Visit /admin/ — see dashboard
# 10. Visit /admin/users — see user list
```

All 10 checks must pass.

### Step 25: Commit and Push

Commit message: `feat: Phase 0 — scaffold platform with shared auth, admin, and Alembic`

Ensure all files are committed including `migrations/`. Push to `main` branch on GitHub.

---

## Completion Checklist

- [ ] All files from the project structure exist
- [ ] `pip install -r requirements.txt` succeeds
- [ ] `flask db upgrade` creates the users table
- [ ] `flask run` starts without errors
- [ ] Home page renders with 3 game cards
- [ ] Register, login, logout, change password all work
- [ ] Profile page shows and updates display name and email
- [ ] Admin dashboard and user list work
- [ ] `flask create-admin` creates an admin user
- [ ] CSRF protection active on all forms
- [ ] Login rate limiting works (10/min)
- [ ] 404 and 500 error pages render correctly
- [ ] Mobile layout works (test by resizing browser)
- [ ] `CLAUDE.md` accurately describes the project
- [ ] All code committed and pushed to GitHub

## Clean Up
Once everything is completed, please ensure .md files are updated, and delete any files that are not needed to keep the repo clean. If any plugins from Claude markertplace would be useful in additional phases of this project, please notify me.