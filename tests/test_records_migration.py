"""The record's division migration (ADR-075, Task C1) on Postgres.

Every other test builds its tables with ``create_all()``; CI runs the Alembic
chain separately (``flask db upgrade`` + ``flask db check`` on an empty
database), which proves the schema but never a backfill. This test runs the
chain to the revision before the division, writes a golf and a Survivor row
the way production's ledger holds them, upgrades to head and reads the
backfill back.
"""
import logging.config
from datetime import UTC, datetime
from pathlib import Path

import pytest
from flask_migrate import upgrade
from sqlalchemy import text

from extensions import db

MIGRATIONS = Path(__file__).resolve().parent.parent / 'migrations'
BEFORE_DIVISION = '32cd68a3e8ea'


def _empty_schema():
    db.session.remove()
    db.drop_all()
    with db.engine.begin() as connection:
        connection.execute(text('DROP TABLE IF EXISTS alembic_version'))


@pytest.mark.postgres
def test_migration_backfills_golf_rows_to_handicap(app, monkeypatch):
    # migrations/env.py calls logging.config.fileConfig, which disables every
    # logger already created; later tests on this worker read theirs (caplog).
    monkeypatch.setattr(logging.config, 'fileConfig', lambda *args, **kwargs: None)
    _empty_schema()
    try:
        upgrade(directory=str(MIGRATIONS), revision=BEFORE_DIVISION)
        with db.engine.begin() as connection:
            connection.execute(text(
                'INSERT INTO season_finishes '
                '(game, season_year, name, place, field_size, closed_at) VALUES '
                "('golf', 2026, 'Casey', 1, 1, :at), ('cfb', 2025, 'Fourth & Pine', 1, 1, :at)"),
                {'at': datetime.now(UTC)})

        upgrade(directory=str(MIGRATIONS))

        with db.engine.connect() as connection:
            rows = connection.execute(text(
                'SELECT game, division, division_name FROM season_finishes ORDER BY game'
            )).all()
        assert [tuple(row) for row in rows] == [
            ('cfb', '', ''),
            ('golf', 'handicap', 'Handicap Pay Sheet'),
        ]
    finally:
        _empty_schema()
