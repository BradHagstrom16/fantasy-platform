"""My Picks groups available teams by CfbTeam.get_conference().

The pool page (tests/test_cfb_pool_index.py) and the model both group by
CfbTeam.get_conference() -- the master-list conference with the stored
cfb_team.conference column as fallback. This locks that /cfb/my-picks
agrees: an admin-added team OFF the master list must land in its stored
conference, not 'Unknown'. The assertion fails on the pre-fix code
(TEAM_CONFERENCES.get(team.name, 'Unknown')) and passes after.
"""

from extensions import db
from games.cfb.models import CfbTeam
from tests._cfb_fixtures import make_enrollment, make_user, make_week


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id  # session identity is auth_id, not id
        sess['_fresh'] = True


def test_my_picks_groups_offmaster_team_by_stored_conference(client, app):
    make_week(1, is_active=True)  # non-CFP active week -> the else branch runs
    member = make_user('member')
    make_enrollment(member)
    # An available pool team whose name is off the master list but whose
    # conference column is set: get_conference() must fall back to it.
    db.session.add(CfbTeam(name='Directional State', conference='Pioneer League'))
    db.session.commit()

    _login(client, member)
    resp = client.get('/cfb/my-picks')

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Directional State' in html
    assert 'Pioneer League' in html   # grouped under its stored conference
    assert 'Unknown' not in html      # never dumped into the Unknown bucket
