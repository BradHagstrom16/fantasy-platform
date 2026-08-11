"""CFB platform-conformance locks (pre-launch audit §7 + §8.20).

Covers the Top-5 #4 ruling (the game-admin password-reset route is
deleted — a delegated game admin could reset an enrolled platform
admin's password, a privilege-escalation path; the platform's
self-service forgot-password is the replacement) and the §8.20 route
conformance smoke: coming_soon gating, enrollment_required redirects,
and the two-tier admin decorator.

Session identity is auth_id, never str(user.id) — see CLAUDE.md.
"""
import dataclasses
from unittest.mock import patch

import pytest

import games.registry as registry
from app import create_app
from extensions import db
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)


@pytest.fixture()
def app():
    """App fixture: testing config + in-memory schema per test."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Flask test client bound to the app fixture."""
    return app.test_client()


def _login(client, user):
    """Seed the session with the user's auth_id (never str(user.id))."""
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


# ── Top-5 #4 — admin password-reset route is deleted ─────────────────────

def test_admin_reset_password_endpoint_does_not_exist(app):
    """The privilege-escalation route is gone from the URL map entirely."""
    assert 'cfb.admin_reset_password' not in app.view_functions


def test_admin_reset_password_post_404s_even_for_platform_admin(app, client):
    """POSTing the old URL is a 404 for everyone, platform admins included."""
    admin = make_user('padmin', is_admin=True)
    target = make_user('victim')
    make_enrollment(target)
    db.session.commit()
    _login(client, admin)

    resp = client.post(
        f'/cfb/admin/users/{target.id}/reset-password',
        data={'new_password': 'hijacked', 'csrf_token': 'x'},
    )

    assert resp.status_code == 404
    assert target.check_password('pw')  # password untouched


def test_admin_users_page_has_no_reset_password_form(app, client):
    """The admin users page no longer renders the reset-password modal."""
    admin = make_user('padmin', is_admin=True)
    enrolled = make_user('player1')
    make_enrollment(enrolled)
    db.session.commit()
    _login(client, admin)

    resp = client.get('/cfb/admin/users')

    assert resp.status_code == 200
    assert b'reset-password' not in resp.data
    assert b'Reset Password' not in resp.data


# ── §7 — avatar conformance (avatar precedes display name everywhere) ─────
# Emoji are written as \U escapes — literal non-BMP chars in .py source
# can break import as invalid surrogate pairs (CLAUDE.md).

UNICORN = '\U0001F984'
TREX = '\U0001F996'
FOX = '\U0001F98A'
GHOST = '\U0001F47B'


def test_index_eliminated_badges_show_avatar(app, client):
    """Eliminated Players badges carry the user's avatar."""
    for name in ('alive1', 'alive2'):
        u = make_user(name)
        make_enrollment(u)
    out = make_user('dino')
    out.avatar_emoji = TREX
    make_enrollment(out, lives=0, eliminated=True, display_name='Dino Dan')
    db.session.commit()

    resp = client.get('/cfb/')

    assert resp.status_code == 200
    assert 'Dino Dan' in resp.get_data(as_text=True)
    assert TREX in resp.get_data(as_text=True)


def test_champion_hero_and_fallen_badges_show_avatars(app, client):
    """The championship hero and Fallen Competitors badges carry avatars."""
    champ = make_user('champ')
    champ.avatar_emoji = UNICORN
    make_enrollment(champ, display_name='Champ Carl')
    fallen = make_user('fallen')
    fallen.avatar_emoji = TREX
    make_enrollment(fallen, lives=0, eliminated=True, display_name='Dino Dan')
    db.session.commit()

    resp = client.get('/cfb/')
    text = resp.get_data(as_text=True)

    assert 'CFB Survivor Pool Champion' in text  # championship page rendered
    assert UNICORN in text
    assert TREX in text


def test_weekly_results_table_shows_avatar_and_display_name_not_username(
        app, client):
    """The All-Picks table renders avatar + enrollment display name —
    never User.username (the one CFB surface that leaked usernames)."""
    week = make_week(1)
    home = make_team('Home1')
    away = make_team('Away1')
    make_game(week, home, away, spread=-7.0, winner='home')
    u = make_user('zzrawusername')
    u.avatar_emoji = FOX
    make_enrollment(u, display_name='Fancy Name')
    make_pick(u, week, home, is_correct=True)
    db.session.commit()

    resp = client.get('/cfb/results/1')
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'Fancy Name' in text
    assert FOX in text
    assert 'zzrawusername' not in text


def test_weekly_results_no_pick_row_shows_avatar(app, client):
    """No-pick rows in the All-Picks table carry the avatar too."""
    week = make_week(1)
    home = make_team('Home1')
    away = make_team('Away1')
    make_game(week, home, away, spread=-7.0, winner='home')
    picker = make_user('picker')
    make_enrollment(picker)
    make_pick(picker, week, home, is_correct=True)
    ghost = make_user('ghosty')
    ghost.avatar_emoji = GHOST
    make_enrollment(ghost, display_name='Ghosty')
    db.session.commit()

    resp = client.get('/cfb/results/1')
    text = resp.get_data(as_text=True)

    assert 'Ghosty' in text
    assert GHOST in text


# ── §8.20 — route conformance smoke ───────────────────────────────────────

def _open_cfb_games():
    """Registry list with CFB pinned to 'open' (entries are frozen)."""
    return [
        dataclasses.replace(e, status='open') if e.slug == 'cfb' else e
        for e in registry.GAMES
    ]


def _coming_soon_cfb_games():
    """Registry list with CFB pinned back to 'coming_soon' — the real status
    is 'open' since the 2026-08-11 changeover; the gating locks below pin the
    pre-launch era to keep testing @game_must_be_open's coming_soon branch."""
    return [
        dataclasses.replace(e, status='coming_soon') if e.slug == 'cfb' else e
        for e in registry.GAMES
    ]


def test_interior_routes_404_for_non_admin_while_coming_soon(app, client):
    """coming_soon hides interior routes from everyone but platform
    admins — even enrolled users."""
    user = make_user('player')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    with patch.object(registry, 'GAMES', _coming_soon_cfb_games()):
        assert client.get('/cfb/my-picks').status_code == 404
        assert client.get('/cfb/pick/1').status_code == 404


def test_interior_routes_bypass_for_platform_admin_while_coming_soon(
        app, client):
    """Platform admins bypass the coming_soon gate (never a 404)."""
    admin = make_user('padmin', is_admin=True)
    db.session.commit()
    _login(client, admin)

    with patch.object(registry, 'GAMES', _coming_soon_cfb_games()):
        assert client.get('/cfb/my-picks').status_code != 404


def test_anonymous_interior_route_redirects_to_login(app, client):
    """@login_required fires before any game gating."""
    resp = client.get('/cfb/my-picks')

    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_join_redirects_home_while_coming_soon(app, client):
    """@game_must_be_open bounces /cfb/join to the lounge pre-launch."""
    user = make_user('joiner')
    db.session.commit()
    _login(client, user)

    with patch.object(registry, 'GAMES', _coming_soon_cfb_games()):
        resp = client.get('/cfb/join')

    assert resp.status_code == 302
    assert resp.headers['Location'] in ('/', 'http://localhost/')


def test_enrollment_required_redirects_unenrolled_to_join_when_open(
        app, client):
    """Once open, unenrolled users are sent to /cfb/join?next=<url>."""
    user = make_user('wanderer')
    db.session.commit()
    _login(client, user)

    with patch.object(registry, 'GAMES', _open_cfb_games()):
        resp = client.get('/cfb/my-picks')

    assert resp.status_code == 302
    location = resp.headers['Location']
    assert '/cfb/join' in location
    assert 'next=' in location


def test_enrolled_user_passes_enrollment_gate_when_open(app, client):
    """Enrolled users reach interior routes once the game is open."""
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    with patch.object(registry, 'GAMES', _open_cfb_games()):
        resp = client.get('/cfb/my-picks')

    assert resp.status_code == 200


def test_admin_routes_reject_enrolled_non_admin(app, client):
    """Two-tier admin: a plain enrolled user is turned away."""
    user = make_user('pleb')
    make_enrollment(user)
    db.session.commit()
    _login(client, user)

    resp = client.get('/cfb/admin/')

    assert resp.status_code == 302
    assert '/cfb' in resp.headers['Location']


def test_admin_routes_allow_enrollment_admin(app, client):
    """Tier two: CfbEnrollment.is_admin grants game-admin access."""
    user = make_user('gameadmin')
    enrollment = make_enrollment(user)
    enrollment.is_admin = True
    db.session.commit()
    _login(client, user)

    assert client.get('/cfb/admin/').status_code == 200


def test_admin_routes_allow_platform_admin_without_enrollment(app, client):
    """Tier one: platform admin passes with no enrollment at all."""
    admin = make_user('padmin', is_admin=True)
    db.session.commit()
    _login(client, admin)

    assert client.get('/cfb/admin/').status_code == 200
