"""Tests for the World Cup football-data.org sync service."""
import pytest
from unittest.mock import patch

from app import create_app
from extensions import db
from games.worldcup.models import WorldCupTeam, WorldCupMatch


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _team(fifa, name, group, tier=1, mult=1.0):
    t = WorldCupTeam(fifa_code=fifa, name=name, display_name=name, tier=tier,
                     multiplier=mult, confederation='UEFA', group_letter=group)
    db.session.add(t)
    return t


def test_match_and_team_have_api_id_columns(app):
    with app.app_context():
        t = _team('MEX', 'Mexico', 'A')
        db.session.flush()
        t.api_team_id = 769
        m = WorldCupMatch(match_number=1, stage='group', group_letter='A',
                          home_team_id=t.id, api_fixture_id=537001)
        db.session.add(m)
        db.session.commit()
        assert db.session.get(WorldCupTeam, t.id).api_team_id == 769
        assert WorldCupMatch.query.filter_by(match_number=1).first().api_fixture_id == 537001
