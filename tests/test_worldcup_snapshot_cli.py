"""Tests for the `flask worldcup snapshot-ranks` CLI (Spec B follow-up B2)."""
from datetime import timedelta

import pytest

from app import create_app
from extensions import db
from games.worldcup.cli import worldcup_cli


@pytest.fixture
def app():
    """Testing app with in-memory SQLite."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_enrollment(total_score=0.0, username='u'):
    """Create a User + WorldCupEnrollment for the current SEASON_YEAR."""
    from games.worldcup.constants import SEASON_YEAR
    from games.worldcup.models import WorldCupEnrollment
    from models.user import User
    user = User(username=username, email=f'{username}@test.com')
    user.set_password('test1234')
    db.session.add(user)
    db.session.commit()
    enr = WorldCupEnrollment(
        user_id=user.id, season_year=SEASON_YEAR,
        picks_submitted=True, total_score=total_score,
    )
    db.session.add(enr)
    db.session.commit()
    return enr


def _today_local():
    """Today's date in WORLDCUP_TZ — matches what the CLI uses."""
    from datetime import datetime

    from games.worldcup.constants import WORLDCUP_TZ
    return datetime.now(WORLDCUP_TZ).date()


def test_snapshot_idempotent_same_day(app):
    """Re-running snapshot-ranks for the same day adds 0 new rows."""
    from games.worldcup.models import WorldCupRankSnapshot
    with app.app_context():
        _make_enrollment(total_score=10.0, username='alice')
        _make_enrollment(total_score=20.0, username='bob')

        runner = app.test_cli_runner()
        result1 = runner.invoke(worldcup_cli, ['snapshot-ranks'])
        assert result1.exit_code == 0, result1.output
        assert WorldCupRankSnapshot.query.count() == 2

        result2 = runner.invoke(worldcup_cli, ['snapshot-ranks'])
        assert result2.exit_code == 0, result2.output
        # Still 2 rows; second run was a no-op.
        assert WorldCupRankSnapshot.query.count() == 2


def test_snapshot_backfill_writes_n_plus_one_descending(app):
    """`--backfill 3` writes today + 3 prior days (4 distinct dates per enrollment)."""
    from games.worldcup.models import WorldCupRankSnapshot
    with app.app_context():
        _make_enrollment(total_score=10.0, username='alice')
        _make_enrollment(total_score=20.0, username='bob')

        runner = app.test_cli_runner()
        result = runner.invoke(worldcup_cli, ['snapshot-ranks', '--backfill', '3'])
        assert result.exit_code == 0, result.output

        # 2 enrollments × 4 days = 8 rows total
        assert WorldCupRankSnapshot.query.count() == 8

        # For each enrollment, dates span today back to today-3
        today = _today_local()
        for enr in db.session.query(WorldCupRankSnapshot.enrollment_id).distinct().all():
            eid = enr[0]
            dates = sorted(
                row.captured_date for row in
                WorldCupRankSnapshot.query.filter_by(enrollment_id=eid).all()
            )
            assert len(dates) == 4
            assert dates[-1] == today
            assert dates[0] == today - timedelta(days=3)


def test_snapshot_negative_backfill_rejected(app):
    """`--backfill -1` exits non-zero with a BadParameter message; no rows written."""
    from games.worldcup.models import WorldCupRankSnapshot
    with app.app_context():
        _make_enrollment(total_score=10.0, username='alice')

        runner = app.test_cli_runner()
        result = runner.invoke(worldcup_cli, ['snapshot-ranks', '--backfill', '-1'])
        assert result.exit_code != 0
        assert '--backfill must be >= 0' in result.output
        assert WorldCupRankSnapshot.query.count() == 0


def test_snapshot_tie_ordering_deterministic(app):
    """3 tied-score enrollments produce identical (eid, rank) ordering across runs.

    Under competition rank, tied scores share a rank, so all three land at
    rank 1 (parity with the displayed leaderboard / compute_rank_neighbors).
    """
    from games.worldcup.models import WorldCupRankSnapshot
    with app.app_context():
        e1 = _make_enrollment(total_score=10.0, username='alice')
        e2 = _make_enrollment(total_score=10.0, username='bob')
        e3 = _make_enrollment(total_score=10.0, username='carol')

        runner = app.test_cli_runner()
        runner.invoke(worldcup_cli, ['snapshot-ranks'])
        first = sorted(
            (row.enrollment_id, row.rank)
            for row in WorldCupRankSnapshot.query.all()
        )

        # Wipe and re-run; captured_date is "today" for both runs so we'd hit
        # idempotency without the wipe.
        WorldCupRankSnapshot.query.delete()
        db.session.commit()

        runner.invoke(worldcup_cli, ['snapshot-ranks'])
        second = sorted(
            (row.enrollment_id, row.rank)
            for row in WorldCupRankSnapshot.query.all()
        )

        assert first == second
        # All scores tied → competition rank gives every row rank 1.
        assert first == sorted([(e1.id, 1), (e2.id, 1), (e3.id, 1)])
