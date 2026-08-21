"""
Tests for the World Cup What-If Simulator service (games/worldcup/services/whatif.py)
and its /worldcup/stats/simulate route. Covers: hypothetical knockout point
deltas, feeder-gating via BRACKET_TOPOLOGY, competition-rank tie handling, the
guarantee that nothing is ever written to the database, and the route's
privacy gate + malformed-input handling.
"""
import os
from unittest.mock import patch

import pytest

from extensions import db
from games.worldcup.models import (
    WorldCupEnrollment,
    WorldCupMatch,
    WorldCupPick,
    WorldCupTeam,
)
from models.user import User


@pytest.fixture()
def session(app):
    yield db.session


# Picks lock at 2026-06-11 19:00 UTC (now in the past) — both sides of the
# gate must fake the clock the same way tests/test_worldcup_stats.py does.
_BEFORE_KICKOFF = {'WC_FAKE_NOW': '2026-06-01T12:00:00+00:00', 'ENVIRONMENT': 'testing'}
_AFTER_KICKOFF = {'WC_FAKE_NOW': '2026-06-15T12:00:00+00:00', 'ENVIRONMENT': 'testing'}


def _make_admin(session, username='wcadmin'):
    u = User(username=username, email=f'{username}@test.com', password_hash='x', is_admin=True)
    session.add(u)
    session.flush()
    return u


def _make_team(session, fifa_code, name, tier, multiplier):
    team = WorldCupTeam(
        fifa_code=fifa_code, name=name, display_name=name,
        tier=tier, multiplier=multiplier,
        confederation='TEST', group_letter='A',
    )
    session.add(team)
    session.flush()
    return team


def _make_match(session, match_number, stage, home_team=None, away_team=None):
    match = WorldCupMatch(
        match_number=match_number,
        stage=stage,
        home_team_id=home_team.id if home_team else None,
        away_team_id=away_team.id if away_team else None,
    )
    session.add(match)
    session.flush()
    return match


def _make_user(session, username):
    user = User(username=username, email=f'{username}@test.com')
    user.set_password('test1234')
    session.add(user)
    session.flush()
    return user


def _make_enrollment(session, user, total_score=0.0, season_year=2026):
    enrollment = WorldCupEnrollment(
        user_id=user.id, season_year=season_year,
        picks_submitted=True, total_score=total_score,
    )
    session.add(enrollment)
    session.flush()
    return enrollment


def _make_pick(session, enrollment, team, tier):
    pick = WorldCupPick(enrollment_id=enrollment.id, team_id=team.id, tier=tier)
    session.add(pick)
    session.flush()
    return pick


def _seed_final_four(session):
    """Mirror the real July 2026 bracket shape: 4 Tier-1 semifinalists, SF
    shells resolved (home/away set, not completed), 3rd-place/final shells
    still fully TBD (no home/away yet)."""
    france = _make_team(session, 'FRA', 'France', 1, 1.0)
    spain = _make_team(session, 'ESP', 'Spain', 1, 1.0)
    england = _make_team(session, 'ENG', 'England', 1, 1.0)
    argentina = _make_team(session, 'ARG', 'Argentina', 1, 1.0)
    sf1 = _make_match(session, 101, 'SF', france, spain)
    sf2 = _make_match(session, 102, 'SF', england, argentina)
    third = _make_match(session, 103, 'third_place')
    final = _make_match(session, 104, 'final')
    session.commit()
    return {
        'france': france, 'spain': spain, 'england': england, 'argentina': argentina,
        'sf1': sf1, 'sf2': sf2, 'third': third, 'final': final,
    }


class TestComputeHypotheticalDeltas:
    def test_sf_win_only_awards_sf_points(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import compute_hypothetical_deltas
            teams = _seed_final_four(db.session)

            deltas = compute_hypothetical_deltas({101: teams['france'].id})

            assert deltas == {teams['france'].id: 19.0}

    def test_champion_and_runner_up_totals(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import compute_hypothetical_deltas
            teams = _seed_final_four(db.session)

            deltas = compute_hypothetical_deltas({
                101: teams['france'].id,
                102: teams['england'].id,
                104: teams['france'].id,
            })

            assert deltas[teams['france'].id] == 69.0  # 19 (SF) + 50 (champion)
            assert deltas[teams['england'].id] == 27.0  # 19 (SF) + 8 (runner-up)

    def test_third_place_winner_gets_bonus_loser_gets_nothing(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import compute_hypothetical_deltas
            teams = _seed_final_four(db.session)

            deltas = compute_hypothetical_deltas({
                101: teams['france'].id,
                102: teams['england'].id,
                103: teams['spain'].id,
            })

            assert deltas[teams['spain'].id] == 8.0
            assert teams['argentina'].id not in deltas

    def test_downstream_match_ignored_until_feeders_decided(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import compute_hypothetical_deltas
            teams = _seed_final_four(db.session)

            # Picking a final winner before its feeders (101/102) are decided
            # can't resolve to a real participant yet, so it's a no-op.
            deltas = compute_hypothetical_deltas({104: teams['france'].id})

            assert deltas == {}

    def test_pick_for_team_not_in_that_match_is_ignored(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import compute_hypothetical_deltas
            teams = _seed_final_four(db.session)

            # Argentina isn't a candidate for match 101 (France vs Spain).
            deltas = compute_hypothetical_deltas({101: teams['argentina'].id})

            assert deltas == {}

    def test_multiplier_applies_for_non_tier_one_teams(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import compute_hypothetical_deltas
            morocco = _make_team(db.session, 'MAR', 'Morocco', 3, 2.5)
            portugal = _make_team(db.session, 'POR', 'Portugal', 1, 1.0)
            _make_match(db.session, 101, 'SF', morocco, portugal)
            db.session.commit()

            deltas = compute_hypothetical_deltas({101: morocco.id})

            assert deltas == {morocco.id: 19.0 * 2.5}


class TestBracketStateForUi:
    def test_reports_known_sides_and_tbd_sides(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import bracket_state_for_ui
            teams = _seed_final_four(db.session)

            state = bracket_state_for_ui()
            by_number = {s['match_number']: s for s in state}

            assert by_number[101]['home']['team_id'] == teams['france'].id
            assert by_number[101]['home']['iso_code'] == teams['france'].iso_code
            assert by_number[101]['away']['team_id'] == teams['spain'].id
            assert by_number[103]['home'] is None
            assert by_number[103]['away'] is None
            assert by_number[104]['home'] is None
            assert by_number[104]['away'] is None

    def test_tbd_sides_carry_feeder_pointers_known_sides_do_not(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import bracket_state_for_ui
            _seed_final_four(db.session)

            state = bracket_state_for_ui()
            by_number = {s['match_number']: s for s in state}

            # 101/102 are already fully resolved (real QF winners) — no feeder
            # pointer needed since the client already has the concrete team.
            assert by_number[101]['home_feeder'] is None
            assert by_number[101]['away_feeder'] is None
            # 104 (final) is fed by the winners of 101 and 102.
            assert by_number[104]['home_feeder'] == {'kind': 'winner', 'match_number': 101}
            assert by_number[104]['away_feeder'] == {'kind': 'winner', 'match_number': 102}
            # 103 (third place) is fed by the losers of 101 and 102.
            assert by_number[103]['home_feeder'] == {'kind': 'loser', 'match_number': 101}
            assert by_number[103]['away_feeder'] == {'kind': 'loser', 'match_number': 102}


class TestCompletedFeederNotYetAutofilled:
    """process_match_result() (the admin manual-entry path) doesn't call
    run_bracket_autofill() synchronously — only the sync cron/CLI does — so a
    feeder can be is_completed=True with a real winner while the downstream
    shell's own home_team_id/away_team_id are still unset. The resolver must
    still read the real result during that window, not just what's already
    baked into the incomplete matches themselves."""

    def _seed_completed_sf1(self, session):
        france = _make_team(session, 'FRA', 'France', 1, 1.0)
        spain = _make_team(session, 'ESP', 'Spain', 1, 1.0)
        england = _make_team(session, 'ENG', 'England', 1, 1.0)
        argentina = _make_team(session, 'ARG', 'Argentina', 1, 1.0)
        sf1 = WorldCupMatch(
            match_number=101, stage='SF',
            home_team_id=france.id, away_team_id=spain.id,
            is_completed=True, winner_team_id=france.id,
        )
        session.add(sf1)
        sf2 = _make_match(session, 102, 'SF', england, argentina)
        third = _make_match(session, 103, 'third_place')  # not yet autofilled
        final = _make_match(session, 104, 'final')          # not yet autofilled
        session.commit()
        return {
            'france': france, 'spain': spain, 'england': england,
            'argentina': argentina, 'sf1': sf1, 'sf2': sf2,
            'third': third, 'final': final,
        }

    def test_bracket_state_resolves_final_side_from_completed_sf(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import bracket_state_for_ui
            teams = self._seed_completed_sf1(db.session)

            state = bracket_state_for_ui()
            by_number = {s['match_number']: s for s in state}

            # SF1 is completed — it's a real result now, not a pick, so it's
            # absent from the returned (still-incomplete) rows entirely.
            assert 101 not in by_number
            # But the Final's home side must still resolve to France (SF1's
            # real winner), not stay TBD just because 101 isn't in the list.
            assert by_number[104]['home']['team_id'] == teams['france'].id
            assert by_number[104]['home_feeder'] is None  # concretely known now
            # Same for the third-place match's home side: Spain (SF1's real
            # loser) resolves concretely too, not just the final's winner side.
            assert by_number[103]['home']['team_id'] == teams['spain'].id
            assert by_number[103]['home_feeder'] is None
            # The third-place match's away side is still TBD (SF2 undecided).
            assert by_number[103]['away'] is None

    def test_compute_deltas_resolves_final_winner_via_completed_sf(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import compute_hypothetical_deltas
            teams = self._seed_completed_sf1(db.session)

            # England wins SF2 (hypothetical); France (real SF1 winner) then
            # wins the final against England, and Spain (real SF1 loser)
            # beats Argentina (hypothetical SF2 loser) for third place.
            deltas = compute_hypothetical_deltas({
                102: teams['england'].id,
                103: teams['spain'].id,
                104: teams['france'].id,
            })

            assert deltas[teams['france'].id] == 50.0  # champion bonus only
            # (France's SF-stage points already live in its real total_score,
            # not in this delta — only 104's champion bonus is new here.)
            assert deltas[teams['england'].id] == 19.0 + 8.0  # SF + runner-up
            assert deltas[teams['spain'].id] == 8.0  # third-place bonus
            assert teams['argentina'].id not in deltas  # third-place loser

    def test_pick_ignored_when_only_one_side_of_the_match_is_resolved(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import compute_hypothetical_deltas
            teams = self._seed_completed_sf1(db.session)

            # Spain (SF1's real loser) is a known candidate for the
            # third-place match, but SF2 hasn't been decided (no pick, no
            # completion) so the OTHER side is still unresolved. Picking
            # Spain here must not score — the match itself isn't real yet.
            deltas = compute_hypothetical_deltas({103: teams['spain'].id})

            assert deltas == {}


class TestSimulateLeaderboard:
    def test_only_affected_enrollments_change_score(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import simulate_leaderboard
            teams = _seed_final_four(db.session)

            u1 = _make_user(db.session, 'p1')
            u2 = _make_user(db.session, 'p2')
            u3 = _make_user(db.session, 'p3')
            e1 = _make_enrollment(db.session, u1, total_score=100.0)
            e2 = _make_enrollment(db.session, u2, total_score=100.0)
            e3 = _make_enrollment(db.session, u3, total_score=50.0)
            _make_pick(db.session, e1, teams['france'], tier=1)
            _make_pick(db.session, e2, teams['spain'], tier=1)
            _make_pick(db.session, e3, teams['argentina'], tier=1)
            db.session.commit()

            result = simulate_leaderboard({101: teams['france'].id})

            by_id = {r['enrollment_id']: r for r in result['ranked']}
            assert by_id[e1.id]['score'] == 119.0  # 100 + 19 (owns the SF winner)
            assert by_id[e2.id]['score'] == 100.0  # unaffected (owns the SF loser)
            assert by_id[e3.id]['score'] == 50.0   # unaffected (team not in this match)
            assert by_id[e1.id]['rank'] == 1
            assert by_id[e2.id]['rank'] == 2
            assert by_id[e3.id]['rank'] == 3
            assert result['total_players'] == 3

    def test_tied_scores_share_competition_rank(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import simulate_leaderboard
            _seed_final_four(db.session)

            u1 = _make_user(db.session, 'p1')
            u2 = _make_user(db.session, 'p2')
            u3 = _make_user(db.session, 'p3')
            e1 = _make_enrollment(db.session, u1, total_score=100.0)
            e2 = _make_enrollment(db.session, u2, total_score=100.0)
            e3 = _make_enrollment(db.session, u3, total_score=90.0)
            db.session.commit()

            result = simulate_leaderboard({})

            ranks = {r['enrollment_id']: (r['rank'], r['tied']) for r in result['ranked']}
            assert ranks[e1.id] == (1, True)
            assert ranks[e2.id] == (1, True)
            assert ranks[e3.id] == (3, False)  # competition rank jumps by tie size


class TestNoPersistence:
    def test_simulate_leaderboard_never_writes_to_db(self, app):
        with app.app_context():
            from games.worldcup.services.whatif import simulate_leaderboard
            teams = _seed_final_four(db.session)
            user = _make_user(db.session, 'p1')
            enrollment = _make_enrollment(db.session, user, total_score=100.0)
            _make_pick(db.session, enrollment, teams['france'], tier=1)
            db.session.commit()

            simulate_leaderboard({
                101: teams['france'].id, 102: teams['england'].id,
                104: teams['france'].id, 103: teams['spain'].id,
            })

            assert not db.session.dirty
            assert not db.session.new

            refreshed_match = WorldCupMatch.query.filter_by(match_number=104).first()
            assert refreshed_match.is_completed is False
            assert refreshed_match.winner_team_id is None
            refreshed_enrollment = db.session.get(WorldCupEnrollment, enrollment.id)
            assert refreshed_enrollment.total_score == 100.0


class TestSimulateRoute:
    """GET /worldcup/stats/simulate — public JSON endpoint, gated like stats()."""

    def test_locked_pre_deadline_for_anonymous(self, client, session):
        _seed_final_four(session)
        session.commit()

        with patch.dict(os.environ, _BEFORE_KICKOFF):
            resp = client.get('/worldcup/stats/simulate')
        assert resp.status_code == 403

    def test_admin_can_preview_pre_deadline(self, client, session):
        _seed_final_four(session)
        admin = _make_admin(session)
        session.commit()

        with client.session_transaction() as sess:
            sess['_user_id'] = admin.get_id()
            sess['_fresh'] = True

        with patch.dict(os.environ, _BEFORE_KICKOFF):
            resp = client.get('/worldcup/stats/simulate')
        assert resp.status_code == 200

    def test_returns_ranked_json_post_deadline(self, client, session):
        teams = _seed_final_four(session)
        user = _make_user(session, 'p1')
        enrollment = _make_enrollment(session, user, total_score=100.0)
        _make_pick(session, enrollment, teams['france'], tier=1)
        session.commit()

        with patch.dict(os.environ, _AFTER_KICKOFF):
            resp = client.get(f'/worldcup/stats/simulate?pick=101:{teams["france"].id}')
        assert resp.status_code == 200
        data = resp.get_json()
        row = next(r for r in data['ranked'] if r['enrollment_id'] == enrollment.id)
        assert row['score'] == 119.0
        assert data['total_players'] == 1

    def test_malformed_pick_param_is_ignored_not_a_400(self, client, session):
        _seed_final_four(session)
        session.commit()

        with patch.dict(os.environ, _AFTER_KICKOFF):
            resp = client.get('/worldcup/stats/simulate?pick=not-a-real-pick&pick=101:999999')
        assert resp.status_code == 200
        assert resp.get_json()['ranked'] == []

    def test_marks_is_you_for_the_authenticated_owner(self, client, session):
        _seed_final_four(session)
        owner = _make_user(session, 'owner')
        other = _make_user(session, 'other')
        mine = _make_enrollment(session, owner, total_score=10.0)
        theirs = _make_enrollment(session, other, total_score=10.0)
        session.commit()

        with client.session_transaction() as sess:
            sess['_user_id'] = owner.get_id()
            sess['_fresh'] = True

        with patch.dict(os.environ, _AFTER_KICKOFF):
            resp = client.get('/worldcup/stats/simulate')
        data = resp.get_json()
        by_id = {r['enrollment_id']: r for r in data['ranked']}
        assert by_id[mine.id]['is_you'] is True
        assert by_id[theirs.id]['is_you'] is False

    def test_route_never_writes_to_db(self, client, session):
        teams = _seed_final_four(session)
        user = _make_user(session, 'p1')
        enrollment = _make_enrollment(session, user, total_score=100.0)
        _make_pick(session, enrollment, teams['france'], tier=1)
        session.commit()

        with patch.dict(os.environ, _AFTER_KICKOFF):
            client.get(
                f'/worldcup/stats/simulate?pick=101:{teams["france"].id}'
                f'&pick=102:{teams["england"].id}&pick=104:{teams["france"].id}'
            )

        refreshed_match = WorldCupMatch.query.filter_by(match_number=104).first()
        assert refreshed_match.is_completed is False
        refreshed_enrollment = db.session.get(WorldCupEnrollment, enrollment.id)
        assert refreshed_enrollment.total_score == 100.0
