"""Tests for the public /worldcup/leaderboard route — payload + new data shapes.

Plan 3 adds three payload keys:
- your_standing: None | dict (rank-neighbor data for authenticated+enrolled user)
- trend_by_enrollment: dict[int, float | None] mapping enrollment.id -> trend score
- show_trend_column: bool (gated on count(distinct captured_date) >= 7)

Trend semantics (per spec §8 + plan ambiguity-A2):
  trend = enrollment.total_score - latest_snapshot.total_score for that enrollment
  None if no snapshot exists for that enrollment
"""
import pytest
from datetime import date, datetime, timezone, timedelta

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupRankSnapshot,
)


PAST_DEADLINE = datetime(2000, 1, 1, tzinfo=timezone.utc)
FUTURE_DEADLINE = datetime(2099, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _seed_user(username, password='pass'):
    u = User(username=username, email=f'{username}@test.com')
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    return u


def _seed_enrollment(user_id, score, usa_goals_guess=5):
    e = WorldCupEnrollment(
        user_id=user_id, season_year=SEASON_YEAR,
        picks_submitted=True, total_score=score,
        usa_goals_guess=usa_goals_guess,
    )
    db.session.add(e)
    db.session.flush()
    return e


def _seed_snapshot(enrollment_id, captured_date, rank, total_score):
    s = WorldCupRankSnapshot(
        enrollment_id=enrollment_id,
        captured_date=captured_date,
        rank=rank,
        total_score=total_score,
    )
    db.session.add(s)
    db.session.flush()
    return s


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


# ── your_standing block ──────────────────────────────────────────────

def test_your_position_block_renders_for_authenticated_enrolled_user(client, app):
    """Authenticated + enrolled user sees the Your Position tribune block (P1 S1.1)."""
    with app.app_context():
        u = _seed_user('alice')
        _seed_enrollment(u.id, score=42.0)
        db.session.commit()
        _login(client, u.id)
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Your Position' in resp.data
    assert b'your-standing-tribune' in resp.data


def test_anonymous_viewer_sees_join_callout(client, app):
    """Anon viewer gets the editorial join callout, not silence (P1 S1.1)."""
    with app.app_context():
        u = _seed_user('alice')
        _seed_enrollment(u.id, score=42.0)
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Your Position' not in resp.data  # owner block is gated on enrollment
    assert b'your-standing-tribune-empty' in resp.data
    assert b'Join the pool' in resp.data


def test_authenticated_unenrolled_viewer_sees_join_callout(client, app):
    """Authenticated but unenrolled user sees the join callout, not silence."""
    with app.app_context():
        u_enr = _seed_user('alice')
        _seed_enrollment(u_enr.id, score=42.0)
        u_unenr = _seed_user('bob')  # No enrollment
        db.session.commit()
        _login(client, u_unenr.id)
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Your Position' not in resp.data
    assert b'your-standing-tribune-empty' in resp.data
    assert b'Join the pool' in resp.data


def test_standing_caption_voices_lead_and_chase(client, app):
    """Five-enrollment fixture, mid-rank user — caption surfaces both deltas.

    With scores [100, 80, 60, 40, 20] and target rank 3 (score 60):
      lead_delta_up   = 100 - 60 = 40.0  ("40 from the top")
      lead_delta_down = 60 - 40  = 20.0  ("20 ahead of the chase")
    No snapshot history so rank_delta is None, hitting the "Holding" branch.
    """
    with app.app_context():
        users = [_seed_user(f'p{i}') for i in range(5)]
        _seed_enrollment(users[0].id, 100.0)
        _seed_enrollment(users[1].id, 80.0)
        _seed_enrollment(users[2].id, 60.0)
        _seed_enrollment(users[3].id, 40.0)
        _seed_enrollment(users[4].id, 20.0)
        db.session.commit()
        _login(client, users[2].id)
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'Holding 3. 40 from the top, 20 ahead of the chase.' in body


# ── trend column ─────────────────────────────────────────────────────

def test_trend_column_uses_latest_snapshot(client, app):
    """Per-row trend = current_score - latest_snapshot_score for that enrollment.

    Latest = max(captured_date). Verify by seeding a snapshot a few days back
    AND a more recent snapshot — the more recent should win the diff.
    """
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=50.0)
        # Seed 8 distinct dates so the gate opens (see A1 below).
        today = date.today()
        for i in range(8):
            # Enrollment's snapshots: oldest=10 pts, latest (i=0) = 47 pts
            _seed_snapshot(
                enrollment_id=e.id,
                captured_date=today - timedelta(days=i + 1),
                rank=1,
                total_score=10.0 + (7 - i) * 5.0,  # newest captured_date = highest score
            )
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    # Latest snapshot was yesterday at 45.0 (i=0 -> 10 + 35 = 45.0)
    # Current score 50.0 -> trend = +5.0
    # Page renders +5.0 (some formatting tolerance).
    assert b'+5.0' in resp.data or b'+5' in resp.data


def test_trend_column_hidden_when_fewer_than_seven_snapshots(client, app):
    """show_trend_column = False when count(distinct captured_date) < 7.

    Per ambiguity-A1 resolution: gate is on distinct captured_date count
    across the whole table — not per-user.
    """
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=50.0)
        # Only 6 distinct dates → gate stays closed
        today = date.today()
        for i in range(6):
            _seed_snapshot(
                enrollment_id=e.id,
                captured_date=today - timedelta(days=i + 1),
                rank=1,
                total_score=40.0,
            )
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    # P1 S1.1: column header is now "Move" (rank-delta). The gate still
    # protects it the same way — under 7 distinct snapshot days, the column
    # is absent entirely (no Pending column polluting the empty table).
    assert b'<th scope="col" class="text-end">Move</th>' not in resp.data


def test_trend_column_gate_scoped_to_active_season(client, app):
    """Snapshots from a previous season must not open the gate for the active season.

    Without season-scoping, prior-cup snapshots would falsely satisfy the
    >= 7 distinct captured_date threshold at the start of a new season.
    """
    with app.app_context():
        # Active-season enrollment with only 3 snapshot days — gate must stay closed.
        active_user = _seed_user('alice')
        active_e = _seed_enrollment(active_user.id, score=50.0)
        today = date.today()
        for i in range(3):
            _seed_snapshot(
                enrollment_id=active_e.id,
                captured_date=today - timedelta(days=i + 1),
                rank=1,
                total_score=40.0,
            )

        # Prior-season enrollment with 10 distinct days — must NOT count toward the gate.
        prior_user = _seed_user('archie')
        prior_e = WorldCupEnrollment(
            user_id=prior_user.id,
            season_year=SEASON_YEAR - 4,  # prior World Cup
            picks_submitted=True, total_score=99.0,
            usa_goals_guess=5,
        )
        db.session.add(prior_e)
        db.session.flush()
        for i in range(10):
            _seed_snapshot(
                enrollment_id=prior_e.id,
                captured_date=date(2022, 11, 20) + timedelta(days=i),
                rank=1,
                total_score=10.0 + i,
            )
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    # Active season has only 3 days of snapshot history — Move column stays
    # closed despite the 10 prior-season days that exist in the table.
    assert b'<th scope="col" class="text-end">Move</th>' not in resp.data


def test_move_column_shows_pending_when_no_prior_snapshot_for_user(client, app):
    """When a row has no snapshot history but the column is open, render 'Pending'.

    P1 S1.1: replaces the old em-dash placeholder with a voiced word; em-dashes
    are banned from user copy by P0 S0.3."""
    with app.app_context():
        u_with = _seed_user('alice')
        e_with = _seed_enrollment(u_with.id, score=50.0)
        u_without = _seed_user('bob')
        _seed_enrollment(u_without.id, score=30.0)
        # Open the gate by seeding 7 distinct dates against alice only.
        # bob has no snapshot history.
        today = date.today()
        for i in range(7):
            _seed_snapshot(
                enrollment_id=e_with.id,
                captured_date=today - timedelta(days=i + 1),
                rank=1,
                total_score=40.0,
            )
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'<th scope="col" class="text-end">Move</th>' in resp.data
    body = resp.data.decode()
    assert 'bob' in body
    # Bob has no snapshot history; his row's Move cell reads "Pending".
    assert 'Pending' in body


# ── basic reskin smoke (Tasks 2-4 will harden) ────────────────────────

def test_leaderboard_route_still_returns_200_with_no_data(client, app):
    """Empty leaderboard renders the new editorial empty-state copy (P1 S1.1)."""
    with app.app_context():
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'The ledger awaits its first name.' in resp.data
    assert b'Lock your roster.' in resp.data
