"""Pre-season posted-docket preview (2026-08-19 ruling): once a future week
has been imported, members read the frozen board before court convenes.
Every pick control stays off the page and every mutation stays refused;
current_week() is None until the start boundary, so the preview is display
only by construction."""
from datetime import datetime

from extensions import db
from games.docket.models import DocketPick
from tests._docket_fixtures import (
    at,
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

PRE_SEASON = '2026-08-20T12:00:00'
IN_WEEK1 = '2026-09-02T12:00:00'
WEEK1_KICKOFF = datetime(2026, 9, 3, 23, 0)  # naive UTC, Thu Sep 3


def _member(client):
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    return user


def _seeded_week():
    week = make_week(1)
    game = make_game(week, kickoff=WEEK1_KICKOFF,
                     home='Notre Dame', away='Wisconsin')
    return week, game


def test_preseason_shows_the_posted_docket_read_only(app, client, monkeypatch):
    _seeded_week()
    _member(client)
    at(monkeypatch, PRE_SEASON)
    data = client.get('/docket/').data.decode()
    assert 'Wisconsin' in data
    assert 'Notre Dame' in data
    assert 'Court convenes' in data
    assert 'docket-day-tab' in data
    # The board is inert: no pick, headliner, or tiebreaker controls.
    assert 'data-docket-action="set-pick"' not in data
    assert 'data-docket-action="set-tiebreaker"' not in data
    # Full-contrast resting pills, never the Cold-Docket dim.
    assert 'is-locked' not in data
    assert 'Locked at kickoff' not in data


def test_preseason_pick_post_is_refused(app, client, monkeypatch):
    _week, game = _seeded_week()
    _member(client)
    at(monkeypatch, PRE_SEASON)
    resp = client.post('/docket/picks/set', data={
        'csrf_token': 'x', 'game_id': game.id,
        'market': 'spread', 'side': 'home',
    })
    assert resp.status_code == 302
    assert DocketPick.query.count() == 0


def test_preseason_without_a_week_keeps_the_empty_state(
        app, client, monkeypatch):
    _member(client)
    at(monkeypatch, PRE_SEASON)
    data = client.get('/docket/').data.decode()
    assert 'The Week 1 docket posts Tuesday morning' in data
    assert 'docket-day-tab' not in data


def test_preseason_with_an_empty_week_keeps_the_empty_state(
        app, client, monkeypatch):
    make_week(1)
    _member(client)
    at(monkeypatch, PRE_SEASON)
    data = client.get('/docket/').data.decode()
    assert 'The Week 1 docket posts Tuesday morning' in data
    assert 'docket-day-tab' not in data


def test_preseason_hides_the_tiebreaker_form_even_when_designated(
        app, client, monkeypatch):
    week = make_week(1)
    game = make_game(week, kickoff=WEEK1_KICKOFF,
                     home='Notre Dame', away='Wisconsin')
    week.tiebreaker_game_id = game.id
    db.session.flush()
    _member(client)
    at(monkeypatch, PRE_SEASON)
    data = client.get('/docket/').data.decode()
    assert 'Tiebreaker case' in data
    assert 'data-docket-action="set-tiebreaker"' not in data


def test_in_season_sheet_is_unchanged_by_the_preview(
        app, client, monkeypatch):
    _seeded_week()
    _member(client)
    at(monkeypatch, IN_WEEK1)
    data = client.get('/docket/').data.decode()
    assert 'data-docket-action="set-pick"' in data
    assert 'Court adjourns' in data
