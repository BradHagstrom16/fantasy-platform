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
from config import TestingConfig
from extensions import db as _db

_BASE_DATABASE_URL = os.environ.get('TEST_DATABASE_URL')
ON_POSTGRES = bool(_BASE_DATABASE_URL)


def _is_throwaway(database_url):
    url = make_url(database_url)
    return url.get_backend_name() == 'postgresql' and (
        url.database or '').endswith('_test')


def _worker_database_url(base_url):
    """Under pytest-xdist every worker process gets its own database
    (``ccc_test`` -> ``ccc_test_gw0`` …), created on first use: the workers
    truncate concurrently, and one shared database would have them emptying
    each other's tables mid-test. A plain run uses the base database as is.

    Nothing is created off a base the ``_test`` guard is about to refuse.
    """
    worker = os.environ.get('PYTEST_XDIST_WORKER')
    if not worker or not _is_throwaway(base_url):
        return base_url
    url = make_url(base_url)
    name = f'{url.database}_{worker}'
    engine = create_engine(base_url, isolation_level='AUTOCOMMIT')
    with engine.connect() as connection:
        exists = connection.execute(
            text('SELECT 1 FROM pg_database WHERE datname = :name'),
            {'name': name}).scalar()
        if not exists:
            # template0: never connected to, so concurrent workers can all
            # copy it at once (template1 refuses while another session is on it)
            connection.execute(
                text(f'CREATE DATABASE "{name}" TEMPLATE template0'))
    engine.dispose()
    return url.set(database=name).render_as_string(hide_password=False)


TEST_DATABASE_URL = (
    _worker_database_url(_BASE_DATABASE_URL) if ON_POSTGRES else None)
if ON_POSTGRES:
    # Every create_app('testing') — the canonical fixture and the 15 local
    # ones alike — reads the URI off this class.
    TestingConfig.SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URL


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
    if not _is_throwaway(_BASE_DATABASE_URL):
        raise pytest.UsageError(
            'TEST_DATABASE_URL must be a Postgres database whose name ends in '
            f'"_test" (got {make_url(_BASE_DATABASE_URL).database!r}). '
            'The suite empties it.')


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
        # Same connect_args as every other suite connection (TestingConfig):
        # the UTC session zone, and — load-bearing on this TRUNCATE path — the
        # lock_timeout that turns a leaked transaction blocking the cleanup
        # into a loud failure instead of a hung run.
        engine = create_engine(
            TEST_DATABASE_URL, **TestingConfig.SQLALCHEMY_ENGINE_OPTIONS)
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
