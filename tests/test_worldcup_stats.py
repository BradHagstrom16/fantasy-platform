import os
from unittest.mock import patch

import pytest
from app import create_app
from extensions import db
from games.worldcup.models import WorldCupEnrollment, WorldCupTeam, WorldCupPick
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
def session(app):
    yield db.session


def _make_user(session, username):
    u = User(username=username, email=f'{username}@test.com', password_hash='x')
    session.add(u)
    session.flush()
    return u


def _make_team(session, fifa_code, name, tier, multiplier, group='A'):
    t = WorldCupTeam(
        fifa_code=fifa_code, name=name, display_name=name,
        tier=tier, multiplier=multiplier, confederation='TEST', group_letter=group,
    )
    session.add(t)
    session.flush()
    return t


def _make_enrollment(session, user_id, season_year=2026):
    e = WorldCupEnrollment(user_id=user_id, season_year=season_year, picks_submitted=True)
    session.add(e)
    session.flush()
    return e


def _make_pick(session, enrollment_id, team_id, tier):
    p = WorldCupPick(enrollment_id=enrollment_id, team_id=team_id, tier=tier)
    session.add(p)
    session.flush()
    return p


def test_get_country_stats_basic(session):
    from games.worldcup.services.stats import get_country_stats

    u1 = _make_user(session, 'alice')
    u2 = _make_user(session, 'bob')
    team_a = _make_team(session, 'USA', 'USA', tier=3, multiplier=2.5)
    team_b = _make_team(session, 'MEX', 'Mexico', tier=3, multiplier=2.5)
    e1 = _make_enrollment(session, u1.id)
    e2 = _make_enrollment(session, u2.id)
    _make_pick(session, e1.id, team_a.id, tier=3)
    _make_pick(session, e2.id, team_a.id, tier=3)
    _make_pick(session, e1.id, team_b.id, tier=3)
    session.commit()

    stats, total_players = get_country_stats(2026)

    assert total_players == 2
    by_name = {c['name']: c for c in stats}
    assert by_name['USA']['pick_count'] == 2
    assert abs(by_name['USA']['pick_pct'] - 100.0) < 0.01
    assert by_name['Mexico']['pick_count'] == 1
    assert abs(by_name['Mexico']['pick_pct'] - 50.0) < 0.01


def test_get_country_stats_zero_picks(session):
    from games.worldcup.services.stats import get_country_stats

    _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
    session.commit()

    stats, total_players = get_country_stats(2026)

    assert total_players == 0
    assert stats[0]['pick_count'] == 0
    assert stats[0]['pick_pct'] == 0.0


def test_get_country_stats_dict_shape(session):
    from games.worldcup.services.stats import get_country_stats

    _make_team(session, 'ENG', 'England', tier=1, multiplier=1.0)
    session.commit()

    stats, _ = get_country_stats(2026)
    c = stats[0]

    assert 'name' in c
    assert 'iso_code' in c
    assert 'tier' in c
    assert 'multiplier' in c
    assert 'pick_count' in c
    assert 'pick_pct' in c
    assert 'group_score' in c
    assert 'ko_score' in c
    assert 'total_score' in c
    assert 'is_active' in c


def test_get_tier_stats(session):
    from games.worldcup.services.stats import get_tier_stats

    country_stats = [
        {'tier': 1, 'total_score': 10.0, 'group_score': 5.0, 'ko_score': 5.0,
         'name': 'Spain', 'pick_count': 2, 'pick_pct': 50.0, 'multiplier': 1.0,
         'iso_code': 'es', 'is_active': True},
        {'tier': 1, 'total_score': 20.0, 'group_score': 10.0, 'ko_score': 10.0,
         'name': 'France', 'pick_count': 1, 'pick_pct': 25.0, 'multiplier': 1.0,
         'iso_code': 'fr', 'is_active': False},
        {'tier': 3, 'total_score': 30.0, 'group_score': 15.0, 'ko_score': 15.0,
         'name': 'USA', 'pick_count': 3, 'pick_pct': 75.0, 'multiplier': 2.5,
         'iso_code': 'us', 'is_active': True},
    ]

    tier_stats = get_tier_stats(country_stats)

    assert tier_stats[1]['avg_score'] == 15.0
    assert tier_stats[1]['total_score'] == 30.0
    assert tier_stats[1]['best_country'] == 'France'
    assert tier_stats[1]['best_score'] == 20.0
    assert tier_stats[3]['avg_score'] == 30.0
    assert tier_stats[3]['best_country'] == 'USA'


def test_get_overview_kpis(session):
    from games.worldcup.services.stats import get_overview_kpis

    country_stats = [
        {'tier': 1, 'total_score': 10.0, 'group_score': 5.0, 'ko_score': 5.0,
         'name': 'Spain', 'pick_count': 2, 'pick_pct': 50.0, 'multiplier': 1.0,
         'iso_code': 'es', 'is_active': False},
        {'tier': 3, 'total_score': 50.0, 'group_score': 20.0, 'ko_score': 30.0,
         'name': 'USA', 'pick_count': 3, 'pick_pct': 75.0, 'multiplier': 2.5,
         'iso_code': 'us', 'is_active': True},
    ]

    kpis = get_overview_kpis(country_stats, total_players=4)

    assert kpis['total_players'] == 4
    assert kpis['active_countries'] == 1
    assert kpis['top_country_score'] == 50.0
    assert kpis['top_country_name'] == 'USA'
    assert kpis['total_pts_awarded'] == 60.0


def test_get_tier_combos_returns_pairs(session):
    from games.worldcup.services.stats import get_tier_combos

    u1 = _make_user(session, 'carol')
    u2 = _make_user(session, 'dave')
    u3 = _make_user(session, 'eve')
    t1 = _make_team(session, 'SPA', 'Spain', tier=1, multiplier=1.0)
    t2 = _make_team(session, 'FRA', 'France', tier=1, multiplier=1.0)
    t3 = _make_team(session, 'ARG', 'Argentina', tier=1, multiplier=1.0)
    e1 = _make_enrollment(session, u1.id)
    e2 = _make_enrollment(session, u2.id)
    e3 = _make_enrollment(session, u3.id)
    # Spain+France: players 1 and 2
    _make_pick(session, e1.id, t1.id, tier=1)
    _make_pick(session, e1.id, t2.id, tier=1)
    _make_pick(session, e2.id, t1.id, tier=1)
    _make_pick(session, e2.id, t2.id, tier=1)
    # Player 3 picks Spain+Argentina
    _make_pick(session, e3.id, t1.id, tier=1)
    _make_pick(session, e3.id, t3.id, tier=1)
    session.commit()

    combos = get_tier_combos(2026)

    assert 1 in combos
    assert 3 not in combos  # no tier 3 picks
    top_pair = combos[1][0]
    # Spain+France appear together 2x; Spain+Argentina 1x
    assert top_pair['count'] == 2
    assert {top_pair['team_a'], top_pair['team_b']} == {'Spain', 'France'}
    assert abs(top_pair['pct'] - (2 / 3 * 100)) < 0.1


def test_get_tier_combos_excludes_tier2(session):
    from games.worldcup.services.stats import get_tier_combos

    session.commit()
    combos = get_tier_combos(2026)

    assert 2 not in combos


def test_get_tier_combos_empty_season(session):
    from games.worldcup.services.stats import get_tier_combos

    session.commit()
    combos = get_tier_combos(2026)

    # No picks at all — all tiers either absent or empty
    for tier_data in combos.values():
        assert tier_data == []


@pytest.fixture()
def client(app):
    return app.test_client()


def _make_admin(session, username='wcadmin'):
    u = User(username=username, email=f'{username}@test.com',
             password_hash='x', is_admin=True)
    session.add(u)
    session.flush()
    return u


# Picks lock at 2026-06-11 19:00 UTC; tests run pre-deadline in real time.
_AFTER_KICKOFF = {'WC_FAKE_NOW': '2026-06-15T12:00:00+00:00', 'ENVIRONMENT': 'testing'}


def test_stats_locked_pre_deadline_anonymous(client, session):
    """Pre-kickoff, a non-admin gets the sealed locked state, not the data."""
    _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
    session.commit()

    resp = client.get('/worldcup/stats')
    assert resp.status_code == 200
    # Hero still renders...
    assert b'The Field Office' in resp.data
    # ...but the data surface (pills + JS bridge) is gated off.
    assert b'wc-stats-pills' not in resp.data
    assert b'MY_PICKS' not in resp.data
    # Sealed-state copy is present.
    assert b'Field office sealed' in resp.data


def test_stats_visible_post_deadline(client, session):
    """Once kickoff passes, the full stats surface is public."""
    _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
    session.commit()

    with patch.dict(os.environ, _AFTER_KICKOFF):
        resp = client.get('/worldcup/stats')
    assert resp.status_code == 200
    assert b'wc-stats-pills' in resp.data


def test_stats_visible_admin_pre_deadline(client, session):
    """Platform admins preview the stats surface before kickoff."""
    _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
    admin = _make_admin(session)
    session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin.id)
        sess['_fresh'] = True

    resp = client.get('/worldcup/stats')  # real time = pre-deadline
    assert resp.status_code == 200
    assert b'wc-stats-pills' in resp.data


def test_stats_route_my_picks_unauthenticated(client, session):
    """Post-deadline, unauthenticated users get MY_PICKS = [] — no error."""
    _make_team(session, 'BRA', 'Brazil', tier=1, multiplier=1.0)
    session.commit()

    with patch.dict(os.environ, _AFTER_KICKOFF):
        resp = client.get('/worldcup/stats')
    assert resp.status_code == 200
    assert b'MY_PICKS = []' in resp.data
