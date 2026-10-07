"""The Pay Sheet — the API-usage meter.

SlashGolf runs on the FREE RapidAPI tier (250 calls a month). The timer
cadence IS the budget (tests/test_golf_timers.py); nothing here enforces it.
This module only reads the call log the sync writes
(``games/golf/services/sync.py``: one line per attempt, asctime in UTC) and
reports the month so far in the league's clock, for the admin dashboard.

Approximate by design: RapidAPI resets on the subscription day, not the
calendar month, so the meter is a floor on what the month has spent.

Counting rule: every attempt that reached RapidAPI counts (``status != 0``),
a 4xx/5xx and every retry included; a network failure (``status=0``) never
left the box. The live file and its rotations are all read.
"""
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from games.golf.constants import API_MONTHLY_LIMIT
from games.golf.utils import GOLF_LEAGUE_TZ

LOG_NAME = 'api_calls.log'
# The sync's RotatingFileHandler keeps three backups: .1, .2, .3.
ROTATIONS = 3
_STAMP = '%Y-%m-%d %H:%M:%S'


def api_log_dir() -> str:
    """Where the sync writes its call log: ``GOLF_API_LOG_DIR``, else the
    package-local ``logs/``. Read at call time so a test can point it."""
    return os.environ.get('GOLF_API_LOG_DIR') or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs',
    )


@dataclass(frozen=True)
class ApiUsage:
    """The month so far, in the league's clock."""
    month: int
    year: int
    calls: int = 0
    limit: int = API_MONTHLY_LIMIT
    by_endpoint: dict[str, int] = field(default_factory=dict)
    by_mode: dict[str, int] = field(default_factory=dict)
    last_call: datetime | None = None

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.calls)

    @property
    def pct(self) -> int:
        return round(self.calls / self.limit * 100)

    @property
    def over_budget(self) -> bool:
        return self.calls > self.limit


def _log_files(log_dir: Path):
    live = log_dir / LOG_NAME
    yield live
    for n in range(1, ROTATIONS + 1):
        yield live.with_name(f'{LOG_NAME}.{n}')


def _parse(line: str):
    """(league-time stamp, fields) for a log line, or None for one that is
    not a call record (a blank, a traceback, a line from another logger)."""
    parts = line.rstrip('\n').split('\t')
    if len(parts) < 2:
        return None
    stamp = parts[0].split(',')[0]
    try:
        at = datetime.strptime(stamp, _STAMP).replace(tzinfo=UTC)
    except ValueError:
        return None
    fields = {}
    for part in parts[1:]:
        key, sep, value = part.partition('=')
        if sep:
            fields[key] = value
    return at.astimezone(GOLF_LEAGUE_TZ), fields


def read_api_usage(now: datetime) -> ApiUsage:
    """The calls logged in ``now``'s month (league time), over every log file.

    A missing directory or file reads as nothing spent; a malformed line is
    skipped (the log is an audit trail, not a contract).
    """
    now = now.astimezone(GOLF_LEAGUE_TZ)
    month, year = now.month, now.year
    by_endpoint: Counter[str] = Counter()
    by_mode: Counter[str] = Counter()
    last_call = None
    for path in _log_files(Path(api_log_dir())):
        try:
            text = path.read_text()
        except OSError:
            continue
        for line in text.splitlines(keepends=True):
            parsed = _parse(line)
            if parsed is None:
                continue
            at, fields = parsed
            if (at.month, at.year) != (month, year) or fields.get('status', '0') == '0':
                continue
            by_endpoint[fields.get('endpoint', 'unknown')] += 1
            by_mode[fields.get('mode', 'unknown')] += 1
            if last_call is None or at > last_call:
                last_call = at
    return ApiUsage(
        month=month, year=year,
        calls=sum(by_endpoint.values()),
        by_endpoint=dict(by_endpoint),
        by_mode=dict(by_mode),
        last_call=last_call,
    )
