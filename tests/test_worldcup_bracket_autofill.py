"""Knockout bracket auto-fill — topology, per-side derivation, reconciliation, run.

The auto-fill fills each downstream KO shell SIDE the moment its feeder match
completes (mirroring how football-data.org / ESPN resolve sides one at a time),
cross-checked per-side against the API. A side the API resolves to a different
team BLOCKS that side; an unresolved/absent API confirms nothing (writes flagged).
"""
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

    # No (kind, feeder) pair is used twice.
    assert len(feeder_uses) == len(set(feeder_uses))


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


# ---------------------------------------------------------------------------
# derive_sides — per-side, empty-side-only, no whole-stage gating
# ---------------------------------------------------------------------------

def test_derive_sides_both_when_both_feeders_done(app):
    # Official topology: shell #89 = Winner(74) vs Winner(77).
    from games.worldcup.services.bracket import derive_sides
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        db.session.flush()
        _completed_ko(74, 'R32', bra, kor, bra)   # winner BRA (shell 89 home)
        _completed_ko(77, 'R32', mex, ned, mex)   # winner MEX (shell 89 away)
        shell = WorldCupMatch(match_number=89, stage='R16')  # empty
        db.session.add(shell)
        db.session.commit()
        assert derive_sides('R16') == {shell.id: {'home': 'BRA', 'away': 'MEX'}}


def test_derive_sides_home_only_when_only_home_feeder_done(app):
    # Headline incremental case: only the home feeder (74) has resolved.
    from games.worldcup.services.bracket import derive_sides
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        db.session.flush()
        _completed_ko(74, 'R32', bra, kor, bra)   # feeder 74 done -> home
        # feeder 77 NOT completed
        m77 = WorldCupMatch(match_number=77, stage='R32',
                            home_team_id=mex.id, away_team_id=ned.id, is_completed=False)
        db.session.add(m77)
        shell = WorldCupMatch(match_number=89, stage='R16')
        db.session.add(shell)
        db.session.commit()
        # away omitted entirely — stays TBD; the stage is NOT gated to None.
        assert derive_sides('R16') == {shell.id: {'home': 'BRA'}}


def test_derive_sides_empty_when_no_feeder_done(app):
    from games.worldcup.services.bracket import derive_sides
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=89, stage='R16'))  # no feeders played
        db.session.commit()
        assert derive_sides('R16') == {}


def test_derive_sides_third_place_uses_sf_losers(app):
    from games.worldcup.services.bracket import derive_sides
    with app.app_context():
        a, b = _team('ARG', 'Argentina'), _team('FRA', 'France')
        c, d = _team('ESP', 'Spain'), _team('GER', 'Germany')
        db.session.flush()
        _completed_ko(101, 'SF', a, b, a)   # loser FRA -> third place home
        _completed_ko(102, 'SF', c, d, d)   # loser ESP -> third place away
        shell = WorldCupMatch(match_number=103, stage='third_place')
        db.session.add(shell)
        db.session.commit()
        assert derive_sides('third_place') == {shell.id: {'home': 'FRA', 'away': 'ESP'}}


def test_derive_sides_skips_already_set_side(app):
    # Home already set (manual or prior pass); only the away feeder is offered.
    from games.worldcup.services.bracket import derive_sides
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        db.session.flush()
        _completed_ko(74, 'R32', bra, kor, bra)
        _completed_ko(77, 'R32', mex, ned, mex)
        # shell 89 home already BRA -> only 'away' offered, BRA never re-derived.
        partial = WorldCupMatch(match_number=89, stage='R16', home_team_id=bra.id)
        db.session.add(partial)
        db.session.commit()
        assert derive_sides('R16') == {partial.id: {'away': 'MEX'}}


def test_derive_sides_fully_set_shell_omitted(app):
    from games.worldcup.services.bracket import derive_sides
    with app.app_context():
        bra, mex = _team('BRA', 'Brazil'), _team('MEX', 'Mexico')
        ned, kor = _team('NED', 'Netherlands'), _team('KOR', 'Korea')
        db.session.flush()
        _completed_ko(74, 'R32', bra, kor, bra)
        _completed_ko(77, 'R32', mex, ned, mex)
        filled = WorldCupMatch(match_number=89, stage='R16',
                               home_team_id=bra.id, away_team_id=mex.id)
        db.session.add(filled)
        db.session.commit()
        assert derive_sides('R16') == {}


# ---------------------------------------------------------------------------
# reconcile — per-side, membership-based cross-check (orientation-independent)
# ---------------------------------------------------------------------------

def _sides_proposal(shell_id, home=None, away=None):
    """API proposal exposing per-side resolution for one shell."""
    return {'target_stage': 'R16', 'error': None, 'unresolved': [], 'proposals': [],
            'sides': {shell_id: {'home': home, 'away': away}}}


def _seed_r16_both():
    """Completed R32 feeders 74 (BRA) & 77 (MEX) -> empty shell #89; returns shell_id."""
    bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
    ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
    db.session.flush()
    _completed_ko(74, 'R32', bra, kor, bra)
    _completed_ko(77, 'R32', mex, ned, mex)
    shell = WorldCupMatch(match_number=89, stage='R16')
    db.session.add(shell)
    db.session.commit()
    return shell.id


def _seed_r16_home_only():
    """Only feeder 74 (BRA) done -> shell #89 home derivable; returns shell_id."""
    bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
    db.session.flush()
    _completed_ko(74, 'R32', bra, kor, bra)
    shell = WorldCupMatch(match_number=89, stage='R16')
    db.session.add(shell)
    db.session.commit()
    return shell.id


def test_reconcile_apply_confirmed_when_api_agrees(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_both()
        # API lists the same pairing in REVERSED orientation — not a conflict.
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_sides_proposal(sid, home='MEX', away='BRA')):
            d = bracket.reconcile('R16')
        assert d['conflicts'] == []
        assert sorted((s, side, fifa, conf) for s, side, fifa, conf in d['applies']) == \
            [(sid, 'away', 'MEX', True), (sid, 'home', 'BRA', True)]


def test_reconcile_conflict_when_api_pairing_excludes_our_team(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_home_only()  # we derive home=BRA
        # API has fully resolved #89 to a pairing that does NOT include BRA.
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_sides_proposal(sid, home='KOR', away='GER')):
            d = bracket.reconcile('R16')
        assert d['applies'] == []
        assert len(d['conflicts']) == 1
        c = d['conflicts'][0]
        assert c[0] == sid and c[1] == 'home' and c[2] == 'BRA'


def test_reconcile_unconfirmed_when_api_side_unresolved(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_home_only()  # derive home=BRA
        # API hasn't resolved this fixture at all yet.
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_sides_proposal(sid, home=None, away=None)):
            d = bracket.reconcile('R16')
        assert d['conflicts'] == []
        assert d['applies'] == [(sid, 'home', 'BRA', False)]  # confirmed=False


def test_reconcile_unconfirmed_when_api_unavailable(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_both()
        with patch.object(bracket, 'fetch_bracket_proposal',
                          side_effect=bracket.SyncError('down')):
            d = bracket.reconcile('R16')
        assert d['conflicts'] == []
        assert all(conf is False for *_, conf in d['applies'])
        assert {(s, side, fifa) for s, side, fifa, _ in d['applies']} == \
            {(sid, 'home', 'BRA'), (sid, 'away', 'MEX')}


def test_reconcile_empty_when_nothing_derivable(app):
    from games.worldcup.services import bracket
    with app.app_context():
        db.session.add(WorldCupMatch(match_number=89, stage='R16'))  # no feeders
        db.session.commit()
        d = bracket.reconcile('R16')
        assert d['applies'] == [] and d['conflicts'] == []


# ---------------------------------------------------------------------------
# run_bracket_autofill — writes sides, blocks conflicts, silent on confirmed
# ---------------------------------------------------------------------------

def test_autofill_writes_confirmed_side_silently(app):
    """A confirmed fill writes the side and sends NO email (logged + in digest)."""
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_home_only()
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_sides_proposal(sid, home='BRA', away=None)), \
             patch.object(bracket, '_send_admin_email', return_value=True) as email:
            out = bracket.run_bracket_autofill()
        s = db.session.get(WorldCupMatch, sid)
        assert s.home_team.fifa_code == 'BRA'      # home filled
        assert s.away_team_id is None               # away stays TBD
        assert out['status'] == 'acted'
        assert not email.called                     # confirmed fill is silent


def test_autofill_unconfirmed_side_emails_spotcheck(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_home_only()
        with patch.object(bracket, 'fetch_bracket_proposal',
                          side_effect=bracket.SyncError('down')), \
             patch.object(bracket, '_send_admin_email', return_value=True) as email, \
             patch.object(bracket, '_notify_once', return_value=True):
            bracket.run_bracket_autofill()
        s = db.session.get(WorldCupMatch, sid)
        assert s.home_team.fifa_code == 'BRA'       # written from our results
        assert email.called                          # spot-check notice sent
        assert 'spot-check' in email.call_args.args[0].lower()


def test_autofill_conflict_blocks_side_and_dedupes_email(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_home_only()  # derive home=BRA
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_sides_proposal(sid, home='KOR', away='GER')), \
             patch.object(bracket, '_send_admin_email', return_value=True) as email, \
             patch.object(bracket, '_notify_once', side_effect=[True, False]):
            bracket.run_bracket_autofill()  # first: notifies
            bracket.run_bracket_autofill()  # second: deduped
        s = db.session.get(WorldCupMatch, sid)
        assert s.home_team_id is None                # blocked, never written
        assert email.call_count == 1                 # de-duped


def test_autofill_idempotent_rerun_writes_nothing_new(app):
    from games.worldcup.services import bracket
    with app.app_context():
        sid = _seed_r16_both()
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_sides_proposal(sid, home='BRA', away='MEX')), \
             patch.object(bracket, '_send_admin_email', return_value=True):
            bracket.run_bracket_autofill()
            out2 = bracket.run_bracket_autofill()  # both sides already set
        s = db.session.get(WorldCupMatch, sid)
        assert s.home_team.fifa_code == 'BRA' and s.away_team.fifa_code == 'MEX'
        assert out2['status'] == 'idle'  # nothing left to fill


def test_autofill_never_overwrites_a_manual_side(app):
    from games.worldcup.services import bracket
    with app.app_context():
        bra, kor = _team('BRA', 'Brazil'), _team('KOR', 'Korea')
        ned, mex = _team('NED', 'Netherlands'), _team('MEX', 'Mexico')
        wal = _team('WAL', 'Wales')
        db.session.flush()
        _completed_ko(74, 'R32', bra, kor, bra)  # topology says #89 home = BRA
        _completed_ko(77, 'R32', mex, ned, mex)
        # Admin manually pinned home to WAL — auto-fill must not clobber it.
        shell = WorldCupMatch(match_number=89, stage='R16', home_team_id=wal.id)
        db.session.add(shell)
        db.session.commit()
        sid = shell.id
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_sides_proposal(sid, home='WAL', away='MEX')), \
             patch.object(bracket, '_send_admin_email', return_value=True):
            bracket.run_bracket_autofill()
        s = db.session.get(WorldCupMatch, sid)
        assert s.home_team.fifa_code == 'WAL'   # manual side preserved
        assert s.away_team.fifa_code == 'MEX'   # empty side still filled


def test_autofill_never_touches_r32(app):
    # Auto-fill only ever processes DOWNSTREAM_STAGES (R16+); the group->R32
    # transition stays admin-confirmed even if R32 shells are fillable-looking.
    from games.worldcup.services import bracket
    with app.app_context():
        assert 'R32' not in bracket.DOWNSTREAM_STAGES
        with patch.object(bracket, 'derive_sides', side_effect=lambda st: {1: {'home': 'X'}}), \
             patch.object(bracket, 'reconcile',
                          return_value={'stage': 'x', 'applies': [], 'conflicts': []}) as rec:
            bracket.run_bracket_autofill()
        called_stages = [c.args[0] for c in rec.call_args_list]
        assert 'R32' not in called_stages
        assert set(called_stages) <= set(bracket.DOWNSTREAM_STAGES)
        assert 'R16' in called_stages


def test_autofill_idle_when_nothing_fillable(app):
    # No completed feeders anywhere -> derive_sides is empty for every stage.
    from games.worldcup.services import bracket
    with app.app_context():
        out = bracket.run_bracket_autofill()
        assert out['status'] == 'idle'


# ---------------------------------------------------------------------------
# The Canada case — the user's exact scenario (R32 #73 RSA v CAN, CAN wins)
# ---------------------------------------------------------------------------

def test_canada_appears_in_r16_the_moment_its_r32_match_completes(app):
    """Shell #90 = Winner(73) vs Winner(75). Canada wins #73 first; it must drop
    into #90 home immediately with the away side TBD, then away fills when #75 ends."""
    from games.worldcup.services import bracket
    with app.app_context():
        rsa, can = _team('RSA', 'South Africa'), _team('CAN', 'Canada')
        ned, mar = _team('NED', 'Netherlands'), _team('MAR', 'Morocco')
        db.session.flush()
        _completed_ko(73, 'R32', rsa, can, can)   # CAN wins -> #90 home
        m75 = WorldCupMatch(match_number=75, stage='R32',
                            home_team_id=ned.id, away_team_id=mar.id, is_completed=False)
        db.session.add(m75)
        shell = WorldCupMatch(match_number=90, stage='R16')
        db.session.add(shell)
        db.session.commit()
        sid = shell.id

        # Pass 1: API already shows CAN vs TBD (it resolves sides incrementally too).
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_sides_proposal(sid, home='CAN', away=None)), \
             patch.object(bracket, '_send_admin_email', return_value=True):
            bracket.run_bracket_autofill()
        s = db.session.get(WorldCupMatch, sid)
        assert s.home_team.fifa_code == 'CAN' and s.away_team_id is None

        # #75 now completes (NED wins) -> #90 away fills on the next pass.
        m75 = WorldCupMatch.query.filter_by(match_number=75).first()
        m75.winner_team_id = ned.id
        m75.home_score, m75.away_score, m75.is_completed = 2, 0, True
        db.session.commit()
        with patch.object(bracket, 'fetch_bracket_proposal',
                          return_value=_sides_proposal(sid, home='CAN', away='NED')), \
             patch.object(bracket, '_send_admin_email', return_value=True):
            bracket.run_bracket_autofill()
        s = db.session.get(WorldCupMatch, sid)
        assert s.home_team.fifa_code == 'CAN' and s.away_team.fifa_code == 'NED'


# ---------------------------------------------------------------------------
# Ops wiring + CLI (unchanged contract: run_scores folds in the autofill)
# ---------------------------------------------------------------------------

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


def test_run_scores_keeps_success_when_bracket_autofill_errors(app):
    from games.worldcup.services import sync
    with app.app_context():
        with patch.object(sync, 'sync_scores',
                          return_value={'applied_count': 0, 'failed': [],
                                        'skipped_unassigned': 0, 'applied': []}), \
             patch('games.worldcup.services.bracket.run_bracket_autofill',
                   side_effect=sync.SyncError('down')):
            out = sync.run_scores()
        assert out['status'] == 'ok'
        assert out['bracket'] == {'status': 'error', 'details': 'down'}


def test_cli_bracket_mode_dispatches(app):
    from games.worldcup.cli import SYNC_MODES, worldcup_cli
    assert 'bracket' in SYNC_MODES
    with patch('games.worldcup.services.bracket.run_bracket_autofill',
               return_value={'status': 'acted',
                             'stages': [{'stage': 'R16', 'filled': ['#90 home: CAN'],
                                         'unconfirmed': 0, 'conflicts': [], 'failed': []}]}) as af:
        result = app.test_cli_runner().invoke(worldcup_cli, ['sync', '--mode', 'bracket'])
    assert result.exit_code == 0
    assert af.called
    assert '[bracket] acted' in result.output
    assert 'R16: filled 1' in result.output


def test_infer_topology_uses_most_recent_prior_appearance(app):
    """infer_topology_from_api maps each feeder to a team's MOST RECENT prior
    appearance — win or loss — never a QF win in place of the SF loss that feeds
    third place."""
    from games.worldcup.services import bracket
    H = 'HOME_TEAM'

    def m(fid, home, away, winner=H):
        return {'id': fid, 'score': {'winner': winner},
                'homeTeam': {'tla': home}, 'awayTeam': {'tla': away}}

    api = {'matches': [
        {**m(1089, 'BRA', 'ARG'), 'stage': 'LAST_16'},
        {**m(1090, 'GER', 'FRA'), 'stage': 'LAST_16'},
        {**m(1097, 'BRA', 'GER'), 'stage': 'QUARTER_FINALS'},
        {**m(1098, 'ESP', 'ITA'), 'stage': 'QUARTER_FINALS'},
        {**m(1099, 'POR', 'NED'), 'stage': 'QUARTER_FINALS'},
        {**m(1100, 'NGA', 'USA'), 'stage': 'QUARTER_FINALS'},
        {**m(1101, 'BRA', 'ESP'), 'stage': 'SEMI_FINALS'},
        {**m(1102, 'NGA', 'POR'), 'stage': 'SEMI_FINALS'},
        {**m(1103, 'ESP', 'POR', winner=None), 'stage': 'THIRD_PLACE'},
    ]}
    rows = [(1089, 89, 'R16'), (1090, 90, 'R16'), (1097, 97, 'QF'), (1098, 98, 'QF'),
            (1099, 99, 'QF'), (1100, 100, 'QF'), (1101, 101, 'SF'), (1102, 102, 'SF'),
            (1103, 103, 'third_place')]
    with app.app_context():
        for fid, num, stage in rows:
            db.session.add(WorldCupMatch(match_number=num, stage=stage, api_fixture_id=fid))
        db.session.commit()
        with patch.object(bracket, '_api_get', return_value=api), \
             patch.object(bracket, '_fifa_for_tla', side_effect=lambda tla: tla):
            topo = bracket.infer_topology_from_api()
        assert topo[97] == (('winner', 89), ('winner', 90))
        assert ('winner', 101) not in topo[97]
        assert topo[103] == (('loser', 101), ('loser', 102))


def _agreeing_proposal(stage):
    """API proposal whose per-side 'sides' mirror derive_sides (always agrees)."""
    from games.worldcup.services.bracket import derive_sides
    derived = derive_sides(stage) or {}
    return {'target_stage': stage, 'error': None, 'unresolved': [], 'proposals': [],
            'sides': {sid: dict(s) for sid, s in derived.items()}}


def test_full_bracket_auto_advances_r32_to_final(app):
    from games.worldcup.services import bracket
    with app.app_context():
        teams = [_team(f'T{i:02d}', f'Team{i}', group='A') for i in range(1, 33)]
        db.session.flush()

        # R32 #73-88: pair teams (0,1),(2,3),...; home wins each (lower index).
        for idx, num in enumerate(range(73, 89)):
            h, a = teams[idx * 2], teams[idx * 2 + 1]
            _completed_ko(num, 'R32', h, a, h)

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
            for m in WorldCupMatch.query.filter_by(stage=stage).all():
                if m.home_team_id and m.away_team_id and not m.is_completed:
                    m.winner_team_id = m.home_team_id
                    m.home_score, m.away_score, m.is_completed = 1, 0, True
            db.session.commit()

        with patch.object(bracket, '_send_admin_email', return_value=True), \
             patch.object(bracket, 'fetch_bracket_proposal',
                          side_effect=lambda st: _agreeing_proposal(st)):
            bracket.run_bracket_autofill()
            assert WorldCupMatch.query.filter_by(match_number=89).first().home_team_id is not None
            complete_round('R16')
            bracket.run_bracket_autofill(); complete_round('QF')
            bracket.run_bracket_autofill(); complete_round('SF')
            bracket.run_bracket_autofill()  # fills final (104) + third place (103)

        final = WorldCupMatch.query.filter_by(match_number=104).first()
        third = WorldCupMatch.query.filter_by(match_number=103).first()
        assert final.home_team_id is not None and final.away_team_id is not None
        assert third.home_team_id is not None and third.away_team_id is not None
        sf1 = WorldCupMatch.query.filter_by(match_number=101).first()
        sf2 = WorldCupMatch.query.filter_by(match_number=102).first()
        assert {final.home_team_id, final.away_team_id} == {sf1.winner_team_id, sf2.winner_team_id}
        assert {third.home_team_id, third.away_team_id} == {sf1.away_team_id, sf2.away_team_id}
