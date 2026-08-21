"""Tests for homepage sections + navbar game loop."""

from extensions import db
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment
from models.user import User


def _make_user(app, username='u1'):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com')
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


# ── nav_games context processor ──────────────────────────────────────────

def test_navbar_hides_all_games_for_anonymous(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'nav-link' in resp.data
    # None of the game labels should appear inside a top-nav <li>
    # (they may still appear in the hero card, but not the nav)
    # Heuristic: nav block between <ul class="navbar-nav me-auto"> and </ul>
    data = resp.data.decode()
    nav_start = data.find('navbar-nav me-auto')
    nav_end = data.find('</ul>', nav_start)
    nav_section = data[nav_start:nav_end]
    assert 'World Cup' not in nav_section
    assert 'Survivor' not in nav_section
    assert 'Golf' not in nav_section


def test_navbar_hides_games_for_zero_joined_logged_in_user(app, client):
    uid = _make_user(app, 'nojoin')
    _login(client, uid)
    resp = client.get('/')
    data = resp.data.decode()
    nav_start = data.find('navbar-nav me-auto')
    nav_end = data.find('</ul>', nav_start)
    nav_section = data[nav_start:nav_end]
    assert 'World Cup' not in nav_section
    assert 'Golf' not in nav_section


def test_navbar_shows_only_joined_active_games(app, client):
    """The switcher carries ACTIVE joined games only; a completed game
    (WC) lives in the account dropdown's Archive section instead (design
    review 2026-08-18 — full gating matrix in test_navbar_solo_game)."""
    uid = _make_user(app, 'wconly')
    _login(client, uid)
    with app.app_context():
        db.session.add(WorldCupEnrollment(user_id=uid, season_year=SEASON_YEAR))
        db.session.commit()
    resp = client.get('/')
    data = resp.data.decode()
    nav_start = data.find('navbar-nav me-auto')
    nav_end = data.find('</ul>', nav_start)
    nav_section = data[nav_start:nav_end]
    assert 'World Cup' not in nav_section
    assert 'Survivor' not in nav_section
    assert 'Golf' not in nav_section
    dd_start = data.find('dropdown-menu')
    dd_section = data[dd_start:data.find('</ul>', dd_start)]
    assert 'The Archive' in dd_section
    assert 'World Cup' in dd_section


def test_game_card_partial_renders_each_state(app):
    """_game_card.html must render cleanly for every state value."""
    from games.registry import GAMES
    wc = next(g for g in GAMES if g.slug == 'worldcup')
    with app.test_request_context('/'):
        from flask import render_template
        for state in ('featured', 'joined', 'available', 'coming_soon', 'logged_out'):
            html = render_template('main/_game_card.html', game=wc, state=state)
            assert wc.display_name in html, f"state={state} missing name"


# ── Homepage section tests removed ──────────────────────────────────────
# Five homepage-section tests previously lived here, asserting the old
# registry-driven home page (Your Leagues / Available to Join / Coming Soon
# section headers, "Enter the Pool" CTA, "Joined ✓" badge). The Spec B home
# redesign replaces that surface with state-aware partials whose assertions
# live in tests/test_home_context.py. The navbar + game-card-partial tests
# above remain unchanged because those components still exist.
