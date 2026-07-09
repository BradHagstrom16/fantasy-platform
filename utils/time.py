"""Platform timezone helpers.

All datetimes flow through the app in UTC; surfaces that render to humans
convert at display time. This module is the one place that conversion
lives, so the rest of the codebase doesn't sprinkle `ZoneInfo` imports
or hardcoded `'America/Chicago'` strings.

Two entry points:

- ``to_ct(dt_utc)``: returns a Central-Time ``datetime`` (or ``None``).
  Use when the caller needs the converted datetime object (e.g. to feed
  into ``.strftime`` in Python code).
- ``format_ct(dt_utc, fmt='%a %d %b · %-I:%M %p CT')``: returns a
  formatted string (or ``None``). Registered as the Jinja filter
  ``ct`` in :func:`app.create_app`, so templates can write
  ``{{ match.kickoff_utc|ct('%a %d %b · %-I:%M %p CT') }}``.

Both honor ``games.worldcup.constants.WORLDCUP_TZ`` (``America/Chicago``)
as the platform display timezone.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from games.worldcup.constants import WORLDCUP_TZ

_UTC = ZoneInfo('UTC')


def to_ct(dt_utc: datetime | None) -> datetime | None:
    """Convert a UTC datetime to platform display TZ (America/Chicago).

    Naive inputs are interpreted as UTC. Returns ``None`` on ``None`` so
    callers can chain through nullable fields without guarding.
    """
    if dt_utc is None:
        return None
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=_UTC)
    return dt_utc.astimezone(WORLDCUP_TZ)


def format_ct(
    dt_utc: datetime | None,
    fmt: str = '%a %d %b · %-I:%M %p CT',
) -> str | None:
    """Format a UTC datetime as a Central-Time display string.

    Default format reads like ``Thu 11 Jun · 7:00 PM CT``. Returns
    ``None`` on ``None`` input so templates can pass through nullable
    fields without raising.
    """
    ct = to_ct(dt_utc)
    if ct is None:
        return None
    return ct.strftime(fmt)
