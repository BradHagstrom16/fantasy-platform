"""The standings pick column reveals the latest LOCKED week, never a week
that has not locked yet — and since 2026-09-08 the whole room leads with it.

2026-09-07: cfb-setup activated Week 2 on Labor-Day Monday morning while
Week 1's last game (SMU @ Florida State) was still that night. Every room
surface read is_active, so standings flipped to Week 2 — whose deadline had
not passed — and hid every Week 1 pick behind "Hidden until deadline" with
a game still to play. Brad's ruling: the pick column shows the latest week
whose deadline has passed (the reveal week), with each pick's own state
(LOCKED = pending, VERDICT = survived / lost a life, DESIGN.md 4.1), while
the pick CTA and the countdown keep following the active week.

2026-09-08: half a split was worse than none (the hero said Week 2 above a
Week 1 table). The room now leads with the reveal week while it is
unfinished — hero eyebrow, a lead panel, My Picks — and the active week's
call rides below it as a second panel (``games/cfb/services/week_state.py``,
states open | locked | overlap | verdict | none).
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
MONDAY_KICKOFF = datetime(2026, 9, 7, 18, 30)  # SMU @ Florida State
SATURDAY_NIGHT = '2026-09-06T02:00:00'          # Sat 9 PM CT: W1 locked
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
    monday = make_game(week, fsu, smu, spread=-3.5,
                       winner='home' if monday_final else None)
    monday.game_time = MONDAY_KICKOFF
    loser = make_user('loser')
    make_enrollment(loser)
    make_pick(loser, week, georgia)
    waiter = make_user('waiter')
    make_enrollment(waiter)
    make_pick(waiter, week, fsu)
    db.session.commit()
    assert process_week_results(week.id)['success'] is True
    return week, {'georgia': georgia, 'fsu': fsu, 'smu': smu}


def _login(client, username):
    """Seed the session as ``username`` (auth_id, never str(id))."""
    from models.user import User
    user = db.session.scalar(db.select(User).filter_by(username=username))
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _week_2(teams, *, active=True):
    """Week 2 on the board: SMU @ Georgia, lines posted."""
    week2 = make_week(2, deadline=WEEK2_DEADLINE, is_active=active)
    make_game(week2, teams['smu'], teams['georgia'], spread=-2.5)
    db.session.commit()
    return week2


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


# ── 2026-09-08: the room leads with the reveal week ───────────────────────

def test_locked_week_leads_with_pending_matchups(app, client, monkeypatch):
    """Saturday night: Week 1 is locked with the Monday game still to play
    and nothing newer is open. The hero eyebrow and a lead panel say so —
    the game, its kickoff, the viewer's pick with its LOCKED chip — and
    there is no call to make a pick, because there is nothing to pick in."""
    _week_1()
    _login(client, 'waiter')
    monkeypatch.setenv('CFB_FAKE_NOW', SATURDAY_NIGHT)

    html = client.get('/cfb/').get_data(as_text=True)

    assert 'Week 1 · Locked · 1 game to go' in html
    assert 'cfb-week-lead' in html
    assert 'SMU at Florida State' in html
    assert 'Kickoff Monday, Sep 7 · 6:30 PM CT' in html
    assert 'Your pick' in html and 'Florida State' in html
    assert 'badge-pending' in html
    assert html.index('cfb-week-lead') < html.index('Active Players')
    assert 'Make Your Pick' not in html
    assert 'Picks lock' not in html


def test_overlap_orders_lead_panel_before_pick_call(app, client, monkeypatch):
    """Monday night with Week 2 open: the Week 1 lead panel first, then the
    Week 2 weekly call in full (crimson rule, status row, Make Your Pick),
    then the standings still on Week 1 with the note."""
    _, teams = _week_1()
    _week_2(teams)
    _login(client, 'waiter')
    monkeypatch.setenv('CFB_FAKE_NOW', MONDAY_NIGHT)

    html = client.get('/cfb/').get_data(as_text=True)

    assert 'Week 1 · Locked · 1 game to go' in html
    assert html.index('cfb-week-lead') < html.index('cfb-pick-cta')
    assert html.index('cfb-pick-cta') < html.index('Active Players')
    assert 'href="/cfb/pick/2"' in html and 'Make Your Pick' in html
    assert 'cfb-status-row' in html
    assert 'September 12' in html
    assert 'until Week 2 locks' in html
    assert 'W1 Pick' in html


def test_verdict_state_when_no_week_is_open(app, client, monkeypatch):
    """Tuesday, Week 1 complete, Week 2 on the board but not yet opened: the
    room leads with the viewer's verdict and says what comes next; no call,
    no lock line, because nothing is pickable yet."""
    _, teams = _week_1(monday_final=True)
    _week_2(teams, active=False)
    _login(client, 'waiter')                       # Florida State won
    monkeypatch.setenv('CFB_FAKE_NOW', TUESDAY)

    html = client.get('/cfb/').get_data(as_text=True)

    assert 'Week 1 · Final' in html
    assert 'Survived.' in html
    assert 'Florida State beat SMU' in html
    assert 'Week 2 opens with its lines.' in html
    assert 'Make Your Pick' not in html
    assert 'Picks lock' not in html


def test_verdict_lead_says_lost_a_life_for_the_loser(app, client, monkeypatch):
    _, teams = _week_1(monday_final=True)
    _login(client, 'loser')                        # Georgia fell to Clemson
    monkeypatch.setenv('CFB_FAKE_NOW', TUESDAY)

    html = client.get('/cfb/').get_data(as_text=True)

    assert 'Lost a life.' in html
    assert 'Georgia fell to Clemson' in html
    assert 'Week 2 is not on the board yet.' in html


def test_open_state_keeps_the_weekly_call_as_the_lead(app, client, monkeypatch):
    """Ordinary Tuesday afternoon: Week 1 complete, Week 2 open. No lead
    panel — the weekly call is the room's center of gravity, the hero keeps
    its identity eyebrow, and the table shows Week 1's verdicts with the note."""
    _, teams = _week_1(monday_final=True)
    _week_2(teams)
    _login(client, 'waiter')
    monkeypatch.setenv('CFB_FAKE_NOW', TUESDAY)

    html = client.get('/cfb/').get_data(as_text=True)

    assert 'cfb-week-lead' not in html
    assert 'Under the Lights' in html
    assert 'Make Your Pick' in html
    assert 'until Week 2 locks' in html


def test_my_picks_eyebrow_follows_the_lead_week(app, client, monkeypatch):
    """Monday night: Your Card is about Week 1 (pending), not the open
    Week 2, and the "This Week" chip sits on the Week 1 row."""
    _, teams = _week_1()
    week2 = _week_2(teams)
    from models.user import User
    waiter = db.session.scalar(db.select(User).filter_by(username='waiter'))
    make_pick(waiter, week2, teams['smu'])
    db.session.commit()
    _login(client, 'waiter')
    monkeypatch.setenv('CFB_FAKE_NOW', MONDAY_NIGHT)

    html = client.get('/cfb/my-picks').get_data(as_text=True)

    assert 'Your Card &middot; Week 1 &middot;' in html
    assert 'Week 1 &middot; Your Season' in html
    assert html.count('cfb-now-tag') == 1
    assert html.index('cfb-now-tag') < html.index('Week 2</strong>')
