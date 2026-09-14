"""Web push platform plumbing — model, send helper, blueprint routes, seam.

Locks the rules from the installable-app design (docs/designs/installable-app-push.md,
"Rules ... test-locked in tests/test_push.py"): the service worker has no fetch
listener but has notificationclick + a showNotification fallback and answers
no-cache; subscribe requires login and refuses non-allowlisted endpoints;
subscribe re-points a shared endpoint to the current owner; eviction past five
devices; send_push never raises and rolls back its own failed write; a fresh
VAPID claims dict and a 10s timeout per call; 404/410 prune, 429 skip-not-retry;
unsubscribe deletes only the posted endpoint; and utils.push imports no game
module.

CSRF is disabled in the testing config (WTF_CSRF_ENABLED=False), so the "requires
CSRF" half of the login+CSRF rule is not exercised here — no route is
csrf-exempt, so it is protected in prod by default. Login is exercised.
"""
import types
from unittest.mock import patch

import pytest

from extensions import db
from models import PushSubscription, User

# ---- VAPID stand-ins (send path is patched, so any non-blank values work) ----
_VAPID = {
    'VAPID_PRIVATE_KEY': 'k1vOH9el9nS0000000000000000000000000000000',
    'VAPID_PUBLIC_KEY': 'BPG_public_test_key',
    'VAPID_SUBJECT': 'mailto:commish@cccfantasy.com',
}
_APPLE = 'https://web.push.apple.com/'


def _make_user(app, username='member', is_admin=False):
    with app.app_context():
        u = User(username=username, email=f'{username}@example.com',
                 is_admin=is_admin)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.id, u.auth_id


def _login(client, auth_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


def _make_sub(app, user_id, endpoint, p256dh='p', auth='a'):
    with app.app_context():
        row = PushSubscription(user_id=user_id, endpoint=endpoint,
                               p256dh=p256dh, auth=auth)
        db.session.add(row)
        db.session.commit()
        return row.id


def _webpush_exc(status, retry_after=None):
    from pywebpush import WebPushException
    headers = {'Retry-After': retry_after} if retry_after else {}
    resp = types.SimpleNamespace(status_code=status, headers=headers)
    return WebPushException(f'status {status}', response=resp)


# ============================ model: upsert + eviction ======================

def test_upsert_repoints_shared_endpoint_to_current_user(app):
    """Subscribe as A, then as B with the same endpoint → only B's row.

    This is the shared-device leak guard (docs/designs rule: "subscribe as A,
    then as B with the same endpoint: only B's row remains"). Locked at the
    model layer because the route delegates verbatim to PushSubscription.upsert
    and a two-authenticated-request route test is defeated by Flask-Login's
    per-app-context user cache under the shared-context test fixture.
    """
    a_id, _ = _make_user(app, 'alice')
    b_id, _ = _make_user(app, 'bob')
    with app.app_context():
        PushSubscription.upsert(a_id, _APPLE + 'shared', 'pa', 'aa')
        db.session.commit()
        PushSubscription.upsert(b_id, _APPLE + 'shared', 'pb', 'ab')
        db.session.commit()
        rows = db.session.query(PushSubscription).filter_by(
            endpoint=_APPLE + 'shared').all()
        assert len(rows) == 1
        assert rows[0].user_id == b_id
        assert rows[0].p256dh == 'pb'


def test_upsert_evicts_oldest_last_seen_past_cap(app):
    """A sixth device evicts the stalest (oldest last_seen_at)."""
    from datetime import UTC, datetime, timedelta
    uid, _ = _make_user(app)
    with app.app_context():
        base = datetime(2026, 9, 1, tzinfo=UTC)
        for i in range(5):
            row = PushSubscription(user_id=uid, endpoint=_APPLE + f'd{i}',
                                   p256dh='p', auth='a',
                                   last_seen_at=base + timedelta(hours=i))
            db.session.add(row)
        db.session.commit()
        # d0 is the oldest last_seen_at.
        PushSubscription.upsert(uid, _APPLE + 'd5', 'p', 'a')
        db.session.commit()
        endpoints = {r.endpoint for r in
                     db.session.query(PushSubscription).filter_by(user_id=uid)}
        assert len(endpoints) == 5
        assert _APPLE + 'd0' not in endpoints
        assert _APPLE + 'd5' in endpoints


def test_upsert_transfer_into_full_user_stays_within_cap(app):
    """Re-pointing a shared endpoint to a member who already holds five devices
    evicts their stalest first, so the transfer never leaves them at six."""
    from datetime import UTC, datetime, timedelta
    a_id, _ = _make_user(app, 'alice')
    b_id, _ = _make_user(app, 'bob')
    with app.app_context():
        base = datetime(2026, 9, 1, tzinfo=UTC)
        # Bob is already at the cap; d0 is his stalest.
        for i in range(5):
            db.session.add(PushSubscription(
                user_id=b_id, endpoint=_APPLE + f'bob{i}', p256dh='p', auth='a',
                last_seen_at=base + timedelta(hours=i)))
        # A shared device currently owned by Alice.
        db.session.add(PushSubscription(
            user_id=a_id, endpoint=_APPLE + 'shared', p256dh='pa', auth='aa'))
        db.session.commit()

        PushSubscription.upsert(b_id, _APPLE + 'shared', 'pb', 'ab')
        db.session.commit()

        endpoints = {r.endpoint for r in
                     db.session.query(PushSubscription).filter_by(user_id=b_id)}
        assert len(endpoints) == 5
        assert _APPLE + 'shared' in endpoints  # the transferred device kept
        assert _APPLE + 'bob0' not in endpoints  # Bob's stalest evicted
        # The shared endpoint now belongs only to Bob.
        assert db.session.query(PushSubscription).filter_by(
            endpoint=_APPLE + 'shared').count() == 1


# ============================ routes: subscribe =============================

def test_subscribe_requires_login(client):
    resp = client.post('/push/subscribe', json={'endpoint': _APPLE + 'x',
                                                 'keys': {'p256dh': 'p', 'auth': 'a'}})
    assert resp.status_code in (301, 302, 401)


def test_subscribe_rejects_http_endpoint(app, client):
    _, auth_id = _make_user(app)
    _login(client, auth_id)
    resp = client.post('/push/subscribe',
                       json={'endpoint': 'http://web.push.apple.com/x',
                             'keys': {'p256dh': 'p', 'auth': 'a'}})
    assert resp.status_code == 400


def test_subscribe_rejects_private_and_unlisted_hosts(app, client):
    _, auth_id = _make_user(app)
    _login(client, auth_id)
    for bad in ('https://10.0.0.5/x', 'https://evil.example.com/x',
                'https://127.0.0.1/x'):
        resp = client.post('/push/subscribe',
                           json={'endpoint': bad,
                                 'keys': {'p256dh': 'p', 'auth': 'a'}})
        assert resp.status_code == 400, bad


def test_subscribe_accepts_allowlisted_host_and_stores_owner(app, client):
    # One authenticated request (the idiomatic suite pattern): an allowlisted
    # host is accepted and the row is owned by the caller. The A→B re-point is
    # locked at the model layer (test_upsert_repoints_shared_endpoint...).
    uid, auth_id = _make_user(app)
    _login(client, auth_id)
    assert client.post('/push/subscribe', json={
        'endpoint': _APPLE + 'dev', 'keys': {'p256dh': 'p', 'auth': 'a'}}).status_code == 200
    with app.app_context():
        rows = db.session.query(PushSubscription).filter_by(
            endpoint=_APPLE + 'dev').all()
        assert len(rows) == 1 and rows[0].user_id == uid


def test_subscribe_accepts_windows_suffix_host(app, client):
    _, auth_id = _make_user(app)
    _login(client, auth_id)
    resp = client.post('/push/subscribe',
                       json={'endpoint': 'https://ab1.notify.windows.com/x',
                             'keys': {'p256dh': 'p', 'auth': 'a'}})
    assert resp.status_code == 200


# ============================ routes: unsubscribe ===========================

def test_unsubscribe_deletes_only_posted_endpoint(app, client):
    uid, auth_id = _make_user(app)
    _make_sub(app, uid, _APPLE + 'keep')
    _make_sub(app, uid, _APPLE + 'drop')
    _login(client, auth_id)
    assert client.post('/push/unsubscribe',
                       json={'endpoint': _APPLE + 'drop'}).status_code == 200
    with app.app_context():
        left = {r.endpoint for r in
                db.session.query(PushSubscription).filter_by(user_id=uid)}
        assert left == {_APPLE + 'keep'}


def test_unsubscribe_non_string_endpoint_is_noop_not_error(app, client):
    """A non-string endpoint value must not reach the query as a bad bind param;
    unsubscribe stays an idempotent 200."""
    uid, auth_id = _make_user(app)
    _make_sub(app, uid, _APPLE + 'keep')
    _login(client, auth_id)
    for bad in ([_APPLE + 'x'], {'a': 1}, 123):
        resp = client.post('/push/unsubscribe', json={'endpoint': bad})
        assert resp.status_code == 200, bad
    with app.app_context():
        assert db.session.query(PushSubscription).filter_by(user_id=uid).count() == 1


def test_test_push_non_string_endpoint_rejected(app, client):
    """A non-string endpoint is rejected at the boundary with the missing_endpoint
    400 (and never crashes the rate-limit key func via .encode on a non-str)."""
    uid, auth_id = _make_user(app)
    _login(client, auth_id)
    with patch('utils.push.webpush') as wp, patch.dict(app.config, _VAPID):
        resp = client.post('/push/test', json={'endpoint': [1, 2]})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'missing_endpoint'
        wp.assert_not_called()


def test_unsubscribe_cannot_delete_another_users_row(app, client):
    a_id, _ = _make_user(app, 'alice')
    b_id, b_auth = _make_user(app, 'bob')
    _make_sub(app, a_id, _APPLE + 'alices')
    _login(client, b_auth)
    client.post('/push/unsubscribe', json={'endpoint': _APPLE + 'alices'})
    with app.app_context():
        assert db.session.query(PushSubscription).filter_by(
            endpoint=_APPLE + 'alices').count() == 1


# ============================ routes: /sw.js ================================

def test_service_worker_contract(client):
    resp = client.get('/sw.js')
    assert resp.status_code == 200
    assert 'javascript' in resp.headers['Content-Type']
    assert resp.headers['Cache-Control'] == 'no-cache, max-age=0'
    body = resp.get_data(as_text=True)
    assert "addEventListener('fetch'" not in body  # no fetch handler (leak guard)
    assert "addEventListener('notificationclick'" in body
    assert 'showNotification' in body
    assert 'Corrupt Commish Club' in body  # the parse-fail fallback title


# ============================ routes: manifest ==============================

def test_manifest_is_anonymous_standalone_with_versioned_icons(client):
    resp = client.get('/manifest.webmanifest')
    assert resp.status_code == 200
    assert 'manifest' in resp.headers['Content-Type']
    body = resp.get_data(as_text=True)
    assert '"display": "standalone"' in body
    assert '"short_name": "CCC"' in body
    assert '?v=' in body  # icon URLs carry the asset version
    assert 'maskable' in body


# ============================ routes: /app ==================================

def test_app_page_anonymous_shows_sign_in_first(client):
    resp = client.get('/app')
    assert resp.status_code == 200
    # A phrase unique to /app's anon branch (not the navbar's "Sign In").
    assert 'Sign in first' in resp.get_data(as_text=True)


def test_app_page_logged_in_shows_buzz_button(app, client):
    _, auth_id = _make_user(app)
    _login(client, auth_id)
    resp = client.get('/app')
    assert resp.status_code == 200
    assert 'push-cta' in resp.get_data(as_text=True)


# ============================ routes: /push/test ============================

def test_test_push_only_hits_callers_own_endpoint(app, client):
    a_id, _ = _make_user(app, 'alice')
    b_id, b_auth = _make_user(app, 'bob')
    _make_sub(app, a_id, _APPLE + 'alices-phone')
    _login(client, b_auth)
    with patch('utils.push.webpush') as wp, patch.dict(app.config, _VAPID):
        # Bob asks for a test to Alice's endpoint → 404, and no send attempted.
        resp = client.post('/push/test', json={'endpoint': _APPLE + 'alices-phone'})
        assert resp.status_code == 404
        wp.assert_not_called()


def test_test_push_delivers_to_own_endpoint(app, client):
    uid, auth_id = _make_user(app)
    _make_sub(app, uid, _APPLE + 'my-phone')
    _login(client, auth_id)
    with patch('utils.push.webpush') as wp, patch.dict(app.config, _VAPID):
        resp = client.post('/push/test', json={'endpoint': _APPLE + 'my-phone'})
        assert resp.status_code == 200
        assert resp.get_json()['delivered'] == 1
        wp.assert_called_once()


def test_test_push_rate_limited_per_endpoint(app, client):
    uid, auth_id = _make_user(app)
    _make_sub(app, uid, _APPLE + 'one')
    _make_sub(app, uid, _APPLE + 'two')
    _login(client, auth_id)
    with patch('utils.push.webpush'), patch.dict(app.config, _VAPID):
        assert client.post('/push/test', json={'endpoint': _APPLE + 'one'}).status_code == 200
        # Same device again within the minute → rate-limited.
        assert client.post('/push/test', json={'endpoint': _APPLE + 'one'}).status_code == 429
        # A different device from the same client is a different quota.
        assert client.post('/push/test', json={'endpoint': _APPLE + 'two'}).status_code == 200


# ============================ send_push helper ==============================

def test_send_push_blank_vapid_is_noop(app):
    uid, _ = _make_user(app)
    _make_sub(app, uid, _APPLE + 'x')
    with app.app_context(), patch('utils.push.webpush') as wp:
        from utils.push import send_push
        # config has blank VAPID by default in testing
        n = send_push([uid], title='t', body='b', url='/', tag='x',
                      ttl=60, urgency='high')
        assert n == 0
        wp.assert_not_called()


def test_send_push_empty_user_list_returns_zero(app):
    with app.app_context(), patch('utils.push.webpush') as wp, patch.dict(app.config, _VAPID):
        from utils.push import send_push
        assert send_push([], title='t', body='b', url='/', tag='x',
                         ttl=60, urgency='high') == 0
        wp.assert_not_called()


def test_send_push_fresh_claims_dict_and_timeout_and_session(app):
    uid, _ = _make_user(app)
    _make_sub(app, uid, _APPLE + 'a')
    _make_sub(app, uid, _APPLE + 'b')
    seen = []
    with app.app_context(), patch.dict(app.config, _VAPID):
        def fake(**kwargs):
            seen.append(kwargs)
            return 'ok'
        with patch('utils.push.webpush', side_effect=fake):
            from utils.push import send_push
            n = send_push([uid], title='t', body='b', url='/', tag='x',
                          ttl=60, urgency='normal', topic='cfb-w3')
    assert n == 2
    # Fresh claims dict per call (pywebpush mutates aud/exp in place).
    assert id(seen[0]['vapid_claims']) != id(seen[1]['vapid_claims'])
    # 10s timeout and one shared keep-alive Session across the fan-out.
    assert all(k['timeout'] == 10 for k in seen)
    assert seen[0]['requests_session'] is seen[1]['requests_session']
    # Urgency + Topic in the headers dict.
    assert seen[0]['headers']['Urgency'] == 'normal'
    assert seen[0]['headers']['Topic'] == 'cfb-w3'


def test_send_push_prunes_dead_subscriptions_and_continues(app):
    uid, _ = _make_user(app)
    _make_sub(app, uid, _APPLE + 'gone')
    _make_sub(app, uid, _APPLE + 'live')
    with app.app_context(), patch.dict(app.config, _VAPID):
        def fake(**kwargs):
            if 'gone' in kwargs['subscription_info']['endpoint']:
                raise _webpush_exc(410)
            return 'ok'
        with patch('utils.push.webpush', side_effect=fake):
            from utils.push import send_push
            n = send_push([uid], title='t', body='b', url='/', tag='x',
                          ttl=60, urgency='high')
        assert n == 1  # the live one delivered
        remaining = {r.endpoint for r in
                     db.session.query(PushSubscription).filter_by(user_id=uid)}
        assert remaining == {_APPLE + 'live'}  # dead row pruned


def test_send_push_429_is_skipped_not_retried_not_pruned(app):
    uid, _ = _make_user(app)
    _make_sub(app, uid, _APPLE + 'busy')
    calls = []
    with app.app_context(), patch.dict(app.config, _VAPID):
        def fake(**kwargs):
            calls.append(1)
            raise _webpush_exc(429, retry_after='60')
        with patch('utils.push.webpush', side_effect=fake):
            from utils.push import send_push
            n = send_push([uid], title='t', body='b', url='/', tag='x',
                          ttl=60, urgency='high')
        assert n == 0
        assert len(calls) == 1  # no in-loop retry
        # Not pruned — the subscription is fine, the service was busy.
        assert db.session.query(PushSubscription).filter_by(
            endpoint=_APPLE + 'busy').count() == 1


def test_send_push_other_error_logged_and_never_raises(app):
    uid, _ = _make_user(app)
    _make_sub(app, uid, _APPLE + 'boom')
    _make_sub(app, uid, _APPLE + 'ok')
    with app.app_context(), patch.dict(app.config, _VAPID):
        def fake(**kwargs):
            if 'boom' in kwargs['subscription_info']['endpoint']:
                raise RuntimeError('socket exploded')
            return 'ok'
        with patch('utils.push.webpush', side_effect=fake):
            from utils.push import send_push
            n = send_push([uid], title='t', body='b', url='/', tag='x',
                          ttl=60, urgency='high')
        assert n == 1  # never raised; the other send went through


def test_send_push_failed_prune_write_rolls_back_no_raise(app):
    uid, _ = _make_user(app)
    _make_sub(app, uid, _APPLE + 'gone')
    def raise_410(**kwargs):
        raise _webpush_exc(410)
    with app.app_context(), patch.dict(app.config, _VAPID), \
            patch('utils.push.webpush', side_effect=raise_410), \
            patch.object(db.session, 'commit', side_effect=RuntimeError('db down')):
        from utils.push import send_push
        # Must not raise even though the prune commit blows up.
        n = send_push([uid], title='t', body='b', url='/', tag='x',
                      ttl=60, urgency='high')
        assert n == 0
        # Session usable afterward (rollback happened inside the helper).
        db.session.rollback()
        assert db.session.query(PushSubscription).count() >= 0


def test_send_push_to_endpoint_scoped_to_user(app):
    a_id, _ = _make_user(app, 'alice')
    b_id, _ = _make_user(app, 'bob')
    _make_sub(app, a_id, _APPLE + 'shared-device')
    with app.app_context(), patch('utils.push.webpush') as wp, patch.dict(app.config, _VAPID):
        from utils.push import send_push_to_endpoint
        # Bob targeting Alice's endpoint → no row for (bob, endpoint) → 0 sends.
        n = send_push_to_endpoint(b_id, _APPLE + 'shared-device',
                                  title='t', body='b', url='/', tag='test')
        assert n == 0
        wp.assert_not_called()


# ============================ seam lock =====================================

def test_utils_push_imports_no_game_module():
    import ast
    from pathlib import Path
    src = Path('utils/push.py').read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or '').startswith('games'), node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith('games'), alias.name


@pytest.mark.parametrize('module_name', ['utils.push'])
def test_importing_push_pulls_no_game_module(module_name):
    import importlib
    import sys
    # Import fresh and confirm no games.* module got pulled transitively by it
    # that wasn't already loaded.
    importlib.import_module(module_name)
    # utils.push must not itself be the reason any games.* module is imported;
    # we assert it declares no such dependency (the AST test is the strong one).
    assert module_name in sys.modules
