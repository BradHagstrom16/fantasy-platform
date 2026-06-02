"""
Fantasy Sports Platform - Application Factory
===============================================
Creates and configures the Flask application.
"""
import logging
import os

import click
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

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

    # User loader for Flask-Login. `user_id` is the cookie identity, which is
    # User.auth_id (a random token), NOT the integer PK — see User.get_id().
    # A stale/forged cookie carrying a recycled integer id matches no auth_id
    # and returns None (logged out) rather than cross-authenticating.
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.filter_by(auth_id=user_id).first()

    # Register blueprints
    from core.auth import auth_bp
    from core.main import main_bp
    from core.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # Register golf blueprint
    from games.golf import golf_bp
    app.register_blueprint(golf_bp)

    # Register golf CLI commands
    from games.golf.cli import register_golf_cli
    register_golf_cli(app)

    # Register CFB Survivor blueprint
    from games.cfb import cfb_bp
    app.register_blueprint(cfb_bp)

    # Register CFB CLI commands
    from games.cfb.cli import register_cfb_cli
    register_cfb_cli(app)

    # Register World Cup Fantasy blueprint
    from games.worldcup import worldcup_bp
    app.register_blueprint(worldcup_bp)

    # Register World Cup CLI commands
    from games.worldcup.cli import register_worldcup_cli
    register_worldcup_cli(app)

    # Platform-wide context processors
    from core.context import register_context_processors
    register_context_processors(app)

    # Platform-wide Jinja filters. `ct` converts a UTC datetime to platform
    # display TZ (America/Chicago) and formats it. Lives at app level so
    # both platform (`core/main`) and game blueprints share one rendering
    # path; see utils/time.py for the helper and games/worldcup/routes.py
    # for the legacy context-processor callable that re-exports it.
    from utils.time import format_ct as _format_ct
    app.jinja_env.filters['ct'] = _format_ct

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

    # Trust one level of proxy headers (Cloudflare → Nginx → Gunicorn)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    return app


# Allow `python app.py` for local development
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
