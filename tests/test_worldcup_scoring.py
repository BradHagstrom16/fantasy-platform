"""
Tests for the World Cup scoring engine.
Covers: group match scoring, advancement milestones, knockout rounds,
podium bonuses, pick/enrollment cascade, idempotency, and full scenarios.
"""
import pytest

from app import create_app
from extensions import db
from games.worldcup.models import (
    WorldCupEnrollment,
    WorldCupMatch,
    WorldCupPick,
    WorldCupTeam,
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
                process_match_result,
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

    def test_pk_match_stores_pen_columns(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'PKA', 'PK Alpha', 4, 4.0)
            t2 = _make_team(db.session, 'PKB', 'PK Beta', 5, 7.0)
            match = _make_match(db.session, 201, 'R32', t1, t2)
            db.session.commit()

            # Away side (PKB) wins the shootout 4-3, so the declared winner must
            # be PKB to match the tally.
            process_match_result(
                match.id, 1, 1, 'PKB',
                extra_time=True, penalties=True,
                home_pen=3, away_pen=4,
            )

            db.session.refresh(match)
            assert match.home_score == 1
            assert match.away_score == 1
            assert match.home_pen == 3
            assert match.away_pen == 4

    def test_non_pk_match_pen_columns_null(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import process_match_result

            t1 = _make_team(db.session, 'REG1', 'Reg One', 4, 4.0)
            t2 = _make_team(db.session, 'REG2', 'Reg Two', 5, 7.0)
            match = _make_match(db.session, 202, 'R32', t1, t2)
            db.session.commit()

            process_match_result(match.id, 2, 0, 'REG1')

            db.session.refresh(match)
            assert match.home_pen is None
            assert match.away_pen is None


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
                process_match_result,
                recalculate_all_scores,
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
                apply_group_advancement,
                process_match_result,
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
                apply_group_advancement,
                process_match_result,
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
                apply_group_advancement,
                process_match_result,
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
            assert 'GA4' in result['eliminated']


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

            set_knockout_teams(match.id, 'SK1', 'SK2')

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


# ============================================================
# Score Event Attribution (display-time derivation, ADR-024)
# ============================================================

class TestComputeTeamScoreEventsGroup:
    """compute_team_score_events derives per-team scoring sources from match state."""

    def test_group_win_emits_single_event(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                compute_team_score_events,
                process_match_result,
            )
            mex = _make_team(db.session, 'MEX', 'Mexico', 3, 2.5, 'A')
            rsa = _make_team(db.session, 'RSA', 'South Africa', 5, 7.0, 'A')
            match = _make_match(db.session, 1, 'group', mex, rsa, 'A')
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=2, away_score=1,
                winner_fifa_code='MEX',
            )
            db.session.refresh(mex)

            events = compute_team_score_events(mex)
            assert len(events) == 1
            assert events[0].source == 'group_win'
            assert events[0].base_points == 3.0
            assert events[0].match_id == match.id
            assert 'RSA' in events[0].label or 'South Africa' in events[0].label

    def test_group_draw_emits_event_for_both_teams(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                compute_team_score_events,
                process_match_result,
            )
            bra = _make_team(db.session, 'BRA', 'Brazil', 1, 1.0, 'B')
            mar = _make_team(db.session, 'MAR', 'Morocco', 3, 2.5, 'B')
            match = _make_match(db.session, 6, 'group', bra, mar, 'B')
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=0, away_score=0,
                winner_fifa_code=None, is_draw=True,
            )
            db.session.refresh(bra)
            db.session.refresh(mar)

            bra_events = compute_team_score_events(bra)
            mar_events = compute_team_score_events(mar)
            assert len(bra_events) == 1
            assert bra_events[0].source == 'group_draw'
            assert bra_events[0].base_points == 1.0
            assert len(mar_events) == 1
            assert mar_events[0].source == 'group_draw'

    def test_group_loss_emits_no_event(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                compute_team_score_events,
                process_match_result,
            )
            arg = _make_team(db.session, 'ARG', 'Argentina', 1, 1.0, 'C')
            ksa = _make_team(db.session, 'KSA', 'Saudi Arabia', 5, 7.0, 'C')
            match = _make_match(db.session, 10, 'group', arg, ksa, 'C')
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=1, away_score=2,
                winner_fifa_code='KSA',
            )
            db.session.refresh(arg)

            events = compute_team_score_events(arg)
            assert events == []


class TestComputeTeamScoreEventsAdvancement:
    """Advancement methods emit events worth the matching constant."""

    def test_group_winner_advancement_emits_event(self, app):
        with app.app_context():
            from games.worldcup.constants import ADVANCE_GROUP_WINNER
            from games.worldcup.services.scoring import (
                apply_group_advancement,
                compute_team_score_events,
            )

            esp = _make_team(db.session, 'ESP', 'Spain', 1, 1.0, 'A')
            _make_team(db.session, 'URU', 'Uruguay', 2, 1.5, 'A')
            _make_team(db.session, 'KSA', 'Saudi Arabia', 5, 7.0, 'A')
            _make_team(db.session, 'JPN', 'Japan', 4, 4.0, 'A')
            db.session.commit()

            apply_group_advancement('A', {
                'ESP': 'group_winner',
                'URU': 'runner_up',
                'KSA': 'best_third',
            })
            db.session.refresh(esp)

            events = compute_team_score_events(esp)
            adv_events = [e for e in events if e.source == 'advancement']
            assert len(adv_events) == 1
            assert adv_events[0].base_points == float(ADVANCE_GROUP_WINNER)
            assert 'winner' in adv_events[0].label.lower()


class TestComputeTeamScoreEventsKnockout:
    """Knockout wins emit events worth KNOCKOUT_POINTS[stage]."""

    def test_r16_win_emits_knockout_event(self, app):
        with app.app_context():
            from games.worldcup.constants import KNOCKOUT_POINTS
            from games.worldcup.services.scoring import (
                compute_team_score_events,
                process_match_result,
            )

            arg = _make_team(db.session, 'ARG', 'Argentina', 1, 1.0, 'A')
            cro = _make_team(db.session, 'CRO', 'Croatia', 3, 2.5, 'B')
            match = _make_match(db.session, 105, 'R16', arg, cro)
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=2, away_score=1,
                winner_fifa_code='ARG',
            )
            db.session.refresh(arg)

            events = compute_team_score_events(arg)
            ko_events = [e for e in events if e.source == 'knockout']
            assert len(ko_events) == 1
            assert ko_events[0].base_points == float(KNOCKOUT_POINTS['R16'])
            assert ko_events[0].match_id == match.id


class TestComputeTeamScoreEventsPodium:
    """Champion / runner_up / third_place each add a podium event."""

    def test_champion_emits_podium_event(self, app):
        with app.app_context():
            from games.worldcup.constants import KNOCKOUT_POINTS
            from games.worldcup.services.scoring import (
                compute_team_score_events,
                process_match_result,
            )

            arg = _make_team(db.session, 'ARG', 'Argentina', 1, 1.0, 'A')
            fra = _make_team(db.session, 'FRA', 'France', 1, 1.0, 'B')
            match = _make_match(db.session, 104, 'final', arg, fra)
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=3, away_score=2,
                winner_fifa_code='ARG',
            )
            db.session.refresh(arg)

            events = compute_team_score_events(arg)
            podium = [e for e in events if e.source == 'podium']
            assert len(podium) == 1
            assert podium[0].base_points == float(KNOCKOUT_POINTS['champion'])


class TestComputeTeamScoreEventsInvariant:
    """Invariant: sum of event base_points == team.base_points."""

    def test_sum_matches_base_points_after_full_recalc(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                apply_group_advancement,
                compute_team_score_events,
                process_match_result,
            )

            # Build a tiny simulated tournament: one group + one R32
            esp = _make_team(db.session, 'ESP', 'Spain', 1, 1.0, 'A')
            uru = _make_team(db.session, 'URU', 'Uruguay', 2, 1.5, 'A')
            ksa = _make_team(db.session, 'KSA', 'Saudi Arabia', 5, 7.0, 'A')
            jpn = _make_team(db.session, 'JPN', 'Japan', 4, 4.0, 'A')
            m1 = _make_match(db.session, 1, 'group', esp, uru, 'A')
            m2 = _make_match(db.session, 2, 'group', ksa, jpn, 'A')
            m3 = _make_match(db.session, 3, 'group', esp, ksa, 'A')
            db.session.commit()

            process_match_result(
                match_id=m1.id, home_score=2, away_score=1,
                winner_fifa_code='ESP',
            )
            process_match_result(
                match_id=m2.id, home_score=0, away_score=0,
                winner_fifa_code=None, is_draw=True,
            )
            process_match_result(
                match_id=m3.id, home_score=3, away_score=0,
                winner_fifa_code='ESP',
            )
            apply_group_advancement('A', {
                'ESP': 'group_winner',
                'URU': 'runner_up',
            })

            for team in WorldCupTeam.query.all():
                db.session.refresh(team)
                events = compute_team_score_events(team)
                derived = sum(e.base_points for e in events)
                assert derived == team.base_points, (
                    f'{team.fifa_code}: derived {derived} != stored {team.base_points}'
                )


class TestComputeMatchAttribution:
    """compute_match_attribution emits chip data for completed matches."""

    def test_incomplete_match_returns_none(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import compute_match_attribution

            a = _make_team(db.session, 'AAA', 'Team A', 3, 2.5, 'A')
            b = _make_team(db.session, 'BBB', 'Team B', 3, 2.5, 'A')
            match = _make_match(db.session, 1, 'group', a, b, 'A')
            db.session.commit()

            assert compute_match_attribution(match) is None

    def test_group_win_returns_winner_plus_three(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                compute_match_attribution,
                process_match_result,
            )
            mex = _make_team(db.session, 'MEX', 'Mexico', 3, 2.5, 'A')
            rsa = _make_team(db.session, 'RSA', 'South Africa', 5, 7.0, 'A')
            match = _make_match(db.session, 1, 'group', mex, rsa, 'A')
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=2, away_score=1,
                winner_fifa_code='MEX',
            )
            db.session.refresh(match)

            attr = compute_match_attribution(match)
            assert attr is not None
            assert attr['type'] == 'group_win'
            assert attr['events'] == [('Mexico', 'MEX', 3.0)]

    def test_group_draw_returns_both_teams_plus_one(self, app):
        with app.app_context():
            from games.worldcup.services.scoring import (
                compute_match_attribution,
                process_match_result,
            )
            bra = _make_team(db.session, 'BRA', 'Brazil', 1, 1.0, 'B')
            mar = _make_team(db.session, 'MAR', 'Morocco', 3, 2.5, 'B')
            match = _make_match(db.session, 6, 'group', bra, mar, 'B')
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=1, away_score=1,
                winner_fifa_code=None, is_draw=True,
            )
            db.session.refresh(match)

            attr = compute_match_attribution(match)
            assert attr is not None
            assert attr['type'] == 'group_draw'
            assert ('Brazil', 'BRA', 1.0) in attr['events']
            assert ('Morocco', 'MAR', 1.0) in attr['events']
            assert len(attr['events']) == 2

    def test_knockout_win_includes_stage_points(self, app):
        with app.app_context():
            from games.worldcup.constants import KNOCKOUT_POINTS
            from games.worldcup.services.scoring import (
                compute_match_attribution,
                process_match_result,
            )

            arg = _make_team(db.session, 'ARG', 'Argentina', 1, 1.0, 'A')
            cro = _make_team(db.session, 'CRO', 'Croatia', 3, 2.5, 'B')
            match = _make_match(db.session, 105, 'R16', arg, cro)
            db.session.commit()

            process_match_result(
                match_id=match.id, home_score=2, away_score=1,
                winner_fifa_code='ARG',
            )
            db.session.refresh(match)

            attr = compute_match_attribution(match)
            assert attr is not None
            assert attr['type'] == 'knockout'
            assert attr['stage'] == 'R16'
            assert attr['events'] == [('Argentina', 'ARG', float(KNOCKOUT_POINTS['R16']))]


def test_points_for_pick_on_match_group_win_t1(app, session):
    """A T1 (mult 1.0) pick wins a group match → +3.0 points."""
    from games.worldcup.services.scoring import points_for_pick_on_match
    with app.app_context():
        bra = _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
        arg = _make_team(session, 'ARG', 'Argentina', tier=1, multiplier=1.0)
        match = _make_match(session, 1, 'group', bra, arg, group_letter='C')
        match.is_completed = True
        match.winner_team_id = bra.id
        user = _make_user(session, 'tester1')
        enr = _make_enrollment(session, user)
        pick = _make_pick(session, enr, bra, tier=1)
        session.commit()
        assert points_for_pick_on_match(pick, match) == 3.0


def test_points_for_pick_on_match_group_draw_t5(app, session):
    """A T5 (mult 7.0) pick draws → +7.0 points (1 base × 7.0 multiplier)."""
    from games.worldcup.services.scoring import points_for_pick_on_match
    with app.app_context():
        nor = _make_team(session, 'NOR', 'Norway', tier=5, multiplier=7.0)
        usa = _make_team(session, 'USA', 'United States', tier=1, multiplier=1.0)
        match = _make_match(session, 2, 'group', nor, usa, group_letter='I')
        match.is_completed = True
        match.is_draw = True
        match.winner_team_id = None
        user = _make_user(session, 'tester2')
        enr = _make_enrollment(session, user)
        pick = _make_pick(session, enr, nor, tier=5)
        session.commit()
        assert points_for_pick_on_match(pick, match) == 7.0


def test_points_for_pick_on_match_loss_returns_zero(app, session):
    """The losing side of a group match earns 0 from that match."""
    from games.worldcup.services.scoring import points_for_pick_on_match
    with app.app_context():
        bra = _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
        arg = _make_team(session, 'ARG', 'Argentina', tier=1, multiplier=1.0)
        match = _make_match(session, 3, 'group', bra, arg, group_letter='C')
        match.is_completed = True
        match.winner_team_id = bra.id  # bra wins
        user = _make_user(session, 'tester3')
        enr = _make_enrollment(session, user)
        pick = _make_pick(session, enr, arg, tier=1)  # user picked the loser
        session.commit()
        assert points_for_pick_on_match(pick, match) == 0.0


def test_points_for_pick_on_match_uncompleted_returns_zero(app, session):
    """A match with is_completed=False yields 0, regardless of winner_team_id."""
    from games.worldcup.services.scoring import points_for_pick_on_match
    with app.app_context():
        bra = _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
        arg = _make_team(session, 'ARG', 'Argentina', tier=1, multiplier=1.0)
        match = _make_match(session, 4, 'group', bra, arg, group_letter='C')
        match.is_completed = False
        match.winner_team_id = bra.id  # set but match not completed
        user = _make_user(session, 'tester4')
        enr = _make_enrollment(session, user)
        pick = _make_pick(session, enr, bra, tier=1)
        session.commit()
        assert points_for_pick_on_match(pick, match) == 0.0


def test_points_for_pick_on_match_group_draw_non_participant_returns_zero(app, session):
    """A pick on a team that did NOT play in a drawn match earns 0.

    Regression: prior to this guard the helper returned GROUP_DRAW × multiplier
    for any pick on any drawn group match, regardless of participation.
    """
    from games.worldcup.services.scoring import points_for_pick_on_match
    with app.app_context():
        esp = _make_team(session, 'ESP', 'Spain', tier=1, multiplier=1.0)
        ger = _make_team(session, 'GER', 'Germany', tier=1, multiplier=1.0)
        bra = _make_team(session, 'BRA', 'Brazil', tier=5, multiplier=7.0)
        match = _make_match(session, 5, 'group', esp, ger, group_letter='B')
        match.is_completed = True
        match.is_draw = True
        match.winner_team_id = None
        user = _make_user(session, 'tester5')
        enr = _make_enrollment(session, user)
        bra_pick = _make_pick(session, enr, bra, tier=5)  # picked a third party
        session.commit()
        assert points_for_pick_on_match(bra_pick, match) == 0.0


def test_points_for_pick_on_match_third_place_winner_returns_zero(app, session):
    """Bronze-medal match yields 0 per-match (points come via podium bonus).

    Regression: prior to routing through _apply_knockout_points, the helper
    returned KNOCKOUT_POINTS['third_place'] × multiplier (8 × m), drifting
    from per-team scoring where third_place points flow through podium bonus.
    """
    from games.worldcup.services.scoring import points_for_pick_on_match
    with app.app_context():
        cro = _make_team(session, 'CRO', 'Croatia', tier=2, multiplier=2.0)
        mar = _make_team(session, 'MAR', 'Morocco', tier=3, multiplier=3.0)
        match = _make_match(session, 103, 'third_place', cro, mar)
        match.is_completed = True
        match.winner_team_id = cro.id
        user = _make_user(session, 'tester6')
        enr = _make_enrollment(session, user)
        cro_pick = _make_pick(session, enr, cro, tier=2)
        session.commit()
        assert points_for_pick_on_match(cro_pick, match) == 0.0


def test_points_for_pick_on_match_parity_with_compute_team_score_events(app, session):
    """Sum of per-match per-pick points equals multiplier × match-tied ScoreEvents.

    Locks the per-pick helper in lockstep with compute_team_score_events
    (the canonical per-team helper). Only match-tied events count — advancement
    and podium events are not match-attributable. This is the invariant the
    'single source of truth' rule in CLAUDE.md implies for the three helpers.

    Scenario: T5 team wins group (2W/1D), advances as winner, wins R32/R16/QF,
    loses SF, wins bronze. Match-tied total: 2×3 + 1 + 8 + 11 + 15 = 41 base.
    With mult 7.0 → 287. (Advancement +4 and podium +8 are excluded — they are
    not per-match.)
    """
    from games.worldcup.services.scoring import (
        compute_team_score_events,
        points_for_pick_on_match,
    )
    with app.app_context():
        # T5 hero team plus 6 distinct opponents
        nor = _make_team(session, 'NOR', 'Norway', tier=5, multiplier=7.0)
        op1 = _make_team(session, 'OP1', 'Opp1', tier=1, multiplier=1.0)
        op2 = _make_team(session, 'OP2', 'Opp2', tier=1, multiplier=1.0)
        op3 = _make_team(session, 'OP3', 'Opp3', tier=1, multiplier=1.0)
        r32 = _make_team(session, 'R32', 'Opp R32', tier=1, multiplier=1.0)
        r16 = _make_team(session, 'R16', 'Opp R16', tier=1, multiplier=1.0)
        qf = _make_team(session, 'QFO', 'Opp QF', tier=1, multiplier=1.0)
        sf = _make_team(session, 'SFO', 'Opp SF', tier=1, multiplier=1.0)
        bro = _make_team(session, 'BRO', 'Opp 3rd', tier=1, multiplier=1.0)

        # Group stage: 2 wins + 1 draw
        m1 = _make_match(session, 11, 'group', nor, op1, group_letter='I')
        m1.is_completed = True
        m1.winner_team_id = nor.id
        m2 = _make_match(session, 12, 'group', nor, op2, group_letter='I')
        m2.is_completed = True
        m2.winner_team_id = nor.id
        m3 = _make_match(session, 13, 'group', nor, op3, group_letter='I')
        m3.is_completed = True
        m3.is_draw = True
        m3.winner_team_id = None

        # Advancement (match_id=None — excluded from match-tied sum)
        nor.advancement_method = 'group_winner'

        # Knockout chain: win R32, R16, QF; lose SF; win bronze
        m_r32 = _make_match(session, 50, 'R32', nor, r32)
        m_r32.is_completed = True
        m_r32.winner_team_id = nor.id
        m_r16 = _make_match(session, 60, 'R16', nor, r16)
        m_r16.is_completed = True
        m_r16.winner_team_id = nor.id
        m_qf = _make_match(session, 70, 'QF', nor, qf)
        m_qf.is_completed = True
        m_qf.winner_team_id = nor.id
        m_sf = _make_match(session, 80, 'SF', nor, sf)
        m_sf.is_completed = True
        m_sf.winner_team_id = sf.id  # NOR loses
        m_bronze = _make_match(session, 103, 'third_place', nor, bro)
        m_bronze.is_completed = True
        m_bronze.winner_team_id = nor.id
        nor.best_finish = '3rd'  # podium bonus 8 — match_id=None, excluded

        user = _make_user(session, 'parity_tester')
        enr = _make_enrollment(session, user)
        pick = _make_pick(session, enr, nor, tier=5)
        session.commit()

        all_matches = [m1, m2, m3, m_r32, m_r16, m_qf, m_sf, m_bronze]
        per_match_total = sum(points_for_pick_on_match(pick, m) for m in all_matches)

        events = compute_team_score_events(nor)
        match_tied_base = sum(e.base_points for e in events if e.match_id is not None)

        # 2 wins + 1 draw + R32 + R16 + QF = 6 + 1 + 8 + 11 + 15 = 41
        assert match_tied_base == 41.0
        assert per_match_total == match_tied_base * nor.multiplier  # 287.0
