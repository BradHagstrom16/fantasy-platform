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

All three honor ``PLATFORM_TZ`` (``America/Chicago``) as the platform
display timezone. It equals ``games.worldcup.constants.WORLDCUP_TZ`` but is
declared here rather than imported: importing a game package from utils/
boots ``games/worldcup/__init__`` (which imports routes, which import this
module) the moment any game utility touches ``utils.time`` first.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

PLATFORM_TZ = ZoneInfo('America/Chicago')
WORLDCUP_TZ = PLATFORM_TZ   # the historical name, kept for readers of the docstring

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


# Short zone labels for the deadline line ("11:00 AM CT"): the lounge, the
# rooms, and every email say "CT" rather than strftime's "CDT"/"CST" split.
# Unknown zones fall back to %Z.
_ZONE_LABELS = {
    'CDT': 'CT', 'CST': 'CT',
    'EDT': 'ET', 'EST': 'ET',
    'MDT': 'MT', 'MST': 'MT',
    'PDT': 'PT', 'PST': 'PT',
}


def format_deadline_short(
    dt: datetime | None,
    tz: ZoneInfo | None = None,
) -> str:
    """'Saturday, Sep 5 · 11:00 AM CT': the platform's one deadline line.

    Weekday, short month, no zero-pad, no year, the short zone label. Naive
    input is UTC (this module's convention: the docket's naive-UTC columns
    pass straight through); aware input is converted. ``tz`` defaults to
    the platform display zone; CFB passes its pool zone through its own
    wrapper (``games/cfb/utils.format_deadline_short``), whose naive input
    is pool wall clock, not UTC. ``None`` renders as ``'TBD'``.
    """
    if dt is None:
        return 'TBD'
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    local = dt.astimezone(tz or WORLDCUP_TZ)
    zone = local.strftime('%Z')
    return (f"{local.strftime('%A, %b %-d · %-I:%M %p')} "
            f"{_ZONE_LABELS.get(zone, zone)}")
