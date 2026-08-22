"""The `flask create-admin` CLI stores identifiers the way the web paths do.

Every web write site lowers the email before storing it (register, profile) —
the contract `utils/identifier.py` documents. The CLI is the one other writer,
so it must not be the path that persists a mixed-case email.
"""
import builtins

from sqlalchemy import select

from extensions import db
from models.user import User


def _answers(*values):
    """Return an input() stand-in that hands back the given answers in order."""
    it = iter(values)
    return lambda prompt='': next(it)


def test_create_admin_stores_email_lowered(app, monkeypatch):
    """A mixed-case email typed at the prompt is stored lowered, like register()."""
    monkeypatch.setattr(builtins, 'input', _answers('Commish', '  Brad@Example.COM '))
    monkeypatch.setattr('getpass.getpass', lambda prompt='': 'pw-not-used-here')

    result = app.test_cli_runner().invoke(args=['create-admin'])

    assert result.exit_code == 0, result.output
    with app.app_context():
        user = db.session.scalar(select(User).where(User.username == 'Commish'))
        assert user is not None
        assert user.is_admin is True
        assert user.email == 'brad@example.com'
