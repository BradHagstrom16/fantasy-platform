"""X-Forwarded-Host pinning locks (post-#166 host hardening).

Behind the live chain (client → Cloudflare → nginx → gunicorn), nginx pins the
X-Forwarded-Host header to the canonical apex, and the app's ProxyFix(x_host=1)
drives request.host from it. Together they make request.host deterministic no
matter which host the visitor arrived on (apex, www, a translated/proxy host),
which:

  - removes the www-vs-apex referrer/host mismatch that produced the #166
    "The referrer does not match the host." login/reset failures, and
  - keeps every url_for(_external=True) — notably the emailed password-reset
    link — on the canonical apex.

Two regressions these tests exist to catch:

1. ProxyFix's x_host hop dropping (x_host=0 or the wrap changing): request.host
   would fall back to the raw Host header and again reflect www-vs-apex.
2. The nginx X-Forwarded-Host pin drifting or vanishing: nothing would normalize
   the forwarded host at the edge and ProxyFix would trust whatever Cloudflare
   forwarded.

The repo copy of deploy/nginx.conf uses the placeholder `yourdomain.com`; the
install-time domain substitution rewrites it to the real apex (see the file
header). So these locks assert the placeholder form, exactly as the realip
locks in tests/test_client_ip_keying.py do.
"""
import re
from pathlib import Path

NGINX_CONF = Path(__file__).parent.parent / 'deploy' / 'nginx.conf'


def _host_probe_client():
    from app import create_app
    app = create_app('testing')

    # Registered pre-first-request so requests traverse the full WSGI stack,
    # including the ProxyFix wrap of app.wsgi_app, before reaching this route.
    @app.get('/__host_probe')
    def probe():
        from flask import request
        return request.host

    return app.test_client()


class TestProxyFixHostContract:
    def test_x_forwarded_host_drives_request_host(self):
        # ProxyFix(x_host=1) must prefer X-Forwarded-Host over the raw Host, so
        # nginx's pinned apex value wins even when the visitor used www.
        resp = _host_probe_client().get(
            '/__host_probe',
            headers={
                'Host': 'www.cccfantasy.com',
                'X-Forwarded-Host': 'cccfantasy.com',
            },
        )
        assert resp.text == 'cccfantasy.com'

    def test_no_x_forwarded_host_falls_back_to_host(self):
        # Sanity: without the header, request.host is just the Host — so it is
        # the pin, not ProxyFix, that normalizes www-vs-apex.
        resp = _host_probe_client().get(
            '/__host_probe', headers={'Host': 'www.cccfantasy.com'}
        )
        assert resp.text == 'www.cccfantasy.com'


class TestNginxForwardedHostPinLock:
    # Structural assumption (shared with test_client_ip_keying.py): the file
    # holds two server blocks, 80 then 443, so "after the listen 443 line" ==
    # "inside the 443 block".

    def test_x_forwarded_host_pinned_in_443_block(self):
        src = NGINX_CONF.read_text()
        m = re.search(
            r'proxy_set_header\s+X-Forwarded-Host\s+(\S+);', src
        )
        assert m, 'nginx must pin X-Forwarded-Host in the proxy block'
        assert src.index('listen 443') < m.start()

    def test_x_forwarded_host_is_the_bare_apex_placeholder(self):
        # Pinned to a single static host (the install substitutes the real
        # apex for `yourdomain.com`) — never $host (would echo www-vs-apex)
        # and never a www-prefixed value.
        src = NGINX_CONF.read_text()
        value = re.search(
            r'proxy_set_header\s+X-Forwarded-Host\s+(\S+);', src
        ).group(1)
        assert value == 'yourdomain.com'
        assert not value.startswith('$')
        assert not value.startswith('www.')
