"""
Fantasy Sports Platform - Flask Extensions
============================================
Centralized extension instances, initialized in the app factory.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

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
    # Storage is config-driven (RATELIMIT_STORAGE_URI, read at init_app time):
    # memory:// in dev/tests, shared Redis in production so all Gunicorn
    # workers count against one bucket. A storage_uri passed here would
    # silently override the config key and resurrect the per-worker-counter
    # bug (engineering backlog 2.1) — don't add one.
)
