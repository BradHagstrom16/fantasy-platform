"""Docket enrollment + registry entry locks (T7 scaffold).

Mirrors the per-game trio in tests/test_registry.py, plus the locks new to
this entry: non-featured/no-lounge-callables (the lounge seam must never
see The Docket), the D6 naive-UTC created_at, and the announce resolver
(a registry entry without a _RESOLVERS entry KeyErrors audience='all' at
runtime — the landmine this file pins shut).
"""
import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from games.docket.models import DocketEnrollment
from tests._docket_fixtures import make_enrollment, make_user


def test_docket_get_enrollment_returns_none_when_absent(app):
    user = make_user('docketuser')
    db.session.commit()
    from games.docket.services import enrollment
    assert enrollment.get_enrollment(user.id) is None


def test_docket_admin_enroll_is_idempotent(app):
    user = make_user('docketuser')
    db.session.commit()
    from games.docket.services import enrollment
    from games.docket.services.weeks import SEASON_YEAR
    e1 = enrollment.admin_enroll(user.id)
    e2 = enrollment.admin_enroll(user.id)
    assert e1.id == e2.id
    assert e1.user_id == user.id
    assert e1.season_year == SEASON_YEAR


def test_docket_entry_registered_in_GAMES(app):
    from games.registry import GAMES
    slugs = {e.slug for e in GAMES}
    assert 'docket' in slugs


def test_docket_entry_is_open_not_featured_no_lounge(app):
    """Survivor keeps the lounge: the docket entry must stay invisible to
    lounge_game() — not featured AND both lounge callables absent."""
    from games.registry import get_entry, lounge_game
    entry = get_entry('docket')
    assert entry.status == 'open'
    assert entry.is_featured is False
    assert entry.lounge_state is None
    assert entry.lounge_context is None
    assert entry.blueprint_index == 'docket.index'
    assert entry.blueprint_join == 'docket.join'
    lounge = lounge_game()
    assert lounge is not None and lounge.slug == 'cfb'


def test_docket_enrollment_created_at_is_naive_utc(app):
    """D6: every docket datetime column stores naive UTC — the enrollment
    audit default must use the docket lambda, not CFB's aware form."""
    user = make_user('docketuser')
    enrollment = make_enrollment(user)
    db.session.commit()
    assert enrollment.created_at is not None
    assert enrollment.created_at.tzinfo is None


def test_docket_enrollment_unique_per_user_season(app):
    user = make_user('docketuser')
    make_enrollment(user)
    db.session.commit()
    with pytest.raises(IntegrityError):
        db.session.add(DocketEnrollment(user_id=user.id, season_year=2026))
        db.session.commit()
    db.session.rollback()


def test_docket_display_name_falls_back_to_username(app):
    user = make_user('docketuser')
    enrollment = make_enrollment(user)
    db.session.commit()
    assert enrollment.get_display_name() == 'docketuser'
    enrollment.display_name = 'The Gavel'
    assert enrollment.get_display_name() == 'The Gavel'


def test_docket_has_announce_resolver(app):
    """Every GAMES slug must resolve in core/admin/announce.py, or the
    audience='all' path raises KeyError at runtime."""
    from core.admin.announce import _RESOLVERS
    from games.registry import GAMES
    for entry in GAMES:
        assert entry.slug in _RESOLVERS


def test_docket_announce_audience_all_includes_docket_members(app):
    user = make_user('docketuser')
    make_enrollment(user, display_name='The Gavel')
    db.session.commit()
    from core.admin.announce import resolve_recipients
    recipients = resolve_recipients('all', active_only=False)
    assert ('docketuser@test.com', 'The Gavel') in [
        (r.email, r.name) for r in recipients]
    # active_only is accepted (and ignored — no elimination concept).
    active = resolve_recipients('docket', active_only=True)
    assert [r.email for r in active] == ['docketuser@test.com']
