"""Tests for the admin-editable "From the Commish" home-page note.

Covers the `CommishNote` model helpers (default fallback + paragraph
rendering + champion substitution) and the platform-admin edit route
(auth gate, pre-fill, save/upsert, blank-suppresses).
"""
import pytest

from app import create_app
from extensions import db
from models.user import User
from models.content import (
    CommishNote, COMMISH_NOTE_DEFAULTS,
    commish_note_body, commish_note_paragraphs,
)


@pytest.fixture()
def app():
    """Fresh testing app with an empty in-memory schema per test."""
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
    """Seed the session with the user's auth_id (never str(id))."""
    auth_id = db.session.get(User, user_id).auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True


class _Champ:
    """Stand-in for a WorldCupTeam with a display_name."""
    def __init__(self, name):
        self.display_name = name


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------

def test_body_falls_back_to_default_when_no_row(app):
    with app.app_context():
        assert commish_note_body('live') == COMMISH_NOTE_DEFAULTS['live']
        assert commish_note_body('pre') == COMMISH_NOTE_DEFAULTS['pre']


def test_stored_row_is_authoritative_even_when_blank(app):
    """An existing row wins over the default — including a blank body, which
    is how an admin intentionally suppresses a state's note."""
    with app.app_context():
        db.session.add(CommishNote(state='live', body='Custom live note.'))
        db.session.add(CommishNote(state='pre', body=''))
        db.session.commit()
        assert commish_note_body('live') == 'Custom live note.'
        assert commish_note_body('pre') == ''  # blank row, NOT the default


def test_paragraphs_split_on_blank_lines(app):
    with app.app_context():
        db.session.add(CommishNote(
            state='live', body='First para.\n\nSecond para.'))
        db.session.commit()
        paras = commish_note_paragraphs('live')
        assert paras == ['First para.', 'Second para.']


def test_paragraphs_empty_body_returns_empty_list(app):
    """A blank stored body yields no paragraphs (template suppresses note)."""
    with app.app_context():
        db.session.add(CommishNote(state='live', body='   '))
        db.session.commit()
        assert commish_note_paragraphs('live') == []


def test_post_paragraphs_substitute_champion(app):
    with app.app_context():
        db.session.add(CommishNote(
            state='post', body='{champion} lifted the trophy.'))
        db.session.commit()
        assert commish_note_paragraphs('post', _Champ('Spain')) == [
            'Spain lifted the trophy.'
        ]


def test_post_paragraphs_neutral_when_no_champion(app):
    with app.app_context():
        db.session.add(CommishNote(
            state='post', body='{champion} lifted the trophy.'))
        db.session.commit()
        # No champion (malformed final): a neutral phrase, never a literal token.
        paras = commish_note_paragraphs('post', None)
        assert paras == ['The champion lifted the trophy.']
        assert '{champion}' not in paras[0]


def test_default_post_substitutes_champion_without_a_row(app):
    """The default post prose carries the {champion} token; the fallback path
    must substitute it too, not leak the literal placeholder."""
    with app.app_context():
        paras = commish_note_paragraphs('post', _Champ('Argentina'))
        assert any('Argentina lifted the trophy' in p for p in paras)
        assert all('{champion}' not in p for p in paras)


# ---------------------------------------------------------------------------
# Admin route
# ---------------------------------------------------------------------------

def test_route_requires_login(client):
    resp = client.get('/admin/commish-note')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_route_blocks_non_admin(app, client):
    uid = _make_user(app, username='plain', is_admin=False)
    _login(client, uid)
    resp = client.get('/admin/commish-note')
    assert resp.status_code == 302  # redirected to main.index, not rendered


def test_admin_get_prefills_textareas_with_defaults(app, client):
    uid = _make_user(app, username='boss', is_admin=True)
    _login(client, uid)
    resp = client.get('/admin/commish-note')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'name="body_pre"' in body
    assert 'name="body_live"' in body
    assert 'name="body_post"' in body
    # Pre-filled with the current default prose when no row exists yet.
    assert 'Goals fall where they fall' in body  # from the live default


def test_admin_post_saves_and_persists(app, client):
    uid = _make_user(app, username='boss', is_admin=True)
    _login(client, uid)
    resp = client.post('/admin/commish-note', data={
        'csrf_token': 'x',
        'body_pre': 'New pre note.',
        'body_live': 'New live note.\n\nSecond line.',
        'body_post': '{champion} won it all.',
    })
    assert resp.status_code == 302  # PRG
    with app.app_context():
        assert commish_note_body('pre') == 'New pre note.'
        assert commish_note_paragraphs('live') == ['New live note.', 'Second line.']
        assert commish_note_paragraphs('post', _Champ('Brazil')) == ['Brazil won it all.']


def test_admin_post_blank_body_suppresses_state(app, client):
    uid = _make_user(app, username='boss', is_admin=True)
    _login(client, uid)
    client.post('/admin/commish-note', data={
        'csrf_token': 'x',
        'body_pre': '',
        'body_live': 'Live stays.',
        'body_post': '',
    })
    with app.app_context():
        # Blank pre row exists and suppresses (no fallback to default).
        assert CommishNote.query.filter_by(state='pre').first() is not None
        assert commish_note_paragraphs('pre') == []
        assert commish_note_paragraphs('live') == ['Live stays.']


def test_admin_post_upserts_existing_row(app, client):
    """Saving twice updates the same row rather than creating duplicates
    (the state column is unique)."""
    uid = _make_user(app, username='boss', is_admin=True)
    _login(client, uid)
    for text in ('First.', 'Second.'):
        client.post('/admin/commish-note', data={
            'csrf_token': 'x',
            'body_pre': text, 'body_live': '', 'body_post': '',
        })
    with app.app_context():
        assert CommishNote.query.filter_by(state='pre').count() == 1
        assert commish_note_body('pre') == 'Second.'
