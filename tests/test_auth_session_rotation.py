"""A password change or reset signs out every other session (ops hardening §G).

Session and remember cookies both carry User.auth_id (tests/
test_auth_session_identity.py), so rotating it on a password change is what
locks out a stolen session: before this, a reset left every other device
signed in, including a remember cookie good for 365 days.

Also here: logout is POST-only (no page can sign a member out with an
<img src="/logout">), and production refuses a blank or the public development
SECRET_KEY.
"""
import pytest

from app import create_app, refuse_default_secret_key
from config import DEV_SECRET_KEY, ProductionConfig
from core.auth.tokens import generate_reset_token
from extensions import db
from models.user import User


def _make_user(username='alice', password='oldpass1', is_admin=False):
    user = User(username=username, email=f'{username}@example.com',
                is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user.id


def _send(client, method, url, **kwargs):
    """One request in its own app context. The fixture's context is shared by
    every request otherwise, and Flask-Login caches the loaded user on its
    `g`, so a second client would see the first client's member."""
    with client.application.app_context():
        return client.open(url, method=method, **kwargs)


def _log_in(client, username='alice', password='oldpass1'):
    resp = _send(client, 'POST', '/login',
                 data={'username': username, 'password': password})
    assert resp.status_code == 302


def _signed_in(client):
    """True when this client's cookies still resolve to a member."""
    return _send(client, 'GET', '/change-password').status_code == 200


def _auth_id(user_id):
    db.session.expire_all()
    return db.session.get(User, user_id).auth_id


# ---- password change / reset rotate auth_id -------------------------------

def test_change_password_keeps_this_session_and_signs_out_the_others(app):
    uid = _make_user()
    phone, laptop = app.test_client(), app.test_client()
    _log_in(phone)
    _log_in(laptop)
    before = _auth_id(uid)

    resp = _send(phone, 'POST', '/change-password', data={
        'current_password': 'oldpass1', 'new_password': 'newpass1',
        'confirm_password': 'newpass1'})
    assert resp.status_code == 302

    assert _auth_id(uid) != before
    assert _signed_in(phone)
    assert not _signed_in(laptop)


def test_change_password_reissues_the_remember_cookie(app):
    """The changer's remember cookie must carry the new auth_id, or their
    session would drop the next time the browser session ends."""
    uid = _make_user()
    client = app.test_client()
    _log_in(client)

    _send(client, 'POST', '/change-password', data={
        'current_password': 'oldpass1', 'new_password': 'newpass1',
        'confirm_password': 'newpass1'})

    cookie = client.get_cookie('remember_token')
    assert cookie is not None
    assert cookie.value.split('|')[0] == _auth_id(uid)


def test_a_stale_remember_cookie_no_longer_loads_the_member(app):
    uid = _make_user()
    old_auth_id = _auth_id(uid)
    user = db.session.get(User, uid)
    user.rotate_auth_id()
    db.session.commit()

    assert app.login_manager._user_callback(old_auth_id) is None
    assert app.login_manager._user_callback(user.auth_id).id == uid


def test_a_failed_change_rotates_nothing(app):
    uid = _make_user()
    client = app.test_client()
    _log_in(client)
    before = _auth_id(uid)

    _send(client, 'POST', '/change-password', data={
        'current_password': 'wrong', 'new_password': 'newpass1',
        'confirm_password': 'newpass1'})

    assert _auth_id(uid) == before
    assert _signed_in(client)


def test_reset_password_signs_out_every_session(app):
    uid = _make_user()
    laptop = app.test_client()
    _log_in(laptop)
    before = _auth_id(uid)
    token = generate_reset_token('alice@example.com')

    resp = _send(app.test_client(), 'POST', f'/reset-password/{token}', data={
        'new_password': 'newpass1', 'confirm_password': 'newpass1'})
    assert resp.status_code == 302

    assert _auth_id(uid) != before
    assert not _signed_in(laptop)


def test_admin_reset_signs_out_every_session(app):
    admin_id = _make_user('commish', is_admin=True)
    uid = _make_user('bob')
    member = app.test_client()
    _log_in(member, 'bob')
    before = _auth_id(uid)

    admin = app.test_client()
    with admin.session_transaction() as sess:
        sess['_user_id'] = _auth_id(admin_id)
        sess['_fresh'] = True
    resp = _send(admin, 'POST', f'/admin/users/{uid}/reset-password')
    assert resp.status_code == 302

    assert _auth_id(uid) != before
    assert not _signed_in(member)


def test_production_remember_cookie_flags():
    assert ProductionConfig.REMEMBER_COOKIE_SECURE is True
    assert ProductionConfig.REMEMBER_COOKIE_HTTPONLY is True
    assert ProductionConfig.REMEMBER_COOKIE_SAMESITE == 'Lax'


# ---- logout is POST-only ---------------------------------------------------

def test_get_logout_is_refused_and_signs_nobody_out(app):
    _make_user()
    client = app.test_client()
    _log_in(client)

    assert _send(client, 'GET', '/logout').status_code == 405
    assert _signed_in(client)


def test_post_logout_signs_out(app):
    _make_user()
    client = app.test_client()
    _log_in(client)

    resp = _send(client, 'POST', '/logout')
    assert resp.status_code == 302
    assert not _signed_in(client)


def test_navbar_logs_out_with_a_form_not_a_link(app):
    _make_user()
    client = app.test_client()
    _log_in(client)

    html = _send(client, 'GET', '/').get_data(as_text=True)
    assert '<form class="js-logout" method="post" action="/logout">' in html
    assert 'name="csrf_token"' in html
    assert 'href="/logout"' not in html


# ---- production refuses the default SECRET_KEY -----------------------------

@pytest.mark.parametrize('key', ['', '   ', DEV_SECRET_KEY])
def test_production_refuses_a_blank_or_default_secret_key(key):
    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        refuse_default_secret_key('production', key)


def test_production_accepts_a_real_secret_key():
    refuse_default_secret_key('production', 'a' * 64)


@pytest.mark.parametrize('config_name', ['development', 'testing'])
def test_other_environments_may_use_the_default(config_name):
    refuse_default_secret_key(config_name, DEV_SECRET_KEY)


def test_create_app_refuses_before_touching_anything(monkeypatch):
    monkeypatch.setattr(ProductionConfig, 'SECRET_KEY', DEV_SECRET_KEY)
    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        create_app('production')
