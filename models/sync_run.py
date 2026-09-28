"""
One row per run of a scheduled job (open-items §H)
===================================================
Written by ``utils.sync_runs.record_run`` around every scheduled CLI command;
read by the platform admin dashboard. ``job`` is the systemd unit's name
(``cfb-scores``, ``club-remind``), the same slug healthchecks.io checks use.

A row is inserted as ``running`` when the job starts and finished when it
ends, so a run killed by its unit's timeout stays visible as running. Rows
are never pruned: about fifty a day.
"""
from extensions import db

OUTCOMES = ('running', 'ok', 'idle', 'stood_down', 'error')


class SyncRun(db.Model):
    __tablename__ = 'sync_runs'
    __table_args__ = (db.Index('ix_sync_runs_job_started_at', 'job', 'started_at'),)

    id = db.Column(db.Integer, primary_key=True)
    job = db.Column(db.String(40), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # OUTCOMES: ok = did its work; idle = ran and found nothing due;
    # stood_down = nothing to do by design (out of season, not imported,
    # the credit floor); error = the job failed or reported a failure.
    outcome = db.Column(db.String(16), nullable=False)
    exit_code = db.Column(db.Integer, nullable=True)
    summary = db.Column(db.String(500), nullable=True)
    # The lowest x-requests-remaining any Odds API response showed this run.
    odds_credits_remaining = db.Column(db.Integer, nullable=True)
    # 'systemd' when systemd started the process (a timer, or a hand-fired
    # `systemctl start`), 'shell' when someone typed the command.
    via = db.Column(db.String(10), nullable=False)
