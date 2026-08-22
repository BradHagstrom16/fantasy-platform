"""
The Docket — Week Boundary Math
===============================
Docket weeks partition time continuously at Tuesday 06:00 America/Chicago
boundaries (import instant → next import instant), half-open
[boundary, next boundary); a game belongs to the week containing its
kickoff. Week 1 opens Tue Sep 1 2026; the season runs 19 docket weeks
(CFB Week 1 through NFL Week 18). The week deadline is its Saturday
11:00 AM CT.

Boundaries are computed by wall-clock arithmetic in CT and only then
converted to UTC, so they stay 06:00/11:00 *local* across the November
DST fall-back by construction (D6). Everything returned here is aware
UTC; the naive-UTC strip for storage happens at the column boundary
(games/docket/utils.to_naive_utc).
"""
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

CT = ZoneInfo('America/Chicago')

SEASON_YEAR = 2026
# Tue Sep 1 2026 06:00 CT — the boundary that opens Docket Week 1
# (CFB Week 1: games from Thu Sep 3, picks due Sat Sep 5 11:00 AM CT).
WEEK_1_BOUNDARY_LOCAL = datetime(2026, 9, 1, 6, 0)
TOTAL_WEEKS = 19
# NFL Week 1 kicks off Thu Sep 10 2026, inside Docket Week 2; Docket Week 1
# is CFB-only. The default-tiebreaker rule (services/tiebreaker_rule.py)
# takes NFL games only from this week on.
FIRST_NFL_WEEK = 2
# Tuesday boundary + 4 days = the week's Saturday.
_DEADLINE_DAY_OFFSET = 4
_DEADLINE_HOUR = 11


def _validate_week_number(week_number, *, allow_season_end=False):
    """Out-of-season week numbers must never compute (and then persist)
    plausible-looking boundaries — reject them loudly."""
    maximum = TOTAL_WEEKS + 1 if allow_season_end else TOTAL_WEEKS
    if not 1 <= week_number <= maximum:
        raise ValueError(
            f'week_number must be between 1 and {maximum}, got {week_number}')


def boundary_utc(week_number):
    """UTC instant of the Tue 06:00 CT boundary that OPENS the given week.

    ``week_number`` may run to TOTAL_WEEKS + 1 (the season end instant).
    """
    _validate_week_number(week_number, allow_season_end=True)
    local = WEEK_1_BOUNDARY_LOCAL + timedelta(weeks=week_number - 1)
    return local.replace(tzinfo=CT).astimezone(UTC)


def week_bounds_utc(week_number):
    """(start, end) aware-UTC pair for the half-open [start, end) week."""
    _validate_week_number(week_number)
    return boundary_utc(week_number), boundary_utc(week_number + 1)


def deadline_utc(week_number):
    """UTC instant of the week's Sat 11:00 AM CT submission deadline."""
    _validate_week_number(week_number)
    local = (WEEK_1_BOUNDARY_LOCAL
             + timedelta(weeks=week_number - 1, days=_DEADLINE_DAY_OFFSET))
    local = local.replace(hour=_DEADLINE_HOUR, minute=0)
    return local.replace(tzinfo=CT).astimezone(UTC)


def week_number_for(instant_utc):
    """Docket week containing the aware-UTC instant, or None outside the season.

    Half-open semantics: an instant exactly at a boundary belongs to the
    week that boundary opens.
    """
    if instant_utc < boundary_utc(1):
        return None
    for n in range(1, TOTAL_WEEKS + 1):
        if instant_utc < boundary_utc(n + 1):
            return n
    return None
