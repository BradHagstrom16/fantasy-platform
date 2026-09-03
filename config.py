"""
Fantasy Sports Platform - Configuration
=========================================
Environment-based configuration classes.
"""
import os
from datetime import timedelta
from typing import ClassVar

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
    # Where game-admin alert emails (score-sync results, setup failures) are
    # delivered. In prod EMAIL_ADDRESS is the Brevo SMTP *login*, not an inbox,
    # so alerts must not default to it there — set ADMIN_EMAIL to a real
    # mailbox. Empty default → senders fall back to EMAIL_ADDRESS (fine in dev,
    # where EMAIL_ADDRESS is a real account).
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', '')
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
    SITE_URL = os.environ.get('SITE_URL', 'http://localhost:5000')

    # Golf Pick 'Em Settings
    SEASON_YEAR = int(os.environ.get('SEASON_YEAR', '2026'))
    ENTRY_FEE = int(os.environ.get('ENTRY_FEE', '25'))
    SYNC_MODE = os.environ.get('SYNC_MODE', 'standard').lower()
    FIXED_DEADLINE_HOUR_CT = int(os.environ.get('FIXED_DEADLINE_HOUR_CT', '7'))
    # SlashGolf (RapidAPI) key for the Golf Pick 'Em sync. Plumbed through
    # config so app-context callers read current_app.config['SLASHGOLF_API_KEY']
    # rather than os.environ directly — the MAIL_FROM_ADDRESS gotcha: a key read
    # via current_app.config.get() that has no os.environ.get() line here is
    # silently None in prod. Empty default → the CLI refuses to run a sync.
    SLASHGOLF_API_KEY = os.environ.get('SLASHGOLF_API_KEY', '')
    SLASHGOLF_API_HOST = 'live-golf-data.p.rapidapi.com'
    STATUS_REFRESH_INTERVAL_SECONDS = int(os.environ.get('STATUS_REFRESH_INTERVAL_SECONDS', '300'))
    PICKS_VISIBLE_AFTER_DEADLINE = True

    # CFB Survivor Pool Settings
    ODDS_API_KEY = os.environ.get('ODDS_API_KEY', '')
    CFB_ENTRY_FEE = int(os.environ.get('CFB_ENTRY_FEE', '25'))
    CFB_SEASON_YEAR = int(os.environ.get('CFB_SEASON_YEAR', '2026'))

    # The Docket Settings (season year lives in games/docket/services/weeks.py,
    # the week-math SSoT — deliberately not a config knob)
    DOCKET_ENTRY_FEE = int(os.environ.get('DOCKET_ENTRY_FEE', '60'))
    # The purse (rulings doc Amendments, 2026-09-03): a fixed prize to each
    # week's top sheet across TOTAL_WEEKS, then a percent split of what is
    # left into first / second / third (games/docket/services/purse.py).
    DOCKET_WEEKLY_PRIZE = int(os.environ.get('DOCKET_WEEKLY_PRIZE', '20'))
    DOCKET_PODIUM_SPLIT = tuple(
        int(x) for x in os.environ.get('DOCKET_PODIUM_SPLIT', '65,25,10').split(','))

    # World Cup Fantasy Pool — football-data.org sync
    FOOTBALL_DATA_API_KEY = os.environ.get('FOOTBALL_DATA_API_KEY', '')

    # Member payment rails (utils/payment.py::payment_rails) — where the
    # "Settle the Tab" nudge + the picks-open emails send a member's buy-in.
    # Defaults ARE the live values (already public in
    # games/worldcup/constants.py) so launch needs no .env edit; blank either
    # one to hide every nudge. The frozen World Cup keeps its own constants.
    PAYMENT_VENMO_HANDLE = os.environ.get('PAYMENT_VENMO_HANDLE', 'Bradley-Hagstrom')
    PAYMENT_ZELLE_PHONE = os.environ.get('PAYMENT_ZELLE_PHONE', '(630) 408-3424')

    # Rate limiting (Flask-Limiter reads this at init_app; extensions.py
    # deliberately passes no storage_uri so this key stays authoritative).
    # memory:// is correct for single-process dev; production overrides below.
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

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
    SQLALCHEMY_ENGINE_OPTIONS: ClassVar[dict] = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }
    # Rate-limit counters must be shared across the 3 Gunicorn workers.
    # memory:// keeps per-worker buckets, so a "10 per minute" guard on
    # /login and /forgot-password was effectively ~30/minute (engineering
    # backlog 2.1). Defaults to the droplet's localhost Redis; a
    # RATELIMIT_STORAGE_URI in .env overrides. If Redis is down, fall back
    # to per-worker in-memory limiting — degraded protection, never a 500.
    RATELIMIT_STORAGE_URI = os.environ.get(
        'RATELIMIT_STORAGE_URI', 'redis://localhost:6379/0'
    )
    RATELIMIT_IN_MEMORY_FALLBACK_ENABLED = True
    # Disable Flask-WTF's SSL-strict *referrer* sub-check. On any HTTPS POST,
    # flask_wtf.csrf.CSRFProtect.protect() runs AFTER the token check and
    # additionally rejects the request unless the browser's Referer origin
    # matches https://<request.host>/ — its same_origin() compares the parsed
    # scheme, hostname, and port. Behind Cloudflare that comparison is
    # unreliable: request.host is proxy-driven (ProxyFix x_host=1) and
    # www-vs-apex, translated pages (*.translate.goog), and privacy/proxy
    # referrers all differ from it, producing "Bad Request — The referrer does
    # not match the host." on login and password reset (reported by a real user
    # 2026-08-21). This flag disables ONLY that referrer sub-check; the signed
    # CSRF token check — the submitted token validated against the value stored
    # in the session, the actual CSRF protection — stays fully active.
    WTF_CSRF_SSL_STRICT = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    # Pinned, not env-derived: the suite must never need a rate-limit service,
    # even on a machine whose .env points production at Redis.
    RATELIMIT_STORAGE_URI = 'memory://'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
