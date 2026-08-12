"""Docket models: import spine + grading spine (D6/D7/D14/D17/D20 subset).

Locks the all-UTC datetime contract (D6 — a deliberate deviation from CFB's
split naive-column contract, pre-approved), the identity/uniqueness rules the
import spine depends on (api_event_id keys game identity end-to-end, D22),
and the grading-spine structure: one-side-per-market and the 8+1 slot model
as schema constraints (D7-eng), integer-tenths key-3 storage (D20-eng), and
one result row per user+week (D14-eng).
"""
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError


def _all_docket_models():
    from games.docket.models import (
        DocketGame,
        DocketPick,
        DocketTiebreakerPrediction,
        DocketWeek,
        DocketWeekResult,
    )

    return (DocketWeek, DocketGame, DocketPick,
            DocketTiebreakerPrediction, DocketWeekResult)


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

    for model in _all_docket_models():
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


def test_audit_default_produces_naive_utc(app):
    """The created_at default must hand the driver a NAIVE UTC value — an
    aware value's storage in a timezone=False column would depend on driver
    offset handling (D6: the strip is explicit, never implicit)."""
    for model in _all_docket_models():
        default = model.__table__.c.created_at.default.arg
        value = default(None)  # SQLAlchemy wraps the lambda to take ctx
        assert value.tzinfo is None, (
            f'{model.__name__}.created_at default must be naive UTC')


def test_week_tiebreaker_designation_points_at_a_game(app):
    from extensions import db

    week = _mk_week(db)
    game = _mk_game(db, week)
    week.tiebreaker_game_id = game.id
    db.session.commit()
    assert week.tiebreaker_game.api_event_id == 'evt1'


# --- Grading spine: DocketPick / DocketTiebreakerPrediction / DocketWeekResult


def _mk_user(db, name='alice'):
    from models import User

    user = User(username=name, email=f'{name}@test.com')
    user.password_hash = 'x'
    db.session.add(user)
    db.session.commit()
    return user


def _mk_pick(db, user, week, game, slot=1, market='spread', side='home', **kw):
    from games.docket.models import DocketPick

    pick = DocketPick(
        user_id=user.id,
        week_id=week.id,
        game_id=game.id,
        slot=slot,
        market=market,
        side=side,
        line_value=kw.pop('line_value', -6.5),
        book=kw.pop('book', 'draftkings'),
        **kw,
    )
    db.session.add(pick)
    db.session.commit()
    return pick


def test_new_pick_is_neither_filed_nor_auto_designated(app):
    """Both provenance flags are opt-in, written only by the deadline pass.
    is_auto_best is separate from is_autopick because auto-designation can
    land the double on a pick the player made themselves."""
    from extensions import db

    user, week = _mk_user(db), _mk_week(db)
    pick = _mk_pick(db, user, week, _mk_game(db, week))
    assert pick.is_best is False
    assert pick.is_autopick is False
    assert pick.is_auto_best is False


def test_pick_rejects_both_sides_of_one_market(app):
    """D7-eng: one-side-per-market is STRUCTURAL — (user, week, game, market)
    is unique, so holding home and away of the same spread is a schema
    violation, not a form-validation nicety."""
    from extensions import db

    user, week = _mk_user(db), _mk_week(db)
    game = _mk_game(db, week)
    _mk_pick(db, user, week, game, slot=1, market='spread', side='home')
    with pytest.raises(IntegrityError):
        _mk_pick(db, user, week, game, slot=2, market='spread', side='away')
    db.session.rollback()


def test_pick_allows_spread_and_total_on_same_game(app):
    """Core ruling: a spread pick and a total pick on the SAME game are two
    legal picks — the constraint is per-market, not per-game."""
    from extensions import db

    user, week = _mk_user(db), _mk_week(db)
    game = _mk_game(db, week)
    _mk_pick(db, user, week, game, slot=1, market='spread', side='home')
    _mk_pick(db, user, week, game, slot=2, market='total', side='over',
             line_value=51.5)
    from sqlalchemy import func, select

    from games.docket.models import DocketPick
    assert db.session.scalar(
        select(func.count()).select_from(DocketPick)) == 2


def test_pick_slot_unique_per_user_week(app):
    """D7-eng: (user, week, slot) is unique — the 8+1 slot model is schema."""
    from extensions import db

    user, week = _mk_user(db), _mk_week(db)
    g1 = _mk_game(db, week, eid='g1')
    g2 = _mk_game(db, week, eid='g2', home_team='Ohio State Buckeyes',
                  away_team='Texas Longhorns')
    _mk_pick(db, user, week, g1, slot=1)
    with pytest.raises(IntegrityError):
        _mk_pick(db, user, week, g2, slot=1)
    db.session.rollback()


def test_pick_slot_range_is_1_through_9(app):
    """Slots are 1–8 scoring + 9 backup; anything else is refused at the
    schema (a slot-10 write is a bug, never data)."""
    from extensions import db

    user, week = _mk_user(db), _mk_week(db)
    game = _mk_game(db, week)
    for bad_slot in (0, 10):
        with pytest.raises(IntegrityError):
            _mk_pick(db, user, week, game, slot=bad_slot)
        db.session.rollback()


def test_pick_single_best_per_user_week(app):
    """D7-eng: partial unique index — at most one is_best pick per (user,
    week); unlimited is_best=False rows; other users unaffected."""
    from extensions import db

    user, week = _mk_user(db), _mk_week(db)
    g1 = _mk_game(db, week, eid='g1')
    g2 = _mk_game(db, week, eid='g2', home_team='Ohio State Buckeyes',
                  away_team='Texas Longhorns')
    g3 = _mk_game(db, week, eid='g3', home_team='Michigan Wolverines',
                  away_team='Oklahoma Sooners')
    _mk_pick(db, user, week, g1, slot=1, is_best=True)
    _mk_pick(db, user, week, g2, slot=2)  # is_best=False coexists
    _mk_pick(db, user, week, g3, slot=3)
    with pytest.raises(IntegrityError):
        _mk_pick(db, user, week,
                 _mk_game(db, week, eid='g4', home_team='H4', away_team='A4'),
                 slot=4, is_best=True)
    db.session.rollback()

    other = _mk_user(db, name='bob')
    _mk_pick(db, other, week, g1, slot=1, is_best=True)  # other user is fine


def test_pick_best_never_on_backup_slot(app):
    """D6-session: the backup (slot 9) can never carry the designation — the
    double lives on a SCORING slot and only substitution moves results."""
    from extensions import db

    user, week = _mk_user(db), _mk_week(db)
    game = _mk_game(db, week)
    with pytest.raises(IntegrityError):
        _mk_pick(db, user, week, game, slot=9, is_best=True)
    db.session.rollback()


def test_pick_line_snapshot_is_mandatory(app):
    """D7-eng: line_value + book are snapshotted onto every pick at creation
    — schema-level NOT NULL (the write-path parity lock vs the game's locked
    line lands with the pick service)."""
    from games.docket.models import DocketPick

    assert DocketPick.__table__.c.line_value.nullable is False
    assert DocketPick.__table__.c.book.nullable is False


def test_prediction_is_stored_as_integer_tenths(app):
    """D20-eng: key-3 storage is integer tenths (515 == 51.5) — the column
    type itself is Integer so no float can ever enter key 3 at rest."""
    from sqlalchemy import Integer

    from extensions import db
    from games.docket.models import DocketTiebreakerPrediction

    assert isinstance(
        DocketTiebreakerPrediction.__table__.c.prediction_tenths.type,
        Integer)

    user, week = _mk_user(db), _mk_week(db)
    row = DocketTiebreakerPrediction(
        user_id=user.id, week_id=week.id, prediction_tenths=515)
    db.session.add(row)
    db.session.commit()
    assert row.prediction_tenths == 515


def test_prediction_unique_per_user_week(app):
    from extensions import db
    from games.docket.models import DocketTiebreakerPrediction

    user, week = _mk_user(db), _mk_week(db)
    db.session.add(DocketTiebreakerPrediction(
        user_id=user.id, week_id=week.id, prediction_tenths=515))
    db.session.commit()
    db.session.add(DocketTiebreakerPrediction(
        user_id=user.id, week_id=week.id, prediction_tenths=471))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_week_result_unique_per_user_week(app):
    """D14-eng: one docket_week_result row per (user, week) — the
    CfbWeekOutcome pattern; error is integer tenths (D20-eng)."""
    from sqlalchemy import Integer

    from extensions import db
    from games.docket.models import DocketWeekResult

    assert isinstance(DocketWeekResult.__table__.c.error_tenths.type, Integer)

    user, week = _mk_user(db), _mk_week(db)
    db.session.add(DocketWeekResult(
        user_id=user.id, week_id=week.id, points=6.5, wins=5,
        error_tenths=33, graded_at=datetime(2026, 9, 8, 5, 0)))
    db.session.commit()
    db.session.add(DocketWeekResult(
        user_id=user.id, week_id=week.id, points=7.0, wins=6,
        error_tenths=12, graded_at=datetime(2026, 9, 8, 6, 0)))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_new_game_carries_no_score_and_no_ruling(app):
    """Scores/finality/No Contest are grading-spine columns: empty at import,
    written by the scores pass or an admin NC ruling (final score includes
    overtime by D23-eng — a grading rule, not a schema shape)."""
    from extensions import db

    week = _mk_week(db)
    game = _mk_game(db, week)
    assert game.home_score is None
    assert game.away_score is None
    assert game.is_final is False
    assert game.no_contest is False
    assert game.nc_reason is None
