"""Docket platform-conformance locks (mirrors tests/test_cfb_conformance.py
§8.20: coming_soon gating, enrollment_required redirects, the two-tier
admin decorator, and POST-only mutation routes)."""
import dataclasses
from unittest.mock import patch

import games.registry as registry
from extensions import db
from tests._docket_fixtures import (
    login,
    make_enrollment,
    make_user,
    make_week,
)


def _coming_soon_docket_games():
    """Registry list with docket pinned to 'coming_soon' (the real status
    is 'open'; these locks keep @game_must_be_open's gate tested)."""
    return [
        dataclasses.replace(e, status='coming_soon') if e.slug == 'docket'
        else e
        for e in registry.GAMES
    ]


def test_interior_routes_404_for_non_admin_while_coming_soon(app, client):
    user = make_user('player')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    with patch.object(registry, 'GAMES', _coming_soon_docket_games()):
        assert client.get('/docket/').status_code == 404


def test_interior_routes_bypass_for_platform_admin_while_coming_soon(
        app, client):
    admin = make_user('padmin', is_admin=True)
    db.session.commit()
    login(client, admin)
    with patch.object(registry, 'GAMES', _coming_soon_docket_games()):
        assert client.get('/docket/').status_code != 404


# Every member-facing GET surface, gated identically. A new page belongs
# here (All Sheets joined 2026-09-04).
MEMBER_PATHS = ('/docket/', '/docket/ledger', '/docket/sheets')


def test_anonymous_interior_route_redirects_to_login(app, client):
    for path in MEMBER_PATHS:
        resp = client.get(path)
        assert resp.status_code == 302, path
        assert '/login' in resp.headers['Location'], path


def test_join_redirects_home_while_coming_soon(app, client):
    user = make_user('joiner')
    db.session.commit()
    login(client, user)
    with patch.object(registry, 'GAMES', _coming_soon_docket_games()):
        resp = client.get('/docket/join')
    assert resp.status_code == 302
    assert resp.headers['Location'] in ('/', 'http://localhost/')


def test_enrollment_required_redirects_unenrolled_to_join_when_open(
        app, client):
    user = make_user('wanderer')
    db.session.commit()
    login(client, user)
    for path in MEMBER_PATHS:
        resp = client.get(path)
        assert resp.status_code == 302, path
        location = resp.headers['Location']
        assert '/docket/join' in location, path
        assert 'next=' in location, path


def test_enrolled_user_passes_enrollment_gate(app, client):
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    for path in MEMBER_PATHS:
        assert client.get(path).status_code == 200, path


def test_mutation_routes_are_post_only(app, client):
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    for path in ('/docket/picks/set', '/docket/picks/remove',
                 '/docket/best', '/docket/tiebreaker'):
        assert client.get(path).status_code == 405


def test_read_only_routes_reject_post(app, client):
    """The inverse matrix: a page that only reads never takes a POST."""
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    for path in ('/docket/sheets', '/docket/ledger', '/docket/rules'):
        assert client.post(path, data={'csrf_token': 'x'}).status_code == 405, path


def test_mutation_route_redirects_unenrolled_to_join(app, client):
    user = make_user('wanderer')
    db.session.commit()
    login(client, user)
    resp = client.post('/docket/picks/set', data={'csrf_token': 'x'})
    assert resp.status_code == 302
    assert '/docket/join' in resp.headers['Location']


# Every admin surface, gated identically. A new screen belongs here.
ADMIN_PATHS = (
    '/docket/admin/',
    '/docket/admin/week/1/tiebreaker',
    '/docket/admin/week/1/rulings',
    '/docket/admin/week/1/lines',
    '/docket/admin/payments',
)

# Every admin POST endpoint. A new mutation belongs here (GET-only screens
# like the dashboard and payments 405 a POST before the gate runs, so they
# can't share the matrix above).
ADMIN_MUTATION_PATHS = (
    '/docket/admin/week/1/tiebreaker',
    '/docket/admin/week/1/rulings',
    '/docket/admin/week/1/lines',
    '/docket/admin/update-payment/1',
)


def test_admin_routes_reject_enrolled_non_admin(app, client):
    user = make_user('pleb')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    for path in ADMIN_PATHS:
        resp = client.get(path)
        assert resp.status_code == 302, path
        # Not just "/docket": every admin path starts with /docket/admin/,
        # so a loose check would pass if the gate bounced an unauthorized
        # user onto another admin screen, which is what this test exists
        # to catch.
        assert '/docket/admin' not in resp.headers['Location'], path
        assert '/docket' in resp.headers['Location'], path


def test_admin_routes_reject_anonymous(app, client):
    for path in ADMIN_PATHS:
        resp = client.get(path)
        assert resp.status_code == 302, path
        assert '/login' in resp.headers['Location']


def test_admin_routes_allow_enrollment_admin(app, client):
    user = make_user('gameadmin')
    enrollment = make_enrollment(user)
    enrollment.is_admin = True
    make_week(1)
    db.session.commit()
    login(client, user)
    for path in ADMIN_PATHS:
        assert client.get(path).status_code == 200, path


def test_admin_routes_allow_platform_admin_without_enrollment(app, client):
    admin = make_user('padmin', is_admin=True)
    make_week(1)
    db.session.commit()
    login(client, admin)
    for path in ADMIN_PATHS:
        assert client.get(path).status_code == 200, path


def test_admin_mutations_reject_an_enrolled_non_admin(app, client):
    """The gate is on the POST too, not just the page that shows the form."""
    user = make_user('pleb2')
    make_enrollment(user)
    make_week(1)
    db.session.commit()
    login(client, user)
    for path in ADMIN_MUTATION_PATHS:
        resp = client.post(path, data={'csrf_token': 'x'})
        assert resp.status_code == 302, path
        assert '/docket/admin' not in resp.headers['Location']
