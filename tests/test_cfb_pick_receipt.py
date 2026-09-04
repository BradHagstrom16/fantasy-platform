"""The CFB Survivor pick receipt (Brad, 2026-09-04).

One Club Letter every time a member makes or changes their pick: the team
and its number, when it kicks off, when picks lock. A refused pick sends
nothing; a refused send never gates the pick.
"""
import os
from datetime import datetime
from unittest.mock import patch

from extensions import db
from games.cfb.models import CfbPick
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_team,
    make_user,
    make_week,
)

DEADLINE = datetime(2026, 9, 5, 11, 0)          # Sat 11:00 CT (naive pool clock)
FAR_NOW = {'ENVIRONMENT': 'testing', 'CFB_FAKE_NOW': '2026-09-01T17:00:00'}
SEND = 'games.cfb.services.receipts.send_platform_email'


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _seed():
    week = make_week(1, deadline=DEADLINE, is_active=True)
    navy, dog = make_team('Navy'), make_team('South Carolina')
    make_game(week, navy, dog, spread=-7.0)
    heavy, light = make_team('Ohio State'), make_team('Akron')
    make_game(week, heavy, light, spread=-24.0)     # over the 16.5 cap
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    return user, navy, dog, heavy


def _pick(client, team):
    return client.post('/cfb/pick/1', data={'team_id': team.id,
                                            'csrf_token': 'x'})


def test_a_new_pick_sends_the_receipt(client, app):
    user, navy, _dog, _heavy = _seed()
    _login(client, user)
    with patch.dict(os.environ, FAR_NOW), \
            patch(SEND, return_value=True) as send:
        resp = _pick(client, navy)
    assert resp.status_code == 302
    assert send.call_count == 1
    to_addr, subject, plain, html = send.call_args[0]
    assert to_addr == user.email
    assert subject == 'Your pick is in: CFB Survivor, Week 1'
    assert 'Your Week 1 pick: Navy -7.0' in plain
    assert 'Picks lock' in plain and 'Saturday, Sep 5' in plain
    assert '/cfb/pick/1' in plain
    assert 'Navy -7.0' in html


def test_a_changed_pick_says_so(client, app):
    user, navy, dog, _heavy = _seed()
    _login(client, user)
    with patch.dict(os.environ, FAR_NOW), \
            patch(SEND, return_value=True) as send:
        _pick(client, navy)
        _pick(client, dog)
    assert send.call_count == 2
    subject, plain = send.call_args[0][1], send.call_args[0][2]
    assert subject == 'Pick changed: CFB Survivor, Week 1'
    assert 'Your Week 1 pick: South Carolina +7.0' in plain


def test_resubmitting_the_same_team_sends_nothing(client, app):
    """The pick page's "Keep" posts the standing team again; nothing
    changed, so nothing mails (and never as "Pick changed")."""
    user, navy, _dog, _heavy = _seed()
    _login(client, user)
    with patch.dict(os.environ, FAR_NOW), \
            patch(SEND, return_value=True) as send:
        _pick(client, navy)
        _pick(client, navy)
    assert send.call_count == 1
    assert send.call_args[0][1] == 'Your pick is in: CFB Survivor, Week 1'


def test_a_refused_pick_sends_nothing(client, app):
    user, _navy, _dog, heavy = _seed()
    _login(client, user)
    with patch.dict(os.environ, FAR_NOW), \
            patch(SEND, return_value=True) as send:
        resp = _pick(client, heavy)
    assert resp.status_code == 302
    assert send.call_count == 0


def test_a_refused_send_never_gates_the_pick(client, app):
    user, navy, _dog, _heavy = _seed()
    _login(client, user)
    with patch.dict(os.environ, FAR_NOW), \
            patch(SEND, return_value=False) as send:
        resp = _pick(client, navy)
    assert send.call_count == 1
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/cfb/')
    assert CfbPick.query.filter_by(user_id=user.id).count() == 1
