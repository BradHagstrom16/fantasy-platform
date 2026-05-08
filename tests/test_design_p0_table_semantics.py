"""P0 S0.2 — lock: every public WC/global table renders `<th scope="col">`
on each header cell and a `<caption class="visually-hidden">` describing the
table contents. WCAG 2.1 SC 1.3.1 (Info and Relationships).

Auth-gated paths are skipped here (the WC pool's interior surfaces are covered
by per-page session integration tests in later phases). The public WC routes
already in scope: leaderboard, schedule, stats, groups, rules.
"""

import re

import pytest

from app import create_app
from extensions import db


PATHS_WITH_TABLES = [
    '/worldcup/leaderboard',
    '/worldcup/schedule',
    '/worldcup/stats',
    '/worldcup/groups',
    '/worldcup/rules',
]


@pytest.fixture
def client():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app.test_client()


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


def test_your_standing_tribune_carries_landmark_semantics(client):
    """The Your Position tribune block (P1 S1.1) is a self-contained landmark.

    Populated branch must render as `<section role="region" aria-labelledby=...>`.
    Empty branch (anon / unenrolled) renders as `<aside aria-label=...>` —
    `<aside>` is an HTML landmark by default and the aria-label names it.
    """
    resp = client.get('/worldcup/leaderboard', follow_redirects=False)
    if resp.status_code == 302:
        pytest.skip('leaderboard requires auth in this config')
    assert resp.status_code == 200

    body = resp.data.decode('utf-8')
    if 'your-standing-tribune' not in body:
        pytest.skip('Your Position tribune block not rendered in this state')

    open_tag_match = re.search(
        r'<(?:section|aside|div)[^>]*class="[^"]*your-standing-tribune[^"]*"[^>]*>',
        body,
    )
    assert open_tag_match, 'Could not find the .your-standing-tribune wrapper'
    open_tag = open_tag_match.group(0)

    is_aside = open_tag.startswith('<aside')
    if is_aside:
        # Empty branch — <aside> is an implicit complementary landmark; an
        # aria-label is enough to name it for screen readers.
        assert 'aria-label="' in open_tag, (
            f'Empty tribune <aside> needs aria-label: {open_tag}'
        )
    else:
        # Populated branch — explicit region role + named labelledby/aria-label.
        assert 'role="region"' in open_tag, (
            f'Populated tribune wrapper is missing role="region": {open_tag}'
        )
        assert ('aria-labelledby="' in open_tag) or ('aria-label="' in open_tag), (
            f'Populated tribune wrapper needs aria-labelledby or aria-label: {open_tag}'
        )
