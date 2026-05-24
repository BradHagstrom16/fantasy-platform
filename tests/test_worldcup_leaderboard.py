"""Tests for the public /worldcup/leaderboard route — payload + new data shapes.

Plan 3 adds three payload keys:
- your_standing: None | dict (rank-neighbor data for authenticated+enrolled user)
- rank_delta_by_enrollment: dict[int, int | None] — per-row rank-delta (Pending when None)
- trend_by_enrollment: dict[int, float | None] mapping enrollment.id -> trend score
- trend_by_enrollment: dict[int, float | None] — points-delta tooltip; empty
  until services.trends.show_trend_column() opens at >= 7 distinct snapshot days.
  The Move column itself ALWAYS renders — only the per-cell `title="Points: ..."`
  tooltip is gated on the >= 7-day snapshot window.

Trend semantics (per spec §8 + plan ambiguity-A2):
  trend = enrollment.total_score - latest_snapshot.total_score for that enrollment
  None if no snapshot exists for that enrollment
"""
import re
import pytest
from datetime import date, datetime, timezone, timedelta

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.constants import SEASON_YEAR, WORLDCUP_TZ
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupRankSnapshot,
)
from games.worldcup.services.state import now_utc


def _wc_today() -> date:
    """World-Cup-local "today" — matches services.ranking.compute_rank_delta's
    cutoff derivation (`now_utc().astimezone(WORLDCUP_TZ).date()`).

    Tests that seed snapshot dates relative to "today" must use this, not
    `date.today()`. The runner's local timezone can differ from WORLDCUP_TZ
    near midnight in either zone, which would shift the cutoff by a day and
    flake the rank-delta and points-delta-tooltip assertions.
    """
    return now_utc().astimezone(WORLDCUP_TZ).date()


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
        today = _wc_today()
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


def test_points_delta_tooltip_hidden_when_fewer_than_seven_snapshots(client, app):
    """show_trend_column = False when count(distinct captured_date) < 7.

    Per ambiguity-A1 resolution: gate is on distinct captured_date count
    across the whole table — not per-user.

    P1 S1.1 follow-up (CR R1): the Move column is decoupled from this gate
    and always renders. What this gate now controls is the per-cell points-delta
    tooltip (`title="Points: ..."`). The Move header must be present even when
    the tooltip is absent.
    """
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=50.0)
        # Only 6 distinct dates → tooltip gate stays closed
        today = _wc_today()
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
    # Move column always renders.
    # Loose match on the Move <th> so the S6.1.3 PI-1 `title=` tooltip
    # attribute on the header doesn't break this lock. The contract is
    # "Move header renders", not the literal attribute set.
    assert re.search(rb'<th[^>]*>Move</th>', resp.data) is not None
    # Points-delta tooltip is gated — no `title="Points: ..."` on any row.
    assert b'title="Points:' not in resp.data


def test_trend_column_gate_scoped_to_active_season(client, app):
    """Snapshots from a previous season must not open the gate for the active season.

    Without season-scoping, prior-cup snapshots would falsely satisfy the
    >= 7 distinct captured_date threshold at the start of a new season.

    P1 S1.1 follow-up (CR R1): the Move column is no longer governed by this
    gate. What the gate scopes is the points-delta tooltip — locked here so the
    season-scoping protection (CLAUDE.md "WorldCupRankSnapshot aggregates must
    be season-scoped") still has a regression assertion against rendered HTML.
    """
    with app.app_context():
        # Active-season enrollment with only 3 snapshot days — tooltip gate must stay closed.
        active_user = _seed_user('alice')
        active_e = _seed_enrollment(active_user.id, score=50.0)
        today = _wc_today()
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
    # Move column always renders.
    # Loose match on the Move <th> so the S6.1.3 PI-1 `title=` tooltip
    # attribute on the header doesn't break this lock. The contract is
    # "Move header renders", not the literal attribute set.
    assert re.search(rb'<th[^>]*>Move</th>', resp.data) is not None
    # Points-delta tooltip stays closed — prior-season days don't open it.
    assert b'title="Points:' not in resp.data


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
        today = _wc_today()
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
    # Loose match on the Move <th> so the S6.1.3 PI-1 `title=` tooltip
    # attribute on the header doesn't break this lock. The contract is
    # "Move header renders", not the literal attribute set.
    assert re.search(rb'<th[^>]*>Move</th>', resp.data) is not None
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


# ── Impeccable 2026-05-24: state hero, points hierarchy, tied, inline delta ──

def test_hero_pre_state_reads_picks_open(client, app):
    """Pre-deadline (default): 'Picks Open' eyebrow; no live dot, no gold Final."""
    with app.app_context():
        u = _seed_user('alice')
        _seed_enrollment(u.id, score=0.0)
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'Picks Open' in resp.data
    assert b'leaderboard-live-dot' not in resp.data
    assert b'wc-eyebrow-gold' not in resp.data
    assert b'leaderboard-champion-tag' not in resp.data


def test_hero_live_state_shows_live_dot(client, app, monkeypatch):
    """Live state: paired live dot + 'Live' label (color is never the sole carrier)."""
    monkeypatch.setattr('games.worldcup.routes.worldcup_state', lambda: 'live')
    with app.app_context():
        u = _seed_user('alice')
        _seed_enrollment(u.id, score=12.0)
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'leaderboard-live-dot' in resp.data
    assert b'Live \xc2\xb7 Tonight' in resp.data  # "Live · Tonight's Ledger" (· is U+00B7)
    assert b'Picks Open' not in resp.data
    assert b'leaderboard-champion-tag' not in resp.data


def test_hero_post_state_crowns_pool_champion(client, app, monkeypatch):
    """Post state: gold 'Final' eyebrow + 'takes the crown'; champion tag on the
    tiebreaker-resolved top row ONLY (one row -> desktop + mobile = 2 marks)."""
    monkeypatch.setattr('games.worldcup.routes.worldcup_state', lambda: 'post')
    with app.app_context():
        winner = _seed_user('winner')
        runner = _seed_user('runner')
        _seed_enrollment(winner.id, score=200.0)
        _seed_enrollment(runner.id, score=120.0)
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'wc-eyebrow-gold' in body
    assert 'Final' in body
    assert 'takes the crown' in body
    # Exactly one crowned row, rendered in both desktop + mobile layouts.
    assert body.count('leaderboard-champion-tag') == 2


def test_desktop_points_carry_hierarchy_classes(client, app):
    """Points become the focal numeral; rank demotes to a quiet ordinal."""
    with app.app_context():
        u = _seed_user('alice')
        _seed_enrollment(u.id, score=42.0)
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'leaderboard-pts' in resp.data
    assert b'leaderboard-rank-ord' in resp.data


def test_tied_label_renders_for_shared_dense_rank(client, app, monkeypatch):
    """Dense-rank ties say 'tied' out loud so three '#1' rows aren't ambiguous.

    Gated to non-pre states: pre-deadline everyone sits at 0 and the label
    would fire on every row, so it only carries signal once play starts.
    """
    monkeypatch.setattr('games.worldcup.routes.worldcup_state', lambda: 'live')
    with app.app_context():
        a, b = _seed_user('a'), _seed_user('b')
        _seed_enrollment(a.id, score=50.0)
        _seed_enrollment(b.id, score=50.0)  # tie at rank 1
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'leaderboard-tied' in resp.data


def test_no_tied_label_when_all_scores_distinct(client, app, monkeypatch):
    """No tie -> no 'tied' label (avoid crying wolf)."""
    monkeypatch.setattr('games.worldcup.routes.worldcup_state', lambda: 'live')
    with app.app_context():
        a, b = _seed_user('a'), _seed_user('b')
        _seed_enrollment(a.id, score=50.0)
        _seed_enrollment(b.id, score=30.0)
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'leaderboard-tied' not in resp.data


def test_tied_label_suppressed_pre_deadline(client, app):
    """Pre-deadline (everyone at 0, all tied at rank 1) hides the label so it
    doesn't fire on every row."""
    with app.app_context():
        a, b = _seed_user('a'), _seed_user('b')
        _seed_enrollment(a.id, score=0.0)
        _seed_enrollment(b.id, score=0.0)
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'leaderboard-tied' not in resp.data


def test_points_delta_surfaces_inline_not_hover_only(client, app):
    """Points-delta renders inline (.leaderboard-move-pts), reachable on touch +
    keyboard, replacing the prior hover-only title= tooltip."""
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=50.0)
        today = _wc_today()
        for i in range(8):  # open the >=7-day trend gate
            _seed_snapshot(
                enrollment_id=e.id,
                captured_date=today - timedelta(days=i + 1),
                rank=1,
                total_score=10.0 + (7 - i) * 5.0,
            )
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'leaderboard-move-pts' in resp.data
    assert b'title="Points:' not in resp.data  # no hover-only delta anymore
