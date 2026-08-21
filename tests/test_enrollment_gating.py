"""Tests for games.common decorators."""
from flask import Blueprint

from extensions import db
from games.registry import GameRegistryEntry
from models.user import User


def _make_user(app, username='u1', is_admin=False):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com', is_admin=is_admin)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(client, user_id):
    from models.user import User
    auth_id = db.session.get(User, user_id).auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
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
