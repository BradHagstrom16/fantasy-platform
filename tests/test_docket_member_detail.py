"""The per-member season page (/docket/ledger/<enrollment_id>).

Brad, 2026-09-09: a line on the ledger opens onto that member's whole season
on its own page, the World Cup rosters→player-detail pattern. The season
table's drawer stays for the in-place peek; this page lays the record open.
Graded weeks only (pick_history), so nothing sealed appears.
"""
import re
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
    # the per-week prize receipt rides the member page now (moved off the
    # ledger board, 2026-09-09): alice took both weeks she was alone in.
    assert 'docket-week-verdict' in html
    # the back way out
    assert '/docket/ledger"' in html


def test_member_page_states_a_no_sheet_charge(app, client):
    """The late-joiner rule made visible on the member page (moved off the
    ledger board, 2026-09-09): 0 points and the week's default error, said
    out loud so it does not read as a bug."""
    week = _week(1, default_error_tenths=180)
    ghost = _member('ghost')
    _result(week, _member('bob'), 6.0, 6)         # someone graded the week
    viewer = _member('viewer')
    db.session.commit()
    login(client, viewer)

    enrollment = get_enrollment(ghost.id)
    html = client.get(f'/docket/ledger/{enrollment.id}').data.decode()
    assert 'no sheet filed, charged 18.0' in html


def test_member_page_explains_the_drop_before_it_applies(app, client):
    """The drop explanation moved off the ledger board onto the member page's
    standing sentence (Brad, 2026-09-09)."""
    week = _week(1)
    alice = _member('alice')
    _result(week, alice, 6.0, 6)
    viewer = _member('viewer')
    db.session.commit()
    login(client, viewer)

    enrollment = get_enrollment(alice.id)
    html = client.get(f'/docket/ledger/{enrollment.id}').data.decode()
    assert 'the drop begins once a second week grades' in html


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


def _standing_sentence(client, user):
    html = client.get(f'/docket/ledger/{get_enrollment(user.id).id}').data.decode()
    body = html.split('class="docket-your-standing"', 1)[1].split('</p>', 1)[0]
    return ' '.join(re.sub(r'<[^>]+>', '', body.split('>', 1)[1]).split())


def test_member_page_says_a_level_pair_below_the_lead_honestly(app, client):
    """Level on points but split by wins, away from the leader, reads as a
    tie from both sides, and a shared rank says the same of the line below
    it rather than "0.0 ahead"."""
    w1 = _week(1)
    lee, ann, bob, cy, dee, fay, eve = (
        _member(n) for n in ('lee', 'ann', 'bob', 'cy', 'dee', 'fay', 'eve'))
    _result(w1, lee, 10.0, 7)
    _result(w1, ann, 8.0, 6)          # 2nd: level with bob, ahead on wins
    _result(w1, bob, 8.0, 5)          # 3rd: level with ann, behind on wins
    _result(w1, cy, 5.0, 4, 10)       # 4th, tied with dee on every key,
    _result(w1, dee, 5.0, 4, 10)      # and level on points with fay
    _result(w1, fay, 5.0, 3)
    _result(w1, eve, 2.0, 1)
    db.session.commit()
    login(client, lee)

    assert _standing_sentence(client, ann).startswith(
        'Sits 2nd of 7, 2.0 behind the leader and level on points with bob, ahead on wins.')
    assert _standing_sentence(client, bob).startswith(
        'Sits 3rd of 7, 2.0 behind the leader and level on points with ann, behind on wins.')
    assert _standing_sentence(client, cy).startswith(
        'Sits 4th of 7, tied with dee, 5.0 behind the leader and level on points with fay, ahead on wins.')


def test_member_page_says_a_shared_rank_honestly(app, client):
    """A shared rank names its partner, is split from the leader by the key
    that actually splits it, and measures the gap to the first line ranked
    below it."""
    w1 = _week(1)
    lee, ann, bob, cy, dee, eve = (_member(n) for n in ('lee', 'ann', 'bob', 'cy', 'dee', 'eve'))
    _result(w1, lee, 10.0, 7)
    _result(w1, ann, 10.0, 5)         # 2nd with bob, level with lee on points
    _result(w1, bob, 10.0, 5)
    _result(w1, cy, 6.0, 4, 10)       # 4th with dee
    _result(w1, dee, 6.0, 4, 10)
    _result(w1, eve, 3.0, 1)
    db.session.commit()
    login(client, lee)

    assert _standing_sentence(client, ann).startswith(
        'Sits 2nd of 6, tied with bob, level on points with the leader and behind on wins.')
    assert _standing_sentence(client, cy).startswith(
        'Sits 4th of 6, tied with dee, 4.0 behind the leader and 3.0 ahead of the next line.')
