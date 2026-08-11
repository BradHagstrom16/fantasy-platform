"""Bridge sheet generator (games/docket/services/bridge_sheet.py, D22).

The generated rows ARE the bridge: they go into the Google Sheet verbatim,
the Apps Script grades off these numbers, and the importer later joins on
api_event_id. Snapshot-locked so the sheet contract can't drift silently.
"""
from datetime import datetime

import pytest


def _seed(db, tiebreaker=True):
    from games.docket.models import DocketGame, DocketWeek

    week = DocketWeek(
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


def test_sheet_rows_snapshot(app):
    """The full row contract: kickoff-ordered, CT-humanized kickoffs, signed
    home spreads, per-market books, empty strings for unlocked markets,
    TRUE only on the designated tiebreaker game."""
    from extensions import db
    from games.docket.services.bridge_sheet import build_sheet_rows

    week = _seed(db)
    assert build_sheet_rows(week) == [
        {
            'api_event_id': 'e-thu', 'sport': 'CFB',
            'away_team': 'Ohio State Buckeyes', 'home_team': 'Texas Longhorns',
            'kickoff_ct': 'Thu Sep 3, 7:30 PM CT',
            'home_spread': '+3', 'spread_book': 'fanduel',
            'total': '', 'total_book': '',
            'tiebreaker': '',
        },
        {
            'api_event_id': 'e-wnd', 'sport': 'CFB',
            'away_team': 'Wisconsin Badgers', 'home_team': 'Notre Dame Fighting Irish',
            'kickoff_ct': 'Sat Sep 5, 7:30 PM CT',
            'home_spread': '-6.5', 'spread_book': 'draftkings',
            'total': '51.5', 'total_book': 'draftkings',
            'tiebreaker': 'TRUE',
        },
    ]


def test_csv_snapshot(app):
    from extensions import db
    from games.docket.services.bridge_sheet import build_sheet_rows, rows_to_csv

    week = _seed(db)
    csv_text = rows_to_csv(build_sheet_rows(week))
    assert csv_text == (
        'api_event_id,sport,away_team,home_team,kickoff_ct,'
        'home_spread,spread_book,total,total_book,tiebreaker\n'
        'e-thu,CFB,Ohio State Buckeyes,Texas Longhorns,'
        '"Thu Sep 3, 7:30 PM CT",+3,fanduel,,,\n'
        'e-wnd,CFB,Wisconsin Badgers,Notre Dame Fighting Irish,'
        '"Sat Sep 5, 7:30 PM CT",-6.5,draftkings,51.5,draftkings,TRUE\n'
    )


def test_set_tiebreaker_matches_away_at_home(app):
    from extensions import db
    from games.docket.services.bridge_sheet import set_tiebreaker

    week = _seed(db, tiebreaker=False)
    game = set_tiebreaker(week, 'Wisconsin @ Notre Dame')
    assert game.api_event_id == 'e-wnd'
    assert week.tiebreaker_game_id == game.id


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
