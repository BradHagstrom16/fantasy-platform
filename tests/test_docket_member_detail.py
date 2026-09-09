"""The per-member season page (/docket/ledger/<enrollment_id>).

Brad, 2026-09-09: a line on the ledger opens onto that member's whole season
on its own page, the World Cup rosters→player-detail pattern. The season
table's drawer stays for the in-place peek; this page lays the record open.
Graded weeks only (pick_history), so nothing sealed appears.
"""
from datetime import datetime

from extensions import db
from games.docket.models import DocketPick, DocketWeekResult
from games.docket.services.enrollment import get_enrollment
from tests._docket_fixtures import (
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

GRADED_AT = datetime(2026, 9, 6, 4, 0)
KICK_THU = datetime(2026, 9, 4, 0, 15)


def _member(name, **kwargs):
    user = make_user(name)
    make_enrollment(user, **kwargs)
    return user


def _week(week_number, default_error_tenths=0):
    week = make_week(week_number)
    week.default_error_tenths = default_error_tenths
    db.session.flush()
    return week


def _result(week, user, points, wins, error_tenths=0):
    db.session.add(DocketWeekResult(
        user_id=user.id, week_id=week.id, points=points, wins=wins,
        error_tenths=error_tenths, graded_at=GRADED_AT))


def test_member_page_requires_enrollment(app, client):
    outsider = make_user('outsider')
    db.session.commit()
    login(client, outsider)
    resp = client.get('/docket/ledger/1')
    assert resp.status_code == 302
    assert '/docket/join' in resp.headers['Location']


def test_member_page_404s_on_a_bad_id(app, client):
    viewer = _member('viewer')
    db.session.commit()
    login(client, viewer)
    assert client.get('/docket/ledger/999999').status_code == 404


def test_member_page_states_the_record_and_the_drop(app, client):
    w1, w2 = _week(1), _week(2)
    alice = _member('alice')
    _result(w1, alice, 9.0, 9, error_tenths=20)
    _result(w2, alice, 4.0, 4, error_tenths=35)      # struck (lower points)
    viewer = _member('viewer')
    db.session.commit()
    login(client, viewer)

    enrollment = get_enrollment(alice.id)
    html = client.get(f'/docket/ledger/{enrollment.id}').data.decode()
    assert 'alice' in html
    assert 'The weekly record' in html
    assert 'W1' in html and 'W2' in html
    # points after the drop (9.0), wins never dropped (13), error never dropped
    assert '9.0 points' in html
    assert '13 wins' in html
    assert 'struck from the record' in html
    # the back way out
    assert '/docket/ledger"' in html


def test_member_page_opens_onto_the_graded_sheet(app, client):
    week = _week(1)
    alice = _member('alice')
    game = make_game(week, kickoff=KICK_THU, home='Utah Utes',
                     away='Idaho Vandals', home_spread=-3.5)
    game.home_score, game.away_score, game.is_final = 31, 17, True
    db.session.add(DocketPick(
        user_id=alice.id, week_id=week.id, game_id=game.id, market='spread',
        side='home', slot=1, line_value=-3.5, book='draftkings'))
    _result(week, alice, 1.0, 1)
    viewer = _member('viewer')
    db.session.commit()
    login(client, viewer)

    enrollment = get_enrollment(alice.id)
    html = client.get(f'/docket/ledger/{enrollment.id}').data.decode()
    assert 'docket-week-sheet' in html
    assert 'Utah Utes -3.5' in html
    assert 'Idaho Vandals at Utah Utes' in html


def test_member_page_before_any_grade_states_the_absence(app, client):
    alice = _member('alice')
    viewer = _member('viewer')
    db.session.commit()
    login(client, viewer)
    enrollment = get_enrollment(alice.id)
    html = client.get(f'/docket/ledger/{enrollment.id}').data.decode()
    assert 'Nothing graded yet' in html
