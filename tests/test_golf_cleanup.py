"""PR 6 — Golf cleanups & test backfill (TDD).

Mirrors the CFB §9 cleanup pass. Two flavours of coverage live here:

Test backfill (regression locks on already-shipped behaviour the audit's
recommended suite named but PRs 1-5 never explicitly locked):
- ``update_status_from_time`` derives active/upcoming from the clock but NEVER
  auto-sets ``complete`` (only a results sync may finalize).
- ``GolfPick.validate_availability`` rejects a used-this-season player and a
  non-field player.
- ``GolfEnrollment.calculate_total_points`` carries the major x1.5 through the
  season aggregate (the resolve-time multiplier survives the sum).

New-behaviour locks (RED before the PR 6 implementation lands):
- ``index()`` standings + ``tournament_detail()`` picks eager-load their user /
  player relationships, so query count is invariant to row count (no N+1).
- ``sync_tournament_results`` short-circuits an already-finalized tournament
  (no API round-trip) unless ``force=True``.
- ``GolfTournamentField.is_alternate`` (dead column) is gone.

Golf tests run against in-memory SQLite via ``create_app('testing')``.
"""
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event

from app import create_app
from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfSeasonPlayerUsage,
    GolfTournament,
    GolfTournamentField,
    GolfTournamentResult,
)
from games.golf.services.sync import TournamentSync
from models.user import User

SEASON = 2026


@pytest.fixture()
def app():
    app = create_app('testing')
    # Pin the season so seed helpers and route/query season-scoping agree even
    # if the testing-config default ever drifts.
    app.config['SEASON_YEAR'] = SEASON
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


# --- seed helpers (run inside the fixture's app context) --------------------

def _make_user(username='golfer', is_admin=False, display_name=None, avatar=None):
    u = User(username=username, email=f'{username}@test.com', is_admin=is_admin,
             display_name=display_name, avatar_emoji=avatar)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    return u


def _make_enrollment(user, season_year=SEASON):
    e = GolfEnrollment(user_id=user.id, season_year=season_year, total_points=0)
    db.session.add(e)
    db.session.commit()
    return e


def _make_tournament(name='Test Open', api_tourn_id=None, is_major=False,
                     is_team_event=False, status='complete',
                     results_finalized=False, purse=10_000_000, season_year=SEASON,
                     start_offset_days=4, end_offset_days=1, deadline_offset_days=4):
    now = datetime.now(UTC)
    t = GolfTournament(
        api_tourn_id=api_tourn_id or f'T-{name}',
        name=name,
        season_year=season_year,
        start_date=now - timedelta(days=start_offset_days),
        end_date=now - timedelta(days=end_offset_days),
        pick_deadline=now - timedelta(days=deadline_offset_days),
        purse=purse,
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


def _add_to_field(tournament, player):
    fe = GolfTournamentField(tournament_id=tournament.id, player_id=player.id)
    db.session.add(fe)
    db.session.commit()
    return fe


def _mark_used(user, player, season_year=SEASON):
    usage = GolfSeasonPlayerUsage(
        user_id=user.id, player_id=player.id, season_year=season_year
    )
    db.session.add(usage)
    db.session.commit()
    return usage


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


@contextmanager
def _count_sql():
    """Count SQL statements executed against the bound engine."""
    engine = db.engine
    counter = {'n': 0}

    def _before(conn, cursor, statement, parameters, context, executemany):
        counter['n'] += 1

    event.listen(engine, 'before_cursor_execute', _before)
    try:
        yield counter
    finally:
        event.remove(engine, 'before_cursor_execute', _before)


class _CountingAPI:
    """SlashGolfAPI stand-in that counts endpoint calls and returns canned data."""

    def __init__(self, leaderboard=None, earnings=None, schedule=None):
        self._leaderboard = leaderboard
        self._earnings = earnings
        self._schedule = schedule
        self.calls = {'leaderboard': 0, 'earnings': 0, 'schedule': 0}

    def get_leaderboard(self, tourn_id, year):
        self.calls['leaderboard'] += 1
        return self._leaderboard

    def get_earnings(self, tourn_id, year):
        self.calls['earnings'] += 1
        return self._earnings

    def get_schedule(self, year):
        self.calls['schedule'] += 1
        return self._schedule


# ============================================================================
# Test backfill — status state machine (audit §4)
# ============================================================================

def test_update_status_from_time_never_auto_completes(app):
    """Time flips upcoming -> active but NEVER active/complete on its own.

    Only a results sync (API-verified) may finalize. A tournament whose end
    date is in the past must still read 'active', not 'complete'.
    """
    t = _make_tournament(name='Clock Open', status='upcoming')
    now = datetime.now(UTC)

    # Before the deadline: stays upcoming.
    t.pick_deadline = now + timedelta(days=2)
    t.start_date = now + timedelta(days=2)
    t.end_date = now + timedelta(days=5)
    assert t.update_status_from_time(now) == 'upcoming'

    # Past the deadline, tournament under way: active.
    assert t.update_status_from_time(now + timedelta(days=3)) == 'active'

    # Past the END date, from a FRESH upcoming tournament: STILL active — never
    # auto-completed. Using a fresh instance proves the past-end branch itself,
    # not merely that an already-active status is left unchanged.
    t2 = _make_tournament(name='Clock Open 2', status='upcoming')
    t2.pick_deadline = now + timedelta(days=2)
    t2.start_date = now + timedelta(days=2)
    t2.end_date = now + timedelta(days=5)
    assert t2.update_status_from_time(now + timedelta(days=6)) == 'active'
    assert t2.status != 'complete'


def test_update_status_from_time_leaves_complete_untouched(app):
    """An already-complete tournament is never walked back to active/upcoming."""
    t = _make_tournament(name='Done Open', status='complete')
    assert t.update_status_from_time(datetime.now(UTC)) == 'complete'


# ============================================================================
# Test backfill — pick availability validation (audit §2 / §8)
# ============================================================================

def test_validate_availability_rejects_used_player(app):
    """A primary/backup already used this season is rejected."""
    user = _make_user()
    t = _make_tournament(status='upcoming')
    primary = _make_player('U1', 'Used', 'Primary')
    backup = _make_player('U2', 'Fresh', 'Backup')
    _add_to_field(t, primary)
    _add_to_field(t, backup)
    _mark_used(user, primary)  # primary already burned this season

    pick = GolfPick(user_id=user.id, tournament_id=t.id,
                    primary_player_id=primary.id, backup_player_id=backup.id)
    errors = pick.validate_availability(SEASON)

    # Exact match: only the used-player error, nothing else (both are in-field).
    assert errors == ['Primary player has already been used this season.']


def test_validate_availability_rejects_non_field_player(app):
    """A primary/backup outside the tournament field is rejected."""
    user = _make_user()
    t = _make_tournament(status='upcoming')
    in_field = _make_player('F1', 'In', 'Field')
    off_field = _make_player('F2', 'Off', 'Field')
    _add_to_field(t, in_field)  # only the primary is in the field

    pick = GolfPick(user_id=user.id, tournament_id=t.id,
                    primary_player_id=in_field.id, backup_player_id=off_field.id)
    errors = pick.validate_availability(SEASON)

    # Exact match: only the non-field backup error (neither player is used).
    assert errors == ['Backup player is not in the tournament field.']


# ============================================================================
# Test backfill — season aggregate carries the major multiplier (audit §8)
# ============================================================================

def test_calculate_total_points_major_multiplier(app):
    """A completed major contributes earnings x1.5 to the enrollment total.

    resolve_pick() stores the multiplied value in points_earned; the season
    aggregate must sum that already-multiplied figure (no second multiply,
    no dropped multiplier).
    """
    user = _make_user()
    enrollment = _make_enrollment(user)
    t = _make_tournament(name='Masters', is_major=True, status='complete')
    p1 = _make_player('M1', 'Major', 'Primary')
    p2 = _make_player('M2', 'Major', 'Backup')
    _make_result(t, p1, earnings=100_000)
    _make_result(t, p2, earnings=50_000)
    pick = _make_pick(user, t, p1, p2)

    assert pick.resolve_pick() is True
    assert pick.points_earned == 150_000  # 100_000 * 1.5 (resolve-time)

    total = enrollment.calculate_total_points()
    assert total == 150_000
    assert enrollment.total_points == 150_000


# ============================================================================
# N+1 eager-loading (audit §5) — query count invariant to row count
# ============================================================================

def test_index_standings_avoids_per_user_query(app, client):
    """index() eager-loads enrollment.user, so the standings query count does
    not grow with the number of enrollees (no N+1)."""
    # Warm the before_request status-refresh throttle so both measured requests
    # skip it identically.
    assert client.get('/golf/').status_code == 200

    for i in range(2):
        _make_enrollment(_make_user(f'g{i}', display_name=f'Golfer{i}'))
    db.session.remove()
    with _count_sql() as c2:
        assert client.get('/golf/').status_code == 200
    n2 = c2['n']

    for i in range(2, 5):
        _make_enrollment(_make_user(f'g{i}', display_name=f'Golfer{i}'))
    db.session.remove()
    with _count_sql() as c5:
        assert client.get('/golf/').status_code == 200
    n5 = c5['n']

    assert n5 == n2, (
        f'index() standings issue a per-enrollee query (N+1): {n2} -> {n5} '
        f'as enrollees went 2 -> 5'
    )


def test_tournament_detail_avoids_per_pick_query(app, client):
    """tournament_detail() eager-loads pick user/primary/backup/active, so the
    query count does not grow with the number of picks (no N+1)."""
    t = _make_tournament(name='Detail Open', status='complete', results_finalized=True)
    # Capture ids before any db.session.remove() detaches these instances.
    tid = t.id
    pids = [_make_player(f'D{i}', 'Pick', f'Player{i}').id for i in range(10)]

    def _add_pick(idx):
        # Re-fetch fresh, session-bound instances (a prior remove() detached them).
        tour = db.session.get(GolfTournament, tid)
        primary = db.session.get(GolfPlayer, pids[2 * idx])
        backup = db.session.get(GolfPlayer, pids[2 * idx + 1])
        user = _make_user(f'tp{idx}', display_name=f'Player{idx}')
        _make_result(tour, primary, earnings=100_000, final_position='1')
        _make_result(tour, backup, earnings=0, final_position='40')
        _make_pick(user, tour, primary, backup, active_player_id=primary.id,
                   points_earned=100_000, primary_used=True)

    # Warm the status-refresh throttle.
    assert client.get(f'/golf/tournament/{tid}').status_code == 200

    _add_pick(0)
    _add_pick(1)
    db.session.remove()
    with _count_sql() as c2:
        assert client.get(f'/golf/tournament/{tid}').status_code == 200
    n2 = c2['n']

    _add_pick(2)
    _add_pick(3)
    db.session.remove()
    with _count_sql() as c4:
        assert client.get(f'/golf/tournament/{tid}').status_code == 200
    n4 = c4['n']

    assert n4 == n2, (
        f'tournament_detail() issues per-pick relationship queries (N+1): '
        f'{n2} -> {n4} as picks went 2 -> 4'
    )


# ============================================================================
# Results-sync short-circuit on already-finalized tournaments (audit §4)
# ============================================================================

def test_sync_results_short_circuits_when_finalized(app):
    """An already-finalized tournament is skipped without an API round-trip."""
    t = _make_tournament(name='Finalized Open', status='complete',
                         results_finalized=True)
    api = _CountingAPI(
        leaderboard={'status': 'Official', 'leaderboardRows': []},
        earnings={'leaderboard': []},
    )
    sync = TournamentSync(api)

    n = sync.sync_tournament_results(t)

    assert n == 0
    # No API round-trip at all — every endpoint counter stays at zero.
    assert api.calls == {'leaderboard': 0, 'earnings': 0, 'schedule': 0}


def test_sync_results_force_reprocesses_finalized(app):
    """force=True re-runs a finalized tournament (API is called, rows written)."""
    t = _make_tournament(name='Force Open', api_tourn_id='F99', status='complete',
                         results_finalized=True)
    player = _make_player('F99A', 'Force', 'Player')
    api = _CountingAPI(
        leaderboard={'status': 'Official', 'leaderboardRows': [
            {'playerId': 'F99A', 'position': '1', 'total': '-10',
             'status': 'complete', 'rounds': [1, 2, 3, 4]},
        ]},
        earnings={'leaderboard': [
            {'playerId': 'F99A', 'position': '1', 'earnings': {'$numberInt': '500000'}},
        ]},
    )
    sync = TournamentSync(api)

    n = sync.sync_tournament_results(t, force=True)

    assert n == 1
    assert api.calls['leaderboard'] == 1
    r = GolfTournamentResult.query.filter_by(
        tournament_id=t.id, player_id=player.id).first()
    assert r is not None
    assert r.earnings == 500_000


# ============================================================================
# Dead-column removal (audit §9)
# ============================================================================

def test_golf_tournament_field_has_no_is_alternate(app):
    """The unused is_alternate column/attribute is gone (dropped by migration)."""
    assert not hasattr(GolfTournamentField, 'is_alternate')
