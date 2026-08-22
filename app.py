"""
Fantasy Sports Platform - Application Factory
===============================================
Creates and configures the Flask application.
"""
import os

import click
from flask import Flask, render_template, request
from flask_login import current_user
from sqlalchemy import select
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config
from extensions import csrf, db, limiter, login_manager, migrate


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
        return db.session.execute(
            select(User).filter_by(auth_id=user_id)
        ).scalar_one_or_none()

    # Register blueprints
    from core.admin import admin_bp
    from core.auth import auth_bp
    from core.main import main_bp

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

    # Register The Docket blueprint. Imported from games.docket.blueprint,
    # not the package init — the init stays import-light so the pure grading
    # package's flask-free import graph holds (D9 purity lock).
    from games.docket.blueprint import docket_bp
    app.register_blueprint(docket_bp)

    # Register The Docket CLI commands
    from games.docket.cli import register_docket_cli
    register_docket_cli(app)

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

    # Defense in depth: an authenticated response is per-user and must never be
    # written to a shared cache. Flask sets Vary: Cookie but a "Cache Everything"
    # edge rule (e.g. Cloudflare) ignores Vary and could serve one logged-in
    # user's rendered page to another. `no-store` forbids any cache from keeping
    # it. Scoped to authenticated requests so public/anonymous pages stay
    # CDN-cacheable; static is served by nginx in prod and skipped here so dev
    # asset caching is unaffected.
    @app.after_request
    def set_private_cache_on_authenticated(response):
        if current_user.is_authenticated and request.endpoint != 'static':
            response.headers['Cache-Control'] = 'private, no-store'
        return response

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

        from utils.identifier import normalize_identifier

        username = input('Admin username: ').strip()
        # Stored lowered like every web write site (utils/identifier.py contract).
        email = input('Admin email: ').strip().lower()
        password = getpass.getpass('Admin password: ')

        if db.session.scalar(select(User).where(
                func.lower(User.username) == normalize_identifier(username))):
            click.echo(f'User "{username}" already exists.')
            return

        user = User(username=username, email=email, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'Admin user "{username}" created.')

    # Client → Cloudflare → nginx → gunicorn. nginx's realip module
    # (deploy/nginx.conf) rewrites $remote_addr from CF-Connecting-IP when the
    # TCP peer is a Cloudflare range, so the LAST X-Forwarded-For entry nginx
    # appends is the real client; x_for=1 selects it, making
    # request.remote_addr — and the Flask-Limiter key — the real client IP.
    # Keep x_for=1: raising it would trust a client-supplied XFF entry on
    # direct-to-origin requests. Locked by tests/test_client_ip_keying.py.
    # x_host=1 reads the X-Forwarded-Host that nginx pins to the canonical apex
    # (deploy/nginx.conf), making request.host deterministic regardless of the
    # www-vs-apex host the visitor used. Locked by tests/test_forwarded_host_pin.py.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    return app


# Allow `python app.py` for local development
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
