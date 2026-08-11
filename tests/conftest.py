"""Canonical shared pytest fixtures (D11, Docket eng review 2026-08-11).

Additive by design: new docket tests consume these fixtures; the ~120
pre-existing test files keep their own local fixtures untouched (pytest
local fixtures shadow conftest ones, so nothing changes for them). The
full-suite migration onto this file is a future, dedicated PR — do not
grow this module beyond the canonical app/client pair without that PR.
"""
import pytest

from app import create_app
from extensions import db as _db


@pytest.fixture()
def app():
    """Canonical testing app: in-memory SQLite, tables created per test."""
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
