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


def test_worldcup_state_pre_when_before_deadline(app):
    """Before TOURNAMENT_DEADLINE_UTC, state is 'pre'."""
    from games.worldcup.services.state import worldcup_state
    # Default: TOURNAMENT_DEADLINE_UTC = 2026-06-11 19:00 UTC. Today is well before.
    with app.app_context():
        # In test runs after kickoff this would naturally fail; force-mock:
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['WC_FAKE_NOW'] = '2026-05-01T00:00:00Z'
        try:
            assert worldcup_state() == 'pre'
        finally:
            del os.environ['WC_FAKE_NOW']
            os.environ.pop('ENVIRONMENT', None)


def test_worldcup_state_live_after_deadline_no_final(app):
    """After deadline + final not complete, state is 'live'."""
    from games.worldcup.services.state import worldcup_state
    with app.app_context():
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['WC_FAKE_NOW'] = '2026-06-15T00:00:00Z'
        try:
            assert worldcup_state() == 'live'
        finally:
            del os.environ['WC_FAKE_NOW']
            os.environ.pop('ENVIRONMENT', None)


def test_worldcup_state_post_when_final_completed(app):
    """After deadline + final marked complete, state is 'post'."""
    from games.worldcup.services.state import worldcup_state
    with app.app_context():
        _seed_final_match(completed=True, winner_id=None)
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['WC_FAKE_NOW'] = '2026-07-20T00:00:00Z'
        try:
            assert worldcup_state() == 'post'
        finally:
            del os.environ['WC_FAKE_NOW']
            os.environ.pop('ENVIRONMENT', None)


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
