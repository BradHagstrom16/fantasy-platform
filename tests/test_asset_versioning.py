"""Regression locks for `infra/asset-versioning` (PR #19 follow-up to PR #18).

Background: PR #18's CSS changes didn't reach users through Cloudflare
because nginx serves `/static/` with `Cache-Control: public, immutable`
under a 30-day TTL. Filename-stable asset URLs (e.g., `style.css`) made
the immutable directive a liability — edge caches and browsers honored
"this URL's bytes never change" for up to 30 days after each deploy.

Fix: cache-bust every CSS/JS asset URL with `?v={{ asset_version }}`,
where `asset_version` is the git short SHA resolved once at app-factory
init. Bytes-at-this-URL really are immutable now — every deploy gets a
new SHA, every SHA gets a new URL, every URL fetches fresh.

These tests assert:
- The helper resolves a non-empty token across all three fallback paths
  (env override → git SHA → 'dev').
- The context processor injects `asset_version` into every Jinja render.
- The rendered HTML on `/` carries `?v=<non-empty>` on both CSS link tags
  and on the countdown JS tag (pre-state only).
"""
import os
import subprocess
from unittest import mock

import pytest

from core.context import _compute_asset_version

# ---------------------------------------------------------------------------
# _compute_asset_version: resolution-order locks.
# ---------------------------------------------------------------------------


def test_helper_returns_env_var_when_set():
    """`ASSET_VERSION` env var beats the git lookup. Useful for tests,
    CI pinning, or non-git deploys (Docker image with stripped .git)."""
    with mock.patch.dict(os.environ, {'ASSET_VERSION': 'release-2026-05-13'}):
        assert _compute_asset_version() == 'release-2026-05-13'


def test_helper_strips_whitespace_in_env_var():
    """Whitespace-only env var values fall through to the next strategy
    (don't render a blank `?v=` param)."""
    with mock.patch.dict(os.environ, {'ASSET_VERSION': '   '}):
        v = _compute_asset_version()
        assert v != '', "blank env var must fall through, not return empty"


def test_helper_returns_git_sha_when_env_absent():
    """In the test environment `git rev-parse --short HEAD` succeeds and
    returns a short SHA (typically 7 hex chars). The exact value floats
    with HEAD, so the lock checks shape, not value."""
    env_without_override = {k: v for k, v in os.environ.items() if k != 'ASSET_VERSION'}
    with mock.patch.dict(os.environ, env_without_override, clear=True):
        v = _compute_asset_version()
    assert v, "git SHA path returned empty"
    assert v != 'dev', (
        f"helper fell through to 'dev' in pytest context — git lookup "
        f"should succeed. Got: {v!r}"
    )
    # A short SHA is 4-40 hex chars (git config core.abbrev defaults to 7).
    assert all(c in '0123456789abcdef' for c in v), (
        f"git SHA path returned non-hex string: {v!r}"
    )


def test_helper_falls_back_to_dev_when_git_unavailable():
    """If `git rev-parse` fails (subprocess error, git binary missing,
    repo absent), the helper returns the literal `'dev'` so templates
    never render `?v=` alone. The `'dev'` token is itself a cache-bust
    on first-ever deploy — subsequent deploys get real SHAs."""
    env_without_override = {k: v for k, v in os.environ.items() if k != 'ASSET_VERSION'}
    with mock.patch.dict(os.environ, env_without_override, clear=True), \
         mock.patch('core.context.subprocess.check_output',
                    side_effect=subprocess.CalledProcessError(128, 'git')):
        assert _compute_asset_version() == 'dev'


def test_helper_falls_back_to_dev_when_subprocess_returns_empty():
    """A subprocess that exits 0 but yields empty stdout (degenerate
    repo state) also routes to `'dev'` rather than blank."""
    env_without_override = {k: v for k, v in os.environ.items() if k != 'ASSET_VERSION'}
    with mock.patch.dict(os.environ, env_without_override, clear=True), \
         mock.patch('core.context.subprocess.check_output', return_value=b'  \n'):
        assert _compute_asset_version() == 'dev'


# ---------------------------------------------------------------------------
# Context processor: `asset_version` injected into every render.
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    from app import create_app
    from extensions import db
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app


def test_context_processor_injects_asset_version(app):
    """The `inject_asset_version` processor must be registered and put
    a non-empty `asset_version` token into Jinja context."""
    with app.test_request_context('/'):
        from flask import render_template_string
        rendered = render_template_string('{{ asset_version }}')
    assert rendered, "asset_version context variable missing or empty"
    assert rendered != '<empty>', "asset_version rendered as a placeholder"


# ---------------------------------------------------------------------------
# Rendered HTML: `?v=<token>` on CSS + JS asset links.
# ---------------------------------------------------------------------------


def test_rendered_home_carries_versioned_css_links(app):
    """The logged-out home must serve both CSS link tags with
    `?v=<non-empty>` query strings. Without these, Cloudflare's 30-day
    immutable cache silently swallows future CSS deploys."""
    with app.test_client() as c:
        resp = c.get('/')
        body = resp.data.decode('utf-8')

    import re
    # Each CSS file must appear exactly once with a non-empty ?v=.
    for css in ('tokens.css', 'style.css'):
        pattern = re.compile(
            rf'<link\s+rel="stylesheet"\s+href="[^"]*{re.escape(css)}\?v=([^"&]+)"'
        )
        match = pattern.search(body)
        assert match, (
            f"`/static/css/{css}` missing or not versioned in rendered "
            f"home page. Cloudflare's immutable cache will swallow future "
            f"deploys of this asset without the `?v=` cache-bust."
        )
        token = match.group(1)
        assert token, f"`{css}` rendered with empty `?v=` (cache-bust no-op)"
        assert token != '{{', (
            f"`{css}` rendered with raw Jinja `{{{{ asset_version }}}}` — "
            f"the context processor isn't injecting the variable into "
            f"this surface."
        )


def test_countdown_js_carries_asset_version_in_template_source():
    """`countdown.js` only loads on pre-state homes (`{% if state == 'pre' %}`
    inside `core/main/templates/main/index.html`). Logged-out and live/post
    states never include it, so the rendered-HTML test in the suite above
    can't reach it via an anonymous test request. Source-pattern lock
    instead: the script tag must annotate `?v={{ asset_version }}` so
    that whenever the pre-state include fires, the cache-bust travels
    with it. The CSS rendered-HTML tests above prove the context
    processor is correctly wired into `base.html`; this test just locks
    the Jinja annotation in `index.html`'s scripts block."""
    from pathlib import Path
    src = Path(__file__).parent.parent / 'core' / 'main' / 'templates' / 'main' / 'index.html'
    text = src.read_text()
    import re
    pattern = re.compile(
        r'<script\s+src="\{\{\s*url_for\(\'static\',\s*filename=\'js/countdown\.js\'\)\s*\}\}'
        r'\?v=\{\{\s*asset_version\s*\}\}"'
    )
    assert pattern.search(text), (
        "`countdown.js` script tag in `index.html` missing the "
        "`?v={{ asset_version }}` cache-bust annotation. A stale cached "
        "countdown breaks the live deadline tick silently."
    )


# ---------------------------------------------------------------------------
# Rendered HTML: `?v=<token>` on brand-image (logo / favicon / seal) URLs.
#
# PR #48 swapped the logo files in place (same filenames, new bytes). The
# brand `<img>`/`<link>` tags carried no `?v=` cache-bust — they relied on a
# "rename the file if ever swapped" convention that the swap didn't follow.
# nginx's 30-day `immutable` directive + Cloudflare's edge then served the OLD
# logo for up to 30 days post-deploy: the new designer mark was on the origin
# (verified by hash) but never reached browsers. Fix: brand images now follow
# the same `?v={{ asset_version }}` policy as CSS/JS, so every deploy's new SHA
# mints a fresh URL that busts the edge automatically. These locks assert it.
# ---------------------------------------------------------------------------


BRAND_IMAGE_PATHS = [
    'img/logo/favicon.svg',         # favicon <link> + navbar brand <img>
    'img/favicon.ico',              # legacy favicon fallback
    'img/apple-touch-icon-180.png', # iOS home-screen tile
    'img/logo/seal-color.svg',      # footer roundel seal
    'img/logo/mascot-bust.svg',     # auth brand panel hero (login/register/forgot/reset)
    'img/logo/wordmark-bone.svg',   # navbar designed wordmark (all widths; CSS hides ≤350px)
]


@pytest.mark.parametrize('path', BRAND_IMAGE_PATHS)
def test_rendered_base_brand_images_are_versioned(app, path):
    """Every brand-image URL in base.html (favicons, navbar mark, footer seal)
    must render with a non-empty `?v=<token>` cache-bust. `/login` is anonymous
    and extends base.html, so its <head> favicons, navbar brand, and footer seal
    all render. Without the cache-bust, a swapped logo (same filename) is frozen
    behind Cloudflare's 30-day immutable edge cache (PR #48 fallout)."""
    import re
    with app.test_client() as c:
        body = c.get('/login').data.decode('utf-8')

    static_path = f'/static/{path}'
    bare = body.count(static_path)
    assert bare >= 1, f'{static_path} not found in rendered base.html'
    versioned = re.findall(re.escape(static_path) + r'\?v=([^"&]+)', body)
    assert len(versioned) == bare, (
        f'{static_path} appears {bare}x but only {len(versioned)} carry `?v=`. '
        f'Every brand-image URL must be cache-busted or a swapped logo is frozen '
        f'behind the 30-day immutable cache (PR #48 fallout).'
    )
    for token in versioned:
        assert token and token != '{{', (
            f'{static_path} rendered with empty/raw `?v=` — asset_version '
            f'not injected into this surface.'
        )


def test_reset_email_seal_is_versioned(app):
    """The password-reset email's seal must also carry `?v=<token>` so a swapped
    `seal-email.png` reaches newly-sent emails through Cloudflare's immutable
    edge. `asset_version` is in scope because context processors run on the
    `render_template` call inside the request-bound forgot-password route."""
    import re
    from unittest import mock

    from extensions import db
    from models.user import User

    with app.app_context():
        u = User(username='av_seal_user', email='av_seal@test.com')
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()

    with app.test_client() as c, \
         mock.patch('core.auth.routes.send_platform_email') as send:
        c.post('/forgot-password',
               data={'email': 'av_seal@test.com', 'csrf_token': 'x'})

    assert send.called, 'send_platform_email was not called'
    html = send.call_args.args[3]  # signature: send(to, subject, plain, html)
    m = re.search(r'/static/img/logo/seal-email\.png\?v=([^"&]+)', html)
    assert m, (
        'reset-email seal missing `?v=` cache-bust — a swapped seal-email.png '
        'would be frozen behind the immutable edge for new emails too.'
    )
    assert m.group(1) and m.group(1) != '{{', (
        'reset-email seal rendered with empty/raw `?v=` — asset_version not '
        'injected into the email render context.'
    )


def test_navbar_brand_has_wordmark_and_accessible_name(app):
    """Navbar brand swaps the Teko CSS text for the designed bone wordmark image,
    and the brand link keeps a stable accessible name at every viewport via
    aria-label (both images are decorative alt='')."""
    with app.test_client() as c:
        body = c.get('/login').data.decode('utf-8')
    assert 'img/logo/wordmark-bone.svg' in body, "navbar wordmark image missing"
    assert 'aria-label="Corrupt Commish Club"' in body, (
        "navbar brand link lost its accessible name — the wordmark is hidden "
        "at ≤350px widths, so the <a> needs aria-label or ultra-narrow-screen "
        "users get no brand name"
    )
