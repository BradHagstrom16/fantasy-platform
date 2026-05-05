"""Tests for games.worldcup.services.home_context.build_worldcup_home_context.

This file covers the dispatcher in Task 5; per-builder tests are added in
Tasks 6 (out), 7 (pre), 8 (live), 9 (post).
"""
import os
from datetime import timedelta
from itertools import groupby
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from games.worldcup.constants import (
    SEASON_YEAR, ENTRY_FEE, TOURNAMENT_DEADLINE_UTC,
)
from games.worldcup.services.home_context import (
    build_worldcup_home_context, _context_out, _context_pre, _context_live,
    _context_post,
)
from games.worldcup.services.scoring import points_for_pick_on_match
from tests._worldcup_fixtures import make_user, make_enrollment, seed_full_tournament


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_dispatcher_routes_to_out_builder(app):
    """The 'out' builder is implemented (Task 6), so the dispatcher should
    return its real-shape dict (state='out') rather than a stub marker."""
    ctx = build_worldcup_home_context(user=None, state='out')
    assert ctx['state'] == 'out'
    assert ctx['cta_state'] == 'guest'


def test_dispatcher_routes_to_pre_builder(app):
    """The 'pre' builder is implemented (Task 7), so the dispatcher should
    return its real-shape dict (state='pre') rather than a stub marker."""
    user = make_user()
    make_enrollment(user, picks_submitted=False)
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = build_worldcup_home_context(user=user, state='pre')
    assert ctx['state'] == 'pre'
    assert ctx['branch'] == 'unsubmitted'


def test_dispatcher_raises_on_unknown_state(app):
    with pytest.raises(ValueError, match='unknown worldcup hub state'):
        build_worldcup_home_context(user=None, state='mystery')


# =====================================================================
# Task 6: _context_out builder tests
# =====================================================================

def test_context_out_anonymous_user_is_guest(app):
    ctx = _context_out(user=None)
    assert ctx['state'] == 'out'
    assert ctx['cta_state'] == 'guest'
    assert ctx['is_authenticated'] is False
    assert ctx['display_name'] is None


def test_context_out_authenticated_unenrolled_pre_deadline(app):
    user = make_user()
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_out(user=user)
    assert ctx['cta_state'] == 'unenrolled_pre'
    assert ctx['is_authenticated'] is True
    assert ctx['display_name'] == 'U'


def test_context_out_authenticated_unenrolled_live(app):
    user = make_user()
    db.session.commit()
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_out(user=user)
    assert ctx['cta_state'] == 'unenrolled_live'


def test_context_out_authenticated_unenrolled_post(app):
    user = make_user()
    # Mark final complete to trigger 'post' phase
    from games.worldcup.models import WorldCupMatch
    final = WorldCupMatch(match_number=104, stage='final', is_completed=True)
    db.session.add(final)
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_out(user=user)
    assert ctx['cta_state'] == 'unenrolled_post'


def test_context_out_includes_voice_copy(app):
    ctx = _context_out(user=None)
    assert 'copy' in ctx
    assert ctx['copy']['eyebrow']  # non-empty
    assert ctx['copy']['headline']
    assert ctx['copy']['subhead']


def test_context_out_includes_total_enrolled(app):
    seed_full_tournament(num_enrollments=3)
    ctx = _context_out(user=None)
    assert ctx['total_enrolled'] == 3


def test_context_out_top_3_preview_only_when_live_or_post(app):
    seed_full_tournament(num_enrollments=5)
    user = make_user(email='spectator@test')
    db.session.commit()

    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx_pre = _context_out(user=user)
    assert ctx_pre['top_3_preview'] == []

    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx_live = _context_out(user=user)
    assert len(ctx_live['top_3_preview']) == 3
    # Top-3 ordered by total_score DESC — seed gives 100 / 95 / 90 / 85 / 80
    assert [e.total_score for e in ctx_live['top_3_preview']] == [100.0, 95.0, 90.0]


def test_context_out_includes_entry_fee_and_deadline(app):
    ctx = _context_out(user=None)
    assert ctx['entry_fee'] == ENTRY_FEE
    assert ctx['deadline_ct'] is not None


# =====================================================================
# Task 7: _context_pre builder tests
# =====================================================================

def test_context_pre_unsubmitted_branch(app):
    user = make_user()
    make_enrollment(user, picks_submitted=False)
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    assert ctx['state'] == 'pre'
    assert ctx['branch'] == 'unsubmitted'
    assert ctx['picks_submitted'] is False
    assert ctx['user_picks'] == []


def test_context_pre_submitted_branch_with_picks(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    assert ctx['branch'] == 'submitted'
    assert ctx['picks_submitted'] is True
    assert len(ctx['user_picks']) == 9


def test_context_pre_user_picks_ordered_by_tier_then_team_name(app):
    seed = seed_full_tournament(num_enrollments=1)
    user = seed['users'][0]
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    tiers = [p.team.tier for p in ctx['user_picks']]
    # Tier 1 picks come first, tier 5 last
    assert tiers == sorted(tiers)
    # Within each tier, picks must be sorted by team display_name
    for tier_value, group in groupby(ctx['user_picks'], key=lambda p: p.team.tier):
        names = [p.team.display_name for p in group]
        assert names == sorted(names), (
            f'tier {tier_value} display_name not sorted: {names}'
        )


def test_context_pre_top_3_preview_renders_even_with_zero_scores(app):
    seed = seed_full_tournament(num_enrollments=5)
    # Reset scores to 0 — pre-kickoff state
    for e in seed['enrollments']:
        e.total_score = 0.0
    db.session.commit()
    user = seed['users'][0]
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    assert len(ctx['top_3_preview']) == 3
    assert all(e.total_score == 0.0 for e in ctx['top_3_preview'])


def test_context_pre_includes_voice_copy_per_branch(app):
    user = make_user()
    make_enrollment(user, picks_submitted=False)
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    # Unsubmitted copy should mention "Make your picks"
    assert 'picks' in ctx['copy']['headline'].lower()


def test_context_pre_total_enrolled_count(app):
    seed_full_tournament(num_enrollments=4)
    user = make_user(email='outsider@test')
    make_enrollment(user, picks_submitted=False)
    db.session.commit()
    fake_pre = (TOURNAMENT_DEADLINE_UTC - timedelta(days=1)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_pre}):
        ctx = _context_pre(user=user)
    assert ctx['total_enrolled'] == 5  # 4 + the outsider


# =====================================================================
# Task 8: dispatcher routing to _context_live + builder tests
# =====================================================================

def test_dispatcher_routes_to_live_builder(app):
    """The 'live' builder is implemented (Task 8), so the dispatcher should
    return its real-shape dict (state='live') rather than a stub marker."""
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = build_worldcup_home_context(user=user, state='live')
    assert ctx['state'] == 'live'
    assert 'your_standing' in ctx
    assert 'branch' in ctx


def test_context_live_includes_your_standing(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][0]  # rank 1
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['state'] == 'live'
    assert ctx['your_standing']['rank'] == 1
    assert ctx['your_standing']['of_n'] == 5
    assert ctx['your_standing']['lead_delta_up'] is None  # leader
    assert ctx['your_standing']['lead_delta_down'] == 5.0  # 100 - 95


def test_context_live_branch_for_leader(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][0]  # rank 1
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['branch'] == 'leader'


def test_context_live_branch_for_tail(app):
    # NOTE: plan spec uses num_enrollments=6; seed_full_tournament caps at 5
    # (T5 fixup commit 768324e). With 5 enrollments, rank 5 -> tail per
    # rank_tier(5, 5): 5 > (5*2)//3 = 3 -> True -> 'tail'. users[4] is rank 5.
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][4]  # rank 5 of 5 — bottom third
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['branch'] == 'tail'


def test_context_live_branch_for_chasing(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][1]  # rank 2
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['branch'] == 'chasing'


def test_context_live_top_5_preview(app):
    # seed_full_tournament caps at 5 enrollments; top-5 here equals all 5.
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][0]
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert len(ctx['top_5_preview']) == 5


def test_context_live_user_picks_carry_score_events(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    for pick in ctx['user_picks']:
        # transient attr — list (may be empty if no scoring data seeded)
        assert hasattr(pick, 'score_events')
        assert isinstance(pick.score_events, list)


def test_context_live_recent_matches_has_points_earned(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    # Mark a match completed so it shows up in recent_matches
    from tests._worldcup_fixtures import make_match
    teams = seed['teams']
    make_match(
        match_number=1, home_team=teams[0], away_team=teams[5],
        is_completed=True, home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert len(ctx['recent_matches']) >= 1
    for entry in ctx['recent_matches']:
        # entry is a dict with 'match' + 'points_earned' + 'stage_label'
        assert 'match' in entry
        assert 'points_earned' in entry  # None or float
        assert 'stage_label' in entry
    # Verify the seeded match's points_earned actually flows through (was
    # only checking key presence). teams[0] is in user[0]'s tier-1 roster
    # via seed_full_tournament's offset=0 disjoint slice, so this should
    # be a non-null, non-negative float.
    seeded = next(
        e for e in ctx['recent_matches'] if e['match'].match_number == 1
    )
    assert seeded['points_earned'] is not None
    assert seeded['points_earned'] >= 0


def test_context_live_recent_matches_sums_when_both_teams_are_picks(app):
    """Regression: when BOTH teams in a completed match are user picks (common
    in knockout), points_earned must SUM both picks' contributions — not just
    the home pick's. The previous if/elif silently dropped the away pick."""
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    teams = seed['teams']
    # User[0]'s picks span teams[0,5,10,11,21,22,32,33,34]. Pick teams[0]
    # (tier 1) and teams[5] (tier 2) — both in the user's roster, different
    # tiers. Use a draw so BOTH picks earn positive points (otherwise the
    # loser earns 0 and the test wouldn't actually exercise the bug).
    from tests._worldcup_fixtures import make_match
    match = make_match(
        match_number=1, home_team=teams[0], away_team=teams[5],
        is_completed=True, home_score=1, away_score=1, winner_team=None,
    )
    match.is_draw = True
    db.session.commit()

    picks_by_team = {
        p.team_id: p for p in seed['picks_by_enr'][seed['enrollments'][0].id]
    }
    pick_a = picks_by_team[teams[0].id]
    pick_b = picks_by_team[teams[5].id]
    expected_a = points_for_pick_on_match(pick_a, match)
    expected_b = points_for_pick_on_match(pick_b, match)

    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)

    seeded = next(
        e for e in ctx['recent_matches'] if e['match'].match_number == 1
    )
    # Both picks must contribute positive points — otherwise the test
    # collapses to the single-pick path and wouldn't catch the if/elif bug.
    assert expected_a > 0, (
        f'Test setup invalid: expected_a={expected_a}; need both picks > 0 '
        f'to exercise the both-teams-are-picks summing path.'
    )
    assert expected_b > 0, (
        f'Test setup invalid: expected_b={expected_b}; need both picks > 0 '
        f'to exercise the both-teams-are-picks summing path.'
    )
    assert seeded['points_earned'] == pytest.approx(expected_a + expected_b)


def test_context_live_trend_gate_closed_when_under_seven_days(app):
    seed = seed_full_tournament(num_enrollments=2, seed_snapshots=True, snapshot_days=3)
    user = seed['users'][0]
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['trend']['show_column'] is False


def test_context_live_trend_open_when_seven_days(app):
    seed = seed_full_tournament(num_enrollments=2, seed_snapshots=True, snapshot_days=7)
    user = seed['users'][0]
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert ctx['trend']['show_column'] is True
    # delta = current 100 - latest snapshot (day 0) score
    assert ctx['trend']['delta'] is not None


def test_context_live_stage_label_callable_in_context(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    fake_live = (TOURNAMENT_DEADLINE_UTC + timedelta(days=2)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_live}):
        ctx = _context_live(user=user)
    assert callable(ctx['stage_label'])
    assert ctx['stage_label']('SF') == 'Semifinals'


# =====================================================================
# Task 9: dispatcher routing to _context_post + builder tests
# =====================================================================

def test_dispatcher_routes_to_post_builder(app):
    """The 'post' builder is implemented (Task 9), so the dispatcher should
    return its real-shape dict (state='post') rather than a stub marker."""
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    teams = seed['teams']
    from tests._worldcup_fixtures import make_match
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True, home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = build_worldcup_home_context(user=user, state='post')
    assert ctx['state'] == 'post'
    assert 'champion_team' in ctx


def test_context_post_includes_champion_team(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    teams = seed['teams']
    # Mark final completed with a winner
    from tests._worldcup_fixtures import make_match
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True,
        home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert ctx['state'] == 'post'
    assert ctx['champion_team'] is not None
    assert ctx['champion_team'].id == teams[0].id


def test_context_post_champion_summary_includes_score(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    teams = seed['teams']
    from tests._worldcup_fixtures import make_match
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True,
        home_score=3, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert '3' in ctx['champion_summary'] and '1' in ctx['champion_summary']


def test_context_post_branch_champion_for_rank_one(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][0]
    teams = seed['teams']
    from tests._worldcup_fixtures import make_match
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True, home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert ctx['branch'] == 'champion'


def test_context_post_branch_top_3_for_rank_two(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][1]
    teams = seed['teams']
    from tests._worldcup_fixtures import make_match
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True, home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert ctx['branch'] == 'top_3'


def test_context_post_roster_recap_marks_champion_pick(app):
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    teams = seed['teams']
    # Pick that user's tier-1 team and use it as champion
    user_picks = seed['picks_by_enr'][seed['enrollments'][0].id]
    champion_pick_team = user_picks[0].team   # tier-1 pick
    from tests._worldcup_fixtures import make_match
    other = next(t for t in teams if t.id != champion_pick_team.id)
    make_match(
        match_number=104, stage='final',
        home_team=champion_pick_team, away_team=other,
        is_completed=True,
        home_score=2, away_score=0, winner_team=champion_pick_team,
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    champ_entries = [r for r in ctx['your_roster_recap'] if r['is_champion']]
    assert len(champ_entries) == 1


def test_context_post_handles_missing_final_gracefully(app):
    """If admin error left winner_team_id null on a 'completed' final,
    surface the banner without a defeat summary rather than crashing."""
    seed = seed_full_tournament(num_enrollments=2)
    user = seed['users'][0]
    teams = seed['teams']
    from tests._worldcup_fixtures import make_match
    # No winner_team — defensive guard path
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True, home_score=2, away_score=1,
        # winner_team intentionally omitted -> winner_team_id is None
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert ctx['champion_team'] is None
    assert ctx['champion_summary'] == ''


def test_context_post_top_3_final(app):
    seed = seed_full_tournament(num_enrollments=5)
    user = seed['users'][0]
    teams = seed['teams']
    from tests._worldcup_fixtures import make_match
    make_match(
        match_number=104, stage='final',
        home_team=teams[0], away_team=teams[1],
        is_completed=True, home_score=2, away_score=1, winner_team=teams[0],
    )
    db.session.commit()
    fake_post = (TOURNAMENT_DEADLINE_UTC + timedelta(days=40)).isoformat()
    with patch.dict(os.environ, {'WC_FAKE_NOW': fake_post}):
        ctx = _context_post(user=user)
    assert len(ctx['top_3_final']) == 3
    assert ctx['total_count'] == 5
