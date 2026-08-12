"""Docket /join flow locks (mirrors the CFB block in test_join_flows.py)."""
from extensions import db
from games.docket.models import DocketEnrollment
from games.docket.services.weeks import SEASON_YEAR
from tests._docket_fixtures import login, make_enrollment, make_user
from tests._registry_helpers import set_status


def test_docket_join_anonymous_redirects_to_login(client):
    resp = client.get('/docket/join', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.location


def test_docket_join_coming_soon_rejects_logged_in(app, client, monkeypatch):
    """@game_must_be_open bounces /docket/join home when not open (era
    pinned — the real status is 'open' from T7 onward)."""
    set_status(monkeypatch, 'docket', 'coming_soon')
    user = make_user('joiner')
    db.session.commit()
    login(client, user)
    resp = client.get('/docket/join', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.location.endswith('/')


def test_docket_join_open_renders_form(app, client):
    user = make_user('joiner')
    db.session.commit()
    login(client, user)
    resp = client.get('/docket/join')
    assert resp.status_code == 200
    assert b'Join The Docket' in resp.data
    assert b'display_name' in resp.data


def test_docket_join_post_creates_enrollment(app, client):
    user = make_user('joiner')
    db.session.commit()
    login(client, user)
    resp = client.post('/docket/join',
                       data={'display_name': '', 'csrf_token': 'x'},
                       follow_redirects=False)
    assert resp.status_code == 302
    enrollment = DocketEnrollment.query.filter_by(user_id=user.id).first()
    assert enrollment is not None
    assert enrollment.season_year == SEASON_YEAR
    assert enrollment.display_name is None


def test_docket_join_post_stores_display_name(app, client):
    user = make_user('joiner')
    db.session.commit()
    login(client, user)
    client.post('/docket/join',
                data={'display_name': '  The Gavel  ', 'csrf_token': 'x'})
    enrollment = DocketEnrollment.query.filter_by(user_id=user.id).first()
    assert enrollment.display_name == 'The Gavel'


def test_docket_join_duplicate_redirects_to_sheet(app, client):
    user = make_user('joiner')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    resp = client.get('/docket/join', follow_redirects=False)
    assert resp.status_code == 302
    assert '/docket' in resp.location
    assert DocketEnrollment.query.filter_by(user_id=user.id).count() == 1


def test_docket_sheet_redirects_non_enrolled_to_join(app, client):
    """An unenrolled logged-in user hitting the sheet is redirected to
    /docket/join?next=..., never silently auto-enrolled."""
    user = make_user('wanderer')
    db.session.commit()
    login(client, user)
    resp = client.get('/docket/', follow_redirects=False)
    assert resp.status_code == 302
    assert '/docket/join' in resp.location
    assert 'next=' in resp.location
    assert DocketEnrollment.query.count() == 0
