"""The standings pick column reveals the latest LOCKED week, never a week
that has not locked yet.

2026-09-07: cfb-setup activated Week 2 on Labor-Day Monday morning while
Week 1's last game (SMU @ Florida State) was still that night. Every room
surface read is_active, so standings flipped to Week 2 — whose deadline had
not passed — and hid every Week 1 pick behind "Hidden until deadline" with
a game still to play. Brad's ruling: the pick column shows the latest week
whose deadline has passed (the reveal week), with each pick's own state
(LOCKED = pending, VERDICT = survived / lost a life, DESIGN.md 4.1), while
the pick CTA and the countdown keep following the active week.
"""
from datetime import datetime

from extensions import db
from games.cfb.services.game_logic import process_week_results
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)

WEEK1_DEADLINE = datetime(2026, 9, 5, 11, 0)   # naive pool wall clock
WEEK2_DEADLINE = datetime(2026, 9, 12, 11, 0)
MONDAY_NIGHT = '2026-09-07T22:00:00'            # Week 1's last game pending
TUESDAY = '2026-09-08T14:00:00'                 # Week 1 complete, Week 2 open
WEEK2_LOCKED = '2026-09-12T18:00:00'
PRESEASON = '2026-09-02T12:00:00'


def _week_1(*, monday_final=False):
    """Week 1 past its deadline: Clemson beat Georgia on Saturday; the
    Monday-night Florida State game is pending unless ``monday_final``."""
    week = make_week(1, deadline=WEEK1_DEADLINE)
    georgia, clemson = make_team('Georgia'), make_team('Clemson')
    fsu, smu = make_team('Florida State'), make_team('SMU')
    make_game(week, georgia, clemson, spread=-7.0, winner='away')
    make_game(week, fsu, smu, spread=-3.5,
              winner='home' if monday_final else None)
    loser = make_user('loser')
    make_enrollment(loser)
    make_pick(loser, week, georgia)
    waiter = make_user('waiter')
    make_enrollment(waiter)
    make_pick(waiter, week, fsu)
    db.session.commit()
    assert process_week_results(week.id)['success'] is True
    return week, {'georgia': georgia, 'fsu': fsu, 'smu': smu}


def test_monday_night_week_stays_on_the_board_after_the_flip(
        app, client, monkeypatch):
    _week_1()
    make_week(2, deadline=WEEK2_DEADLINE, is_active=True)
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', MONDAY_NIGHT)

    html = client.get('/cfb/').get_data(as_text=True)

    assert 'Hidden until deadline' not in html
    assert 'W1 Pick' in html
    assert 'Georgia' in html and 'badge-lost-life' in html
    assert 'Florida State' in html and 'badge-pending' in html
    assert 'until Week 2 locks' in html
    # the pick call and its countdown still follow the active week
    assert 'September 12' in html


def test_completed_week_shows_verdicts_until_the_next_week_locks(
        app, client, monkeypatch):
    _week_1(monday_final=True)
    make_week(2, deadline=WEEK2_DEADLINE, is_active=True)
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', TUESDAY)

    html = client.get('/cfb/').get_data(as_text=True)

    assert 'W1 Pick' in html
    assert 'badge-survived' in html and 'badge-lost-life' in html
    assert 'badge-pending' not in html
    assert 'until Week 2 locks' in html


def test_next_week_takes_the_board_at_its_own_deadline(
        app, client, monkeypatch):
    week1, teams = _week_1(monday_final=True)
    week2 = make_week(2, deadline=WEEK2_DEADLINE, is_active=True)
    make_game(week2, teams['smu'], teams['georgia'], spread=-2.5)
    waiter = db.session.scalar(
        db.select(db.Model.registry._class_registry['User'])
        .filter_by(username='waiter'))
    make_pick(waiter, week2, teams['smu'])
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_LOCKED)

    html = client.get('/cfb/').get_data(as_text=True)

    assert 'W2 Pick' in html and 'W1 Pick' not in html
    assert 'SMU' in html and 'badge-pending' in html
    assert 'until Week 2 locks' not in html


def test_nothing_locked_yet_keeps_the_picks_hidden(app, client, monkeypatch):
    """Before the first deadline there is no reveal week: the column keeps
    the active week's header and the hidden-until-deadline copy."""
    week = make_week(1, deadline=WEEK1_DEADLINE, is_active=True)
    make_game(week, make_team('Georgia'), make_team('Clemson'), spread=-7.0)
    user = make_user('early')
    make_enrollment(user)
    db.session.commit()
    monkeypatch.setenv('CFB_FAKE_NOW', PRESEASON)

    html = client.get('/cfb/').get_data(as_text=True)

    assert 'W1 Pick' in html
    assert 'Hidden until deadline' in html
    assert 'badge-pending' not in html
