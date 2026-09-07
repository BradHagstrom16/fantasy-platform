"""Find a player and sort the ledger (Brad's Phase 3 rulings, 2026-09-07).

- Find: a `role="search"` GET form (the sheet's own `.docket-find` shape,
  7.7); every typed word must appear in a display name; **your line is
  always first** when a query is in force; zero matches are stated with the
  query and the field keeps the text; no silent caps.
- Sort: `?sort=name|points|wins|error&dir=asc|desc`, computed in the route
  (never Jinja `sort(attribute=...)`); the rank column keeps the official
  competition rank in every order, so an alternate sort never invents one;
  the default is the official order. Sort and find compose.
"""
import re
from datetime import datetime

import pytest

from extensions import db
from games.docket.models import DocketWeekResult
from tests._docket_fixtures import login, make_enrollment, make_user, make_week

GRADED_AT = datetime(2026, 9, 6, 4, 0)


def _member(username, display_name):
    user = make_user(username)
    make_enrollment(user, display_name=display_name)
    return user


def _week(week_number):
    week = make_week(week_number)
    week.default_error_tenths = 0
    db.session.flush()
    return week


def _result(week, user, points, wins, error_tenths=0):
    db.session.add(DocketWeekResult(
        user_id=user.id, week_id=week.id, points=points, wins=wins,
        error_tenths=error_tenths, graded_at=GRADED_AT))


def _rows(html):
    """[[rank, player, points, wins, error], ...] from the standings table."""
    body = html[html.find('<tbody>'):html.find('</tbody>')]
    rows = []
    for cells in re.findall(r'<tr class="[^"]*">(.*?)</tr>', body, re.S):
        rows.append([' '.join(re.sub(r'<[^>]+>', ' ', cell).split())
                     for cell in re.findall(r'<td[^>]*>(.*?)</td>',
                                            cells, re.S)])
    return rows


def _names(html):
    """The player cell without its avatar glyph or the You tag."""
    return [re.sub(r'^[^A-Za-z]+', '', row[1]).replace(' You', '')
            for row in _rows(html)]


def _seed():
    """Four lines, official order: Marty (13.0/5/off 2.0), Tierney twins
    level at 9.0/4 split by error, Zach last. The viewer is Mike Tierney,
    officially 3rd."""
    week = _week(1)
    marty = _member('marty', 'Marty Tierney')
    mike = _member('mike', 'Mike Tierney')
    greg = _member('greg', 'Greg Tierney')
    zach = _member('zach', 'Zach Myers')
    _result(week, marty, 13.0, 5, 20)
    _result(week, greg, 9.0, 4, 5)
    _result(week, mike, 9.0, 4, 15)
    _result(week, zach, 4.0, 2, 40)
    db.session.commit()
    return mike


def test_default_order_is_the_official_order(app, client):
    login(client, _seed())
    html = client.get('/docket/ledger').get_data(as_text=True)
    assert _names(html) == ['Marty Tierney', 'Greg Tierney', 'Mike Tierney',
                            'Zach Myers']
    assert [row[0].split()[0] for row in _rows(html)] == ['1', '2', '3', '4']


def test_find_form_is_a_search_landmark_on_the_ledger(app, client):
    login(client, _seed())
    html = client.get('/docket/ledger').get_data(as_text=True)
    form = re.search(r'<form role="search"[^>]*class="docket-find[^"]*"[^>]*>(.*?)</form>',
                     html, re.S)
    assert form, 'the ledger carries the sheet\'s find form'
    assert 'method="get"' in form.group(0)
    assert 'action="/docket/ledger"' in form.group(0)
    assert '<label class="docket-find-label" for="ledger-find-q">' in form.group(1)
    assert 'name="q"' in form.group(1) and 'maxlength="60"' in form.group(1)


def test_find_matches_every_word_of_a_display_name(app, client):
    login(client, _seed())
    html = client.get('/docket/ledger?q=greg+TIERNEY').get_data(as_text=True)
    assert _names(html) == ['Mike Tierney', 'Greg Tierney']  # you, then the match
    assert 'Showing 1 of 4' in html and 'greg TIERNEY' in html


def test_find_pins_your_line_first_ahead_of_earlier_matches(app, client):
    """Marty and Greg both match 'tierney' and both stand above Mike in the
    official order; with a query in force Mike's line leads anyway."""
    login(client, _seed())
    html = client.get('/docket/ledger?q=tierney').get_data(as_text=True)
    assert _names(html) == ['Mike Tierney', 'Marty Tierney', 'Greg Tierney']
    assert 'Showing 3 of 4' in html
    # the pinned line keeps its official rank
    assert _rows(html)[0][0].split()[0] == '3'


def test_find_with_no_match_states_it_and_keeps_your_line(app, client):
    login(client, _seed())
    html = client.get('/docket/ledger?q=zzz').get_data(as_text=True)
    assert 'No line matches' in html and 'zzz' in html
    assert 'Showing 0 of 4' in html
    assert _names(html) == ['Mike Tierney']
    assert 'value="zzz"' in html


def test_find_query_is_normalized_and_capped(app, client):
    login(client, _seed())
    long = 'x' * 80
    html = client.get(f'/docket/ledger?q=+{long}+').get_data(as_text=True)
    assert f'value="{"x" * 60}"' in html


@pytest.mark.parametrize('key,direction,expected', [
    ('name', 'asc', ['Greg Tierney', 'Marty Tierney', 'Mike Tierney', 'Zach Myers']),
    ('name', 'desc', ['Zach Myers', 'Mike Tierney', 'Marty Tierney', 'Greg Tierney']),
    ('points', 'desc', ['Marty Tierney', 'Greg Tierney', 'Mike Tierney', 'Zach Myers']),
    ('points', 'asc', ['Zach Myers', 'Greg Tierney', 'Mike Tierney', 'Marty Tierney']),
    ('wins', 'asc', ['Zach Myers', 'Greg Tierney', 'Mike Tierney', 'Marty Tierney']),
    ('error', 'asc', ['Greg Tierney', 'Mike Tierney', 'Marty Tierney', 'Zach Myers']),
    ('error', 'desc', ['Zach Myers', 'Marty Tierney', 'Mike Tierney', 'Greg Tierney']),
])
def test_sort_by_each_key_in_both_directions(app, client, key, direction, expected):
    login(client, _seed())
    html = client.get(f'/docket/ledger?sort={key}&dir={direction}').get_data(as_text=True)
    assert _names(html) == expected


def test_sort_keeps_the_official_rank_on_every_row(app, client):
    """An alternate order never invents a rank: the rank column still prints
    the competition rank, and the caption says what the rows are sorted by."""
    login(client, _seed())
    html = client.get('/docket/ledger?sort=name&dir=asc').get_data(as_text=True)
    ranks = [row[0].split()[0] for row in _rows(html)]
    assert ranks == ['2', '1', '3', '4']
    assert 'sorted by name' in html.lower()
    assert 'aria-sort="ascending"' in html


def test_sort_headers_link_to_the_next_direction(app, client):
    login(client, _seed())
    html = client.get('/docket/ledger?sort=points&dir=desc').get_data(as_text=True)
    assert 'sort=points&amp;dir=asc' in html or 'sort=points&dir=asc' in html
    assert 'aria-sort="descending"' in html


def test_sort_and_find_compose(app, client):
    login(client, _seed())
    html = client.get('/docket/ledger?q=tierney&sort=name&dir=asc').get_data(as_text=True)
    assert _names(html) == ['Mike Tierney', 'Greg Tierney', 'Marty Tierney']
    assert 'sort=name&amp;dir=desc&amp;q=tierney' in html or 'q=tierney' in html


def test_unknown_sort_falls_back_to_the_official_order(app, client):
    login(client, _seed())
    html = client.get('/docket/ledger?sort=luck&dir=sideways').get_data(as_text=True)
    assert _names(html) == ['Marty Tierney', 'Greg Tierney', 'Mike Tierney',
                            'Zach Myers']
