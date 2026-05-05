"""Tests for games.worldcup.services.home_context.build_worldcup_home_context.

This file covers the dispatcher in Task 5; per-builder tests are added in
Tasks 6 (out), 7 (pre), 8 (live), 9 (post).
"""
import pytest

from app import create_app
from extensions import db
from games.worldcup.services.home_context import build_worldcup_home_context


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.mark.parametrize('state,expected_marker', [
    ('out', '_marker_out'),
    ('pre', '_marker_pre'),
    ('live', '_marker_live'),
    ('post', '_marker_post'),
])
def test_dispatcher_routes_to_correct_builder(app, state, expected_marker):
    """Each builder stub returns a context dict containing a unique marker
    key. Assert the dispatcher returns the right one."""
    ctx = build_worldcup_home_context(user=None, state=state)
    assert expected_marker in ctx, (
        f'state={state} expected marker {expected_marker} in context, '
        f'got keys: {list(ctx.keys())}'
    )


def test_dispatcher_raises_on_unknown_state(app):
    with pytest.raises(ValueError, match='unknown worldcup hub state'):
        build_worldcup_home_context(user=None, state='mystery')
