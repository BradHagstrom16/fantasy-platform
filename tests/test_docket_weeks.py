"""Docket week-boundary math (games/docket/services/weeks.py).

Grading Clarifications (design SSoT 2026-08-11): docket weeks partition time
continuously at Tuesday 06:00 America/Chicago boundaries, half-open
[boundary, next boundary); a game belongs to the week containing its kickoff.
Week 1 opens Tue Sep 1 2026 06:00 CT; the season is 19 docket weeks. The
deadline is the week's Saturday 11:00 AM CT. All service outputs are aware
UTC (the D6 naive-UTC strip happens at the column boundary, not here).
"""
from datetime import UTC, datetime, timedelta


def test_week_1_boundary_is_tue_sep_1_0600_ct():
    from games.docket.services.weeks import boundary_utc

    # Sep 1 2026 is CDT (UTC-5): 06:00 CT == 11:00 UTC.
    assert boundary_utc(1) == datetime(2026, 9, 1, 11, 0, tzinfo=UTC)


def test_boundaries_advance_by_wall_clock_weeks_across_dst():
    """DST ends Sun Nov 1 2026: boundaries stay Tue 06:00 *wall clock*, so the
    UTC instant shifts from 11:00 (CDT) to 12:00 (CST) and the fall-back week
    spans 169 UTC hours."""
    from games.docket.services.weeks import boundary_utc

    assert boundary_utc(9) == datetime(2026, 10, 27, 11, 0, tzinfo=UTC)   # CDT
    assert boundary_utc(10) == datetime(2026, 11, 3, 12, 0, tzinfo=UTC)   # CST
    assert boundary_utc(10) - boundary_utc(9) == timedelta(hours=169)


def test_week_bounds_are_half_open_at_the_exact_boundary_instant():
    """A kickoff exactly AT a boundary belongs to the week the boundary
    opens — [boundary, next boundary), locked at the instant level."""
    from games.docket.services.weeks import boundary_utc, week_number_for

    b2 = boundary_utc(2)
    assert week_number_for(b2) == 2
    assert week_number_for(b2 - timedelta(microseconds=1)) == 1


def test_week_number_for_covers_the_whole_season_window():
    from games.docket.services.weeks import TOTAL_WEEKS, boundary_utc, week_number_for

    assert TOTAL_WEEKS == 19
    # Thu Sep 3 2026 19:30 CT — CFB Week 1 opener territory.
    assert week_number_for(datetime(2026, 9, 4, 0, 30, tzinfo=UTC)) == 1
    # Last instant of the season window.
    season_end = boundary_utc(TOTAL_WEEKS + 1)
    assert week_number_for(season_end - timedelta(seconds=1)) == TOTAL_WEEKS


def test_week_number_for_returns_none_outside_the_season():
    from games.docket.services.weeks import TOTAL_WEEKS, boundary_utc, week_number_for

    assert week_number_for(boundary_utc(1) - timedelta(seconds=1)) is None
    assert week_number_for(boundary_utc(TOTAL_WEEKS + 1)) is None


def test_deadline_is_saturday_1100_ct_and_dst_aware():
    from games.docket.services.weeks import deadline_utc

    # Week 1: Sat Sep 5 2026 11:00 CDT == 16:00 UTC.
    assert deadline_utc(1) == datetime(2026, 9, 5, 16, 0, tzinfo=UTC)
    # Week 10 (post-fall-back): Sat Nov 7 2026 11:00 CST == 17:00 UTC.
    assert deadline_utc(10) == datetime(2026, 11, 7, 17, 0, tzinfo=UTC)


def test_deadline_falls_inside_its_own_week():
    from games.docket.services.weeks import TOTAL_WEEKS, deadline_utc, week_number_for

    for n in (1, 9, 10, TOTAL_WEEKS):
        assert week_number_for(deadline_utc(n)) == n


def test_out_of_season_week_numbers_are_rejected():
    """Week 0 or 25 must raise, never compute a plausible-looking boundary
    that ensure_week would then happily persist."""
    import pytest

    from games.docket.services.weeks import (
        TOTAL_WEEKS,
        boundary_utc,
        deadline_utc,
        week_bounds_utc,
    )

    for bad in (0, -1, TOTAL_WEEKS + 2):
        with pytest.raises(ValueError):
            boundary_utc(bad)
    for bad in (0, TOTAL_WEEKS + 1):
        with pytest.raises(ValueError):
            week_bounds_utc(bad)
        with pytest.raises(ValueError):
            deadline_utc(bad)
    # The season-end instant stays computable (week_number_for needs it).
    assert boundary_utc(TOTAL_WEEKS + 1) is not None
