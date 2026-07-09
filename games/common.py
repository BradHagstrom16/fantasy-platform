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
    """Redirect to homepage with a flash if the game's registry status != 'open'.

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
