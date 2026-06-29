"""Knockout bracket auto-fill — topology, derivation, reconciliation, run."""
from unittest.mock import patch

import pytest

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


def test_topology_is_structurally_consistent():
    from games.worldcup.services.bracket import BRACKET_TOPOLOGY

    # Exactly the 16 downstream shells: R16 89-96, QF 97-100, SF 101-102,
    # third place 103, final 104.
    assert set(BRACKET_TOPOLOGY) == set(range(89, 105))

    feeder_uses = []  # (kind, feeder_no) usages across all shells
    for shell_no, feeders in BRACKET_TOPOLOGY.items():
        assert len(feeders) == 2, f"shell {shell_no} needs exactly 2 feeders"
        for kind, feeder_no in feeders:
            assert kind in ('winner', 'loser')
            assert feeder_no < shell_no, f"shell {shell_no} feeder {feeder_no} not earlier"
            feeder_uses.append((kind, feeder_no))

    # Third place = both SF losers; final = both SF winners.
    assert set(BRACKET_TOPOLOGY[103]) == {('loser', 101), ('loser', 102)}
    assert set(BRACKET_TOPOLOGY[104]) == {('winner', 101), ('winner', 102)}

    # Each R32 winner (73-88) feeds exactly one R16 slot.
    r32_winner_uses = [f for f in feeder_uses if f[0] == 'winner' and 73 <= f[1] <= 88]
    assert sorted(n for _, n in r32_winner_uses) == list(range(73, 89))

    # No (kind, feeder) pair is used twice except the deliberate SF reuse
    # (101 & 102 each feed both final-as-winner and third-as-loser).
    winner_feeders = [n for k, n in feeder_uses if k == 'winner']
    assert len(winner_feeders) == len(set(winner_feeders))


def _team(fifa, name, group='A', tier=1, mult=1.0):
    t = WorldCupTeam(fifa_code=fifa, name=name, display_name=name, tier=tier,
                     multiplier=mult, confederation='UEFA', group_letter=group)
    db.session.add(t)
    return t


def _completed_ko(match_number, stage, home, away, winner):
    """Create a completed KO match with a winner; return the shell."""
    m = WorldCupMatch(match_number=match_number, stage=stage,
                      home_team_id=home.id, away_team_id=away.id,
                      winner_team_id=winner.id, is_completed=True,
                      home_score=1, away_score=0)
    db.session.add(m)
    return m


def test_derive_pairings_r16_happy_path(app):
    from games.worldcup.services.bracket import derive_pairings
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        db.session.flush()
        _completed_ko(73, 'R32', bra, kor, bra)   # winner BRA
        _completed_ko(74, 'R32', ned, mex, mex)   # winner MEX
        shell = WorldCupMatch(match_number=89, stage='R16')  # empty
        db.session.add(shell)
        db.session.commit()
        out = derive_pairings('R16')
        assert out == {shell.id: ('BRA', 'MEX')}


def test_derive_pairings_not_ready_when_feeder_incomplete(app):
    from games.worldcup.services.bracket import derive_pairings
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        db.session.flush()
        _completed_ko(73, 'R32', bra, kor, bra)
        # match 74 NOT completed (no winner)
        m74 = WorldCupMatch(match_number=74, stage='R32',
                            home_team_id=ned.id, away_team_id=mex.id, is_completed=False)
        db.session.add(m74)
        db.session.add(WorldCupMatch(match_number=89, stage='R16'))
        db.session.commit()
        assert derive_pairings('R16') is None


def test_derive_pairings_third_place_uses_sf_losers(app):
    from games.worldcup.services.bracket import derive_pairings
    with app.app_context():
        a, b = _team('ARG', 'Argentina'), _team('FRA', 'France')
        c, d = _team('ESP', 'Spain'), _team('GER', 'Germany')
        db.session.flush()
        _completed_ko(101, 'SF', a, b, a)   # loser FRA
        _completed_ko(102, 'SF', c, d, d)   # loser ESP
        shell = WorldCupMatch(match_number=103, stage='third_place')
        db.session.add(shell)
        db.session.commit()
        out = derive_pairings('third_place')
        assert out == {shell.id: ('FRA', 'ESP')}


def test_derive_pairings_skips_already_filled_shell(app):
    from games.worldcup.services.bracket import derive_pairings
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        db.session.flush()
        _completed_ko(73, 'R32', bra, kor, bra)
        _completed_ko(74, 'R32', ned, mex, mex)
        # shell 89 already filled -> not in output
        filled = WorldCupMatch(match_number=89, stage='R16',
                               home_team_id=bra.id, away_team_id=mex.id)
        db.session.add(filled)
        db.session.commit()
        assert derive_pairings('R16') == {}


def _api_proposal(shell_id, home, away):
    return {'target_stage': 'R16', 'error': None, 'unresolved': [],
            'proposals': [{'match_number': 89, 'shell_id': shell_id,
                           'home_fifa': home, 'away_fifa': away,
                           'already_set': False, 'is_completed': False}]}


def _seed_r16_ready():
    """Two completed R32 feeders + one empty R16 shell; returns shell_id."""
    bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
    ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
    db.session.flush()
    _completed_ko(73, 'R32', bra, kor, bra)
    _completed_ko(74, 'R32', ned, mex, mex)
    shell = WorldCupMatch(match_number=89, stage='R16')
    db.session.add(shell)
    db.session.commit()
    return shell.id


def test_reconcile_apply_when_api_agrees(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_ready()
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_api_proposal(sid, 'MEX', 'BRA')):  # reversed order ok
            d = bracket.reconcile('R16')
        assert d['decision'] == 'APPLY'
        assert d['pairings'] == {sid: ('BRA', 'MEX')}


def test_reconcile_conflict_when_api_disagrees(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_ready()
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_api_proposal(sid, 'BRA', 'KOR')):  # wrong team
            d = bracket.reconcile('R16')
        assert d['decision'] == 'CONFLICT'
        assert d['conflicts'] and d['conflicts'][0]['shell_id'] == sid


def test_reconcile_apply_unconfirmed_when_api_unavailable(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_ready()
        with patch.object(bracket, 'fetch_bracket_proposal',
                          side_effect=bracket.SyncError('down')):
            d = bracket.reconcile('R16')
        assert d['decision'] == 'APPLY_UNCONFIRMED'
        assert d['pairings'] == {sid: ('BRA', 'MEX')}


def test_reconcile_not_ready_when_feeders_incomplete(app):
    from games.worldcup.services import bracket
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=89, stage='R16'))  # no feeders
        db.session.commit()
        d = bracket.reconcile('R16')
        assert d['decision'] == 'NOT_READY'
