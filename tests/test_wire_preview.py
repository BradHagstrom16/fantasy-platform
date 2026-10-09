"""The Wire's live preview (ADR-074, PR B): the one push a member would get
next, as `/app` paints it before they turn The Wire on.

Locks:
  - each game's ``wire_preview`` seam: a member who owes a pick sees the
    reminder they would get (the sender's own ``nag_push_copy``), a member
    holding a pick sees the verdict shape over their own team or side,
    and everyone the game has nothing to promise (not enrolled, eliminated,
    off-season, the pick graded, every side final) gets None
  - ``games.registry.wire_preview_for`` takes the first game in billing
    order with something to promise
  - `/app` reads it only through the registry (the import lock lives in
    tests/test_wire_distribution.py), paints it in three panels, and falls
    to the real test dispatch when no game has a promise
"""
import html
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from extensions import db
from games import registry
from games.cfb.services.reminders import nag_push_copy as cfb_nag_copy
from games.cfb.services.wire_preview import wire_preview as cfb_preview
from games.cfb.utils import make_aware
from games.docket.models import DocketPick
from games.docket.services.picks import sheet_state
from games.docket.services.reminders import nag_push_copy as docket_nag_copy
from games.docket.services.wire_preview import wire_preview as docket_preview
from tests import _cfb_fixtures as cfb
from tests._docket_fixtures import (
    IN_WEEK1,
    at,
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)
from tests.test_docket_sheet_flow import (
    KICK_SAT,
    _file_eight_with_x2_and_number,
    _final,
)
from utils.push import TEST_BODY, TEST_TITLE

CFB_DEADLINE = datetime(2026, 9, 5, 11, 0)          # Sat 11:00 CT, Week 1
TUESDAY = datetime(2026, 9, 1, 17, 0, tzinfo=UTC)   # the week just opened
SATURDAY_9 = datetime(2026, 9, 5, 14, 0, tzinfo=UTC)   # Sat 9:00 CT, final window
WEDNESDAY = datetime(2026, 9, 2, 18, 0, tzinfo=UTC)    # Docket Week 1, sheet open
JUNE = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


# ── Survivor ─────────────────────────────────────────────────────────────

def _survivor(*, enrolled=True, eliminated=False, pick=False, active=True,
              graded=None):
    week = cfb.make_week(1, deadline=CFB_DEADLINE, is_active=active)
    navy, dog = cfb.make_team('Navy'), cfb.make_team('South Carolina')
    cfb.make_game(week, navy, dog, spread=-7.0)
    user = cfb.make_user('previewer')
    if enrolled:
        cfb.make_enrollment(user, eliminated=eliminated)
    if pick:
        cfb.make_pick(user, week, navy, is_correct=graded)
    db.session.commit()
    return user, week


def test_cfb_owing_member_sees_the_warning_they_would_get(app):
    user, week = _survivor()
    preview = cfb_preview(user.id, TUESDAY)
    title, body = cfb_nag_copy(week, 'warning', make_aware(week.deadline), TUESDAY)
    assert preview == {'title': title, 'body': body,
                       'when': 'Saturday, Sep 5 · 11:00 AM CT'}
    assert title == 'CFB pick due Sat 11 AM CT'


def test_cfb_owing_member_inside_the_final_window_sees_the_final(app):
    user, week = _survivor()
    preview = cfb_preview(user.id, SATURDAY_9)
    assert preview['title'] == 'CFB pick locks in 2 hrs'
    assert preview['body'].startswith('No pick for Week 1.')


def test_cfb_after_the_warning_window_the_final_reads_as_it_will_be_sent(app):
    # Friday noon: the warning is behind, so the final leads, timed at its
    # own window's open (T-2h35m), never "locks in 23 hrs".
    user, _week = _survivor()
    friday_noon = datetime(2026, 9, 4, 17, 0, tzinfo=UTC)
    assert cfb_preview(user.id, friday_noon)['title'] == 'CFB pick locks in 2 hrs 30 min'


def test_cfb_member_with_a_pick_sees_the_verdict_shape_over_their_team(app):
    user, _week = _survivor(pick=True)
    assert cfb_preview(user.id, TUESDAY) == {
        'title': 'Navy won.', 'body': 'You survive.',
        'when': 'When Navy goes final'}
    # The promise holds past the deadline until the game is graded.
    assert cfb_preview(user.id, SATURDAY_9 + timedelta(hours=3))['title'] == 'Navy won.'


def test_cfb_nothing_to_promise(app):
    assert cfb_preview(_survivor(enrolled=False)[0].id, TUESDAY) is None


def test_cfb_eliminated_member_gets_none(app):
    assert cfb_preview(_survivor(eliminated=True)[0].id, TUESDAY) is None


def test_cfb_off_season_gets_none(app):
    assert cfb_preview(_survivor(active=False)[0].id, TUESDAY) is None


def test_cfb_graded_pick_gets_none(app):
    user, _week = _survivor(pick=True, graded=True)
    assert cfb_preview(user.id, SATURDAY_9) is None


def test_cfb_no_pick_after_the_deadline_gets_none(app):
    user, _week = _survivor()
    assert cfb_preview(user.id, SATURDAY_9 + timedelta(hours=3)) is None


# ── The Docket ───────────────────────────────────────────────────────────

def _docket(monkeypatch, client, *, enrolled=True):
    user = make_user('docketpreview')
    if enrolled:
        make_enrollment(user)
    db.session.commit()
    login(client, user)
    week = make_week(1)
    games = [make_game(week, kickoff=KICK_SAT, home=f'Home {i}', away=f'Away {i}')
             for i in range(8)]
    week.tiebreaker_game_id = games[7].id
    db.session.commit()
    at(monkeypatch, IN_WEEK1)
    return user, week, games


def test_docket_short_sheet_sees_the_48h_nag_as_it_will_be_sent(monkeypatch, app, client):
    user, week, _games = _docket(monkeypatch, client)
    preview = docket_preview(user.id, WEDNESDAY)
    send_at = week.deadline_at - timedelta(hours=48)
    state = sheet_state(user.id, week, now=send_at)
    title, body = docket_nag_copy(week, '48h', state, send_at)
    assert preview == {'title': title, 'body': body,
                       'when': 'Sunday, Sep 6 · 12:00 PM CT'}
    assert (title, body) == ('Docket closes Sun 12 PM CT', 'Week 1: no sides picked yet.')


def test_docket_last_call_reads_from_the_tier_instant(monkeypatch, app, client):
    user, week, _games = _docket(monkeypatch, client)
    sunday_11 = datetime(2026, 9, 6, 16, 0, tzinfo=UTC)   # 11:00 CT, inside 2h
    preview = docket_preview(user.id, sunday_11)
    assert preview['title'] == 'Docket closes in 1 hr'
    assert preview['body'] == 'Last call for Week 1. No sides picked yet.'


def test_docket_filed_sheet_sees_its_next_unsettled_side(monkeypatch, app, client):
    user, week, games = _docket(monkeypatch, client)
    _file_eight_with_x2_and_number(client, week, games)
    preview = docket_preview(user.id, WEDNESDAY)
    assert preview == {'title': 'WIN: Home 0 -3.5',
                       'body': 'Away 0 at Home 0. Only your sheet had them.',
                       'when': 'When Away 0 at Home 0 goes final'}
    # A final side steps aside for the next one; once every side is final
    # there is nothing left to promise.
    _final(games[0], home=30, away=20)
    db.session.commit()
    assert docket_preview(user.id, WEDNESDAY)['title'] == 'WIN: Home 1 -3.5'
    for game in games[1:]:
        _final(game, home=30, away=20)
    db.session.commit()
    assert docket_preview(user.id, WEDNESDAY) is None


def test_docket_shared_side_counts_the_other_sheets(monkeypatch, app, client):
    user, week, games = _docket(monkeypatch, client)
    _file_eight_with_x2_and_number(client, week, games)
    other = make_user('otherpreview')
    make_enrollment(other)
    # The same side on another scoring sheet, and on a reserve (slot 9),
    # which never counts.
    for member, slot in ((other, 1), (make_user('reserver'), 9)):
        db.session.add(DocketPick(
            user_id=member.id, week_id=week.id, game_id=games[0].id,
            market='spread', side='home', slot=slot, line_value=-3.5,
            book='draftkings'))
    db.session.commit()
    assert docket_preview(user.id, WEDNESDAY)['body'] == (
        'Away 0 at Home 0. 1 other sheet had them.')


def test_docket_nothing_to_promise(monkeypatch, app, client):
    user, _week, _games = _docket(monkeypatch, client, enrolled=False)
    assert docket_preview(user.id, WEDNESDAY) is None


def test_docket_off_season_gets_none(monkeypatch, app, client):
    user, _week, _games = _docket(monkeypatch, client)
    assert docket_preview(user.id, JUNE) is None


def test_docket_week_not_imported_gets_none(monkeypatch, app, client):
    user, _week, _games = _docket(monkeypatch, client)
    week_9 = datetime(2026, 10, 28, 18, 0, tzinfo=UTC)
    assert docket_preview(user.id, week_9) is None


# ── The registry seam and /app ───────────────────────────────────────────

def test_wire_preview_for_takes_the_first_billing_with_a_promise(monkeypatch):
    cfb_entry, docket_entry = registry.get_entry('cfb'), registry.get_entry('docket')
    quiet = replace(cfb_entry, wire_preview=lambda _u, _n: None)
    loud = replace(docket_entry, wire_preview=lambda _u, _n: {'title': 'docket'})
    monkeypatch.setattr(registry, 'GAMES', [quiet, loud])
    assert registry.wire_preview_for(1, TUESDAY) == {'title': 'docket'}
    monkeypatch.setattr(registry, 'GAMES',
                        [replace(cfb_entry, wire_preview=lambda _u, _n: {'title': 'cfb'}), loud])
    assert registry.wire_preview_for(1, TUESDAY) == {'title': 'cfb'}
    monkeypatch.setattr(registry, 'GAMES', [quiet, replace(docket_entry, wire_preview=None)])
    assert registry.wire_preview_for(1, TUESDAY) is None


def test_app_paints_the_test_dispatch_when_no_game_has_a_promise(app, client):
    user = make_user('idle')
    db.session.commit()
    login(client, user)
    body = html.unescape(client.get('/app').get_data(as_text=True))
    assert body.count('class="app-wire-screen"') == 3
    assert body.count(TEST_TITLE) == 6 and TEST_BODY in body   # 3 cards + 3 aria-labels


def test_app_paints_a_members_real_next_push(app, client):
    """The route reads the real clock, so the week's deadline sits two days
    ahead of whenever this runs."""
    pool_now = datetime.now(ZoneInfo('America/Chicago')).replace(tzinfo=None)
    week = cfb.make_week(1, deadline=pool_now + timedelta(days=2), is_active=True)
    navy, dog = cfb.make_team('Navy'), cfb.make_team('South Carolina')
    cfb.make_game(week, navy, dog, spread=-7.0)
    user = cfb.make_user('owing')
    cfb.make_enrollment(user)
    db.session.commit()
    login(client, user)
    body = client.get('/app').get_data(as_text=True)
    assert 'CFB pick due ' in body
    assert 'Week 1: no pick on file yet.' in body
    assert TEST_TITLE not in body


def test_app_anonymous_paints_no_preview(client):
    body = client.get('/app').get_data(as_text=True)
    assert 'app-wire-screen' not in body
