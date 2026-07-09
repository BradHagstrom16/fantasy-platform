"""CFB_FAKE_NOW time-seam locks (pre-launch audit §7 — platform-seam adoption).

Mirrors the WC seam contract (games/worldcup/services/state.now_utc):
active only when ENVIRONMENT is development/testing; naive ISO strings
are treated as UTC; malformed values are logged and fall back to real
time; production never reads CFB_FAKE_NOW.

Per the CLAUDE.md gotcha, every patch.dict that sets the fake-now var
also sets ENVIRONMENT in the same dict — the seam only activates in
dev/testing and the outside-process env var doesn't propagate.
"""
import os
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app import create_app
from games.cfb.utils import get_current_time, get_utc_time


@pytest.fixture()
def app():
    """App context only — the seam reads config (pool tz), not the DB."""
    app = create_app('testing')
    with app.app_context():
        yield app


FAKE_ISO = '2026-09-05T16:00:00+00:00'
FAKE_UTC = datetime(2026, 9, 5, 16, 0, tzinfo=UTC)


def test_get_utc_time_honors_cfb_fake_now(app):
    """get_utc_time returns the faked instant when the seam is active."""
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'CFB_FAKE_NOW': FAKE_ISO}):
        assert get_utc_time() == FAKE_UTC


def test_get_current_time_converts_fake_now_to_pool_tz(app):
    """get_current_time returns the faked instant in the pool timezone."""
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'CFB_FAKE_NOW': FAKE_ISO}):
        now = get_current_time()
    assert now == FAKE_UTC  # same instant (aware comparison)
    assert now.hour == 11   # 16:00 UTC = 11:00 CDT wall clock


def test_naive_fake_now_treated_as_utc(app):
    """A naive ISO string is interpreted as UTC, matching the WC seam."""
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'CFB_FAKE_NOW': '2026-09-05T16:00:00'}):
        assert get_utc_time() == FAKE_UTC


def test_aware_non_utc_fake_now_normalized_to_utc(app):
    """An offset-bearing ISO value converts to UTC tzinfo, same instant.

    get_utc_time() feeds naive-UTC created_at columns; Postgres
    truncates the offset on a naive column, so a non-UTC tzinfo here
    would store a wall clock hours off the contract.
    """
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'CFB_FAKE_NOW': '2026-09-05T11:00:00-05:00'}):
        now = get_utc_time()
    assert now == FAKE_UTC
    assert now.tzinfo == UTC


def test_malformed_fake_now_falls_back_to_real_time(app):
    """A malformed value is ignored — real time, no exception."""
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'CFB_FAKE_NOW': 'not-a-datetime'}):
        now = get_utc_time()
    assert abs((datetime.now(UTC) - now).total_seconds()) < 5


def test_production_never_reads_fake_now(app):
    """The seam is inert outside development/testing environments."""
    with patch.dict(os.environ, {'ENVIRONMENT': 'production',
                                 'CFB_FAKE_NOW': FAKE_ISO}):
        now = get_utc_time()
    assert abs((datetime.now(UTC) - now).total_seconds()) < 5
