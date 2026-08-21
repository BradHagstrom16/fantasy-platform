"""CFB admin-route guard matrix (pre-launch audit §7 — test hardening).

test_cfb_conformance.py locks the two-tier @cfb_admin_required on a single
route (/admin/). This widens that to the FULL set of state-mutating admin
routes and adds three guarantees the single-route test can't:

  - every mutating route turns away an unauthenticated caller (→ login) and
    an enrolled non-admin (→ /cfb), with the guard firing BEFORE any 404 on a
    missing entity id (we POST to non-existent week/user ids and still get the
    guard redirect, not a 404);
  - POST-only routes reject GET with 405 (no state-changing GET slips in);
  - enrollment-admin is scoped to the active season — a prior-season admin is
    rejected, the active-season admin passes.

Admin routes are NOT behind @game_must_be_open, so no registry patch is
needed. Session identity is auth_id, never str(user.id).
"""
import pytest

from extensions import db
from tests._cfb_fixtures import make_enrollment, make_user


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _login_admin(client):
    admin = make_user('padmin', is_admin=True)
    db.session.commit()
    _login(client, admin)
    return admin


# Bogus ids on purpose: the guard must fire before the view can 404 on them.
MUTATING_ROUTES = [
    '/cfb/admin/week/new',
    '/cfb/admin/week/999/activate',
    '/cfb/admin/week/999/complete',
    '/cfb/admin/week/999/games',
    '/cfb/admin/week/999/games/888/delete',
    '/cfb/admin/week/999/mark-results',
    '/cfb/admin/week/999/apply-scores',
    '/cfb/admin/process-autopicks/999',
    '/cfb/admin/users/999/toggle-admin',
    '/cfb/admin/update-payment/999',
    '/cfb/admin/manage-teams',
]

# The subset declared POST-only (no GET method) — a GET must 405.
POST_ONLY_ROUTES = [
    '/cfb/admin/week/999/activate',
    '/cfb/admin/week/999/complete',
    '/cfb/admin/week/999/games/888/delete',
    '/cfb/admin/week/999/apply-scores',
    '/cfb/admin/process-autopicks/999',
    '/cfb/admin/users/999/toggle-admin',
    '/cfb/admin/update-payment/999',
]


# ── unauthenticated + non-admin are turned away from every mutating route ──

@pytest.mark.parametrize('path', MUTATING_ROUTES)
def test_mutating_admin_route_requires_login(app, client, path):
    """An unauthenticated POST is bounced to login — never executes."""
    resp = client.post(path, data={'csrf_token': 'x'}, follow_redirects=False)

    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


@pytest.mark.parametrize('path', MUTATING_ROUTES)
def test_mutating_admin_route_rejects_enrolled_non_admin(app, client, path):
    """An enrolled non-admin is redirected to /cfb (not /login, not a 404):
    the two-tier guard fires before the view sees the bogus entity id."""
    user = make_user('pleb')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    resp = client.post(path, data={'csrf_token': 'x'}, follow_redirects=False)

    assert resp.status_code == 302
    location = resp.headers['Location']
    assert '/cfb' in location
    assert '/login' not in location


# ── POST-only routes reject GET ───────────────────────────────────────────

@pytest.mark.parametrize('path', POST_ONLY_ROUTES)
def test_state_mutating_routes_reject_get(app, client, path):
    """A GET on a POST-only route is 405 even for a platform admin — the
    method gate is the only thing that can block them here."""
    _login_admin(client)

    resp = client.get(path)

    assert resp.status_code == 405


# ── enrollment-admin is scoped to the active season ───────────────────────

def test_active_season_enrollment_admin_allowed(app, client):
    """An enrollment admin for the active season reaches the admin dashboard."""
    season = app.config['CFB_SEASON_YEAR']
    user = make_user('current_admin')
    make_enrollment(user, season=season).is_admin = True
    db.session.commit()
    _login(client, user)

    assert client.get('/cfb/admin/').status_code == 200


def test_prior_season_enrollment_admin_rejected(app, client):
    """An enrollment admin for a PRIOR season is rejected — the decorator
    filters CfbEnrollment by CFB_SEASON_YEAR, so a stale admin can't carry
    over once the active season rolls forward."""
    season = app.config['CFB_SEASON_YEAR']
    user = make_user('prior_admin')
    make_enrollment(user, season=season - 1).is_admin = True
    db.session.commit()
    _login(client, user)

    resp = client.get('/cfb/admin/')

    assert resp.status_code == 302
    assert '/cfb' in resp.headers['Location']
