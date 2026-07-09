"""Tests for the World Cup football-data.org sync service."""
from datetime import datetime
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from games.worldcup.models import WorldCupMatch, WorldCupTeam


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
    from games.worldcup.services.sync import SyncError, _api_get
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


def test_api_get_retries_transient_network_error_then_succeeds(app):
    """A single transient network blip (the 'Address unavailable' family) is
    absorbed by retry, not surfaced as a SyncError / admin alert."""
    import requests

    from games.worldcup.services import sync

    class _OK:
        status_code = 200
        headers = {}
        def json(self): return {'matches': ['ok']}

    with app.app_context():
        app.config['FOOTBALL_DATA_API_KEY'] = 'k'
        side = [requests.exceptions.ConnectionError('Address unavailable'), _OK()]
        with patch.object(sync.time, 'sleep'), \
             patch.object(sync.requests, 'get', side_effect=side) as g:
            out = sync._api_get('competitions/WC/matches')
        assert out == {'matches': ['ok']}
        assert g.call_count == 2  # failed once, retried, succeeded


def test_api_get_raises_only_after_exhausting_retries(app):
    """A *sustained* outage still raises SyncError (→ admin email) once retries run out."""
    import requests

    from games.worldcup.services import sync
    from games.worldcup.services.sync import SyncError

    with app.app_context():
        app.config['FOOTBALL_DATA_API_KEY'] = 'k'
        boom = requests.exceptions.ConnectionError('Address unavailable')
        with patch.object(sync.time, 'sleep'), \
             patch.object(sync.requests, 'get', side_effect=boom) as g:
            with pytest.raises(SyncError):
                sync._api_get('competitions/WC/matches')
        assert sync.API_MAX_RETRIES > 1
        assert g.call_count == sync.API_MAX_RETRIES  # every attempt was made


def test_api_get_retries_5xx_then_succeeds(app):
    """Transient 5xx is retried (server-side blip), unlike a permanent 4xx."""
    from games.worldcup.services import sync

    class _Resp:
        def __init__(self, code): self.status_code = code; self.headers = {}
        def json(self): return {'matches': []}

    with app.app_context():
        app.config['FOOTBALL_DATA_API_KEY'] = 'k'
        with patch.object(sync.time, 'sleep'), \
             patch.object(sync.requests, 'get', side_effect=[_Resp(503), _Resp(200)]) as g:
            out = sync._api_get('competitions/WC/matches')
        assert out == {'matches': []}
        assert g.call_count == 2


def test_api_get_does_not_retry_4xx(app):
    """A permanent client error (e.g. bad key → 403) fails fast — no wasted retries."""
    from games.worldcup.services import sync
    from games.worldcup.services.sync import SyncError

    class _Resp:
        status_code = 403
        headers = {}
        def json(self): return {}

    with app.app_context():
        app.config['FOOTBALL_DATA_API_KEY'] = 'k'
        with patch.object(sync.time, 'sleep'), \
             patch.object(sync.requests, 'get', return_value=_Resp()) as g:
            with pytest.raises(SyncError):
                sync._api_get('competitions/WC/matches')
        assert g.call_count == 1  # no retry on 4xx


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


def _seed_linked_ko_match(app, match_number=90, fixture_id=537090):
    """Seed two teams + a linked R16 shell; returns (match_id, home_id, away_id)."""
    with app.app_context():
        a = _team('ESP', 'Spain', 'B'); b = _team('BRA', 'Brazil', 'C')
        db.session.flush()
        m = WorldCupMatch(match_number=match_number, stage='R16',
                          home_team_id=a.id, away_team_id=b.id,
                          api_fixture_id=fixture_id,
                          kickoff_utc=datetime(2026, 7, 4, 19, 0, 0))
        db.session.add(m); db.session.commit()
        return m.id, a.id, b.id


def _pk_payload(fixture_id=537090, winner='AWAY_TEAM', regular=(1, 1),
                extra=(0, 0), pens=(3, 4), full_time=None):
    """Realistic football-data.org PENALTY_SHOOTOUT payload.

    regularTime is the score after 90'; extraTime is goals scored DURING the
    ET period only; fullTime bundles the shootout goals into the total
    (reg + et + pens), as observed live on 2026-07-07.
    """
    if full_time is None:
        full_time = (regular[0] + extra[0] + pens[0], regular[1] + extra[1] + pens[1])
    return {'matches': [{
        'id': fixture_id, 'status': 'FINISHED', 'stage': 'LAST_16',
        'homeTeam': {'tla': 'ESP'}, 'awayTeam': {'tla': 'BRA'},
        'score': {'winner': winner, 'duration': 'PENALTY_SHOOTOUT',
                  'fullTime': {'home': full_time[0], 'away': full_time[1]},
                  'regularTime': {'home': regular[0], 'away': regular[1]},
                  'extraTime': {'home': extra[0], 'away': extra[1]},
                  'penalties': {'home': pens[0], 'away': pens[1]}},
    }]}


def test_sync_scores_knockout_extra_time_penalties(app):
    """Settled PK payload: stored score is regularTime + extraTime (the real
    120' score — extraTime holds only the goals scored DURING the ET period),
    never the bundled fullTime; the shootout tally lands in home_pen/away_pen."""
    from games.worldcup.services import sync
    mid, home_id, away_id = _seed_linked_ko_match(app)
    with app.app_context():
        # 2-2 after 90, 1-1 in the ET period (3-3 at 120'), 3-4 pens => fullTime 6-7.
        payload = _pk_payload(winner='AWAY_TEAM', regular=(2, 2), extra=(1, 1), pens=(3, 4))
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        m = db.session.get(WorldCupMatch, mid)
        assert m.is_completed and m.winner_team_id == away_id
        assert m.extra_time is True and m.penalties is True
        assert m.home_score == 3 and m.away_score == 3
        assert m.home_pen == 3 and m.away_pen == 4
        assert report['applied_count'] == 1


def test_sync_scores_ko_null_winner_never_defaults_to_away(app):
    """2026-07-07 SUI-COL incident lock: the API published status=FINISHED with
    winner=null and a level penalties breakdown (its PK data had not settled).
    Sync must skip the fixture as unsettled — the old `homeTeam if HOME_TEAM
    else awayTeam` ternary silently awarded the away team (Colombia)."""
    from games.worldcup.services import sync
    mid, home_id, away_id = _seed_linked_ko_match(app, fixture_id=537382)
    with app.app_context():
        # Verbatim shape of the live 537382 payload: winner null, pens 3-3,
        # fullTime 4-3 (the only field implying the home side actually won).
        payload = _pk_payload(fixture_id=537382, winner=None, regular=(0, 0),
                              extra=(0, 0), pens=(3, 3), full_time=(4, 3))
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        m = db.session.get(WorldCupMatch, mid)
        assert not m.is_completed
        assert m.winner_team_id is None
        assert report['applied_count'] == 0
        assert any(s['match_number'] == 90 for s in report['skipped_unsettled'])
        assert not report['failed']  # unsettled is a retry state, not a failure


def test_sync_scores_ko_regular_null_winner_unsettled(app):
    """A non-PK knockout fixture FINISHED with winner=null is equally unsettled
    — never resolved from the score or defaulted to a side."""
    from games.worldcup.services import sync
    mid, _, _ = _seed_linked_ko_match(app)
    with app.app_context():
        payload = {'matches': [{
            'id': 537090, 'status': 'FINISHED', 'stage': 'LAST_16',
            'homeTeam': {'tla': 'ESP'}, 'awayTeam': {'tla': 'BRA'},
            'score': {'winner': None, 'duration': 'REGULAR',
                      'fullTime': {'home': 1, 'away': 4}},
        }]}
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        assert not db.session.get(WorldCupMatch, mid).is_completed
        assert any(s['match_number'] == 90 for s in report['skipped_unsettled'])


def test_sync_scores_pk_level_pens_unsettled(app):
    """2026-07-03 AUS-EGY incident lock: at FINISHED-time the API briefly
    reported a level shootout (4-4; later settled to 2-4). A shootout cannot
    end level — treat as unsettled and retry, never persist the snapshot."""
    from games.worldcup.services import sync
    mid, _, _ = _seed_linked_ko_match(app)
    with app.app_context():
        payload = _pk_payload(winner='AWAY_TEAM', regular=(1, 1), extra=(0, 0),
                              pens=(4, 4), full_time=(3, 5))
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        assert not db.session.get(WorldCupMatch, mid).is_completed
        assert any(s['match_number'] == 90 for s in report['skipped_unsettled'])


def test_sync_scores_pk_pens_contradicting_winner_unsettled(app):
    """The declared winner side must agree with the penalties breakdown."""
    from games.worldcup.services import sync
    mid, _, _ = _seed_linked_ko_match(app)
    with app.app_context():
        payload = _pk_payload(winner='HOME_TEAM', regular=(1, 1), extra=(0, 0),
                              pens=(2, 4))
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        assert not db.session.get(WorldCupMatch, mid).is_completed
        assert any(s['match_number'] == 90 for s in report['skipped_unsettled'])


def test_sync_scores_pk_fulltime_inconsistent_unsettled(app):
    """fullTime must equal regularTime + extraTime + penalties componentwise —
    a mismatch means the API snapshot is still settling."""
    from games.worldcup.services import sync
    mid, _, _ = _seed_linked_ko_match(app)
    with app.app_context():
        payload = _pk_payload(winner='AWAY_TEAM', regular=(1, 1), extra=(0, 0),
                              pens=(2, 4), full_time=(3, 4))  # away should be 5
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        assert not db.session.get(WorldCupMatch, mid).is_completed
        assert any(s['match_number'] == 90 for s in report['skipped_unsettled'])


def test_sync_scores_skips_pk_without_extra_time(app):
    """A PENALTY_SHOOTOUT payload missing the regularTime/extraTime/penalties
    breakdown is unsettled (the breakdown appears once the API settles) — never
    written from the bundled fullTime total."""
    from games.worldcup.services import sync
    mid, _, _ = _seed_linked_ko_match(app, match_number=91, fixture_id=537091)
    with app.app_context():
        payload = {'matches': [{
            'id': 537091, 'status': 'FINISHED', 'stage': 'LAST_16',
            'homeTeam': {'tla': 'ESP'}, 'awayTeam': {'tla': 'BRA'},
            'score': {'winner': 'AWAY_TEAM', 'duration': 'PENALTY_SHOOTOUT',
                      'fullTime': {'home': 4, 'away': 5}},
        }]}
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        m = db.session.get(WorldCupMatch, mid)
        assert not m.is_completed
        assert any(s['match_number'] == 91 for s in report['skipped_unsettled'])


def test_sync_scores_ko_unmapped_winner_tla_fails_not_silent(app):
    """A resolved winner whose TLA can't map to a FIFA code is a mapping error:
    reported in failed (admin alert), and the match must NOT be completed
    winnerless (a winnerless completed KO match scores zero for everyone)."""
    from games.worldcup.services import sync
    mid, _, _ = _seed_linked_ko_match(app)
    with app.app_context():
        payload = {'matches': [{
            'id': 537090, 'status': 'FINISHED', 'stage': 'LAST_16',
            'homeTeam': {'tla': 'ESP'}, 'awayTeam': {'tla': 'ZZZ'},
            'score': {'winner': 'AWAY_TEAM', 'duration': 'REGULAR',
                      'fullTime': {'home': 0, 'away': 1}},
        }]}
        with patch.object(sync, '_api_get', return_value=payload):
            report = sync.sync_scores()
        m = db.session.get(WorldCupMatch, mid)
        assert not m.is_completed
        assert m.winner_team_id is None
        assert any(fr['match_number'] == 90 for fr in report['failed'])


def test_run_scores_notifies_unsettled_once_per_episode(app, tmp_path):
    """Unsettled fixtures alert the admin once per distinct pending set (marker
    de-dupe), not every 30-minute timer tick — and do not flip status to error."""
    from games.worldcup.services import sync
    with app.app_context():
        app.config['EMAIL_ADDRESS'] = 'commish@test.com'
        app.instance_path = str(tmp_path)
        result = {'applied_count': 0, 'applied': [], 'skipped_unassigned': 0,
                  'failed': [],
                  'skipped_unsettled': [{'match_number': 96, 'match_id': 1,
                                         'reason': 'winner not settled'}]}
        with patch.object(sync, 'sync_scores', return_value=result), \
             patch('games.worldcup.services.bracket.run_bracket_autofill',
                   return_value={'status': 'idle'}), \
             patch.object(sync, '_send_admin_email', return_value=True) as send:
            out1 = sync.run_scores()
            out2 = sync.run_scores()   # same pending set -> suppressed
        assert out1['status'] == 'ok' and out2['status'] == 'ok'
        assert send.call_count == 1


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


def test_group_stage_detection(app):
    from games.worldcup.services import sync
    with app.app_context():
        a = _team('MEX', 'Mexico', 'A'); b = _team('RSA', 'South Africa', 'A')
        db.session.flush()
        # One completed group match, no advancement set yet.
        db.session.add(WorldCupMatch(match_number=1, stage='group', group_letter='A',
                                     home_team_id=a.id, away_team_id=b.id,
                                     is_completed=True))
        db.session.commit()
        assert sync.group_stage_complete_and_unconfirmed() is True
        # Confirm advancement -> no longer flagged.
        a.advancement_method = 'group_winner'
        b.advancement_method = 'runner_up'
        db.session.commit()
        assert sync.group_stage_complete_and_unconfirmed() is False


def test_group_stage_detection_false_when_incomplete(app):
    from games.worldcup.services import sync
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=1, stage='group', group_letter='A',
                                     is_completed=False))
        db.session.commit()
        assert sync.group_stage_complete_and_unconfirmed() is False


def test_send_admin_email_uses_platform_helper(app):
    from games.worldcup.services import sync
    with app.app_context():
        app.config['EMAIL_ADDRESS'] = 'commish@test.com'
        with patch.object(sync, 'send_platform_email', return_value=True) as send:
            sync._send_admin_email('Subject', 'Body')
        assert send.call_args.args[0] == 'commish@test.com'
        assert '[World Cup]' in send.call_args.args[1]


def test_run_scores_emails_on_error(app):
    from games.worldcup.services import sync
    with app.app_context():
        app.config['EMAIL_ADDRESS'] = 'commish@test.com'
        with patch.object(sync, 'sync_scores', side_effect=sync.SyncError('down')), \
             patch.object(sync, '_send_admin_email', return_value=True) as send:
            out = sync.run_scores()
        assert out['status'] == 'error'
        assert send.called


def test_run_advancement_check_notifies_once_per_episode(app, tmp_path):
    from games.worldcup.services import sync
    with app.app_context():
        app.config['EMAIL_ADDRESS'] = 'commish@test.com'
        app.instance_path = str(tmp_path)
        with patch.object(sync, 'group_stage_complete_and_unconfirmed', return_value=True), \
             patch.object(sync, 'ko_round_pending', return_value=None), \
             patch.object(sync, '_send_admin_email', return_value=True) as send:
            sync.run_advancement_check()   # fires
            sync.run_advancement_check()   # same episode -> suppressed
        assert send.call_count == 1


def test_run_advancement_check_distinct_ko_rounds_each_notify(app, tmp_path):
    from games.worldcup.services import sync
    with app.app_context():
        app.config['EMAIL_ADDRESS'] = 'commish@test.com'
        app.instance_path = str(tmp_path)
        with patch.object(sync, 'group_stage_complete_and_unconfirmed', return_value=False), \
             patch.object(sync, '_send_admin_email', return_value=True) as send:
            # R32 pending, then R16 pending — distinct signatures must each fire.
            with patch.object(sync, 'ko_round_pending', return_value='R32'):
                sync.run_advancement_check()
                sync.run_advancement_check()   # same episode -> suppressed
            with patch.object(sync, 'ko_round_pending', return_value='R16'):
                sync.run_advancement_check()   # new episode -> fires
        assert send.call_count == 2


def test_ko_round_pending_sf_checks_both_final_and_third_place(app):
    from games.worldcup.services import sync
    with app.app_context():
        a = _team('ESP', 'Spain', 'B'); b = _team('BRA', 'Brazil', 'C')
        db.session.flush()
        db.session.add(WorldCupMatch(match_number=101, stage='SF', is_completed=True,
                                     home_team_id=a.id, away_team_id=b.id))
        db.session.add(WorldCupMatch(match_number=102, stage='SF', is_completed=True,
                                     home_team_id=a.id, away_team_id=b.id))
        # final filled, but third_place is an empty shell -> still pending on SF.
        db.session.add(WorldCupMatch(match_number=104, stage='final',
                                     home_team_id=a.id, away_team_id=b.id))
        db.session.add(WorldCupMatch(match_number=103, stage='third_place'))
        db.session.commit()
        assert sync.ko_round_pending() == 'SF'
        tp = WorldCupMatch.query.filter_by(stage='third_place').first()
        tp.home_team_id = a.id; tp.away_team_id = b.id
        db.session.commit()
        assert sync.ko_round_pending() is None


def test_link_fixtures_records_conflict_without_overwrite(app):
    from games.worldcup.services import sync
    with app.app_context():
        mex = _team('MEX', 'Mexico', 'A'); rsa = _team('RSA', 'South Africa', 'A')
        db.session.flush()
        m = WorldCupMatch(match_number=1, stage='group', group_letter='A',
                          home_team_id=mex.id, away_team_id=rsa.id,
                          api_fixture_id=111111,  # already linked to a DIFFERENT id
                          kickoff_utc=datetime(2026, 6, 11, 19, 0, 0))
        db.session.add(m); db.session.commit()
        mid = m.id
        with patch.object(sync, '_api_get', return_value=_API_MATCHES_FIXTURE):
            report = sync.link_fixtures()
        # Incoming 537001 differs from stored 111111 -> recorded, not overwritten.
        assert db.session.get(WorldCupMatch, mid).api_fixture_id == 111111
        assert any(c['match_number'] == 1 for c in report['fixture_conflicts'])
        assert report['fixtures_linked'] == 0


def test_cli_sync_link_invokes_service(app):
    from games.worldcup.services import sync
    runner = app.test_cli_runner()
    with patch.object(sync, 'link_fixtures',
                      return_value={'fixtures_linked': 104, 'teams_linked': 48,
                                    'unmatched_fixtures': [], 'unmapped_teams': [],
                                    'api_fixture_count': 104}) as link:
        result = runner.invoke(args=['worldcup', 'sync', '--mode', 'link'])
    assert link.called
    assert '104' in result.output


def test_cli_sync_rejects_bad_mode(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=['worldcup', 'sync', '--mode', 'bogus'])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Bulk bracket populate — fetch_bracket_proposal
# ---------------------------------------------------------------------------

def _ko_matches_payload():
    """Two LAST_32 fixtures, one fully resolved, one half-resolved."""
    return {'matches': [
        {'id': 9001, 'stage': 'LAST_32', 'utcDate': '2026-06-28T19:00:00Z',
         'homeTeam': {'tla': 'BRA', 'name': 'Brazil'},
         'awayTeam': {'tla': 'KSA', 'name': 'Saudi Arabia'}},
        {'id': 9002, 'stage': 'LAST_32', 'utcDate': '2026-06-28T23:00:00Z',
         'homeTeam': {'tla': 'ARG', 'name': 'Argentina'},
         'awayTeam': {'tla': None, 'name': None}},
    ]}


def test_fetch_bracket_proposal_maps_resolved_and_flags_unresolved(app):
    from games.worldcup.services import sync
    with app.app_context():
        for code, name, grp in [('BRA', 'Brazil', 'A'), ('KSA', 'Saudi Arabia', 'A'),
                                ('ARG', 'Argentina', 'B')]:
            db.session.add(WorldCupTeam(fifa_code=code, name=name, display_name=name,
                                        tier=1, multiplier=1.0, confederation='X',
                                        group_letter=grp))
        db.session.add(WorldCupMatch(match_number=73, stage='R32', api_fixture_id=9001))
        db.session.add(WorldCupMatch(match_number=74, stage='R32', api_fixture_id=9002))
        db.session.commit()

        with patch.object(sync, '_api_get', return_value=_ko_matches_payload()):
            out = sync.fetch_bracket_proposal('R32')

        assert out['error'] is None
        assert len(out['proposals']) == 1
        p = out['proposals'][0]
        assert (p['match_number'], p['home_fifa'], p['away_fifa']) == (73, 'BRA', 'KSA')
        assert p['already_set'] is False
        # Match 74 has an unresolved away team -> reported, not proposed.
        assert any(u['match_number'] == 74 for u in out['unresolved'])


def test_fetch_bracket_proposal_exposes_per_side_resolution(app):
    """`sides` surfaces each fixture's independently-resolved home/away (None for a
    side the API has not resolved yet) — the half-resolved ARG-vs-TBD case feeds the
    per-side bracket auto-fill cross-check."""
    from games.worldcup.services import sync
    with app.app_context():
        for code, name, grp in [('BRA', 'Brazil', 'A'), ('KSA', 'Saudi Arabia', 'A'),
                                ('ARG', 'Argentina', 'B')]:
            db.session.add(WorldCupTeam(fifa_code=code, name=name, display_name=name,
                                        tier=1, multiplier=1.0, confederation='X',
                                        group_letter=grp))
        s73 = WorldCupMatch(match_number=73, stage='R32', api_fixture_id=9001)
        s74 = WorldCupMatch(match_number=74, stage='R32', api_fixture_id=9002)
        db.session.add_all([s73, s74])
        db.session.commit()
        s73_id, s74_id = s73.id, s74.id

        with patch.object(sync, '_api_get', return_value=_ko_matches_payload()):
            out = sync.fetch_bracket_proposal('R32')

        assert out['sides'][s73_id] == {'home': 'BRA', 'away': 'KSA'}
        assert out['sides'][s74_id] == {'home': 'ARG', 'away': None}


def test_fetch_bracket_proposal_rejects_non_ko_stage(app):
    from games.worldcup.services import sync
    with app.app_context():
        out = sync.fetch_bracket_proposal('group')
        assert out['error'] is not None
        assert out['proposals'] == []


def test_fetch_bracket_proposal_matches_by_kickoff_when_unlinked(app):
    """A shell with no api_fixture_id still matches via (stage, kickoff)."""
    from datetime import datetime

    from games.worldcup.services import sync
    with app.app_context():
        for code, name in [('BRA', 'Brazil'), ('KSA', 'Saudi Arabia')]:
            db.session.add(WorldCupTeam(fifa_code=code, name=name, display_name=name,
                                        tier=1, multiplier=1.0, confederation='X', group_letter='A'))
        # No api_fixture_id; kickoff matches the API fixture's utcDate.
        db.session.add(WorldCupMatch(match_number=73, stage='R32',
                                     kickoff_utc=datetime(2026, 6, 28, 19, 0, 0)))
        db.session.commit()

        payload = {'matches': [
            {'id': 9001, 'stage': 'LAST_32', 'utcDate': '2026-06-28T19:00:00Z',
             'homeTeam': {'tla': 'BRA', 'name': 'Brazil'},
             'awayTeam': {'tla': 'KSA', 'name': 'Saudi Arabia'}},
        ]}
        with patch.object(sync, '_api_get', return_value=payload):
            out = sync.fetch_bracket_proposal('R32')

        assert out['error'] is None
        assert len(out['proposals']) == 1
        assert out['proposals'][0]['match_number'] == 73


def test_fetch_bracket_proposal_propagates_sync_error(app):
    """A football-data.org outage surfaces as SyncError (the route flashes it)."""
    from games.worldcup.services import sync
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=73, stage='R32'))
        db.session.commit()
        with patch.object(sync, '_api_get', side_effect=sync.SyncError('boom')):
            with pytest.raises(sync.SyncError):
                sync.fetch_bracket_proposal('R32')


def test_all_group_advancement_confirmed(app):
    from games.worldcup.services import sync
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=1, stage='group', group_letter='A',
                                     is_completed=True))
        db.session.add(WorldCupTeam(fifa_code='BRA', name='Brazil', display_name='Brazil',
                                    tier=1, multiplier=1.0, confederation='X', group_letter='A',
                                    advancement_method='group_winner'))
        db.session.add(WorldCupTeam(fifa_code='KSA', name='Saudi Arabia', display_name='Saudi Arabia',
                                    tier=5, multiplier=7.0, confederation='X', group_letter='A',
                                    is_eliminated=True))
        db.session.commit()
        assert sync.all_group_advancement_confirmed() is True

        # Add an unconfirmed team (no method, not eliminated) -> not confirmed.
        db.session.add(WorldCupTeam(fifa_code='ARG', name='Argentina', display_name='Argentina',
                                    tier=1, multiplier=1.0, confederation='X', group_letter='A'))
        db.session.commit()
        assert sync.all_group_advancement_confirmed() is False


# ---------------------------------------------------------------------------
# repair-pk-scores — backfills completed PK rows from settled API data
# ---------------------------------------------------------------------------

def _seed_completed_pk_match(app, home_pen, away_pen, winner_side='away'):
    """Completed PK row carrying the 2026-07-03/07 corruption shape:
    0-0 stored score (extraTime-only bug) + a possibly-level pen tally."""
    with app.app_context():
        a = _team('AUS', 'Australia', 'D', tier=5, mult=7.0)
        b = _team('EGY', 'Egypt', 'D', tier=4, mult=4.0)
        db.session.flush()
        m = WorldCupMatch(match_number=88, stage='R32',
                          home_team_id=a.id, away_team_id=b.id,
                          api_fixture_id=537428, is_completed=True,
                          home_score=0, away_score=0,
                          home_pen=home_pen, away_pen=away_pen,
                          extra_time=True, penalties=True,
                          winner_team_id=(b.id if winner_side == 'away' else a.id),
                          kickoff_utc=datetime(2026, 7, 3, 19, 0, 0))
        db.session.add(m); db.session.commit()
        return m.id


def _settled_pk_api(pens=(2, 4), winner='AWAY_TEAM'):
    return {'matches': [{
        'id': 537428, 'status': 'FINISHED', 'stage': 'LAST_32',
        'homeTeam': {'tla': 'AUS'}, 'awayTeam': {'tla': 'EGY'},
        'score': {'winner': winner, 'duration': 'PENALTY_SHOOTOUT',
                  'fullTime': {'home': 1 + pens[0], 'away': 1 + pens[1]},
                  'regularTime': {'home': 1, 'away': 1},
                  'extraTime': {'home': 0, 'away': 0},
                  'penalties': {'home': pens[0], 'away': pens[1]}},
    }]}


def test_repair_pk_scores_fixes_level_pens_row(app):
    """A completed row whose stored pen tally is level (an unsettled snapshot —
    impossible for a real shootout) is a repair candidate: score becomes
    regularTime + extraTime and the pens re-read from the settled API."""
    from games.worldcup.services import sync
    mid = _seed_completed_pk_match(app, home_pen=4, away_pen=4)
    with app.app_context():
        with patch.object(sync, '_api_get', return_value=_settled_pk_api()):
            result = app.test_cli_runner().invoke(
                args=['worldcup', 'repair-pk-scores'])
        assert result.exit_code == 0
        m = db.session.get(WorldCupMatch, mid)
        assert m.home_score == 1 and m.away_score == 1
        assert m.home_pen == 2 and m.away_pen == 4
        assert m.winner_team_id == m.away_team_id  # winner never touched


def test_repair_pk_scores_skips_api_contradicting_stored_winner(app):
    """If the settled API says the OTHER side won the shootout, the row needs a
    human decision (winner rewrites cascade into the bracket) — repair must
    leave it untouched and warn."""
    from games.worldcup.services import sync
    mid = _seed_completed_pk_match(app, home_pen=4, away_pen=4, winner_side='away')
    with app.app_context():
        with patch.object(sync, '_api_get',
                          return_value=_settled_pk_api(pens=(4, 2), winner='HOME_TEAM')):
            result = app.test_cli_runner().invoke(
                args=['worldcup', 'repair-pk-scores'])
        m = db.session.get(WorldCupMatch, mid)
        assert m.home_score == 0 and m.away_score == 0  # untouched
        assert m.home_pen == 4 and m.away_pen == 4
        assert 'WARNING' in result.output


def test_repair_pk_scores_skips_unsettled_api(app):
    """API still unsettled (level pens / null winner) -> row left for a later run."""
    from games.worldcup.services import sync
    mid = _seed_completed_pk_match(app, home_pen=None, away_pen=None)
    with app.app_context():
        with patch.object(sync, '_api_get',
                          return_value=_settled_pk_api(pens=(3, 3), winner=None)):
            result = app.test_cli_runner().invoke(
                args=['worldcup', 'repair-pk-scores'])
        m = db.session.get(WorldCupMatch, mid)
        assert m.home_score == 0 and m.away_score == 0
        assert m.home_pen is None and m.away_pen is None


def test_populatable_bracket_stages_offers_r32_after_advancement(app):
    from games.worldcup.services import sync
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=1, stage='group', group_letter='A',
                                     is_completed=True))
        db.session.add(WorldCupTeam(fifa_code='BRA', name='Brazil', display_name='Brazil',
                                    tier=1, multiplier=1.0, confederation='X', group_letter='A',
                                    advancement_method='group_winner'))
        # An empty R32 shell.
        db.session.add(WorldCupMatch(match_number=73, stage='R32'))
        db.session.commit()
        assert 'R32' in sync.populatable_bracket_stages()
