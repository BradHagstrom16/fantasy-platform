"""CSRF SSL-strict referrer-check config lock.

Flask-WTF's ``CSRFProtect.protect()`` runs, on every HTTPS POST and *after*
the signed-token check, an additional referrer sub-check: it rejects the
request unless the browser's ``Referer`` origin byte-matches
``https://<request.host>/`` (flask_wtf/csrf.py, guarded by
``request.is_secure and WTF_CSRF_SSL_STRICT``). Behind Cloudflare that
comparison is unreliable — ``request.host`` is proxy-driven and www-vs-apex,
translated pages, and privacy/proxy referrers all differ from it — which is
what produced "Bad Request — The referrer does not match the host." on login
and password reset (real-user report 2026-08-21).

Production therefore disables ONLY that referrer sub-check. These tests lock
two things a future edit must not silently break:

- The referrer sub-check stays OFF in production (``WTF_CSRF_SSL_STRICT`` False).
- The cryptographic token check — the actual CSRF protection — stays ON
  (``WTF_CSRF_ENABLED`` True, inherited from base). Disabling the referrer
  check must never be mistaken for, or drift into, disabling CSRF wholesale.
"""
from config import Config, ProductionConfig, TestingConfig


def test_production_disables_ssl_strict_referrer_check():
    assert ProductionConfig.WTF_CSRF_SSL_STRICT is False


def test_production_keeps_token_csrf_enabled():
    # The token check is the real protection; only the referrer sub-check was
    # disabled. Prod inherits WTF_CSRF_ENABLED=True from base (never overrides).
    assert ProductionConfig.WTF_CSRF_ENABLED is True


def test_base_config_leaves_csrf_enabled_and_does_not_force_ssl_strict():
    # Base keeps CSRF on and does NOT set WTF_CSRF_SSL_STRICT, so dev (plain
    # http, request.is_secure False) never runs the referrer block regardless
    # of the Flask-WTF default. The False lives only on ProductionConfig.
    assert Config.WTF_CSRF_ENABLED is True
    assert 'WTF_CSRF_SSL_STRICT' not in vars(Config)


def test_testing_disables_csrf_entirely():
    # Documents why the referrer path can't be exercised through the test
    # client: CSRF is off wholesale under testing.
    assert TestingConfig.WTF_CSRF_ENABLED is False
