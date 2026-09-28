"""
utils/observability.py
======================
Error tracking. Sentry's free tier, errors only, never member data.

Initialized once from `create_app`, so it covers both Gunicorn requests (the
Flask integration captures an unhandled exception through
`got_request_exception`, before the `errorhandler(500)` page renders) and every
`flask …` timer job, whose uncaught exceptions reach Sentry's excepthook.

A blank SENTRY_DSN means Sentry is never initialized: dev, the test suite, and
production until the DSN is set in .env.
"""
import re

import sentry_sdk

# A password-reset link is /reset-password/<token>, a bearer credential for an
# hour. It can reach an event through the request URL or a Referer header.
_RESET_TOKEN = re.compile(r'(/reset-password/)[^/?#\s]+')


def scrub_event(event, hint):
    """before_send: strip what send_default_pii=False still lets through.

    The WSGI integration attaches the query string (a `next=` or search term)
    regardless of send_default_pii, and the URL and Referer can carry a reset
    token. Drop the query string, redact tokens, drop the Referer.
    """
    request = event.get('request')
    if request:
        request.pop('query_string', None)
        if isinstance(request.get('url'), str):
            request['url'] = _RESET_TOKEN.sub(r'\1[redacted]', request['url'])
        headers = request.get('headers')
        if isinstance(headers, dict):
            for name in [h for h in headers if h.lower() == 'referer']:
                del headers[name]
    return event


def init_sentry(app, config_name):
    """Start the Sentry client when SENTRY_DSN is set; otherwise do nothing."""
    dsn = app.config['SENTRY_DSN']
    if not dsn:
        return
    # Imported here, not at module top: core.context imports the game
    # registry, and this module is loaded before any blueprint.
    from core.context import _compute_asset_version

    sentry_sdk.init(
        dsn=dsn,
        environment=config_name,
        # The deployed git SHA, the same token the static assets carry.
        release=_compute_asset_version(),
        # No cookies, no client IPs, no logged-in user attached to an event.
        send_default_pii=False,
        # No request bodies either: login, profile and join forms carry
        # passwords, phones and emails.
        max_request_body_size='never',
        # No stack-frame locals: a frame holding an email, a phone or a pick
        # would ship it, and the default scrubber only knows secret-ish names.
        include_local_variables=False,
        before_send=scrub_event,
        # Errors only. Performance tracing would spend the free quota.
        traces_sample_rate=0,
    )
