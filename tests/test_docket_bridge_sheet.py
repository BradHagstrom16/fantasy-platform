"""The tiebreaker hand override (games/docket/services/bridge_sheet.py)."""
from datetime import datetime

import pytest


def _seed(db, tiebreaker=True):
    from games.docket.models import DocketGame, DocketWeek

    week = DocketWeek(
        season_year=2026,
        week_number=1,
        start_at=datetime(2026, 9, 1, 11, 0),
        end_at=datetime(2026, 9, 8, 11, 0),
        deadline_at=datetime(2026, 9, 5, 16, 0),
    )
    db.session.add(week)
    db.session.flush()
    wnd = DocketGame(
        week_id=week.id, sport='americanfootball_ncaaf', api_event_id='e-wnd',
        home_team='Notre Dame Fighting Irish', away_team='Wisconsin Badgers',
        kickoff=datetime(2026, 9, 6, 0, 30),  # Sat Sep 5, 7:30 PM CT
        home_spread=-6.5, spread_book='draftkings',
        spread_locked_at=datetime(2026, 9, 1, 11, 5),
        total_points=51.5, total_book='draftkings',
        total_locked_at=datetime(2026, 9, 1, 11, 5),
    )
    early = DocketGame(
        week_id=week.id, sport='americanfootball_ncaaf', api_event_id='e-thu',
        home_team='Texas Longhorns', away_team='Ohio State Buckeyes',
        kickoff=datetime(2026, 9, 4, 0, 30),  # Thu Sep 3, 7:30 PM CT
        home_spread=3.0, spread_book='fanduel',
        spread_locked_at=datetime(2026, 9, 1, 11, 5),
    )
    db.session.add_all([wnd, early])
    db.session.flush()
    if tiebreaker:
        week.tiebreaker_game_id = wnd.id
    db.session.commit()
    return week


def test_set_tiebreaker_matches_away_at_home(app, monkeypatch):
    from extensions import db
    from games.docket.services.bridge_sheet import set_tiebreaker
    from tests._docket_fixtures import at

    week = _seed(db, tiebreaker=False)
    at(monkeypatch, '2026-09-02T12:00:00')  # designation is pre-deadline only
    game = set_tiebreaker(week, 'Wisconsin @ Notre Dame')
    assert game.api_event_id == 'e-wnd'
    assert week.tiebreaker_game_id == game.id


def test_set_tiebreaker_is_refused_once_the_docket_closes(app, monkeypatch):
    """The CLI fallback shares the admin service, so it inherits the
    pre-deadline gate: a designation cannot move after the docket closes."""
    from extensions import db
    from games.docket.services.bridge_sheet import set_tiebreaker
    from tests._docket_fixtures import at

    week = _seed(db, tiebreaker=False)
    at(monkeypatch, '2026-09-05T16:30:00')
    with pytest.raises(ValueError, match='closed'):
        set_tiebreaker(week, 'Wisconsin @ Notre Dame')
    assert week.tiebreaker_game_id is None


def test_set_tiebreaker_rejects_unmatched_and_ambiguous(app):
    from extensions import db
    from games.docket.services.bridge_sheet import set_tiebreaker

    week = _seed(db, tiebreaker=False)
    with pytest.raises(ValueError):
        set_tiebreaker(week, 'Slippery Rock @ Nowhere State')
    with pytest.raises(ValueError):
        set_tiebreaker(week, ' @ ')  # blank sides match every game
    with pytest.raises(ValueError):
        set_tiebreaker(week, 'Wisconsin @ ')  # one blank side


def test_blank_tiebreaker_never_matches_a_one_game_week(app):
    """CR regression: on a one-game week, blank sides would substring-match
    that single game and silently designate it. Must raise instead."""
    from extensions import db
    from games.docket.services.bridge_sheet import set_tiebreaker

    week = _seed(db, tiebreaker=False)
    # Reduce the week to a single game.
    for game in list(week.games)[1:]:
        db.session.delete(game)
    db.session.commit()
    assert len(week.games) == 1
    with pytest.raises(ValueError):
        set_tiebreaker(week, ' @ ')
    assert week.tiebreaker_game_id is None
