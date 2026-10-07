"""Golf's relationships are plain many-to-one, declared on the child.

The models once carried ``lazy='dynamic'`` collections and ``backref=`` pairs
(``GolfTournament.picks``, ``User.golf_picks``, ...) that nothing read: golf
always queries the child model directly. They were dropped, and the four
many-to-one sides that existed only as backrefs are declared where they live.
These locks keep a collection or a backref from growing back unnoticed.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import configure_mappers
from sqlalchemy.orm.interfaces import MANYTOONE

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfSeasonPlayerUsage,
    GolfTournament,
    GolfTournamentField,
    GolfTournamentResult,
)
from models.user import User

EXPECTED = {
    GolfEnrollment: {'user'},
    GolfPlayer: set(),
    GolfTournament: set(),
    GolfTournamentField: {'tournament', 'player'},
    GolfSeasonPlayerUsage: {'user', 'player'},
    GolfTournamentResult: {'tournament', 'player'},
    GolfPick: {'user', 'tournament', 'primary_player', 'backup_player', 'active_player'},
}

RETIRED_USER_COLLECTIONS = ('golf_enrollments', 'golf_season_usages', 'golf_picks', 'push_subscriptions')


def _relationships(model):
    return db.inspect(model).relationships


def test_no_dynamic_relationship_anywhere(app):
    configure_mappers()
    dynamic = [
        f'{mapper.class_.__name__}.{rel.key}'
        for mapper in db.Model.registry.mappers
        for rel in mapper.relationships
        if rel.lazy == 'dynamic'
    ]
    assert dynamic == []


def test_golf_relationships_are_exactly_the_many_to_one_sides(app):
    configure_mappers()
    for model, expected in EXPECTED.items():
        rels = _relationships(model)
        assert set(rels.keys()) == expected, model.__name__
        for rel in rels:
            assert rel.direction is MANYTOONE, f'{model.__name__}.{rel.key}'


def test_user_carries_no_retired_collection(app):
    configure_mappers()
    keys = set(_relationships(User).keys())
    assert keys.isdisjoint(RETIRED_USER_COLLECTIONS)
    assert not any(k.startswith('golf_') for k in keys)


def test_declared_many_to_one_sides_load(app):
    now = datetime.now(UTC)
    user = User(username='rel_golfer', email='rel_golfer@example.com')
    user.set_password('x')
    db.session.add(user)
    tournament = GolfTournament(
        api_tourn_id='rel-001', name='Relationship Open', season_year=2026,
        start_date=now + timedelta(days=2), end_date=now + timedelta(days=5),
        status='upcoming',
    )
    primary = GolfPlayer(api_player_id='rel-p1', first_name='Pri', last_name='Mary')
    backup = GolfPlayer(api_player_id='rel-p2', first_name='Back', last_name='Up')
    db.session.add_all([tournament, primary, backup])
    db.session.flush()
    field = GolfTournamentField(tournament_id=tournament.id, player_id=primary.id)
    result = GolfTournamentResult(tournament_id=tournament.id, player_id=primary.id,
                                  status='active', rounds_completed=0)
    pick = GolfPick(user_id=user.id, tournament_id=tournament.id,
                    primary_player_id=primary.id, backup_player_id=backup.id)
    db.session.add_all([field, result, pick])
    db.session.commit()
    db.session.expire_all()

    field = db.session.get(GolfTournamentField, field.id)
    result = db.session.get(GolfTournamentResult, result.id)
    pick = db.session.get(GolfPick, pick.id)
    assert field.tournament.name == 'Relationship Open'
    assert field.player.last_name == 'Mary'
    assert result.tournament.name == 'Relationship Open'
    assert result.player.last_name == 'Mary'
    assert pick.tournament.name == 'Relationship Open'
    assert pick.user.username == 'rel_golfer'
    assert pick.backup_player.last_name == 'Up'
