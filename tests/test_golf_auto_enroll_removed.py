"""Regression tests: golf pick routes must NOT silently auto-enroll users."""
import pytest
from datetime import datetime, timedelta, timezone

from app import create_app
from extensions import db
from models.user import User
from games.golf.models import GolfEnrollment, GolfTournament
from tests._registry_helpers import set_status as _set_status


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


def _seed_open_tournament(app):
    """Seed a GolfTournament with fields matching the actual model."""
    with app.app_context():
        now = datetime.now(timezone.utc)
        t = GolfTournament(
            api_tourn_id='TEST-1',
            name='Test Open',
            season_year=2026,
            start_date=now,
            end_date=now + timedelta(days=3),
            pick_deadline=now + timedelta(days=1),
            status='upcoming',
        )
        db.session.add(t)
        db.session.commit()
        return t.id


def test_make_pick_redirects_unenrolled_user_to_join(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    uid = _make_user(app, 'not_enrolled')
    tid = _seed_open_tournament(app)
    _login(client, uid)

    resp = client.get(f'/golf/pick/{tid}', follow_redirects=False)
    assert resp.status_code == 302
    assert '/golf/join' in resp.location


def test_make_pick_does_not_create_enrollment_when_user_not_joined(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    uid = _make_user(app, 'not_enrolled2')
    tid = _seed_open_tournament(app)
    _login(client, uid)

    client.get(f'/golf/pick/{tid}', follow_redirects=False)

    with app.app_context():
        assert GolfEnrollment.query.filter_by(user_id=uid).count() == 0


def test_admin_update_payment_rejects_unenrolled_user(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    admin_id = _make_user(app, 'golfadmin', is_admin=True)
    target_id = _make_user(app, 'orphan')
    _login(client, admin_id)

    resp = client.post(f'/golf/admin/update-payment/{target_id}',
                       json={'has_paid': True})
    assert resp.status_code == 400
    with app.app_context():
        assert GolfEnrollment.query.filter_by(user_id=target_id).count() == 0
