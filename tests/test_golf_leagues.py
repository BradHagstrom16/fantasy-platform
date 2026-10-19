"""The Pay Sheet's two leagues (ADR-075): the spec lock for the whole change.

Golf is one game with two leagues inside it, Handicap (the house league) and
Pollyanna. Each league is a row in ``golf_league`` carrying its own entry fee
and penalty; every enrollment, pick and golfer usage belongs to exactly one.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from games.golf.models import GolfEnrollment
from games.golf.services.leagues import (
    house_league,
    league_by_slug,
    leagues,
    seed_leagues,
)
from models.user import User


def _user(username):
    user = User(username=username, email=f'{username}@example.com')
    user.set_password('x')
    db.session.add(user)
    db.session.commit()
    return user


def test_seed_leagues_is_idempotent_and_ordered(app):
    seed_leagues()
    seed_leagues()

    assert [league.slug for league in leagues()] == ['handicap', 'pollyanna']
    assert [league.name for league in leagues()] == ['Handicap Pay Sheet', 'Pollyanna Pay Sheet']
    assert house_league().slug == 'handicap'
    assert league_by_slug('pollyanna').ordinal == 2
    assert league_by_slug('nope') is None
    for league in leagues():
        assert league.entry_fee == 25
        assert league.penalty_per_incident == 15


def test_the_same_member_holds_a_line_in_both_leagues(app, golf_leagues):
    brad = _user('two_sheets')
    db.session.add_all([
        GolfEnrollment(user_id=brad.id, league_id=golf_leagues['handicap'].id, season_year=2027),
        GolfEnrollment(user_id=brad.id, league_id=golf_leagues['pollyanna'].id, season_year=2027),
    ])
    db.session.commit()

    db.session.add(GolfEnrollment(user_id=brad.id, league_id=golf_leagues['handicap'].id,
                                  season_year=2027))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
