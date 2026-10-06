"""The scorecard (/golf/member/<id>): Golf Phase U4.

Locks ``games/golf/services/scorecard.py`` and the page built from it
(games/golf/DESIGN.md §8, §9):

- public like the sheet, and secret by the lock: until a week is revealed,
  nobody but the member is handed its pick;
- the weeks run newest first, from the next pick back to week 1;
- rank and total are the sheet's own row, pencil included;
- every read is season-scoped, and the query count does not grow with the
  weeks or the room;
- /golf/my-picks is the old address and redirects to the member's own card.

The routing, secrecy, tile and ledger cases are ported from the legacy app's
``tests/test_member_scorecard.py``. Every clock-dependent test pins
GOLF_FAKE_NOW (the conftest app fixture pins ENVIRONMENT=testing). A test
signs in before its first request or not at all: Flask-Login caches the viewer
on the fixture's app context, so a login after an anonymous request is not seen.
"""
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import event

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfSeasonPlayerUsage,
    GolfTournament,
    GolfTournamentField,
    GolfTournamentResult,
)
from models.user import User
from tests._registry_helpers import set_status

TEMPLATES = Path(__file__).parent.parent / 'games' / 'golf' / 'templates' / 'golf'

# Masters week 2026 on the league's wall clock; the fake clock is UTC.
TUESDAY_BEFORE = '2026-04-07T15:00:00'
SUNDAY_430_PM_CT = '2026-04-12T21:30:00'
THURSDAY_AFTER_LOCK = '2026-04-09T15:00:00'


@pytest.fixture()
def season(app):
    return app.config['SEASON_YEAR']


@pytest.fixture()
def tuesday(monkeypatch):
    """The Tuesday of Masters week: two weeks banked, the Masters open."""
    monkeypatch.setenv('GOLF_FAKE_NOW', TUESDAY_BEFORE)


@pytest.fixture()
def sunday(monkeypatch):
    monkeypatch.setenv('GOLF_FAKE_NOW', SUNDAY_430_PM_CT)


# --- seed helpers (run inside the fixture's app context) --------------------

def _member(season, username, display_name=None, total=0, has_paid=True, penalty_paid=0):
    user = User(username=username, email=f'{username}@test.com',
                display_name=display_name or username)
    user.set_password('pw')
    db.session.add(user)
    db.session.flush()
    db.session.add(GolfEnrollment(user_id=user.id, season_year=season, total_points=total,
                                  has_paid=has_paid, penalty_paid=penalty_paid))
    db.session.commit()
    return user


def _week(season, name, week, start, finalized=True, is_major=False, lock=True,
          purse=10_000_000):
    """A tournament starting on ``start``, locking that morning at 7:00."""
    t = GolfTournament(
        api_tourn_id=f'{season}-{week}', name=name, season_year=season,
        start_date=start, end_date=start.replace(day=start.day + 3),
        pick_deadline=start.replace(hour=7) if lock else None, purse=purse,
        is_major=is_major, status='complete' if finalized else 'upcoming',
        results_finalized=finalized, week_number=week,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _golfer(last):
    player = GolfPlayer(api_player_id=last[:20], first_name='Test', last_name=last)
    db.session.add(player)
    db.session.commit()
    return player


def _result(tournament, player, position='1', status='complete', rounds=4, earnings=0, score=None):
    db.session.add(GolfTournamentResult(
        tournament_id=tournament.id, player_id=player.id, status=status,
        final_position=position, rounds_completed=rounds, earnings=earnings, score_to_par=score,
    ))
    db.session.commit()


def _pick(user, tournament, primary, backup, **kwargs):
    pick = GolfPick(user_id=user.id, tournament_id=tournament.id,
                    primary_player_id=primary.id, backup_player_id=backup.id, **kwargs)
    db.session.add(pick)
    db.session.commit()
    return pick


def _banked(user, tournament, primary, backup, points, counted=None, **kwargs):
    """A resolved pick with the usage row the scoring would have written."""
    counted = counted or primary
    pick = _pick(
        user, tournament, primary, backup, active_player_id=counted.id, points_earned=points,
        primary_used=counted is primary, backup_used=counted is backup, **kwargs,
    )
    db.session.add(GolfSeasonPlayerUsage(
        user_id=user.id, player_id=counted.id, season_year=tournament.season_year,
    ))
    db.session.commit()
    return pick


def _field(tournament, size=50):
    players = [GolfPlayer(api_player_id=f'F{tournament.id}-{i}', first_name='Field',
                          last_name=f'Golfer{i:02d}') for i in range(size)]
    db.session.add_all(players)
    db.session.flush()
    db.session.add_all([GolfTournamentField(tournament_id=tournament.id, player_id=p.id)
                        for p in players])
    db.session.commit()


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _get(client, user, **query):
    return client.get(f'/golf/member/{user.id}', query_string=query)


def _body(client, user, **query):
    resp = _get(client, user, **query)
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def _row(body, event_name):
    """The scorecard row for one event."""
    start = body.index(f'>{event_name}</a>')
    return body[body.rindex('<tr', 0, start):body.index('</tr>', start)]


def _tile(body, label):
    """The <dd> under a tile's label, as text."""
    start = body.index(f'>{label}</dt>')
    dd = body[body.index('<dd>', start):body.index('</dd>', start)]
    return ' '.join(re.sub(r'<[^>]+>', ' ', dd).split())


@contextmanager
def _count_sql():
    counter = {'n': 0}

    def _before(conn, cursor, statement, parameters, context, executemany):
        counter['n'] += 1

    event.listen(db.engine, 'before_cursor_execute', _before)
    try:
        yield counter
    finally:
        event.remove(db.engine, 'before_cursor_execute', _before)


def _two_weeks_and_the_masters(season):
    """Viewer and Rival through two banked weeks, the Masters next, the RBC after.

    Week 11: the viewer's Alpha finished 2nd ($500,000); Rival's Bravo missed
    the cut. Week 12: the viewer's primary withdrew early and the backup,
    Charlie, counted ($120,000); Rival had no pick. Week 13 is the Masters
    (a major), week 14 the RBC Heritage.
    """
    viewer = _member(season, 'viewer', display_name='ViewerLine', total=620_000)
    rival = _member(season, 'rival', display_name='RivalLine', total=0)
    g = {name: _golfer(name) for name in (
        'Alpha', 'Bravo', 'Charlie', 'Withdrew', 'Spare', 'Hotgolfer', 'Coldgolfer')}
    valspar = _week(season, 'Valspar Championship', 11, datetime(2026, 3, 19))
    houston = _week(season, 'Houston Open', 12, datetime(2026, 3, 26))
    masters = _week(season, 'Masters Tournament', 13, datetime(2026, 4, 9),
                    finalized=False, is_major=True)
    rbc = _week(season, 'RBC Heritage', 14, datetime(2026, 4, 16), finalized=False)

    _result(valspar, g['Alpha'], position='2', earnings=500_000, score=-9)
    _result(valspar, g['Bravo'], position='CUT', status='cut', rounds=2)
    _result(houston, g['Withdrew'], position='WD', status='wd', rounds=1)
    _result(houston, g['Charlie'], position='T12', earnings=120_000, score=-4)
    _banked(viewer, valspar, g['Alpha'], g['Spare'], 500_000)
    _banked(rival, valspar, g['Bravo'], g['Spare'], 0)
    _banked(viewer, houston, g['Withdrew'], g['Charlie'], 120_000, counted=g['Charlie'])
    return viewer, rival, g, {'valspar': valspar, 'houston': houston, 'masters': masters, 'rbc': rbc}


# ============================================================================
# Routing
# ============================================================================

def test_scorecard_is_public_and_named_for_its_member(app, client, season, tuesday):
    viewer, rival, *_ = _two_weeks_and_the_masters(season)

    body = _body(client, rival)                     # signed out
    assert 'RivalLine&#39;s Scorecard</h1>' in body
    assert 'golf-your-line--theirs' in body         # no pen bracket on a line that is not yours


def test_your_own_scorecard_is_yours(app, client, season, tuesday):
    viewer, rival, *_ = _two_weeks_and_the_masters(season)
    _login(client, viewer)

    body = _body(client, viewer)
    assert 'Your Scorecard</h1>' in body
    assert 'golf-your-line--theirs' not in body
    theirs = _body(client, rival)
    assert 'RivalLine&#39;s Scorecard</h1>' in theirs and 'golf-your-line--theirs' in theirs


def test_scorecard_404s_without_a_line(app, client, season, tuesday):
    viewer, *_ = _two_weeks_and_the_masters(season)
    outsider = User(username='no_line', email='no_line@test.com')
    outsider.set_password('pw')
    db.session.add(outsider)
    db.session.commit()

    assert client.get('/golf/member/999999').status_code == 404
    assert _get(client, outsider).status_code == 404          # a platform user with no line
    assert _get(client, viewer, season=season - 1).status_code == 404
    assert _get(client, viewer, season='soon').status_code == 404


def test_switcher_lands_on_the_scorecards_own_url(app, client, season, tuesday):
    viewer, rival, *_ = _two_weeks_and_the_masters(season)

    resp = client.get('/golf/member', query_string={'user_id': rival.id})
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith(f'/golf/member/{rival.id}')

    resp = client.get('/golf/member', query_string={'user_id': rival.id, 'season': season - 1})
    assert resp.headers['Location'].endswith(f'/golf/member/{rival.id}?season={season - 1}')

    # isdigit() would pass a superscript two on to int(), which refuses it.
    resp = client.get('/golf/member', query_string={'user_id': '²'})
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/golf/')


def test_bare_member_address_is_your_own_scorecard(app, client, season, tuesday):
    viewer, *_ = _two_weeks_and_the_masters(season)
    _login(client, viewer)

    resp = client.get('/golf/member')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith(f'/golf/member/{viewer.id}')


def test_switcher_lists_the_seasons_members_and_posts_without_script(app, client, season, tuesday):
    viewer, rival, *_ = _two_weeks_and_the_masters(season)
    body = _body(client, rival)

    form = body[body.index('<form class="golf-switch"'):body.index('</form>')]
    assert 'method="get"' in form and 'action="/golf/member"' in form
    assert f'<option value="{rival.id}" selected>RivalLine</option>' in form
    assert f'<option value="{viewer.id}">ViewerLine</option>' in form
    assert form.index('RivalLine') < form.index('ViewerLine')      # by name
    assert 'type="submit"' in form
    assert '<script' not in (TEMPLATES / 'member_scorecard.html').read_text()


def test_my_picks_asks_a_guest_to_sign_in(app, client, season, tuesday, monkeypatch):
    set_status(monkeypatch, 'golf', 'open')
    _two_weeks_and_the_masters(season)

    resp = client.get('/golf/my-picks')
    assert resp.status_code == 302 and '/login' in resp.headers['Location']


def test_my_picks_is_the_old_address(app, client, season, tuesday, monkeypatch):
    set_status(monkeypatch, 'golf', 'open')
    viewer, *_ = _two_weeks_and_the_masters(season)
    _login(client, viewer)

    resp = client.get('/golf/my-picks')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith(f'/golf/member/{viewer.id}')
    assert client.get('/golf/my-picks', follow_redirects=True).status_code == 200


# ============================================================================
# The weeks
# ============================================================================

def test_weeks_run_newest_first_from_the_next_pick(app, client, season, tuesday):
    viewer, *_ = _two_weeks_and_the_masters(season)
    body = _body(client, viewer)

    table = body[body.index('<table class="golf-sheet golf-weeks"'):body.index('</table>')]
    assert (table.index('Masters Tournament') < table.index('Houston Open')
            < table.index('Valspar Championship'))
    assert 'RBC Heritage' not in table              # after the next pick: counted, not listed
    assert '1 week still to play' in body

    valspar = _row(body, 'Valspar Championship')
    assert 'Wk 11' in valspar
    assert 'golf-money--banked">$500,000' in valspar
    assert 'Alpha <span class="golf-chip golf-chip--pen">Used</span>' in valspar
    assert '· 2 · −9' in valspar
    assert 'backup Spare' in valspar

    # The backup counted: he is the one spent, and the line says whom he replaced.
    houston = _row(body, 'Houston Open')
    assert 'Charlie <span class="golf-chip golf-chip--pen">Used</span> · Backup, replaces Withdrew' in houston
    assert 'golf-money--banked">$120,000' in houston
    assert 'backup Charlie' not in houston

    masters = _row(body, 'Masters Tournament')
    assert 'Major ×1.5' in masters
    assert 'golf-money' not in masters              # nothing banked, nothing projected


def test_week_marks_cut_penalty_commish_and_no_pick(app, client, season, tuesday):
    viewer, rival, g, weeks = _two_weeks_and_the_masters(season)
    pick = GolfPick.query.filter_by(user_id=rival.id, tournament_id=weeks['valspar'].id).one()
    pick.admin_override = True
    pick.admin_override_note = 'Phoned it in'
    db.session.commit()
    body = _body(client, rival)

    valspar = _row(body, 'Valspar Championship')
    assert 'golf-chip--deduction">Cut<' in valspar
    assert 'title="Phoned it in">Commish<' in valspar
    assert '“Phoned it in”' in valspar                # in words: a phone has no hover
    assert 'golf-money--banked">$0' in valspar
    houston = _row(body, 'Houston Open')
    assert 'No pick' in houston
    assert 'golf-money--banked">$0' in houston
    assert _tile(body, 'Commish overrides') == '1'


def test_live_week_is_in_pencil_with_the_sheets_own_figures(app, client, season, sunday):
    """On Masters Sunday the scorecard's total, rank and week are the sheet's."""
    viewer, rival, g, weeks = _two_weeks_and_the_masters(season)
    masters = weeks['masters']
    _result(masters, g['Hotgolfer'], position='1', status='active', rounds=3)
    _result(masters, g['Coldgolfer'], position='CUT', status='cut', rounds=2)
    _pick(viewer, masters, g['Hotgolfer'], g['Spare'])
    _pick(rival, masters, g['Coldgolfer'], g['Spare'], penalty_triggered=True)
    masters.status = 'active'
    db.session.commit()
    _login(client, viewer)

    sheet = client.get('/golf/').get_data(as_text=True)
    figure = re.search(r'golf-hero-figure--projected">(~\$[\d,]+)<', sheet).group(1)
    body = _body(client, viewer)
    assert f'golf-hero-figure--projected">{figure}<' in body
    assert '<strong>1st</strong> of 2' in body and '<strong>1st</strong> of 2' in sheet

    row = _row(body, 'Masters Tournament')
    assert 'golf-chip--live">Live<' in row
    assert 'golf-money--projected">~$2,700,000' in row          # the purse's 18%, ×1.5
    assert '>Projected<' in row
    assert 'Used' not in row                                    # nobody is spent until it banks

    theirs = _row(_body(client, rival), 'Masters Tournament')
    assert 'golf-chip--deduction">Cut<' in theirs and 'badge-penalty' in theirs
    assert 'golf-money--projected">$0' in theirs                # a certain zero takes no tilde


def test_a_banked_week_with_no_deadline_still_shows(app, client, season, tuesday):
    """The lock reads a missing deadline as open; a banked week is revealed anyway."""
    viewer = _member(season, 'viewer', display_name='ViewerLine')
    alpha, spare = _golfer('Alpha'), _golfer('Spare')
    imported = _week(season, 'Imported Open', 3, datetime(2026, 1, 22), lock=False)
    _result(imported, alpha, position='5', earnings=90_000)
    _banked(viewer, imported, alpha, spare, 90_000)

    row = _row(_body(client, viewer), 'Imported Open')          # signed out
    assert 'Alpha' in row and 'golf-money--banked">$90,000' in row


# ============================================================================
# Nothing shows before the lock
# ============================================================================

@pytest.mark.parametrize('signed_in', [False, True])
def test_open_week_pick_is_hidden_from_everyone_but_the_member(app, client, season, tuesday,
                                                               signed_in):
    viewer, rival, g, weeks = _two_weeks_and_the_masters(season)
    _pick(rival, weeks['masters'], g['Hotgolfer'], g['Coldgolfer'], admin_override=True)
    if signed_in:
        _login(client, viewer)

    body = _body(client, rival)
    assert ('Your Scorecard' in client.get(f'/golf/member/{viewer.id}').get_data(as_text=True)) is signed_in
    assert 'Hotgolfer' not in body and 'Coldgolfer' not in body
    assert 'golf-weeks-row--open' not in body                   # the wash is the member's own
    assert ('Hidden until the lock, <span class="golf-nowrap">Thu Apr 9 · 7:00 AM CT</span>'
            in _row(body, 'Masters Tournament'))
    assert '/golf/pick/' not in body
    assert _tile(body, 'Commish overrides') == '0'              # an open week's override stays shut


def test_the_member_sees_their_own_open_pick_and_can_change_it(app, client, season, tuesday):
    viewer, rival, g, weeks = _two_weeks_and_the_masters(season)
    _pick(viewer, weeks['masters'], g['Hotgolfer'], g['Coldgolfer'])
    _login(client, viewer)

    row = _row(_body(client, viewer), 'Masters Tournament')
    assert 'Your pick: <strong>Hotgolfer</strong>, backup Coldgolfer.' in row
    assert f'href="/golf/pick/{weeks["masters"].id}">Change</a>' in row
    assert 'Picks lock <strong class="golf-nowrap">Thu Apr 9 · 7:00 AM CT</strong>' in row
    assert 'golf-weeks-row--open' in row              # the active week takes the pen wash
    assert 'golf-btn' not in row                      # a pick is in: no pick action
    assert 'Hidden' not in row


def test_the_lock_opens_the_week_to_everyone(app, client, season, monkeypatch):
    """Locked, not yet banked and not yet read: the pick shows, the figure does not."""
    viewer, rival, g, weeks = _two_weeks_and_the_masters(season)
    _pick(rival, weeks['masters'], g['Hotgolfer'], g['Coldgolfer'])
    monkeypatch.setenv('GOLF_FAKE_NOW', THURSDAY_AFTER_LOCK)

    row = _row(_body(client, rival), 'Masters Tournament')
    assert 'Hotgolfer' in row and 'backup Coldgolfer' in row
    assert 'no read yet' in row
    assert 'Hidden' not in row


def test_open_week_without_a_pick_offers_the_pick_only_to_the_member(app, client, season, tuesday):
    viewer, rival, g, weeks = _two_weeks_and_the_masters(season)
    _login(client, viewer)

    row = _row(_body(client, viewer), 'Masters Tournament')
    assert 'The field publishes Tuesday. Picks open then.' in row
    assert '/golf/pick/' not in row

    _field(weeks['masters'])
    body = _body(client, viewer)
    row = _row(body, 'Masters Tournament')
    assert 'No pick in yet.' in row
    # The pick action is the room's filled button (§7.24), once on the page.
    assert (f'<a class="btn btn-game golf-btn golf-weeks-act" href="/golf/pick/{weeks["masters"].id}">'
            'Spend a golfer</a>') in row
    assert body.count('golf-btn') == 1

    assert '/golf/pick/' not in _body(client, rival)            # never on another member's card


# ============================================================================
# The tiles, the fold and the ledger
# ============================================================================

def test_tiles_count_the_members_banked_season(app, client, season, tuesday):
    viewer, rival, *_ = _two_weeks_and_the_masters(season)

    body = _body(client, viewer)
    assert 'golf-hero-figure--banked">$620,000' in body
    assert '<strong>1st</strong> of 2' in body
    assert _tile(body, 'In the money') == '2 of 2'
    assert _tile(body, 'Golfers used') == '2'
    assert _tile(body, 'Commish overrides') == '0'
    assert _tile(body, 'Best pick') == '$500,000 Test Alpha, Valspar Championship'
    assert _tile(body, 'Missed cuts at majors') == '0'

    theirs = _body(client, rival)
    assert _tile(theirs, 'In the money') == '0 of 1'
    assert _tile(theirs, 'Best pick') == 'Nothing banked yet'


@pytest.mark.parametrize('paid,note', [(0, '$30 still owed to the pot'),
                                       (15, '$15 still owed to the pot'),
                                       (30, 'Settled, $30 paid')])
def test_majors_tile_says_what_the_pot_is_owed(app, client, season, tuesday, paid, note):
    """The tile counts the flag the scoring wrote, so it equals penalty_owed()."""
    viewer = _member(season, 'viewer', penalty_paid=paid)
    cut, spare = _golfer('Cutgolfer'), _golfer('Spare')
    for week, name in ((5, 'The Players'), (9, 'PGA Championship')):
        major = _week(season, name, week, datetime(2026, 2, week), is_major=True)
        # The archive's casing drifts; the tile must not re-read the status.
        _result(major, cut, position='CUT', status='CUT', rounds=2)
        _pick(viewer, major, cut, spare, active_player_id=cut.id, points_earned=0,
              primary_used=True, penalty_triggered=True)

    enrollment = GolfEnrollment.query.filter_by(user_id=viewer.id).one()
    assert enrollment.penalty_owed() == 30
    assert _tile(_body(client, viewer), 'Missed cuts at majors') == f'2 {note}'


def test_a_card_with_nothing_banked_says_so(app, client, season, tuesday):
    """No "0 of 0": an empty season is said in words."""
    viewer = _member(season, 'viewer')
    body = _body(client, viewer)

    assert 'no weeks on the schedule yet' in body
    assert _tile(body, 'In the money') == 'No weeks banked yet'
    assert _tile(body, 'Best pick') == 'Nothing banked yet'
    assert 'No week has been played yet.' in body
    assert '0 of 0' not in body


def test_used_golfers_show_on_any_members_card(app, client, season, tuesday):
    viewer, *_ = _two_weeks_and_the_masters(season)
    body = _body(client, viewer)                                # signed out

    fold = body[body.index('<summary>Used golfers (2)</summary>'):]
    fold = fold[:fold.index('</details>')]
    # Newest first, like the weeks above it.
    assert fold.index('Wk 12') < fold.index('Test Charlie') < fold.index('Wk 11') < fold.index('Test Alpha')
    assert 'Withdrew' not in fold                               # he went back to the pool


def test_commissioners_ledger_counts_revealed_weeks_and_marks_this_card(app, client, season, tuesday):
    viewer, rival, g, weeks = _two_weeks_and_the_masters(season)
    assert 'The Commish has not set a pick by hand this season.' in _body(client, viewer)

    for pick in GolfPick.query.filter_by(user_id=viewer.id):
        pick.admin_override = True
    GolfPick.query.filter_by(user_id=rival.id).one().admin_override = True
    db.session.commit()
    _pick(rival, weeks['masters'], g['Hotgolfer'], g['Coldgolfer'], admin_override=True)

    body = _body(client, rival)
    ledger = body[body.index('id="golf-ledger-label"'):body.index('class="golf-foot"')]
    rows = re.findall(r'<li>(.*?)</li>', ledger, re.S)
    assert len(rows) == 2
    assert 'ViewerLine' in rows[0] and '>2<' in rows[0]
    assert all('golf-sheet-avatar' in row for row in rows)      # the member's mark stays
    assert f'href="/golf/member/{viewer.id}"' in rows[0]
    assert 'RivalLine' in rows[1] and 'this scorecard' in rows[1] and '>1<' in rows[1]


# ============================================================================
# Seasons
# ============================================================================

def test_scorecard_reads_one_season(app, client, season, tuesday):
    """A member with a line in two seasons: each card shows its own weeks, its
    own golfers and its own total, and offers the other."""
    viewer, rival, g, weeks = _two_weeks_and_the_masters(season)
    db.session.add(GolfEnrollment(user_id=viewer.id, season_year=season - 1, total_points=77_000))
    db.session.commit()
    old = _golfer('Oldgolfer')
    last_year = GolfTournament(
        api_tourn_id='LY-1', name='Last Year Open', season_year=season - 1,
        start_date=datetime(2025, 3, 6), end_date=datetime(2025, 3, 9),
        pick_deadline=datetime(2025, 3, 6, 7), purse=1, status='complete',
        results_finalized=True, week_number=9,
    )
    db.session.add(last_year)
    db.session.commit()
    _result(last_year, old, position='3', earnings=77_000)
    _banked(viewer, last_year, old, g['Spare'], 77_000)
    _login(client, viewer)

    now = _body(client, viewer)
    assert 'Last Year Open' not in now and 'Oldgolfer' not in now
    assert _tile(now, 'Golfers used') == '2'
    assert f'href="/golf/member/{viewer.id}?season={season - 1}">{season - 1} scorecard</a>' in now

    then = _body(client, viewer, season=season - 1)
    assert 'Valspar Championship' not in then and 'Alpha' not in then
    assert 'golf-hero-figure--banked">$77,000' in then
    assert '<strong>1st</strong> of 1' in then
    assert _tile(then, 'Golfers used') == '1'
    assert f'href="/golf/member/{viewer.id}">{season} scorecard</a>' in then
    assert '/golf/pick/' not in then                            # a past season takes no pick
    assert f'name="season" value="{season - 1}"' in then        # the switcher stays in it

    assert 'scorecard</a>' not in _body(client, rival)          # one season: no selector


# ============================================================================
# No query per week, no query per member
# ============================================================================

def test_scorecard_query_count_does_not_grow_with_weeks_or_members(app, client, season, tuesday):
    viewer, rival, g, weeks = _two_weeks_and_the_masters(season)
    _login(client, viewer)
    viewer_id, spare_id = viewer.id, g['Spare'].id

    # Warm the before_request status refresh so both measured requests skip it.
    assert _get(client, viewer).status_code == 200
    db.session.remove()
    with _count_sql() as small:
        assert client.get(f'/golf/member/{viewer_id}').status_code == 200

    spare = db.session.get(GolfPlayer, spare_id)
    members = [db.session.get(User, viewer_id)] + [_member(season, f'extra{i}') for i in range(4)]
    for week in range(1, 9):
        banked = _week(season, f'Early Week {week}', week, datetime(2026, 1, 1 + week))
        golfer = _golfer(f'Early{week}')
        _result(banked, golfer, position=str(week), earnings=10_000 * week)
        for member in members:
            _pick(member, banked, golfer, spare, active_player_id=golfer.id,
                  points_earned=10_000 * week, primary_used=True, admin_override=week % 2 == 0)
        db.session.add(GolfSeasonPlayerUsage(
            user_id=viewer_id, player_id=golfer.id, season_year=season))
    db.session.commit()
    db.session.remove()
    with _count_sql() as large:
        assert client.get(f'/golf/member/{viewer_id}').status_code == 200

    assert large['n'] == small['n'], (
        f"the scorecard issues a query per week or member: {small['n']} -> {large['n']} "
        f'as the season went 2 -> 10 banked weeks and the room 2 -> 6'
    )


# ============================================================================
# The ways in
# ============================================================================

def _nav(client, path):
    body = client.get(path).get_data(as_text=True)
    return body[body.index('subnav-golf'):body.index('</nav>', body.index('subnav-golf'))]


def test_sub_nav_carries_stats_for_everyone(app, client, season, tuesday):
    _two_weeks_and_the_masters(season)
    nav = _nav(client, '/golf/')
    assert 'href="/golf/stats">Stats</a>' in nav
    assert 'My Scorecard' not in nav


def test_sub_nav_offers_no_scorecard_to_a_viewer_with_no_line(app, client, season, tuesday):
    _two_weeks_and_the_masters(season)
    outsider = User(username='no_line', email='no_line@test.com')
    outsider.set_password('pw')
    db.session.add(outsider)
    db.session.commit()
    _login(client, outsider)

    assert 'My Scorecard' not in _nav(client, '/golf/')


def test_sub_nav_scorecard_pill_is_the_members_own(app, client, season, tuesday):
    viewer, rival, *_ = _two_weeks_and_the_masters(season)
    _login(client, viewer)

    pill = r'class="subnav-pill %s"\s+href="/golf/member/%d">My Scorecard'
    assert re.search(pill % ('active', viewer.id), _nav(client, f'/golf/member/{viewer.id}'))
    assert re.search(pill % ('', viewer.id), _nav(client, f'/golf/member/{rival.id}'))


def test_sheet_and_board_names_link_to_scorecards(app, client, season, tuesday):
    viewer, rival, g, weeks = _two_weeks_and_the_masters(season)

    sheet = client.get('/golf/').get_data(as_text=True)
    assert f'<a class="golf-quiet" href="/golf/member/{viewer.id}">ViewerLine</a>' in sheet
    board = client.get(f'/golf/tournament/{weeks["valspar"].id}').get_data(as_text=True)
    assert f'<a class="golf-quiet" href="/golf/member/{rival.id}">RivalLine</a>' in board


# ============================================================================
# Template source: the season surfaces are built on the sheet's primitives
# ============================================================================

@pytest.mark.parametrize('name', ['member_scorecard.html', 'record_room.html'])
def test_season_templates_carry_no_pre_u_markup(name):
    source = (TEMPLATES / name).read_text()
    for retired in ('table-golf', 'row-leader', 'col-divider', 'page-hero', 'stat-block',
                    'stat-value', 'row-current-user', 'loop.index', 'badge bg-', 'bi bi-',
                    'text-gold', 'text-muted', 'form-select', 'form-control', 'cdn.', '//'):
        assert retired not in source, f'{name} still carries {retired!r}'
    assert not re.search(r'class="(?:[^"]* )?card(?:-[a-z-]+)?[ "]', source)
    # The only inline styles are the positions and shares the server computed.
    assert all(style.startswith('--') for style in re.findall(r'style="([^"]*)"', source))
    assert not re.search(r'eyebrow', source)
    # Copy discipline: no em dashes or double hyphens in the room's copy.
    assert '—' not in source and ' -- ' not in source


def test_my_picks_template_is_gone():
    assert not (TEMPLATES / 'my_picks.html').exists()
