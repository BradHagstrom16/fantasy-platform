"""
The admin dashboard's health reads (open-items §H)
===================================================
Read-only views over ``sync_runs`` (utils/sync_runs.py writes it): the
latest run of each job that has run, and the Odds API balance the most
recent job saw. The page makes no outside call.
"""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from extensions import db
from models.sync_run import SyncRun
from utils.sync_runs import JOBS

# Each outcome as the dashboard says it: a word and an icon, never colour
# alone (DESIGN.md: semantic state pairs a tint with a leading icon).
OUTCOME_DISPLAY = {
    'ok': ('Ran', 'bi-check-circle-fill'),
    'idle': ('Idle', 'bi-dash-circle'),
    'stood_down': ('Stood down', 'bi-pause-circle'),
    'error': ('Failed', 'bi-x-octagon-fill'),
    'running': ('Running', 'bi-hourglass-split'),
}

# How far back a failure stays on a job's row after a later run went fine.
RECENT_ERROR_WINDOW = timedelta(days=7)


@dataclass
class JobRow:
    label: str
    run: SyncRun
    recent_error: SyncRun | None

    @property
    def outcome_word(self):
        return OUTCOME_DISPLAY[self.run.outcome][0]

    @property
    def outcome_icon(self):
        return OUTCOME_DISPLAY[self.run.outcome][1]

    @property
    def duration(self):
        """'42s' / '3m 05s', or None while the run is still going."""
        if self.run.finished_at is None:
            return None
        seconds = round((self.run.finished_at - self.run.started_at).total_seconds())
        if seconds < 60:
            return f'{seconds}s'
        return f'{seconds // 60}m {seconds % 60:02d}s'


def job_rows(now=None):
    """One row per ``JOBS`` key that has run at least once, in ``JOBS`` order."""
    now = now or datetime.now(UTC)
    latest_ids = select(func.max(SyncRun.id)).group_by(SyncRun.job)
    latest = {run.job: run for run in db.session.scalars(
        select(SyncRun).where(SyncRun.id.in_(latest_ids)))}
    recent_errors = {}
    for run in db.session.scalars(
            select(SyncRun)
            .where(SyncRun.outcome == 'error',
                   SyncRun.started_at >= now - RECENT_ERROR_WINDOW)
            .order_by(SyncRun.id)):
        recent_errors[run.job] = run   # ascending, so the newest wins
    rows = []
    for job, label in JOBS.items():
        run = latest.get(job)
        if run is None:
            continue
        error = recent_errors.get(job)
        rows.append(JobRow(label, run,
                           error if error is not None and error.id != run.id else None))
    return rows


def latest_credits():
    """The newest run that saw an Odds API balance, or None."""
    return db.session.scalar(
        select(SyncRun)
        .where(SyncRun.odds_credits_remaining.is_not(None))
        .order_by(SyncRun.id.desc())
        .limit(1))
