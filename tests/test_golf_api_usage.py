"""The Pay Sheet admin: the API-usage meter (Golf Phase U6).

SlashGolf runs on the FREE RapidAPI tier, 250 calls a month. The timer
cadence is the budget (tests/test_golf_timers.py); this meter only READS the
API call log the sync writes (games/golf/services/sync.py, one line per
attempt, asctime in UTC) and reports the month so far in the league's clock.
It is approximate by design: RapidAPI resets on the subscription day, not the
calendar month.

Counting rule: every attempt that reached RapidAPI counts (status != 0),
including a 4xx/5xx and every retry; a network failure (status=0) never left
the box and does not. The live file and its three rotations are all read.
"""
from datetime import UTC, datetime

from games.golf.constants import API_MONTHLY_LIMIT
from games.golf.services.api_usage import read_api_usage
from games.golf.utils import GOLF_LEAGUE_TZ

# The reader's "now": Thursday 2026-04-16 noon CT, mid-month.
NOW = datetime(2026, 4, 16, 12, 0, tzinfo=GOLF_LEAGUE_TZ)


def _line(stamp_utc, endpoint='leaderboard', status=200, mode='free', count=1):
    """One log line the way the sync's RotatingFileHandler writes it."""
    return (f'{stamp_utc},123\tcount={count}\tmode={mode}\tendpoint={endpoint}'
            f'\tstatus={status}\tattempt=1\tduration=0.42s\tparams={{}}\n')


def _write(log_dir, name, lines):
    (log_dir / name).write_text(''.join(lines))


def test_limit_is_the_free_tier():
    assert API_MONTHLY_LIMIT == 250


def test_missing_log_dir_reads_as_nothing_spent(tmp_path, monkeypatch):
    monkeypatch.setenv('GOLF_API_LOG_DIR', str(tmp_path / 'never-made'))
    usage = read_api_usage(NOW)
    assert usage.calls == 0
    assert usage.remaining == API_MONTHLY_LIMIT
    assert usage.pct == 0
    assert usage.last_call is None
    assert (usage.month, usage.year) == (4, 2026)
    assert usage.over_budget is False


def test_counts_this_month_in_league_time_across_rotations(tmp_path, monkeypatch):
    monkeypatch.setenv('GOLF_API_LOG_DIR', str(tmp_path))
    _write(tmp_path, 'api_calls.log', [
        _line('2026-04-16 17:00:00', endpoint='leaderboard'),        # noon CT, counts
        _line('2026-04-16 21:00:00', endpoint='leaderboard', status=500),  # reached RapidAPI
        _line('2026-04-16 21:00:03', endpoint='leaderboard', status=0),    # network failure, no
        _line('2026-04-14 13:00:00', endpoint='schedule', mode='standard'),
        _line('2026-05-01 04:30:00', endpoint='leaderboard'),        # Apr 30 23:30 CT: this month
        _line('2026-05-01 05:30:00', endpoint='leaderboard'),        # May 1 00:30 CT: next month
        _line('2026-03-31 23:00:00', endpoint='leaderboard'),        # March, no
        'garbage line with no tabs\n',
        'not-a-date\tcount=9\tendpoint=x\tstatus=200\n',
    ])
    _write(tmp_path, 'api_calls.log.1', [
        _line('2026-04-02 13:00:00', endpoint='field'),
    ])
    _write(tmp_path, 'api_calls.log.2', [
        _line('2026-02-02 13:00:00', endpoint='field'),             # February, no
    ])

    usage = read_api_usage(NOW)

    assert usage.calls == 5
    assert usage.by_endpoint == {'leaderboard': 3, 'schedule': 1, 'field': 1}
    assert usage.by_mode == {'free': 4, 'standard': 1}
    assert usage.remaining == API_MONTHLY_LIMIT - 5
    assert usage.pct == 2
    # The last read, in the league's clock.
    assert usage.last_call == datetime(2026, 5, 1, 4, 30, tzinfo=UTC).astimezone(GOLF_LEAGUE_TZ)
    assert usage.limit == API_MONTHLY_LIMIT


def test_pct_rounds_and_remaining_floors_at_zero(tmp_path, monkeypatch):
    monkeypatch.setenv('GOLF_API_LOG_DIR', str(tmp_path))
    _write(tmp_path, 'api_calls.log',
           [_line('2026-04-10 13:00:00', count=i) for i in range(API_MONTHLY_LIMIT + 7)])
    usage = read_api_usage(NOW)
    assert usage.calls == API_MONTHLY_LIMIT + 7
    assert usage.remaining == 0
    assert usage.pct == 103
    assert usage.over_budget is True


def test_the_sync_stamps_the_log_in_utc(tmp_path, monkeypatch):
    """The reader treats asctime as UTC, so the writer must stamp it in UTC
    whatever the box's clock: the handler's formatter converts with gmtime."""
    import time

    import games.golf.services.sync as sync_mod
    monkeypatch.setenv('GOLF_API_LOG_DIR', str(tmp_path))
    monkeypatch.setattr(sync_mod, '_api_call_logging_configured', False)
    monkeypatch.setattr(sync_mod.API_CALL_LOGGER, 'handlers', [])
    sync_mod._ensure_api_call_logging()
    handler = sync_mod.API_CALL_LOGGER.handlers[0]
    assert handler.formatter.converter is time.gmtime
    assert handler.baseFilename == str(tmp_path / 'api_calls.log')
