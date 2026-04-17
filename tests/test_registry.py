"""Unit tests for games.registry helper functions."""
import pytest
from unittest.mock import MagicMock

from app import create_app
from extensions import db
from models.user import User


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(app, username='u1', is_admin=False):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com', is_admin=is_admin)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.id


def _mock_entry(slug, status='open', is_featured=False,
                enrollment=None):
    """Build a GameRegistryEntry-shaped mock with get_enrollment returning `enrollment`."""
    from games.registry import GameRegistryEntry
    return GameRegistryEntry(
        slug=slug,
        display_name=slug.title(),
        description='desc',
        emoji='🎮',
        status=status,
        is_featured=is_featured,
        blueprint_index=f'{slug}.index',
        blueprint_join=f'{slug}.join',
        get_enrollment=lambda uid: enrollment,
        admin_enroll=lambda uid: enrollment,
    )


def test_get_entry_returns_matching_entry(app, monkeypatch):
    from games import registry
    fake = [_mock_entry('alpha'), _mock_entry('beta')]
    monkeypatch.setattr(registry, 'GAMES', fake)
    assert registry.get_entry('beta').slug == 'beta'


def test_get_entry_raises_on_unknown_slug(app, monkeypatch):
    from games import registry
    monkeypatch.setattr(registry, 'GAMES', [])
    with pytest.raises(KeyError):
        registry.get_entry('nonexistent')


def test_joined_games_returns_only_enrolled(app, monkeypatch):
    from games import registry
    uid = _make_user(app)
    entries = [
        _mock_entry('alpha', enrollment=object()),   # joined
        _mock_entry('beta', enrollment=None),        # not joined
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    with app.app_context():
        user = db.session.get(User, uid)
        joined = registry.joined_games(user)
    assert [e.slug for e in joined] == ['alpha']


def test_joined_games_empty_for_anonymous(app, monkeypatch):
    from games import registry
    monkeypatch.setattr(registry, 'GAMES', [_mock_entry('alpha', enrollment=object())])
    anon = MagicMock(is_authenticated=False)
    assert registry.joined_games(anon) == []


def test_available_games_returns_open_not_joined(app, monkeypatch):
    from games import registry
    uid = _make_user(app)
    entries = [
        _mock_entry('alpha', status='open', enrollment=object()),   # joined — excluded
        _mock_entry('beta',  status='open', enrollment=None),       # available
        _mock_entry('gamma', status='coming_soon', enrollment=None),# not open — excluded
        _mock_entry('delta', status='closed', enrollment=None),     # not open — excluded
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    with app.app_context():
        user = db.session.get(User, uid)
        result = registry.available_games(user)
    assert [e.slug for e in result] == ['beta']


def test_available_games_for_anonymous_returns_all_open(app, monkeypatch):
    from games import registry
    entries = [
        _mock_entry('alpha', status='open'),
        _mock_entry('beta', status='coming_soon'),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    anon = MagicMock(is_authenticated=False)
    assert [e.slug for e in registry.available_games(anon)] == ['alpha']


def test_coming_soon_games_returns_coming_soon_only(app, monkeypatch):
    from games import registry
    entries = [
        _mock_entry('alpha', status='open'),
        _mock_entry('beta', status='coming_soon'),
        _mock_entry('gamma', status='coming_soon'),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert [e.slug for e in registry.coming_soon_games()] == ['beta', 'gamma']


def test_featured_games_respects_is_featured_flag(app, monkeypatch):
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=True),
        _mock_entry('beta',  status='open', is_featured=False),
        _mock_entry('gamma', status='coming_soon', is_featured=True),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    anon = MagicMock(is_authenticated=False)
    result = registry.featured_games(anon)
    assert [e.slug for e in result] == ['alpha']  # coming_soon featured excluded


def test_games_for_user_pairs_entries_with_enrollments(app, monkeypatch):
    from games import registry
    uid = _make_user(app)
    enr = object()
    entries = [
        _mock_entry('alpha', enrollment=enr),
        _mock_entry('beta', enrollment=None),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    with app.app_context():
        user = db.session.get(User, uid)
        pairs = registry.games_for_user(user)
    assert [(p[0].slug, p[1]) for p in pairs] == [('alpha', enr), ('beta', None)]
