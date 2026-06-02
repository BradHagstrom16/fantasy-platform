"""Tests for the World Cup football-data.org sync service."""
from datetime import datetime

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


def test_api_get_raises_without_key(app):
    from games.worldcup.services.sync import _api_get, SyncError
    with app.app_context():
        app.config['FOOTBALL_DATA_API_KEY'] = ''
        with pytest.raises(SyncError):
            _api_get('competitions/WC/matches')


def test_api_get_returns_json_on_200(app):
    from games.worldcup.services import sync
    with app.app_context():
        app.config['FOOTBALL_DATA_API_KEY'] = 'k'

        class _Resp:
            status_code = 200
            headers = {'X-Requests-Available-Minute': '9'}
            def json(self): return {'matches': []}

        with patch.object(sync.requests, 'get', return_value=_Resp()) as g:
            out = sync._api_get('competitions/WC/matches')
        assert out == {'matches': []}
        # Auth header is sent
        assert g.call_args.kwargs['headers']['X-Auth-Token'] == 'k'


def _seed_group_pair(app):
    """Two teams + their group match shell, kickoff matching the API sample."""
    with app.app_context():
        mex = _team('MEX', 'Mexico', 'A')
        rsa = _team('RSA', 'South Africa', 'A')
        db.session.flush()
        m = WorldCupMatch(match_number=1, stage='group', group_letter='A',
                          home_team_id=mex.id, away_team_id=rsa.id,
                          kickoff_utc=datetime(2026, 6, 11, 19, 0, 0))
        db.session.add(m)
        db.session.commit()
        return m.id


_API_MATCHES_FIXTURE = {'matches': [{
    'id': 537001, 'utcDate': '2026-06-11T19:00:00Z', 'status': 'TIMED',
    'stage': 'GROUP_STAGE', 'group': 'Group A',
    'homeTeam': {'id': 769, 'name': 'Mexico', 'tla': 'MEX'},
    'awayTeam': {'id': 805, 'name': 'South Africa', 'tla': 'RSA'},
    'score': {'winner': None, 'duration': 'REGULAR',
              'fullTime': {'home': None, 'away': None}},
}]}


def test_link_fixtures_maps_ids(app):
    from games.worldcup.services import sync
    mid = _seed_group_pair(app)
    with app.app_context():
        with patch.object(sync, '_api_get', return_value=_API_MATCHES_FIXTURE):
            report = sync.link_fixtures()
        m = db.session.get(WorldCupMatch, mid)
        assert m.api_fixture_id == 537001
        assert db.session.get(WorldCupTeam, m.home_team_id).api_team_id == 769
        assert db.session.get(WorldCupTeam, m.away_team_id).api_team_id == 805
        assert report['fixtures_linked'] == 1
        assert report['unmatched_fixtures'] == []


def test_link_fixtures_reports_unmatched(app):
    from games.worldcup.services import sync
    _seed_group_pair(app)
    bad = {'matches': [{
        'id': 999, 'utcDate': '2026-06-11T19:00:00Z', 'status': 'TIMED',
        'stage': 'GROUP_STAGE', 'group': 'Group Z',
        'homeTeam': {'id': 1, 'name': 'Narnia', 'tla': 'NAR'},
        'awayTeam': {'id': 2, 'name': 'Oz', 'tla': 'OZX'},
        'score': {'winner': None, 'duration': 'REGULAR',
                  'fullTime': {'home': None, 'away': None}},
    }]}
    with app.app_context():
        with patch.object(sync, '_api_get', return_value=bad):
            report = sync.link_fixtures()
        assert report['fixtures_linked'] == 0
        assert len(report['unmatched_fixtures']) == 1
