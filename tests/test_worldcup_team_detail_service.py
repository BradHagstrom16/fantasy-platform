"""Tests for games/worldcup/services/team_detail helpers."""
import pytest

from app import create_app
from extensions import db
from games.worldcup.constants import ADVANCE_GROUP_WINNER, KNOCKOUT_POINTS
from games.worldcup.models import (
    WorldCupEnrollment,
    WorldCupMatch,
    WorldCupPick,
    WorldCupTeam,
)
from games.worldcup.services.team_detail import (
    compute_path_to_crown,
    compute_team_ownership,
    current_user_owns_team,
)
from models.user import User


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _seed_team(fifa='USA', tier=1, multiplier=1.0, group='A',
               base=0.0, multiplied=0.0,
               adv=None, finish=None, eliminated=False):
    t = WorldCupTeam(
        fifa_code=fifa, name=fifa, display_name=fifa,
        tier=tier, multiplier=multiplier, confederation='CONCACAF',
        group_letter=group, base_points=base, multiplied_points=multiplied,
        advancement_method=adv, best_finish=finish, is_eliminated=eliminated,
    )
    db.session.add(t)
    db.session.flush()
    return t


def _seed_completed_match(home_id, away_id, stage, winner_id,
                          match_number=49, home_score=0, away_score=1):
    m = WorldCupMatch(
        match_number=match_number, stage=stage,
        home_team_id=home_id, away_team_id=away_id,
        home_score=home_score, away_score=away_score,
        winner_team_id=winner_id, is_completed=True,
    )
    db.session.add(m)
    db.session.commit()
    return m


def _seed_enrollment_with_pick(team_id, tier, username='owner'):
    u = User(username=username, email=f'{username}@test.com')
    u.set_password('pass')
    db.session.add(u)
    db.session.flush()
    e = WorldCupEnrollment(user_id=u.id, season_year=2026, picks_submitted=True)
    db.session.add(e)
    db.session.flush()
    p = WorldCupPick(enrollment_id=e.id, team_id=team_id, tier=tier)
    db.session.add(p)
    db.session.commit()
    return u.id, e.id


# -- compute_team_ownership ----------------------------------------------

def test_ownership_pre_deadline_returns_none_for_picker_names(app):
    with app.app_context():
        team = _seed_team()
        _seed_enrollment_with_pick(team.id, tier=1, username='alice')
        _seed_enrollment_with_pick(team.id, tier=1, username='bob')
        result = compute_team_ownership(team.id, deadline_passed=False)
        assert result['picker_names'] is None
        assert result['count'] == 0
        assert result['percent'] == 0.0


def test_ownership_post_deadline_returns_picker_names_and_count(app):
    with app.app_context():
        team = _seed_team()
        _seed_enrollment_with_pick(team.id, tier=1, username='alice')
        _seed_enrollment_with_pick(team.id, tier=1, username='bob')
        u = User(username='carol', email='carol@test.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.flush()
        e = WorldCupEnrollment(user_id=u.id, season_year=2026, picks_submitted=True)
        db.session.add(e)
        db.session.commit()

        result = compute_team_ownership(team.id, deadline_passed=True)
        assert result['count'] == 2
        assert result['percent'] == pytest.approx(66.67, abs=0.01)
        assert sorted(result['picker_names']) == ['alice', 'bob']


def test_ownership_post_deadline_zero_picks(app):
    with app.app_context():
        team = _seed_team()
        result = compute_team_ownership(team.id, deadline_passed=True)
        assert result['count'] == 0
        assert result['percent'] == 0.0
        assert result['picker_names'] == []


# -- current_user_owns_team ----------------------------------------------

def test_current_user_owns_team_true_when_pick_exists(app):
    with app.app_context():
        team = _seed_team()
        user_id, _ = _seed_enrollment_with_pick(team.id, tier=1)
        assert current_user_owns_team(user_id, team.id) is True


def test_current_user_owns_team_false_when_no_pick(app):
    with app.app_context():
        team = _seed_team()
        u = User(username='other', email='other@test.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.flush()
        e = WorldCupEnrollment(user_id=u.id, season_year=2026, picks_submitted=True)
        db.session.add(e)
        db.session.commit()
        assert current_user_owns_team(u.id, team.id) is False


# -- compute_path_to_crown -----------------------------------------------

def test_path_to_crown_group_in_progress(app):
    """No advancement, no elimination -> Group is 'current', rest 'future'."""
    with app.app_context():
        team = _seed_team(multiplier=1.0)
        result = compute_path_to_crown(team)
        assert result['eliminated'] is False
        assert result['eliminated_at_label'] is None
        assert [s['stage'] for s in result['segments']] == [
            'Group', 'R32', 'R16', 'QF', 'SF', 'Final',
        ]
        assert [s['status'] for s in result['segments']] == [
            'current', 'future', 'future', 'future', 'future', 'future',
        ]
        assert result['projected_ceiling'] == 107.0


def test_path_to_crown_group_eliminated(app):
    with app.app_context():
        team = _seed_team(multiplier=1.0, finish='group', eliminated=True,
                          base=3.0, multiplied=3.0)
        result = compute_path_to_crown(team)
        assert result['eliminated'] is True
        assert result['eliminated_at_label'] == 'Group Stage'
        assert [s['status'] for s in result['segments']] == [
            'eliminated', 'future', 'future', 'future', 'future', 'future',
        ]
        assert result['projected_ceiling'] == 3.0


def test_path_to_crown_advanced_from_group(app):
    """Cleared group, R32 not yet played: bf=None + advancement_method set."""
    with app.app_context():
        team = _seed_team(multiplier=1.0, adv='group_winner',
                          base=ADVANCE_GROUP_WINNER)
        result = compute_path_to_crown(team)
        assert result['eliminated'] is False
        assert [s['status'] for s in result['segments']] == [
            'won', 'current', 'future', 'future', 'future', 'future',
        ]
        assert result['projected_ceiling'] == 107.0


def test_path_to_crown_won_R32(app):
    with app.app_context():
        team = _seed_team(multiplier=1.0, adv='group_winner', finish='R32',
                          base=ADVANCE_GROUP_WINNER + KNOCKOUT_POINTS['R32'])
        result = compute_path_to_crown(team)
        assert result['eliminated'] is False
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'current', 'future', 'future', 'future',
        ]


def test_path_to_crown_lost_R16_via_match(app):
    """Won R32, then lost R16 - KO elimination derived from completed match."""
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='R32',
                          base=ADVANCE_GROUP_WINNER + KNOCKOUT_POINTS['R32'],
                          multiplied=ADVANCE_GROUP_WINNER + KNOCKOUT_POINTS['R32'])
        opp = _seed_team(fifa='OPP', group='B')
        _seed_completed_match(team.id, opp.id, stage='R16',
                              winner_id=opp.id, match_number=49)
        result = compute_path_to_crown(team)
        assert result['eliminated'] is True
        assert result['eliminated_at_label'] == 'Round of 16'
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'eliminated', 'future', 'future', 'future',
        ]
        assert result['projected_ceiling'] == 12.0


def test_path_to_crown_runner_up(app):
    with app.app_context():
        team = _seed_team(multiplier=1.0, adv='group_winner', finish='runner_up')
        result = compute_path_to_crown(team)
        assert result['eliminated'] is True
        assert result['eliminated_at_label'] == 'Final'
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'won', 'won', 'won', 'eliminated',
        ]


def test_path_to_crown_third_place_winner(app):
    """Lost SF, won 3rd-place playoff."""
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='3rd')
        result = compute_path_to_crown(team)
        assert result['eliminated'] is True
        assert result['eliminated_at_label'] == 'Semifinals'
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'won', 'won', 'eliminated', 'future',
        ]


def test_path_to_crown_champion(app):
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='champion')
        result = compute_path_to_crown(team)
        assert result['eliminated'] is False
        assert result['eliminated_at_label'] is None
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'won', 'won', 'won', 'won',
        ]


def test_path_to_crown_champion_sets_champion_flag(app):
    """A champion (cleared all 6 segments, not eliminated) carries
    champion=True so the template can swap the live 'projected ceiling /
    wins out from here' framing for a past-tense crowned register."""
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='champion')
        result = compute_path_to_crown(team)
        assert result['champion'] is True


def test_path_to_crown_alive_team_is_not_champion(app):
    """A team still alive mid-tournament (cleared the group, more to play)
    is not a champion — the projecting register still applies."""
    with app.app_context():
        team = _seed_team(adv='group_winner', finish=None)
        result = compute_path_to_crown(team)
        assert result['eliminated'] is False
        assert result['champion'] is False


def test_path_to_crown_eliminated_team_is_not_champion(app):
    """A runner-up lost the Final — eliminated, never champion."""
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='runner_up')
        result = compute_path_to_crown(team)
        assert result['champion'] is False


def test_path_to_crown_sf_state_with_no_terminal_match(app):
    """bf='SF' before any third_place/final completes -> treated as alive at depth=5."""
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='SF')
        result = compute_path_to_crown(team)
        assert result['eliminated'] is False
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'won', 'won', 'won', 'current',
        ]


def test_path_to_crown_fourth_place_finisher(app):
    """bf='SF' + completed third_place match -> 4th-place finisher."""
    with app.app_context():
        team = _seed_team(adv='group_winner', finish='SF')
        opp = _seed_team(fifa='OPP', group='B')
        _seed_completed_match(team.id, opp.id, stage='third_place',
                              winner_id=opp.id, match_number=63)
        result = compute_path_to_crown(team)
        assert result['eliminated'] is True
        assert result['eliminated_at_label'] == 'Semifinals'
        assert [s['status'] for s in result['segments']] == [
            'won', 'won', 'won', 'won', 'eliminated', 'future',
        ]
