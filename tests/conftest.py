"""Canonical shared pytest fixtures (D11, Docket eng review 2026-08-11).

The whole suite runs on this pair since the 2026-08-21 migration (backlog
3.1): 103 exact-canonical local duplicates across 66 files were deleted.
The 15 files whose fixtures genuinely differ (FAKE_NOW seams, golf season
pins, module-scoped seeds) keep them locally — pytest resolves a local
fixture first, and conftest's ``client(app)`` binds to whichever ``app``
wins in the requesting module. The allowlist and the no-new-duplicates
rule are enforced by ``tests/test_conftest_lock.py``.

Keep this module to the canonical app/client pair; a fixture that only
some files need belongs in those files (and on the allowlist), not here.

Two databases, one suite. In-memory SQLite is the default. With
``TEST_DATABASE_URL`` set (config.py) the same tests run on Postgres —
production's engine — where the tables persist between tests, so they are
created once and emptied per test instead of created and dropped.
"""
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app import create_app
from extensions import db as _db

TEST_DATABASE_URL = os.environ.get('TEST_DATABASE_URL')
ON_POSTGRES = bool(TEST_DATABASE_URL)


def pytest_configure(config):
    config.addinivalue_line(
        'markers',
        'postgres: needs a real Postgres (row locks, a second connection, '
        'the timestamptz cast); skipped on the in-memory SQLite run')
    config.addinivalue_line(
        'markers',
        'sqlite_only: builds a state a typed, foreign-key-enforcing database '
        'refuses to hold (a float in an Integer column, a dangling key); '
        'skipped on the Postgres run')
    if not ON_POSTGRES:
        return
    # The fixtures truncate and drop every table. Only a throwaway database
    # may ever be on the other end of that.
    url = make_url(TEST_DATABASE_URL)
    if url.get_backend_name() != 'postgresql' or not (
            url.database or '').endswith('_test'):
        raise pytest.UsageError(
            'TEST_DATABASE_URL must be a Postgres database whose name ends in '
            f'"_test" (got {url.database!r}). The suite empties it.')


def pytest_collection_modifyitems(config, items):
    if ON_POSTGRES:
        marker, reason = 'sqlite_only', 'a state Postgres refuses to hold'
    else:
        marker, reason = 'postgres', 'needs Postgres: set TEST_DATABASE_URL'
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if marker in item.keywords:
            item.add_marker(skip)


def _empty_every_table(connection):
    tables = connection.execute(text(
        "SELECT quote_ident(tablename) FROM pg_tables "
        "WHERE schemaname = 'public'")).scalars().all()
    if tables:
        connection.execute(text(
            f'TRUNCATE {", ".join(tables)} RESTART IDENTITY CASCADE'))


@pytest.fixture(scope='module', autouse=True)
def _postgres_clean_module():
    """Postgres only: every module starts on empty tables, including the
    modules whose local fixtures never pass through the canonical ``app``."""
    if ON_POSTGRES:
        engine = create_engine(TEST_DATABASE_URL)
        with engine.begin() as connection:
            _empty_every_table(connection)
        engine.dispose()
    yield


@pytest.fixture()
def app(monkeypatch):
    """Canonical testing app: a fresh, empty database per test.

    ENVIRONMENT is pinned too — code that reads os.environ directly (the
    *_FAKE_NOW seams) must see 'testing' even when a file is run without
    the ENVIRONMENT=testing prefix.
    """
    monkeypatch.setenv('ENVIRONMENT', 'testing')
    app = create_app('testing')
    with app.app_context():
        _db.create_all()
        if not ON_POSTGRES:
            yield app
            _db.session.remove()
            _db.drop_all()
            return
        # Emptied at SETUP, so a test that leaked rows cannot poison the next.
        with _db.engine.begin() as connection:
            _empty_every_table(connection)
        yield app
        _db.session.remove()
        _db.engine.dispose()


@pytest.fixture()
def client(app):
    """Test client bound to the canonical app fixture."""
    return app.test_client()
