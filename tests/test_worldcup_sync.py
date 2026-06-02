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


def _seed_linked_group_match(app, status_winner, home, away):
    """Seed a linked group match and return (match_id, api payload)."""
    with app.app_context():
        a = _team('MEX', 'Mexico', 'A'); b = _team('RSA', 'South Africa', 'A')
        db.session.flush()
        m = WorldCupMatch(match_number=1, stage='group', group_letter='A',
                          home_team_id=a.id, away_team_id=b.id,
                          api_fixture_id=537001,
                          kickoff_utc=datetime(2026, 6, 11, 19, 0, 0))
        db.session.add(m); db.session.commit()
        payload = {'matches': [{
            'id': 537001, 'status': 'FINISHED', 'stage': 'GROUP_STAGE',
            'homeTeam': {'tla': 'MEX'}, 'awayTeam': {'tla': 'RSA'},
            'score': {'winner': status_winner, 'duration': 'REGULAR',
                      'fullTime': {'home': home, 'away': away}},
        }]}
        return m.id, payload


def test_sync_scores_applies_group_win(app):
    from games.worldcup.services import sync
    mid, payload = _seed_linked_group_match(app, 'HOME_TEAM', 2, 0)
    with app.app_context():
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        m = db.session.get(WorldCupMatch, mid)
        assert m.is_completed and m.home_score == 2 and m.away_score == 0
        assert m.winner_team_id == m.home_team_id
        assert report['applied_count'] == 1


def test_sync_scores_skips_unfinished_and_completed(app):
    from games.worldcup.services import sync
    mid, payload = _seed_linked_group_match(app, 'HOME_TEAM', 2, 0)
    with app.app_context():
        payload['matches'][0]['status'] = 'IN_PLAY'
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        assert report['applied_count'] == 0
        assert db.session.get(WorldCupMatch, mid).is_completed is False


def test_sync_scores_knockout_extra_time_penalties(app):
    from games.worldcup.services import sync
    with app.app_context():
        a = _team('ESP', 'Spain', 'B'); b = _team('BRA', 'Brazil', 'C')
        db.session.flush()
        m = WorldCupMatch(match_number=90, stage='R16',
                          home_team_id=a.id, away_team_id=b.id,
                          api_fixture_id=537090,
                          kickoff_utc=datetime(2026, 7, 4, 19, 0, 0))
        db.session.add(m); db.session.commit()
        mid = m.id
        payload = {'matches': [{
            'id': 537090, 'status': 'FINISHED', 'stage': 'LAST_16',
            'homeTeam': {'tla': 'ESP'}, 'awayTeam': {'tla': 'BRA'},
            'score': {'winner': 'AWAY_TEAM', 'duration': 'PENALTY_SHOOTOUT',
                      'fullTime': {'home': 1, 'away': 1},
                      'penalties': {'home': 3, 'away': 4}},
        }]}
        with patch.object(sync, '_api_get', return_value=payload):
            sync.sync_scores()
        m = db.session.get(WorldCupMatch, mid)
        assert m.is_completed and m.winner_team_id == b.id
        assert m.extra_time is True and m.penalties is True


def test_sync_scores_skips_knockout_with_unset_teams(app):
    from games.worldcup.services import sync
    with app.app_context():
        m = WorldCupMatch(match_number=90, stage='R16', api_fixture_id=537090,
                          kickoff_utc=datetime(2026, 7, 4, 19, 0, 0))
        db.session.add(m); db.session.commit()
        payload = {'matches': [{
            'id': 537090, 'status': 'FINISHED', 'stage': 'LAST_16',
            'homeTeam': {'tla': 'ESP'}, 'awayTeam': {'tla': 'BRA'},
            'score': {'winner': 'AWAY_TEAM', 'duration': 'REGULAR',
                      'fullTime': {'home': 0, 'away': 1}},
        }]}
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        assert report['applied_count'] == 0
        assert report['skipped_unassigned'] == 1


_STANDINGS_FIXTURE = {'standings': [{
    'stage': 'GROUP_STAGE', 'type': 'TOTAL', 'group': 'Group A',
    'table': [
        {'position': 1, 'team': {'tla': 'MEX', 'name': 'Mexico'}, 'points': 9,
         'goalDifference': 5, 'goalsFor': 6, 'playedGames': 3},
        {'position': 2, 'team': {'tla': 'RSA', 'name': 'South Africa'}, 'points': 4,
         'goalDifference': 0, 'goalsFor': 3, 'playedGames': 3},
        {'position': 3, 'team': {'tla': 'KOR', 'name': 'South Korea'}, 'points': 3,
         'goalDifference': -1, 'goalsFor': 2, 'playedGames': 3},
        {'position': 4, 'team': {'tla': 'CZE', 'name': 'Czechia'}, 'points': 1,
         'goalDifference': -4, 'goalsFor': 1, 'playedGames': 3},
    ],
}]}

_KO_MATCHES_FIXTURE = {'matches': [{
    'id': 537073, 'utcDate': '2026-06-28T19:00:00Z', 'status': 'TIMED',
    'stage': 'LAST_32', 'group': None,
    'homeTeam': {'tla': 'MEX', 'name': 'Mexico'},
    'awayTeam': {'tla': 'KOR', 'name': 'South Korea'},
    'score': {'winner': None, 'duration': 'REGULAR', 'fullTime': {'home': None, 'away': None}},
}]}


def test_fetch_advancement_proposal(app):
    from games.worldcup.services import sync
    with app.app_context():
        def fake_get(path, params=None):
            return _STANDINGS_FIXTURE if 'standings' in path else _KO_MATCHES_FIXTURE
        with patch.object(sync, '_api_get', side_effect=fake_get):
            proposal = sync.fetch_advancement_proposal()
        groups = {g['letter']: g for g in proposal['groups']}
        assert groups['A']['group_winner'] == 'MEX'
        assert groups['A']['runner_up'] == 'RSA'
        # KOR appears in resolved LAST_32 -> flagged as the advancing best third.
        assert groups['A']['best_third'] == 'KOR'
        # CZE did not advance.
        assert groups['A']['third_advances'] is True
