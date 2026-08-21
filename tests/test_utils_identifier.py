"""utils/identifier.py — the shared auth-identifier fold (backlog 2.8).

Pure-function locks. The behavioral contract of the call sites (login by
username OR email, any case, username-first precedence; register/profile
duplicate rejection) is locked in tests/test_auth_login_recovery.py and the
auth suites, which must keep passing unchanged with the sites routed through
this helper.
"""
from utils.identifier import normalize_identifier


def test_strips_and_casefolds():
    assert normalize_identifier('  Alice ') == 'alice'
    assert normalize_identifier('BRAD@EXAMPLE.COM') == 'brad@example.com'


def test_none_and_empty_normalize_to_empty_string():
    """'' matches nothing — both unique columns are non-empty — so a missing
    form field can never accidentally match a row."""
    assert normalize_identifier(None) == ''
    assert normalize_identifier('') == ''
    assert normalize_identifier('   ') == ''


def test_casefold_is_the_i18n_superset_of_lower():
    """The documented ß case: casefold folds to 'ss' where lower() leaves ß.
    This is why every call site must use the SAME fold — four disagreeing
    idioms was the trap this helper retires."""
    assert normalize_identifier('Straße') == 'strasse'
    assert 'Straße'.lower() != normalize_identifier('Straße')


def test_idempotent():
    """A call site that already stripped/lowered its input is safe to route
    through the helper — normalizing twice equals normalizing once."""
    for raw in ('  MixedCase ', 'already lower', 'Straße', ''):
        once = normalize_identifier(raw)
        assert normalize_identifier(once) == once
