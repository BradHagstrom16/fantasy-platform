"""Tests for the reserved avatars (admin crown, reigning-champion trophy), the
football default, and signup/profile phone collection."""
import pytest

from core.auth.routes import AVATAR_CATEGORIES
from extensions import db
from models.user import User
from utils.phone import normalize_us_phone

CROWN = "\U0001F451"     # crown — reserved for platform admins
TROPHY = "\U0001F3C6"    # trophy — reserved for every reigning club champion
DEFAULT = "\U0001F3C8"   # football — the default for anyone who never chose
BASEBALL = "⚾"      # the picker slot the trophy vacated
SOCCER = "⚽"        # the retired World Cup-era default


def _all_selectable():
    """Flatten the picker's categories into one list of selectable emoji."""
    return [e for choices in AVATAR_CATEGORIES.values() for e in choices]


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
    from models.user import User
    auth_id = db.session.get(User, user_id).auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
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


def test_non_admin_with_crown_falls_back_to_default(app):
    """A non-admin who has the crown stored renders the default instead."""
    u = User(username="b", email="b@t.com", is_admin=False, avatar_emoji=CROWN)
    assert u.get_avatar() == DEFAULT


def test_non_admin_keeps_their_chosen_emoji(app):
    """A non-admin renders their own chosen (non-crown) emoji."""
    u = User(username="b", email="b@t.com", is_admin=False, avatar_emoji="🦊")
    assert u.get_avatar() == "🦊"


def test_crown_not_selectable_in_categories():
    """The crown is excluded from the selectable avatar list."""
    assert CROWN not in _all_selectable()


def test_substitute_emojis_present():
    """The four substitute emojis are selectable in the picker."""
    all_emojis = _all_selectable()
    for sub in ("🃏", "🎩", "🦹", "🧞"):
        assert sub in all_emojis


# --- football default (the soccer ball was the World Cup era's) -----------

def test_default_avatar_is_football():
    """The platform default is the football, stored as an escape, not a literal."""
    assert User.DEFAULT_AVATAR == DEFAULT
    assert User.DEFAULT_AVATAR != SOCCER


def test_user_who_never_chose_renders_football(app):
    """A NULL avatar_emoji renders the football — legacy accounts included, since
    the default lives only in get_avatar(), never in the row."""
    u = User(username="fresh", email="fresh@t.com")
    assert u.get_avatar() == DEFAULT


def test_football_still_selectable():
    """Members may still pick the football explicitly."""
    assert DEFAULT in _all_selectable()


# --- trophy reserved for the reigning Survivor champion ------------------

def test_trophy_not_selectable_in_categories():
    """The trophy is excluded from the selectable avatar list (reserved)."""
    assert TROPHY not in _all_selectable()


def test_baseball_fills_the_trophy_slot():
    """The trophy's picker slot is taken by the baseball, keeping Sports at 15."""
    sports = AVATAR_CATEGORIES["Sports & Games"]
    assert BASEBALL in sports
    assert len(sports) == 15


def test_non_champion_with_trophy_falls_back_to_default(app):
    """A stored trophy on anyone but the champion renders the default instead."""
    u = User(username="pretender", email="p@t.com", avatar_emoji=TROPHY)
    assert u.get_avatar() == DEFAULT


def _crown_on_the_record(app, user_id, game='cfb', season_year=2025):
    """Close a season on the record with this member in first place (ADR-068:
    the reigning champion is derived from season_finishes, never declared)."""
    from models.records import FinishDraft, record_season
    with app.app_context():
        record_season(game, season_year, [
            FinishDraft(user_id=user_id, name='Champ', place=1, outcome='champion',
                        detail=None),
        ])


def test_no_declared_champion_constant():
    """The champion is read from the record, never typed into the model."""
    assert not hasattr(User, 'REIGNING_CHAMPION_USERNAME')


def test_reigning_champion_gets_trophy_regardless_of_choice(app):
    """The reigning champion renders the trophy even with a stored pick."""
    cid = _make_user(app, 'champ', avatar_emoji=BASEBALL)
    _crown_on_the_record(app, cid)
    u = db.session.get(User, cid)
    assert u.is_reigning_champion is True
    assert u.get_avatar() == TROPHY


def test_only_the_latest_closed_season_reigns(app):
    """A past champion hands the trophy on when the game's next season closes."""
    old = _make_user(app, 'old')
    new = _make_user(app, 'new')
    _crown_on_the_record(app, old, season_year=2025)
    _crown_on_the_record(app, new, season_year=2026)
    assert db.session.get(User, old).get_avatar() == DEFAULT
    assert db.session.get(User, new).get_avatar() == TROPHY


def test_non_champion_is_not_reigning_champion(app):
    """Everyone else on the board is not the champion."""
    cid = _make_user(app, 'champ')
    other = _make_user(app, 'other')
    _crown_on_the_record(app, cid)
    assert db.session.get(User, other).is_reigning_champion is False


def test_champion_who_is_admin_gets_crown(app):
    """Crown outranks trophy: an admin champion still renders the crown."""
    cid = _make_user(app, 'boss', is_admin=True)
    _crown_on_the_record(app, cid, game='worldcup', season_year=2026)
    assert db.session.get(User, cid).get_avatar() == CROWN


# --- profile page rendering ---------------------------------------------

def test_profile_admin_sees_reserved_note_not_picker(app, client):
    """An admin's profile shows the reserved-crown note and hides the picker."""
    aid = _make_user(app, 'admin', is_admin=True)
    _login(client, aid)
    data = client.get('/profile').data.decode()
    assert 'reserved for admins' in data
    assert 'id="avatarTabContent"' not in data  # picker element hidden


def test_profile_champion_sees_reserved_note_not_picker(app, client):
    """The reigning champion's profile shows the trophy note and hides the picker."""
    cid = _make_user(app, 'champ')
    _crown_on_the_record(app, cid)
    _login(client, cid)
    data = client.get('/profile').data.decode()
    assert 'reigning club champion' in data
    assert TROPHY in data
    assert 'id="avatarTabContent"' not in data  # picker element hidden
    assert 'reserved for admins' not in data


def test_profile_non_admin_sees_picker_without_reserved_glyphs(app, client):
    """A non-admin's profile shows the picker and never a reserved glyph."""
    uid = _make_user(app, 'player')
    _login(client, uid)
    data = client.get('/profile').data.decode()
    assert 'id="avatarTabContent"' in data  # picker element present
    assert CROWN not in data
    assert TROPHY not in data


def test_profile_previews_football_and_carries_no_soccer_literal(app, client):
    """A never-chose member previews the football, and the JS deselect default is
    templated from the model — no hard-coded soccer-ball string literal survives
    (the soccer ball itself stays selectable in the picker, so only the JS
    literal form is locked)."""
    uid = _make_user(app, 'player2')
    _login(client, uid)
    data = client.get('/profile').data.decode()
    assert f'id="avatarPreview">{DEFAULT}<' in data
    assert f'data-default-avatar="{DEFAULT}"' in data
    assert f"'{SOCCER}'" not in data


def test_profile_post_with_trophy_is_coerced_to_default(app, client):
    """A hand-POSTed trophy is outside the allow-list and is not stored."""
    uid = _make_user(app, 'sneaky')
    _login(client, uid)
    client.post('/profile', data={
        'email': 'sneaky@test.com', 'display_name': '',
        'avatar_emoji': TROPHY, 'phone': '',
    })
    with app.app_context():
        assert db.session.get(User, uid).avatar_emoji is None


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
