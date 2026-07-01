"""PR 1 — Golf scoring & resolution correctness (TDD).

Locks:
- the battle-tested WD branching in ``GolfPick.resolve_pick()`` (regression),
- the Zurich team-event FULL-payout ruling (ADR-033),
- the major x1.5 multiplier + its precedence,
- ``is_backup_activated()`` reflecting an early primary WD live, and
- transactional reprocessing in ``process_tournament_picks`` that must not
  persist partial clears when a single pick fails to resolve.

Golf tests run against in-memory SQLite via ``create_app('testing')``.
"""
import pytest
from datetime import datetime, timedelta, timezone

from app import create_app
from extensions import db
from models.user import User
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfTournament,
    GolfTournamentResult,
    GolfSeasonPlayerUsage,
)
from games.golf.services.sync import SlashGolfAPI, TournamentSync

SEASON = 2026


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


# --- seed helpers (run inside the fixture's app context) --------------------

def _make_user(username='golfer'):
    u = User(username=username, email=f'{username}@test.com')
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


def _make_enrollment(user):
    e = GolfEnrollment(user_id=user.id, season_year=SEASON, total_points=0)
    db.session.add(e)
    db.session.commit()
    return e


def _make_tournament(name='Test Open', is_major=False, is_team_event=False, status='complete'):
    now = datetime.now(timezone.utc)
    t = GolfTournament(
        api_tourn_id=f'T-{name}',
        name=name,
        season_year=SEASON,
        start_date=now - timedelta(days=4),
        end_date=now - timedelta(days=1),
        pick_deadline=now - timedelta(days=4),
        purse=10_000_000,
        is_major=is_major,
        is_team_event=is_team_event,
        status=status,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _make_player(api_id, first, last):
    p = GolfPlayer(api_player_id=api_id, first_name=first, last_name=last)
    db.session.add(p)
    db.session.commit()
    return p


def _make_result(tournament, player, status='complete', rounds_completed=4, earnings=0):
    r = GolfTournamentResult(
        tournament_id=tournament.id,
        player_id=player.id,
        status=status,
        rounds_completed=rounds_completed,
        earnings=earnings,
        final_position='1',
    )
    db.session.add(r)
    db.session.commit()
    return r


def _make_pick(user, tournament, primary, backup, **kwargs):
    pick = GolfPick(
        user_id=user.id,
        tournament_id=tournament.id,
        primary_player_id=primary.id,
        backup_player_id=backup.id,
        **kwargs,
    )
    db.session.add(pick)
    db.session.commit()
    return pick


def _add_usage(user, player):
    u = GolfSeasonPlayerUsage(user_id=user.id, player_id=player.id, season_year=SEASON)
    db.session.add(u)
    db.session.commit()


def _usage_player_ids(user):
    return {
        row.player_id
        for row in GolfSeasonPlayerUsage.query.filter_by(user_id=user.id, season_year=SEASON)
    }


def _sync():
    return TournamentSync(SlashGolfAPI(api_key='test-key'))


# --- WD branching regression locks -----------------------------------------

def test_resolve_pick_primary_finishes(app):
    user = _make_user()
    t = _make_tournament()
    p1 = _make_player('P1', 'Primary', 'One')
    p2 = _make_player('P2', 'Backup', 'Two')
    _make_result(t, p1, status='complete', rounds_completed=4, earnings=100_000)
    _make_result(t, p2, status='complete', rounds_completed=4, earnings=50_000)
    pick = _make_pick(user, t, p1, p2)

    assert pick.resolve_pick() is True
    assert pick.active_player_id == p1.id
    assert pick.points_earned == 100_000
    assert pick.primary_used is True
    assert pick.backup_used is False


def test_resolve_pick_primary_wd_before_r2_backup_finishes(app):
    user = _make_user()
    t = _make_tournament()
    p1 = _make_player('P1', 'Primary', 'One')
    p2 = _make_player('P2', 'Backup', 'Two')
    _make_result(t, p1, status='wd', rounds_completed=1, earnings=0)
    _make_result(t, p2, status='complete', rounds_completed=4, earnings=80_000)
    pick = _make_pick(user, t, p1, p2)

    assert pick.resolve_pick() is True
    assert pick.active_player_id == p2.id
    assert pick.points_earned == 80_000
    assert pick.primary_used is False  # returns to pool
    assert pick.backup_used is True


def test_resolve_pick_primary_wd_after_r2(app):
    user = _make_user()
    t = _make_tournament()
    p1 = _make_player('P1', 'Primary', 'One')
    p2 = _make_player('P2', 'Backup', 'Two')
    _make_result(t, p1, status='wd', rounds_completed=2, earnings=0)
    _make_result(t, p2, status='complete', rounds_completed=4, earnings=80_000)
    pick = _make_pick(user, t, p1, p2)

    assert pick.resolve_pick() is True
    assert pick.active_player_id == p1.id  # primary counts (post-R2 WD)
    assert pick.points_earned == 0
    assert pick.primary_used is True
    assert pick.backup_used is False


def test_resolve_pick_both_wd_before_r2(app):
    user = _make_user()
    t = _make_tournament()
    p1 = _make_player('P1', 'Primary', 'One')
    p2 = _make_player('P2', 'Backup', 'Two')
    _make_result(t, p1, status='wd', rounds_completed=1, earnings=0)
    _make_result(t, p2, status='wd', rounds_completed=0, earnings=0)
    pick = _make_pick(user, t, p1, p2)

    assert pick.resolve_pick() is True
    assert pick.active_player_id == p1.id
    assert pick.points_earned == 0
    assert pick.primary_used is True  # primary used for 0
    assert pick.backup_used is False  # backup returns to pool


# --- Zurich full-payout ruling (ADR-033) + major multiplier ----------------

def test_calculate_total_points_team_event_rule(app):
    """ADR-033: a Zurich team-event pick earns the FULL team payout, not halved."""
    user = _make_user()
    t = _make_tournament(name='Zurich Classic', is_team_event=True)
    p1 = _make_player('P1', 'Primary', 'One')
    p2 = _make_player('P2', 'Backup', 'Two')
    _make_result(t, p1, status='complete', rounds_completed=4, earnings=100_000)
    _make_result(t, p2, status='complete', rounds_completed=4, earnings=50_000)
    pick = _make_pick(user, t, p1, p2)

    assert pick.resolve_pick() is True
    assert pick.active_player_id == p1.id
    assert pick.points_earned == 100_000  # FULL payout, not 50_000


def test_resolve_pick_major_applies_multiplier(app):
    """Majors earn x1.5; team halving is gone, so only the multiplier applies."""
    user = _make_user()
    t = _make_tournament(name='Masters', is_major=True)
    p1 = _make_player('P1', 'Primary', 'One')
    p2 = _make_player('P2', 'Backup', 'Two')
    _make_result(t, p1, status='complete', rounds_completed=4, earnings=100_000)
    _make_result(t, p2, status='complete', rounds_completed=4, earnings=50_000)
    pick = _make_pick(user, t, p1, p2)

    assert pick.resolve_pick() is True
    assert pick.points_earned == 150_000  # 100_000 * 1.5


# --- live early-WD backup activation ---------------------------------------

def test_is_backup_activated_true_when_primary_wd_early_live(app):
    user = _make_user()
    t = _make_tournament(name='Live Open', status='active')
    p1 = _make_player('P1', 'Primary', 'One')
    p2 = _make_player('P2', 'Backup', 'Two')
    _make_result(t, p1, status='wd', rounds_completed=1, earnings=0)
    _make_result(t, p2, status='complete', rounds_completed=2, earnings=40_000)
    pick = _make_pick(user, t, p1, p2)

    assert pick.is_backup_activated() is True


def test_get_current_earnings_reflects_activated_backup_live(app):
    """During an active tournament, a pre-R2 primary WD surfaces the backup's earnings."""
    user = _make_user()
    t = _make_tournament(name='Live Open', status='active')
    p1 = _make_player('P1', 'Primary', 'One')
    p2 = _make_player('P2', 'Backup', 'Two')
    _make_result(t, p1, status='wd', rounds_completed=1, earnings=0)
    _make_result(t, p2, status='complete', rounds_completed=2, earnings=40_000)
    pick = _make_pick(user, t, p1, p2)

    assert pick.get_current_earnings() == 40_000  # backup's, not the dead primary's 0


# --- transactional reprocessing --------------------------------------------

def test_reprocess_removes_stale_primary_backup_usage(app):
    """Reprocess clears usage for primary+backup+old-active, not just old-active,
    and does not touch other users' usage rows."""
    user = _make_user('u1')
    _make_enrollment(user)
    other = _make_user('u2')
    t = _make_tournament()
    p1 = _make_player('P1', 'Primary', 'One')
    p2 = _make_player('P2', 'Backup', 'Two')
    p3 = _make_player('P3', 'Other', 'Three')
    _make_result(t, p1, status='complete', rounds_completed=4, earnings=100_000)
    _make_result(t, p2, status='complete', rounds_completed=4, earnings=50_000)
    # Pick already resolved to the primary, but a STALE backup-usage row lingers.
    pick = _make_pick(user, t, p1, p2, active_player_id=p1.id, points_earned=100_000,
                      primary_used=True)
    _add_usage(user, p1)
    _add_usage(user, p2)  # stale — backup should not be "used" when primary counts
    _add_usage(other, p3)  # unrelated, must survive
    t.recap_email_sent = True  # skip the recap-email branch
    db.session.commit()

    _sync().process_tournament_picks(t)

    db.session.expire_all()
    assert _usage_player_ids(user) == {p1.id}       # stale p2 removed
    assert _usage_player_ids(other) == {p3.id}      # untouched


def test_reprocess_failed_pick_preserves_prior_resolution(app):
    """A pick that fails to re-resolve must keep its prior points + usage (no partial
    clear), and must not corrupt a sibling pick's total."""
    u1 = _make_user('good')
    e1 = _make_enrollment(u1)
    u2 = _make_user('bad')
    _make_enrollment(u2)
    t = _make_tournament()
    p1 = _make_player('P1', 'GoodPrimary', 'One')
    p2 = _make_player('P2', 'GoodBackup', 'Two')
    p3 = _make_player('P3', 'BadPrimary', 'Three')
    p4 = _make_player('P4', 'BadBackup', 'Four')
    # Good pick has fresh results.
    _make_result(t, p1, status='complete', rounds_completed=4, earnings=100_000)
    _make_result(t, p2, status='complete', rounds_completed=4, earnings=50_000)
    _make_pick(u1, t, p1, p2)
    # Bad pick: NO result for its primary -> resolve_pick() returns False.
    bad_pick = _make_pick(u2, t, p3, p4, active_player_id=p3.id, points_earned=77_000,
                          primary_used=True)
    _add_usage(u2, p3)  # prior resolution's usage
    t.recap_email_sent = True
    db.session.commit()
    bad_pick_id = bad_pick.id

    _sync().process_tournament_picks(t)

    db.session.expire_all()
    # Good pick resolved + total recalculated.
    assert db.session.get(GolfEnrollment, e1.id).total_points == 100_000
    # Bad pick's prior state preserved (NOT cleared to None), usage intact.
    bad = db.session.get(GolfPick, bad_pick_id)
    assert bad.points_earned == 77_000
    assert _usage_player_ids(u2) == {p3.id}
