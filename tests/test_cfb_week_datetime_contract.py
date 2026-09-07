"""CFB datetime columns hold naive pool-tz wall clock — enforced on the way IN.

The 2026-09-07 incident: run_setup built Week 2 from _calculate_week_dates,
which returns AWARE America/Chicago datetimes, and assigned them straight to
CfbWeek.start_date / CfbWeek.deadline (naive DateTime columns). SQLite keeps
the wall clock, so every test passed; Postgres binds an aware value as
timestamptz and casts it in the session's zone (GMT on the droplet), so the
11:00 AM CT deadline landed as 16:00 and read back as 4:00 PM CT. The column
contract (games/cfb/models.py docstring) is therefore enforced by the model on
assignment: an aware value is converted to pool-tz wall clock and stripped;
a naive value passes through untouched. The assertions here are on the ORM
attribute, not on a round-trip, because the round-trip is exactly the thing
SQLite cannot reproduce.
"""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from games.cfb.models import CfbGame, CfbWeek

CHICAGO = ZoneInfo('America/Chicago')


def test_aware_pool_tz_week_dates_are_stripped_to_wall_clock(app):
    week = CfbWeek(
        week_number=2,
        start_date=datetime(2026, 9, 10, 0, 0, tzinfo=CHICAGO),
        deadline=datetime(2026, 9, 12, 11, 0, tzinfo=CHICAGO),
    )
    assert week.deadline.tzinfo is None
    assert week.deadline == datetime(2026, 9, 12, 11, 0)
    assert week.start_date.tzinfo is None
    assert week.start_date == datetime(2026, 9, 10, 0, 0)


def test_aware_utc_week_deadline_is_converted_to_pool_wall_clock(app):
    """An aware value in ANY zone lands as the pool's wall clock, never as
    the foreign zone's digits — the Postgres failure shape, inverted."""
    week = CfbWeek(
        week_number=2,
        start_date=datetime(2026, 9, 10, 5, 0, tzinfo=UTC),
        deadline=datetime(2026, 9, 12, 16, 0, tzinfo=UTC),
    )
    assert week.deadline == datetime(2026, 9, 12, 11, 0)
    assert week.start_date == datetime(2026, 9, 10, 0, 0)


def test_naive_week_dates_pass_through_untouched(app):
    """The admin form and the fixtures already hand over naive wall clock;
    normalization must be a no-op for them, not a second conversion."""
    week = CfbWeek(
        week_number=1,
        start_date=datetime(2026, 9, 3, 0, 0),
        deadline=datetime(2026, 9, 5, 11, 0),
    )
    assert week.deadline == datetime(2026, 9, 5, 11, 0)
    assert week.deadline.tzinfo is None
    assert week.start_date == datetime(2026, 9, 3, 0, 0)


def test_aware_game_time_is_stripped_to_pool_wall_clock(app):
    game = CfbGame(week_id=1, game_time=datetime(2026, 9, 7, 23, 30, tzinfo=UTC))
    assert game.game_time.tzinfo is None
    assert game.game_time == datetime(2026, 9, 7, 18, 30)


def test_none_dates_stay_none(app):
    game = CfbGame(week_id=1, game_time=None)
    assert game.game_time is None
