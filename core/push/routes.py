"""
core/push/routes.py
===================
The installable-app surface: the service worker, the web manifest, the /app
install-and-buzz page, and the subscribe / unsubscribe / test JSON endpoints.

    /app STATE DECISION (server half only; push.js decides device facts)
    --------------------------------------------------------------------
    GET /app
      ├── current_user anonymous → template shows "sign in first"
      └── current_user logged in → template shows the install steps + button
    (PR 2 builds the full eight-branch device-fact tree in push.js. PR 1 renders
    one template and lets push.js register the worker + wire the button.)

    SSRF GUARD on subscribe
    -----------------------
    The endpoint a browser hands us is a URL our server will later POST to. An
    attacker who could register an arbitrary endpoint could make the droplet POST
    into the private VPC. So subscribe accepts https:// only, and only to a known
    push-service host — anything else is a 400 and never stored.
"""
import hashlib
import logging
from urllib.parse import urlparse

from flask import (
    Response,
    jsonify,
    render_template,
    request,
)
from flask_login import current_user, login_required

from core.push import push_bp
from extensions import db, limiter
from models.push import PushSubscription
from utils.push import send_push_to_endpoint

logger = logging.getLogger(__name__)


def _json_dict():
    """Parsed JSON body as a dict, or {} for missing/empty/array/scalar bodies.

    A top-level JSON array or scalar is truthy, so `get_json(silent=True) or {}`
    would pass it straight to `.get()` and raise — reject it to {} here."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}

# Push-service hosts we will POST to. A security allowlist, deliberately a code
# constant (not env-overridable) so a bad env can never widen it. Windows uses a
# per-region subdomain of notify.windows.com, matched as a suffix.
_ALLOWED_PUSH_HOSTS = frozenset({
    'web.push.apple.com',
    'fcm.googleapis.com',
    'updates.push.services.mozilla.com',
})
_ALLOWED_PUSH_SUFFIX = '.notify.windows.com'


def _endpoint_ok(endpoint: str) -> bool:
    """True only for an https URL to a known push-service host (SSRF guard)."""
    if not endpoint or not isinstance(endpoint, str):
        return False
    try:
        parsed = urlparse(endpoint)
    except ValueError:
        return False
    if parsed.scheme != 'https' or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return host in _ALLOWED_PUSH_HOSTS or host.endswith(_ALLOWED_PUSH_SUFFIX)


def _test_endpoint_key() -> str:
    """Rate-limit key for /push/test: the sha256 of the posted endpoint, so the
    quota is per device — extensions.limiter keys on the client IP, and every
    phone on one household's Wi-Fi would otherwise share it."""
    endpoint = _json_dict().get('endpoint')
    if isinstance(endpoint, str) and endpoint:
        return 'pushtest:' + hashlib.sha256(endpoint.encode('utf-8')).hexdigest()
    return 'pushtest:' + (request.remote_addr or 'anon')


@push_bp.route('/app')
def app_page():
    """The install-and-buzz page. Anonymous callers see a sign-in prompt; the
    device-fact branching lives in push.js (PR 2 expands it)."""
    return render_template('push/app.html')


@push_bp.route('/sw.js')
def service_worker():
    """The push-only service worker, served from the root so its scope is '/'.

    ALWAYS no-cache: Cloudflare caches by .js extension and the after_request
    hook only stamps logged-in responses, but the browser fetches the worker
    without credentials, so nothing else would keep this fresh.
    """
    body = render_template('push/sw.js.j2')
    resp = Response(body, mimetype='application/javascript')
    resp.headers['Cache-Control'] = 'no-cache, max-age=0'
    # Allow a root scope even though the script is served from /sw.js.
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp


@push_bp.route('/manifest.webmanifest')
def manifest():
    """The web app manifest. Anonymous-accessible (fetched without credentials;
    a login redirect here breaks Add to Home Screen)."""
    body = render_template('push/manifest.webmanifest.j2')
    resp = Response(body, mimetype='application/manifest+json')
    resp.headers['Cache-Control'] = 'max-age=300'
    return resp


@push_bp.route('/push/subscribe', methods=['POST'])
@login_required
@limiter.limit('30 per minute')
def subscribe():
    """Store (or re-point) this device's push subscription for the current user.

    Ownership-following upsert lives on the model; this route validates the
    endpoint against the SSRF allowlist first.
    """
    data = _json_dict()
    endpoint = data.get('endpoint')
    keys = data.get('keys') or {}
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')

    if not _endpoint_ok(endpoint):
        logger.warning('Rejected push subscribe from user %s: bad endpoint host',
                       current_user.id)
        return jsonify({'ok': False, 'error': 'bad_endpoint'}), 400
    if not p256dh or not auth:
        return jsonify({'ok': False, 'error': 'missing_keys'}), 400

    PushSubscription.upsert(
        user_id=current_user.id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=request.headers.get('User-Agent', '')[:400] or None,
    )
    db.session.commit()
    return jsonify({'ok': True})


@push_bp.route('/push/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    """Delete only THIS device's row (other devices stay armed). Scoped to the
    current user so a guessed endpoint can't drop someone else's subscription."""
    endpoint = _json_dict().get('endpoint')
    # Idempotent by design: a missing endpoint is a no-op 200. Guard the type so
    # a non-string value can never reach the query as a bad bind param.
    if isinstance(endpoint, str) and endpoint:
        db.session.query(PushSubscription).filter_by(
            endpoint=endpoint, user_id=current_user.id).delete()
        db.session.commit()
    return jsonify({'ok': True})


@push_bp.route('/push/test', methods=['POST'])
@login_required
@limiter.limit('1 per minute', key_func=_test_endpoint_key)
def test_push():
    """Send the fixed 'This is the buzz.' push to ONE of the caller's own
    devices (the posted endpoint), so a member can confirm the buzz works."""
    data = _json_dict()
    endpoint = data.get('endpoint')
    if not endpoint:
        return jsonify({'ok': False, 'error': 'missing_endpoint'}), 400
    delivered = send_push_to_endpoint(
        current_user.id, endpoint,
        title='This is the buzz.',
        body='See you Saturday. Tap to come back.',
        url='/app',
        tag='test',
    )
    if delivered == 0:
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    return jsonify({'ok': True, 'delivered': delivered})
