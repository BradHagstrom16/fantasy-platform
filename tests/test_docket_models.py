"""Docket model slice: DocketWeek + DocketGame (D6/D7/D17 subset).

Locks the all-UTC datetime contract (D6 — a deliberate deviation from CFB's
split naive-column contract, pre-approved) and the identity/uniqueness rules
the import spine depends on (api_event_id keys game identity end-to-end, D22).
"""
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError


def _mk_week(db, number=1):
    from games.docket.models import DocketWeek

    week = DocketWeek(
        week_number=number,
        start_at=datetime(2026, 9, 1, 11, 0),
        end_at=datetime(2026, 9, 8, 11, 0),
        deadline_at=datetime(2026, 9, 5, 16, 0),
    )
    db.session.add(week)
    db.session.commit()
    return week


def _mk_game(db, week, eid='evt1', **kw):
    from games.docket.models import DocketGame

    game = DocketGame(
        week_id=week.id,
        sport=kw.pop('sport', 'americanfootball_ncaaf'),
        api_event_id=eid,
        home_team=kw.pop('home_team', 'Notre Dame Fighting Irish'),
        away_team=kw.pop('away_team', 'Wisconsin Badgers'),
        kickoff=kw.pop('kickoff', datetime(2026, 9, 5, 0, 30)),
        **kw,
    )
    db.session.add(game)
    db.session.commit()
    return game


def test_all_docket_datetime_columns_are_timezone_naive_utc(app):
    """D6 lock, schema level: no docket column may be created timezone-aware —
    the contract is naive UTC everywhere, one converter story at render."""
    from sqlalchemy import DateTime

    from games.docket.models import DocketGame, DocketWeek

    for model in (DocketWeek, DocketGame):
        dt_cols = [c for c in model.__table__.columns
                   if isinstance(c.type, DateTime)]
        assert dt_cols, f'{model.__name__} must carry datetime columns'
        for col in dt_cols:
            assert not col.type.timezone, (
                f'{model.__name__}.{col.name} is timezone-aware; the docket '
                f'contract is naive UTC (D6)')


def test_models_module_never_touches_wall_clock_helpers():
    """D6 lock, source level: the contract is documented atop models.py and no
    pool-timezone helper may creep in (make_aware on a UTC column is the CFB
    +5/6h mislabel bug the single contract exists to prevent)."""
    import inspect

    import games.docket.models as models_module

    source = inspect.getsource(models_module)
    assert 'naive UTC' in source.split('"""')[1], (
        'the UTC contract must be documented in the module docstring')
    for forbidden in ('make_aware', 'ZoneInfo', 'to_pool_time', 'astimezone'):
        assert forbidden not in source, (
            f'{forbidden} must not appear in docket models (D6 all-UTC contract)')


def test_api_event_id_is_globally_unique(app):
    """D22: api_event_id keys game identity end-to-end — duplicates are a
    schema violation, not a soft dedupe."""
    from extensions import db

    week = _mk_week(db)
    _mk_game(db, week, eid='dup')
    with pytest.raises(IntegrityError):
        _mk_game(db, week, eid='dup', home_team='Ohio State Buckeyes',
                 away_team='Texas Longhorns')


def test_week_number_is_unique(app):
    from extensions import db

    _mk_week(db, number=1)
    with pytest.raises(IntegrityError):
        _mk_week(db, number=1)


def test_new_game_carries_no_lines_and_no_frozen_kickoff(app):
    """Lines exist only once locked (value + book + locked_at move together,
    D17), and kickoff_at_deadline stays empty until the deadline pass (D7)."""
    from extensions import db

    week = _mk_week(db)
    game = _mk_game(db, week)
    assert game.home_spread is None
    assert game.spread_book is None
    assert game.spread_locked_at is None
    assert game.total_points is None
    assert game.total_book is None
    assert game.total_locked_at is None
    assert game.kickoff_at_deadline is None


def test_week_tiebreaker_designation_points_at_a_game(app):
    from extensions import db

    week = _mk_week(db)
    game = _mk_game(db, week)
    week.tiebreaker_game_id = game.id
    db.session.commit()
    assert week.tiebreaker_game.api_event_id == 'evt1'
