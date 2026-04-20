# Per-Game Enrollment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make per-game enrollment an explicit, uniform, user-initiated action uniform across World Cup, CFB, and Golf, driven by a single `games/registry.py` that future games slot into with one entry.

**Architecture:** Introduce `games/registry.py` (dataclass + helpers) as the single source of truth for game metadata and status. Each game blueprint exposes a thin `services/enrollment.py` module implementing `get_enrollment(user_id)` / `admin_enroll(user_id)` that the registry calls into. Shared `games/common.py` decorators (`@game_must_be_open`, `@enrollment_required`) gate `/join` and interior routes off the registry. Homepage + navbar consume helpers (`joined_games`, `available_games`, `coming_soon_games`) to render per-user sections. Golf loses its silent auto-enroll; CFB gains a `/join` page; World Cup keeps its existing pattern.

**Tech Stack:** Python 3.13, Flask 3 + Flask-Login + Flask-WTF, SQLAlchemy 2.0, Jinja2, Bootstrap 5.3, pytest.

**Working directory note:** The spec is at `docs/superpowers/specs/2026-04-17-per-game-enrollment-design.md`. Read it if any ambiguity arises. This plan assumes it is run in the main worktree on a branch like `feature/per-game-enrollment`.

---

## File Structure

### New files

| Path | Responsibility |
|---|---|
| `games/registry.py` | `GameRegistryEntry` dataclass, `GAMES` list, helper functions (`games_for_user`, `joined_games`, `available_games`, `coming_soon_games`, `featured_games`, `get_entry`) |
| `games/common.py` | Shared decorators (`game_must_be_open`, `enrollment_required`) |
| `games/worldcup/services/enrollment.py` | `get_enrollment(user_id)`, `admin_enroll(user_id)` |
| `games/cfb/services/enrollment.py` | Same interface, using `CFB_SEASON_YEAR` from app config |
| `games/golf/services/enrollment.py` | Same interface, using `SEASON_YEAR` from app config |
| `games/cfb/templates/cfb/join.html` | Crimson/midnight-palette join page |
| `games/golf/templates/golf/join.html` | Augusta green/gold-palette join page |
| `core/context.py` | Platform-wide Jinja context processor (`nav_games`), registered from `app.py` |
| `core/admin/enrollments.py` | Admin add-user-to-league route (uses `admin_bp`) |
| `core/admin/templates/admin/enrollments.html` | Form template for admin enroll |
| `core/main/templates/main/_game_card.html` | Card partial with `state` parameter (`joined`\|`available`\|`coming_soon`\|`logged_out`\|`featured`) |
| `scripts/wipe_pre_launch_enrollments.py` | Standalone one-shot DB wipe with `--confirm` / dry-run |
| `tests/test_registry.py` | Helper function unit tests |
| `tests/test_enrollment_gating.py` | Decorator behavior tests |
| `tests/test_join_flows.py` | Per-game `/join` route tests |
| `tests/test_golf_auto_enroll_removed.py` | Regression: unenrolled golf pick attempt redirects to `/golf/join` |
| `tests/test_admin_enrollments.py` | Admin add-user-to-league route tests |
| `tests/test_homepage_sections.py` | Homepage renders correct sections for each user state |

### Modified files

| Path | What changes |
|---|---|
| `games/worldcup/routes.py` | Apply `@game_must_be_open('worldcup')` to `/join` |
| `games/cfb/routes.py` | Add `/join` route; apply `@enrollment_required('cfb')` to pick-submit + pick-edit routes |
| `games/golf/routes.py` | Add `/join` route; **remove auto-enroll** at lines 354-361, 585-587, 660-662; apply `@enrollment_required('golf')` to `/submit-pick` |
| `core/main/routes.py` | Rewrite `index()` to drive off registry helpers |
| `core/main/templates/main/index.html` | Rewrite layout: hero, "Your Leagues", "Available to Join", "Coming Soon" sections |
| `templates/base.html` | Replace hardcoded nav `<li>` block with `{% for game in nav_games %}` loop |
| `core/admin/__init__.py` | Import new `enrollments` routes module |
| `core/admin/templates/admin/dashboard.html` | Add "Enrollments" management card |
| `app.py` | Register `core.context.register_context_processors(app)` |
| `.claude/skills/add-game/SKILL.md` | Add enrollment-contract checklist (registry entry, service module, `/join`, template, guards) |

### Deferred (executed after merge/deploy)

- Run `python scripts/wipe_pre_launch_enrollments.py --confirm` on the prod server once new code is deployed.

---

## Conventions

- **TDD first.** Each task starts with a failing test, implements the minimum to pass, then commits.
- **SQLAlchemy 2.0 style** — `db.session.get(Model, id)`, `db.get_or_404()`. `datetime.now(timezone.utc)`. Never `utcnow()` / pytz.
- **Testing config** sets `WTF_CSRF_ENABLED=False`; form POSTs may include a placeholder `csrf_token` field (see `tests/test_worldcup_admin.py`).
- **Admin auth pattern** (replicate exactly):
  ```python
  with client.session_transaction() as sess:
      sess['_user_id'] = str(admin_id)
      sess['_fresh'] = True
  ```
- **No raw SQL** — Flask-Migrate for any schema change. (This plan introduces no schema changes.)
- **Commit granularity** — commit at the end of each task. Messages use Conventional Commits (`feat:`, `refactor:`, `test:`, `docs:`, `chore:`).

---

## Task Breakdown

### Task 1: Registry dataclass + helpers (with failing tests)

**Files:**
- Create: `games/registry.py`
- Create: `tests/test_registry.py`

- [ ] **Step 1: Write failing tests for registry helpers**

Create `tests/test_registry.py`:

```python
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
```

- [ ] **Step 2: Run tests, verify all 9 fail**

Run: `venv/bin/python -m pytest tests/test_registry.py -v`
Expected: `ModuleNotFoundError: No module named 'games.registry'` or all 9 tests fail.

- [ ] **Step 3: Create `games/registry.py` with dataclass + helpers (empty GAMES list for now)**

```python
"""
Game Registry
==============
Single source of truth for game metadata, status, and per-user enrollment lookup.

Consumed by:
- core/main/routes.py (homepage sections)
- core/context.py (navbar)
- core/admin/enrollments.py (admin add-user form)
- games/common.py (decorators)
"""
from dataclasses import dataclass
from typing import Callable, Literal, Optional, Any

GameStatus = Literal['coming_soon', 'open', 'closed', 'completed']


@dataclass(frozen=True)
class GameRegistryEntry:
    slug: str
    display_name: str
    description: str
    emoji: str
    status: GameStatus
    is_featured: bool
    blueprint_index: str
    blueprint_join: str
    get_enrollment: Callable[[int], Optional[Any]]
    admin_enroll: Callable[[int], Any]


# Populated in Tasks 3, 5, 8. Intentionally empty at file-creation time so
# helpers remain testable against mock lists via monkeypatch.
GAMES: list[GameRegistryEntry] = []


def get_entry(slug: str) -> GameRegistryEntry:
    """Return the registry entry for the given slug. Raises KeyError if absent."""
    for entry in GAMES:
        if entry.slug == slug:
            return entry
    raise KeyError(f"Unknown game slug: {slug}")


def _is_authenticated(user) -> bool:
    return bool(getattr(user, 'is_authenticated', False))


def games_for_user(user) -> list[tuple[GameRegistryEntry, Optional[Any]]]:
    """Return every game paired with this user's current-season enrollment (or None)."""
    if not _is_authenticated(user):
        return [(entry, None) for entry in GAMES]
    return [(entry, entry.get_enrollment(user.id)) for entry in GAMES]


def joined_games(user) -> list[GameRegistryEntry]:
    """Games this user has a current-season enrollment for. Powers nav."""
    if not _is_authenticated(user):
        return []
    return [entry for entry, enr in games_for_user(user) if enr is not None]


def available_games(user) -> list[GameRegistryEntry]:
    """Open games the user has NOT joined. For anonymous users, all open games."""
    if not _is_authenticated(user):
        return [entry for entry in GAMES if entry.status == 'open']
    return [
        entry for entry, enr in games_for_user(user)
        if entry.status == 'open' and enr is None
    ]


def coming_soon_games() -> list[GameRegistryEntry]:
    """Games flagged coming_soon, regardless of user."""
    return [entry for entry in GAMES if entry.status == 'coming_soon']


def featured_games(user) -> list[GameRegistryEntry]:
    """Featured games with status='open' (coming_soon featured games are not shown)."""
    return [entry for entry in GAMES if entry.is_featured and entry.status == 'open']
```

- [ ] **Step 4: Run tests, verify all 9 pass**

Run: `venv/bin/python -m pytest tests/test_registry.py -v`
Expected: all 9 tests pass.

- [ ] **Step 5: Pyright check**

Run: `venv/bin/pyright games/registry.py tests/test_registry.py`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add games/registry.py tests/test_registry.py
git commit -m "feat(registry): add GameRegistryEntry dataclass + helper functions

Single source of truth for game metadata/status. Empty GAMES list until
per-game enrollment services are wired up in subsequent tasks."
```

---

### Task 2: Shared `@game_must_be_open` and `@enrollment_required` decorators

**Files:**
- Create: `games/common.py`
- Create: `tests/test_enrollment_gating.py`

- [ ] **Step 1: Write failing tests for both decorators**

Create `tests/test_enrollment_gating.py`:

```python
"""Tests for games.common decorators."""
import pytest
from flask import Flask, Blueprint

from app import create_app
from extensions import db
from models.user import User
from games.registry import GameRegistryEntry


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


def _make_user(app, username='u1', is_admin=False):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com', is_admin=is_admin)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _install_entry(monkeypatch, slug, status, enrollment=None, is_featured=False):
    from games import registry
    entry = GameRegistryEntry(
        slug=slug, display_name=slug.title(), description='d', emoji='🎮',
        status=status, is_featured=is_featured,
        blueprint_index=f'{slug}.index', blueprint_join=f'{slug}.join',
        get_enrollment=lambda uid: enrollment,
        admin_enroll=lambda uid: enrollment,
    )
    monkeypatch.setattr(registry, 'GAMES', [entry])
    return entry


# ── game_must_be_open ───────────────────────────────────────────────────

def test_game_must_be_open_passes_when_open(app, client, monkeypatch):
    _install_entry(monkeypatch, 'alpha', status='open')
    from games.common import game_must_be_open

    bp = Blueprint('alpha', __name__, url_prefix='/alpha')

    @bp.route('/join')
    @game_must_be_open('alpha')
    def join():
        return 'joined-page', 200

    @bp.route('/')
    def index():
        return 'index', 200
    app.register_blueprint(bp)

    resp = client.get('/alpha/join')
    assert resp.status_code == 200
    assert b'joined-page' in resp.data


def test_game_must_be_open_redirects_when_coming_soon(app, client, monkeypatch):
    _install_entry(monkeypatch, 'alpha', status='coming_soon')
    from games.common import game_must_be_open

    bp = Blueprint('alpha', __name__, url_prefix='/alpha')

    @bp.route('/join')
    @game_must_be_open('alpha')
    def join():
        return 'should-not-see', 200

    @bp.route('/')
    def index():
        return 'index', 200
    app.register_blueprint(bp)

    resp = client.get('/alpha/join', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.location.endswith('/')


# ── enrollment_required ──────────────────────────────────────────────────

def test_enrollment_required_passes_when_enrolled(app, client, monkeypatch):
    _install_entry(monkeypatch, 'alpha', status='open', enrollment=object())
    from games.common import enrollment_required

    bp = Blueprint('alpha', __name__, url_prefix='/alpha')

    @bp.route('/picks')
    @enrollment_required('alpha')
    def picks():
        return 'picks-page', 200

    @bp.route('/join')
    def join():
        return 'join-page', 200

    @bp.route('/')
    def index():
        return 'index', 200
    app.register_blueprint(bp)

    uid = _make_user(app)
    _login(client, uid)
    resp = client.get('/alpha/picks')
    assert resp.status_code == 200
    assert b'picks-page' in resp.data


def test_enrollment_required_redirects_to_join_when_not_enrolled(app, client, monkeypatch):
    _install_entry(monkeypatch, 'alpha', status='open', enrollment=None)
    from games.common import enrollment_required

    bp = Blueprint('alpha', __name__, url_prefix='/alpha')

    @bp.route('/picks')
    @enrollment_required('alpha')
    def picks():
        return 'should-not-see', 200

    @bp.route('/join')
    def join():
        return 'join-page', 200

    @bp.route('/')
    def index():
        return 'index', 200
    app.register_blueprint(bp)

    uid = _make_user(app)
    _login(client, uid)
    resp = client.get('/alpha/picks', follow_redirects=False)
    assert resp.status_code == 302
    assert '/alpha/join' in resp.location
    assert 'next=' in resp.location


def test_enrollment_required_404s_coming_soon_for_regular_user(app, client, monkeypatch):
    _install_entry(monkeypatch, 'alpha', status='coming_soon', enrollment=None)
    from games.common import enrollment_required

    bp = Blueprint('alpha', __name__, url_prefix='/alpha')

    @bp.route('/picks')
    @enrollment_required('alpha')
    def picks():
        return 'should-not-see', 200

    @bp.route('/join')
    def join():
        return 'join-page', 200

    @bp.route('/')
    def index():
        return 'index', 200
    app.register_blueprint(bp)

    uid = _make_user(app)
    _login(client, uid)
    resp = client.get('/alpha/picks')
    assert resp.status_code == 404


def test_enrollment_required_platform_admin_bypasses_coming_soon(app, client, monkeypatch):
    _install_entry(monkeypatch, 'alpha', status='coming_soon', enrollment=None)
    from games.common import enrollment_required

    bp = Blueprint('alpha', __name__, url_prefix='/alpha')

    @bp.route('/picks')
    @enrollment_required('alpha')
    def picks():
        return 'admin-sees', 200

    @bp.route('/join')
    def join():
        return 'join-page', 200

    @bp.route('/')
    def index():
        return 'index', 200
    app.register_blueprint(bp)

    admin_id = _make_user(app, username='admin', is_admin=True)
    _login(client, admin_id)
    resp = client.get('/alpha/picks')
    assert resp.status_code == 200
    assert b'admin-sees' in resp.data


def test_enrollment_required_403_when_closed_and_not_enrolled(app, client, monkeypatch):
    _install_entry(monkeypatch, 'alpha', status='closed', enrollment=None)
    from games.common import enrollment_required

    bp = Blueprint('alpha', __name__, url_prefix='/alpha')

    @bp.route('/picks')
    @enrollment_required('alpha')
    def picks():
        return 'should-not-see', 200

    @bp.route('/join')
    def join():
        return 'join-page', 200

    @bp.route('/')
    def index():
        return 'index', 200
    app.register_blueprint(bp)

    uid = _make_user(app)
    _login(client, uid)
    resp = client.get('/alpha/picks')
    assert resp.status_code == 403


def test_enrollment_required_redirects_anonymous_to_login(app, client, monkeypatch):
    _install_entry(monkeypatch, 'alpha', status='open', enrollment=None)
    from games.common import enrollment_required

    bp = Blueprint('alpha', __name__, url_prefix='/alpha')

    @bp.route('/picks')
    @enrollment_required('alpha')
    def picks():
        return 'should-not-see', 200

    @bp.route('/join')
    def join():
        return 'join-page', 200

    @bp.route('/')
    def index():
        return 'index', 200
    app.register_blueprint(bp)

    resp = client.get('/alpha/picks', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.location
```

- [ ] **Step 2: Run tests, verify all fail**

Run: `venv/bin/python -m pytest tests/test_enrollment_gating.py -v`
Expected: `ModuleNotFoundError: No module named 'games.common'` or all fail.

- [ ] **Step 3: Create `games/common.py`**

```python
"""
Shared decorators for per-game enrollment gating.
=================================================
Keyed off games.registry.GAMES so a single flag flip in the registry
controls behavior for every route using these decorators.
"""
from functools import wraps

from flask import redirect, url_for, flash, request, abort
from flask_login import current_user, login_required

from games.registry import get_entry


def game_must_be_open(slug: str):
    """Redirect to homepage with a flash if the game's registry status != 'open'.

    Apply to /join routes and any enrollment-mutating routes.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            entry = get_entry(slug)
            if entry.status != 'open':
                flash(
                    f'{entry.display_name} is not currently open for enrollment.',
                    'info',
                )
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def enrollment_required(slug: str):
    """Gate interior routes behind a current-season enrollment.

    Behavior by registry status:
      - coming_soon: 404 for non-platform-admins; platform admin bypasses.
      - open: enrolled passes; non-enrolled redirects to /<slug>/join?next=<url>.
      - closed: enrolled passes; non-enrolled 403.
      - completed: enrolled passes (read-only is the route's job); non-enrolled 403.

    Anonymous users are redirected to login (via @login_required).
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            entry = get_entry(slug)
            is_platform_admin = bool(
                current_user.is_authenticated and getattr(current_user, 'is_admin', False)
            )

            if entry.status == 'coming_soon':
                if is_platform_admin:
                    return f(*args, **kwargs)
                abort(404)

            enrollment = entry.get_enrollment(current_user.id)
            if enrollment is not None:
                return f(*args, **kwargs)

            if entry.status == 'open':
                flash(f'Join {entry.display_name} to continue.', 'info')
                return redirect(url_for(entry.blueprint_join, next=request.url))

            abort(403)
        return wrapper
    return decorator
```

- [ ] **Step 4: Run tests, verify all pass**

Run: `venv/bin/python -m pytest tests/test_enrollment_gating.py -v`
Expected: all 8 tests pass.

- [ ] **Step 5: Pyright check**

Run: `venv/bin/pyright games/common.py tests/test_enrollment_gating.py`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add games/common.py tests/test_enrollment_gating.py
git commit -m "feat(games): add @game_must_be_open and @enrollment_required decorators

Shared decorators gated off games.registry for uniform /join + interior
route protection. Covers coming_soon/open/closed/completed status semantics,
with platform admin bypass for coming_soon."
```

---

### Task 3: World Cup enrollment service + registry wiring

**Files:**
- Create: `games/worldcup/services/enrollment.py`
- Modify: `games/registry.py` (append World Cup entry to `GAMES`)

- [ ] **Step 1: Write failing unit test for the WC enrollment service**

Append to `tests/test_registry.py`:

```python
# ── World Cup enrollment service ─────────────────────────────────────────

def test_worldcup_get_enrollment_returns_none_when_absent(app):
    uid = _make_user(app, username='wcuser')
    from games.worldcup.services import enrollment
    with app.app_context():
        assert enrollment.get_enrollment(uid) is None


def test_worldcup_admin_enroll_is_idempotent(app):
    uid = _make_user(app, username='wcuser')
    from games.worldcup.services import enrollment
    with app.app_context():
        e1 = enrollment.admin_enroll(uid)
        e2 = enrollment.admin_enroll(uid)
        assert e1.id == e2.id
        assert e1.user_id == uid
        assert e1.season_year == 2026


def test_worldcup_entry_registered_in_GAMES(app):
    from games.registry import GAMES
    slugs = {e.slug for e in GAMES}
    assert 'worldcup' in slugs
```

- [ ] **Step 2: Run tests, verify 3 new tests fail**

Run: `venv/bin/python -m pytest tests/test_registry.py::test_worldcup_get_enrollment_returns_none_when_absent tests/test_registry.py::test_worldcup_admin_enroll_is_idempotent tests/test_registry.py::test_worldcup_entry_registered_in_GAMES -v`
Expected: ModuleNotFoundError / AssertionError.

- [ ] **Step 3: Create `games/worldcup/services/enrollment.py`**

```python
"""World Cup enrollment service — registry integration point."""
from typing import Optional

from extensions import db
from games.worldcup.models import WorldCupEnrollment
from games.worldcup.constants import SEASON_YEAR


def get_enrollment(user_id: int) -> Optional[WorldCupEnrollment]:
    """Return the user's current-season World Cup enrollment, or None."""
    return WorldCupEnrollment.query.filter_by(
        user_id=user_id, season_year=SEASON_YEAR
    ).first()


def admin_enroll(user_id: int) -> WorldCupEnrollment:
    """Idempotently enroll a user in the current World Cup season."""
    existing = get_enrollment(user_id)
    if existing is not None:
        return existing
    enrollment = WorldCupEnrollment(user_id=user_id, season_year=SEASON_YEAR)
    db.session.add(enrollment)
    db.session.commit()
    return enrollment
```

- [ ] **Step 4: Register World Cup in `games/registry.py`**

Append to `games/registry.py`, **replacing** the `GAMES: list[GameRegistryEntry] = []` line:

```python
from games.worldcup.services import enrollment as _worldcup_enrollment

GAMES: list[GameRegistryEntry] = [
    GameRegistryEntry(
        slug='worldcup',
        display_name='2026 FIFA World Cup',
        description=(
            'Pick 9 national teams across 5 tiers. Points accumulate as your teams '
            'win and advance through the bracket.'
        ),
        emoji='⚽',
        status='open',
        is_featured=True,
        blueprint_index='worldcup.index',
        blueprint_join='worldcup.join',
        get_enrollment=_worldcup_enrollment.get_enrollment,
        admin_enroll=_worldcup_enrollment.admin_enroll,
    ),
]
```

- [ ] **Step 5: Run tests, verify all pass (including existing registry tests via monkeypatch)**

Run: `venv/bin/python -m pytest tests/test_registry.py -v`
Expected: all pass. The monkeypatched tests replace `GAMES` so they're unaffected.

- [ ] **Step 6: Pyright check**

Run: `venv/bin/pyright games/worldcup/services/enrollment.py games/registry.py`
Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add games/worldcup/services/enrollment.py games/registry.py tests/test_registry.py
git commit -m "feat(worldcup): expose enrollment service + register in games.registry

games/worldcup/services/enrollment.py: get_enrollment/admin_enroll keyed
to SEASON_YEAR. Registry now knows about World Cup; subsequent tasks add
CFB and Golf."
```

---

### Task 4: Apply `@game_must_be_open('worldcup')` to WC `/join`

**Files:**
- Modify: `games/worldcup/routes.py` (add decorator on existing `/join` route at line 179)
- Add test class in: `tests/test_join_flows.py` (new file)

- [ ] **Step 1: Create `tests/test_join_flows.py` with WC section**

```python
"""Tests for /join flows across all games."""
import pytest
from unittest.mock import patch

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment


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


def _make_user(app, username='u1'):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com')
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _set_wc_status(monkeypatch, status):
    """Rewrite the WC registry entry's status for this test."""
    from games import registry
    original = registry.GAMES
    patched = [
        registry.GameRegistryEntry(
            slug=e.slug, display_name=e.display_name, description=e.description,
            emoji=e.emoji, status=(status if e.slug == 'worldcup' else e.status),
            is_featured=e.is_featured, blueprint_index=e.blueprint_index,
            blueprint_join=e.blueprint_join, get_enrollment=e.get_enrollment,
            admin_enroll=e.admin_enroll,
        ) for e in original
    ]
    monkeypatch.setattr(registry, 'GAMES', patched)


# ── World Cup /join ──────────────────────────────────────────────────────

def test_wc_join_anonymous_redirects_to_login(client):
    resp = client.get('/worldcup/join', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.location


def test_wc_join_logged_in_open_renders_form(app, client):
    uid = _make_user(app, 'wc1')
    _login(client, uid)
    resp = client.get('/worldcup/join')
    assert resp.status_code == 200
    assert b'Join' in resp.data


def test_wc_join_post_creates_enrollment(app, client):
    uid = _make_user(app, 'wc2')
    _login(client, uid)
    resp = client.post('/worldcup/join',
                       data={'display_name': '', 'csrf_token': 'x'},
                       follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        enr = WorldCupEnrollment.query.filter_by(user_id=uid).first()
        assert enr is not None
        assert enr.season_year == 2026


def test_wc_join_duplicate_redirects_to_dashboard(app, client):
    uid = _make_user(app, 'wc3')
    _login(client, uid)
    with app.app_context():
        db.session.add(WorldCupEnrollment(user_id=uid, season_year=2026))
        db.session.commit()
    resp = client.get('/worldcup/join', follow_redirects=False)
    assert resp.status_code == 302
    assert '/worldcup' in resp.location


def test_wc_join_rejected_when_status_not_open(app, client, monkeypatch):
    uid = _make_user(app, 'wc4')
    _login(client, uid)
    _set_wc_status(monkeypatch, 'closed')
    resp = client.get('/worldcup/join', follow_redirects=False)
    assert resp.status_code == 302
    # redirected to homepage
    assert resp.location.endswith('/')
```

- [ ] **Step 2: Run tests, verify `test_wc_join_rejected_when_status_not_open` fails**

Run: `venv/bin/python -m pytest tests/test_join_flows.py -v`
Expected: most pass, but `test_wc_join_rejected_when_status_not_open` FAILS because the guard isn't applied yet.

- [ ] **Step 3: Apply the guard to WC `/join`**

Edit `games/worldcup/routes.py`. At the top of the imports section, add:

```python
from games.common import game_must_be_open
```

Then modify the `/join` route around line 179-202:

```python
@worldcup_bp.route('/join', methods=['GET', 'POST'])
@login_required
@game_must_be_open('worldcup')
def join():
    """Enrollment page."""
    # ... existing body unchanged
```

- [ ] **Step 4: Run tests, verify all pass**

Run: `venv/bin/python -m pytest tests/test_join_flows.py -v`
Expected: all 5 tests pass.

- [ ] **Step 5: Pyright check + full existing test suite**

Run: `venv/bin/pyright games/worldcup/routes.py`
Expected: 0 errors.

Run: `venv/bin/python -m pytest tests/ -v`
Expected: no regressions (existing WC admin, scoring, UI tests still pass).

- [ ] **Step 6: Commit**

```bash
git add games/worldcup/routes.py tests/test_join_flows.py
git commit -m "feat(worldcup): gate /join behind @game_must_be_open

First application of the shared decorator. No behavior change while status
is 'open' (the default) — but flips of the registry constant now correctly
reject new joins at the route level."
```

---

### Task 5: CFB enrollment service + registry wiring

**Files:**
- Create: `games/cfb/services/enrollment.py`
- Modify: `games/registry.py`

- [ ] **Step 1: Append failing tests to `tests/test_registry.py`**

```python
# ── CFB enrollment service ───────────────────────────────────────────────

def test_cfb_get_enrollment_returns_none_when_absent(app):
    uid = _make_user(app, username='cfbuser')
    from games.cfb.services import enrollment
    with app.app_context():
        assert enrollment.get_enrollment(uid) is None


def test_cfb_admin_enroll_is_idempotent(app):
    uid = _make_user(app, username='cfbuser')
    from games.cfb.services import enrollment
    with app.app_context():
        e1 = enrollment.admin_enroll(uid)
        e2 = enrollment.admin_enroll(uid)
        assert e1.id == e2.id
        assert e1.user_id == uid
        assert e1.season_year == 2026


def test_cfb_entry_registered_in_GAMES(app):
    from games.registry import GAMES
    slugs = {e.slug for e in GAMES}
    assert 'cfb' in slugs
```

- [ ] **Step 2: Run tests, verify 3 fail**

Run: `venv/bin/python -m pytest tests/test_registry.py -k cfb -v`
Expected: fail.

- [ ] **Step 3: Create `games/cfb/services/enrollment.py`**

CFB stores `SEASON_YEAR` in app config (`CFB_SEASON_YEAR`), not a module constant. Use `current_app` to read it.

```python
"""CFB Survivor enrollment service — registry integration point."""
from typing import Optional

from flask import current_app

from extensions import db
from games.cfb.models import CfbEnrollment


def _season_year() -> int:
    return current_app.config.get('CFB_SEASON_YEAR', 2026)


def get_enrollment(user_id: int) -> Optional[CfbEnrollment]:
    """Return the user's current-season CFB enrollment, or None."""
    return CfbEnrollment.query.filter_by(
        user_id=user_id, season_year=_season_year()
    ).first()


def admin_enroll(user_id: int) -> CfbEnrollment:
    """Idempotently enroll a user in the current CFB season."""
    existing = get_enrollment(user_id)
    if existing is not None:
        return existing
    enrollment = CfbEnrollment(user_id=user_id, season_year=_season_year())
    db.session.add(enrollment)
    db.session.commit()
    return enrollment
```

- [ ] **Step 4: Add CFB entry to `games/registry.py`**

Append below the existing `_worldcup_enrollment` import:

```python
from games.cfb.services import enrollment as _cfb_enrollment
```

Append inside the `GAMES` list (after the World Cup entry):

```python
    GameRegistryEntry(
        slug='cfb',
        display_name='CFB Survivor Pool',
        description=(
            'Weekly college football picks against the spread. Two lives. '
            'Last survivor wins.'
        ),
        emoji='🏈',
        status='coming_soon',
        is_featured=False,
        blueprint_index='cfb.index',
        blueprint_join='cfb.join',
        get_enrollment=_cfb_enrollment.get_enrollment,
        admin_enroll=_cfb_enrollment.admin_enroll,
    ),
```

- [ ] **Step 5: Run tests, verify pass**

Run: `venv/bin/python -m pytest tests/test_registry.py -v`
Expected: all pass.

- [ ] **Step 6: Pyright check**

Run: `venv/bin/pyright games/cfb/services/enrollment.py games/registry.py`
Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add games/cfb/services/enrollment.py games/registry.py tests/test_registry.py
git commit -m "feat(cfb): expose enrollment service + register in games.registry

CFB registered as 'coming_soon' — no /join route yet (next task). No
behavior change for existing routes; CfbEnrollment continues to be seeded
by existing paths until Task 6."
```

---

### Task 6: CFB `/join` route + template

**Files:**
- Modify: `games/cfb/routes.py` (add `/join` route)
- Create: `games/cfb/templates/cfb/join.html`
- Update: `tests/test_join_flows.py` (add CFB section)

- [ ] **Step 1: Add CFB join tests to `tests/test_join_flows.py`**

Append:

```python
# ── CFB /join ────────────────────────────────────────────────────────────

def _set_status(monkeypatch, slug, status):
    from games import registry
    patched = [
        registry.GameRegistryEntry(
            slug=e.slug, display_name=e.display_name, description=e.description,
            emoji=e.emoji, status=(status if e.slug == slug else e.status),
            is_featured=e.is_featured, blueprint_index=e.blueprint_index,
            blueprint_join=e.blueprint_join, get_enrollment=e.get_enrollment,
            admin_enroll=e.admin_enroll,
        ) for e in registry.GAMES
    ]
    monkeypatch.setattr(registry, 'GAMES', patched)


def test_cfb_join_anonymous_redirects_to_login(client):
    resp = client.get('/cfb/join', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.location


def test_cfb_join_coming_soon_rejects_logged_in(app, client):
    """CFB is seeded 'coming_soon' in registry, so /join must reject even
    logged-in users until status flips to 'open'."""
    uid = _make_user(app, 'cfb1')
    _login(client, uid)
    resp = client.get('/cfb/join', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.location.endswith('/')


def test_cfb_join_open_renders_form(app, client, monkeypatch):
    _set_status(monkeypatch, 'cfb', 'open')
    uid = _make_user(app, 'cfb2')
    _login(client, uid)
    resp = client.get('/cfb/join')
    assert resp.status_code == 200
    assert b'CFB Survivor' in resp.data


def test_cfb_join_post_creates_enrollment(app, client, monkeypatch):
    _set_status(monkeypatch, 'cfb', 'open')
    uid = _make_user(app, 'cfb3')
    _login(client, uid)
    resp = client.post('/cfb/join',
                       data={'display_name': '', 'csrf_token': 'x'},
                       follow_redirects=False)
    assert resp.status_code == 302
    from games.cfb.models import CfbEnrollment
    with app.app_context():
        enr = CfbEnrollment.query.filter_by(user_id=uid).first()
        assert enr is not None
        assert enr.season_year == 2026


def test_cfb_join_duplicate_redirects_to_dashboard(app, client, monkeypatch):
    _set_status(monkeypatch, 'cfb', 'open')
    uid = _make_user(app, 'cfb4')
    _login(client, uid)
    from games.cfb.models import CfbEnrollment
    with app.app_context():
        db.session.add(CfbEnrollment(user_id=uid, season_year=2026))
        db.session.commit()
    resp = client.get('/cfb/join', follow_redirects=False)
    assert resp.status_code == 302
    assert '/cfb' in resp.location
```

- [ ] **Step 2: Run, verify CFB tests fail**

Run: `venv/bin/python -m pytest tests/test_join_flows.py -k cfb -v`
Expected: 404s because `/cfb/join` doesn't exist yet.

- [ ] **Step 3: Add `/join` route to `games/cfb/routes.py`**

Add near the top of the imports:

```python
from games.common import game_must_be_open
```

Add a new route below the existing `index()`:

```python
@cfb_bp.route('/join', methods=['GET', 'POST'])
@login_required
@game_must_be_open('cfb')
def join():
    """Enrollment page for CFB Survivor."""
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    existing = CfbEnrollment.query.filter_by(
        user_id=current_user.id, season_year=season_year
    ).first()
    if existing:
        flash('You are already enrolled in the CFB Survivor Pool!', 'info')
        return redirect(url_for('cfb.index'))

    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        enrollment = CfbEnrollment(
            user_id=current_user.id,
            season_year=season_year,
            display_name=display_name or None,
        )
        db.session.add(enrollment)
        db.session.commit()
        flash('Welcome to the CFB Survivor Pool!', 'success')
        return redirect(url_for('cfb.index'))

    return render_template('cfb/join.html')
```

- [ ] **Step 4: Create `games/cfb/templates/cfb/join.html`**

```jinja
{% extends "base.html" %}
{% block title %}Join — CFB Survivor Pool{% endblock %}

{% block content %}
<div class="page-hero">
  <div class="hero-glow"></div>
  <div class="container">
    <h1>Join the CFB Survivor Pool</h1>
    <p class="lead mb-0">{{ cfb_season_year }} College Football Season &mdash; ${{ cfb_entry_fee }} entry</p>
  </div>
</div>

<div class="container pb-5">
  <div class="row justify-content-center">
    <div class="col-lg-6 col-md-8">

      <div class="card border-0 shadow-sm animate-in">
        <div class="card-body p-4">
          <h3 class="mb-3" style="font-family:'Teko',sans-serif; text-transform:uppercase; letter-spacing:.04em;">How It Works</h3>
          <ul class="mb-4">
            <li>Each week, pick <strong>one FBS team</strong> to win outright</li>
            <li>You have <strong>two lives</strong> — survive a wrong pick once</li>
            <li>Teams can only be used once per regular season</li>
            <li>Tiebreaker: lowest cumulative spread of picked favorites</li>
          </ul>

          <form method="POST">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>

            <div class="mb-3">
              <label for="display_name" class="form-label">Display Name <small class="text-muted">(optional)</small></label>
              <input type="text" class="form-control" id="display_name" name="display_name"
                     placeholder="{{ current_user.username }}" maxlength="80">
              <div class="form-text">Leave blank to use your username.</div>
            </div>

            <button type="submit" class="btn btn-game btn-lg w-100">
              <i class="bi bi-flag-fill me-2"></i>Join the Pool
            </button>
          </form>
        </div>
      </div>

    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Run tests, verify all CFB join tests pass**

Run: `venv/bin/python -m pytest tests/test_join_flows.py -k cfb -v`
Expected: 5 pass.

- [ ] **Step 6: Pyright + full suite**

Run: `venv/bin/pyright games/cfb/routes.py`
Run: `venv/bin/python -m pytest tests/ -v`
Expected: 0 pyright errors, no regressions.

- [ ] **Step 7: Commit**

```bash
git add games/cfb/routes.py games/cfb/templates/cfb/join.html tests/test_join_flows.py
git commit -m "feat(cfb): add /join route + template with @game_must_be_open guard

Route idle while CFB registry status='coming_soon' but renders correctly
once flipped to 'open'. Uses the CFB crimson palette via the existing
.game-cfb body class + shared .btn-game/.page-hero components."
```

---

### Task 7: Gate CFB pick-mutation routes behind `@enrollment_required('cfb')`

**Files:**
- Modify: `games/cfb/routes.py`

Identify pick routes first. Known pick-related routes in `games/cfb/routes.py`:
- Pick submission POST (search for `CfbPick(`)
- Any `/pick` or `/my-picks` interior route

- [ ] **Step 1: Locate pick routes**

Run:
```bash
venv/bin/python -c "import importlib; m=importlib.import_module('games.cfb.routes'); \
from games.cfb import cfb_bp; print('\n'.join(sorted(r.rule for r in cfb_bp.app.url_map.iter_rules() if r.endpoint.startswith('cfb.'))))" 2>/dev/null || \
venv/bin/python -c "from app import create_app; app=create_app('testing'); \
print('\n'.join(sorted(r.rule + ' -> ' + r.endpoint for r in app.url_map.iter_rules() if r.endpoint.startswith('cfb.'))))"
```

Expected: a list of CFB routes — identify the ones that render pick forms or accept pick POSTs. Typical: `/cfb/pick`, `/cfb/pick/<week>`, `/cfb/my-picks`.

- [ ] **Step 2: Write a regression test ensuring a non-enrolled user hitting `/cfb/pick` (or the first pick-mutation route identified) redirects to `/cfb/join`**

Append to `tests/test_join_flows.py`:

```python
def test_cfb_pick_route_redirects_non_enrolled_to_join(app, client, monkeypatch):
    """Regression: an unenrolled logged-in user hitting a CFB pick route
    is redirected to /cfb/join?next=..., NOT silently auto-enrolled."""
    _set_status(monkeypatch, 'cfb', 'open')
    uid = _make_user(app, 'cfb_pick')
    _login(client, uid)
    # Substitute the actual pick route discovered in Step 1.
    # If no pick route exists yet, this test can stay skipped with pytest.skip.
    resp = client.get('/cfb/my-picks', follow_redirects=False)
    if resp.status_code == 404:
        pytest.skip("CFB my-picks route not present; adjust URL when adding")
    assert resp.status_code == 302
    assert '/cfb/join' in resp.location
```

- [ ] **Step 3: Run — verify fails (or skips) before change**

Run: `venv/bin/python -m pytest tests/test_join_flows.py::test_cfb_pick_route_redirects_non_enrolled_to_join -v`

- [ ] **Step 4: Apply `@enrollment_required('cfb')` decorator to each pick-mutation route**

In `games/cfb/routes.py`, add import at top:

```python
from games.common import enrollment_required
```

For each pick-mutation route identified in Step 1 (typical candidates: `my_picks`, `submit_pick`, and any route that creates/updates a `CfbPick`), stack the decorator after `@login_required`:

```python
@cfb_bp.route('/my-picks')
@login_required
@enrollment_required('cfb')
def my_picks():
    # unchanged body
    ...
```

Note: leave **public** routes (standings `/`, `/results`, admin routes already guarded by `@cfb_admin_required`) untouched.

- [ ] **Step 5: Run the test, verify pass**

Run: `venv/bin/python -m pytest tests/test_join_flows.py -v`
Expected: pass.

- [ ] **Step 6: Full suite regression**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: no regressions.

- [ ] **Step 7: Commit**

```bash
git add games/cfb/routes.py tests/test_join_flows.py
git commit -m "feat(cfb): gate pick-mutation routes behind @enrollment_required

Non-enrolled users hitting /cfb/my-picks (and other pick routes) now
redirect to /cfb/join?next=<url> rather than 200-ing. Public standings
and weekly-results pages remain fully public per spec."
```

---

### Task 8: Golf enrollment service + registry wiring

**Files:**
- Create: `games/golf/services/enrollment.py`
- Modify: `games/registry.py`

- [ ] **Step 1: Append failing golf registry tests to `tests/test_registry.py`**

```python
# ── Golf enrollment service ──────────────────────────────────────────────

def test_golf_get_enrollment_returns_none_when_absent(app):
    uid = _make_user(app, username='golfuser')
    from games.golf.services import enrollment
    with app.app_context():
        assert enrollment.get_enrollment(uid) is None


def test_golf_admin_enroll_is_idempotent(app):
    uid = _make_user(app, username='golfuser')
    from games.golf.services import enrollment
    with app.app_context():
        e1 = enrollment.admin_enroll(uid)
        e2 = enrollment.admin_enroll(uid)
        assert e1.id == e2.id
        assert e1.user_id == uid
        assert e1.season_year == 2026


def test_golf_entry_registered_in_GAMES(app):
    from games.registry import GAMES
    slugs = {e.slug for e in GAMES}
    assert 'golf' in slugs
```

- [ ] **Step 2: Run — verify fail**

Run: `venv/bin/python -m pytest tests/test_registry.py -k golf -v`

- [ ] **Step 3: Create `games/golf/services/enrollment.py`**

Golf uses `SEASON_YEAR` from app config (not a module constant).

```python
"""Golf Pick 'Em enrollment service — registry integration point."""
from typing import Optional

from flask import current_app

from extensions import db
from games.golf.models import GolfEnrollment


def _season_year() -> int:
    return current_app.config['SEASON_YEAR']


def get_enrollment(user_id: int) -> Optional[GolfEnrollment]:
    """Return the user's current-season Golf enrollment, or None."""
    return GolfEnrollment.query.filter_by(
        user_id=user_id, season_year=_season_year()
    ).first()


def admin_enroll(user_id: int) -> GolfEnrollment:
    """Idempotently enroll a user in the current Golf season."""
    existing = get_enrollment(user_id)
    if existing is not None:
        return existing
    enrollment = GolfEnrollment(user_id=user_id, season_year=_season_year())
    db.session.add(enrollment)
    db.session.commit()
    return enrollment
```

- [ ] **Step 4: Register golf in `games/registry.py`**

Add import:

```python
from games.golf.services import enrollment as _golf_enrollment
```

Append the entry to `GAMES` (after CFB):

```python
    GameRegistryEntry(
        slug='golf',
        display_name="Golf Pick 'Em",
        description=(
            'Season-long PGA Tour fantasy. Pick one golfer per tournament. '
            'Points = prize money.'
        ),
        emoji='⛳',
        status='coming_soon',
        is_featured=False,
        blueprint_index='golf.index',
        blueprint_join='golf.join',
        get_enrollment=_golf_enrollment.get_enrollment,
        admin_enroll=_golf_enrollment.admin_enroll,
    ),
```

- [ ] **Step 5: Run all registry tests**

Run: `venv/bin/python -m pytest tests/test_registry.py -v`
Expected: all pass.

- [ ] **Step 6: Pyright**

Run: `venv/bin/pyright games/golf/services/enrollment.py games/registry.py`

- [ ] **Step 7: Commit**

```bash
git add games/golf/services/enrollment.py games/registry.py tests/test_registry.py
git commit -m "feat(golf): expose enrollment service + register in games.registry

Golf enters the registry as 'coming_soon'. Auto-enroll behavior in
routes.py is still present; Task 10 removes it."
```

---

### Task 9: Golf `/join` route + template

**Files:**
- Modify: `games/golf/routes.py`
- Create: `games/golf/templates/golf/join.html`
- Update: `tests/test_join_flows.py`

- [ ] **Step 1: Append golf join tests to `tests/test_join_flows.py`**

```python
# ── Golf /join ───────────────────────────────────────────────────────────

def test_golf_join_anonymous_redirects_to_login(client):
    resp = client.get('/golf/join', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.location


def test_golf_join_coming_soon_rejects(app, client):
    uid = _make_user(app, 'g1')
    _login(client, uid)
    resp = client.get('/golf/join', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.location.endswith('/')


def test_golf_join_open_renders_form(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    uid = _make_user(app, 'g2')
    _login(client, uid)
    resp = client.get('/golf/join')
    assert resp.status_code == 200
    assert b"Pick 'Em" in resp.data or b"Golf" in resp.data


def test_golf_join_post_creates_enrollment(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    uid = _make_user(app, 'g3')
    _login(client, uid)
    resp = client.post('/golf/join', data={'csrf_token': 'x'}, follow_redirects=False)
    assert resp.status_code == 302
    from games.golf.models import GolfEnrollment
    with app.app_context():
        enr = GolfEnrollment.query.filter_by(user_id=uid).first()
        assert enr is not None
        assert enr.season_year == 2026


def test_golf_join_duplicate_redirects_to_dashboard(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    uid = _make_user(app, 'g4')
    _login(client, uid)
    from games.golf.models import GolfEnrollment
    with app.app_context():
        db.session.add(GolfEnrollment(user_id=uid, season_year=2026))
        db.session.commit()
    resp = client.get('/golf/join', follow_redirects=False)
    assert resp.status_code == 302
    assert '/golf' in resp.location
```

- [ ] **Step 2: Run — tests fail (no route yet)**

Run: `venv/bin/python -m pytest tests/test_join_flows.py -k golf -v`

- [ ] **Step 3: Add `/join` to `games/golf/routes.py`**

Add near the top:

```python
from games.common import game_must_be_open
```

Add a new route below the existing `index()` function:

```python
@golf_bp.route('/join', methods=['GET', 'POST'])
@login_required
@game_must_be_open('golf')
def join():
    """Enrollment page for Golf Pick 'Em."""
    season_year = current_app.config['SEASON_YEAR']
    existing = GolfEnrollment.query.filter_by(
        user_id=current_user.id, season_year=season_year
    ).first()
    if existing:
        flash("You are already enrolled in Golf Pick 'Em!", 'info')
        return redirect(url_for('golf.index'))

    if request.method == 'POST':
        enrollment = GolfEnrollment(
            user_id=current_user.id,
            season_year=season_year,
        )
        db.session.add(enrollment)
        db.session.commit()
        flash("Welcome to Golf Pick 'Em!", 'success')
        return redirect(url_for('golf.index'))

    return render_template('golf/join.html')
```

- [ ] **Step 4: Create `games/golf/templates/golf/join.html`**

```jinja
{% extends "base.html" %}
{% block title %}Join — Golf Pick 'Em{% endblock %}

{% block content %}
<div class="page-hero">
  <div class="hero-glow"></div>
  <div class="container">
    <h1>Join Golf Pick 'Em</h1>
    <p class="lead mb-0">{{ season_year }} PGA Tour Season &mdash; ${{ entry_fee }} entry</p>
  </div>
</div>

<div class="container pb-5">
  <div class="row justify-content-center">
    <div class="col-lg-6 col-md-8">

      <div class="card border-0 shadow-sm animate-in">
        <div class="card-body p-4">
          <h3 class="mb-3" style="font-family:'Teko',sans-serif; text-transform:uppercase; letter-spacing:.04em;">How It Works</h3>
          <ul class="mb-4">
            <li>Pick <strong>one primary + one backup golfer</strong> per tournament</li>
            <li>Points equal actual prize money earned by your active pick</li>
            <li>Each golfer can be used only <strong>once per season</strong></li>
            <li>Backup activates if your primary withdraws before Round 2</li>
            <li>Majors earn 1.5× points; team events half</li>
          </ul>

          <form method="POST">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>

            <button type="submit" class="btn btn-game btn-lg w-100">
              <i class="bi bi-flag-fill me-2"></i>Join the League
            </button>
          </form>
        </div>
      </div>

    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Run tests, all golf join tests pass**

Run: `venv/bin/python -m pytest tests/test_join_flows.py -k golf -v`

- [ ] **Step 6: Pyright + full suite**

Run: `venv/bin/pyright games/golf/routes.py`
Run: `venv/bin/python -m pytest tests/ -v`

- [ ] **Step 7: Commit**

```bash
git add games/golf/routes.py games/golf/templates/golf/join.html tests/test_join_flows.py
git commit -m "feat(golf): add /join route + template with @game_must_be_open guard

Golf join page uses the Augusta green/gold palette via .game-golf body
class + shared .btn-game component. Auto-enroll removal happens in the
next task."
```

---

### Task 10: Remove golf auto-enroll from pick-submission route + gate it

**Files:**
- Modify: `games/golf/routes.py`
- Create: `tests/test_golf_auto_enroll_removed.py`

This is the most behaviorally significant task — it's the primary bug the spec is fixing.

- [ ] **Step 1: Write the regression test**

Create `tests/test_golf_auto_enroll_removed.py`:

```python
"""Regression tests: golf pick routes must NOT silently auto-enroll users."""
import pytest
from datetime import datetime, timedelta, timezone

from app import create_app
from extensions import db
from models.user import User
from games.golf.models import GolfEnrollment, GolfTournament


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


def _make_user(app, username='gu', is_admin=False):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com', is_admin=is_admin)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _set_golf_open(monkeypatch):
    from games import registry
    patched = [
        registry.GameRegistryEntry(
            slug=e.slug, display_name=e.display_name, description=e.description,
            emoji=e.emoji, status=('open' if e.slug == 'golf' else e.status),
            is_featured=e.is_featured, blueprint_index=e.blueprint_index,
            blueprint_join=e.blueprint_join, get_enrollment=e.get_enrollment,
            admin_enroll=e.admin_enroll,
        ) for e in registry.GAMES
    ]
    monkeypatch.setattr(registry, 'GAMES', patched)


def _seed_open_tournament(app):
    with app.app_context():
        t = GolfTournament(
            tourn_id='TEST-1',
            name='Test Open',
            season_year=2026,
            start_date=datetime.now(timezone.utc).date(),
            end_date=(datetime.now(timezone.utc) + timedelta(days=3)).date(),
            deadline=datetime.now(timezone.utc) + timedelta(days=1),
            status='upcoming',
        )
        db.session.add(t)
        db.session.commit()
        return t.id


def test_submit_pick_redirects_unenrolled_user_to_join(app, client, monkeypatch):
    _set_golf_open(monkeypatch)
    uid = _make_user(app, 'not_enrolled')
    tid = _seed_open_tournament(app)
    _login(client, uid)

    resp = client.get(f'/golf/submit-pick/{tid}', follow_redirects=False)
    assert resp.status_code == 302
    assert '/golf/join' in resp.location


def test_submit_pick_does_not_create_enrollment_when_user_not_joined(app, client, monkeypatch):
    _set_golf_open(monkeypatch)
    uid = _make_user(app, 'not_enrolled2')
    tid = _seed_open_tournament(app)
    _login(client, uid)

    client.get(f'/golf/submit-pick/{tid}', follow_redirects=False)

    with app.app_context():
        assert GolfEnrollment.query.filter_by(user_id=uid).count() == 0
```

Note: the test assumes `GolfTournament` fields match the model. Adjust field names if the constructor signature differs — inspect `games/golf/models.py` for the exact schema and trim unused required fields. Any required NOT-NULL without a default should be filled in.

- [ ] **Step 2: Run — expect failure (currently auto-enrolls)**

Run: `venv/bin/python -m pytest tests/test_golf_auto_enroll_removed.py -v`
Expected: `test_submit_pick_redirects_unenrolled_user_to_join` fails (200/other instead of 302 to /golf/join), and `test_submit_pick_does_not_create_enrollment_when_user_not_joined` fails (finds 1 enrollment).

- [ ] **Step 3: Remove the auto-enroll block from `games/golf/routes.py` submit-pick handler**

Edit `games/golf/routes.py` **lines 354-361** (the current auto-enroll block). Replace:

```python
    # Get or create enrollment
    enrollment = GolfEnrollment.query.filter_by(
        user_id=current_user.id, season_year=season_year
    ).first()
    if not enrollment:
        enrollment = GolfEnrollment(user_id=current_user.id, season_year=season_year)
        db.session.add(enrollment)
        db.session.commit()
```

With:

```python
    # Enrollment is required; decorator above already short-circuits,
    # but we still need the object for used-player-ids lookup.
    enrollment = GolfEnrollment.query.filter_by(
        user_id=current_user.id, season_year=season_year
    ).first()
```

Then apply the decorator on the route. Locate the route at approximately line 336 (`@golf_bp.route('/submit-pick/<int:tournament_id>', ...)`). Stack `@enrollment_required('golf')` after `@login_required`:

```python
@golf_bp.route('/submit-pick/<int:tournament_id>', methods=['GET', 'POST'])
@login_required
@enrollment_required('golf')
def submit_pick(tournament_id):
    ...
```

Add to imports at top:

```python
from games.common import game_must_be_open, enrollment_required
```

- [ ] **Step 4: Apply `@enrollment_required('golf')` to `my_picks` too**

`my_picks` at approximately line 440 — also a user-specific interior route. Stack the decorator:

```python
@golf_bp.route('/my-picks')
@login_required
@enrollment_required('golf')
def my_picks():
    ...
```

- [ ] **Step 5: Run the regression suite, verify both tests pass**

Run: `venv/bin/python -m pytest tests/test_golf_auto_enroll_removed.py -v`

- [ ] **Step 6: Full suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: no regressions.

- [ ] **Step 7: Pyright**

Run: `venv/bin/pyright games/golf/routes.py`

- [ ] **Step 8: Commit**

```bash
git add games/golf/routes.py tests/test_golf_auto_enroll_removed.py
git commit -m "refactor(golf): remove silent auto-enroll from submit-pick + my-picks

Unenrolled users hitting /golf/submit-pick/<id> or /golf/my-picks now
redirect to /golf/join?next=<url> via @enrollment_required('golf')
instead of being auto-enrolled. Resolves the primary bug driving this
spec.

Regression test locks in the new behavior."
```

---

### Task 11: Remove golf auto-enroll from admin routes

**Files:**
- Modify: `games/golf/routes.py` (two more auto-enroll sites)

- [ ] **Step 1: Remove auto-enroll from `admin_update_payment` (lines ~585-587)**

Replace:

```python
    enrollment = GolfEnrollment.query.filter_by(
        user_id=user_id, season_year=season_year
    ).first()
    if not enrollment:
        enrollment = GolfEnrollment(user_id=user_id, season_year=season_year)
        db.session.add(enrollment)
```

With:

```python
    enrollment = GolfEnrollment.query.filter_by(
        user_id=user_id, season_year=season_year
    ).first()
    if not enrollment:
        return jsonify({
            'success': False,
            'error': 'User is not enrolled in Golf Pick \'Em.',
        }), 400
```

- [ ] **Step 2: Remove auto-enroll from `admin_override_pick` (lines ~660-662)**

Replace:

```python
                # Ensure enrollment exists
                enrollment = GolfEnrollment.query.filter_by(
                    user_id=user_id, season_year=season_year
                ).first()
                if not enrollment:
                    enrollment = GolfEnrollment(user_id=user_id, season_year=season_year)
                    db.session.add(enrollment)
```

With:

```python
                # Enrollment must exist — use Platform Admin → Enrollments
                # to add a user to this league before overriding picks.
                enrollment = GolfEnrollment.query.filter_by(
                    user_id=user_id, season_year=season_year
                ).first()
                if not enrollment:
                    flash(
                        f'User must be enrolled in Golf Pick \'Em before an '
                        f'admin override can be applied. Add them via '
                        f'Admin → Enrollments first.',
                        'error',
                    )
                    db.session.rollback()
                    return redirect(url_for('golf.admin_override_pick'))
```

- [ ] **Step 3: Run full suite — check for any admin-path regressions**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: no regressions. (Existing admin payment tests, if any, may need updating — inspect test failures and adjust tests to reflect the new requirement.)

- [ ] **Step 4: Add a smoke test for the payment admin guard**

Append to `tests/test_golf_auto_enroll_removed.py`:

```python
def test_admin_update_payment_rejects_unenrolled_user(app, client, monkeypatch):
    _set_golf_open(monkeypatch)
    admin_id = _make_user(app, 'golfadmin', is_admin=True)
    target_id = _make_user(app, 'orphan')
    _login(client, admin_id)

    resp = client.post(f'/golf/admin/update-payment/{target_id}',
                       json={'has_paid': True})
    assert resp.status_code == 400
    with app.app_context():
        assert GolfEnrollment.query.filter_by(user_id=target_id).count() == 0
```

- [ ] **Step 5: Run — verify pass**

Run: `venv/bin/python -m pytest tests/test_golf_auto_enroll_removed.py -v`

- [ ] **Step 6: Pyright**

Run: `venv/bin/pyright games/golf/routes.py`

- [ ] **Step 7: Commit**

```bash
git add games/golf/routes.py tests/test_golf_auto_enroll_removed.py
git commit -m "refactor(golf): remove auto-enroll from admin payment/override paths

admin_update_payment returns 400 for unenrolled users; admin_override_pick
flashes an error pointing admins to the new Platform Admin → Enrollments
tool (added in Task 15). No silent GolfEnrollment creation anywhere."
```

---

### Task 12: Platform-wide `nav_games` context processor + navbar template loop

**Files:**
- Create: `core/context.py`
- Modify: `app.py`
- Modify: `templates/base.html`
- Create: `tests/test_homepage_sections.py` (initial nav tests)

- [ ] **Step 1: Create `tests/test_homepage_sections.py` with nav-focused tests**

```python
"""Tests for homepage sections + navbar game loop."""
import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment
from games.cfb.models import CfbEnrollment
from games.golf.models import GolfEnrollment


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


def _make_user(app, username='u1'):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com')
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


# ── nav_games context processor ──────────────────────────────────────────

def test_navbar_hides_all_games_for_anonymous(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'nav-link' in resp.data
    # None of the game labels should appear inside a top-nav <li>
    # (they may still appear in the hero card, but not the nav)
    # Heuristic: nav block between <ul class="navbar-nav me-auto"> and </ul>
    data = resp.data.decode()
    nav_start = data.find('navbar-nav me-auto')
    nav_end = data.find('</ul>', nav_start)
    nav_section = data[nav_start:nav_end]
    assert 'World Cup' not in nav_section
    assert 'CFB' not in nav_section
    assert 'Golf' not in nav_section


def test_navbar_hides_games_for_zero_joined_logged_in_user(app, client):
    uid = _make_user(app, 'nojoin')
    _login(client, uid)
    resp = client.get('/')
    data = resp.data.decode()
    nav_start = data.find('navbar-nav me-auto')
    nav_end = data.find('</ul>', nav_start)
    nav_section = data[nav_start:nav_end]
    assert 'World Cup' not in nav_section
    assert 'Golf' not in nav_section


def test_navbar_shows_only_joined_games(app, client):
    uid = _make_user(app, 'wconly')
    _login(client, uid)
    with app.app_context():
        db.session.add(WorldCupEnrollment(user_id=uid, season_year=2026))
        db.session.commit()
    resp = client.get('/')
    data = resp.data.decode()
    nav_start = data.find('navbar-nav me-auto')
    nav_end = data.find('</ul>', nav_start)
    nav_section = data[nav_start:nav_end]
    assert 'World Cup' in nav_section
    assert 'CFB' not in nav_section
    assert 'Golf' not in nav_section
```

- [ ] **Step 2: Run — expect failure (nav still hardcoded)**

Run: `venv/bin/python -m pytest tests/test_homepage_sections.py -v`
Expected: all three nav tests fail (nav currently always shows all three games).

- [ ] **Step 3: Create `core/context.py`**

```python
"""Platform-wide Jinja context processors."""
from flask_login import current_user

from games.registry import joined_games


def register_context_processors(app):
    """Attach platform-wide context processors to the Flask app."""

    @app.context_processor
    def inject_nav_games():
        try:
            games = joined_games(current_user)
        except Exception:
            # Anonymous / detached contexts — render empty nav rather than 500.
            games = []
        return {'nav_games': games}
```

- [ ] **Step 4: Register in `app.py`**

In `app.py`, after blueprint registration and before error handlers, add:

```python
    # Platform-wide context processors
    from core.context import register_context_processors
    register_context_processors(app)
```

- [ ] **Step 5: Replace the hardcoded nav block in `templates/base.html`**

Edit `templates/base.html`. Replace **lines 40-53** (the three hardcoded `<li class="nav-item">` entries for World Cup / Golf / CFB):

```jinja
                <ul class="navbar-nav me-auto">
                    {% for game in nav_games %}
                    <li class="nav-item">
                        <a class="nav-link {% if request.blueprint == game.slug %}active{% endif %}"
                           href="{{ url_for(game.blueprint_index) }}">{{ game.display_name }}</a>
                    </li>
                    {% endfor %}
                </ul>
```

- [ ] **Step 6: Run tests, verify pass**

Run: `venv/bin/python -m pytest tests/test_homepage_sections.py -v`
Expected: the three nav tests pass.

- [ ] **Step 7: Full suite regression + manual sub-nav check**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: no regressions. The game sub-nav (below the main nav) is controlled by `{% elif request.blueprint == '<game>' %}` blocks that already gate on blueprint name — they still work for enrolled users browsing their game.

- [ ] **Step 8: Pyright**

Run: `venv/bin/pyright core/context.py`

- [ ] **Step 9: Commit**

```bash
git add core/context.py app.py templates/base.html tests/test_homepage_sections.py
git commit -m "feat(nav): show only games the user has joined

Adds platform-wide nav_games context processor (joined_games(current_user))
and replaces three hardcoded <li> entries with a loop. Anonymous users
and zero-joined users see only brand + login/avatar."
```

---

### Task 13: Create `_game_card.html` partial

**Files:**
- Create: `core/main/templates/main/_game_card.html`

This partial is the rendering primitive the homepage uses for each game entry. Writing it first lets Task 14 be a pure integration step.

- [ ] **Step 1: Create `core/main/templates/main/_game_card.html`**

```jinja
{# _game_card.html
   Renders a single game card.

   Params:
     game   — GameRegistryEntry
     state  — 'featured' | 'joined' | 'available' | 'coming_soon' | 'logged_out'
#}

{% if state == 'featured' %}
  <a href="{{ url_for(game.blueprint_index) if state != 'coming_soon' else '#' }}"
     class="card game-card game-card--featured text-decoration-none">
    <div class="card-body p-0">
      <div class="featured-game-inner">
        <div class="featured-game-content">
          <span class="featured-badge">Live Now</span>
          <span class="featured-icon">{{ game.emoji }}</span>
          <h3 class="featured-title">{{ game.display_name }}</h3>
          <p class="featured-desc">{{ game.description }}</p>
          <span class="btn btn-warning btn-lg px-5 featured-cta">
            <i class="bi bi-globe2 me-2"></i>Enter the Pool
          </span>
        </div>
      </div>
    </div>
  </a>

{% elif state == 'joined' %}
  <a href="{{ url_for(game.blueprint_index) }}"
     class="card game-card game-card--live h-100 text-decoration-none">
    <div class="card-body text-center py-4 px-3">
      <span class="game-icon">{{ game.emoji }}</span>
      <h5 class="game-title">{{ game.display_name }}</h5>
      <p class="game-desc">{{ game.description }}</p>
      <span class="status-badge status-badge--joined">Joined ✓</span>
    </div>
    <div class="card-footer text-center bg-transparent py-3">
      <span class="btn btn-warning btn-sm px-4">Play Now</span>
    </div>
  </a>

{% elif state == 'available' %}
  <a href="{{ url_for(game.blueprint_join) }}"
     class="card game-card game-card--live h-100 text-decoration-none">
    <div class="card-body text-center py-4 px-3">
      <span class="game-icon">{{ game.emoji }}</span>
      <h5 class="game-title">{{ game.display_name }}</h5>
      <p class="game-desc">{{ game.description }}</p>
    </div>
    <div class="card-footer text-center bg-transparent py-3">
      <span class="btn btn-warning btn-sm px-4">Join the League</span>
    </div>
  </a>

{% elif state == 'coming_soon' %}
  <div class="card game-card game-card--coming-soon h-100">
    <div class="card-body text-center py-4 px-3">
      <span class="game-icon">{{ game.emoji }}</span>
      <h5 class="game-title">{{ game.display_name }}</h5>
      <p class="game-desc">{{ game.description }}</p>
    </div>
    <div class="card-footer text-center bg-transparent py-3">
      <span class="status-badge status-badge--muted">Coming Soon</span>
    </div>
  </div>

{% elif state == 'logged_out' %}
  <a href="{{ url_for('auth.register', next=url_for(game.blueprint_join)) }}"
     class="card game-card game-card--live h-100 text-decoration-none">
    <div class="card-body text-center py-4 px-3">
      <span class="game-icon">{{ game.emoji }}</span>
      <h5 class="game-title">{{ game.display_name }}</h5>
      <p class="game-desc">{{ game.description }}</p>
    </div>
    <div class="card-footer text-center bg-transparent py-3">
      <span class="btn btn-warning btn-sm px-4">Sign Up to Play</span>
    </div>
  </a>
{% endif %}
```

- [ ] **Step 2: Verify the partial renders in isolation via a smoke test**

Append to `tests/test_homepage_sections.py`:

```python
def test_game_card_partial_renders_each_state(app):
    """_game_card.html must render cleanly for every state value."""
    from games.registry import GAMES
    wc = next(g for g in GAMES if g.slug == 'worldcup')
    with app.test_request_context('/'):
        from flask import render_template
        for state in ('featured', 'joined', 'available', 'coming_soon', 'logged_out'):
            html = render_template('main/_game_card.html', game=wc, state=state)
            assert wc.display_name in html, f"state={state} missing name"
```

- [ ] **Step 3: Run — verify pass**

Run: `venv/bin/python -m pytest tests/test_homepage_sections.py::test_game_card_partial_renders_each_state -v`

- [ ] **Step 4: Commit**

```bash
git add core/main/templates/main/_game_card.html tests/test_homepage_sections.py
git commit -m "feat(homepage): add _game_card.html partial with 5 render states

Supports featured/joined/available/coming_soon/logged_out. Reuses existing
.game-card* CSS classes — no new styles required; a new .status-badge--joined
class is added to style.css in the homepage rewrite task."
```

---

### Task 14: Rewrite homepage to use registry + sections

**Files:**
- Modify: `core/main/routes.py`
- Modify: `core/main/templates/main/index.html`
- Modify: `static/css/style.css` (add `.status-badge--joined`)
- Update: `tests/test_homepage_sections.py`

- [ ] **Step 1: Write homepage integration tests**

Append to `tests/test_homepage_sections.py`:

```python
# ── Homepage sections ────────────────────────────────────────────────────

def test_homepage_logged_out_shows_available_and_coming_soon(client):
    resp = client.get('/')
    assert resp.status_code == 200
    data = resp.data.decode()
    assert '2026 FIFA World Cup' in data
    # CFB + Golf are coming_soon by default
    assert 'Coming Soon' in data


def test_homepage_zero_joined_shows_available_section(app, client):
    uid = _make_user(app, 'newuser')
    _login(client, uid)
    resp = client.get('/')
    data = resp.data.decode()
    assert 'Available to Join' in data
    assert '2026 FIFA World Cup' in data


def test_homepage_one_joined_shows_your_leagues_section(app, client):
    uid = _make_user(app, 'wcjoined')
    _login(client, uid)
    with app.app_context():
        db.session.add(WorldCupEnrollment(user_id=uid, season_year=2026))
        db.session.commit()
    resp = client.get('/')
    data = resp.data.decode()
    assert 'Your Leagues' in data
    assert '2026 FIFA World Cup' in data


def test_homepage_hides_empty_sections(app, client):
    """When a user has joined every available game, 'Available to Join' is absent."""
    uid = _make_user(app, 'alljoined')
    _login(client, uid)
    with app.app_context():
        db.session.add(WorldCupEnrollment(user_id=uid, season_year=2026))
        db.session.commit()
    resp = client.get('/')
    data = resp.data.decode()
    # World Cup is the only 'open' game; user has it → no 'Available to Join'
    assert 'Available to Join' not in data
    assert 'Your Leagues' in data
```

- [ ] **Step 2: Run — expect failures (current homepage hardcoded)**

Run: `venv/bin/python -m pytest tests/test_homepage_sections.py -v`

- [ ] **Step 3: Rewrite `core/main/routes.py`**

Replace the file contents:

```python
"""
Fantasy Sports Platform - Main Routes
=======================================
Home page and platform-level pages. Registry-driven.
"""
from flask import render_template
from flask_login import current_user

from core.main import main_bp
from games.registry import (
    joined_games, available_games, coming_soon_games, featured_games,
)


@main_bp.route('/')
def index():
    """Platform home page. Sections driven by games.registry."""
    if current_user.is_authenticated:
        user_joined = joined_games(current_user)
        user_available = available_games(current_user)
        return render_template(
            'main/index.html',
            mode='logged_in',
            joined=user_joined,
            available=user_available,
            coming_soon=coming_soon_games(),
            featured=featured_games(current_user),
        )

    return render_template(
        'main/index.html',
        mode='logged_out',
        joined=[],
        available=available_games(current_user),
        coming_soon=coming_soon_games(),
        featured=featured_games(current_user),
    )
```

- [ ] **Step 4: Rewrite `core/main/templates/main/index.html`**

```jinja
{% extends "base.html" %}

{% block title %}The Commissioner's Club{% endblock %}

{% block content %}
<!-- Hero -->
<div class="home-hero text-center">
  <div class="container position-relative" style="z-index:1;">
    <p class="hero-eyebrow">The Commissioner's Club</p>
    <h1>
      Your Fantasy Games,
      <span class="gold-line">All in One Place.</span>
    </h1>
    <p class="hero-body">
      Pick 'ems, survivor pools, tournament drafts — compete with your group across every sport.
    </p>

    {% if mode == 'logged_out' %}
    <div class="hero-actions d-flex gap-3 justify-content-center flex-wrap">
      <a href="{{ url_for('auth.register') }}" class="btn btn-warning btn-lg px-5">
        <i class="bi bi-trophy-fill me-1"></i> Join Now
      </a>
      <a href="{{ url_for('auth.login') }}" class="btn btn-outline-light btn-lg px-4">
        Sign In
      </a>
    </div>
    {% else %}
    <p class="hero-welcome">
      Welcome back, <strong class="text-gold">{{ current_user.get_display_name() }}</strong>
    </p>
    {% endif %}
  </div>
</div>

{# Featured hero card — only for open featured games the user has access to #}
{% if featured %}
<div class="container my-5">
  {% for game in featured %}
  <div class="animate-in">
    {% include 'main/_game_card.html' with context %}
    {% set _ = None %}
  </div>
  {% endfor %}
</div>
{% endif %}

<div class="container my-5">

{% if mode == 'logged_in' %}
  {% if joined %}
  <div class="text-center mt-5 mb-4 animate-in">
    <p class="section-heading">Your Leagues</p>
    <hr class="gold-rule">
  </div>
  <div class="row g-4 justify-content-center">
    {% for game in joined %}
      {# Skip featured — already rendered above as hero #}
      {% if not game.is_featured %}
      <div class="col-sm-6 col-md-5 animate-in stagger-{{ loop.index }}">
        {% with state='joined' %}{% include 'main/_game_card.html' %}{% endwith %}
      </div>
      {% endif %}
    {% endfor %}
  </div>
  {% endif %}

  {% if available %}
  <div class="text-center mt-5 mb-4 animate-in">
    <p class="section-heading">Available to Join</p>
    <hr class="gold-rule">
  </div>
  <div class="row g-4 justify-content-center">
    {% for game in available %}
      {% if not game.is_featured %}
      <div class="col-sm-6 col-md-5 animate-in stagger-{{ loop.index }}">
        {% with state='available' %}{% include 'main/_game_card.html' %}{% endwith %}
      </div>
      {% endif %}
    {% endfor %}
  </div>
  {% endif %}

{% else %}
  {# Logged-out view: non-featured open games as "sign up to play" cards #}
  {% set remaining = available | rejectattr('is_featured') | list %}
  {% if remaining %}
  <div class="text-center mt-5 mb-4 animate-in">
    <p class="section-heading">Play Now</p>
    <hr class="gold-rule">
  </div>
  <div class="row g-4 justify-content-center">
    {% for game in remaining %}
    <div class="col-sm-6 col-md-5 animate-in stagger-{{ loop.index }}">
      {% with state='logged_out' %}{% include 'main/_game_card.html' %}{% endwith %}
    </div>
    {% endfor %}
  </div>
  {% endif %}
{% endif %}

{% if coming_soon %}
<div class="text-center mt-5 mb-4 animate-in">
  <p class="section-heading">Coming Soon</p>
  <hr class="gold-rule">
</div>
<div class="row g-4 justify-content-center">
  {% for game in coming_soon %}
  <div class="col-sm-6 col-md-5 animate-in stagger-{{ loop.index }}">
    {% with state='coming_soon' %}{% include 'main/_game_card.html' %}{% endwith %}
  </div>
  {% endfor %}
</div>
{% endif %}

</div>
{% endblock %}
```

- [ ] **Step 5: Add `.status-badge--joined` to `static/css/style.css`**

Search for the existing `.status-badge--muted` rule (likely in the "STATUS BADGES" section) and add next to it:

```css
.status-badge--joined {
  background: rgba(184, 153, 62, 0.15);
  color: var(--gold);
  border: 1px solid rgba(184, 153, 62, 0.35);
  padding: 0.2rem 0.75rem;
  border-radius: 999px;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 600;
}
```

(Exact location: place it immediately after the `.status-badge--muted` declaration. If the variable names don't match, substitute the tokens used elsewhere in the file — Grep for `--gold` in style.css to confirm.)

- [ ] **Step 6: Invoke the frontend-design skill for visual polish**

Announce to the user: **"Invoking frontend-design skill to polish homepage card partials and join templates"**, then invoke `/frontend-design`. The skill should:
- Review `_game_card.html` for consistent visual hierarchy across states.
- Ensure palette matches: World Cup navy/red (featured hero), CFB crimson (join page), Golf Augusta green (join page), coming-soon dimmed.
- Confirm mobile card heights + hover states feel considered.

Manually verify the homepage as logged-out + logged-in + one-joined + all-joined users by starting the dev server:

```bash
FLASK_APP=app.py venv/bin/flask run
```

And visiting `/` in each of the four states.

- [ ] **Step 7: Run homepage tests + full suite**

Run: `venv/bin/python -m pytest tests/test_homepage_sections.py -v`
Run: `venv/bin/python -m pytest tests/ -v`
Expected: all pass.

- [ ] **Step 8: Pyright**

Run: `venv/bin/pyright core/main/routes.py`

- [ ] **Step 9: Commit**

```bash
git add core/main/routes.py core/main/templates/main/index.html \
        static/css/style.css tests/test_homepage_sections.py
git commit -m "feat(homepage): rewrite as Your Leagues / Available / Coming Soon

Registry-driven sections replace the hardcoded featured+others layout.
Sections only render when non-empty. Featured (WC) still gets hero-card
treatment via _game_card.html state='featured'. Adds .status-badge--joined
for 'Joined ✓' treatment on joined-league cards."
```

---

### Task 15: Admin add-user-to-league page

**Files:**
- Create: `core/admin/enrollments.py`
- Create: `core/admin/templates/admin/enrollments.html`
- Modify: `core/admin/__init__.py`
- Modify: `core/admin/templates/admin/dashboard.html` (add card)
- Create: `tests/test_admin_enrollments.py`

- [ ] **Step 1: Write failing admin enroll tests**

Create `tests/test_admin_enrollments.py`:

```python
"""Tests for the platform-admin add-user-to-league tool."""
import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment


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


def _make_user(app, username='u1', is_admin=False):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com', is_admin=is_admin)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def test_admin_enrollments_redirects_non_admin(app, client):
    uid = _make_user(app, 'regular')
    _login(client, uid)
    resp = client.get('/admin/enrollments', follow_redirects=False)
    assert resp.status_code == 302
    # admin_required redirects to main.index
    assert resp.location.endswith('/')


def test_admin_enrollments_renders_for_platform_admin(app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)
    resp = client.get('/admin/enrollments')
    assert resp.status_code == 200
    assert b'2026 FIFA World Cup' in resp.data


def test_admin_enrollments_dropdown_excludes_coming_soon_games(app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)
    resp = client.get('/admin/enrollments')
    data = resp.data.decode()
    # Only open games in the select options
    assert 'value="worldcup"' in data
    assert 'value="cfb"' not in data   # CFB is coming_soon
    assert 'value="golf"' not in data  # Golf is coming_soon


def test_admin_enrollments_post_enrolls_user(app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    target_id = _make_user(app, 'target')
    _login(client, aid)

    resp = client.post('/admin/enrollments', data={
        'user_id': target_id,
        'game_slug': 'worldcup',
        'csrf_token': 'x',
    }, follow_redirects=False)
    assert resp.status_code == 302

    with app.app_context():
        enr = WorldCupEnrollment.query.filter_by(user_id=target_id).first()
        assert enr is not None


def test_admin_enrollments_post_is_idempotent(app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    target_id = _make_user(app, 'target')
    _login(client, aid)

    with app.app_context():
        db.session.add(WorldCupEnrollment(user_id=target_id, season_year=2026))
        db.session.commit()

    resp = client.post('/admin/enrollments', data={
        'user_id': target_id,
        'game_slug': 'worldcup',
        'csrf_token': 'x',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'already enrolled' in resp.data

    with app.app_context():
        rows = WorldCupEnrollment.query.filter_by(user_id=target_id).count()
        assert rows == 1


def test_admin_enrollments_post_rejects_unknown_game(app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    target_id = _make_user(app, 'target')
    _login(client, aid)
    resp = client.post('/admin/enrollments', data={
        'user_id': target_id,
        'game_slug': 'does_not_exist',
        'csrf_token': 'x',
    }, follow_redirects=True)
    assert resp.status_code == 200
    # No enrollments created of any kind
    with app.app_context():
        assert WorldCupEnrollment.query.filter_by(user_id=target_id).count() == 0
```

- [ ] **Step 2: Run — expect failure (route 404)**

Run: `venv/bin/python -m pytest tests/test_admin_enrollments.py -v`

- [ ] **Step 3: Create `core/admin/enrollments.py`**

```python
"""Platform admin: add a user to a game's current-season enrollment."""
from flask import render_template, redirect, url_for, flash, request

from extensions import db
from models.user import User
from core.admin import admin_bp
from core.admin.routes import admin_required
from games.registry import GAMES, get_entry


@admin_bp.route('/enrollments', methods=['GET', 'POST'])
@admin_required
def enrollments():
    """List users + open games; on POST, call the selected game's admin_enroll."""
    open_entries = [e for e in GAMES if e.status == 'open']
    users = User.query.order_by(User.username).all()

    if request.method == 'POST':
        user_id = request.form.get('user_id', type=int)
        slug = (request.form.get('game_slug') or '').strip()

        if not user_id or not slug:
            flash('Both user and game are required.', 'error')
            return redirect(url_for('admin.enrollments'))

        try:
            entry = get_entry(slug)
        except KeyError:
            flash('Unknown game.', 'error')
            return redirect(url_for('admin.enrollments'))

        if entry.status != 'open':
            flash(f'{entry.display_name} is not accepting new enrollments.', 'error')
            return redirect(url_for('admin.enrollments'))

        user = db.session.get(User, user_id)
        if user is None:
            flash('User not found.', 'error')
            return redirect(url_for('admin.enrollments'))

        existing = entry.get_enrollment(user_id)
        if existing is not None:
            flash(
                f'{user.get_display_name()} is already enrolled in '
                f'{entry.display_name}.',
                'info',
            )
            return redirect(url_for('admin.enrollments'))

        entry.admin_enroll(user_id)
        flash(
            f'Enrolled {user.get_display_name()} in {entry.display_name}.',
            'success',
        )
        return redirect(url_for('admin.enrollments'))

    return render_template(
        'admin/enrollments.html',
        open_entries=open_entries,
        users=users,
    )
```

- [ ] **Step 4: Create template `core/admin/templates/admin/enrollments.html`**

```jinja
{% extends "base.html" %}
{% block title %}Enrollments — Admin{% endblock %}

{% block content %}
<div class="page-hero">
  <div class="hero-glow"></div>
  <div class="container">
    <h1><i class="bi bi-person-plus-fill me-2"></i>Manage Enrollments</h1>
    <p class="lead mb-0">Add a user to a live league.</p>
  </div>
</div>

<div class="container pb-5">
  <div class="row justify-content-center">
    <div class="col-lg-7 col-md-9">
      <div class="card border-0 shadow-sm animate-in">
        <div class="card-body p-4">

          {% if not open_entries %}
          <p class="text-muted mb-0">
            No games are currently open for enrollment.
          </p>
          {% else %}
          <form method="POST">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>

            <div class="mb-3">
              <label for="user_id" class="form-label">User</label>
              <select id="user_id" name="user_id" class="form-select" required>
                <option value="">— Select a user —</option>
                {% for u in users %}
                <option value="{{ u.id }}">{{ u.username }} — {{ u.email }}</option>
                {% endfor %}
              </select>
            </div>

            <div class="mb-4">
              <label for="game_slug" class="form-label">Game</label>
              <select id="game_slug" name="game_slug" class="form-select" required>
                <option value="">— Select a game —</option>
                {% for entry in open_entries %}
                <option value="{{ entry.slug }}">
                  {{ entry.emoji }} {{ entry.display_name }}
                </option>
                {% endfor %}
              </select>
              <div class="form-text">
                Only games with status='open' appear here. Flip the registry
                to add coming-soon games to this list.
              </div>
            </div>

            <button type="submit" class="btn btn-primary btn-lg w-100">
              <i class="bi bi-plus-lg me-1"></i>Add to League
            </button>
          </form>
          {% endif %}

        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Register the module in `core/admin/__init__.py`**

Open `core/admin/__init__.py`. At the bottom, add alongside the existing routes import:

```python
from core.admin import enrollments  # noqa: E402, F401
```

- [ ] **Step 6: Add a card to the admin dashboard**

Edit `core/admin/templates/admin/dashboard.html`. In the Management card grid (near lines 49-60), add a fourth card:

```jinja
        <div class="col-md-4 animate-in stagger-4">
            <div class="card h-100">
                <div class="card-body p-4">
                    <div style="font-size:1.8rem;margin-bottom:.5rem;">🎫</div>
                    <h5 class="card-title mb-1">Enrollments</h5>
                    <p class="text-muted small mb-3">Add a user to a live league.</p>
                    <a href="{{ url_for('admin.enrollments') }}" class="btn btn-primary btn-sm">
                        Manage Enrollments
                    </a>
                </div>
            </div>
        </div>
```

- [ ] **Step 7: Run admin tests, verify pass**

Run: `venv/bin/python -m pytest tests/test_admin_enrollments.py -v`

- [ ] **Step 8: Full suite + pyright**

Run: `venv/bin/python -m pytest tests/ -v`
Run: `venv/bin/pyright core/admin/enrollments.py`

- [ ] **Step 9: Commit**

```bash
git add core/admin/enrollments.py core/admin/templates/admin/enrollments.html \
        core/admin/__init__.py core/admin/templates/admin/dashboard.html \
        tests/test_admin_enrollments.py
git commit -m "feat(admin): add platform-wide 'Add user to league' page

/admin/enrollments — platform-admin-only. Dispatches on game slug and
calls entry.admin_enroll from the registry. Only games with status='open'
appear in the dropdown. Idempotent: already-enrolled users get a graceful
flash."
```

---

### Task 16: Wipe script for pre-launch CFB + Golf enrollments

**Files:**
- Create: `scripts/wipe_pre_launch_enrollments.py`

- [ ] **Step 1: Verify `scripts/` dir exists or create it**

Run: `ls /Users/bhagstrom/fantasy-platform/scripts/ 2>/dev/null || mkdir /Users/bhagstrom/fantasy-platform/scripts`

- [ ] **Step 2: Create `scripts/wipe_pre_launch_enrollments.py`**

```python
"""
Wipe pre-launch CFB + Golf enrollment data.

Usage (dry run):
    venv/bin/python scripts/wipe_pre_launch_enrollments.py

Apply:
    venv/bin/python scripts/wipe_pre_launch_enrollments.py --confirm

Behavior:
- Deletes ALL CfbEnrollment + dependent CfbPick rows.
- Deletes ALL GolfEnrollment + dependent GolfPick + GolfSeasonPlayerUsage rows.
- Leaves WorldCupEnrollment untouched (World Cup is live).
- Leaves User accounts untouched.
- Aborts loudly if any CfbGame, CfbWeek, or GolfTournament in the current
  season is marked complete — that would indicate real play happened,
  not test data.
"""
import argparse
import sys

from app import create_app
from extensions import db


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--confirm', action='store_true',
        help='Actually perform the deletes. Without this flag, dry-run only.',
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        from games.cfb.models import CfbEnrollment, CfbPick, CfbGame, CfbWeek
        from games.golf.models import (
            GolfEnrollment, GolfPick, GolfSeasonPlayerUsage, GolfTournament,
        )

        cfb_season = app.config.get('CFB_SEASON_YEAR', 2026)
        golf_season = app.config.get('SEASON_YEAR', 2026)

        # Safety: refuse to run if the current season has seen real play.
        cfb_complete_weeks = CfbWeek.query.filter_by(is_complete=True).count()
        cfb_complete_games = CfbGame.query.filter(
            CfbGame.home_team_won.isnot(None)
        ).count()
        golf_complete_tournaments = GolfTournament.query.filter_by(
            season_year=golf_season, status='complete',
        ).count()

        if cfb_complete_weeks or cfb_complete_games or golf_complete_tournaments:
            print('ABORT: Refusing to wipe — real play appears to have occurred:')
            print(f'  CFB completed weeks: {cfb_complete_weeks}')
            print(f'  CFB games with recorded outcome: {cfb_complete_games}')
            print(f'  Golf completed tournaments: {golf_complete_tournaments}')
            return 1

        cfb_pick_count = CfbPick.query.count()
        cfb_enr_count = CfbEnrollment.query.count()
        golf_pick_count = GolfPick.query.count()
        golf_usage_count = GolfSeasonPlayerUsage.query.count()
        golf_enr_count = GolfEnrollment.query.count()

        print(f'Planning to delete:')
        print(f'  CfbPick rows:               {cfb_pick_count}')
        print(f'  CfbEnrollment rows:         {cfb_enr_count}')
        print(f'  GolfPick rows:              {golf_pick_count}')
        print(f'  GolfSeasonPlayerUsage rows: {golf_usage_count}')
        print(f'  GolfEnrollment rows:        {golf_enr_count}')
        print(f'  (WorldCupEnrollment, Users untouched.)')

        if not args.confirm:
            print('\nDry run — pass --confirm to apply.')
            return 0

        try:
            CfbPick.query.delete(synchronize_session=False)
            CfbEnrollment.query.delete(synchronize_session=False)
            GolfPick.query.delete(synchronize_session=False)
            GolfSeasonPlayerUsage.query.delete(synchronize_session=False)
            GolfEnrollment.query.delete(synchronize_session=False)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            print(f'ERROR: rollback — {exc}')
            return 2

        print('\nDone.')
        return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 3: Smoke-test the dry-run path against an in-memory DB**

Run:

```bash
FLASK_APP=app.py ENVIRONMENT=testing venv/bin/python -c "
from app import create_app
app = create_app('testing')
with app.app_context():
    from extensions import db
    db.create_all()
print('create_all OK')
" && venv/bin/python scripts/wipe_pre_launch_enrollments.py
```

Expected: Planning output with zeros, `Dry run — pass --confirm to apply.`. Exit 0.

- [ ] **Step 4: Commit**

```bash
git add scripts/wipe_pre_launch_enrollments.py
git commit -m "chore(scripts): add one-shot wipe_pre_launch_enrollments.py

Dry-run by default; requires --confirm. Refuses to run if any CFB week
or golf tournament in the current season is marked complete. Intended
to be run once on the prod server post-deploy to reset Golf/CFB tables
to a clean pre-launch state before the new enrollment flow goes live."
```

---

### Task 17: Update the add-game skill with the enrollment contract

**Files:**
- Modify: `.claude/skills/add-game/SKILL.md`

- [ ] **Step 1: Append a new section to `.claude/skills/add-game/SKILL.md`**

After the existing Step 9, before the "Critical Conventions" section, insert a new Step 10 section and add the corresponding registry checklist to "Critical Conventions".

Add as Step 10:

```markdown
10. **Wire per-game enrollment into the platform:**
    - Create `games/<name>/services/enrollment.py` with two module-level callables:
      ```python
      def get_enrollment(user_id: int) -> Optional[<Name>Enrollment]:
          return <Name>Enrollment.query.filter_by(
              user_id=user_id, season_year=SEASON_YEAR
          ).first()

      def admin_enroll(user_id: int) -> <Name>Enrollment:
          existing = get_enrollment(user_id)
          if existing is not None:
              return existing
          enrollment = <Name>Enrollment(user_id=user_id, season_year=SEASON_YEAR)
          db.session.add(enrollment)
          db.session.commit()
          return enrollment
      ```
    - Add a `/<name>/join` route in `games/<name>/routes.py`:
      ```python
      from games.common import game_must_be_open, enrollment_required

      @<name>_bp.route('/join', methods=['GET', 'POST'])
      @login_required
      @game_must_be_open('<name>')
      def join():
          # render games/<name>/templates/<name>/join.html and POST to create enrollment
          ...
      ```
    - Create `games/<name>/templates/<name>/join.html` following the World Cup
      template shape (`page-hero` + How-It-Works card + form + `btn-game`).
    - Apply `@enrollment_required('<name>')` to every interior pick route
      (not to leaderboards/public standings).
    - Add one entry to `games/registry.py`:
      ```python
      from games.<name>.services import enrollment as _<name>_enrollment

      GameRegistryEntry(
          slug='<name>',
          display_name='...',
          description='...',
          emoji='...',
          status='coming_soon',  # flip to 'open' on launch
          is_featured=False,
          blueprint_index='<name>.index',
          blueprint_join='<name>.join',
          get_enrollment=_<name>_enrollment.get_enrollment,
          admin_enroll=_<name>_enrollment.admin_enroll,
      )
      ```
    - **Do not** auto-enroll on pick submission or admin actions. Platform
      admins enroll users via `/admin/enrollments` if needed.
```

Then append to "Critical Conventions":

```markdown
- Enrollment must be explicit: users reach a game's interior routes ONLY
  via `/<name>/join`. Never create `<Name>Enrollment` rows from pick or
  admin paths — that's a regression against the per-game enrollment
  design (spec: docs/superpowers/specs/2026-04-17-per-game-enrollment-design.md).
- Every game must expose `games/<name>/services/enrollment.py` with
  `get_enrollment` + `admin_enroll` to plug into the registry.
- A new game's default registry `status` is `'coming_soon'`. Flip to
  `'open'` only at launch.
```

- [ ] **Step 2: Read back the file to verify insertion**

Run: `venv/bin/python -c "p=open('.claude/skills/add-game/SKILL.md').read(); assert 'enrollment.py' in p and 'games/registry.py' in p, 'insertion missed'; print('ok')"`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/add-game/SKILL.md
git commit -m "docs(skill): add per-game enrollment checklist to add-game

Step 10 now documents the registry entry + /join + enrollment service
contract so future games plug in without rediscovering the pattern."
```

---

### Task 18: Full-suite verification + rebuild graphify

**Files:** none modified in this task — purely verification.

- [ ] **Step 1: Full pytest run**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: all tests pass. If any existing test was relying on golf auto-enroll, update it now (check for any test in `tests/` that creates a golf pick without an explicit enrollment).

- [ ] **Step 2: Full pyright run**

Run: `venv/bin/pyright`
Expected: 0 errors.

- [ ] **Step 3: Manual smoke test — start the server**

Run: `FLASK_APP=app.py venv/bin/flask run`

Verify:
- Visit `/` logged out → hero + "Play Now" card for World Cup + Coming Soon for CFB/Golf + no games in navbar.
- Register a new user → log in → `/` → "Available to Join" has World Cup, no "Your Leagues", Coming Soon has CFB/Golf, navbar empty.
- Join World Cup via the `/join` flow → back to `/` → "Your Leagues" shows WC with "Joined ✓", no "Available to Join", navbar shows World Cup only.
- As logged-in user, hit `/golf/my-picks` directly → redirects to `/golf/join?next=/golf/my-picks`.
- But Golf `/join` flashes "not open" and bounces to `/` because status is `coming_soon`. Temporarily flip `games/registry.py` Golf status to `'open'` to verify the full join flow, then revert.
- As platform admin, visit `/admin/enrollments` → form shows only World Cup in the game dropdown.
- Stop the server.

- [ ] **Step 4: Rebuild graphify knowledge graph**

Run: `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`

- [ ] **Step 5: Final commit (if graphify output changed)**

```bash
git add graphify-out/
git diff --cached --quiet || git commit -m "chore: rebuild graphify knowledge graph after per-game enrollment plan"
```

- [ ] **Step 6: Announce deploy ordering in the PR description**

When opening the PR, the description MUST include:

```markdown
## Deploy Ordering

1. Merge + deploy this branch.
2. On the prod server, run:
   ```
   python scripts/wipe_pre_launch_enrollments.py          # dry run — confirm counts
   python scripts/wipe_pre_launch_enrollments.py --confirm
   ```
3. Done.

The wipe script is gated on `--confirm` + a safety check that refuses to run
if any CFB week or Golf tournament in the current season is marked complete.
```

---

## Post-Merge (Out-of-Scope Operations)

These are executed by a human on the prod server after the PR merges:

1. `git pull` on PythonAnywhere.
2. `pip install -r requirements.txt` (no new deps expected — verify).
3. `flask db upgrade` (no migrations expected — this plan adds no schema changes; verify).
4. Run `python scripts/wipe_pre_launch_enrollments.py` (dry run — review counts).
5. Run `python scripts/wipe_pre_launch_enrollments.py --confirm`.
6. Reload web app from the PythonAnywhere Web tab.

---

## Self-Review

### Spec coverage

- ✅ Goal 1 (no cross-enrollment): each game has its own `/join` + decorator — Tasks 4, 6, 9.
- ✅ Goal 2 (explicit `/join` everywhere): Tasks 4, 6, 9 add/confirm all three.
- ✅ Goal 3 (homepage + nav per-user): Tasks 12–14.
- ✅ Goal 4 (`GAME_STATUS` as first-class concept): Task 1 (registry) + Task 2 (decorators read it).
- ✅ Goal 5 (add game N+1 = 1 registry entry + blueprint): Task 17 codifies the pattern.
- ✅ Non-goal "no user-initiated unenroll": never added.
- ✅ Non-goal "no BaseEnrollment model": each game keeps its own table; registry carries callables.
- ✅ Non-goal "admin UI doesn't flip status at runtime": registry is a module constant; no UI added.
- ✅ Key decision "admin enroll capability": Task 15.
- ✅ Key decision "hybrid nav/homepage UX": Tasks 12–14.
- ✅ Key decision "registry + per-game blueprint ownership": structure matches.
- ✅ Key decision "wipe on deploy": Task 16.
- ✅ Key decision "`/join` mid-flow UX is a redirect": `@enrollment_required` (Task 2) does `redirect(url_for(entry.blueprint_join, next=request.url))`.
- ✅ Key decision "featured retained": registry has `is_featured`; `_game_card.html` renders featured state.
- ✅ Per-game `/join` flow for WC/CFB/Golf: Tasks 4, 6, 9.
- ✅ Shared decorators: Task 2.
- ✅ Homepage rewrite: Tasks 13, 14.
- ✅ Navbar loop: Task 12.
- ✅ Admin add-user page: Task 15.
- ✅ Wipe script: Task 16.
- ✅ Future-game checklist: Task 17.
- ✅ Testing strategy: each task has tests covering its slice.

### Placeholder scan

- No TODO, TBD, "implement later", "fill in details".
- No "add validation" / "handle edge cases" in the abstract — each task names the specific behavior.
- No "similar to Task N" references without actual code.
- Every method/function referenced in a later task is defined in an earlier task. Cross-checked:
  - `get_enrollment` / `admin_enroll` — defined in Tasks 3, 5, 8 before being called in Tasks 4, 6, 9, 15.
  - `game_must_be_open` / `enrollment_required` — defined in Task 2, used from Task 4 onward.
  - Registry helpers `joined_games` / `available_games` / `coming_soon_games` / `featured_games` / `get_entry` — defined in Task 1, used from Task 12 onward.
  - `_game_card.html` — created in Task 13, used in Task 14.
  - `register_context_processors` — created in Task 12.

### Type consistency

- `GameRegistryEntry.get_enrollment: Callable[[int], Optional[object]]` — each service implementation returns `Optional[<Model>]`, which satisfies `Optional[object]`. ✅
- `GameRegistryEntry.admin_enroll: Callable[[int], object]` — each implementation returns the concrete model. ✅
- Decorator slug strings match registry entries exactly (`'worldcup'`, `'cfb'`, `'golf'`). ✅
- Blueprint endpoint strings (`'<slug>.index'`, `'<slug>.join'`) are consistent between registry and decorators. ✅
- Template parameter names (`state`, `game`) match between `_game_card.html` (Task 13) and the includes in `index.html` (Task 14). ✅

---

## Notes on Sequencing & Worktrees

- The original spec's Sequencing section lists 10 steps in rough dependency order. This plan refines those into 18 bite-sized tasks. The mapping:
  - Spec step 1 (registry + decorators) → Tasks 1, 2
  - Spec step 2 (WC enrollment + guard) → Tasks 3, 4
  - Spec step 3 (Golf `/join` + remove auto-enroll) → Tasks 8, 9, 10, 11
  - Spec step 4 (CFB `/join`) → Tasks 5, 6, 7
  - Spec step 5 (nav context processor) → Task 12
  - Spec step 6 (homepage rewrite + frontend-design pass) → Tasks 13, 14
  - Spec step 7 (admin add-user-to-league) → Task 15
  - Spec step 8 (wipe script) → Task 16
  - Spec step 9 (add-game skill update) → Task 17
  - Spec step 10 (tests) → interleaved per task; Task 18 is the final full-suite + graphify rebuild gate.

- This plan was written in the main worktree. If you're about to execute, consider creating an isolated worktree first via the `using-git-worktrees` skill — Tasks 10 and 11 touch behavior that blocks other game-admin work, so isolation is worth it.
