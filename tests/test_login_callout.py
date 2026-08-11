"""Render locks for the era-neutral login callout (Phase 5 changeover).

The callout branches on the sanitized ``next`` path: CFB deep-links get the
survivor line, WC deep-links get the archive line, everything else (including
crafted ``/cfb-*`` prefixes — CR finding on PR #133) gets the default line.
"""
import pytest

from app import create_app
from extensions import db


@pytest.fixture()
def client():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def _callout(client, query=''):
    resp = client.get(f'/login{query}')
    assert resp.status_code == 200
    return resp.data.decode()


def test_cfb_next_shows_survivor_callout(client):
    body = _callout(client, '?next=/cfb/my-picks')
    assert 'one step away from the <strong>CFB Survivor Pool</strong>' in body


def test_worldcup_next_shows_archive_callout(client):
    body = _callout(client, '?next=/worldcup/leaderboard')
    assert 'archive awaits inside' in body


def test_default_shows_open_callout(client):
    body = _callout(client)
    assert 'CFB Survivor Pool</strong> is open. Join today.' in body


def test_crafted_prefix_falls_through_to_default(client):
    """/cfb-other must NOT match the CFB deep-link branch (PR #133 CR fix)."""
    body = _callout(client, '?next=/cfb-other')
    assert 'is open. Join today.' in body
    assert 'one step away' not in body
