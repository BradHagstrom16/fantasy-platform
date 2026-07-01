"""PR 3 — Golf major missed-cut/DQ penalty system (TDD, ADR-034).

Faithful port of the standalone's $15/incident side pot:
- ``GolfPick.penalty_triggered`` set at final resolution (major AND active
  result status ∈ {cut, dq}), re-derived True/False every resolution;
- ``GolfPick.refresh_live_penalty()`` for live majors before finalization;
- ``GolfEnrollment.penalty_paid`` + ``penalty_owed()`` / ``penalty_outstanding()``;
- ``GolfPick.show_penalty_badge`` gating player-facing badges;
- ``flask golf refresh-live-penalties`` CLI;
- admin payments AJAX (``penalty_paid``) + pot totals.

Golf tests run against in-memory SQLite via ``create_app('testing')``.
"""
import pytest
from datetime import datetime, timedelta, timezone

from app import create_app
from extensions import db
from models.user import User
from games.golf.models import (
    PENALTY_PER_INCIDENT,
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfTournament,
    GolfTournamentResult,
)
from games.golf.services.sync import SlashGolfAPI, TournamentSync
from tests._registry_helpers import set_status as _set_status

SEASON = 2026


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


# --- seed helpers (run inside the fixture's app context) --------------------

def _make_user(username='golfer', is_admin=False):
    u = User(username=username, email=f'{username}@test.com', is_admin=is_admin)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


def _make_enrollment(user, season_year=SEASON):
    e = GolfEnrollment(user_id=user.id, season_year=season_year, total_points=0)
    db.session.add(e)
    db.session.commit()
    return e


def _make_tournament(name='Test Open', is_major=False, is_team_event=False,
                     status='complete', results_finalized=False, season_year=SEASON):
    now = datetime.now(timezone.utc)
    t = GolfTournament(
        api_tourn_id=f'T-{name}',
        name=name,
        season_year=season_year,
        start_date=now - timedelta(days=4),
        end_date=now - timedelta(days=1),
        pick_deadline=now - timedelta(days=4),
        purse=10_000_000,
        is_major=is_major,
        is_team_event=is_team_event,
        status=status,
        results_finalized=results_finalized,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _make_player(api_id, first, last):
    p = GolfPlayer(api_player_id=api_id, first_name=first, last_name=last)
    db.session.add(p)
    db.session.commit()
    return p


def _make_result(tournament, player, status='complete', rounds_completed=4,
                 earnings=0, final_position='1'):
    r = GolfTournamentResult(
        tournament_id=tournament.id,
        player_id=player.id,
        status=status,
        rounds_completed=rounds_completed,
        earnings=earnings,
        final_position=final_position,
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


def _players(n=2):
    return [_make_player(f'P{i}', 'First', f'Last{i}') for i in range(n)]


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


# ============================================================================
# Column defaults + constant
# ============================================================================

def test_penalty_per_incident_is_15():
    assert PENALTY_PER_INCIDENT == 15


def test_pick_penalty_triggered_defaults_false(app):
    u = _make_user()
    t = _make_tournament(is_major=True)
    p1, p2 = _players()
    pick = _make_pick(u, t, p1, p2)
    assert pick.penalty_triggered is False


def test_enrollment_penalty_paid_defaults_zero(app):
    u = _make_user()
    e = _make_enrollment(u)
    assert e.penalty_paid == 0


# ============================================================================
# resolve_pick() penalty flagging
# ============================================================================

def test_resolve_pick_major_cut_penalty(app):
    """Active pick at a major that finishes CUT triggers the penalty."""
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True)
    primary, backup = _players()
    _make_result(t, primary, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    _make_result(t, backup, status='complete', rounds_completed=4, earnings=500_000)
    pick = _make_pick(u, t, primary, backup)

    assert pick.resolve_pick() is True
    assert pick.penalty_triggered is True


def test_resolve_pick_major_dq_penalty(app):
    """Active pick at a major that is DQ'd triggers the penalty."""
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True)
    primary, backup = _players()
    _make_result(t, primary, status='dq', rounds_completed=3, earnings=0, final_position='DQ')
    _make_result(t, backup, status='complete', rounds_completed=4, earnings=500_000)
    pick = _make_pick(u, t, primary, backup)

    assert pick.resolve_pick() is True
    assert pick.penalty_triggered is True


def test_resolve_pick_major_made_cut_no_penalty(app):
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True)
    primary, backup = _players()
    _make_result(t, primary, status='complete', rounds_completed=4, earnings=1_000_000)
    _make_result(t, backup, status='complete', rounds_completed=4, earnings=500_000)
    pick = _make_pick(u, t, primary, backup)

    assert pick.resolve_pick() is True
    assert pick.penalty_triggered is False


def test_resolve_pick_non_major_cut_no_penalty(app):
    """A cut at a NON-major must not trigger the penalty."""
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=False)
    primary, backup = _players()
    _make_result(t, primary, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    _make_result(t, backup, status='complete', rounds_completed=4, earnings=500_000)
    pick = _make_pick(u, t, primary, backup)

    assert pick.resolve_pick() is True
    assert pick.penalty_triggered is False


def test_resolve_pick_penalty_follows_activated_backup(app):
    """Primary WD before R2 → the activated backup's cut drives the penalty."""
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True)
    primary, backup = _players()
    # Primary WD early (backup activates); backup is CUT → penalty on the backup.
    _make_result(t, primary, status='wd', rounds_completed=1, earnings=0, final_position='WD')
    _make_result(t, backup, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    pick = _make_pick(u, t, primary, backup)

    assert pick.resolve_pick() is True
    assert pick.active_player_id == backup.id
    assert pick.penalty_triggered is True


def test_resolve_pick_both_wd_before_r2_no_penalty(app):
    """Both WD before R2 keeps primary active for 0 pts — status 'wd', not cut/dq."""
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True)
    primary, backup = _players()
    _make_result(t, primary, status='wd', rounds_completed=1, earnings=0, final_position='WD')
    _make_result(t, backup, status='wd', rounds_completed=1, earnings=0, final_position='WD')
    pick = _make_pick(u, t, primary, backup)

    assert pick.resolve_pick() is True
    assert pick.active_player_id == primary.id
    assert pick.penalty_triggered is False


def test_resolve_pick_failure_resets_penalty_triggered(app):
    """A failed resolution (missing result) must clear a stale live penalty flag."""
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True)
    primary, backup = _players()
    # No result rows for either player → the missing-primary early return fires.
    pick = _make_pick(u, t, primary, backup, penalty_triggered=True)

    assert pick.resolve_pick() is False
    assert pick.penalty_triggered is False


def test_resolve_pick_re_derives_penalty_false_on_reresolve(app):
    """No separate clear: a corrected result flips penalty_triggered back to False."""
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True)
    primary, backup = _players()
    r_primary = _make_result(t, primary, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    _make_result(t, backup, status='complete', rounds_completed=4, earnings=500_000)
    pick = _make_pick(u, t, primary, backup)

    pick.resolve_pick()
    assert pick.penalty_triggered is True

    # Corrected: primary actually made the cut and earned money.
    r_primary.status = 'complete'
    r_primary.rounds_completed = 4
    r_primary.earnings = 250_000
    db.session.commit()

    pick.resolve_pick()
    assert pick.penalty_triggered is False


# ============================================================================
# refresh_live_penalty()
# ============================================================================

def test_refresh_live_penalty_flags_active_major_cut(app):
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True, status='active')
    primary, backup = _players()
    _make_result(t, primary, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    _make_result(t, backup, status='active', rounds_completed=2, earnings=0)
    pick = _make_pick(u, t, primary, backup)

    pick.refresh_live_penalty()
    assert pick.penalty_triggered is True


def test_refresh_live_penalty_clears_when_status_recovers(app):
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True, status='active')
    primary, backup = _players()
    r_primary = _make_result(t, primary, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    _make_result(t, backup, status='active', rounds_completed=2, earnings=0)
    pick = _make_pick(u, t, primary, backup)

    pick.refresh_live_penalty()
    assert pick.penalty_triggered is True

    r_primary.status = 'active'
    db.session.commit()
    pick.refresh_live_penalty()
    assert pick.penalty_triggered is False


def test_refresh_live_penalty_non_major_always_false(app):
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=False, status='active')
    primary, backup = _players()
    _make_result(t, primary, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    _make_result(t, backup, status='active', rounds_completed=2, earnings=0)
    pick = _make_pick(u, t, primary, backup, penalty_triggered=True)

    pick.refresh_live_penalty()
    assert pick.penalty_triggered is False


def test_refresh_live_penalty_uses_activated_backup(app):
    """Live: primary WD before R2 → the activated backup's cut flags the penalty."""
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True, status='active')
    primary, backup = _players()
    _make_result(t, primary, status='wd', rounds_completed=1, earnings=0, final_position='WD')
    _make_result(t, backup, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    pick = _make_pick(u, t, primary, backup)

    pick.refresh_live_penalty()
    assert pick.penalty_triggered is True


def test_is_backup_activated_complete_unresolved_early_primary_wd(app):
    """A complete-but-unresolved major (active_player_id unset) still activates the
    backup when the primary withdrew early — the CLI refresh window."""
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True, status='complete', results_finalized=False)
    primary, backup = _players()
    _make_result(t, primary, status='wd', rounds_completed=1, earnings=0, final_position='WD')
    _make_result(t, backup, status='complete', rounds_completed=4, earnings=400_000)
    pick = _make_pick(u, t, primary, backup)  # active_player_id unset

    assert pick.is_backup_activated() is True


def test_refresh_live_penalty_complete_unresolved_uses_backup(app):
    """CLI refresh on a complete-but-unresolved major must read the activated
    backup's cut, not the withdrawn primary — no side-pot skew."""
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True, status='complete', results_finalized=False)
    primary, backup = _players()
    _make_result(t, primary, status='wd', rounds_completed=1, earnings=0, final_position='WD')
    _make_result(t, backup, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    pick = _make_pick(u, t, primary, backup)

    pick.refresh_live_penalty()
    assert pick.penalty_triggered is True


# ============================================================================
# penalty_owed / penalty_outstanding
# ============================================================================

def test_penalty_owed_counts_flagged_picks(app):
    u = _make_user()
    e = _make_enrollment(u)
    p1, p2 = _players()
    for i in range(3):
        t = _make_tournament(name=f'Major {i}', is_major=True)
        _make_pick(u, t, p1, p2, penalty_triggered=True)
    assert e.penalty_owed() == 3 * PENALTY_PER_INCIDENT  # 45


def test_penalty_owed_ignores_unflagged_picks(app):
    u = _make_user()
    e = _make_enrollment(u)
    p1, p2 = _players()
    t1 = _make_tournament(name='Major A', is_major=True)
    _make_pick(u, t1, p1, p2, penalty_triggered=True)
    t2 = _make_tournament(name='Major B', is_major=True)
    _make_pick(u, t2, p1, p2, penalty_triggered=False)
    assert e.penalty_owed() == 15


def test_penalty_owed_is_season_scoped(app):
    u = _make_user()
    e = _make_enrollment(u, season_year=2026)
    p1, p2 = _players()
    t_this = _make_tournament(name='This Year Major', is_major=True, season_year=2026)
    _make_pick(u, t_this, p1, p2, penalty_triggered=True)
    t_prior = _make_tournament(name='Prior Year Major', is_major=True, season_year=2025)
    _make_pick(u, t_prior, p1, p2, penalty_triggered=True)
    # Only the 2026 flagged pick counts for the 2026 enrollment.
    assert e.penalty_owed() == 15


def test_penalty_outstanding_subtracts_paid(app):
    u = _make_user()
    e = _make_enrollment(u)
    p1, p2 = _players()
    for i in range(2):
        t = _make_tournament(name=f'Major {i}', is_major=True)
        _make_pick(u, t, p1, p2, penalty_triggered=True)
    e.penalty_paid = 15
    db.session.commit()
    assert e.penalty_owed() == 30
    assert e.penalty_outstanding() == 15


def test_penalty_outstanding_clamps_at_zero(app):
    u = _make_user()
    e = _make_enrollment(u)
    p1, p2 = _players()
    t = _make_tournament(name='Major', is_major=True)
    _make_pick(u, t, p1, p2, penalty_triggered=True)
    e.penalty_paid = 50
    db.session.commit()
    assert e.penalty_owed() == 15
    assert e.penalty_outstanding() == 0


# ============================================================================
# show_penalty_badge gating
# ============================================================================

def test_show_penalty_badge_active_major(app):
    u = _make_user()
    t = _make_tournament(is_major=True, status='active', results_finalized=False)
    p1, p2 = _players()
    pick = _make_pick(u, t, p1, p2, penalty_triggered=True)
    assert pick.show_penalty_badge is True


def test_show_penalty_badge_finalized_major(app):
    u = _make_user()
    t = _make_tournament(is_major=True, status='complete', results_finalized=True)
    p1, p2 = _players()
    pick = _make_pick(u, t, p1, p2, penalty_triggered=True)
    assert pick.show_penalty_badge is True


def test_show_penalty_badge_hidden_complete_not_finalized(app):
    """Complete-but-not-yet-finalized limbo must not show a premature badge."""
    u = _make_user()
    t = _make_tournament(is_major=True, status='complete', results_finalized=False)
    p1, p2 = _players()
    pick = _make_pick(u, t, p1, p2, penalty_triggered=True)
    assert pick.show_penalty_badge is False


def test_show_penalty_badge_hidden_non_major(app):
    u = _make_user()
    t = _make_tournament(is_major=False, status='complete', results_finalized=True)
    p1, p2 = _players()
    pick = _make_pick(u, t, p1, p2, penalty_triggered=True)
    assert pick.show_penalty_badge is False


def test_show_penalty_badge_hidden_when_not_triggered(app):
    u = _make_user()
    t = _make_tournament(is_major=True, status='complete', results_finalized=True)
    p1, p2 = _players()
    pick = _make_pick(u, t, p1, p2, penalty_triggered=False)
    assert pick.show_penalty_badge is False


# ============================================================================
# process_tournament_picks end-to-end flags the penalty
# ============================================================================

def test_process_tournament_picks_flags_penalty(app):
    u = _make_user()
    _make_enrollment(u)
    # recap pre-marked so the results-recap email path is skipped in the test.
    t = _make_tournament(is_major=True, status='complete')
    t.recap_email_sent = True
    db.session.commit()
    primary, backup = _players()
    _make_result(t, primary, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    _make_result(t, backup, status='complete', rounds_completed=4, earnings=500_000)
    pick = _make_pick(u, t, primary, backup)

    sync = TournamentSync(SlashGolfAPI('key'))
    sync.process_tournament_picks(t)

    db.session.expire_all()
    refreshed = db.session.get(GolfPick, pick.id)
    assert refreshed.penalty_triggered is True


def test_sync_live_leaderboard_penalty_refresh_failure_does_not_mask_sync(app, monkeypatch):
    """A penalty-refresh failure must not roll back or fail the leaderboard sync
    that already committed (ADR-034 isolation)."""
    from games.golf.services import sync as sync_mod

    t = _make_tournament(name='Masters Tournament', is_major=True, status='active')
    p = _make_player('MX', 'Major', 'Player')

    class _FakeAPI:
        def get_leaderboard(self, tourn_id, year):
            return {"status": "In Progress", "leaderboardRows": [
                {"playerId": "MX", "position": "1", "total": "-10",
                 "status": "active", "rounds": [1, 2]},
            ]}

    def _boom(tournament):
        raise RuntimeError("penalty refresh blew up")

    monkeypatch.setattr(sync_mod, 'refresh_tournament_penalties', _boom)

    sync = sync_mod.TournamentSync(_FakeAPI())
    updated = sync.sync_live_leaderboard(t)

    # Sync reports success and the leaderboard result persisted despite the
    # penalty-refresh blowing up.
    assert updated == 1
    r = GolfTournamentResult.query.filter_by(tournament_id=t.id, player_id=p.id).first()
    assert r is not None and r.earnings > 0


def test_process_tournament_picks_clears_stale_penalty_on_skipped_pick(app):
    """A pick that fails to resolve (missing result) is rolled back by its
    savepoint; its stale live penalty flag must still be cleared before commit so
    the admin pot doesn't count an unresolved pick."""
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True, status='complete')
    t.recap_email_sent = True
    db.session.commit()
    primary, backup = _players()
    # No result rows → resolve_pick returns False → this pick is skipped.
    pick = _make_pick(u, t, primary, backup, penalty_triggered=True)

    sync = TournamentSync(SlashGolfAPI('key'))
    sync.process_tournament_picks(t)

    db.session.expire_all()
    assert db.session.get(GolfPick, pick.id).penalty_triggered is False


# ============================================================================
# refresh-live-penalties CLI
# ============================================================================

def test_refresh_live_penalties_cli_flags_active_majors(app):
    u = _make_user()
    _make_enrollment(u)
    t = _make_tournament(is_major=True, status='active')
    primary, backup = _players()
    _make_result(t, primary, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    _make_result(t, backup, status='active', rounds_completed=2, earnings=0)
    pick = _make_pick(u, t, primary, backup)
    pick_id = pick.id

    runner = app.test_cli_runner()
    result = runner.invoke(args=['golf', 'refresh-live-penalties'])
    assert result.exit_code == 0

    db.session.expire_all()
    assert db.session.get(GolfPick, pick_id).penalty_triggered is True


# ============================================================================
# Admin payments AJAX + page
# ============================================================================

def test_admin_update_payment_sets_penalty_paid(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    _make_enrollment(member)
    _login(client, admin)

    resp = client.post(f'/golf/admin/update-payment/{member.id}',
                       json={'penalty_paid': 30})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['penalty_paid'] == 30
    with app.app_context():
        e = GolfEnrollment.query.filter_by(user_id=member.id, season_year=SEASON).first()
        assert e.penalty_paid == 30


def test_admin_update_payment_clamps_negative_penalty(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    _make_enrollment(member)
    _login(client, admin)

    resp = client.post(f'/golf/admin/update-payment/{member.id}',
                       json={'penalty_paid': -5})
    assert resp.status_code == 200
    assert resp.get_json()['penalty_paid'] == 0


def test_admin_update_payment_rejects_non_integer_penalty(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    _make_enrollment(member)
    _login(client, admin)

    resp = client.post(f'/golf/admin/update-payment/{member.id}',
                       json={'penalty_paid': 'abc'})
    assert resp.status_code == 400


def test_admin_update_payment_rejects_fractional_penalty(app, client, monkeypatch):
    """A JSON float must be rejected, not silently truncated to an int."""
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    _make_enrollment(member)
    _login(client, admin)

    resp = client.post(f'/golf/admin/update-payment/{member.id}',
                       json={'penalty_paid': 12.75})
    assert resp.status_code == 400
    with app.app_context():
        e = GolfEnrollment.query.filter_by(user_id=member.id, season_year=SEASON).first()
        assert e.penalty_paid == 0  # unchanged, NOT truncated to 12


def test_admin_update_payment_penalty_only_preserves_has_paid(app, client, monkeypatch):
    """A penalty-only update must not reset the entry-fee paid flag."""
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    e = _make_enrollment(member)
    e.has_paid = True
    db.session.commit()
    _login(client, admin)

    resp = client.post(f'/golf/admin/update-payment/{member.id}',
                       json={'penalty_paid': 15})
    assert resp.status_code == 200
    with app.app_context():
        refreshed = GolfEnrollment.query.filter_by(user_id=member.id, season_year=SEASON).first()
        assert refreshed.has_paid is True
        assert refreshed.penalty_paid == 15


def test_admin_payments_page_shows_penalty_pot(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    admin = _make_user('gadmin', is_admin=True)
    member = _make_user('member')
    _make_enrollment(member)
    p1, p2 = _players()
    for i in range(2):
        t = _make_tournament(name=f'Major {i}', is_major=True, status='complete', results_finalized=True)
        _make_pick(member, t, p1, p2, penalty_triggered=True)
    _login(client, admin)

    resp = client.get('/golf/admin/payments')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Penalty' in body
    # Pot = 2 flagged picks x $15 = $30
    assert '30' in body


# ============================================================================
# Player-facing badge/prize-pool rendering
# ============================================================================

def test_index_prize_pool_includes_penalty_pot(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    member = _make_user('member')
    _make_enrollment(member)
    p1, p2 = _players()
    for i in range(2):
        t = _make_tournament(name=f'Major {i}', is_major=True, status='complete', results_finalized=True)
        _make_pick(member, t, p1, p2, penalty_triggered=True)

    resp = client.get('/golf/')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Prize Pool' in body
    assert '$30' in body  # penalty pot = 2 x $15


def test_tournament_detail_shows_penalty_badge_for_finalized_major(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    member = _make_user('member')
    _make_enrollment(member)
    t = _make_tournament(is_major=True, status='complete', results_finalized=True)
    primary, backup = _players()
    _make_result(t, primary, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    _make_result(t, backup, status='complete', rounds_completed=4, earnings=500_000)
    pick = _make_pick(member, t, primary, backup)
    pick.resolve_pick()
    db.session.commit()

    resp = client.get(f'/golf/tournament/{t.id}')
    assert resp.status_code == 200
    assert 'badge-penalty' in resp.get_data(as_text=True)


def test_tournament_detail_hides_penalty_badge_when_not_finalized(app, client, monkeypatch):
    """Complete-but-not-finalized major must not render a premature badge."""
    _set_status(monkeypatch, 'golf', 'open')
    member = _make_user('member')
    _make_enrollment(member)
    t = _make_tournament(is_major=True, status='complete', results_finalized=False)
    primary, backup = _players()
    _make_result(t, primary, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    _make_result(t, backup, status='complete', rounds_completed=4, earnings=500_000)
    pick = _make_pick(member, t, primary, backup)
    pick.resolve_pick()
    db.session.commit()

    resp = client.get(f'/golf/tournament/{t.id}')
    assert resp.status_code == 200
    assert 'badge-penalty' not in resp.get_data(as_text=True)


def test_my_picks_shows_penalty_badge_for_finalized_major(app, client, monkeypatch):
    _set_status(monkeypatch, 'golf', 'open')
    member = _make_user('member')
    _make_enrollment(member)
    t = _make_tournament(is_major=True, status='complete', results_finalized=True)
    primary, backup = _players()
    _make_result(t, primary, status='cut', rounds_completed=2, earnings=0, final_position='CUT')
    _make_result(t, backup, status='complete', rounds_completed=4, earnings=500_000)
    pick = _make_pick(member, t, primary, backup)
    pick.resolve_pick()
    db.session.commit()
    _login(client, member)

    resp = client.get('/golf/my-picks')
    assert resp.status_code == 200
    assert 'badge-penalty' in resp.get_data(as_text=True)
