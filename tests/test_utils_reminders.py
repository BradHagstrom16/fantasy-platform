"""utils/reminders.py — the shared reminder de-dup order gate.

Pure-function locks; the per-game record policies are locked in each game's
own reminder tests (tests/test_cfb_reminders.py, tests/test_docket_reminders.py,
tests/test_golf_automation.py).
"""
import pytest

from utils.reminders import tier_already_sent

ORDER = {'warning': 0, 'final': 1}


def test_nothing_sent_yet_never_blocks():
    assert tier_already_sent(None, 'warning', ORDER) is False
    assert tier_already_sent(None, 'final', ORDER) is False


def test_same_tier_twice_is_blocked():
    assert tier_already_sent('warning', 'warning', ORDER) is True
    assert tier_already_sent('final', 'final', ORDER) is True


def test_earlier_tier_after_later_is_blocked():
    """A catch-up firing after the final went out must not send the warning."""
    assert tier_already_sent('final', 'warning', ORDER) is True


def test_later_tier_after_earlier_sends():
    assert tier_already_sent('warning', 'final', ORDER) is False


def test_unknown_stored_value_never_blocks():
    """A legacy or corrupt stored tier falls back to -1: it must never
    suppress a send."""
    assert tier_already_sent('junk', 'warning', ORDER) is False
    assert tier_already_sent('junk', 'final', ORDER) is False


def test_unknown_active_tier_fails_loud():
    """Docket doctrine: a caller holding a tier outside its own vocabulary is
    corrupt and should crash, not silently skip."""
    with pytest.raises(KeyError):
        tier_already_sent(None, 'nonsense', ORDER)


def test_works_with_richer_tier_maps():
    """The gate is vocabulary-agnostic — a three-tier game composes the same
    way (the Docket shape)."""
    order = {'early': 0, 'mid': 1, 'last': 2}
    assert tier_already_sent('early', 'mid', order) is False
    assert tier_already_sent('last', 'mid', order) is True
    assert tier_already_sent('mid', 'mid', order) is True
