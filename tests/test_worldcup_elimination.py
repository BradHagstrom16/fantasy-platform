"""Tests for derived knockout elimination (services/elimination.py).

is_eliminated is GROUP-STAGE-ONLY (scoring sets it only for group non-advancers).
eliminated_team_ids() must additionally derive knockout losers from completed
matches, matching team_detail._path_status() elimination semantics.
"""

from extensions import db
from games.worldcup.models import WorldCupMatch, WorldCupTeam
from games.worldcup.services.elimination import eliminated_team_ids
from games.worldcup.services.team_detail import _path_status


def _team(name, code, *, is_eliminated=False, best_finish=None, advancement_method=None):
    # iso_code is a derived property; the writable key is fifa_code (3-char).
    fifa = (code * 3)[:3].upper()
    t = WorldCupTeam(
        name=name, display_name=name, fifa_code=fifa, confederation='UEFA',
        group_letter='A', tier=1, multiplier=1, is_eliminated=is_eliminated,
        best_finish=best_finish, advancement_method=advancement_method,
    )
    db.session.add(t)
    db.session.flush()
    return t


def _match(number, stage, home, away, *, winner=None, completed=True):
    m = WorldCupMatch(
        match_number=number, stage=stage,
        home_team_id=home.id, away_team_id=away.id,
        winner_team_id=(winner.id if winner else None),
        is_completed=completed,
    )
    db.session.add(m)
    db.session.flush()
    return m


def test_group_stage_eliminated_team_is_out(app):
    with app.app_context():
        t = _team('Group Exit', 'aa', is_eliminated=True, best_finish='group')
        assert t.id in eliminated_team_ids()


def test_knockout_loser_is_out(app):
    """A team that lost a completed R32 match is out even though is_eliminated=False."""
    with app.app_context():
        winner = _team('Advancer', 'bb', advancement_method='winner', best_finish='R16')
        loser = _team('R32 Loser', 'cc', advancement_method='winner', best_finish='R32')
        _match(73, 'R32', winner, loser, winner=winner)
        ids = eliminated_team_ids()
        assert loser.id in ids
        assert loser.is_eliminated is False  # group flag never set for KO losers


def test_group_winner_that_lost_r32_is_out(app):
    """Distinct from group exit: advanced from group, then lost R32 → out."""
    with app.app_context():
        opp = _team('Opp', 'dd', advancement_method='winner', best_finish='R16')
        grp_winner = _team('Grp Winner', 'ee', advancement_method='winner', best_finish='R32')
        _match(74, 'R32', grp_winner, opp, winner=opp)
        assert grp_winner.id in eliminated_team_ids()


def test_still_advancing_team_is_not_out(app):
    """Won its last completed KO match, next match not yet played → alive."""
    with app.app_context():
        alive = _team('Alive', 'ff', advancement_method='winner', best_finish='QF')
        beaten = _team('Beaten', 'gg', advancement_method='winner', best_finish='R16')
        _match(89, 'QF', alive, beaten, winner=alive)  # alive WON the QF
        ids = eliminated_team_ids()
        assert alive.id not in ids
        assert beaten.id in ids


def test_null_winner_completed_ko_eliminates_both(app):
    """Completed KO match with no winner set → both teams out (knockouts never draw)."""
    with app.app_context():
        a = _team('A', 'hh', best_finish='R32', advancement_method='winner')
        b = _team('B', 'ii', best_finish='R32', advancement_method='winner')
        _match(75, 'R32', a, b, winner=None, completed=True)
        ids = eliminated_team_ids()
        assert a.id in ids and b.id in ids


def test_incomplete_ko_match_does_not_eliminate(app):
    """A scheduled-but-not-completed KO match must not mark anyone out."""
    with app.app_context():
        a = _team('A', 'jj', best_finish='R32', advancement_method='winner')
        b = _team('B', 'kk', best_finish='R32', advancement_method='winner')
        _match(76, 'R32', a, b, winner=None, completed=False)
        assert eliminated_team_ids() == set()


def test_semifinal_loser_is_alive_until_third_place(app):
    """An SF loser still plays the third-place match, so they are NOT out until
    that match completes — matching _path_status (returns alive 5,None) and
    scoring.py (keeps SF losers best_finish='SF', not eliminated)."""
    with app.app_context():
        sf_winner = _team('SFW', 'pp', best_finish='SF', advancement_method='winner')
        sf_loser = _team('SFL', 'qq', best_finish='SF', advancement_method='winner')
        _match(101, 'SF', sf_winner, sf_loser, winner=sf_winner)
        # No third_place match yet → the SF loser is still alive.
        assert sf_loser.id not in eliminated_team_ids()


def test_third_place_match_marks_both_participants_out(app):
    """Once the third-place match completes, BOTH the 3rd and 4th finishers are
    out of the tournament (the SF loss alone did not eliminate them)."""
    with app.app_context():
        third = _team('Third', 'rr', best_finish='3rd', advancement_method='winner')
        fourth = _team('Fourth', 'ss', best_finish='SF', advancement_method='winner')
        _match(103, 'third_place', third, fourth, winner=third)
        ids = eliminated_team_ids()
        assert third.id in ids and fourth.id in ids


def test_parity_with_path_status(app):
    """eliminated_team_ids() agrees with _path_status: a team is in the set iff
    _path_status returns a non-None eliminated_at_index."""
    with app.app_context():
        champ = _team('Champ', 'll', best_finish='champion', advancement_method='winner')
        runner = _team('Runner', 'mm', best_finish='runner_up', advancement_method='winner')
        group = _team('Group', 'nn', is_eliminated=True, best_finish='group')
        sf_winner_alive = _team('SFW', 'oo', best_finish='SF', advancement_method='winner')
        # SF loser whose third-place match has NOT been played yet — _path_status
        # treats them as alive (5, None); the helper must agree (no early-out).
        sf_loser = _team('SFL', 'tt', best_finish='SF', advancement_method='winner')
        # champ beat runner in the final; sf_winner_alive beat sf_loser in a SF
        _match(104, 'final', champ, runner, winner=champ)
        _match(102, 'SF', sf_winner_alive, sf_loser, winner=sf_winner_alive)
        ids = eliminated_team_ids()
        for t in (champ, runner, group, sf_winner_alive, sf_loser):
            _, elim_at = _path_status(t)
            assert (t.id in ids) == (elim_at is not None), t.display_name
