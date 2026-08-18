"""
Shared decorators for per-game enrollment gating.
=================================================
Keyed off games.registry.GAMES so a single flag flip in the registry
controls behavior for every route using these decorators.
"""
from functools import wraps

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required

# games.registry is imported lazily inside each decorator wrapper body to break
# the cycle: games/<game>/routes.py -> games.common -> games.registry ->
# games/<game>/services/enrollment -> games/<game>/models -> games/<game>/__init__
# -> games/<game>/routes.py. Deferring the import to request time (when all
# modules are fully loaded) avoids partial-init imports.


def game_must_be_open(slug: str):
    """Redirect to homepage with a flash unless self-serve enrollment is open.

    Two gates: the registry status must be 'open', and when the entry
    carries a ``join_open`` window (the 2026-08-18 enrollment-deadline
    ruling) that window must not have closed. An already-enrolled member
    passes the window gate so the route's own "already enrolled" handling
    still runs; admin enrollment never routes through here, so late seats
    stay the Commish's to grant.

    Apply to /join routes and any enrollment-mutating routes.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from games.registry import get_entry
            entry = get_entry(slug)
            if entry.status != 'open':
                flash(
                    f'{entry.display_name} is not currently open for enrollment.',
                    'info',
                )
                return redirect(url_for('main.index'))
            if entry.join_open is not None and not entry.join_open():
                already_enrolled = (
                    current_user.is_authenticated
                    and entry.get_enrollment(current_user.id) is not None
                )
                if not already_enrolled:
                    flash(
                        f'Enrollment for {entry.display_name} is closed for '
                        'the season. Late seats are granted by the Commish.',
                        'info',
                    )
                    return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def enrollment_required(slug: str):
    """Gate interior routes behind a current-season enrollment.

    Behavior by registry status:
      - coming_soon: 404 for non-platform-admins; platform admin bypasses.
      - open: enrolled passes; non-enrolled redirects to /<slug>/join?next=<url>.
      - closed: enrolled passes; non-enrolled 403.
      - completed: enrolled passes (read-only is the route's job); non-enrolled 403.

    Anonymous users are redirected to login (via @login_required).
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            from games.registry import get_entry
            entry = get_entry(slug)
            is_platform_admin = bool(
                current_user.is_authenticated and getattr(current_user, 'is_admin', False)
            )

            if entry.status == 'coming_soon':
                if is_platform_admin:
                    return f(*args, **kwargs)
                abort(404)

            enrollment = entry.get_enrollment(current_user.id)
            if enrollment is not None:
                return f(*args, **kwargs)

            if entry.status == 'open':
                flash(f'Join {entry.display_name} to continue.', 'info')
                return redirect(url_for(entry.blueprint_join, next=request.url))

            abort(403)
        return wrapper
    return decorator
