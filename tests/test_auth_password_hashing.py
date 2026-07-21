"""Regression lock: the stored-password hash format and legacy verification.

`User.set_password` pins `method='scrypt'` rather than inheriting Werkzeug's
default, which has moved over time (pbkdf2:sha1 -> pbkdf2:sha256 -> scrypt in
2.3). The pin is a no-op against Werkzeug 3.1.8 — scrypt is already its default
— which is exactly why it needs a lock: nothing else in the suite would notice
the pin being dropped, because every other test generates its hash with the
current code and would keep passing whatever the format became.

The legacy hashes below are deliberately **literals**, not values produced by
`generate_password_hash(method=...)` at test time. Production rows written
under older Werkzeug defaults are literal strings sitting in a column; a
generate-based test would fail at *generation* if a method were ever removed,
which is a different (and less interesting) failure than the one that matters —
that an existing user can no longer log in.
"""
import pytest
from werkzeug.security import generate_password_hash

from models.user import User

# All three encode the password 'correct horse', generated under Werkzeug 3.1.8.
LEGACY_HASHES = {
    'pbkdf2:sha1': (
        'pbkdf2:sha1:1000000$nbF4nc7BkrbhkhTl$'
        'af05189fe7c9494277fa24d62585dd600e443c06'
    ),
    'pbkdf2:sha256': (
        'pbkdf2:sha256:1000000$SDhImTYFdmztU5YF$'
        '180fab5fcab620c502f2be42120db8d8c70ede1152908eafef5b9b967645ee6d'
    ),
    'scrypt': (
        'scrypt:32768:8:1$TB8jn028p4Zk0S0m$'
        '1f925e2de9717ef475ff0e46f31df3b35bcd53a7ac48b6f590386e2ac83015aa'
        '980e7ae6a848c389ac63488b8933c38f1abb8695c7e42fcd22b2651971e1f7b6'
    ),
}


@pytest.mark.parametrize('method', sorted(LEGACY_HASHES))
def test_legacy_hash_formats_still_verify(method):
    """A row written under an older Werkzeug default must still log in.

    This is the check that a Werkzeug upgrade could silently break for every
    pre-existing account at once.
    """
    user = User(username='legacy', email='legacy@example.com')
    user.password_hash = LEGACY_HASHES[method]

    assert user.check_password('correct horse') is True


@pytest.mark.parametrize('method', sorted(LEGACY_HASHES))
def test_legacy_hash_formats_reject_wrong_password(method):
    """Verification must be real, not a permissive fallback for old formats."""
    user = User(username='legacy', email='legacy@example.com')
    user.password_hash = LEGACY_HASHES[method]

    assert user.check_password('wrong horse') is False


def test_set_password_emits_scrypt():
    """The format contract.

    Note this passes today either way — scrypt is already Werkzeug 3.1.8's
    default, so removing the pin changes nothing yet. It is a *forward* lock:
    it fires on the combination that would actually hurt, a Werkzeug upgrade
    moving the default while the pin is absent.
    """
    user = User(username='new', email='new@example.com')
    user.set_password('correct horse')

    assert user.password_hash.startswith('scrypt:')


def test_set_password_round_trips():
    user = User(username='new', email='new@example.com')
    user.set_password('correct horse')

    assert user.check_password('correct horse') is True
    assert user.check_password('correct horses') is False


def test_set_password_salts_each_call():
    """Two users with the same password must not share a hash."""
    a = User(username='a', email='a@example.com')
    b = User(username='b', email='b@example.com')
    a.set_password('correct horse')
    b.set_password('correct horse')

    assert a.password_hash != b.password_hash


def test_literal_fixtures_match_current_werkzeug_output():
    """Guard the fixtures themselves.

    If Werkzeug ever changes a format's default parameters, the literals above
    stop resembling what production writes today and quietly become a weaker
    test than they look. This compares structure (algorithm and cost prefix),
    not the digest, since the salt is random per call.
    """
    for method, literal in LEGACY_HASHES.items():
        fresh = generate_password_hash('correct horse', method=method)
        assert fresh.split('$')[0] == literal.split('$')[0], (
            f'{method} default parameters changed; regenerate the fixture'
        )
