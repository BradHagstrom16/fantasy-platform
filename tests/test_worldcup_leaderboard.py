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
import os
import re
import pytest
from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.constants import SEASON_YEAR, WORLDCUP_TZ
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupRankSnapshot, WorldCupTeam, WorldCupPick,
    WorldCupMatch,
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

# The real TOURNAMENT_DEADLINE_UTC (2026-06-11 19:00 UTC) has passed, so
# pre-deadline behavior needs a faked clock. The env seam pins now_utc()
# itself, keeping worldcup_state() AND deadline_passed coherent (matching
# test_worldcup_stats.py's _BEFORE_KICKOFF idiom).
_BEFORE_KICKOFF = {'WC_FAKE_NOW': '2026-06-01T12:00:00+00:00', 'ENVIRONMENT': 'testing'}


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


def _seed_team(fifa_code, tier=1, multiplier=1.0, is_eliminated=False):
    t = WorldCupTeam(
        fifa_code=fifa_code, name=fifa_code, display_name=fifa_code,
        tier=tier, multiplier=multiplier, confederation='UEFA',
        group_letter='A', is_eliminated=is_eliminated,
    )
    db.session.add(t)
    db.session.flush()
    return t


def _seed_pick(enrollment_id, team):
    p = WorldCupPick(
        enrollment_id=enrollment_id, team_id=team.id, tier=team.tier,
    )
    db.session.add(p)
    db.session.flush()
    return p


def _login(client, user_id):
    from models.user import User
    auth_id = db.session.get(User, user_id).auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
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
    """Pre state: 'Picks Open' eyebrow; no live dot, no gold Final.

    Clock faked pre-deadline via the WC_FAKE_NOW seam — the real 2026
    deadline passed on 2026-06-11, so the unfaked state is no longer pre."""
    with app.app_context():
        u = _seed_user('alice')
        _seed_enrollment(u.id, score=0.0)
        db.session.commit()
        with patch.dict(os.environ, _BEFORE_KICKOFF):
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


def test_tied_label_renders_for_shared_rank(client, app, monkeypatch):
    """Shared-rank ties say 'tied' out loud so three '#1' rows aren't ambiguous.

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
    doesn't fire on every row. Clock faked pre-deadline via WC_FAKE_NOW —
    the real 2026 deadline has passed, so the unfaked state is no longer pre."""
    with app.app_context():
        a, b = _seed_user('a'), _seed_user('b')
        _seed_enrollment(a.id, score=0.0)
        _seed_enrollment(b.id, score=0.0)
        db.session.commit()
        with patch.dict(os.environ, _BEFORE_KICKOFF):
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


# ── inline roster rail (D11 privacy + post-deadline reveal) ───────────

def test_roster_flags_hidden_pre_deadline(client, app, monkeypatch):
    """D11 privacy: before the deadline the board exposes no roster markup —
    picks stay sealed, matching player_detail's picks_visible gate."""
    monkeypatch.setattr(
        'games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE
    )
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=0.0)
        _seed_pick(e.id, _seed_team('USA'))
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'leaderboard-roster' not in resp.data
    assert b'lb-flag' not in resp.data


def test_roster_flags_render_post_deadline(client, app, monkeypatch):
    """Post-deadline the roster rail surfaces each pick as a flag SVG so the
    board answers 'who picked who' without a click-through."""
    monkeypatch.setattr(
        'games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE
    )
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=10.0)
        _seed_pick(e.id, _seed_team('USA'))
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'leaderboard-roster' in body
    assert 'lb-flag' in body
    assert '/flags/us.svg' in body  # USA -> iso 'us' self-hosted SVG, not emoji


def test_roster_flag_dims_eliminated_nation(client, app, monkeypatch):
    """Knocked-out picks carry .is-out so the board dims dead horses at a glance."""
    monkeypatch.setattr(
        'games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE
    )
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=10.0)
        _seed_pick(e.id, _seed_team('USA', is_eliminated=True))
        db.session.commit()
        resp = client.get('/worldcup/leaderboard')
    assert resp.status_code == 200
    assert b'lb-flag is-out' in resp.data


def test_roster_flag_marks_knockout_loser_out(client, app, monkeypatch):
    """A pick that lost a completed knockout match reads is-out on the rail even
    though is_eliminated stays False (group-stage-only flag). Derived via
    eliminated_team_ids()."""
    monkeypatch.setattr(
        'games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE
    )
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=10.0)
        winner = _seed_team('BRA')
        loser = _seed_team('ARG', tier=2)   # is_eliminated defaults False
        _seed_pick(e.id, loser)
        db.session.add(WorldCupMatch(
            match_number=73, stage='R32',
            home_team_id=winner.id, away_team_id=loser.id,
            winner_team_id=winner.id, is_completed=True,
        ))
        db.session.commit()
        assert loser.is_eliminated is False  # group flag never set for KO losers
        resp = client.get('/worldcup/leaderboard')
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'lb-flag is-out' in body
    assert '· out' in body


def test_roster_flag_rings_shared_pick_on_other_rows(client, app, monkeypatch):
    """A pick the viewer also holds gets .is-shared on OTHER players' rows; the
    viewer's own row never rings (every flag would match)."""
    monkeypatch.setattr(
        'games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE
    )
    with app.app_context():
        me = _seed_user('me')
        rival = _seed_user('rival')
        my_e = _seed_enrollment(me.id, score=10.0)
        rival_e = _seed_enrollment(rival.id, score=20.0)
        usa = _seed_team('USA')
        bra = _seed_team('BRA', tier=2)
        _seed_pick(my_e.id, usa)          # shared
        _seed_pick(rival_e.id, usa)       # shared -> should ring on rival row
        _seed_pick(rival_e.id, bra)       # rival-only -> no ring
        db.session.commit()
        _login(client, me.id)
        resp = client.get('/worldcup/leaderboard')
    body = resp.data.decode()
    assert resp.status_code == 200
    # Rival's shared USA pick rings; the rail is duplicated desktop + mobile so
    # the class appears at least twice (and never zero).
    assert 'lb-flag is-shared' in body


# ── player detail (/worldcup/leaderboard/<id>) scoring ledger ────────


def test_player_detail_points_column_renders_post_deadline(client, app, monkeypatch):
    """Post-deadline the player detail table shows each pick's points and the
    score-events drill-down. Regression lock: _pick_row.html gates these on
    show_scoring (PR #38), and player_detail.html must set it — undefined is
    falsy in Jinja, which blanked the whole Points column."""
    monkeypatch.setattr(
        'games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE
    )
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=19.5)
        t = _seed_team('URU', tier=3, multiplier=2.5)
        p = _seed_pick(e.id, t)
        p.base_points = 7.8
        p.multiplied_points = 19.5
        db.session.commit()
        resp = client.get(f'/worldcup/leaderboard/{e.id}')
    body = resp.data.decode()
    assert resp.status_code == 200
    # Per-row Points cell (class order distinguishes it from the tfoot total).
    assert '<td class="text-end wc-numeral fw-bold">19.5</td>' in body
    # Rendered toggle button (the always-included accordion script also
    # contains the bare selector string, so match the class attribute).
    assert 'class="pick-accordion-toggle"' in body


def test_player_detail_sealed_pre_deadline_owner(client, app, monkeypatch):
    """Pre-deadline the owner sees a sealed roster — multiplier as the stakes
    signal, no Points column, no drill-down — matching the picks-page
    show_scoring doctrine (nothing has scored yet, so no ledger of zeros)."""
    monkeypatch.setattr(
        'games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE
    )
    with app.app_context():
        u = _seed_user('alice')
        e = _seed_enrollment(u.id, score=0.0)
        t = _seed_team('URU', tier=3, multiplier=2.5)
        _seed_pick(e.id, t)
        db.session.commit()
        _login(client, u.id)
        resp = client.get(f'/worldcup/leaderboard/{e.id}')
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'wc-multiplier-chip' in body                # roster + stakes visible to owner
    assert 'class="pick-accordion-toggle"' not in body  # nothing to drill into yet
    assert '>Points</th>' not in body                   # no Points header over sealed rows
