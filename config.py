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
    # Visible From-address, decoupled from the SMTP auth user (EMAIL_ADDRESS). Empty
    # default → utils/email.send_platform_email falls back to EMAIL_ADDRESS. Required so
    # production sends from the DKIM-authenticated commish@cccfantasy.com rather than the
    # SMTP-login address, which Gmail drops as unauthenticated.
    MAIL_FROM_ADDRESS = os.environ.get('MAIL_FROM_ADDRESS', '')
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
    SITE_URL = os.environ.get('SITE_URL', 'http://localhost:5000')

    # Golf Pick 'Em Settings
    SEASON_YEAR = int(os.environ.get('SEASON_YEAR', '2026'))
    ENTRY_FEE = int(os.environ.get('ENTRY_FEE', '25'))
    SYNC_MODE = os.environ.get('SYNC_MODE', 'standard').lower()
    FIXED_DEADLINE_HOUR_CT = int(os.environ.get('FIXED_DEADLINE_HOUR_CT', '7'))
    SLASHGOLF_API_HOST = 'live-golf-data.p.rapidapi.com'
    STATUS_REFRESH_INTERVAL_SECONDS = int(os.environ.get('STATUS_REFRESH_INTERVAL_SECONDS', '300'))
    PICKS_VISIBLE_AFTER_DEADLINE = True

    # CFB Survivor Pool Settings
    ODDS_API_KEY = os.environ.get('ODDS_API_KEY', '')
    CFB_ENTRY_FEE = int(os.environ.get('CFB_ENTRY_FEE', '25'))
    CFB_SEASON_YEAR = int(os.environ.get('CFB_SEASON_YEAR', '2026'))

    # CSRF
    WTF_CSRF_ENABLED = True


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Managed Postgres closes idle connections; long-lived Gunicorn workers
    # must re-check before use and recycle before the provider's idle timeout.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }


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
