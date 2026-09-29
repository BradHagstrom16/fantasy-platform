"""
The Docket — Week Boundary Math
===============================
Docket weeks partition time continuously at Tuesday 06:00 America/Chicago
boundaries (import instant → next import instant), half-open
[boundary, next boundary); a game belongs to the week containing its
kickoff. Week 1 opens Tue Sep 1 2026; the season runs 19 docket weeks
(CFB Week 1 through NFL Week 18). The week deadline is its Sunday
12:00 PM CT.

Boundaries are computed by wall-clock arithmetic in CT and only then
converted to UTC, so they stay 06:00/12:00 *local* across the November
DST fall-back by construction (D6). Everything returned here is aware
UTC; the naive-UTC strip for storage happens at the column boundary
(games/docket/utils.to_naive_utc).

Every season has its own calendar (``SEASON_CALENDARS``, ADR-069) and every
function takes ``season_year`` (default ``SEASON_YEAR``, the season being
played). A season with no calendar is a KeyError: add next season's entry
when its dates exist.
"""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

CT = ZoneInfo('America/Chicago')


@dataclass(frozen=True)
class SeasonCalendar:
    """One Docket season's fixed dates."""
    # The Tue 06:00 CT boundary that opens Week 1, naive CT wall clock.
    week_1_boundary_local: datetime
    total_weeks: int
    # The first docket week holding NFL games; the default-tiebreaker rule
    # (services/tiebreaker_rule.py) takes NFL games only from this week on.
    first_nfl_week: int
    # Self-serve joining closes here: the shared club cutoff (ADR-050), the
    # same instant as Survivor's calendar (equality-locked in tests).
    enrollment_deadline_utc: datetime


# The season being played. A module constant, deliberately not a config
# knob (config.py): the week math is the SSoT for the Docket's season.
SEASON_YEAR = 2026

SEASON_CALENDARS = {
    # Week 1 opens Tue Sep 1 2026 06:00 CT (CFB Week 1: games from Thu Sep 3,
    # picks due Sun Sep 6 12:00 PM CT). NFL Week 1 kicks off Thu Sep 10 2026,
    # inside Docket Week 2, so Docket Week 1 is CFB-only. Joining closed Sat
    # Sep 5 2026 11:00 AM CT (16:00 UTC; CDT is UTC-5), pinned rather than
    # derived from deadline_utc(1): the pick deadline moved to Sunday on
    # 2026-09-09 and the join cutoff deliberately did not.
    2026: SeasonCalendar(
        week_1_boundary_local=datetime(2026, 9, 1, 6, 0),
        total_weeks=19,
        first_nfl_week=2,
        enrollment_deadline_utc=datetime(2026, 9, 5, 16, 0, tzinfo=UTC),
    ),
}

# The current season's dates by their old names, for the many readers.
WEEK_1_BOUNDARY_LOCAL = SEASON_CALENDARS[SEASON_YEAR].week_1_boundary_local
TOTAL_WEEKS = SEASON_CALENDARS[SEASON_YEAR].total_weeks
FIRST_NFL_WEEK = SEASON_CALENDARS[SEASON_YEAR].first_nfl_week
# Tuesday boundary + 5 days = the week's Sunday.
_DEADLINE_DAY_OFFSET = 5
_DEADLINE_HOUR = 12


def _validate_week_number(week_number, calendar, *, allow_season_end=False):
    """Out-of-season week numbers must never compute (and then persist)
    plausible-looking boundaries — reject them loudly."""
    maximum = calendar.total_weeks + 1 if allow_season_end else calendar.total_weeks
    if not 1 <= week_number <= maximum:
        raise ValueError(
            f'week_number must be between 1 and {maximum}, got {week_number}')


def boundary_utc(week_number, season_year=SEASON_YEAR):
    """UTC instant of the Tue 06:00 CT boundary that OPENS the given week.

    ``week_number`` may run to the season's total_weeks + 1 (the season end
    instant).
    """
    calendar = SEASON_CALENDARS[season_year]
    _validate_week_number(week_number, calendar, allow_season_end=True)
    local = calendar.week_1_boundary_local + timedelta(weeks=week_number - 1)
    return local.replace(tzinfo=CT).astimezone(UTC)


def week_bounds_utc(week_number, season_year=SEASON_YEAR):
    """(start, end) aware-UTC pair for the half-open [start, end) week."""
    _validate_week_number(week_number, SEASON_CALENDARS[season_year])
    return (boundary_utc(week_number, season_year),
            boundary_utc(week_number + 1, season_year))


def deadline_utc(week_number, season_year=SEASON_YEAR):
    """UTC instant of the week's Sun 12:00 PM CT submission deadline."""
    calendar = SEASON_CALENDARS[season_year]
    _validate_week_number(week_number, calendar)
    local = (calendar.week_1_boundary_local
             + timedelta(weeks=week_number - 1, days=_DEADLINE_DAY_OFFSET))
    local = local.replace(hour=_DEADLINE_HOUR, minute=0)
    return local.replace(tzinfo=CT).astimezone(UTC)


def week_number_for(instant_utc, season_year=SEASON_YEAR):
    """Docket week of the season containing the aware-UTC instant, or None
    outside that season.

    Half-open semantics: an instant exactly at a boundary belongs to the
    week that boundary opens.
    """
    if instant_utc < boundary_utc(1, season_year):
        return None
    for n in range(1, SEASON_CALENDARS[season_year].total_weeks + 1):
        if instant_utc < boundary_utc(n + 1, season_year):
            return n
    return None
