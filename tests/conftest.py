"""Canonical shared pytest fixtures (D11, Docket eng review 2026-08-11).

The whole suite runs on this pair since the 2026-08-21 migration (backlog
3.1): 103 exact-canonical local duplicates across 66 files were deleted.
The 16 files whose fixtures genuinely differ (FAKE_NOW seams, golf season
pins, module-scoped seeds) keep them locally — pytest resolves a local
fixture first, and conftest's ``client(app)`` binds to whichever ``app``
wins in the requesting module. The allowlist and the no-new-duplicates
rule are enforced by ``tests/test_conftest_lock.py``.

Keep this module to the canonical app/client pair; a fixture that only
some files need belongs in those files (and on the allowlist), not here.
"""
import pytest

from app import create_app
from extensions import db as _db


@pytest.fixture()
def app(monkeypatch):
    """Canonical testing app: in-memory SQLite, tables created per test.

    ENVIRONMENT is pinned too — code that reads os.environ directly (the
    *_FAKE_NOW seams) must see 'testing' even when a file is run without
    the ENVIRONMENT=testing prefix.
    """
    monkeypatch.setenv('ENVIRONMENT', 'testing')
    app = create_app('testing')
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    """Test client bound to the canonical app fixture."""
    return app.test_client()
