"""Registry seam contract (C2 slices 1 + 2, transition plan section 5).

The lounge dispatches through the registry's featured-game seam instead of
importing worldcup modules directly:

- ``GameRegistryEntry.lounge_state`` — per-game state-resolver callable.
- ``GameRegistryEntry.lounge_context`` — per-game per-state context builder
  (slice 2: the WC builders moved to ``games/worldcup/services/lounge.py``).
- ``lounge_game()`` — the single featured-open game that owns the lounge;
  owning it requires BOTH callables (launch safety: flags alone never hand
  the lounge to a game whose lounge code hasn't shipped).
- ``core.main.routes.index`` resolves state via ``lounge_game()`` and picks
  the per-game partial tree (``<slug>/lounge``); ``build_home_context``
  overlays the featured game's context on the registry-generic base.
- ``'completed'`` status behaves correctly across every registry helper
  (the changeover flips WC to 'completed'; these are the semantics locks).

Rendering contract for both slices: WC stays open/featured, so the lounge
renders identically — tests/test_home_context.py remains the net.
"""
from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

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


def _stub_lounge_context(user, state):
    """Minimal context builder for mock entries (ownership tests that are
    not about the lounge_context gate itself)."""
    return {}


def _mock_entry(slug, status='open', is_featured=False, enrollment=None,
                lounge_state=None, lounge_context=_stub_lounge_context):
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
        lounge_context=lounge_context,
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
        _mock_entry('alpha', status='open', is_featured=False,
                    lounge_state=lambda: 'pre'),
        _mock_entry('beta', status='open', is_featured=True,
                    lounge_state=lambda: 'pre'),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert registry.lounge_game().slug == 'beta'


def test_lounge_game_excludes_featured_but_not_open(app, monkeypatch):
    """A featured entry that is coming_soon or completed never owns the lounge,
    resolver or not."""
    from games import registry
    entries = [
        _mock_entry('alpha', status='coming_soon', is_featured=True,
                    lounge_state=lambda: 'pre'),
        _mock_entry('beta', status='completed', is_featured=True,
                    lounge_state=lambda: 'post'),
        _mock_entry('gamma', status='open', is_featured=True,
                    lounge_state=lambda: 'live'),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert registry.lounge_game().slug == 'gamma'


def test_lounge_game_none_when_no_featured_open_game(app, monkeypatch):
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=False,
                    lounge_state=lambda: 'pre'),
        _mock_entry('beta', status='completed', is_featured=True,
                    lounge_state=lambda: 'post'),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert registry.lounge_game() is None


def test_lounge_game_skips_featured_open_entry_without_resolver(app, monkeypatch):
    """A game that cannot render the lounge never owns it: featured+open with
    no lounge_state resolver is skipped in favor of the next eligible entry."""
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=True, lounge_state=None),
        _mock_entry('beta', status='open', is_featured=True,
                    lounge_state=lambda: 'live'),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert registry.lounge_game().slug == 'beta'


def test_lounge_game_none_when_sole_featured_open_lacks_resolver(app, monkeypatch):
    """Launch safety: flipping a game featured+open before its resolver ships
    cannot hand it the lounge — the dispatch refuses, never crashes."""
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=True, lounge_state=None),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert registry.lounge_game() is None


def test_lounge_game_real_config_is_cfb(app):
    """Post-changeover lock (flipped 2026-08-11): CFB owns the lounge."""
    from games.registry import lounge_game
    entry = lounge_game()
    assert entry is not None
    assert entry.slug == 'cfb'


def test_worldcup_entry_lounge_state_is_worldcup_state(app):
    """The WC entry's resolver IS the canonical worldcup_state (no wrapper drift)."""
    from games.registry import get_entry
    from games.worldcup.services.state import worldcup_state
    assert get_entry('worldcup').lounge_state is worldcup_state


def test_changeover_flip_hands_lounge_to_cfb(app, monkeypatch):
    """Simulate the atomic changeover (plan section 6 E) against the REAL
    registry: WC -> completed/unfeatured, CFB -> open/featured. The seam,
    not any hardcoded slug, must hand the lounge to CFB.

    Since C2 slice 3 the CFB entry carries its real lounge callables, so
    the flip alone hands it the lounge -- exactly the two-line Phase 5
    changeover diff. The missing-callable cases are locked separately by
    the lacks_resolver / lacks_context_builder tests."""
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
        user = db.session.scalar(select(User).filter_by(auth_id=auth_id))
        joined = registry.joined_games(user)
    assert [e.slug for e in joined] == ['alpha']


# ── lounge route dispatch through the seam ────────────────────────────────

def test_home_route_resolves_state_via_lounge_game(app, client, monkeypatch):
    """The home route must call EVERY headliner's lounge_state resolver
    (never import a game's state function directly). Both real headliners
    get a spy so the test is wall-clock-independent."""
    from games import registry
    auth_id = _make_user(app)
    calls = []

    def make_resolver(slug):
        def fake_resolver():
            calls.append(slug)
            return 'pre'
        return fake_resolver

    patched = [
        replace(entry, lounge_state=make_resolver(entry.slug))
        if entry.slug in ('cfb', 'docket') else entry
        for entry in registry.GAMES
    ]
    monkeypatch.setattr(registry, 'GAMES', patched)
    _login(client, auth_id)
    resp = client.get('/')
    assert resp.status_code == 200
    assert sorted(calls) == ['cfb', 'docket'], (
        'the home route must resolve state through each headliner, '
        f'got {calls}'
    )
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


# ── lounge_context gating (C2 slice 2) ────────────────────────────────────

def test_lounge_game_skips_featured_open_entry_without_context_builder(app, monkeypatch):
    """Owning the lounge requires the context builder too: featured+open with
    a resolver but no lounge_context is skipped for the next eligible entry."""
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=True,
                    lounge_state=lambda: 'live', lounge_context=None),
        _mock_entry('beta', status='open', is_featured=True,
                    lounge_state=lambda: 'live'),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert registry.lounge_game().slug == 'beta'


def test_lounge_game_none_when_sole_featured_open_lacks_context_builder(app, monkeypatch):
    """Launch safety, slice-2 half: a resolver alone cannot hand a game the
    lounge — without its context builder the dispatch refuses, never 500s."""
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=True,
                    lounge_state=lambda: 'live', lounge_context=None),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert registry.lounge_game() is None


def test_worldcup_entry_lounge_context_is_build_lounge_context(app):
    """The WC entry's context builder IS the canonical moved module's entry
    point (no wrapper drift) — mirrors the lounge_state identity lock."""
    from games.registry import get_entry
    from games.worldcup.services.lounge import build_lounge_context
    assert get_entry('worldcup').lounge_context is build_lounge_context


def test_cfb_entry_lounge_state_is_cfb_lounge_state(app):
    """The CFB entry's resolver IS the canonical cfb_lounge_state (no
    wrapper drift) — mirrors the WC identity lock. Wiring the callables is
    safe pre-flip: CFB stays coming_soon/unfeatured, so lounge_game()
    never selects it until the Phase 5 changeover."""
    from games.cfb.services.lounge import cfb_lounge_state
    from games.registry import get_entry
    assert get_entry('cfb').lounge_state is cfb_lounge_state


def test_cfb_entry_lounge_context_is_build_lounge_context(app):
    """The CFB entry's context builder IS the canonical module entry point
    (no wrapper drift) — the slice-3 half of the CFB identity locks."""
    from games.cfb.services.lounge import build_lounge_context
    from games.registry import get_entry
    assert get_entry('cfb').lounge_context is build_lounge_context


# ── build_home_context dispatch through the seam (C2 slice 2) ─────────────

def test_build_home_context_dispatches_through_featured_lounge_context(app, monkeypatch):
    """Authenticated states: the dispatcher calls the featured game's
    lounge_context with (user, state) and overlays its dict on the
    registry-generic base (joined + coming-soon + commish note)."""
    from core.main.home_context import build_home_context
    from games import registry
    auth_id = _make_user(app, username='dispatchuser')
    calls = []

    def fake_context(user, state):
        calls.append((user, state))
        return {'sentinel': 42}

    entries = [
        _mock_entry('alpha', status='open', is_featured=True,
                    lounge_state=lambda: 'pre', lounge_context=fake_context),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    with app.app_context():
        user = db.session.scalar(select(User).filter_by(auth_id=auth_id))
        ctx = build_home_context(user, 'pre')
    assert calls == [(user, 'pre')]
    assert ctx['sentinel'] == 42
    assert ctx['joined_games'] == []
    assert ctx['coming_soon_games'] == []
    assert 'commish_paragraphs' in ctx
    # Slice 3: the dispatcher names the featured entry so registry-generic
    # partials (the compact tile strip) can render it slug-agnostically.
    assert ctx['lounge_entry'].slug == 'alpha'


def test_build_home_context_out_state_overlays_game_dict_on_registry_base(app, monkeypatch):
    """state=None (logged-out): base carries the registry tiles; the featured
    game's overlay wins on shared keys (WC supplies the real total_enrolled).
    No commish note on the out surface."""
    from core.main.home_context import build_home_context
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=True,
                    lounge_state=lambda: 'pre',
                    lounge_context=lambda user, state: {'total_enrolled': 7}),
        _mock_entry('beta', status='coming_soon'),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    with app.app_context():
        ctx = build_home_context(None, None)
    assert [e.slug for e in ctx['available_games']] == ['alpha']
    assert [e.slug for e in ctx['coming_soon_games']] == ['beta']
    assert ctx['total_enrolled'] == 7
    assert 'commish_paragraphs' not in ctx


def test_build_home_context_no_featured_game_returns_registry_base(app, monkeypatch):
    """Between-eras fallback (unreachable while the flip is atomic): no
    featured game means base context only — safe defaults, no game keys."""
    from core.main.home_context import build_home_context
    from games import registry
    monkeypatch.setattr(registry, 'GAMES', [_mock_entry('beta', status='coming_soon')])
    with app.app_context():
        ctx = build_home_context(None, None)
    assert ctx['available_games'] == []
    assert [e.slug for e in ctx['coming_soon_games']] == ['beta']
    assert ctx['total_enrolled'] == 0


def test_home_context_module_no_direct_worldcup_import():
    """Source lock: after the slice-2 extraction, core/main/home_context.py
    reaches WC data only through the registry seam — never a direct import.
    (Prose references to the moved module's path are fine; import lines
    are what would re-couple the dispatcher.)"""
    import inspect

    import core.main.home_context as home_context
    import_lines = [
        line for line in inspect.getsource(home_context).splitlines()
        if line.strip().startswith(('import ', 'from '))
    ]
    offenders = [line for line in import_lines if 'worldcup' in line]
    assert not offenders, f'direct WC import(s) in core dispatcher: {offenders}'


# ── per-game lounge partial tree (C2 slice 2) ─────────────────────────────

WC_LOUNGE_PARTIALS = [
    '_home_out.html', '_home_pre.html', '_home_live.html', '_home_post.html',
    '_ballot_card.html', '_champion_banner.html', '_countdown_card.html',
    '_dossier_card.html', '_recent_results.html', '_view_cta_card.html',
]


def test_wc_lounge_partials_moved_under_worldcup_lounge_tree():
    """The ten WC-specific lounge partials live in the WC-owned tree
    (games/worldcup/templates/worldcup/lounge/) and are gone from the
    shared main/ tree. The registry-generic partials (_game_tiles_compact,
    _commish_note, _dispatches, _game_card, index) stay shared."""
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    lounge_dir = repo / 'games' / 'worldcup' / 'templates' / 'worldcup' / 'lounge'
    main_dir = repo / 'core' / 'main' / 'templates' / 'main'
    for name in WC_LOUNGE_PARTIALS:
        assert (lounge_dir / name).exists(), f'{name} missing from WC lounge tree'
        assert not (main_dir / name).exists(), f'{name} still in shared main/ tree'
    for name in ('index.html', '_game_tiles_compact.html', '_commish_note.html',
                 '_dispatches.html', '_game_card.html'):
        assert (main_dir / name).exists(), f'shared partial {name} missing from main/'


def test_index_dispatcher_includes_via_lounge_tree():
    """index.html includes the state shells through the per-game lounge_tree
    context variable — no hardcoded main/_home_* (or worldcup/) paths."""
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    src = (repo / 'core' / 'main' / 'templates' / 'main' / 'index.html').read_text()
    assert "lounge_tree ~ '/_home_" in src
    assert "main/_home_" not in src
    assert 'worldcup' not in src


# ── lounge_games() — the multi-featured seam ──────────────────────────────

def test_lounge_games_returns_all_featured_open_in_order(app, monkeypatch):
    """Every featured-open entry with both callables is a headliner, in
    GAMES (billing) order."""
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=True,
                    lounge_state=lambda: 'pre'),
        _mock_entry('beta', status='open', is_featured=False,
                    lounge_state=lambda: 'pre'),
        _mock_entry('gamma', status='open', is_featured=True,
                    lounge_state=lambda: 'live'),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert [e.slug for e in registry.lounge_games()] == ['alpha', 'gamma']


def test_lounge_games_requires_both_callables_per_entry(app, monkeypatch):
    """The launch-safety gate is per entry: a featured-open game missing
    either lounge callable is skipped without disqualifying the others."""
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=True,
                    lounge_state=None),
        _mock_entry('beta', status='open', is_featured=True,
                    lounge_state=lambda: 'pre', lounge_context=None),
        _mock_entry('gamma', status='open', is_featured=True,
                    lounge_state=lambda: 'pre'),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert [e.slug for e in registry.lounge_games()] == ['gamma']


def test_lounge_game_is_first_of_lounge_games(app, monkeypatch):
    """lounge_game() survives as 'the first billing' for the archival
    page-mode branch and the legacy single-overlay path."""
    from games import registry
    entries = [
        _mock_entry('alpha', status='open', is_featured=True,
                    lounge_state=lambda: 'pre'),
        _mock_entry('beta', status='open', is_featured=True,
                    lounge_state=lambda: 'live'),
    ]
    monkeypatch.setattr(registry, 'GAMES', entries)
    assert registry.lounge_game().slug == 'alpha'
    assert registry.lounge_game() is registry.lounge_games()[0]


def test_worldcup_entry_is_page_mode_all_others_panel():
    """Exactly one archival full-page lounge tree exists: the World Cup's.
    Every other entry (and every future game) is a panel game."""
    from games.registry import GAMES
    modes = {entry.slug: entry.lounge_mode for entry in GAMES}
    assert modes.pop('worldcup') == 'page'
    assert set(modes.values()) == {'panel'}
