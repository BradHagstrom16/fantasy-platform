"""Tests for games.worldcup.services.trends.

Two functions extracted from routes.py for reuse by both leaderboard()
and the new home_context._context_live builder:
- show_trend_column() — global gate, count(distinct captured_date) >= 7,
  scoped to active SEASON_YEAR via WorldCupEnrollment join
- compute_trend_by_enrollment(ids) — per-enrollment delta vs latest
  captured_date snapshot; None when no snapshot exists
"""
import pytest
from datetime import date, timedelta

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import WorldCupEnrollment, WorldCupRankSnapshot
from games.worldcup.services.trends import (
    show_trend_column, compute_trend_by_enrollment,
)


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(email='u@test'):
    # username is NOT NULL on the User model — derive a unique value from the
    # email local-part so each call site stays unique without callers having
    # to supply it. (Plan 4 Task 2 plan code omitted username; surfaced in
    # report.)
    username = email.split('@', 1)[0]
    u = User(username=username, email=email, password_hash='x', display_name='U')
    db.session.add(u)
    db.session.flush()
    return u


def _make_enrollment(user, total_score=0.0, season_year=SEASON_YEAR):
    e = WorldCupEnrollment(
        user_id=user.id, season_year=season_year, total_score=total_score,
    )
    db.session.add(e)
    db.session.flush()
    return e


def _seed_snapshots(enrollment, days_back, total_score=0.0, rank=1):
    """Insert one snapshot per day in days_back (a list of int days back from today)."""
    today = date.today()
    for d in days_back:
        s = WorldCupRankSnapshot(
            enrollment_id=enrollment.id,
            captured_date=today - timedelta(days=d),
            total_score=total_score,
            rank=rank,
        )
        db.session.add(s)
    db.session.flush()


def test_show_trend_column_false_when_no_snapshots(app):
    assert show_trend_column() is False


def test_show_trend_column_false_when_fewer_than_seven_distinct_days(app):
    user = _make_user()
    enr = _make_enrollment(user)
    _seed_snapshots(enr, days_back=[0, 1, 2, 3, 4, 5])  # 6 distinct days
    db.session.commit()
    assert show_trend_column() is False


def test_show_trend_column_true_when_seven_distinct_days(app):
    user = _make_user()
    enr = _make_enrollment(user)
    _seed_snapshots(enr, days_back=[0, 1, 2, 3, 4, 5, 6])  # 7 distinct days
    db.session.commit()
    assert show_trend_column() is True


def test_show_trend_column_scoped_to_active_season(app):
    """Snapshots from a prior cup must not satisfy the current-cup gate."""
    user = _make_user()
    prior_enr = _make_enrollment(user, season_year=SEASON_YEAR - 4)
    _seed_snapshots(prior_enr, days_back=[0, 1, 2, 3, 4, 5, 6])  # 7 days, prior season
    db.session.commit()
    assert show_trend_column() is False


def test_compute_trend_by_enrollment_returns_none_when_no_history(app):
    user = _make_user()
    enr = _make_enrollment(user, total_score=42.0)
    db.session.commit()
    result = compute_trend_by_enrollment([enr.id])
    assert result == {enr.id: None}


def test_compute_trend_by_enrollment_uses_latest_snapshot(app):
    """trend = current_score - latest_snapshot_score (latest = MAX captured_date)."""
    user = _make_user()
    enr = _make_enrollment(user, total_score=50.0)
    today = date.today()
    db.session.add(WorldCupRankSnapshot(
        enrollment_id=enr.id, captured_date=today - timedelta(days=3),
        total_score=30.0, rank=5,
    ))
    db.session.add(WorldCupRankSnapshot(
        enrollment_id=enr.id, captured_date=today - timedelta(days=1),
        total_score=45.0, rank=3,
    ))
    db.session.commit()
    result = compute_trend_by_enrollment([enr.id])
    assert result == {enr.id: 5.0}  # 50 - 45 = 5


def test_compute_trend_by_enrollment_handles_empty_input(app):
    assert compute_trend_by_enrollment([]) == {}


def test_compute_trend_by_enrollment_batches_multiple_ids(app):
    user_a = _make_user('a@test')
    user_b = _make_user('b@test')
    enr_a = _make_enrollment(user_a, total_score=20.0)
    enr_b = _make_enrollment(user_b, total_score=10.0)
    today = date.today()
    db.session.add(WorldCupRankSnapshot(
        enrollment_id=enr_a.id, captured_date=today - timedelta(days=2),
        total_score=15.0, rank=1,
    ))
    db.session.add(WorldCupRankSnapshot(
        enrollment_id=enr_b.id, captured_date=today - timedelta(days=1),
        total_score=8.0, rank=2,
    ))
    db.session.commit()
    result = compute_trend_by_enrollment([enr_a.id, enr_b.id])
    assert result == {enr_a.id: 5.0, enr_b.id: 2.0}
