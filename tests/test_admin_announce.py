"""Tests for the platform-admin announce (mass email) tool."""
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import WorldCupEnrollment
from games.cfb.models import CfbEnrollment
from games.golf.models import GolfEnrollment
from games.worldcup.constants import SEASON_YEAR


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _make_user(app, username='u1', is_admin=False):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com', is_admin=is_admin)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(client, user_id):
    auth_id = db.session.get(User, user_id).auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


def _enroll_wc(user_id, picks_submitted=True, season=SEASON_YEAR):
    e = WorldCupEnrollment(
        user_id=user_id, season_year=season, picks_submitted=picks_submitted,
    )
    db.session.add(e)
    db.session.commit()
    return e


def _enroll_cfb(user_id, eliminated=False, season=2026):
    e = CfbEnrollment(
        user_id=user_id, season_year=season, is_eliminated=eliminated,
    )
    db.session.add(e)
    db.session.commit()
    return e


def _enroll_golf(user_id, season=2026):
    e = GolfEnrollment(user_id=user_id, season_year=season)
    db.session.add(e)
    db.session.commit()
    return e


def _compose(action='preview', audience='worldcup', recipient_filter='all',
             subject='Big news', body_text='Hello everyone.'):
    return {
        'action': action,
        'audience': audience,
        'recipient_filter': recipient_filter,
        'subject': subject,
        'body_text': body_text,
        'csrf_token': 'x',
    }


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def test_announce_redirects_anonymous(client):
    resp = client.get('/admin/announce', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.location


def test_announce_redirects_non_admin(app, client):
    uid = _make_user(app, 'regular')
    _login(client, uid)
    resp = client.get('/admin/announce', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.location.endswith('/')


# ---------------------------------------------------------------------------
# GET — fresh compose form
# ---------------------------------------------------------------------------

def test_announce_get_renders_form(app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)
    resp = client.get('/admin/announce')
    assert resp.status_code == 200
    data = resp.data.decode()
    for slug in ('worldcup', 'cfb', 'golf', 'all'):
        assert f'value="{slug}"' in data
    assert 'name="subject"' in data
    assert 'name="body_text"' in data
    assert 'value="preview"' in data


def test_announce_get_has_no_send_buttons(app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)
    data = client.get('/admin/announce').data.decode()
    assert 'value="send"' not in data
    assert 'value="test"' not in data


# ---------------------------------------------------------------------------
# resolve_recipients — unit tests
# ---------------------------------------------------------------------------

def test_resolve_worldcup_active_filters_picks_submitted(app):
    with app.app_context():
        from core.admin.announce import resolve_recipients
        u1 = _make_user_inline('locked')
        u2 = _make_user_inline('drafting')
        _enroll_wc(u1.id, picks_submitted=True)
        _enroll_wc(u2.id, picks_submitted=False)

        active = resolve_recipients('worldcup', active_only=True)
        assert [r.email for r in active] == ['locked@test.com']

        everyone = resolve_recipients('worldcup', active_only=False)
        assert sorted(r.email for r in everyone) == [
            'drafting@test.com', 'locked@test.com',
        ]


def test_resolve_cfb_active_excludes_eliminated_and_other_seasons(app):
    with app.app_context():
        from core.admin.announce import resolve_recipients
        alive = _make_user_inline('alive')
        out = _make_user_inline('out')
        old = _make_user_inline('old')
        _enroll_cfb(alive.id, eliminated=False)
        _enroll_cfb(out.id, eliminated=True)
        _enroll_cfb(old.id, eliminated=False, season=2025)

        active = resolve_recipients('cfb', active_only=True)
        assert [r.email for r in active] == ['alive@test.com']

        everyone = resolve_recipients('cfb', active_only=False)
        assert sorted(r.email for r in everyone) == [
            'alive@test.com', 'out@test.com',
        ]


def test_resolve_golf_active_equals_all(app):
    with app.app_context():
        from core.admin.announce import resolve_recipients
        assert resolve_recipients('golf', active_only=True) == []

        u = _make_user_inline('golfer')
        _enroll_golf(u.id)
        active = resolve_recipients('golf', active_only=True)
        everyone = resolve_recipients('golf', active_only=False)
        assert active == everyone
        assert [r.email for r in active] == ['golfer@test.com']


def test_resolve_all_dedupes_by_email_case_insensitive(app):
    with app.app_context():
        from core.admin.announce import resolve_recipients
        both = _make_user_inline('both')
        wc_only = _make_user_inline('wconly')
        _enroll_wc(both.id)
        _enroll_cfb(both.id)
        _enroll_wc(wc_only.id)
        # Same mailbox, different casing, enrolled in a second game.
        shouty = User(username='shouty', email='BOTH@TEST.COM')
        shouty.set_password('pw')
        db.session.add(shouty)
        db.session.commit()
        _enroll_cfb(shouty.id)

        recipients = resolve_recipients('all', active_only=False)
        emails = [r.email.lower() for r in recipients]
        assert sorted(emails) == ['both@test.com', 'wconly@test.com']


def test_resolve_skips_falsy_email(app):
    with app.app_context():
        from core.admin.announce import resolve_recipients
        u = _make_user_inline('ghost')
        _enroll_wc(u.id)
        u.email = ''
        db.session.commit()
        assert resolve_recipients('worldcup', active_only=False) == []


def _make_user_inline(username, is_admin=False):
    u = User(username=username, email=f'{username}@test.com', is_admin=is_admin)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


# ---------------------------------------------------------------------------
# render_announcement — escaping is load-bearing (.j2 templates do NOT
# autoescape in Flask)
# ---------------------------------------------------------------------------

def test_render_announcement_escapes_admin_html(app):
    with app.test_request_context():
        from core.admin.announce import render_announcement
        plain, html = render_announcement(
            'Hi <b>', 'line one\n\n<script>alert(1)</script>',
        )
        assert '<script>' not in html
        assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
        assert 'Hi &lt;b&gt;' in html
        assert '<script>alert(1)</script>' in plain  # plain text untouched


def test_render_announcement_paragraphs_and_br(app):
    with app.test_request_context():
        from core.admin.announce import render_announcement
        _, html = render_announcement(
            'Subject', 'para one\nstill one\n\npara two',
        )
        assert 'para one<br>still one' in html
        assert html.count('para one') == 1
        assert '<p' in html and 'para two' in html


# ---------------------------------------------------------------------------
# Preview action
# ---------------------------------------------------------------------------

@patch('core.admin.announce.send_platform_email', return_value=True)
def test_preview_shows_count_and_send_buttons(mock_send, app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    with app.app_context():
        for name in ('p1', 'p2', 'p3'):
            u = _make_user_inline(name)
            _enroll_wc(u.id)
    _login(client, aid)

    resp = client.post('/admin/announce', data=_compose())
    assert resp.status_code == 200
    data = resp.data.decode()
    assert '3' in data
    assert 'value="send"' in data
    assert 'value="test"' in data
    assert '<iframe' in data and 'srcdoc=' in data
    assert 'Big news' in data            # subject repopulated
    assert 'Hello everyone.' in data     # body repopulated
    mock_send.assert_not_called()


@patch('core.admin.announce.send_platform_email', return_value=True)
def test_preview_rejects_blank_subject_or_body(mock_send, app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)

    for field in ('subject', 'body_text'):
        resp = client.post('/admin/announce', data=_compose(**{field: '   '}))
        assert resp.status_code == 200
        data = resp.data.decode()
        assert 'value="send"' not in data
    mock_send.assert_not_called()


@patch('core.admin.announce.send_platform_email', return_value=True)
def test_preview_rejects_invalid_audience_or_filter(mock_send, app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)

    for overrides in ({'audience': 'bogus'}, {'recipient_filter': 'bogus'}):
        resp = client.post('/admin/announce', data=_compose(**overrides))
        assert resp.status_code == 200
        assert 'value="send"' not in resp.data.decode()
    mock_send.assert_not_called()


@patch('core.admin.announce.send_platform_email', return_value=True)
def test_preview_zero_recipients_hides_send_button(mock_send, app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)
    resp = client.post('/admin/announce', data=_compose())
    assert resp.status_code == 200
    data = resp.data.decode()
    assert 'value="send"' not in data
    assert 'value="test"' in data  # test-to-self still offered
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Test send (to the composing admin only)
# ---------------------------------------------------------------------------

@patch('core.admin.announce.send_platform_email', return_value=True)
def test_action_test_sends_one_email_to_admin_only(mock_send, app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    with app.app_context():
        for name in ('m1', 'm2', 'm3', 'm4', 'm5'):
            u = _make_user_inline(name)
            _enroll_wc(u.id)
    _login(client, aid)

    resp = client.post('/admin/announce', data=_compose(action='test'))
    assert resp.status_code == 200
    mock_send.assert_called_once()
    to_addr, subject = mock_send.call_args[0][0], mock_send.call_args[0][1]
    assert to_addr == 'admin@test.com'
    assert subject.startswith('[TEST] ')
    # Still in preview state with the real recipient count.
    data = resp.data.decode()
    assert 'value="send"' in data
    assert '5' in data


# ---------------------------------------------------------------------------
# Mass send
# ---------------------------------------------------------------------------

@patch('core.admin.announce.send_platform_email', return_value=True)
def test_action_send_loops_all_recipients_prg(mock_send, app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    with app.app_context():
        for name in ('s1', 's2', 's3'):
            u = _make_user_inline(name)
            _enroll_wc(u.id)
    _login(client, aid)

    resp = client.post('/admin/announce', data=_compose(action='send'),
                       follow_redirects=False)
    assert resp.status_code == 302
    assert '/admin/announce' in resp.location
    assert mock_send.call_count == 3
    sent_to = sorted(c.args[0] for c in mock_send.call_args_list)
    assert sent_to == ['s1@test.com', 's2@test.com', 's3@test.com']

    follow = client.get(resp.location)
    assert 'Sent 3 of 3' in follow.data.decode()


@patch('core.admin.announce.send_platform_email')
def test_action_send_counts_failures(mock_send, app, client):
    mock_send.side_effect = [True, False, True]
    aid = _make_user(app, 'admin', is_admin=True)
    with app.app_context():
        for name in ('f1', 'f2', 'f3'):
            u = _make_user_inline(name)
            _enroll_wc(u.id)
    _login(client, aid)

    resp = client.post('/admin/announce', data=_compose(action='send'),
                       follow_redirects=True)
    data = resp.data.decode()
    assert 'Sent 2 of 3' in data
    assert '1 failed' in data


@patch('core.admin.announce.send_platform_email', return_value=True)
def test_action_send_validation_failure_sends_nothing(mock_send, app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    with app.app_context():
        u = _make_user_inline('v1')
        _enroll_wc(u.id)
    _login(client, aid)

    resp = client.post('/admin/announce',
                       data=_compose(action='send', subject='  '))
    assert resp.status_code == 200
    mock_send.assert_not_called()


@patch('core.admin.announce.send_platform_email', return_value=True)
def test_action_send_zero_recipients_warns_without_sending(mock_send, app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)
    resp = client.post('/admin/announce', data=_compose(action='send'))
    assert resp.status_code == 200
    mock_send.assert_not_called()


@patch('core.admin.announce.send_platform_email', return_value=True)
def test_action_send_dedupes_all_audience(mock_send, app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    with app.app_context():
        u = _make_user_inline('dual')
        _enroll_wc(u.id)
        _enroll_cfb(u.id)
    _login(client, aid)

    client.post('/admin/announce', data=_compose(action='send', audience='all'))
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0] == 'dual@test.com'


# ---------------------------------------------------------------------------
# Dashboard entry point
# ---------------------------------------------------------------------------

def test_dashboard_shows_announce_card(app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)
    resp = client.get('/admin/')
    data = resp.data.decode()
    assert '/admin/announce' in data
    assert 'bi-megaphone-fill' in data
