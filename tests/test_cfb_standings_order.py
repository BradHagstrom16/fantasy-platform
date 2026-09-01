"""The room's standings table follows the official order (games/cfb/DESIGN.md
10.5, 10.8): the '#' column is the competition rank from the central helper
(ties share a rank, the next distinct key gaps), never the row number -- an
all-tied pool before Week 1 grades must read 1, 1, 1, not 1, 2, 3 -- and the
rows run highest cumulative spread first.
"""
import re

from extensions import db
from tests._cfb_fixtures import make_enrollment, make_user, make_week


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id  # session identity is auth_id, not id
        sess['_fresh'] = True


def _rank_cells(html):
    """The '#' cell of every Active Players row, in render order."""
    table = html.split('Active Players', 1)[1].split('</table>', 1)[0]
    return re.findall(r'<td class="cfb-rank-cell">(\d+)</td>', table)


def test_tied_pool_shares_rank_one(client, app):
    make_week(1, is_active=True)
    viewer = make_user('viewer')
    make_enrollment(viewer)
    for name in ['amy', 'ben']:
        make_enrollment(make_user(name))
    db.session.commit()

    _login(client, viewer)
    html = client.get('/cfb/').get_data(as_text=True)

    assert _rank_cells(html) == ['1', '1', '1']


def test_rank_column_gaps_after_a_tie_and_leads_with_the_highest_spread(client, app):
    make_week(1, is_active=True)
    viewer = make_user('viewer')
    make_enrollment(viewer).cumulative_spread = -13.5
    make_enrollment(make_user('amy')).cumulative_spread = 3.0
    make_enrollment(make_user('ben')).cumulative_spread = 3.0
    db.session.commit()

    _login(client, viewer)
    html = client.get('/cfb/').get_data(as_text=True)

    assert _rank_cells(html) == ['1', '1', '3']
    assert html.index('>amy<') < html.index('>viewer<')


# -- the rule text follows the code: room copy + doctrine ---------------------

def _read(path):
    from pathlib import Path
    return Path(path).read_text(encoding='utf-8')


def test_room_tiebreaker_copy_states_higher_is_better():
    html = _read('games/cfb/templates/cfb/index.html')
    rules = html.split('Tiebreaker Rules', 1)[1].split('</ol>', 1)[0]
    assert 'Higher is better' in rules
    assert 'Lower is better' not in rules
    assert 'deadline' in rules  # a week's picks count once its deadline passes


def test_my_picks_spread_note_states_higher_is_better():
    html = _read('games/cfb/templates/cfb/my_picks.html')
    note = html.split('How the spread works', 1)[1].split('</div>', 1)[0]
    assert 'higher total is better' in note
    assert 'lower total' not in note
    assert 'adds points' not in note


def test_doctrine_states_the_signed_higher_is_better_rule():
    doc = _read('games/cfb/DESIGN.md')
    assert 'lower is better' not in doc
    assert 'favorites add, underdogs subtract' not in doc
    assert doc.count('higher is better') >= 2  # 1.10 and 10.8 both carry it
