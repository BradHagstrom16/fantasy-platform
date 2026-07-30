"""
Client-IP rate-limit keying locks (engineering backlog 2.5).

Behind the live chain (client → Cloudflare → nginx → gunicorn), nginx's realip
module rewrites $remote_addr from CF-Connecting-IP when — and only when — the
TCP peer is a Cloudflare range (deploy/nginx.conf), so the LAST X-Forwarded-For
entry nginx appends is the real client. ProxyFix(x_for=1) in app.py selects it,
making request.remote_addr — and the Flask-Limiter key — the real client IP.

Three regressions these tests exist to catch:

1. The ProxyFix hop count drifting (x_for=2, or the wrap removed): a
   direct-to-origin request could then key the limiter on an attacker-chosen
   X-Forwarded-For entry (spoofed-DoS on someone else's bucket, or free
   evasion), because gunicorn sits behind a unix socket and the app can never
   validate header provenance itself.
2. The nginx realip block drifting or vanishing: rate-limit keys silently
   regress to Cloudflare edge IPs — shared buckets per CF PoP for every user
   routed through it (the pre-fix 2.5 bug, masked before 2.1's shared Redis).
3. The origin-cloak runbook's paste-ready CIDR block (backlog 2.6) drifting
   from the pinned list: a partial Cloudflare-range refresh would leave the
   DO firewall allowlist stale, which hard-blocks legitimate CF traffic.
"""
import ipaddress
import re
from pathlib import Path

from flask_limiter.util import get_remote_address

NGINX_CONF = Path(__file__).parent.parent / 'deploy' / 'nginx.conf'
RUNBOOK = (
    Path(__file__).parent.parent
    / 'docs' / 'superpowers' / 'plans' / '2026-07-30-origin-cloak-do-firewall.md'
)
_CF_BLOCK = re.compile(
    r'<!-- CF-RANGES-START -->\n(.*?)<!-- CF-RANGES-END -->', re.DOTALL
)

# Pinned copy of https://www.cloudflare.com/ips-v4 + /ips-v6 (fetched
# 2026-07-30). Must equal deploy/nginx.conf's set_real_ip_from list AND the
# origin-cloak runbook's marker block — refresh all three together (recipe in
# the nginx.conf realip comment; the live DO firewall is the fourth mirror,
# updated per the runbook).
CLOUDFLARE_RANGES = frozenset({
    '173.245.48.0/20',
    '103.21.244.0/22',
    '103.22.200.0/22',
    '103.31.4.0/22',
    '141.101.64.0/18',
    '108.162.192.0/18',
    '190.93.240.0/20',
    '188.114.96.0/20',
    '197.234.240.0/22',
    '198.41.128.0/17',
    '162.158.0.0/15',
    '104.16.0.0/13',
    '104.24.0.0/14',
    '172.64.0.0/13',
    '131.0.72.0/22',
    '2400:cb00::/32',
    '2606:4700::/32',
    '2803:f800::/32',
    '2405:b500::/32',
    '2405:8100::/32',
    '2a06:98c0::/29',
    '2c0f:f248::/32',
})


def _probe_client():
    from app import create_app
    app = create_app('testing')

    # Registered pre-first-request, so requests traverse the full WSGI stack
    # (including the ProxyFix wrap of app.wsgi_app) before hitting it.
    @app.get('/__ip_probe')
    def probe():
        return get_remote_address()  # exactly what the limiter's key_func sees

    return app.test_client()


class TestProxyFixKeyContract:
    def test_key_is_last_xff_entry(self):
        # nginx appends the realip-corrected client LAST; x_for=1 must take it
        # and ignore attacker-controlled leading entries.
        resp = _probe_client().get(
            '/__ip_probe',
            headers={'X-Forwarded-For': '203.0.113.66, 198.51.100.7'},
            environ_base={'REMOTE_ADDR': '10.0.0.1'},
        )
        assert resp.text == '198.51.100.7'

    def test_no_xff_falls_back_to_peer(self):
        resp = _probe_client().get(
            '/__ip_probe', environ_base={'REMOTE_ADDR': '10.0.0.1'}
        )
        assert resp.text == '10.0.0.1'


class TestLimiterWiring:
    def test_key_func_is_get_remote_address(self):
        from extensions import limiter

        # _key_func is private API — acceptable against the pinned
        # Flask-Limiter==4.1.1; re-check on any limiter upgrade.
        assert limiter._key_func is get_remote_address


class TestNginxRealipSourceLock:
    # Structural assumption: the file holds two server blocks, 80 then 443,
    # so "after the listen 443 line" == "inside the 443 block".

    def test_real_ip_header_cf_connecting_ip_exactly_once_in_443_block(self):
        src = NGINX_CONF.read_text()
        assert src.count('real_ip_header') == 1
        assert 'real_ip_header CF-Connecting-IP;' in src
        assert src.index('listen 443') < src.index('real_ip_header')

    def test_set_real_ip_from_ranges_match_pinned_list(self):
        src = NGINX_CONF.read_text()
        found = re.findall(r'^\s*set_real_ip_from\s+(\S+);', src, re.MULTILINE)
        assert len(found) == len(set(found))  # no duplicates
        assert set(found) == set(CLOUDFLARE_RANGES)
        assert src.index('listen 443') < src.index('set_real_ip_from')

    def test_pinned_ranges_are_valid_cidr(self):
        for cidr in CLOUDFLARE_RANGES:
            ipaddress.ip_network(cidr)  # raises on any typo

    def test_xff_proxy_header_still_appends(self):
        # Everything rides on append semantics: the realip-corrected
        # $remote_addr must land as the LAST X-Forwarded-For entry.
        src = NGINX_CONF.read_text()
        assert re.search(
            r'proxy_set_header\s+X-Forwarded-For\s+\$proxy_add_x_forwarded_for;',
            src,
        )


class TestFirewallRunbookRangeSync:
    """Backlog 2.6: the DO-firewall runbook's paste-ready CIDR block must
    equal the pinned CF list (which the nginx source lock above already ties
    to deploy/nginx.conf). Guards repo-side drift; the live firewall itself
    is dashboard state no test can see — see the runbook's refresh recipe.
    """

    def _runbook_ranges(self):
        m = _CF_BLOCK.search(RUNBOOK.read_text())
        assert m, 'CF-RANGES markers missing from origin-cloak runbook'
        return [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]

    def test_runbook_block_is_unique_valid_cidrs(self):
        found = self._runbook_ranges()
        assert len(found) == len(set(found))
        for cidr in found:
            ipaddress.ip_network(cidr)  # raises on any typo

    def test_runbook_ranges_match_pinned_list(self):
        assert frozenset(self._runbook_ranges()) == CLOUDFLARE_RANGES
