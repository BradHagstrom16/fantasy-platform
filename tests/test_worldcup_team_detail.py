"""Tests for the public /worldcup/team/<int:team_id> route."""
import re
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.constants import SEASON_YEAR
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupPick, WorldCupMatch,
)


PAST_DEADLINE = datetime(2000, 1, 1, tzinfo=timezone.utc)
FUTURE_DEADLINE = datetime(2099, 1, 1, tzinfo=timezone.utc)


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
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
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
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
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
