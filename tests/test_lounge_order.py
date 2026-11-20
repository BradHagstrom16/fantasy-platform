"""The member's own lounge order (`User.lounge_order`).

A member sets it on /profile (POST /profile/lounge-order, one place up or
down); `games.registry.in_member_order` applies it to the lounge's
headliners and to the games menu. Unset keeps registry order. Clocks are
pinned to the pre-season, where both headliners are on every bill.
"""
import os
from types import SimpleNamespace
from unittest.mock import patch

from flask import url_for

from extensions import db
from games.cfb.models import CfbEnrollment
from games.docket.services import enrollment as docket_enrollment
from games.registry import in_member_order, lounge_games
from models.user import User

DUAL_PRE = {'ENVIRONMENT': 'testing',
            'CFB_FAKE_NOW': '2026-08-18T17:00:00',
            'DOCKET_FAKE_NOW': '2026-08-18T17:00:00'}
WINDOW_CLOSED = {'ENVIRONMENT': 'testing',
                 'CFB_FAKE_NOW': '2026-09-06T00:00:00',
                 'DOCKET_FAKE_NOW': '2026-09-06T00:00:00'}


def _member(username, *, cfb=True, docket=True, lounge_order=None):
    user = User(username=username, email=f'{username}@test.com',
                lounge_order=lounge_order)
    user.set_password('pw')
    db.session.add(user)
    db.session.commit()
    if cfb:
        db.session.add(CfbEnrollment(user_id=user.id, season_year=2026))
        db.session.commit()
    if docket:
        docket_enrollment.admin_enroll(user.id)
    return user


def _login(client, app, **kwargs):
    with app.app_context():
        user = _member(**kwargs)
        auth_id, user_id = user.auth_id, user.id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    return user_id


def _saved(app, user_id):
    with app.app_context():
        return db.session.get(User, user_id).lounge_order


# == the sort ===============================================================

def _viewer(order):
    return SimpleNamespace(is_authenticated=True, lounge_order=order)


def test_in_member_order_cases(app):
    with app.app_context():
        bill = lounge_games()
        slugs = lambda entries: [e.slug for e in entries]  # noqa: E731
        assert slugs(bill) == ['cfb', 'docket']
        assert slugs(in_member_order(bill, _viewer(None))) == ['cfb', 'docket']
        assert slugs(in_member_order(bill, _viewer('docket,cfb'))) == ['docket', 'cfb']
        # Partial: the unplaced game follows in registry order.
        assert slugs(in_member_order(bill, _viewer('docket'))) == ['docket', 'cfb']
        # A slug no longer on the bill is skipped; a repeat counts once.
        assert slugs(in_member_order(bill, _viewer('golf,docket,docket'))) == ['docket', 'cfb']
        # Anonymous viewers never read a saved order.
        anon = SimpleNamespace(is_authenticated=False, lounge_order='docket,cfb')
        assert slugs(in_member_order(bill, anon)) == ['cfb', 'docket']


# == the lounge and the menu ================================================

def test_lounge_default_order_is_registry_order(app, client):
    _login(client, app, username='defaultorder')
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    assert text.index('hl-panel--cfb') < text.index('hl-panel--docket')


def test_saved_order_leads_the_lounge_tiles_and_menu(app, client):
    _login(client, app, username='docketfirst', lounge_order='docket,cfb')
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/').get_data(as_text=True)
    assert text.index('hl-panel--docket') < text.index('hl-panel--cfb')
    with app.test_request_context():
        cfb_href = f'href="{url_for("cfb.index")}"'
        docket_href = f'href="{url_for("docket.index")}"'
    # The games menu (navbar switcher) follows the same order.
    menu = text[text.index('id="navbarNav"'):]
    assert menu.index(docket_href) < menu.index(cfb_href)


# == the profile control ====================================================

def test_profile_lists_the_bill_in_order(app, client):
    _login(client, app, username='profilelist', lounge_order='docket,cfb')
    with patch.dict(os.environ, DUAL_PRE):
        text = client.get('/profile').get_data(as_text=True)
    assert 'Lounge order' in text
    assert text.index('data-slug="docket"') < text.index('data-slug="cfb"')
    assert 'aria-label="Move Docket up" disabled' in text
    assert 'aria-label="Move Survivor down" disabled' in text


def test_profile_hides_the_control_with_one_game(app, client):
    _login(client, app, username='onegame', docket=False)
    with patch.dict(os.environ, WINDOW_CLOSED):
        text = client.get('/profile').get_data(as_text=True)
    assert 'Lounge order' not in text


def test_move_up_and_down_store_the_whole_bill(app, client):
    user_id = _login(client, app, username='mover')
    with patch.dict(os.environ, DUAL_PRE):
        resp = client.post('/profile/lounge-order',
                           data={'slug': 'docket', 'direction': 'up'})
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/profile')
        assert _saved(app, user_id) == 'docket,cfb'
        client.post('/profile/lounge-order', data={'slug': 'docket', 'direction': 'down'})
        assert _saved(app, user_id) == 'cfb,docket'


def test_move_past_the_end_writes_nothing(app, client):
    user_id = _login(client, app, username='edgemove')
    with patch.dict(os.environ, DUAL_PRE):
        client.post('/profile/lounge-order', data={'slug': 'cfb', 'direction': 'up'})
    assert _saved(app, user_id) is None


def test_bad_slug_or_direction_writes_nothing(app, client):
    user_id = _login(client, app, username='badmove')
    with patch.dict(os.environ, DUAL_PRE):
        for data in ({'slug': 'golf', 'direction': 'up'},
                     {'slug': 'docket', 'direction': 'sideways'},
                     {'direction': 'up'}):
            resp = client.post('/profile/lounge-order', data=data)
            assert resp.status_code == 302
    assert _saved(app, user_id) is None


def test_lounge_order_is_post_only_and_members_only(app, client):
    assert client.post('/profile/lounge-order',
                       data={'slug': 'docket', 'direction': 'up'}).status_code == 302
    _login(client, app, username='getter')
    assert client.get('/profile/lounge-order').status_code == 405
