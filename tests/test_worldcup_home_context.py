"""Tests for games.worldcup.services.home_context.build_worldcup_home_context.

This file covers the dispatcher in Task 5; per-builder tests are added in
Tasks 6 (out), 7 (pre), 8 (live), 9 (post).
"""
import os
from datetime import timedelta
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from games.worldcup.constants import (
    SEASON_YEAR, ENTRY_FEE, TOURNAMENT_DEADLINE_UTC,
)
from games.worldcup.services.home_context import (
    build_worldcup_home_context, _context_out,
)
from tests._worldcup_fixtures import (
    make_user, make_enrollment, seed_full_tournament,
)


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.mark.parametrize('state,expected_marker', [
    ('pre', '_marker_pre'),
    ('live', '_marker_live'),
    ('post', '_marker_post'),
])
def test_dispatcher_routes_to_correct_builder(app, state, expected_marker):
    """Each remaining builder stub returns a context dict containing a unique
    marker key. Assert the dispatcher returns the right one. The 'out' branch
    is implemented in Task 6 and asserted via its real-shape tests below."""
    ctx = build_worldcup_home_context(user=None, state=state)
    assert expected_marker in ctx, (
        f'state={state} expected marker {expected_marker} in context, '
        f'got keys: {list(ctx.keys())}'
    )


def test_dispatcher_routes_to_out_builder(app):
    """The 'out' builder is implemented (Task 6), so the dispatcher should
    return its real-shape dict (state='out') rather than a stub marker."""
    ctx = build_worldcup_home_context(user=None, state='out')
    assert ctx['state'] == 'out'
    assert ctx['cta_state'] == 'guest'


def test_dispatcher_raises_on_unknown_state(app):
    with pytest.raises(ValueError, match='unknown worldcup hub state'):
        build_worldcup_home_context(user=None, state='mystery')


# =====================================================================
# Task 6: _context_out builder tests
# =====================================================================

def test_context_out_anonymous_user_is_guest(app):
    ctx = _context_out(user=None)
    assert ctx['state'] == 'out'
    assert ctx['cta_state'] == 'guest'
    assert ctx['is_authenticated'] is False
    assert ctx['display_name'] is None


def test_context_out_authenticated_unenrolled_pre_deadline(app):
    user = make_user()
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_out(user=user)
    assert ctx['cta_state'] == 'unenrolled_pre'
    assert ctx['is_authenticated'] is True
    assert ctx['display_name'] == 'U'


def test_context_out_authenticated_unenrolled_live(app):
    user = make_user()
    db.session.commit()
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_out(user=user)
    assert ctx['cta_state'] == 'unenrolled_live'


def test_context_out_authenticated_unenrolled_post(app):
    user = make_user()
    # Mark final complete to trigger 'post' phase
    from games.worldcup.models import WorldCupMatch
    final = WorldCupMatch(match_number=104, stage='final', is_completed=True)
    db.session.add(final)
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_out(user=user)
    assert ctx['cta_state'] == 'unenrolled_post'


def test_context_out_includes_voice_copy(app):
    ctx = _context_out(user=None)
    assert 'copy' in ctx
    assert ctx['copy']['eyebrow']  # non-empty
    assert ctx['copy']['headline']
    assert ctx['copy']['subhead']


def test_context_out_includes_total_enrolled(app):
    seed_full_tournament(num_enrollments=3)
    ctx = _context_out(user=None)
    assert ctx['total_enrolled'] == 3


def test_context_out_top_3_preview_only_when_live_or_post(app):
    seed_full_tournament(num_enrollments=5)
    user = make_user(email='spectator@test')
    db.session.commit()

    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx_pre = _context_out(user=user)
    assert ctx_pre['top_3_preview'] == []

    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx_live = _context_out(user=user)
    assert len(ctx_live['top_3_preview']) == 3
    # Top-3 ordered by total_score DESC — seed gives 100 / 95 / 90 / 85 / 80
    assert [e.total_score for e in ctx_live['top_3_preview']] == [100.0, 95.0, 90.0]


def test_context_out_includes_entry_fee_and_deadline(app):
    ctx = _context_out(user=None)
    assert ctx['entry_fee'] == ENTRY_FEE
    assert ctx['deadline_ct'] is not None
