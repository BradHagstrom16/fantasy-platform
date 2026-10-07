"""Golf admin-route guard matrix (Phase U6).

Widens the single-route checks in tests/test_golf_conformance.py to every
golf admin route, the way tests/test_cfb_admin_route_matrix.py does for
Survivor:

  - every admin route turns away an unauthenticated caller (-> login) and an
    enrolled non-admin (-> /golf/), the guard firing BEFORE any 404 on a bogus
    entity id;
  - POST-only routes reject GET with 405;
  - enrollment-admin is scoped to the configured season: a prior-season admin
    is rejected, the current-season admin passes;
  - the admin user lists are this season's enrollees, never every platform
    user (the dashboard, /admin/users and the override page's member select).

Admin routes are not behind @game_must_be_open, so no registry patch is
needed. Session identity is auth_id, never str(user.id).
"""
import pytest

from extensions import db
from games.golf.models import GolfEnrollment
from models.user import User


def _user(username, is_admin=False, display_name=None):
    u = User(username=username, email=f'{username}@test.com', is_admin=is_admin,
             display_name=display_name)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


def _enroll(user, season, is_admin=False):
    e = GolfEnrollment(user_id=user.id, season_year=season, is_admin=is_admin)
    db.session.add(e)
    db.session.commit()
    return e


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


GET_ROUTES = [
    '/golf/admin/',
    '/golf/admin/tournaments',
    '/golf/admin/users',
    '/golf/admin/payments',
    '/golf/admin/override-pick',
]

# Bogus ids on purpose: the guard must fire before the view can 404 on them.
POST_ROUTES = [
    '/golf/admin/update-payment/999',
    '/golf/admin/process-results/999',
    '/golf/admin/override-pick',
]

POST_ONLY_ROUTES = [
    '/golf/admin/update-payment/999',
    '/golf/admin/process-results/999',
]


@pytest.mark.parametrize('path', GET_ROUTES)
def test_admin_page_requires_login(app, client, path):
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


@pytest.mark.parametrize('path', POST_ROUTES)
def test_admin_post_requires_login(app, client, path):
    resp = client.post(path, data={'csrf_token': 'x'}, follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


@pytest.mark.parametrize('path', GET_ROUTES + POST_ROUTES)
def test_admin_route_rejects_enrolled_non_admin(app, client, path):
    """An enrolled non-admin is sent to the room (not /login, not a 404)."""
    user = _user('pleb')
    _enroll(user, app.config['SEASON_YEAR'])
    _login(client, user)

    method = client.post if path in POST_ROUTES else client.get
    resp = method(path, data={'csrf_token': 'x'}, follow_redirects=False)

    assert resp.status_code == 302
    location = resp.headers['Location']
    assert '/golf' in location
    assert '/login' not in location


@pytest.mark.parametrize('path', POST_ONLY_ROUTES)
def test_state_mutating_routes_reject_get(app, client, path):
    _login(client, _user('padmin', is_admin=True))
    assert client.get(path).status_code == 405


def test_current_season_enrollment_admin_allowed(app, client):
    user = _user('current_admin')
    _enroll(user, app.config['SEASON_YEAR'], is_admin=True)
    _login(client, user)
    assert client.get('/golf/admin/').status_code == 200


def test_prior_season_enrollment_admin_rejected(app, client):
    user = _user('prior_admin')
    _enroll(user, app.config['SEASON_YEAR'] - 1, is_admin=True)
    _login(client, user)
    resp = client.get('/golf/admin/')
    assert resp.status_code == 302
    assert '/golf' in resp.headers['Location']


def test_admin_lists_are_this_seasons_enrollees_only(app, client):
    """The roster, the override member select and the dashboard read this
    season's enrollees: a platform user with no line, or a line from another
    season, is not on them."""
    season = app.config['SEASON_YEAR']
    admin = _user('padmin', is_admin=True, display_name='The Commish')
    on_sheet = _user('on_sheet', display_name='Casey Onsheet')
    _enroll(on_sheet, season)
    last_year = _user('last_year', display_name='Dana Lastyear')
    _enroll(last_year, season - 1)
    _user('no_line', display_name='Morgan Noline')
    _login(client, admin)

    users_page = client.get('/golf/admin/users').get_data(as_text=True)
    assert 'Casey Onsheet' in users_page
    assert 'Dana Lastyear' not in users_page
    assert 'Morgan Noline' not in users_page

    override_page = client.get('/golf/admin/override-pick').get_data(as_text=True)
    assert 'Casey Onsheet' in override_page
    assert 'Dana Lastyear' not in override_page
    assert 'Morgan Noline' not in override_page

    dashboard = client.get('/golf/admin/').get_data(as_text=True)
    assert 'Morgan Noline' not in dashboard
