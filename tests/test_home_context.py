"""Unit tests for home-page state detection and context assembly (Spec B)."""
import os
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
    """Seed match #104 (the Final). Used to flip live → post."""
    from games.worldcup.models import WorldCupMatch
    match = WorldCupMatch(
        match_number=104,
        stage='final',
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
