"""Tests for the public /worldcup/team/<int:team_id> route."""
import re
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import (
    WorldCupEnrollment,
    WorldCupMatch,
    WorldCupPick,
    WorldCupTeam,
)
from models.user import User

PAST_DEADLINE = datetime(2000, 1, 1, tzinfo=UTC)
FUTURE_DEADLINE = datetime(2099, 1, 1, tzinfo=UTC)


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


def _seed_team(app, fifa='USA'):
    with app.app_context():
        t = WorldCupTeam(
            fifa_code=fifa, name=fifa, display_name=fifa,
            tier=1, multiplier=1.0, confederation='CONCACAF',
            group_letter='A',
        )
        db.session.add(t)
        db.session.commit()
        return t.id


def _seed_owner_with_pick(app, team_id, username='owner'):
    with app.app_context():
        u = User(username=username, email=f'{username}@test.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.flush()
        e = WorldCupEnrollment(user_id=u.id, season_year=SEASON_YEAR, picks_submitted=True)
        db.session.add(e)
        db.session.flush()
        p = WorldCupPick(enrollment_id=e.id, team_id=team_id, tier=1)
        db.session.add(p)
        db.session.commit()
        return u.id


def test_team_detail_surfaces_podium_and_advancement_bonuses(client, app):
    """F2: the +50 champion podium bonus and the advancement milestone are
    non-match scoring events (match_id=None) that the match log skips. They
    must be itemized somewhere on the page (with multiplier applied), or the
    single largest scoring event in the game is invisible.

    No final match is seeded here, so this now locks the FALLBACK path: when
    the podium bonus's deciding match is missing from the log, it must remain
    a 'Beyond the matches' line item. (With the match present, it attributes
    to that row instead — see test_team_detail_final_row_attributes_champion_points.)"""
    with app.app_context():
        t = WorldCupTeam(
            fifa_code='AUS', name='Australia', display_name='Australia',
            tier=5, multiplier=7.0, confederation='AFC', group_letter='D',
            best_finish='champion', advancement_method='group_winner',
        )
        db.session.add(t)
        db.session.commit()
        tid = t.id
    body = client.get(f'/worldcup/team/{tid}').data.decode()
    assert 'Group winner' in body   # advancement milestone label, surfaced
    assert '28.0' in body           # advancement: 4 base × 7 multiplier
    assert '350.0' in body          # champion podium: 50 base × 7 multiplier


def test_team_detail_returns_200_for_valid_team(client, app):
    team_id = _seed_team(app)
    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200


def test_team_detail_returns_404_for_invalid_team(client):
    resp = client.get('/worldcup/team/99999')
    assert resp.status_code == 404


def test_team_detail_public_no_auth_required(client, app):
    """Anonymous users see the page (matches leaderboard/stats access policy)."""
    team_id = _seed_team(app)
    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'USA' in resp.data


def test_team_detail_renders_team_name_and_fifa_code(client, app):
    team_id = _seed_team(app, fifa='ENG')
    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'ENG' in resp.data


def test_team_detail_ownership_hidden_pre_deadline(client, app):
    """Pre-deadline + non-owner: no ownership ribbon, no count, no picker names."""
    team_id = _seed_team(app)
    _seed_owner_with_pick(app, team_id, username='alice')
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    # No ownership ribbon block content
    assert b'You Own This Nation' not in resp.data
    assert b'Roster ownership' not in resp.data
    assert b'Who Picked This' not in resp.data
    # Specifically: 'alice' must not appear in the response
    assert b'alice' not in resp.data
    # Path-to-crown section still renders (it's not gated by deadline)
    assert b'Path to the Crown' in resp.data or b'Out of the running' in resp.data


def test_team_detail_ownership_visible_post_deadline(client, app):
    """Post-deadline + non-owner: ribbon shows count/percent; picker list renders."""
    team_id = _seed_team(app)
    _seed_owner_with_pick(app, team_id, username='alice')
    _seed_owner_with_pick(app, team_id, username='bob')
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'Roster ownership' in resp.data
    assert b'Who Picked This' in resp.data
    assert b'alice' in resp.data
    assert b'bob' in resp.data


def test_team_detail_zero_ownership_ribbon_post_deadline(client, app):
    """Post-deadline + nobody picked the team: ribbon still renders with 0 / 0.0%.
    Documented intent (template branch comment): post-deadline shows count/percent
    regardless of count, so unpicked teams display '0 / 0.0% of Club'."""
    team_id = _seed_team(app, fifa='ZIM')
    # No picks seeded — ownership.count will be 0.
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'Roster ownership' in resp.data
    # Count of 0 and 0.0% both rendered in the ribbon-stat block
    assert b'>0<' in resp.data  # count "0" inside the ownership-ribbon-count div
    assert b'0.0% of Club' in resp.data


def test_team_detail_user_owns_ribbon(client, app):
    """Authenticated user with a pick on this team sees red 'You Own This Nation' ribbon."""
    team_id = _seed_team(app)
    user_id = _seed_owner_with_pick(app, team_id, username='alice')
    with app.app_context():
        auth_id = db.session.get(User, user_id).auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', PAST_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'You Own This Nation' in resp.data


def test_team_detail_user_owns_ribbon_pre_deadline(client, app):
    """Even pre-deadline, the owner sees their own 'You Own This Nation' ribbon
    (no privacy concern — it's their own pick)."""
    team_id = _seed_team(app)
    user_id = _seed_owner_with_pick(app, team_id, username='alice')
    with app.app_context():
        auth_id = db.session.get(User, user_id).auth_id
    with client.session_transaction() as sess:
        sess['_user_id'] = auth_id
        sess['_fresh'] = True
    with patch('games.worldcup.routes.TOURNAMENT_DEADLINE_UTC', FUTURE_DEADLINE):
        resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'You Own This Nation' in resp.data
    # But ownership counts/names of OTHERS still hidden pre-deadline
    assert b'Who Picked This' not in resp.data


def test_team_detail_match_log_includes_all_team_fixtures(client, app):
    """Both home and away fixtures appear in the match log."""
    team_id = _seed_team(app, fifa='USA')
    other_id = _seed_team(app, fifa='ENG')
    with app.app_context():
        # Match where USA is home, vs ENG
        m1 = WorldCupMatch(
            match_number=1, stage='group', group_letter='A',
            home_team_id=team_id, away_team_id=other_id,
            home_score=2, away_score=1, is_completed=True,
        )
        # Match where USA is away, vs ENG
        m2 = WorldCupMatch(
            match_number=2, stage='group', group_letter='A',
            home_team_id=other_id, away_team_id=team_id,
            home_score=0, away_score=3, is_completed=True,
        )
        db.session.add_all([m1, m2])
        db.session.commit()

    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    # Both fixture lines should be visible (each has the opponent's FIFA code)
    # Two ENG fixture rows means 'ENG' appears at least twice in the response.
    assert resp.data.count(b'ENG') >= 2


def test_team_detail_score_events_match_canonical_helper(client, app):
    """Sum of displayed per-match points equals compute_team_score_events total — SSoT parity."""
    from games.worldcup.services.scoring import compute_team_score_events

    team_id = _seed_team(app, fifa='USA')
    with app.app_context():
        team = db.session.get(WorldCupTeam, team_id)
        assert team is not None
        # Simulate a completed group win for USA
        opponent = WorldCupTeam(
            fifa_code='ENG', name='ENG', display_name='ENG',
            tier=1, multiplier=1.0, confederation='UEFA',
            group_letter='A',
        )
        db.session.add(opponent)
        db.session.flush()
        m = WorldCupMatch(
            match_number=10, stage='group', group_letter='A',
            home_team_id=team.id, away_team_id=opponent.id,
            home_score=2, away_score=0, is_completed=True,
            winner_team_id=team.id, is_draw=False,
        )
        db.session.add(m)
        # Update USA group_wins to reflect the result for compute_team_score_events
        team.group_wins = 1
        team.base_points = 3.0  # GROUP_WIN
        db.session.commit()

        canonical_total = sum(ev.base_points for ev in compute_team_score_events(team))

    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    # Anchor the assertion to the hero's "Base × Multiplier" derivation
    # microline (S2.3.1 hero re-shape moved Base out of a 4-tile stat strip
    # into a Newsreader derivation line). An unscoped substring check could
    # pass if the same numeric appeared elsewhere (e.g., a fixture-points
    # cell) even after a Base-binding regression.
    base_str = f"{canonical_total:.1f}".encode()
    pattern = (
        rb'<p class="team-hero-derivation mb-0">\s*'
        rb'Base\s*<strong class="wc-numeral">' + re.escape(base_str) + rb'</strong>'
    )
    assert re.search(pattern, resp.data), (
        f'expected hero derivation line to bind canonical Base {base_str!r}'
    )


def test_team_detail_fixture_pts_apply_multiplier(client, app):
    """Per-match fixture-pts column displays base × team.multiplier so the unit
    matches the hero's 'Scored' stat. Without the multiplier, a tier-5 team's
    group win would show '+3.0' in the match log while the hero reports
    '+21.0' Scored — confusing and easy to misread as undercounting."""
    from games.worldcup.constants import GROUP_WIN

    with app.app_context():
        # Tier 5 team (multiplier 7.0) — pick a multiplier that makes
        # base vs multiplied unambiguously distinguishable.
        team = WorldCupTeam(
            fifa_code='SAU', name='SAU', display_name='SAU',
            tier=5, multiplier=7.0, confederation='AFC',
            group_letter='A',
        )
        opponent = WorldCupTeam(
            fifa_code='AUS', name='AUS', display_name='AUS',
            tier=4, multiplier=4.0, confederation='AFC',
            group_letter='A',
        )
        db.session.add_all([team, opponent])
        db.session.flush()
        m = WorldCupMatch(
            match_number=42, stage='group', group_letter='A',
            home_team_id=team.id, away_team_id=opponent.id,
            home_score=1, away_score=0, is_completed=True,
            winner_team_id=team.id, is_draw=False,
        )
        db.session.add(m)
        team.group_wins = 1
        team.base_points = float(GROUP_WIN)  # base = 3
        db.session.commit()
        team_id = team.id

    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    # Multiplied points = 3 × 7 = 21.0. Base (3.0) must NOT appear in the
    # fixture-pts cell — only the multiplied display value.
    pattern = (
        rb'<div class="fixture-pts wc-numeral[^"]*">\s*\+21\.0\s*</div>'
    )
    assert re.search(pattern, resp.data), (
        'fixture-pts cell expected to render multiplied points (+21.0) for '
        'a tier-5 group win, not raw base points'
    )


def test_team_detail_hero_has_no_invisible_multiplier_chip(client, app):
    """The hero must not render a .wc-multiplier-chip. The chip's canonical
    color resolved to dark ink (var(--text-primary)) on the navy hero
    substrate (~1.01:1 contrast — invisible; the WC P0 reported 2026-06-01).
    The multiplier now reads only through the Newsreader derivation line,
    which has its own light-on-navy color. Lock the chip out of this hero so
    a future edit can't reintroduce the unreadable box."""
    with app.app_context():
        team = WorldCupTeam(
            fifa_code='NED', name='NED', display_name='NED',
            tier=5, multiplier=7.0, confederation='UEFA',
            group_letter='B',
        )
        db.session.add(team)
        db.session.commit()
        team_id = team.id

    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    assert b'wc-multiplier-chip' not in resp.data, (
        'team_detail hero must not render the multiplier chip (dark-ink chip '
        'on the navy hero is invisible); the derivation line carries the value'
    )


def test_team_detail_hero_multiplier_uses_g_format(client, app):
    """Hero derivation renders an integer multiplier without a trailing .0
    (house format via "%g"; raw {{ team.multiplier }} renders '7.0'). A 1.5
    tier still keeps its decimal under %g."""
    with app.app_context():
        team = WorldCupTeam(
            fifa_code='ARG', name='ARG', display_name='ARG',
            tier=5, multiplier=7.0, confederation='CONMEBOL',
            group_letter='C',
        )
        db.session.add(team)
        db.session.commit()
        team_id = team.id

    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    pattern = (
        rb'Multiplier\s*<strong class="wc-numeral">7</strong>'
    )
    assert re.search(pattern, resp.data), (
        'hero derivation multiplier expected to render "7" (via %g), not "7.0"'
    )


def _seed_champion(app, fifa='AUS', multiplier=7.0, base=108.0, multiplied=756.0):
    with app.app_context():
        t = WorldCupTeam(
            fifa_code=fifa, name=fifa, display_name=fifa,
            tier=5, multiplier=multiplier, confederation='AFC',
            group_letter='D', base_points=base, multiplied_points=multiplied,
            best_finish='champion', advancement_method='group_winner',
        )
        db.session.add(t)
        db.session.commit()
        return t.id


def test_team_detail_champion_path_uses_crowned_heading_not_projected(client, app):
    """Path-to-the-Crown terminal state: a champion has already won out, so
    the live 'Projected ceiling' framing is counterfactual. The heading reads
    past-tense 'Champion ·' instead."""
    team_id = _seed_champion(app)
    body = client.get(f'/worldcup/team/{team_id}').data.decode()
    assert 'Champion ·' in body
    assert 'Projected ceiling' not in body


def test_team_detail_champion_path_drops_wins_out_fineprint(client, app):
    """'If AUS wins out from here…' is counterfactual once AUS is champion —
    there is no 'from here'. The champion register drops it."""
    team_id = _seed_champion(app)
    body = client.get(f'/worldcup/team/{team_id}').data.decode()
    assert 'wins out from here' not in body


def test_team_detail_champion_final_segment_renders_trophy(client, app):
    """The Final segment of a champion's path gets a ceremonial trophy mark,
    breaking the six-identical-checkmarks monotony of a completed run."""
    team_id = _seed_champion(app)
    body = client.get(f'/worldcup/team/{team_id}').data.decode()
    assert 'bi-trophy-fill' in body
    assert 'path-segment-champion' in body


def test_team_detail_alive_team_keeps_projected_ceiling(client, app):
    """A team still alive (not champion, not eliminated) keeps the projecting
    register — the live framing is correct mid-tournament."""
    with app.app_context():
        t = WorldCupTeam(
            fifa_code='BRA', name='BRA', display_name='BRA',
            tier=2, multiplier=1.5, confederation='CONMEBOL',
            group_letter='E', base_points=12.0, multiplied_points=18.0,
            best_finish=None, advancement_method='group_winner',
        )
        db.session.add(t)
        db.session.commit()
        team_id = t.id
    body = client.get(f'/worldcup/team/{team_id}').data.decode()
    assert 'Projected ceiling' in body
    assert 'wins out from here' in body
    assert 'Champion ·' not in body


def test_team_detail_final_row_attributes_champion_points(client, app):
    """The champion's final-match row shows the +50 podium bonus (base ×
    multiplier), not '+0.0' — and the bonus does NOT double-display in
    'Beyond the matches' (with no advancement milestone, that whole section
    disappears because the podium event moved onto its deciding match)."""
    with app.app_context():
        team = WorldCupTeam(
            fifa_code='ESP', name='ESP', display_name='ESP',
            tier=1, multiplier=1.0, confederation='UEFA',
            group_letter='A', best_finish='champion', base_points=50.0,
        )
        opponent = WorldCupTeam(
            fifa_code='ARG', name='ARG', display_name='ARG',
            tier=1, multiplier=1.0, confederation='CONMEBOL',
            group_letter='B',
        )
        db.session.add_all([team, opponent])
        db.session.flush()
        m = WorldCupMatch(
            match_number=104, stage='final',
            home_team_id=team.id, away_team_id=opponent.id,
            home_score=1, away_score=0, is_completed=True,
            winner_team_id=team.id, is_draw=False,
        )
        db.session.add(m)
        db.session.commit()
        team_id = team.id

    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    pattern = rb'<div class="fixture-pts wc-numeral[^"]*">\s*\+50\.0\s*</div>'
    assert re.search(pattern, resp.data), (
        'final-row fixture-pts expected to carry the champion bonus (+50.0), '
        'not render the podium match as zero'
    )
    assert b'Beyond the matches' not in resp.data, (
        'podium bonus must not double-display as a separate bonus line item'
    )


def test_team_detail_bronze_row_attributes_third_place_points(client, app):
    """Third-place winner (tier 3, x2.5): the bronze-match row shows +20.0
    (8 base x 2.5) while 'Beyond the matches' keeps the advancement milestone
    but drops the podium line."""
    with app.app_context():
        team = WorldCupTeam(
            fifa_code='ENG', name='ENG', display_name='ENG',
            tier=3, multiplier=2.5, confederation='UEFA',
            group_letter='L', best_finish='3rd', base_points=12.0,
            advancement_method='group_winner',
        )
        opponent = WorldCupTeam(
            fifa_code='FRA', name='FRA', display_name='FRA',
            tier=1, multiplier=1.0, confederation='UEFA',
            group_letter='K',
        )
        db.session.add_all([team, opponent])
        db.session.flush()
        m = WorldCupMatch(
            match_number=103, stage='third_place',
            home_team_id=opponent.id, away_team_id=team.id,
            home_score=4, away_score=6, is_completed=True,
            winner_team_id=team.id, is_draw=False,
        )
        db.session.add(m)
        db.session.commit()
        team_id = team.id

    resp = client.get(f'/worldcup/team/{team_id}')
    assert resp.status_code == 200
    pattern = rb'<div class="fixture-pts wc-numeral[^"]*">\s*\+20\.0\s*</div>'
    assert re.search(pattern, resp.data), (
        'bronze-row fixture-pts expected to carry the third-place bonus '
        '(+20.0 = 8 base x 2.5)'
    )
    assert b'Beyond the matches' in resp.data
    assert b'Group winner' in resp.data
    # The podium ScoreEvent label ('Third place') must not render as a bonus
    # row eyebrow — matching on the row markup, not the bare string, because
    # the journey tracker legitimately says 'Third place' elsewhere.
    assert b'<span class="wc-eyebrow">Third place</span>' not in resp.data, (
        'podium bonus must not double-display as a separate bonus line item'
    )


def test_team_detail_podium_tracker_third_place(client, app):
    """A bronze medalist's journey tracker reads as a podium finish, not the
    loss-framed 'Out of the running / Eliminated · Semifinals' (the team WON
    its last match of the tournament)."""
    with app.app_context():
        t = WorldCupTeam(
            fifa_code='ENG', name='ENG', display_name='ENG',
            tier=1, multiplier=1.0, confederation='UEFA',
            group_letter='L', best_finish='3rd',
        )
        db.session.add(t)
        db.session.commit()
        team_id = t.id
    body = client.get(f'/worldcup/team/{team_id}').data.decode()
    # Scope to the path-tracker section so unrelated future copy elsewhere on
    # the page can't trip the negative assertions.
    tracker = re.search(r'<section class="team-path.*?</section>', body, re.S)
    assert tracker, 'path-tracker section missing'
    tracker = tracker.group(0)
    assert 'On the podium' in tracker
    assert 'Third place · Won the bronze final' in tracker
    assert 'Out of the running' not in tracker
    assert 'Eliminated ·' not in tracker


def test_team_detail_podium_tracker_runner_up(client, app):
    """The beaten finalist reads as runners-up, not a bare elimination."""
    with app.app_context():
        t = WorldCupTeam(
            fifa_code='ARG', name='ARG', display_name='ARG',
            tier=1, multiplier=1.0, confederation='CONMEBOL',
            group_letter='B', best_finish='runner_up',
        )
        db.session.add(t)
        db.session.commit()
        team_id = t.id
    body = client.get(f'/worldcup/team/{team_id}').data.decode()
    tracker = re.search(r'<section class="team-path.*?</section>', body, re.S)
    assert tracker, 'path-tracker section missing'
    tracker = tracker.group(0)
    assert 'On the podium' in tracker
    assert 'Runners-up · Lost the Final' in tracker
    assert 'Out of the running' not in tracker
