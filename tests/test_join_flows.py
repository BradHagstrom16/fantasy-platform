"""Tests for /join flows across all games."""
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
