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

    # Golf Pick 'Em Settings
    SEASON_YEAR = int(os.environ.get('SEASON_YEAR', '2026'))
    ENTRY_FEE = int(os.environ.get('ENTRY_FEE', '25'))
    SYNC_MODE = os.environ.get('SYNC_MODE', 'standard').lower()
    FIXED_DEADLINE_HOUR_CT = int(os.environ.get('FIXED_DEADLINE_HOUR_CT', '7'))
    SLASHGOLF_API_HOST = 'live-golf-data.p.rapidapi.com'
    STATUS_REFRESH_INTERVAL_SECONDS = int(os.environ.get('STATUS_REFRESH_INTERVAL_SECONDS', '300'))
    PICKS_VISIBLE_AFTER_DEADLINE = True

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
