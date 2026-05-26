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
    """Provide a testing app with a fresh in-memory schema per test."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Return a test client bound to the testing app."""
    return app.test_client()


def _make_user(app, username='u1', is_admin=False, avatar_emoji=None):
    """Create and persist a user, returning its id."""
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com',
                 is_admin=is_admin, avatar_emoji=avatar_emoji)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(client, user_id):
    """Mark the given user id as the logged-in session user."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


# --- normalize_us_phone: pure helper -------------------------------------

@pytest.mark.parametrize("raw", [
    "2125550123",
    "(212) 555-0123",
    "212-555-0123",
    "212.555.0123",
    "+1 212 555 0123",
    "1-212-555-0123",
])
def test_normalize_accepts_valid_nanp(raw):
    """Various punctuation/country-code forms normalize to one canonical string."""
    normalized, error = normalize_us_phone(raw)
    assert error is None
    assert normalized == "(212) 555-0123"


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_normalize_blank_is_allowed(raw):
    """Blank input is valid (the field is optional) and yields no value."""
    normalized, error = normalize_us_phone(raw)
    assert normalized is None
    assert error is None


# --- crown reserved for admin (get_avatar) -------------------------------

def test_admin_always_gets_crown():
    """An admin renders the crown regardless of any stored avatar."""
    u = User(username="a", email="a@t.com", is_admin=True, avatar_emoji="🦊")
    assert u.get_avatar() == CROWN


def test_admin_gets_crown_even_with_no_stored_emoji():
    """An admin with no stored avatar still renders the crown."""
    u = User(username="a", email="a@t.com", is_admin=True)
    assert u.get_avatar() == CROWN


def test_non_admin_with_crown_falls_back_to_default():
    """A non-admin who has the crown stored renders the default instead."""
    u = User(username="b", email="b@t.com", is_admin=False, avatar_emoji=CROWN)
    assert u.get_avatar() == DEFAULT


def test_non_admin_keeps_their_chosen_emoji():
    """A non-admin renders their own chosen (non-crown) emoji."""
    u = User(username="b", email="b@t.com", is_admin=False, avatar_emoji="🦊")
    assert u.get_avatar() == "🦊"


def test_crown_not_selectable_in_categories():
    """The crown is excluded from the selectable avatar list."""
    all_emojis = [e for choices in AVATAR_CATEGORIES.values() for e in choices]
    assert CROWN not in all_emojis


def test_substitute_emojis_present():
    """The four substitute emojis are selectable in the picker."""
    all_emojis = [e for choices in AVATAR_CATEGORIES.values() for e in choices]
    for sub in ("🃏", "🎩", "🦹", "🧞"):
        assert sub in all_emojis


# --- profile page rendering ---------------------------------------------

def test_profile_admin_sees_reserved_note_not_picker(app, client):
    """An admin's profile shows the reserved-crown note and hides the picker."""
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)
    data = client.get('/profile').data.decode()
    assert 'reserved for admins' in data
    assert 'id="avatarTabContent"' not in data  # picker element hidden


def test_profile_non_admin_sees_picker_without_crown(app, client):
    """A non-admin's profile shows the picker and never the crown."""
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
    "2120123456",            # exchange code starts with 0
    "2121234567",            # exchange code starts with 1
])
def test_normalize_rejects_invalid(raw):
    """Non-NANP or malformed numbers are rejected with an error message."""
    normalized, error = normalize_us_phone(raw)
    assert normalized is None
    assert error is not None


# --- phone at registration ----------------------------------------------

def test_register_stores_normalized_phone(app, client):
    """Registering with a phone stores it in normalized form."""
    client.post('/register', data={
        'username': 'newbie', 'email': 'newbie@test.com',
        'password': 'secret1', 'confirm_password': 'secret1',
        'phone': '212.555.0123',
    })
    with app.app_context():
        u = User.query.filter_by(username='newbie').first()
        assert u is not None
        assert u.phone == '(212) 555-0123'


def test_register_without_phone_succeeds(app, client):
    """Registering without a phone succeeds and leaves phone unset."""
    client.post('/register', data={
        'username': 'nophone', 'email': 'nophone@test.com',
        'password': 'secret1', 'confirm_password': 'secret1',
    })
    with app.app_context():
        u = User.query.filter_by(username='nophone').first()
        assert u is not None
        assert u.phone is None


def test_register_rejects_invalid_phone(app, client):
    """An invalid phone blocks registration; no user is created."""
    client.post('/register', data={
        'username': 'badphone', 'email': 'badphone@test.com',
        'password': 'secret1', 'confirm_password': 'secret1',
        'phone': '12345',
    })
    with app.app_context():
        assert User.query.filter_by(username='badphone').first() is None


# --- phone on profile ---------------------------------------------------

def test_profile_updates_normalized_phone(app, client):
    """Saving a valid phone on the profile stores it normalized."""
    uid = _make_user(app, 'editor')
    _login(client, uid)
    client.post('/profile', data={
        'email': 'editor@test.com', 'display_name': '',
        'avatar_emoji': '', 'phone': '+1 (555) 987-6543',
    })
    with app.app_context():
        assert db.session.get(User, uid).phone == '(555) 987-6543'


def test_profile_invalid_phone_not_saved(app, client):
    """An invalid phone on the profile is rejected and not persisted."""
    uid = _make_user(app, 'editor2')
    _login(client, uid)
    client.post('/profile', data={
        'email': 'editor2@test.com', 'display_name': '',
        'avatar_emoji': '', 'phone': 'nope',
    })
    with app.app_context():
        assert db.session.get(User, uid).phone is None
