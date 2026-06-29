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
    # Official topology: shell #89 = Winner(74) vs Winner(77).
    from games.worldcup.services.bracket import derive_pairings
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        db.session.flush()
        _completed_ko(74, 'R32', bra, kor, bra)   # winner BRA (shell 89 home)
        _completed_ko(77, 'R32', mex, ned, mex)   # winner MEX (shell 89 away)
        shell = WorldCupMatch(match_number=89, stage='R16')  # empty
        db.session.add(shell)
        db.session.commit()
        out = derive_pairings('R16')
        assert out == {shell.id: ('BRA', 'MEX')}


def test_derive_pairings_not_ready_when_feeder_incomplete(app):
    # Official topology: shell #89 = Winner(74) vs Winner(77); 77 unplayed.
    from games.worldcup.services.bracket import derive_pairings
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        db.session.flush()
        _completed_ko(74, 'R32', bra, kor, bra)   # feeder 74 done
        # feeder 77 NOT completed (no winner)
        m77 = WorldCupMatch(match_number=77, stage='R32',
                            home_team_id=mex.id, away_team_id=ned.id, is_completed=False)
        db.session.add(m77)
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
        _completed_ko(74, 'R32', bra, kor, bra)
        _completed_ko(77, 'R32', mex, ned, mex)
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
    """Completed R32 feeders 74 & 77 (-> shell #89) + empty R16 shell; returns shell_id."""
    bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
    ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
    db.session.flush()
    _completed_ko(74, 'R32', bra, kor, bra)   # winner BRA (shell 89 home)
    _completed_ko(77, 'R32', mex, ned, mex)   # winner MEX (shell 89 away)
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


def test_autofill_apply_writes_shells_and_emails(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_ready()
        with patch.object(bracket, 'populatable_bracket_stages', return_value=['R16']), \
             patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_api_proposal(sid, 'BRA', 'MEX')), \
             patch.object(bracket, '_send_admin_email', return_value=True) as email:
            out = bracket.run_bracket_autofill()
        assert out['status'] == 'acted'
        s = db.session.get(WorldCupMatch, sid)
        assert s.home_team.fifa_code == 'BRA' and s.away_team.fifa_code == 'MEX'
        assert email.called  # receipt sent


def test_autofill_conflict_writes_nothing_and_dedupes_email(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_ready()
        with patch.object(bracket, 'populatable_bracket_stages', return_value=['R16']), \
             patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_api_proposal(sid, 'BRA', 'KOR')), \
             patch.object(bracket, '_send_admin_email', return_value=True) as email, \
             patch.object(bracket, '_notify_once', side_effect=[True, False]):
            bracket.run_bracket_autofill()  # first: notifies
            bracket.run_bracket_autofill()  # second: deduped
        s = db.session.get(WorldCupMatch, sid)
        assert s.home_team_id is None and s.away_team_id is None  # never written
        assert email.call_count == 1  # _notify_once gated the 2nd send


def test_autofill_never_touches_r32(app):
    from games.worldcup.services import bracket
    with app.app_context():
        with patch.object(bracket, 'populatable_bracket_stages',
                          return_value=['R32', 'R16']), \
             patch.object(bracket, 'reconcile',
                          return_value={'stage': 'x', 'decision': 'NOT_READY'}) as rec:
            bracket.run_bracket_autofill()
        # reconcile is called for R16 only, never R32
        called_stages = [c.args[0] for c in rec.call_args_list]
        assert 'R32' not in called_stages and 'R16' in called_stages


def test_autofill_idle_when_nothing_populatable(app):
    from games.worldcup.services import bracket
    with app.app_context():
        with patch.object(bracket, 'populatable_bracket_stages', return_value=[]):
            out = bracket.run_bracket_autofill()
        assert out['status'] == 'idle'


def test_run_scores_invokes_bracket_autofill(app):
    from games.worldcup.services import sync
    with app.app_context():
        with patch.object(sync, 'sync_scores',
                          return_value={'applied_count': 0, 'failed': [],
                                        'skipped_unassigned': 0, 'applied': []}), \
             patch('games.worldcup.services.bracket.run_bracket_autofill',
                   return_value={'status': 'idle', 'stages': []}) as af:
            out = sync.run_scores()
        assert af.called
        assert out['bracket'] == {'status': 'idle', 'stages': []}


def test_cli_bracket_mode_dispatches(app):
    from games.worldcup.cli import SYNC_MODES
    assert 'bracket' in SYNC_MODES


def _agreeing_proposal(stage):
    """Build an API proposal that mirrors derive_pairings (always agrees)."""
    from games.worldcup.services.bracket import derive_pairings
    pairings = derive_pairings(stage) or {}
    return {'target_stage': stage, 'error': None, 'unresolved': [],
            'proposals': [{'match_number': db.session.get(WorldCupMatch, sid).match_number,
                           'shell_id': sid, 'home_fifa': h, 'away_fifa': a,
                           'already_set': False, 'is_completed': False}
                          for sid, (h, a) in pairings.items()]}


def test_full_bracket_auto_advances_r32_to_final(app):
    from games.worldcup.services import bracket
    with app.app_context():
        # 32 teams T01..T32.
        teams = []
        for i in range(1, 33):
            teams.append(_team(f'T{i:02d}', f'Team{i}', group='A'))
        db.session.flush()

        # R32 #73-88: pair teams (0,1),(2,3),... home wins each (lower index).
        for idx, num in enumerate(range(73, 89)):
            h, a = teams[idx * 2], teams[idx * 2 + 1]
            _completed_ko(num, 'R32', h, a, h)

        # Empty shells for R16/QF/SF/third/final.
        for num in range(89, 97):
            db.session.add(WorldCupMatch(match_number=num, stage='R16'))
        for num in range(97, 101):
            db.session.add(WorldCupMatch(match_number=num, stage='QF'))
        for num in (101, 102):
            db.session.add(WorldCupMatch(match_number=num, stage='SF'))
        db.session.add(WorldCupMatch(match_number=103, stage='third_place'))
        db.session.add(WorldCupMatch(match_number=104, stage='final'))
        db.session.commit()

        def complete_round(stage):
            """Mark every filled shell of `stage` completed; home team wins."""
            for m in WorldCupMatch.query.filter_by(stage=stage).all():
                if m.home_team_id and m.away_team_id and not m.is_completed:
                    m.winner_team_id = m.home_team_id
                    m.home_score, m.away_score, m.is_completed = 1, 0, True
            db.session.commit()

        # Patch populatable_bracket_stages + API to track our own DB state.
        def fake_populatable():
            stages = []
            for st in bracket.DOWNSTREAM_STAGES:
                empty = (WorldCupMatch.query.filter_by(stage=st)
                         .filter(db.or_(WorldCupMatch.home_team_id.is_(None),
                                        WorldCupMatch.away_team_id.is_(None))).count())
                if empty:
                    stages.append(st)
            return stages

        with patch.object(bracket, '_send_admin_email', return_value=True), \
             patch.object(bracket, 'populatable_bracket_stages', side_effect=fake_populatable), \
             patch.object(bracket, 'fetch_bracket_proposal',
                          side_effect=lambda st: _agreeing_proposal(st)):
            # R16 fills from R32 results.
            bracket.run_bracket_autofill()
            assert WorldCupMatch.query.filter_by(match_number=89).first().home_team_id is not None
            complete_round('R16')
            # QF fills, then SF, then final+third.
            bracket.run_bracket_autofill(); complete_round('QF')
            bracket.run_bracket_autofill(); complete_round('SF')
            bracket.run_bracket_autofill()  # fills final (104) + third place (103)

        final = WorldCupMatch.query.filter_by(match_number=104).first()
        third = WorldCupMatch.query.filter_by(match_number=103).first()
        assert final.home_team_id is not None and final.away_team_id is not None
        assert third.home_team_id is not None and third.away_team_id is not None
        # Final = SF winners (home sides); third = SF losers (away sides).
        sf1 = WorldCupMatch.query.filter_by(match_number=101).first()
        sf2 = WorldCupMatch.query.filter_by(match_number=102).first()
        assert {final.home_team_id, final.away_team_id} == {sf1.winner_team_id, sf2.winner_team_id}
        assert {third.home_team_id, third.away_team_id} == {sf1.away_team_id, sf2.away_team_id}
