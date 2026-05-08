"""P0 S0.2 — lock: every public WC/global table renders `<th scope="col">`
on each header cell and a `<caption class="visually-hidden">` describing the
table contents. WCAG 2.1 SC 1.3.1 (Info and Relationships).

Auth-gated paths are skipped here (the WC pool's interior surfaces are covered
by per-page session integration tests in later phases). The public WC routes
already in scope: leaderboard, schedule, stats, groups, rules.
"""

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

    # Every <thead> block on the page must contain at least one scope="col" attr,
    # and every <table> must include a <caption> with the visually-hidden class.
    import re

    thead_blocks = re.findall(r'<thead[^>]*>(.*?)</thead>', body, re.DOTALL)
    for block in thead_blocks:
        assert 'scope="col"' in block, (
            f'{path}: a <thead> on this page is missing scope="col" on its <th>: '
            f'{block[:200]}'
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


def test_your_standing_carries_region_role(client):
    """The leaderboard's Your Standing block is a self-contained landmark; it
    must wrap as `<section role="region" aria-labelledby=...>` (or an aria-label
    equivalent) so screen readers can navigate to it."""
    resp = client.get('/worldcup/leaderboard', follow_redirects=False)
    if resp.status_code == 302:
        pytest.skip('leaderboard requires auth in this config')
    assert resp.status_code == 200

    body = resp.data.decode('utf-8')
    # Anonymous leaderboard renders without your_standing context, so this
    # check is conditional. When present, the wrapping element MUST be a
    # landmark with role="region" + aria-labelledby (or aria-label).
    if 'your-standing' not in body:
        pytest.skip('Your Standing block is not rendered in the anonymous state')

    import re
    # Look for the .your-standing element and confirm it carries a region role
    # and aria-labelledby OR aria-label attribute.
    section_match = re.search(
        r'<(?:section|div)[^>]*class="[^"]*your-standing[^"]*"[^>]*>', body
    )
    assert section_match, 'Could not find the .your-standing wrapper element'
    open_tag = section_match.group(0)
    assert 'role="region"' in open_tag, (
        f'.your-standing wrapper is missing role="region": {open_tag}'
    )
    assert ('aria-labelledby="' in open_tag) or ('aria-label="' in open_tag), (
        f'.your-standing wrapper needs aria-labelledby or aria-label: {open_tag}'
    )
