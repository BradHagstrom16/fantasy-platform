"""Tests for the platform-admin add-user-to-league tool."""
import pytest

from app import create_app
from extensions import db
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment
from models.user import User


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
    from models.user import User
    auth_id = db.session.get(User, user_id).auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


def test_admin_enrollments_redirects_non_admin(app, client):
    uid = _make_user(app, 'regular')
    _login(client, uid)
    resp = client.get('/admin/enrollments', follow_redirects=False)
    assert resp.status_code == 302
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
    assert 'value="worldcup"' in data
    assert 'value="cfb"' not in data
    assert 'value="golf"' not in data


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
        db.session.add(WorldCupEnrollment(user_id=target_id, season_year=SEASON_YEAR))
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
    with app.app_context():
        assert WorldCupEnrollment.query.filter_by(user_id=target_id).count() == 0
