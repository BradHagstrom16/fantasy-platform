"""Navbar solo-game hoist + full mobile lockup (mobile top-bar redesign),
plus the archive split (design review 2026-08-18).

While a user's ACTIVE enrolled-game count == 1, the game switcher hoists out
of the hamburger into the visible bar (`.navbar-solo-game`, below-lg only)
and the collapse copy hides below lg (`d-none d-lg-block`) so the link
appears exactly once per breakpoint. A completed game (World Cup) leaves the
switcher entirely and lives in the account dropdown's Archive section for
its members — `joined_games()` still returns it (registry archive contract);
the split happens in the nav context processor. The brand wordmark renders
at all widths (the CSS ≤350px fallback hides it; the template no longer
gates it at `d-md-inline`).
"""
import pytest

from app import create_app
from extensions import db
from games.cfb.services.enrollment import admin_enroll as cfb_admin_enroll
from games.docket.services.enrollment import admin_enroll as docket_admin_enroll
from tests._worldcup_fixtures import make_enrollment, make_user


@pytest.fixture
def app():
    """Testing app with a fresh in-memory schema per test."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client bound to the per-test app."""
    return app.test_client()


def _login(client, user):
    """Seed the session with the user's identity.

    Session identity is auth_id, NOT str(user.id) — see CLAUDE.md invariant.
    """
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _enrolled_user(email='solo@test'):
    """Create a user joined to exactly one ACTIVE game (CFB) — the hoist case."""
    u = make_user(email=email, display_name='Solo')
    db.session.commit()
    cfb_admin_enroll(u.id)
    return u


def _wc_archived_user(email='archivist@test'):
    """Create a user whose only membership is the completed World Cup."""
    u = make_user(email=email, display_name='Archivist')
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
    assert '/cfb' in solo
    assert 'CFB' in html


def test_solo_game_collapse_copy_hidden_below_lg(app, client):
    """The hamburger copy of the solo game hides below lg — no duplicate link."""
    u = _enrolled_user()
    _login(client, u)
    html = client.get('/').get_data(as_text=True)
    li = _tag_containing(html, 'nav-item', tag='li')
    assert 'd-none' in li and 'd-lg-block' in li


def test_anonymous_gets_no_solo_game_link(app, client):
    """Anonymous ⇒ joined_games() is [] ⇒ no hoist (count != 1)."""
    html = client.get('/').get_data(as_text=True)
    assert 'navbar-solo-game' not in html


def test_logged_in_zero_enrollments_gets_no_solo_game_link(app, client):
    """Authenticated-but-joined-nothing ⇒ no hoist. Distinct path from
    anonymous: joined_games() runs the per-game enrollment queries and
    filters to [] instead of short-circuiting on is_authenticated, so a
    guard regression like `length <= 1` is caught here, not above."""
    u = make_user(email='nogames@test', display_name='NoGames')
    db.session.commit()
    _login(client, u)
    html = client.get('/').get_data(as_text=True)
    assert 'navbar-solo-game' not in html


def test_two_enrollments_fall_back_to_dropdown(app, client):
    """2+ joined ACTIVE games ⇒ no hoist; both collapse items render unhidden."""
    u = _enrolled_user()
    docket_admin_enroll(u.id)
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
    html = client.get('/cfb/history').get_data(as_text=True)
    solo = _tag_containing(html, 'navbar-solo-game')
    assert 'active' in solo


# ── the archive split (design review 2026-08-18) ─────────────────────────

def _nav_section(html):
    start = html.find('navbar-nav me-auto')
    return html[start:html.find('</ul>', start)]


def _dropdown_section(html):
    start = html.find('dropdown-menu')
    return html[start:html.find('</ul>', start)]


def test_completed_game_moves_to_the_archive_dropdown(app, client):
    """A WC member's link leaves the switcher and lands in the account
    dropdown under The Archive — same audience as before, new address."""
    u = _wc_archived_user()
    _login(client, u)
    html = client.get('/').get_data(as_text=True)
    assert 'World Cup' not in _nav_section(html)
    dd = _dropdown_section(html)
    assert 'The Archive' in dd
    assert 'World Cup' in dd
    assert '/worldcup' in dd


def test_archived_game_never_hoists_solo(app, client):
    """A WC-only member has zero ACTIVE games: no hoist, archive only."""
    u = _wc_archived_user(email='wconly@test')
    _login(client, u)
    html = client.get('/').get_data(as_text=True)
    assert 'navbar-solo-game' not in html
    assert 'The Archive' in html


def test_no_archive_section_without_archived_membership(app, client):
    """A CFB-only member gets no Archive section — the dropdown stays
    member-gated exactly like the old navbar link."""
    u = _enrolled_user(email='cfbonly@test')
    _login(client, u)
    html = client.get('/').get_data(as_text=True)
    assert 'The Archive' not in html
    assert 'dropdown-header' not in html


def test_anonymous_gets_no_archive_section(app, client):
    html = client.get('/').get_data(as_text=True)
    assert 'The Archive' not in html


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
