"""Navbar solo-game hoist + full mobile lockup (mobile top-bar redesign).

While a user's enrolled-game count == 1, the game switcher hoists out of the
hamburger into the visible bar (`.navbar-solo-game`, below-lg only) and the
collapse copy hides below lg (`d-none d-lg-block`) so the link appears exactly
once per breakpoint. The brand wordmark renders at all widths (the CSS
≤350px fallback hides it; the template no longer gates it at `d-md-inline`).
"""
import pytest

from app import create_app
from extensions import db

from tests._worldcup_fixtures import make_user, make_enrollment


@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, user):
    # Session identity is auth_id, NOT str(user.id) — see CLAUDE.md invariant.
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _enrolled_user(email='solo@test'):
    u = make_user(email=email, display_name='Solo')
    make_enrollment(u, picks_submitted=True)
    db.session.commit()
    return u


def test_solo_game_link_hoisted_into_bar(app, client):
    """Exactly one enrolled game ⇒ in-bar link, hidden at lg+ (desktop nav owns it)."""
    u = _enrolled_user()
    _login(client, u)
    html = client.get('/').get_data(as_text=True)
    assert 'navbar-solo-game' in html
    solo = _tag_containing(html, 'navbar-solo-game')
    assert 'd-lg-none' in solo
    assert '/worldcup' in solo
    assert 'World Cup' in html


def test_solo_game_collapse_copy_hidden_below_lg(app, client):
    """The hamburger copy of the solo game hides below lg — no duplicate link."""
    u = _enrolled_user()
    _login(client, u)
    html = client.get('/').get_data(as_text=True)
    li = _tag_containing(html, 'nav-item', tag='li')
    assert 'd-none' in li and 'd-lg-block' in li


def test_anonymous_gets_no_solo_game_link(app, client):
    html = client.get('/').get_data(as_text=True)
    assert 'navbar-solo-game' not in html


def test_two_enrollments_fall_back_to_dropdown(app, client):
    """2+ joined games ⇒ no hoist; both collapse items render unhidden."""
    u = _enrolled_user()
    from games.cfb.services.enrollment import admin_enroll as cfb_enroll
    cfb_enroll(u.id)
    _login(client, u)
    html = client.get('/').get_data(as_text=True)
    assert 'navbar-solo-game' not in html
    li = _tag_containing(html, 'nav-item', tag='li')
    assert 'd-none' not in li


def test_brand_wordmark_renders_at_all_widths(app, client):
    """The wordmark img is no longer gated `d-none d-md-inline` — the full
    lockup shows on mobile (CSS hides it only ≤350px)."""
    html = client.get('/').get_data(as_text=True)
    img = _tag_containing(html, 'brand-wordmark', tag='img')
    assert 'd-none' not in img
    assert 'd-md-inline' not in img


def test_solo_game_link_active_on_game_pages(app, client):
    """On the game's own blueprint the hoisted link carries the gold .active."""
    u = _enrolled_user()
    _login(client, u)
    html = client.get('/worldcup/rules').get_data(as_text=True)
    solo = _tag_containing(html, 'navbar-solo-game')
    assert 'active' in solo


def _tag_containing(html, needle, tag='a'):
    """Return the first `<tag ...>` opening-tag source that contains `needle`.

    Fails loudly (assert, not None) so a missing element reads as the real
    regression instead of a TypeError downstream.
    """
    start = 0
    while True:
        idx = html.find(f'<{tag}', start)
        assert idx != -1, f'no <{tag}> containing {needle!r} found'
        end = html.find('>', idx)
        candidate = html[idx:end + 1]
        if needle in candidate:
            return candidate
        start = end
