"""P0 S0.2 — lock: every public WC/global table renders `<th scope="col">`
on each header cell and a `<caption class="visually-hidden">` describing the
table contents. WCAG 2.1 SC 1.3.1 (Info and Relationships).

The table-semantics tests run against the public anonymous routes. The Tribune
landmark test (P1 S1.1) covers BOTH branches — anonymous (`<aside>`) and
authenticated+enrolled (`<section role="region">`) — because the populated
branch only renders for an enrolled user, and CR R1 caught that the original
anon-only test left the populated assertion as dead code.
"""

import re

import pytest

from app import create_app
from extensions import db
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment
from models.user import User


PATHS_WITH_TABLES = [
    '/worldcup/leaderboard',
    '/worldcup/schedule',
    '/worldcup/stats',
    '/worldcup/groups',
    '/worldcup/rules',
]


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


def _seed_enrolled_user(username='alice'):
    u = User(username=username, email=f'{username}@test.com')
    u.set_password('pass')
    db.session.add(u)
    db.session.flush()
    e = WorldCupEnrollment(
        user_id=u.id, season_year=SEASON_YEAR,
        picks_submitted=True, total_score=42.0, usa_goals_guess=5,
    )
    db.session.add(e)
    db.session.commit()
    return u


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


@pytest.mark.parametrize('path', PATHS_WITH_TABLES)
def test_tables_carry_scope_col_and_caption(client, path):
    """Public GET must render `<th scope="col">` on every column header AND
    a `<caption class="visually-hidden">` on every standings table. Pages
    that don't actually render a `<table>` in the current state pass trivially."""
    resp = client.get(path, follow_redirects=False)
    if resp.status_code == 302:
        pytest.skip(f'{path} requires auth; covered by per-page session tests')
    assert resp.status_code == 200, f'{path} returned {resp.status_code}'

    body = resp.data.decode('utf-8')
    if '<table' not in body:
        return  # page may not render a table in this state (e.g., empty leaderboard)

    # Every <th> in every <thead> on the page must carry scope="col",
    # and every <table> must include a <caption> with the visually-hidden class.
    thead_blocks = re.findall(r'<thead[^>]*>(.*?)</thead>', body, re.DOTALL | re.IGNORECASE)
    for block in thead_blocks:
        header_cells = re.findall(r'<th\b[^>]*>', block, re.IGNORECASE)
        assert header_cells, f'{path}: <thead> has no <th> cells: {block[:200]}'
        missing_scope = [
            th for th in header_cells
            if not re.search(r'\bscope\s*=\s*["\']col["\']', th, re.IGNORECASE)
        ]
        assert not missing_scope, (
            f'{path}: <thead> has <th> without scope="col": '
            f'{missing_scope[:3]}'
        )

    # Per-table caption check.
    tables = re.findall(r'<table[^>]*>(.*?)</table>', body, re.DOTALL)
    for tbl in tables:
        assert '<caption' in tbl, f'{path}: a <table> is missing <caption>'
        caption_match = re.search(
            r'<caption[^>]*class="[^"]*visually-hidden[^"]*"', tbl
        )
        assert caption_match, (
            f'{path}: caption present but not class="visually-hidden". '
            'Captions must be screen-reader-only on these surfaces.'
        )


_TRIBUNE_OPEN_TAG_RE = re.compile(
    r'<(?:section|aside|div)[^>]*class="[^"]*your-standing-tribune[^"]*"[^>]*>',
)


def test_your_standing_tribune_anon_branch_landmark(client):
    """Anon viewer hits the empty branch — `<aside aria-label=...>`.

    `<aside>` is an HTML landmark by default; the aria-label names it for
    screen readers.
    """
    resp = client.get('/worldcup/leaderboard', follow_redirects=False)
    if resp.status_code == 302:
        pytest.skip('leaderboard requires auth in this config')
    assert resp.status_code == 200

    body = resp.data.decode('utf-8')
    open_tag_match = _TRIBUNE_OPEN_TAG_RE.search(body)
    assert open_tag_match, 'Could not find the .your-standing-tribune wrapper'
    open_tag = open_tag_match.group(0)

    assert open_tag.startswith('<aside'), (
        f'Anon viewer must hit the <aside> empty branch, got: {open_tag}'
    )
    assert 'aria-label="' in open_tag, (
        f'Empty tribune <aside> needs aria-label: {open_tag}'
    )


def test_your_standing_tribune_populated_branch_landmark(client, app):
    """Authenticated + enrolled viewer hits the populated branch — must render
    as `<section role="region" aria-labelledby=...>`.

    Locks the landmark contract on the populated path (CR R1 caught that the
    prior single-test version only ever exercised the anon path).
    """
    with app.app_context():
        u = _seed_enrolled_user('alice')
        _login(client, u.id)
        resp = client.get('/worldcup/leaderboard', follow_redirects=False)
    assert resp.status_code == 200

    body = resp.data.decode('utf-8')
    open_tag_match = _TRIBUNE_OPEN_TAG_RE.search(body)
    assert open_tag_match, 'Could not find the .your-standing-tribune wrapper'
    open_tag = open_tag_match.group(0)

    assert open_tag.startswith('<section'), (
        f'Populated viewer must hit the <section> branch, got: {open_tag}'
    )
    assert 'role="region"' in open_tag, (
        f'Populated tribune wrapper is missing role="region": {open_tag}'
    )
    assert 'aria-labelledby="' in open_tag or 'aria-label="' in open_tag, (
        f'Populated tribune wrapper needs aria-labelledby or aria-label: {open_tag}'
    )
