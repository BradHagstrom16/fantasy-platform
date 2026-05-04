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

def test_your_standing_block_renders_for_authenticated_enrolled_user(client, app):
    """Authenticated + enrolled user sees Your Standing block in payload + DOM."""
    with app.app_context():
        u = _seed_user('alice')
        _seed_enrollment(u.id, score=42.0)
        db.session.commit()
        _login(client, u.id)
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Your Standing' in resp.data


def test_your_standing_omitted_for_anonymous(client, app):
    """Anonymous user does not see Your Standing block."""
    with app.app_context():
        u = _seed_user('alice')
        _seed_enrollment(u.id, score=42.0)
        db.session.commit()
        # No login
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Your Standing' not in resp.data


def test_your_standing_omitted_for_authenticated_unenrolled(client, app):
    """Authenticated but unenrolled user does not see Your Standing block."""
    with app.app_context():
        u_enr = _seed_user('alice')
        _seed_enrollment(u_enr.id, score=42.0)
        u_unenr = _seed_user('bob')  # No enrollment
        db.session.commit()
        _login(client, u_unenr.id)
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Your Standing' not in resp.data


def test_lead_delta_calculation(client, app):
    """Five-enrollment fixture with known scores — Your Standing caption reflects neighbors.

    Caption format from _your_standing_caption: '{up} pts from 1st · {down} ahead of next.'
    With scores [100, 80, 60, 40, 20] and target rank 3 (score 60):
      up = 100 - 60 = 40.0  (rounded to 2 decimals -> 40.0)
      down = 60 - 40 = 20.0
    """
    with app.app_context():
        users = [_seed_user(f'p{i}') for i in range(5)]
        # scores: 100 (rank 1), 80 (rank 2), 60 (rank 3, target), 40 (rank 4), 20 (rank 5)
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
    # Verify the literal caption rendered. The leader/tail/sole variants use
    # different copy, so a hit on this exact phrase confirms the mid-rank path
    # AND the deltas are correct.
    assert '40.0 pts from 1st · 20.0 ahead of next.' in body


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
    # The literal column header "Trend" must not appear in the desktop table
    # OR mobile-card line — but other usages of the word "trend" in templates
    # are fine. Gate by the unique <th> markup.
    assert b'<th class="text-end">Trend</th>' not in resp.data


def test_trend_column_shows_dash_when_no_prior_snapshot_for_user(client, app):
    """When a row has no snapshot history but the column is open, render '—'."""
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
    # Column is open
    assert b'<th class="text-end">Trend</th>' in resp.data
    # Bob's row trend cell renders '—'
    body = resp.data.decode()
    assert 'bob' in body
    # We can't easily isolate bob's row without parsing, but at minimum:
    assert '—' in body


# ── basic reskin smoke (Tasks 2-4 will harden) ────────────────────────

def test_leaderboard_route_still_returns_200_with_no_data(client, app):
    """Empty leaderboard renders the empty-state copy."""
    with app.app_context():
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'No players enrolled yet' in resp.data
