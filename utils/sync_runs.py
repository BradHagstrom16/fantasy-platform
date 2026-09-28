"""
Scheduled-job run recorder (open-items §H)
===========================================
Every scheduled CLI command runs its body inside ``record_run(job)``, which
writes one ``models.sync_run.SyncRun`` row per run for the admin
dashboard's Jobs list:

- On entry it inserts a ``running`` row and commits it at once, so a run
  killed by its unit's timeout still shows as running.
- On exit it stores the finish time, the exit code, the outcome and a
  one-line summary. An uncaught exception is an ``error`` and is re-raised;
  a ``SystemExit`` keeps its code. Any non-zero exit is an ``error``.
  Otherwise the outcome is what the command said through ``mark_run``,
  else ``ok``.

The rows go through a connection of their own (Core on ``db.engine``), so
the job's own commits and rollbacks never carry a run row with them. A
failed write logs a warning and changes nothing about the job: the job's
work matters more than its log, and a timer can fire between ``git pull``
and ``flask db upgrade`` in deploy.sh.

``note_credits`` is how ``utils/odds_api.py`` hands every response's
``x-requests-remaining`` to the run in progress; the row keeps the lowest.
This module imports nothing from the app at import time (``odds_api``
imports it, and game modules import ``odds_api``).

tests/test_sync_runs.py locks that every scheduled unit records under its
own name.
"""
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Every job that records, keyed by its systemd unit's name, in the order
# the dashboard lists them. docket-setup has no unit since ADR-065 step 9
# (the Paper opens the week); a hand run still records.
JOBS = {
    'club-paper': 'The Tuesday Paper',
    'club-remind': 'Reminder desk',
    'scores-gameday': 'Game-day scores',
    'cfb-setup': 'Survivor setup',
    'cfb-spreads': 'Survivor spreads',
    'cfb-scores': 'Survivor scores',
    'cfb-autopick': 'Survivor auto-picks',
    'docket-setup': 'Docket setup',
    'docket-lines': 'Docket lines',
    'docket-deadline': 'Docket deadline',
    'docket-scores': 'Docket scores',
    'golf-schedule': 'Golf schedule',
    'golf-field': 'Golf field',
    'golf-live': 'Golf live',
    'golf-live-wd': 'Golf live + withdrawals',
    'golf-results': 'Golf results',
    'golf-remind': 'Golf reminders',
}

SUMMARY_MAX = 500


@dataclass
class Run:
    """The run in progress. Commands refine it through ``mark_run``."""
    job: str
    outcome: str | None = None
    summary: str | None = None
    credits: int | None = None
    row_id: int | None = None


_current: ContextVar[Run | None] = ContextVar('sync_run', default=None)


def mark_run(outcome, summary=None):
    """Say how the current run went, when a command knows better than its
    exit code (a stand-down and a finished job both exit 0). No-op outside
    a recorded run, so shared helpers can call it unconditionally."""
    run = _current.get()
    if run is None:
        return
    run.outcome = outcome
    if summary is not None:
        run.summary = summary


def note_credits(remaining):
    """Keep the lowest Odds API balance seen during the current run."""
    run = _current.get()
    if run is None:
        return
    run.credits = remaining if run.credits is None else min(run.credits, remaining)


def _one_line(text):
    for line in str(text).splitlines():
        if line.strip():
            return line.strip()[:SUMMARY_MAX]
    return None


def _exit_code(code):
    """``SystemExit.code`` as the process exit status Python would use."""
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def _insert(job, started_at):
    from extensions import db
    from models.sync_run import SyncRun
    try:
        with db.engine.begin() as conn:
            result = conn.execute(SyncRun.__table__.insert().values(
                job=job, started_at=started_at, outcome='running',
                via='systemd' if os.environ.get('INVOCATION_ID') else 'shell'))
            return result.inserted_primary_key[0]
    except Exception:
        logger.warning('sync_runs: could not record the start of %s', job,
                       exc_info=True)
        return None


def _finish(run, exit_code):
    from extensions import db
    from models.sync_run import SyncRun
    table = SyncRun.__table__
    outcome = 'error' if exit_code else (run.outcome or 'ok')
    try:
        with db.engine.begin() as conn:
            conn.execute(table.update().where(table.c.id == run.row_id).values(
                finished_at=datetime.now(UTC), outcome=outcome,
                exit_code=exit_code,
                summary=_one_line(run.summary) if run.summary else None,
                odds_credits_remaining=run.credits))
    except Exception:
        logger.warning('sync_runs: could not record the end of %s', run.job,
                       exc_info=True)


@contextmanager
def record_run(job):
    """Record one run of ``job`` (a ``JOBS`` key). ``None`` records nothing,
    for the read-only modes (``status``, ``--dry-run``) that share a command
    with a recorded one."""
    if job is None:
        yield None
        return
    run = Run(job)
    run.row_id = _insert(job, datetime.now(UTC))
    token = _current.set(run)
    exit_code = 0
    try:
        yield run
    except SystemExit as exc:
        exit_code = _exit_code(exc.code)
        raise
    except BaseException as exc:
        exit_code = 1
        run.summary = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        _current.reset(token)
        if run.row_id is not None:
            _finish(run, exit_code)
