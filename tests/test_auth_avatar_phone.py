"""Tests for admin-reserved crown avatar + signup/profile phone collection."""
import pytest

from app import create_app
from core.auth.routes import AVATAR_CATEGORIES
from extensions import db
from models.user import User
from utils.phone import normalize_us_phone

CROWN = "\U0001F451"  # crown
DEFAULT = "⚽"   # soccer ball


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


def _make_user(app, username='u1', is_admin=False, avatar_emoji=None):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com',
                 is_admin=is_admin, avatar_emoji=avatar_emoji)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


# --- normalize_us_phone: pure helper -------------------------------------

@pytest.mark.parametrize("raw", [
    "5551234567",
    "(555) 123-4567",
    "555-123-4567",
    "555.123.4567",
    "+1 555 123 4567",
    "1-555-123-4567",
])
def test_normalize_accepts_valid_nanp(raw):
    normalized, error = normalize_us_phone(raw)
    assert error is None
    assert normalized == "(555) 123-4567"


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_normalize_blank_is_allowed(raw):
    normalized, error = normalize_us_phone(raw)
    assert normalized is None
    assert error is None


# --- crown reserved for admin (get_avatar) -------------------------------

def test_admin_always_gets_crown():
    u = User(username="a", email="a@t.com", is_admin=True, avatar_emoji="🦊")
    assert u.get_avatar() == CROWN


def test_admin_gets_crown_even_with_no_stored_emoji():
    u = User(username="a", email="a@t.com", is_admin=True)
    assert u.get_avatar() == CROWN


def test_non_admin_with_crown_falls_back_to_default():
    u = User(username="b", email="b@t.com", is_admin=False, avatar_emoji=CROWN)
    assert u.get_avatar() == DEFAULT


def test_non_admin_keeps_their_chosen_emoji():
    u = User(username="b", email="b@t.com", is_admin=False, avatar_emoji="🦊")
    assert u.get_avatar() == "🦊"


def test_crown_not_selectable_in_categories():
    all_emojis = [e for choices in AVATAR_CATEGORIES.values() for e in choices]
    assert CROWN not in all_emojis


def test_substitute_emojis_present():
    all_emojis = [e for choices in AVATAR_CATEGORIES.values() for e in choices]
    for sub in ("🃏", "🎩", "🦹", "🧞"):
        assert sub in all_emojis


# --- profile page rendering ---------------------------------------------

def test_profile_admin_sees_reserved_note_not_picker(app, client):
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)
    data = client.get('/profile').data.decode()
    assert 'reserved for admins' in data
    assert 'id="avatarTabContent"' not in data  # picker element hidden


def test_profile_non_admin_sees_picker_without_crown(app, client):
    uid = _make_user(app, 'player')
    _login(client, uid)
    data = client.get('/profile').data.decode()
    assert 'id="avatarTabContent"' in data  # picker element present
    assert CROWN not in data


# --- normalize_us_phone: invalid ----------------------------------------

@pytest.mark.parametrize("raw", [
    "12345",                 # too short
    "555123456789",          # too long
    "+44 20 1234 5678",      # non-NANP country code
    "abc-defg",              # non-numeric
    "0551234567",            # area code starts with 0
    "1551234567",            # area code starts with 1
])
def test_normalize_rejects_invalid(raw):
    normalized, error = normalize_us_phone(raw)
    assert normalized is None
    assert error is not None


# --- phone at registration ----------------------------------------------

def test_register_stores_normalized_phone(app, client):
    client.post('/register', data={
        'username': 'newbie', 'email': 'newbie@test.com',
        'password': 'secret1', 'confirm_password': 'secret1',
        'phone': '555.123.4567',
    })
    with app.app_context():
        u = User.query.filter_by(username='newbie').first()
        assert u is not None
        assert u.phone == '(555) 123-4567'


def test_register_without_phone_succeeds(app, client):
    client.post('/register', data={
        'username': 'nophone', 'email': 'nophone@test.com',
        'password': 'secret1', 'confirm_password': 'secret1',
    })
    with app.app_context():
        u = User.query.filter_by(username='nophone').first()
        assert u is not None
        assert u.phone is None


def test_register_rejects_invalid_phone(app, client):
    client.post('/register', data={
        'username': 'badphone', 'email': 'badphone@test.com',
        'password': 'secret1', 'confirm_password': 'secret1',
        'phone': '12345',
    })
    with app.app_context():
        assert User.query.filter_by(username='badphone').first() is None


# --- phone on profile ---------------------------------------------------

def test_profile_updates_normalized_phone(app, client):
    uid = _make_user(app, 'editor')
    _login(client, uid)
    client.post('/profile', data={
        'email': 'editor@test.com', 'display_name': '',
        'avatar_emoji': '', 'phone': '+1 (555) 987-6543',
    })
    with app.app_context():
        assert db.session.get(User, uid).phone == '(555) 987-6543'


def test_profile_invalid_phone_not_saved(app, client):
    uid = _make_user(app, 'editor2')
    _login(client, uid)
    client.post('/profile', data={
        'email': 'editor2@test.com', 'display_name': '',
        'avatar_emoji': '', 'phone': 'nope',
    })
    with app.app_context():
        assert db.session.get(User, uid).phone is None
