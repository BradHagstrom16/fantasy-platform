"""/records, The Record (ADR-068, open-items §E PR 2): the public page over the
season_finishes ledger, its nav entry points, and its CSS section."""
import re
from pathlib import Path

from extensions import db
from models.records import FinishDraft, record_season
from models.user import User

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / 'static' / 'css' / 'style.css'


def _user(username, *, display_name=None, avatar_emoji=None):
    u = User(username=username, email=f'{username}@test.com', avatar_emoji=avatar_emoji)
    u.display_name = display_name
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _seed():
    cub = _user('cubbies22', display_name='Cubs Fan', avatar_emoji='\U0001F9A1')
    record_season('cfb', 2025, [
        FinishDraft(cub.id, 'Fourth & Pine', 1, 'champion', '2 lives · spread -163.5'),
        FinishDraft(None, 'CamTheRam17', 2, 'eliminated', 'Out Week 16 · spread -144.5'),
        FinishDraft(None, 'Caputa22', 3, 'eliminated', 'Out Week 2 · spread -12.0'),
    ])
    brad = _user('brad')
    record_season('worldcup', 2026, [
        FinishDraft(brad.id, 'brad', 1, None, '487.0 pts'),
        FinishDraft(None, 'Runner', 2, None, '250.0 pts'),
    ])
    return cub, brad


def test_the_record_is_public_and_cacheable(client):
    _seed()
    resp = client.get('/records')
    assert resp.status_code == 200
    page = resp.data.decode()
    assert 'The Record' in page
    assert 'Fourth &amp; Pine' in page and 'Caputa22' in page and 'Runner' in page
    assert '2 lives · spread -163.5' in page and '487.0 pts' in page
    assert '<form' not in page
    assert 'no-store' not in resp.headers.get('Cache-Control', '')


def test_champions_roll_leads_and_links_each_board(client):
    _seed()
    page = client.get('/records').data.decode()
    roll = page.index('records-roll')
    boards = page.index('records-board')
    assert roll < boards
    assert 'href="#board-cfb-2025"' in page
    assert 'href="#board-worldcup-2026"' in page
    # Newest season first; only the newest board opens.
    assert page.index('id="board-worldcup-2026"') < page.index('id="board-cfb-2025"')
    opened = re.findall(r'<details[^>]*records-board[^>]*>', page)
    assert len(opened) == 2
    assert ' open' in opened[0] and ' open' not in opened[1]


def test_linked_rows_carry_the_avatar_and_the_current_name_only_when_it_differs(client):
    cub, brad = _seed()
    page = client.get('/records').data.decode()
    # The linked 2025 winner is Survivor's reigning champion: the trophy,
    # never the stored choice (ADR-068 through User.get_avatar).
    assert User.CHAMPION_AVATAR in page
    assert '\U0001F9A1' not in page
    assert 'now Cubs Fan' in page
    # brad's recorded name is his current name: no "now" line.
    assert 'now brad' not in page


def test_each_board_links_the_room_archive(client, app):
    _seed()
    page = client.get('/records').data.decode()
    with app.test_request_context():
        from flask import url_for
        assert url_for('cfb.history') in page
        assert url_for('worldcup.leaderboard') in page
        assert url_for('docket.ledger') not in page


def test_empty_record_reads_as_a_promise(client):
    page = client.get('/records').data.decode()
    assert 'Nothing on the record yet' in page
    assert 'records-board' not in page


def test_footer_carries_the_record_for_everyone(client):
    anon = client.get('/login').data.decode()
    assert 'ccc-footer-link" href="/records"' in anon
    assert 'The Record' in anon


def test_account_dropdown_carries_the_record_for_members(client):
    # Log in before any request: Flask-Login caches the anonymous user on g
    # for the fixture's one app context otherwise.
    _login(client, _user('member'))
    home = client.get('/profile').data.decode()
    assert 'dropdown-item" href="/records"' in home


def test_the_2025_archive_points_at_the_record(client):
    page = client.get('/cfb/history').data.decode()
    assert 'href="/records"' in page


def test_css_section_is_its_own_with_a_phone_block():
    css = CSS.read_text(encoding='utf-8')
    start = css.index('/* === THE RECORD')
    section = css[start:]
    assert '@media (max-width: 575.98px)' in section
    assert '.records-page' in section
    assert '.tribune-' not in section     # the parallel-trees rule: no cross-applied primitives
