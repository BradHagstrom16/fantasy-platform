"""Tests for homepage sections + navbar game loop."""
import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment
from games.worldcup.constants import SEASON_YEAR


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
    assert 'CFB' not in nav_section
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


def test_navbar_shows_only_joined_games(app, client):
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
    assert 'World Cup' in nav_section
    assert 'CFB' not in nav_section
    assert 'Golf' not in nav_section


def test_game_card_partial_renders_each_state(app):
    """_game_card.html must render cleanly for every state value."""
    from games.registry import GAMES
    wc = next(g for g in GAMES if g.slug == 'worldcup')
    with app.test_request_context('/'):
        from flask import render_template
        for state in ('featured', 'joined', 'available', 'coming_soon', 'logged_out'):
            html = render_template('main/_game_card.html', game=wc, state=state)
            assert wc.display_name in html, f"state={state} missing name"
