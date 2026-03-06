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

    # Register golf blueprint
    from games.golf import golf_bp
    app.register_blueprint(golf_bp)

    # Register golf CLI commands
    from games.golf.cli import register_golf_cli
    register_golf_cli(app)

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
