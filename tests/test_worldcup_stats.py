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
    with app.app_context():
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
    assert 'flag_emoji' in c
    assert 'tier' in c
    assert 'multiplier' in c
    assert 'pick_count' in c
    assert 'pick_pct' in c
    assert 'group_score' in c
    assert 'ko_score' in c
    assert 'total_score' in c
    assert 'is_active' in c
