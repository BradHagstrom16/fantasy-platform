"""The CFB room's lead panel copy (games/cfb/routes.py::_lead_card).

No eyebrow above the headline (ADR-066): the headline leads with the week
and says what is left or the verdict; the supporting line opens on the
week's state word ("Locked." / "Final."). Every branch the card can take,
built from plain stand-ins so no week has to be staged.
"""
from types import SimpleNamespace

import pytest

from games.cfb.routes import _lead_card
from games.cfb.services.week_state import LOCKED, VERDICT

WEEK4 = SimpleNamespace(week_number=4, round_name=None)


def _game(away, home, **extra):
    return SimpleNamespace(
        get_away_team_display=lambda: away,
        get_home_team_display=lambda: home,
        game_time=None, **extra)


def _room(state, pending=()):
    return SimpleNamespace(lead=WEEK4, state=state, pending=list(pending))


@pytest.mark.parametrize(('pending', 'headline'), [
    ([], 'Week 4: Awaiting the verdict'),
    ([_game('SMU', 'Florida State')], 'Week 4: SMU at Florida State'),
    ([_game('SMU', 'Florida State'), _game('Iowa', 'Ohio State')],
     'Week 4: SMU at Florida State · Iowa at Ohio State'),
    ([_game('A', 'B')] * 3, 'Week 4: A at B · A at B · A at B'),
    ([_game('A', 'B')] * 4, 'Week 4: 4 games to go'),
])
def test_locked_headline_names_the_week_and_what_is_left(app, pending, headline):
    card = _lead_card(_room(LOCKED, pending), {}, None, None)
    assert card['headline'] == headline
    assert card['state'] == 'Locked'
    assert card['derivation'] == 'Verdict pending.'   # no kickoff time known
    assert 'eyebrow' not in card and 'hero_eyebrow' not in card


def test_locked_names_a_round_by_its_name(app):
    room = SimpleNamespace(lead=SimpleNamespace(week_number=16,
                                                round_name='CFP Quarterfinals'),
                           state=LOCKED, pending=[])
    card = _lead_card(room, {}, None, None)
    assert card['headline'] == 'CFP Quarterfinals: Awaiting the verdict'


def _pick(is_correct, team_id=1, name='Oregon'):
    return SimpleNamespace(is_correct=is_correct, team_id=team_id,
                           team=SimpleNamespace(name=name))


def _played(home_team_id, home_score, away_score, is_no_contest=False):
    game = _game('Oregon', 'Washington', home_team_id=home_team_id,
                 home_score=home_score, away_score=away_score,
                 is_no_contest=is_no_contest)
    game.get_spread_for_team = lambda team_id: None
    return game


def test_verdict_for_a_spectator_is_in_the_books(app):
    card = _lead_card(_room(VERDICT), {}, None, None)
    assert card['headline'] == 'Week 4: In the books.'
    assert card['state'] == 'Final'
    assert card['derivation'] is None
    assert card['next_line'] == 'Week 5 is not on the board yet.'


def test_verdict_no_pick(app):
    card = _lead_card(_room(VERDICT), {}, None,
                      SimpleNamespace(is_eliminated=False))
    assert card['headline'] == 'Week 4: No pick.'
    assert card['derivation'] == 'No pick was filed.'
    assert card['tone'] == 'lost'


@pytest.mark.parametrize(('is_correct', 'eliminated', 'no_contest', 'headline', 'line'), [
    (True, False, False, 'Week 4: Survived.', 'Oregon beat Washington, 31–17.'),
    (False, False, False, 'Week 4: Lost a life.', 'Oregon fell to Washington, 31–17.'),
    (False, True, False, 'Week 4: Eliminated.', 'Oregon fell to Washington, 31–17.'),
    (None, False, True, 'Week 4: No contest.', "Oregon's game was ruled a no contest."),
])
def test_verdict_for_a_pick(app, is_correct, eliminated, no_contest, headline, line):
    # Oregon (team 1) is the away side here: away 31, home 17. The pool
    # grades against the spread, so a loss can carry the higher score.
    game = _played(home_team_id=2, home_score=17, away_score=31,
                   is_no_contest=no_contest)
    card = _lead_card(_room(VERDICT), {1: game}, _pick(is_correct),
                      SimpleNamespace(is_eliminated=eliminated))
    assert card['headline'] == headline
    assert card['state'] == 'Final'
    assert card['derivation'] == line
