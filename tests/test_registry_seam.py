"""Registry seam contract (C2 slice 1, transition plan section 5).

The lounge dispatches through the registry's featured-game seam instead of
importing worldcup_state directly:

- ``GameRegistryEntry.lounge_state`` — per-game state-resolver callable.
- ``lounge_game()`` — the single featured-open game that owns the lounge.
- ``core.main.routes.index`` resolves state via ``lounge_game()``.
- ``'completed'`` status behaves correctly across every registry helper
  (the changeover flips WC to 'completed'; these are the semantics locks).

Rendering contract for this slice: WC stays open/featured, so the lounge
renders identically — tests/test_home_context.py remains the net.
"""
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from app import create_app
from extensions import db
from models.user import User
from tests._registry_helpers import set_is_featured, set_status


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _mock_entry(slug, status='open', is_featured=False, enrollment=None,
                lounge_state=None):
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
        lounge_state=lounge_state,
    )


def _make_user(app, username='seamuser'):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com')
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.get_id()


def _login(client, auth_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


# ── lounge_game() ─────────────────────────────────────────────────────────

def test_lounge_game_returns_featured_open_entry(app, monkeypatch):
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=False),
        _mock_entry('beta', status='open', is_featured=True),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert registry.lounge_game().slug == 'beta'


def test_lounge_game_excludes_featured_but_not_open(app, monkeypatch):
    """A featured entry that is coming_soon or completed never owns the lounge."""
    from games import registry
    entries = [
        _mock_entry('alpha', status='coming_soon', is_featured=True),
        _mock_entry('beta', status='completed', is_featured=True),
        _mock_entry('gamma', status='open', is_featured=True),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert registry.lounge_game().slug == 'gamma'


def test_lounge_game_none_when_no_featured_open_game(app, monkeypatch):
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=False),
        _mock_entry('beta', status='completed', is_featured=True),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert registry.lounge_game() is None


def test_lounge_game_real_config_is_worldcup(app):
    """Pre-changeover lock: WC owns the lounge until the atomic flip."""
    from games.registry import lounge_game
    entry = lounge_game()
    assert entry is not None
    assert entry.slug == 'worldcup'


def test_worldcup_entry_lounge_state_is_worldcup_state(app):
    """The WC entry's resolver IS the canonical worldcup_state (no wrapper drift)."""
    from games.registry import get_entry
    from games.worldcup.services.state import worldcup_state
    assert get_entry('worldcup').lounge_state is worldcup_state


def test_changeover_flip_hands_lounge_to_cfb(app, monkeypatch):
    """Simulate the atomic changeover (plan section 6 E) against the REAL
    registry: WC -> completed/unfeatured, CFB -> open/featured. The seam,
    not any hardcoded slug, must hand the lounge to CFB."""
    from games import registry
    set_status(monkeypatch, 'worldcup', 'completed')
    set_is_featured(monkeypatch, 'worldcup', False)
    set_status(monkeypatch, 'cfb', 'open')
    set_is_featured(monkeypatch, 'cfb', True)
    assert registry.lounge_game().slug == 'cfb'


# ── 'completed' status semantics across helpers ──────────────────────────

def test_completed_game_excluded_from_available(app, monkeypatch):
    from games import registry
    monkeypatch.setattr(registry, 'GAMES', [
        _mock_entry('alpha', status='completed'),
        _mock_entry('beta', status='open'),
    ])
    anon = MagicMock(is_authenticated=False)
    assert [e.slug for e in registry.available_games(anon)] == ['beta']


def test_completed_game_excluded_from_coming_soon(app, monkeypatch):
    from games import registry
    monkeypatch.setattr(registry, 'GAMES', [_mock_entry('alpha', status='completed')])
    assert registry.coming_soon_games() == []


def test_completed_game_still_joined_for_enrolled_user(app, monkeypatch):
    """Archive access: a completed game stays in joined_games (navbar) for
    its enrolled members. The WC archive must remain reachable post-flip."""
    from games import registry
    auth_id = _make_user(app)
    monkeypatch.setattr(registry, 'GAMES', [
        _mock_entry('alpha', status='completed', enrollment=object()),
        _mock_entry('beta', status='completed', enrollment=None),
    ])
    with app.app_context():
        user = User.query.filter_by(auth_id=auth_id).first()
        joined = registry.joined_games(user)
    assert [e.slug for e in joined] == ['alpha']


# ── lounge route dispatch through the seam ────────────────────────────────

def test_home_route_resolves_state_via_lounge_game(app, client, monkeypatch):
    """The home route must call the featured game's lounge_state resolver,
    not import worldcup_state directly."""
    from games import registry
    auth_id = _make_user(app)
    calls = []

    def fake_resolver():
        calls.append(True)
        return 'pre'

    patched = [
        replace(entry, lounge_state=fake_resolver)
        if entry.slug == 'worldcup' else entry
        for entry in registry.GAMES
    ]
    monkeypatch.setattr(registry, 'GAMES', patched)
    _login(client, auth_id)
    resp = client.get('/')
    assert resp.status_code == 200
    assert calls, 'lounge_state resolver was never called by the home route'
    assert b'home-shell--pre' in resp.data


def test_home_route_no_featured_game_falls_back_to_out_shell(app, client, monkeypatch):
    """Defensive fallback (unreachable while the changeover flip is atomic):
    an authenticated user with no featured-open game gets the out shell,
    never a 500."""
    from games import registry
    auth_id = _make_user(app)
    monkeypatch.setattr(
        registry, 'GAMES',
        [replace(e, is_featured=False) for e in registry.GAMES],
    )
    _login(client, auth_id)
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'home-shell--out' in resp.data


def test_home_route_anonymous_still_renders_out(app, client):
    """Anonymous dispatch is untouched by the seam."""
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'home-shell--out' in resp.data


def test_main_routes_no_direct_worldcup_state_import():
    """Source lock: core/main/routes.py resolves state only through the seam."""
    import inspect

    import core.main.routes as main_routes
    src = inspect.getsource(main_routes)
    assert 'worldcup_state' not in src
