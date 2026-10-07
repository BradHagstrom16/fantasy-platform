"""The club's two pages in the bar, and the member chip (navbar redesign
2026-10-07).

The Tribune and The Record left the account dropdown for the switcher list,
after the rooms: text links like the games, no icon (the gear on the admin
link is the bar's one icon, the thing that tells the Commish's desk from his
account). Members only; the footer stays the anonymous door to The Record.
The account toggle is the member chip, an outlined toggle with a chevron, so
it reads as a menu.
"""

from extensions import db
from games.cfb.services.enrollment import admin_enroll as cfb_admin_enroll
from games.docket.services.enrollment import admin_enroll as docket_admin_enroll
from tests._worldcup_fixtures import make_user


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id   # auth_id, never str(user.id)
        sess['_fresh'] = True


def _member(email='club@test'):
    u = make_user(email=email, display_name='Clubber')
    db.session.commit()
    cfb_admin_enroll(u.id)
    docket_admin_enroll(u.id)
    return u


def _switcher(html):
    start = html.index('navbar-nav me-auto')
    return html[start:html.index('</ul>', start)]


def _menu(html):
    start = html.index('dropdown-menu')
    return html[start:html.index('</ul>', start)]


def _link(html, href):
    """The full <a ...>...</a> for href inside html."""
    at = html.index(f'href="{href}"')
    start = html.rindex('<a ', 0, at)
    return html[start:html.index('</a>', at) + 4]


def test_members_get_tribune_and_record_after_the_rooms(app, client):
    _login(client, _member())
    nav = _switcher(client.get('/').get_data(as_text=True))
    docket, tribune, record = (nav.index(h) for h in ('href="/docket', 'href="/tribune', 'href="/records"'))
    assert nav.index('href="/cfb') < docket < tribune < record
    assert '>Tribune</a>' in nav and '>Record</a>' in nav
    assert 'nav-item nav-item--club' in nav


def test_bar_links_carry_no_icon(app, client):
    _login(client, _member())
    nav = _switcher(client.get('/').get_data(as_text=True))
    assert 'bi-' not in nav


def test_dropdown_no_longer_carries_them(app, client):
    _login(client, _member())
    menu = _menu(client.get('/').get_data(as_text=True))
    assert '/tribune' not in menu
    assert '/records' not in menu
    assert '/profile' in menu and 'js-logout' in menu


def test_anonymous_bar_stays_bare(app, client):
    html = client.get('/').get_data(as_text=True)
    nav = _switcher(html)
    assert '/tribune' not in nav and '/records' not in nav
    assert 'ccc-footer-link" href="/records"' in html


def test_each_page_marks_its_own_link_active(app, client):
    _login(client, _member())
    tribune = client.get('/tribune').get_data(as_text=True)
    assert 'active' in _link(_switcher(tribune), '/tribune/')
    assert 'active' not in _link(_switcher(tribune), '/records')
    records = client.get('/records').get_data(as_text=True)
    assert 'active' in _link(_switcher(records), '/records')
    assert 'active' not in _link(_switcher(records), '/tribune/')


def test_account_toggle_is_the_member_chip(app, client):
    _login(client, _member())
    html = client.get('/').get_data(as_text=True)
    start = html.rindex('<a ', 0, html.index('nav-account'))
    chip = html[start:html.index('</a>', start)]
    assert 'dropdown-toggle' in chip
    assert 'aria-haspopup="menu"' in chip and 'aria-expanded="false"' in chip
    assert 'nav-account-name">Clubber<' in chip
    assert 'bi-chevron-down nav-account-chevron' in chip
