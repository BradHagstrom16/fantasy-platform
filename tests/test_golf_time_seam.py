"""GOLF_FAKE_NOW time-seam locks (Golf Phase U1).

The same contract as the CFB seam (tests/test_cfb_time_seam.py): active only
when ENVIRONMENT is development/testing; a naive ISO string is UTC; a
malformed value is logged and falls back to real time; production never reads
GOLF_FAKE_NOW. The tournament clock (lock passed, status from time) reads
through it.

Every patch.dict that sets the fake-now var also sets ENVIRONMENT in the same
dict: the seam only activates in dev/testing.
"""
import os
from datetime import UTC, datetime
from unittest.mock import patch

from games.golf.models import GolfTournament
from games.golf.utils import GOLF_LEAGUE_TZ, format_lock, get_current_time

FAKE_ISO = '2026-04-12T21:30:00+00:00'
FAKE_UTC = datetime(2026, 4, 12, 21, 30, tzinfo=UTC)


def _tournament(**overrides):
    fields = {
        'api_tourn_id': 'T-seam', 'name': 'Seam Open', 'season_year': 2026,
        'start_date': datetime(2026, 4, 16), 'end_date': datetime(2026, 4, 19),
        'pick_deadline': datetime(2026, 4, 16, 6, 5), 'status': 'upcoming',
    }
    return GolfTournament(**{**fields, **overrides})


def test_get_current_time_honors_golf_fake_now():
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing', 'GOLF_FAKE_NOW': FAKE_ISO}):
        now = get_current_time()
    assert now == FAKE_UTC                 # same instant
    assert now.tzinfo == GOLF_LEAGUE_TZ
    assert (now.hour, now.minute) == (16, 30)   # 21:30 UTC = 4:30 PM CDT


def test_naive_fake_now_is_utc():
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'GOLF_FAKE_NOW': '2026-04-12T21:30:00'}):
        assert get_current_time() == FAKE_UTC


def test_aware_offset_fake_now_is_the_same_instant():
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'GOLF_FAKE_NOW': '2026-04-12T16:30:00-05:00'}):
        assert get_current_time() == FAKE_UTC


def test_malformed_fake_now_falls_back_to_real_time():
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing', 'GOLF_FAKE_NOW': 'not-a-datetime'}):
        now = get_current_time()
    assert abs((datetime.now(UTC) - now).total_seconds()) < 5


def test_production_never_reads_fake_now():
    with patch.dict(os.environ, {'ENVIRONMENT': 'production', 'GOLF_FAKE_NOW': FAKE_ISO}):
        now = get_current_time()
    assert abs((datetime.now(UTC) - now).total_seconds()) < 5


def test_lock_reads_the_seam():
    """The lock is league wall clock: 6:05 AM CT is 11:05 UTC in April."""
    t = _tournament()
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'GOLF_FAKE_NOW': '2026-04-16T11:04:00'}):
        assert not t.is_deadline_passed()
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'GOLF_FAKE_NOW': '2026-04-16T11:06:00'}):
        assert t.is_deadline_passed()


def test_status_from_time_reads_the_seam_and_never_completes():
    t = _tournament()
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'GOLF_FAKE_NOW': '2026-04-14T15:00:00'}):
        assert t.update_status_from_time() == 'upcoming'
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'GOLF_FAKE_NOW': '2026-04-17T15:00:00'}):
        assert t.update_status_from_time() == 'active'
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'GOLF_FAKE_NOW': '2026-04-21T15:00:00'}):
        assert t.update_status_from_time() == 'active'


def test_format_lock_is_the_rooms_short_line():
    assert format_lock(datetime(2026, 4, 16, 6, 5)) == 'Thu Apr 16 · 6:05 AM CT'
    assert format_lock(None) == 'TBD'
