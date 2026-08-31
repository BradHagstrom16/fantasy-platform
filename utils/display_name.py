"""The one validator for a member's display name (ADR-057).

A member has exactly one display name, ``User.display_name``, shown on every
standings surface across the club; enrollment helpers delegate to it. Every
write site (/register, /profile, the Commish's /admin/users rename) runs the
raw form value through :func:`normalize_display_name` — the shape mirrors
``utils/phone.normalize_us_phone``: ``(value, error)``, blank meaning "go by
your username".

Uniqueness is a soft, write-time check (case-folded through
``normalize_identifier`` against every other member's display name AND
username) rather than a DB index — the platform's standing decision is no
functional ``lower()`` index (CLAUDE.md → Auth), and the username half stops a
member from standing under somebody else's login name.
"""
import re

from sqlalchemy import func, or_, select

from extensions import db
from models.user import User
from utils.identifier import normalize_identifier

MAX_LENGTH = User.display_name.type.length  # the column's own limit (100)

_TOO_LONG_MSG = f'Display names are at most {MAX_LENGTH} characters.'
_TAKEN_MSG = 'That name is already taken in the club.'


def normalize_display_name(raw, *, exclude_user_id=None):
    """Return ``(normalized, error)``.

    - blank/None -> ``(None, None)`` (the member goes by their username)
    - valid -> ``("Fourth & Pine", None)`` — stripped, inner runs of
      whitespace collapsed to one space, at most :data:`MAX_LENGTH` chars,
      and not another member's display name or username (case-folded).
    - anything else -> ``(None, error_message)``

    ``exclude_user_id`` is the member being edited, so re-saving their own
    name (or standing under their own username) never collides with itself.
    """
    value = re.sub(r'\s+', ' ', raw or '').strip()
    if not value:
        return None, None
    if len(value) > MAX_LENGTH:
        return None, _TOO_LONG_MSG

    folded = normalize_identifier(value)
    stmt = select(User.id).where(or_(
        func.lower(User.display_name) == folded,
        func.lower(User.username) == folded,
    ))
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    if db.session.scalar(stmt.limit(1)) is not None:
        return None, _TAKEN_MSG
    return value, None
