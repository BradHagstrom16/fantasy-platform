"""
utils/push.py
=============
Shared platform Web Push helper — the buzz twin of utils/email.py.

The ONLY module that imports pywebpush, and it imports NO game module (top-level
or lazy): games pass words, never library objects. Every game hook calls
send_push AFTER its grading commit; this helper NEVER raises — not into the
caller, and not out of its own DB work — so a slow or dead push service can
neither roll back a landed grade nor fail a systemd pass.

    SEND PIPELINE (per send_push call)
    ----------------------------------
    send_push(user_ids, ...)
      │  blank VAPID config? ───────────────► return 0 (feature off)
      │  1 query: PushSubscription WHERE user_id IN (...)   empty ► return 0
      ▼
    _send_to_subscriptions(subs, payload, ttl, urgency, topic)
      │  one requests.Session (keep-alive to each push host)
      │  120s wall-clock budget — past it, skip the rest, log the skipped count
      ▼  per subscription (fresh vapid_claims dict — pywebpush mutates aud/exp):
        webpush(... timeout=10 ...)
          ├── 201/200         ► delivered += 1
          ├── WebPushException 404/410  ► queue row for prune
          ├── WebPushException 429       ► log retry_after, skip this sub (no in-loop retry)
          └── any other error            ► log (user id, never endpoint), continue
      ▼
    prune queued rows ──► commit; on DB error ► rollback (caller's next commit is safe)
    return delivered count
"""
import json
import logging
import time

import requests
from flask import current_app
from pywebpush import WebPushException, webpush

from extensions import db
from models.push import PushSubscription

logger = logging.getLogger(__name__)

# POST timeout to a single push service (seconds).
PUSH_TIMEOUT_SEC = 10
# Wall-clock budget for one fan-out. Every scores/reminder unit carries
# TimeoutStartSec=5m; a slow push service must end in a log line, not a
# SIGKILL mid-fan-out, so past this we skip the remainder and log the count.
PUSH_WALLCLOCK_BUDGET_SEC = 120
# Push-service statuses that mean the subscription is dead — prune the row.
_PRUNE_STATUSES = (404, 410)


def _vapid_config():
    """(private_key, subject) from config, or (None, None) when either is
    blank — the blank-config-hides-feature convention (utils/payment.py)."""
    private_key = (current_app.config.get('VAPID_PRIVATE_KEY') or '').strip()
    subject = (current_app.config.get('VAPID_SUBJECT') or '').strip()
    if not private_key or not subject:
        return None, None
    return private_key, subject


def _build_payload(*, title, body, url, tag, app_badge=None):
    """The <4KB payload the service worker reads. `app_badge` is included only
    when set (the nag sets 1; a verdict omits it). The key is `app_badge`, never
    `badge` — `showNotification({badge})` is an image URL the worker hardcodes."""
    payload = {'title': title, 'body': body, 'url': url, 'tag': tag}
    if app_badge is not None:
        payload['app_badge'] = app_badge
    return payload


def _send_to_subscriptions(subs, payload, *, ttl, urgency, topic):
    """Shared send loop for both public helpers. Never raises. Returns the
    delivered count."""
    private_key, subject = _vapid_config()
    if private_key is None:
        return 0
    if not subs:
        return 0

    data = json.dumps(payload)
    headers = {'Urgency': urgency}
    if topic is not None:
        # The push service collapses queued messages sharing a Topic. Apple
        # validates it strictly: <= 32 URL-safe chars.
        headers['Topic'] = topic

    session = requests.Session()
    delivered = 0
    to_prune = []
    started = time.monotonic()
    skipped = 0
    try:
        for index, sub in enumerate(subs):
            if time.monotonic() - started > PUSH_WALLCLOCK_BUDGET_SEC:
                skipped = len(subs) - index
                logger.warning(
                    'Push fan-out hit the %ss budget; skipping %s remaining '
                    'sends', PUSH_WALLCLOCK_BUDGET_SEC, skipped)
                break
            try:
                webpush(
                    subscription_info={
                        'endpoint': sub.endpoint,
                        'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                    },
                    data=data,
                    vapid_private_key=private_key,
                    # FRESH dict per call: pywebpush fills aud/exp in place, and
                    # a reused dict sends one service's audience to another
                    # (Apple rejects as BadJwtToken).
                    vapid_claims={'sub': subject},
                    ttl=ttl,
                    timeout=PUSH_TIMEOUT_SEC,
                    headers=headers,
                    requests_session=session,
                )
                delivered += 1
            except WebPushException as exc:
                status = getattr(exc, 'status_code', None)
                if status in _PRUNE_STATUSES:
                    to_prune.append(sub)
                    logger.info(
                        'Pruning dead push subscription (status %s) for user '
                        '%s', status, sub.user_id)
                elif status == 429:
                    logger.warning(
                        'Push service rate-limited user %s (retry_after=%s); '
                        'skipping this run', sub.user_id, exc.retry_after)
                else:
                    logger.warning(
                        'Push send failed for user %s (status %s)',
                        sub.user_id, status)
            except Exception:
                # A malformed key, a socket timeout — log and keep going. This
                # helper never raises into the caller.
                logger.exception('Unexpected push error for user %s',
                                 sub.user_id)
    finally:
        session.close()

    _prune(to_prune)
    return delivered


def _prune(subs):
    """Delete dead subscription rows. A failed write rolls back inside the
    helper so the caller's next commit never hits PendingRollbackError."""
    if not subs:
        return
    try:
        for sub in subs:
            db.session.delete(sub)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Failed to prune %s dead push subscription(s)',
                         len(subs))


def send_push(user_ids, *, title, body, url, tag, ttl, urgency,
              topic=None, app_badge=None):
    """Send one Web Push to every device of every user in `user_ids`.

    Never raises. Returns the number of devices the push was delivered to.
    A blank VAPID config makes this a no-op returning 0.
    """
    ids = list(user_ids)
    if not ids:
        return 0
    try:
        subs = db.session.scalars(
            db.select(PushSubscription)
            .where(PushSubscription.user_id.in_(ids))
        ).all()
    except Exception:
        # Uphold the never-raises contract even out of our own DB work: a bad
        # session must not fail the caller's systemd pass after its grade landed.
        db.session.rollback()
        logger.exception('Push subscription lookup failed for %s user(s)',
                         len(ids))
        return 0
    payload = _build_payload(title=title, body=body, url=url, tag=tag,
                             app_badge=app_badge)
    return _send_to_subscriptions(subs, payload, ttl=ttl, urgency=urgency,
                                  topic=topic)


def send_push_to_endpoint(user_id, endpoint, *, title, body, url, tag):
    """Send a test push to ONE device — the row matching BOTH endpoint and
    user_id (so a member can never buzz another member's device). Returns 0 if
    no such row. Never raises. Shares the send path with send_push."""
    try:
        sub = db.session.scalar(
            db.select(PushSubscription)
            .filter_by(endpoint=endpoint, user_id=user_id)
        )
    except Exception:
        db.session.rollback()
        logger.exception('Push endpoint lookup failed for user %s', user_id)
        return 0
    if sub is None:
        return 0
    payload = _build_payload(title=title, body=body, url=url, tag=tag)
    return _send_to_subscriptions([sub], payload, ttl=600, urgency='high',
                                  topic=None)
