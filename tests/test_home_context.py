"""Unit tests for home-page state detection and context assembly (Spec B)."""
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db


@pytest.fixture
def app():
    """Testing app with in-memory SQLite + WC_FAKE_NOW disabled."""
    os.environ.pop('WC_FAKE_NOW', None)
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _seed_final_match(completed: bool, winner_id: int | None = None):
    """Seed match #104 (the Final). Used to flip live → post.

    Seeds two minimal teams to satisfy NOT NULL home_team_id / away_team_id.
    """
    from games.worldcup.models import WorldCupMatch, WorldCupTeam
    home = WorldCupTeam(
        fifa_code='FNA', name='Finalist A', display_name='Finalist A',
        tier=1, multiplier=1.0, confederation='TEST', group_letter='Z',
    )
    away = WorldCupTeam(
        fifa_code='FNB', name='Finalist B', display_name='Finalist B',
        tier=1, multiplier=1.0, confederation='TEST', group_letter='Z',
    )
    db.session.add_all([home, away])
    db.session.flush()
    match = WorldCupMatch(
        match_number=104,
        stage='final',
        home_team_id=home.id,
        away_team_id=away.id,
        is_completed=completed,
        winner_team_id=winner_id,
    )
    db.session.add(match)
    db.session.commit()


def _make_user(username='alice', email='alice@example.com'):
    """Create + persist a User. Returns the User."""
    from models.user import User
    user = User(username=username, email=email)
    user.set_password('test1234')
    db.session.add(user)
    db.session.commit()
    return user


def _make_enrollment(user, picks_submitted=False, total_score=0.0):
    """Create + persist a WorldCupEnrollment for the current SEASON_YEAR."""
    from games.worldcup.models import WorldCupEnrollment
    from games.worldcup.constants import SEASON_YEAR
    enr = WorldCupEnrollment(
        user_id=user.id,
        season_year=SEASON_YEAR,
        picks_submitted=picks_submitted,
        total_score=total_score,
    )
    db.session.add(enr)
    db.session.commit()
    return enr


def test_worldcup_state_pre_when_before_deadline(app):
    """Before TOURNAMENT_DEADLINE_UTC, state is 'pre'."""
    from games.worldcup.services.state import worldcup_state
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        assert worldcup_state() == 'pre'


def test_worldcup_state_live_after_deadline_no_final(app):
    """After deadline + final not complete, state is 'live'."""
    from games.worldcup.services.state import worldcup_state
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T00:00:00Z'}):
        assert worldcup_state() == 'live'


def test_worldcup_state_post_when_final_completed(app):
    """After deadline + final marked complete, state is 'post'."""
    from games.worldcup.services.state import worldcup_state
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-07-20T00:00:00Z'}):
        _seed_final_match(completed=True, winner_id=None)
        assert worldcup_state() == 'post'


def test_context_out_basic(app):
    """Logged-out context returns game tiles + total_enrolled."""
    from core.main.home_context import build_home_context
    with app.app_context():
        ctx = build_home_context(None, None)
        assert 'available_games' in ctx
        assert 'coming_soon_games' in ctx
        assert ctx['total_enrolled'] == 0  # no enrollments seeded
        # WC is the only open game in the registry currently
        assert any(g.slug == 'worldcup' for g in ctx['available_games'])


def test_context_pre_unenrolled(app):
    """Logged-in but no WC enrollment → is_enrolled=False, no picks."""
    from core.main.home_context import build_home_context
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        user = _make_user()
        ctx = build_home_context(user, 'pre')
        assert ctx['is_enrolled'] is False
        assert ctx['picks'] == []
        assert ctx['display_name'] == 'alice'
        assert 'court_line' in ctx
        assert 'deadline_utc' in ctx
        assert ctx['now_utc'] == datetime(2026, 5, 1, tzinfo=timezone.utc)


def test_context_pre_enrolled_no_picks(app):
    """Enrolled but picks_submitted=False → is_enrolled=True, picks=[]."""
    from core.main.home_context import build_home_context
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        user = _make_user()
        _make_enrollment(user, picks_submitted=False)
        ctx = build_home_context(user, 'pre')
        assert ctx['is_enrolled'] is True
        assert ctx['picks'] == []


def test_context_pre_enrolled_sealed(app):
    """Enrolled + picks_submitted=True → picks list populated."""
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupPick
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        user = _make_user()
        enr = _make_enrollment(user, picks_submitted=True)
        # Seed one team + one pick (the test only checks structure, not 9 picks)
        team = WorldCupTeam(
            fifa_code='USA', name='United States', display_name='USA',
            tier=1, multiplier=1.0, confederation='CONCACAF', group_letter='A',
        )
        db.session.add(team)
        db.session.commit()
        pick = WorldCupPick(enrollment_id=enr.id, team_id=team.id, tier=1)
        db.session.add(pick)
        db.session.commit()
        ctx = build_home_context(user, 'pre')
        assert ctx['is_enrolled'] is True
        assert len(ctx['picks']) == 1
        assert ctx['picks'][0].team.fifa_code == 'USA'


def test_context_live_unenrolled(app):
    """Live state, no enrollment → is_enrolled=False, dossier dict missing."""
    from core.main.home_context import build_home_context
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T00:00:00Z'}):
        user = _make_user()
        ctx = build_home_context(user, 'live')
        assert ctx['is_enrolled'] is False
        assert ctx['dossier'] is None
        assert ctx['top_3_plus_you'] == []  # no enrollments seeded


def test_context_live_enrolled_basic(app):
    """Live state, enrolled → dossier populated with rank/points/alive."""
    from core.main.home_context import build_home_context
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T00:00:00Z'}):
        user = _make_user()
        _make_enrollment(user, picks_submitted=True, total_score=100.0)
        ctx = build_home_context(user, 'live')
        assert ctx['is_enrolled'] is True
        assert ctx['dossier']['rank'] == 1  # only 1 enrollment
        assert ctx['dossier']['total_score'] == 100.0
        assert ctx['dossier']['alive_count'] == 0  # no picks seeded
        assert ctx['dossier']['week_delta_rank'] is None  # no snapshots
        # CR10: prove WC_FAKE_NOW flowed through to court_line weekday.
        # 2026-06-15T00:00:00Z = 2026-06-14 19:00 CDT (UTC-5) → Sunday.
        assert 'Sunday' in ctx['court_line']
        # No picks seeded → empty roster ledger.
        assert ctx['dossier']['roster'] == []


def test_context_live_roster_ledger_status_leader_and_sort(app):
    """Live dossier.roster lists every pick with flag/code/name/points and a
    status; the top scorer is crowned + sorted first; an eliminated pick is
    'out' (even with points) and sinks to the tail; alive_count agrees with the
    roster's non-out count (eliminated_team_ids, NOT group-only is_eliminated).
    """
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupPick
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T00:00:00Z'}):
        ldr = WorldCupTeam(
            fifa_code='LDR', name='Leadland', display_name='Leadland',
            tier=2, multiplier=2.0, confederation='TEST', group_letter='A',
        )
        drm = WorldCupTeam(
            fifa_code='DRM', name='Dormantia', display_name='Dormantia',
            tier=5, multiplier=7.0, confederation='TEST', group_letter='B',
        )
        # Group-eliminated → in eliminated_team_ids() despite carrying points.
        out = WorldCupTeam(
            fifa_code='OUT', name='Outland', display_name='Outland',
            tier=4, multiplier=4.0, confederation='TEST', group_letter='C',
            is_eliminated=True,
        )
        db.session.add_all([ldr, drm, out])
        db.session.commit()
        user = _make_user()
        enr = _make_enrollment(user, picks_submitted=True, total_score=47.5)
        db.session.add_all([
            WorldCupPick(enrollment_id=enr.id, team_id=ldr.id, tier=2, multiplied_points=42.5),
            WorldCupPick(enrollment_id=enr.id, team_id=drm.id, tier=5, multiplied_points=0.0),
            WorldCupPick(enrollment_id=enr.id, team_id=out.id, tier=4, multiplied_points=5.0),
        ])
        db.session.commit()

        ctx = build_home_context(user, 'live')
        roster = ctx['dossier']['roster']
        assert len(roster) == 3
        # Sort: scoring → dormant → out; leader first.
        assert [r['code'] for r in roster] == ['LDR', 'DRM', 'OUT']
        by_code = {r['code']: r for r in roster}
        assert by_code['LDR']['status'] == 'scoring'
        assert by_code['LDR']['is_leader'] is True
        assert by_code['LDR']['iso'] == ldr.iso_code
        assert by_code['LDR']['name'] == 'Leadland'
        assert by_code['LDR']['points'] == 42.5
        assert by_code['DRM']['status'] == 'dormant'
        assert by_code['DRM']['is_leader'] is False
        # Eliminated wins over a non-zero score: status 'out', points retained.
        assert by_code['OUT']['status'] == 'out'
        assert by_code['OUT']['is_leader'] is False
        assert by_code['OUT']['points'] == 5.0
        # alive_count counts non-out picks (2), via eliminated_team_ids — the
        # crowned leader is the same pick as top_earner.
        assert ctx['dossier']['alive_count'] == 2
        assert ctx['dossier']['top_earner']['team_code'] == 'LDR'


def test_context_live_roster_no_leader_when_nothing_scored(app):
    """When no pick has scored yet, no row is crowned (is_leader all False)
    and top_earner is None — the gold hero row never appears speculatively."""
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupPick
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T00:00:00Z'}):
        a = WorldCupTeam(
            fifa_code='AAA', name='Aaa', display_name='Aaa',
            tier=1, multiplier=1.0, confederation='TEST', group_letter='A',
        )
        b = WorldCupTeam(
            fifa_code='BBB', name='Bbb', display_name='Bbb',
            tier=5, multiplier=7.0, confederation='TEST', group_letter='B',
        )
        db.session.add_all([a, b])
        db.session.commit()
        user = _make_user()
        enr = _make_enrollment(user, picks_submitted=True, total_score=0.0)
        db.session.add_all([
            WorldCupPick(enrollment_id=enr.id, team_id=a.id, tier=1, multiplied_points=0.0),
            WorldCupPick(enrollment_id=enr.id, team_id=b.id, tier=5, multiplied_points=0.0),
        ])
        db.session.commit()

        ctx = build_home_context(user, 'live')
        roster = ctx['dossier']['roster']
        assert len(roster) == 2
        assert all(r['is_leader'] is False for r in roster)
        assert all(r['status'] == 'dormant' for r in roster)
        assert ctx['dossier']['top_earner'] is None


def test_context_post_with_champion(app):
    """Post state with match #104 completed → champion_team populated."""
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupMatch
    with app.app_context():
        # Seed the champion + final match
        bra = WorldCupTeam(
            fifa_code='BRA', name='Brazil', display_name='Brazil',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='C',
        )
        arg = WorldCupTeam(
            fifa_code='ARG', name='Argentina', display_name='Argentina',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='B',
        )
        db.session.add_all([bra, arg])
        db.session.commit()
        final = WorldCupMatch(
            match_number=104, stage='final',
            home_team_id=bra.id, away_team_id=arg.id,
            home_score=3, away_score=2, extra_time=True,
            winner_team_id=bra.id, is_completed=True,
        )
        db.session.add(final)
        db.session.commit()

        user = _make_user()
        ctx = build_home_context(user, 'post')
        assert ctx['champion_team'].fifa_code == 'BRA'
        assert 'Argentina' in ctx['champion_summary']
        assert '3' in ctx['champion_summary']
        assert ctx['is_enrolled'] is False


def test_context_post_enrolled_with_climb_and_roster_recap(app):
    """Post state, enrolled with picks: your_final_rank, your_climbed_n,
    and your_roster_recap (with is_champion flag) all populate.

    Covers the previously-untested ~30 lines of the enrolled branch in
    _context_post — your_climbed_n sign convention, tier_name lookup,
    best_finish fallback, and is_champion flag against the right pick.
    """
    from core.main.home_context import build_home_context
    from games.worldcup.models import (
        WorldCupTeam, WorldCupMatch, WorldCupPick, WorldCupRankSnapshot,
    )
    from datetime import date, timedelta
    with app.app_context():
        bra = WorldCupTeam(
            fifa_code='BRA', name='Brazil', display_name='Brazil',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='C',
            best_finish='champion',
        )
        arg = WorldCupTeam(
            fifa_code='ARG', name='Argentina', display_name='Argentina',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='B',
            best_finish='runner_up',
        )
        db.session.add_all([bra, arg])
        db.session.commit()
        final = WorldCupMatch(
            match_number=104, stage='final',
            home_team_id=bra.id, away_team_id=arg.id,
            home_score=3, away_score=2, extra_time=True,
            winner_team_id=bra.id, is_completed=True,
        )
        db.session.add(final)
        # Two enrollments so the user has someone to climb past
        u1 = _make_user(username='other', email='other@test.com')
        _make_enrollment(u1, picks_submitted=True, total_score=50.0)
        u2 = _make_user()
        e2 = _make_enrollment(u2, picks_submitted=True, total_score=200.0)
        # User picks BRA (champion) + ARG (runner-up)
        db.session.add_all([
            WorldCupPick(enrollment_id=e2.id, team_id=bra.id, tier=2),
            WorldCupPick(enrollment_id=e2.id, team_id=arg.id, tier=2),
        ])
        # Snapshots: user started at rank 2, ended at rank 1 → climbed 1
        today = date(2026, 7, 20)
        db.session.add_all([
            WorldCupRankSnapshot(enrollment_id=e2.id, captured_date=today - timedelta(days=10), rank=2, total_score=50.0),
            WorldCupRankSnapshot(enrollment_id=e2.id, captured_date=today, rank=1, total_score=200.0),
        ])
        db.session.commit()

        ctx = build_home_context(u2, 'post')
        assert ctx['is_enrolled'] is True
        assert ctx['your_final_rank'] == 1
        assert ctx['your_climbed_n'] == 1  # first.rank (2) - your_final_rank (1)
        assert len(ctx['your_roster_recap']) == 2
        champion_recaps = [r for r in ctx['your_roster_recap'] if r['is_champion']]
        assert len(champion_recaps) == 1
        assert champion_recaps[0]['pick'].team_id == bra.id


def test_context_post_roster_recap_renders_best_finish_labels(app):
    """B1 + F1: the lounge roster recap must show display labels, not raw codes,
    and must distinguish an advanced-but-R32-eliminated team (empty best_finish
    -> 'Round of 32') from a group-stage exit ('group' -> 'Group Stage')."""
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupMatch, WorldCupPick
    with app.app_context():
        # champion, won-R16, group-eliminated, advanced-lost-R32 (empty)
        specs = [
            ('CHA', 'champion', 'group_winner', False),
            ('RSX', 'R16', 'group_winner', False),
            ('GRP', 'group', None, True),
            ('R32', '', 'group_winner', False),  # advanced, lost R32 -> empty
        ]
        teams = {}
        for i, (code, finish, adv, elim) in enumerate(specs):
            t = WorldCupTeam(
                fifa_code=code, name=code, display_name=code,
                tier=5, multiplier=7.0, confederation='TEST', group_letter='A',
                best_finish=finish, advancement_method=adv, is_eliminated=elim,
            )
            db.session.add(t)
            teams[code] = t
        db.session.flush()
        db.session.add(WorldCupMatch(
            match_number=104, stage='final',
            home_team_id=teams['CHA'].id, away_team_id=teams['RSX'].id,
            home_score=1, away_score=0, winner_team_id=teams['CHA'].id,
            is_completed=True,
        ))
        user = _make_user()
        enr = _make_enrollment(user, picks_submitted=True, total_score=100.0)
        for code in ('CHA', 'RSX', 'GRP', 'R32'):
            db.session.add(WorldCupPick(enrollment_id=enr.id, team_id=teams[code].id, tier=5))
        db.session.commit()

        ctx = build_home_context(user, 'post')
        labels = {r['pick'].team.fifa_code: r['best_finish'] for r in ctx['your_roster_recap']}
        assert labels['CHA'] == 'Champion'
        assert labels['RSX'] == 'Round of 16'
        assert labels['GRP'] == 'Group Stage'
        assert labels['R32'] == 'Round of 32'   # F1: NOT 'Group'


def test_context_live_sparkline_flat_line_render(app, client):
    """Lounge dossier sparkline renders a centered dashed line (not a
    full-height area block) when every snapshot carries the same rank.

    Locks the Critique 2026-05-15 P0-3 fix: when min_v == max_v the
    prior path/area math collapsed every point to y=pad, so the area
    fill closed from y=pad down to y=height — producing a near-full-
    height rectangle that read as a solid block on the dark lounge.
    The most-engaged user (a stable leader at #1) got the least
    informative chart.

    The WC hub no longer carries a parity sparkline: the 2026-05-24
    "differentiate the hub" redesign replaced the parity dossier embed
    with the Leverage Board (the hub leans on the multiplier system, the
    lounge keeps the rank chart). This test now asserts the hub chart is
    gone while the standing card still renders.
    """
    from datetime import date, timedelta
    from games.worldcup.models import WorldCupRankSnapshot
    with app.app_context(), patch.dict(os.environ, {
        'ENVIRONMENT': 'testing',
        'WC_FAKE_NOW': '2026-06-15T00:00:00Z',
    }):
        user = _make_user()
        enr = _make_enrollment(user, picks_submitted=True, total_score=150.0)
        # Seed 8 days of identical rank-1 snapshots — the canonical
        # "stable leader" pattern that produced the degenerate render.
        today = date(2026, 6, 14)
        for delta in range(8):
            db.session.add(WorldCupRankSnapshot(
                enrollment_id=enr.id,
                captured_date=today - timedelta(days=delta),
                rank=1, total_score=150.0,
            ))
        db.session.commit()

        # Log in and fetch the lounge home page.
        with client.session_transaction() as sess:
            sess['_user_id'] = user.get_id()
            sess['_fresh'] = True
        lounge = client.get('/')
        assert lounge.status_code == 200
        lounge_html = lounge.data.decode()
        # Flat-line branch indicators
        assert 'stroke-dasharray="4 4"' in lounge_html, (
            'Lounge dossier sparkline must render the dashed centered '
            'line on flat-rank data (P0-3 regression lock).'
        )
        # The path/area fill from the non-flat branch must NOT appear —
        # the rgba(242,211,107,0.16) area fill is the visual symptom of
        # the bug, and the (M…L…L…Z) area path is its scaffolding.
        assert 'fill="rgba(242,211,107,0.16)"' not in lounge_html, (
            'Flat-rank sparkline must drop the area fill (P0-3): the '
            'fill produces the near-full-height solid block.'
        )

        # WC hub: the parity sparkline retired in the 2026-05-24 Leverage
        # Board differentiation. Assert the rank chart is gone and the
        # standing card still renders.
        hub = client.get('/worldcup/')
        assert hub.status_code == 200
        hub_html = hub.data.decode()
        assert 'wc-standing-card' in hub_html, (
            'WC hub live state must still render the standing card.'
        )
        assert 'stroke-dasharray="4 4"' not in hub_html, (
            'WC hub no longer renders the parity rank sparkline after the '
            '2026-05-24 Leverage Board differentiation.'
        )


def test_live_home_renders_roster_ledger(app, client):
    """The live lounge home renders the 'Your Nine Nations' roster panel for an
    enrolled user: the .live-roster container, each pick's flag + code + points,
    the gold leader row, and the 'Out' label for an eliminated pick. Locks the
    home-page-roster-visibility requirement. No leverage bars (lounge != hub).
    """
    from games.worldcup.models import WorldCupTeam, WorldCupPick
    with app.app_context(), patch.dict(os.environ, {
        'ENVIRONMENT': 'testing',
        'WC_FAKE_NOW': '2026-06-15T00:00:00Z',
    }):
        ldr = WorldCupTeam(
            fifa_code='LDR', name='Leadland', display_name='Leadland',
            tier=2, multiplier=2.0, confederation='TEST', group_letter='A',
        )
        out = WorldCupTeam(
            fifa_code='OUT', name='Outland', display_name='Outland',
            tier=4, multiplier=4.0, confederation='TEST', group_letter='C',
            is_eliminated=True,
        )
        db.session.add_all([ldr, out])
        db.session.commit()
        user = _make_user()
        enr = _make_enrollment(user, picks_submitted=True, total_score=42.5)
        db.session.add_all([
            WorldCupPick(enrollment_id=enr.id, team_id=ldr.id, tier=2, multiplied_points=42.5),
            WorldCupPick(enrollment_id=enr.id, team_id=out.id, tier=4, multiplied_points=0.0),
        ])
        db.session.commit()

        with client.session_transaction() as sess:
            sess['_user_id'] = user.get_id()
            sess['_fresh'] = True
        resp = client.get('/')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'live-roster' in html
        assert 'Your Nine Nations' in html
        # Both picks render with code + points.
        assert 'LDR' in html and 'OUT' in html
        assert '42.5' in html
        # Leader crowned + eliminated marked.
        assert 'live-roster-row--leader' in html
        assert 'live-roster-row--out' in html
        assert '>Out<' in html
        # Differentiation: the lounge roster carries NO Leverage Board bars.
        assert 'wc-leverage-bar' not in html


def test_context_live_dense_rank_for_tied_scores(app):
    """Lounge live dossier + leaderboard preview both use dense rank.

    Locks the Critique 2026-05-15 P0-1 fix: the prior `enumerate(...)+1`
    rendered competition rank, which diverged from the WC hub's dense
    rank for any tied-score pair. CLAUDE.md "Dense rank everywhere"
    invariant — tied scores share a rank, the next distinct score
    advances by 1 (no gap).

    Seeds three enrollments where the top two tie at 150 pts: dense
    rank → 1, 1, 2 (not the prior 1, 2, 3).
    """
    from core.main.home_context import build_home_context
    with app.app_context(), patch.dict(os.environ, {
        'ENVIRONMENT': 'testing',
        'WC_FAKE_NOW': '2026-06-15T00:00:00Z',
    }):
        u_first = _make_user(username='first', email='first@test.com')
        u_tied = _make_user(username='tied', email='tied@test.com')
        u_third = _make_user(username='third', email='third@test.com')
        _make_enrollment(u_first, picks_submitted=True, total_score=150.0)
        _make_enrollment(u_tied, picks_submitted=True, total_score=150.0)
        _make_enrollment(u_third, picks_submitted=True, total_score=50.0)

        # Viewer is the tied user — their dossier rank should equal the
        # first user's rank (both share rank 1 under dense rank).
        ctx = build_home_context(u_tied, 'live')
        assert ctx['dossier']['rank'] == 1, (
            'Tied-leader pair must share rank 1 under dense rank '
            '(prior competition rank rendered the second tied row as #2).'
        )

        # Top-3-plus-you must also render dense rank.
        ranks = [row['rank'] for row in ctx['top_3_plus_you']]
        assert ranks == [1, 1, 2], (
            f'top_3_plus_you must use dense rank, got {ranks}. '
            'Tied scores share a rank; the next distinct score is rank+1.'
        )

        # Viewer at rank 1 + leader at rank 1 → lead_delta_up is None
        # (you ARE the leader, no points back of the lead).
        assert ctx['dossier']['lead_delta_up'] is None


def test_context_live_lead_delta_for_chaser(app):
    """Bolder P1: lounge dossier surfaces lead_delta_up/down (parity port
    from the WC hub embed; lounge previously omitted it).
    """
    from core.main.home_context import build_home_context
    with app.app_context(), patch.dict(os.environ, {
        'ENVIRONMENT': 'testing',
        'WC_FAKE_NOW': '2026-06-15T00:00:00Z',
    }):
        u_lead = _make_user(username='leader', email='leader@test.com')
        u_you = _make_user(username='you', email='you@test.com')
        u_chaser = _make_user(username='chaser', email='chaser@test.com')
        _make_enrollment(u_lead, picks_submitted=True, total_score=200.0)
        _make_enrollment(u_you, picks_submitted=True, total_score=125.0)
        _make_enrollment(u_chaser, picks_submitted=True, total_score=50.0)

        ctx = build_home_context(u_you, 'live')
        assert ctx['dossier']['rank'] == 2
        assert ctx['dossier']['lead_delta_up'] == 75.0  # 200 - 125
        assert ctx['dossier']['lead_delta_down'] == 75.0  # 125 - 50


def test_context_live_roster_match_away_side(app):
    """Live state with user's pick on the away side of a recent result.

    Covers the elif match.away_team_id in user_team_ids branch — previously
    untested. A regression in side mapping or away-side
    user_picks_by_team_id lookup would silently lose the roster banner
    + points-earned chip for half of viewers.
    """
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupMatch, WorldCupPick
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-15T00:00:00Z'}):
        home_team = WorldCupTeam(
            fifa_code='ESP', name='Spain', display_name='Spain',
            tier=1, multiplier=1.0, confederation='UEFA', group_letter='B',
        )
        away_team = WorldCupTeam(
            fifa_code='NOR', name='Norway', display_name='Norway',
            tier=5, multiplier=7.0, confederation='UEFA', group_letter='B',
        )
        db.session.add_all([home_team, away_team])
        db.session.commit()
        # Spain home wins, but the user's roster has Norway (away)
        match = WorldCupMatch(
            match_number=20, stage='group', group_letter='B',
            home_team_id=home_team.id, away_team_id=away_team.id,
            home_score=2, away_score=1, is_completed=True,
            winner_team_id=home_team.id,
        )
        db.session.add(match)
        user = _make_user()
        enr = _make_enrollment(user, picks_submitted=True)
        db.session.add(WorldCupPick(enrollment_id=enr.id, team_id=away_team.id, tier=5))
        db.session.commit()

        ctx = build_home_context(user, 'live')
        results = ctx['your_pick_results']
        assert len(results) == 1
        assert results[0]['roster_match'] is not None
        assert results[0]['roster_match']['side'] == 'away'
        assert results[0]['roster_match']['team_id'] == away_team.id
        # Norway lost → 0 points (not a draw)
        assert results[0]['points_earned'] == 0.0
        assert results[0]['is_draw'] is False


def test_context_post_champion_summary_away_winner_on_penalties(app):
    """Post state with away-team winner on penalties.

    Verifies (a) score order is winner-first regardless of home/away
    alignment, and (b) ' on penalties' suffix is appended.
    """
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupMatch
    with app.app_context():
        bra = WorldCupTeam(
            fifa_code='BRA', name='Brazil', display_name='Brazil',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='C',
        )
        arg = WorldCupTeam(
            fifa_code='ARG', name='Argentina', display_name='Argentina',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='B',
        )
        db.session.add_all([bra, arg])
        db.session.commit()
        # ARG (away) wins on penalties, regulation 1-2 (home_score=1, away_score=2)
        final = WorldCupMatch(
            match_number=104, stage='final',
            home_team_id=bra.id, away_team_id=arg.id,
            home_score=1, away_score=2, penalties=True,
            winner_team_id=arg.id, is_completed=True,
        )
        db.session.add(final)
        db.session.commit()

        user = _make_user()
        ctx = build_home_context(user, 'post')
        assert ctx['champion_team'].fifa_code == 'ARG'
        # Winner score (2) listed first; loser is Brazil
        assert 'Defeated Brazil 2–1 on penalties' == ctx['champion_summary']


def test_context_post_malformed_final_no_corrupted_summary(app):
    """Post state with a malformed Final still renders the champion banner
    but skips the defeat summary rather than rendering corrupted data.

    Triggers: (a) winner_team_id matches neither team (admin manual edit
    error), (b) scores left null on a row marked complete.
    """
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupMatch
    with app.app_context():
        bra = WorldCupTeam(
            fifa_code='BRA', name='Brazil', display_name='Brazil',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='C',
        )
        arg = WorldCupTeam(
            fifa_code='ARG', name='Argentina', display_name='Argentina',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='B',
        )
        ghost = WorldCupTeam(
            fifa_code='GHO', name='Ghost', display_name='Ghost',
            tier=1, multiplier=1.0, confederation='TEST', group_letter='Z',
        )
        db.session.add_all([bra, arg, ghost])
        db.session.commit()
        # winner_team_id = ghost.id, but match teams are BRA + ARG
        final = WorldCupMatch(
            match_number=104, stage='final',
            home_team_id=bra.id, away_team_id=arg.id,
            home_score=3, away_score=2,
            winner_team_id=ghost.id, is_completed=True,
        )
        db.session.add(final)
        db.session.commit()

        user = _make_user()
        ctx = build_home_context(user, 'post')
        # Banner still shows the (anomalous) champion_team
        assert ctx['champion_team'].fifa_code == 'GHO'
        # But summary is empty rather than "Defeated X 0-0" or score-flipped nonsense
        assert ctx['champion_summary'] == ''


def test_context_post_malformed_final_null_scores_no_summary(app):
    """Post state with Final marked complete but scores=None → no summary."""
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupMatch
    with app.app_context():
        bra = WorldCupTeam(
            fifa_code='BRA', name='Brazil', display_name='Brazil',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='C',
        )
        arg = WorldCupTeam(
            fifa_code='ARG', name='Argentina', display_name='Argentina',
            tier=2, multiplier=1.5, confederation='CONMEBOL', group_letter='B',
        )
        db.session.add_all([bra, arg])
        db.session.commit()
        final = WorldCupMatch(
            match_number=104, stage='final',
            home_team_id=bra.id, away_team_id=arg.id,
            home_score=None, away_score=None,
            winner_team_id=bra.id, is_completed=True,
        )
        db.session.add(final)
        db.session.commit()

        user = _make_user()
        ctx = build_home_context(user, 'post')
        assert ctx['champion_team'].fifa_code == 'BRA'
        assert ctx['champion_summary'] == ''  # not "Defeated ARG 0-0"


def test_context_live_week_delta_requires_seven_snapshots(app):
    """Week-delta only populates once we have a full week of snapshots.

    Earlier days only fill the sparkline (so the dossier still shows
    movement) but suppress the trend tagline that overstates a 2-day
    swing as a "weekly" trend.
    """
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupRankSnapshot
    from datetime import date, timedelta
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-20T00:00:00Z'}):
        user = _make_user()
        enr = _make_enrollment(user, picks_submitted=True, total_score=100.0)
        today = date(2026, 6, 20)
        # Only 6 snapshots (< 7 threshold)
        for i in range(6):
            db.session.add(WorldCupRankSnapshot(
                enrollment_id=enr.id,
                captured_date=today - timedelta(days=i),
                rank=i + 1,
                total_score=100.0 - i,
            ))
        db.session.commit()
        ctx = build_home_context(user, 'live')
        # Sparkline still populated (UX: show what we have)
        assert len(ctx['dossier']['sparkline_data']) == 6
        # But week-delta is suppressed until we have 7
        assert ctx['dossier']['week_delta_rank'] is None
        assert ctx['dossier']['week_delta_points'] is None


def test_context_live_week_delta_points_suppressed_when_baseline_zero(app):
    """Lounge ledger: a zero 7-day-ago baseline makes the points-delta equal
    the current total (reads as a glitch). Suppress the points-delta while
    keeping the rank-delta. $impeccable critique 2026-05-24."""
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupRankSnapshot
    from datetime import date, timedelta
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-06-20T00:00:00Z'}):
        user = _make_user()
        enr = _make_enrollment(user, picks_submitted=True, total_score=100.0)
        today = date(2026, 6, 20)
        for i in range(7):
            db.session.add(WorldCupRankSnapshot(
                enrollment_id=enr.id,
                captured_date=today - timedelta(days=i),
                rank=5 if i == 6 else 1,
                total_score=0.0 if i == 6 else 100.0,
            ))
        db.session.commit()
        ctx = build_home_context(user, 'live')
        # Rank-delta still computed — a baseline rank is always meaningful.
        assert ctx['dossier']['week_delta_rank'] == 1 - 5
        # Points-delta suppressed because the baseline scored 0.
        assert ctx['dossier']['week_delta_points'] is None


def test_context_pre_next_3_matches_excludes_completed(app):
    """Pre-state next_3_matches must exclude already-completed matches."""
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupMatch
    from datetime import datetime as dt
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-05-01T00:00:00Z'}):
        a = WorldCupTeam(fifa_code='AAA', name='A', display_name='A', tier=1, multiplier=1.0, confederation='T', group_letter='A')
        b = WorldCupTeam(fifa_code='BBB', name='B', display_name='B', tier=1, multiplier=1.0, confederation='T', group_letter='A')
        db.session.add_all([a, b])
        db.session.commit()
        # 1 completed (earliest kickoff) + 4 future incomplete
        kickoffs = [
            (1, dt(2026, 6, 11, 19, tzinfo=timezone.utc), True),
            (2, dt(2026, 6, 12, 19, tzinfo=timezone.utc), False),
            (3, dt(2026, 6, 13, 19, tzinfo=timezone.utc), False),
            (4, dt(2026, 6, 14, 19, tzinfo=timezone.utc), False),
            (5, dt(2026, 6, 15, 19, tzinfo=timezone.utc), False),
        ]
        for num, ko, completed in kickoffs:
            db.session.add(WorldCupMatch(
                match_number=num, stage='group', group_letter='A',
                home_team_id=a.id, away_team_id=b.id,
                kickoff_utc=ko, is_completed=completed,
            ))
        db.session.commit()

        user = _make_user()
        ctx = build_home_context(user, 'pre')
        assert len(ctx['next_3_matches']) == 3
        # The completed match (#1) must not appear
        assert all(m.match_number != 1 for m in ctx['next_3_matches'])
        # First three by kickoff among incomplete ones: 2, 3, 4
        assert [m.match_number for m in ctx['next_3_matches']] == [2, 3, 4]


def test_context_live_pick_results_carry_display_ready_stage_label(app):
    """Each your_pick_results item gets a precomputed stage_label so the
    template doesn't fall back to match.stage|title (which mangles
    'SF' → 'Sf', 'QF' → 'Qf', 'third_place' → 'Third_Place').
    """
    from core.main.home_context import build_home_context
    from games.worldcup.models import WorldCupTeam, WorldCupMatch, WorldCupPick
    with app.app_context(), patch.dict(os.environ, {'WC_FAKE_NOW': '2026-07-15T00:00:00Z'}):
        nor = WorldCupTeam(
            fifa_code='NOR', name='Norway', display_name='Norway',
            tier=5, multiplier=7.0, confederation='UEFA', group_letter='I',
        )
        opp = WorldCupTeam(
            fifa_code='OPP', name='Opp', display_name='Opp',
            tier=1, multiplier=1.0, confederation='TEST', group_letter='Z',
        )
        db.session.add_all([nor, opp])
        db.session.commit()
        # Knockout stage where match.stage|title would have produced 'Sf'
        sf_match = WorldCupMatch(
            match_number=99, stage='SF',
            home_team_id=nor.id, away_team_id=opp.id,
            home_score=2, away_score=1, is_completed=True,
            winner_team_id=nor.id,
        )
        db.session.add(sf_match)
        user = _make_user()
        enr = _make_enrollment(user, picks_submitted=True)
        db.session.add(WorldCupPick(enrollment_id=enr.id, team_id=nor.id, tier=5))
        db.session.commit()

        ctx = build_home_context(user, 'live')
        results = ctx['your_pick_results']
        assert len(results) == 1
        assert results[0]['stage_label'] == 'Semifinals'
        # Defensively: not the mangled fallback
        assert results[0]['stage_label'] != 'Sf'
