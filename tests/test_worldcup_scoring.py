"""
Tests for the World Cup scoring engine.
Covers: group match scoring, advancement milestones, knockout rounds,
podium bonuses, pick/enrollment cascade, idempotency, and full scenarios.
"""
import pytest
from app import create_app
from extensions import db
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick,
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


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def session(app):
    with app.app_context():
        yield db.session


def _make_team(session, fifa_code, name, tier, multiplier, group='A'):
    """Helper to create a team."""
    team = WorldCupTeam(
        fifa_code=fifa_code,
        name=name,
        display_name=name,
        tier=tier,
        multiplier=multiplier,
        confederation='TEST',
        group_letter=group,
    )
    session.add(team)
    session.flush()
    return team


def _make_match(session, match_number, stage, home_team, away_team,
                group_letter=None):
    """Helper to create a match shell."""
    match = WorldCupMatch(
        match_number=match_number,
        stage=stage,
        group_letter=group_letter,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
    )
    session.add(match)
    session.flush()
    return match


def _make_user(session, username):
    """Helper to create a user."""
    user = User(username=username, email=f'{username}@test.com')
    user.set_password('test1234')
    session.add(user)
    session.flush()
    return user


def _make_enrollment(session, user, season_year=2026):
    """Helper to create an enrollment."""
    enrollment = WorldCupEnrollment(
        user_id=user.id,
        season_year=season_year,
        picks_submitted=True,
    )
    session.add(enrollment)
    session.flush()
    return enrollment


def _make_pick(session, enrollment, team, tier):
    """Helper to create a pick."""
    pick = WorldCupPick(
        enrollment_id=enrollment.id,
        team_id=team.id,
        tier=tier,
    )
    session.add(pick)
    session.flush()
    return pick


# ============================================================
# Group Stage Scoring
# ============================================================

class TestGroupWin:
    """A group stage win awards 3 base points and records W/L."""

    def test_single_group_win(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            mex = _make_team(db.session, 'MEX', 'Mexico', 3, 2.5, 'A')
            rsa = _make_team(db.session, 'RSA', 'South Africa', 5, 7.0, 'A')
            match = _make_match(db.session, 1, 'group', mex, rsa, 'A')
            db.session.commit()

            result = process_match_result(
                match_id=match.id,
                home_score=2, away_score=1,
                winner_fifa_code='MEX',
            )

            assert result['scores_updated'] is True
            db.session.refresh(mex)
            db.session.refresh(rsa)
            assert mex.base_points == 3.0
            assert mex.multiplied_points == 7.5  # 3.0 * 2.5
            assert mex.group_wins == 1
            assert mex.group_losses == 0
            assert rsa.base_points == 0.0
            assert rsa.multiplied_points == 0.0
            assert rsa.group_losses == 1
            assert rsa.group_wins == 0


class TestGroupDraw:
    """A group draw awards 1 base point to both teams."""

    def test_group_draw(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            bra = _make_team(db.session, 'BRA', 'Brazil', 1, 1.0, 'B')
            mar = _make_team(db.session, 'MAR', 'Morocco', 3, 2.5, 'B')
            match = _make_match(db.session, 6, 'group', bra, mar, 'B')
            db.session.commit()

            process_match_result(
                match_id=match.id,
                home_score=0, away_score=0,
                winner_fifa_code=None,
                is_draw=True,
            )

            db.session.refresh(bra)
            db.session.refresh(mar)
            assert bra.base_points == 1.0
            assert bra.multiplied_points == 1.0  # 1.0 * 1.0
            assert bra.group_draws == 1
            assert mar.base_points == 1.0
            assert mar.multiplied_points == 2.5  # 1.0 * 2.5
            assert mar.group_draws == 1


class TestFullGroupStage:
    """Three group matches produce correct standings."""

    def test_three_matches_one_group(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, recalculate_all_scores,
            )

            # Group A: 4 teams, 6 matches (round-robin)
            t1 = _make_team(db.session, 'T1A', 'Team1A', 1, 1.0, 'A')
            t2 = _make_team(db.session, 'T2A', 'Team2A', 2, 1.5, 'A')
            t3 = _make_team(db.session, 'T3A', 'Team3A', 3, 2.5, 'A')
            t4 = _make_team(db.session, 'T4A', 'Team4A', 4, 4.0, 'A')

            # T1 beats T2, T1 beats T3, T1 draws T4
            # T2 beats T3, T2 beats T4
            # T3 beats T4
            m1 = _make_match(db.session, 101, 'group', t1, t2, 'A')
            m2 = _make_match(db.session, 102, 'group', t1, t3, 'A')
            m3 = _make_match(db.session, 103, 'group', t1, t4, 'A')
            m4 = _make_match(db.session, 104, 'group', t2, t3, 'A')
            m5 = _make_match(db.session, 105, 'group', t2, t4, 'A')
            m6 = _make_match(db.session, 106, 'group', t3, t4, 'A')
            db.session.commit()

            process_match_result(m1.id, 2, 1, 'T1A')
            process_match_result(m2.id, 3, 0, 'T1A')
            process_match_result(m3.id, 1, 1, None, is_draw=True)
            process_match_result(m4.id, 2, 0, 'T2A')
            process_match_result(m5.id, 1, 0, 'T2A')
            process_match_result(m6.id, 2, 1, 'T3A')

            db.session.refresh(t1)
            db.session.refresh(t2)
            db.session.refresh(t3)
            db.session.refresh(t4)

            # T1: 2W 0D 1D = 6+1=7 base
            assert t1.group_wins == 2
            assert t1.group_draws == 1
            assert t1.group_losses == 0
            assert t1.base_points == 7.0

            # T2: 2W 1L = 6 base
            assert t2.group_wins == 2
            assert t2.group_losses == 1
            assert t2.base_points == 6.0

            # T3: 1W 2L = 3 base
            assert t3.group_wins == 1
            assert t3.group_losses == 2
            assert t3.base_points == 3.0

            # T4: 0W 1D 2L = 1 base
            assert t4.group_wins == 0
            assert t4.group_draws == 1
            assert t4.group_losses == 2
            assert t4.base_points == 1.0


# ============================================================
# Advancement Milestones
# ============================================================

class TestAdvancementMilestones:
    """Advancement milestones add 4/3/1 base points."""

    def test_group_winner_gets_4(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import recalculate_all_scores

            team = _make_team(db.session, 'ESP', 'Spain', 1, 1.0)
            team.advancement_method = 'group_winner'
            db.session.commit()

            recalculate_all_scores()
            db.session.refresh(team)
            assert team.base_points == 4.0

    def test_runner_up_gets_3(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import recalculate_all_scores

            team = _make_team(db.session, 'URU', 'Uruguay', 3, 2.5)
            team.advancement_method = 'runner_up'
            db.session.commit()

            recalculate_all_scores()
            db.session.refresh(team)
            assert team.base_points == 3.0
            assert team.multiplied_points == 7.5

    def test_best_third_gets_1(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import recalculate_all_scores

            team = _make_team(db.session, 'IRN', 'Iran', 5, 7.0)
            team.advancement_method = 'best_third'
            db.session.commit()

            recalculate_all_scores()
            db.session.refresh(team)
            assert team.base_points == 1.0
            assert team.multiplied_points == 7.0


# ============================================================
# Knockout Scoring
# ============================================================

class TestKnockoutScoring:
    """Knockout wins award stage-specific points."""

    def test_r32_win(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'KO1', 'KO Team 1', 1, 1.0)
            t2 = _make_team(db.session, 'KO2', 'KO Team 2', 2, 1.5)
            match = _make_match(db.session, 50, 'R32', t1, t2)
            db.session.commit()

            process_match_result(match.id, 2, 1, 'KO1')

            db.session.refresh(t1)
            assert t1.base_points == 8.0
            assert t1.best_finish == 'R32'

    def test_r16_win(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'R16A', 'R16 Team A', 3, 2.5)
            t2 = _make_team(db.session, 'R16B', 'R16 Team B', 4, 4.0)
            match = _make_match(db.session, 60, 'R16', t1, t2)
            db.session.commit()

            process_match_result(match.id, 1, 0, 'R16A')

            db.session.refresh(t1)
            assert t1.base_points == 11.0
            assert t1.multiplied_points == 27.5

    def test_qf_win(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'QFA', 'QF Team A', 1, 1.0)
            t2 = _make_team(db.session, 'QFB', 'QF Team B', 1, 1.0)
            match = _make_match(db.session, 70, 'QF', t1, t2)
            db.session.commit()

            process_match_result(match.id, 3, 2, 'QFA')

            db.session.refresh(t1)
            assert t1.base_points == 15.0

    def test_sf_win(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'SFA', 'SF Team A', 2, 1.5)
            t2 = _make_team(db.session, 'SFB', 'SF Team B', 3, 2.5)
            match = _make_match(db.session, 80, 'SF', t1, t2)
            db.session.commit()

            process_match_result(match.id, 2, 1, 'SFA')

            db.session.refresh(t1)
            assert t1.base_points == 19.0
            db.session.refresh(t2)
            assert t2.best_finish == 'SF'

    def test_knockout_with_penalties(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'PEN1', 'Pen Team 1', 4, 4.0)
            t2 = _make_team(db.session, 'PEN2', 'Pen Team 2', 5, 7.0)
            match = _make_match(db.session, 55, 'R32', t1, t2)
            db.session.commit()

            process_match_result(
                match.id, 1, 1, 'PEN1',
                extra_time=True, penalties=True,
            )

            db.session.refresh(t1)
            assert t1.base_points == 8.0  # same as normal win


# ============================================================
# Podium Bonuses
# ============================================================

class TestPodiumBonuses:
    """Champion (50), runner-up (8), third place (8)."""

    def test_champion_bonus(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import recalculate_all_scores

            team = _make_team(db.session, 'CHP', 'Champion', 1, 1.0)
            team.best_finish = 'champion'
            db.session.commit()

            recalculate_all_scores()
            db.session.refresh(team)
            assert team.base_points == 50.0

    def test_runner_up_bonus(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import recalculate_all_scores

            team = _make_team(db.session, 'RUP', 'Runner Up', 2, 1.5)
            team.best_finish = 'runner_up'
            db.session.commit()

            recalculate_all_scores()
            db.session.refresh(team)
            assert team.base_points == 8.0
            assert team.multiplied_points == 12.0

    def test_third_place_bonus(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import recalculate_all_scores

            team = _make_team(db.session, 'THR', 'Third Place', 3, 2.5)
            team.best_finish = '3rd'
            db.session.commit()

            recalculate_all_scores()
            db.session.refresh(team)
            assert team.base_points == 8.0
            assert team.multiplied_points == 20.0

    def test_final_sets_champion_and_runner_up(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'FIN1', 'Finalist 1', 1, 1.0)
            t2 = _make_team(db.session, 'FIN2', 'Finalist 2', 1, 1.0)
            match = _make_match(db.session, 104, 'final', t1, t2)
            db.session.commit()

            process_match_result(match.id, 3, 1, 'FIN1')

            db.session.refresh(t1)
            db.session.refresh(t2)
            assert t1.best_finish == 'champion'
            assert t2.best_finish == 'runner_up'

    def test_third_place_match(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'TP1', '3rd Place 1', 2, 1.5)
            t2 = _make_team(db.session, 'TP2', '3rd Place 2', 3, 2.5)
            # Both lost semifinals, so best_finish = 'SF'
            t1.best_finish = 'SF'
            t2.best_finish = 'SF'
            match = _make_match(db.session, 103, 'third_place', t1, t2)
            db.session.commit()

            process_match_result(match.id, 2, 0, 'TP1')

            db.session.refresh(t1)
            db.session.refresh(t2)
            assert t1.best_finish == '3rd'
            assert t2.best_finish == 'SF'  # loser stays at SF


# ============================================================
# Pick & Enrollment Cascade
# ============================================================

class TestPickEnrollmentCascade:
    """Scores cascade: team -> pick -> enrollment."""

    def test_pick_reflects_team_score(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            team = _make_team(db.session, 'CSC', 'Cascade', 3, 2.5, 'C')
            opp = _make_team(db.session, 'OPP', 'Opponent', 4, 4.0, 'C')
            match = _make_match(db.session, 10, 'group', team, opp, 'C')

            user = _make_user(db.session, 'cascadeuser')
            enrollment = _make_enrollment(db.session, user)
            pick = _make_pick(db.session, enrollment, team, 3)
            db.session.commit()

            process_match_result(match.id, 1, 0, 'CSC')

            db.session.refresh(pick)
            db.session.refresh(enrollment)
            assert pick.base_points == 3.0
            assert pick.multiplied_points == 7.5
            assert enrollment.total_score == 7.5

    def test_enrollment_sums_all_picks(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import recalculate_all_scores

            t1 = _make_team(db.session, 'SUM1', 'Sum1', 1, 1.0, 'A')
            t2 = _make_team(db.session, 'SUM2', 'Sum2', 5, 7.0, 'B')
            t1.advancement_method = 'group_winner'
            t2.advancement_method = 'best_third'
            user = _make_user(db.session, 'sumuser')
            enrollment = _make_enrollment(db.session, user)
            _make_pick(db.session, enrollment, t1, 1)
            _make_pick(db.session, enrollment, t2, 5)
            db.session.commit()

            recalculate_all_scores()

            db.session.refresh(enrollment)
            # t1: 4 base * 1.0 = 4.0; t2: 1 base * 7.0 = 7.0
            assert enrollment.total_score == 11.0


# ============================================================
# Idempotency
# ============================================================

class TestIdempotency:
    """Running recalc twice produces identical results."""

    def test_double_recalc(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, recalculate_all_scores,
            )

            mex = _make_team(db.session, 'MEX', 'Mexico', 3, 2.5, 'A')
            rsa = _make_team(db.session, 'RSA', 'South Africa', 5, 7.0, 'A')
            match = _make_match(db.session, 1, 'group', mex, rsa, 'A')
            db.session.commit()

            process_match_result(match.id, 2, 1, 'MEX')

            r1 = recalculate_all_scores()
            db.session.refresh(mex)
            mex_pts_1 = mex.multiplied_points
            db.session.refresh(rsa)
            rsa_pts_1 = rsa.multiplied_points

            r2 = recalculate_all_scores()
            db.session.refresh(mex)
            mex_pts_2 = mex.multiplied_points
            db.session.refresh(rsa)
            rsa_pts_2 = rsa.multiplied_points

            assert mex_pts_1 == mex_pts_2
            assert rsa_pts_1 == rsa_pts_2
            assert r1 == r2


# ============================================================
# Full Scenarios from Game Design Doc
# ============================================================

class TestSpainChampion:
    """Spain (Tier 1, x1): 3W group + win group + all knockout + champion = 116.0"""

    def test_spain_undefeated_champion(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, apply_group_advancement,
                recalculate_all_scores,
            )

            esp = _make_team(db.session, 'ESP', 'Spain', 1, 1.0, 'A')
            opp1 = _make_team(db.session, 'OP1', 'Opp1', 3, 2.5, 'A')
            opp2 = _make_team(db.session, 'OP2', 'Opp2', 4, 4.0, 'A')
            opp3 = _make_team(db.session, 'OP3', 'Opp3', 5, 7.0, 'A')

            # Group matches
            gm1 = _make_match(db.session, 1, 'group', esp, opp1, 'A')
            gm2 = _make_match(db.session, 2, 'group', esp, opp2, 'A')
            gm3 = _make_match(db.session, 3, 'group', esp, opp3, 'A')

            # Knockout opponents
            ko_opp1 = _make_team(db.session, 'KR1', 'KO R32', 2, 1.5)
            ko_opp2 = _make_team(db.session, 'KR2', 'KO R16', 3, 2.5)
            ko_opp3 = _make_team(db.session, 'KR3', 'KO QF', 1, 1.0)
            ko_opp4 = _make_team(db.session, 'KR4', 'KO SF', 2, 1.5)
            ko_opp5 = _make_team(db.session, 'KR5', 'KO Final', 1, 1.0)

            km1 = _make_match(db.session, 50, 'R32', esp, ko_opp1)
            km2 = _make_match(db.session, 60, 'R16', esp, ko_opp2)
            km3 = _make_match(db.session, 70, 'QF', esp, ko_opp3)
            km4 = _make_match(db.session, 80, 'SF', esp, ko_opp4)
            km5 = _make_match(db.session, 104, 'final', esp, ko_opp5)
            db.session.commit()

            # Group wins
            process_match_result(gm1.id, 2, 0, 'ESP')
            process_match_result(gm2.id, 3, 1, 'ESP')
            process_match_result(gm3.id, 1, 0, 'ESP')

            # Advancement
            apply_group_advancement('A', {
                'ESP': 'group_winner',
            })

            # Knockout wins
            process_match_result(km1.id, 2, 0, 'ESP')
            process_match_result(km2.id, 1, 0, 'ESP')
            process_match_result(km3.id, 2, 1, 'ESP')
            process_match_result(km4.id, 3, 2, 'ESP')
            process_match_result(km5.id, 2, 0, 'ESP')

            db.session.refresh(esp)
            # 3W(9) + group_winner(4) + R32(8) + R16(11) + QF(15) + SF(19) + champion(50) = 116
            assert esp.base_points == 116.0
            assert esp.multiplied_points == 116.0  # x1


class TestIranCinderella:
    """Iran (Tier 5, x7): 1W 1D 1L + best_third + R32 + R16 = 24 base * 7 = 168.0"""

    def test_iran_cinderella_run(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, apply_group_advancement,
                recalculate_all_scores,
            )

            irn = _make_team(db.session, 'IRN', 'Iran', 5, 7.0, 'F')
            op1 = _make_team(db.session, 'IF1', 'Iran Opp 1', 1, 1.0, 'F')
            op2 = _make_team(db.session, 'IF2', 'Iran Opp 2', 3, 2.5, 'F')
            op3 = _make_team(db.session, 'IF3', 'Iran Opp 3', 4, 4.0, 'F')

            gm1 = _make_match(db.session, 20, 'group', irn, op1, 'F')
            gm2 = _make_match(db.session, 21, 'group', irn, op2, 'F')
            gm3 = _make_match(db.session, 22, 'group', op3, irn, 'F')

            ko_op1 = _make_team(db.session, 'IK1', 'Iran KO1', 2, 1.5)
            ko_op2 = _make_team(db.session, 'IK2', 'Iran KO2', 1, 1.0)

            km1 = _make_match(db.session, 51, 'R32', irn, ko_op1)
            km2 = _make_match(db.session, 61, 'R16', irn, ko_op2)
            db.session.commit()

            # 1W 1D 1L
            process_match_result(gm1.id, 1, 0, 'IRN')     # win
            process_match_result(gm2.id, 0, 0, None, is_draw=True)  # draw
            process_match_result(gm3.id, 2, 1, 'IF3')     # loss (op3 wins)

            apply_group_advancement('F', {'IRN': 'best_third'})

            process_match_result(km1.id, 1, 0, 'IRN')
            process_match_result(km2.id, 2, 1, 'IRN')

            db.session.refresh(irn)
            # 1W(3) + 1D(1) + best_third(1) + R32(8) + R16(11) = 24 base
            assert irn.base_points == 24.0
            assert irn.multiplied_points == 168.0  # 24 * 7


class TestNorwayRunnerUp:
    """Norway (Tier 2, x1.5): 2W 1D + runner_up + R32-SF + runner_up bonus = 71 * 1.5 = 106.5"""

    def test_norway_runner_up_half_points(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                process_match_result, apply_group_advancement,
                recalculate_all_scores,
            )

            nor = _make_team(db.session, 'NOR', 'Norway', 2, 1.5, 'C')
            no1 = _make_team(db.session, 'NO1', 'Nor Opp 1', 1, 1.0, 'C')
            no2 = _make_team(db.session, 'NO2', 'Nor Opp 2', 3, 2.5, 'C')
            no3 = _make_team(db.session, 'NO3', 'Nor Opp 3', 4, 4.0, 'C')

            gm1 = _make_match(db.session, 30, 'group', nor, no1, 'C')
            gm2 = _make_match(db.session, 31, 'group', nor, no2, 'C')
            gm3 = _make_match(db.session, 32, 'group', nor, no3, 'C')

            ko1 = _make_team(db.session, 'NK1', 'Nor KO1', 3, 2.5)
            ko2 = _make_team(db.session, 'NK2', 'Nor KO2', 4, 4.0)
            ko3 = _make_team(db.session, 'NK3', 'Nor KO3', 2, 1.5)
            ko4 = _make_team(db.session, 'NK4', 'Nor KO4', 1, 1.0)
            final_opp = _make_team(db.session, 'NK5', 'Final Opp', 1, 1.0)

            km1 = _make_match(db.session, 52, 'R32', nor, ko1)
            km2 = _make_match(db.session, 62, 'R16', nor, ko2)
            km3 = _make_match(db.session, 72, 'QF', nor, ko3)
            km4 = _make_match(db.session, 82, 'SF', nor, ko4)
            km5 = _make_match(db.session, 104, 'final', final_opp, nor)
            db.session.commit()

            # 2W 1D in group
            process_match_result(gm1.id, 2, 1, 'NOR')
            process_match_result(gm2.id, 3, 0, 'NOR')
            process_match_result(gm3.id, 0, 0, None, is_draw=True)

            apply_group_advancement('C', {'NOR': 'runner_up'})

            process_match_result(km1.id, 1, 0, 'NOR')
            process_match_result(km2.id, 2, 0, 'NOR')
            process_match_result(km3.id, 1, 0, 'NOR')
            process_match_result(km4.id, 2, 1, 'NOR')
            # Lose the final
            process_match_result(km5.id, 3, 1, 'NK5')

            db.session.refresh(nor)
            # 2W(6) + 1D(1) + runner_up_advance(3) + R32(8) + R16(11) + QF(15) + SF(19) + runner_up_bonus(8) = 71
            assert nor.base_points == 71.0
            assert nor.multiplied_points == 106.5  # 71 * 1.5


# ============================================================
# best_finish never regresses
# ============================================================

class TestBestFinishProgression:
    """best_finish only moves forward, never backward."""

    def test_best_finish_does_not_regress(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'PRG', 'Progressor', 1, 1.0)
            t2 = _make_team(db.session, 'PRO', 'Opp Prog', 2, 1.5)
            # Manually set best_finish to QF (as if they already won QF)
            t1.best_finish = 'QF'

            # Now they play an R32 match (shouldn't happen, but tests regression guard)
            match = _make_match(db.session, 55, 'R32', t1, t2)
            db.session.commit()

            process_match_result(match.id, 1, 0, 'PRG')

            db.session.refresh(t1)
            assert t1.best_finish == 'QF'  # should NOT regress to R32


# ============================================================
# process_match_result error handling
# ============================================================

class TestProcessMatchErrors:
    """Duplicate match entry returns error."""

    def test_reject_already_completed(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'DUP1', 'Dup1', 1, 1.0, 'A')
            t2 = _make_team(db.session, 'DUP2', 'Dup2', 2, 1.5, 'A')
            match = _make_match(db.session, 99, 'group', t1, t2, 'A')
            db.session.commit()

            process_match_result(match.id, 2, 0, 'DUP1')
            result = process_match_result(match.id, 3, 1, 'DUP1')

            assert 'error' in result


# ============================================================
# Group Advancement
# ============================================================

class TestGroupAdvancement:
    """apply_group_advancement sets methods and eliminates non-advancers."""

    def test_advancement_and_elimination(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import apply_group_advancement

            t1 = _make_team(db.session, 'GA1', 'Group A1', 1, 1.0, 'A')
            t2 = _make_team(db.session, 'GA2', 'Group A2', 2, 1.5, 'A')
            t3 = _make_team(db.session, 'GA3', 'Group A3', 3, 2.5, 'A')
            t4 = _make_team(db.session, 'GA4', 'Group A4', 4, 4.0, 'A')
            db.session.commit()

            result = apply_group_advancement('A', {
                'GA1': 'group_winner',
                'GA2': 'runner_up',
                'GA3': 'best_third',
            })

            db.session.refresh(t1)
            db.session.refresh(t2)
            db.session.refresh(t3)
            db.session.refresh(t4)

            assert t1.advancement_method == 'group_winner'
            assert t1.is_eliminated is False
            assert t2.advancement_method == 'runner_up'
            assert t3.advancement_method == 'best_third'
            assert t4.is_eliminated is True
            assert t4.best_finish == 'group'
            assert 'GA4' in [t for t in result['eliminated']]


# ============================================================
# set_knockout_teams
# ============================================================

class TestSetKnockoutTeams:
    """Assigns teams to knockout match shells."""

    def test_assign_teams(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import set_knockout_teams

            t1 = _make_team(db.session, 'SK1', 'SetKO 1', 1, 1.0)
            t2 = _make_team(db.session, 'SK2', 'SetKO 2', 2, 1.5)
            match = WorldCupMatch(
                match_number=49, stage='R32',
            )
            db.session.add(match)
            db.session.commit()

            result = set_knockout_teams(match.id, 'SK1', 'SK2')

            db.session.refresh(match)
            assert match.home_team_id == t1.id
            assert match.away_team_id == t2.id


# ============================================================
# Half-point precision
# ============================================================

class TestHalfPointPrecision:
    """Multipliers on odd base values produce .5 scores."""

    def test_tier2_three_base_gives_4_5(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            team = _make_team(db.session, 'HLF', 'Half Pt', 2, 1.5, 'D')
            opp = _make_team(db.session, 'HLO', 'Half Opp', 3, 2.5, 'D')
            match = _make_match(db.session, 15, 'group', team, opp, 'D')
            db.session.commit()

            process_match_result(match.id, 1, 0, 'HLF')

            db.session.refresh(team)
            assert team.base_points == 3.0
            assert team.multiplied_points == 4.5
