"""The eligible-team pool on the CFB room landing (/cfb/).

Covers the "which teams can I pick from?" surface added to the standings
page: the pure grouping helper (games/cfb/services/game_logic.
pool_teams_by_conference) and its render in games/cfb/templates/cfb/
index.html, including the viewer-aware "used team" strike-through.

Conference grouping is by constants.TEAM_CONFERENCES, so the seeded team
NAMES must be real short names (Alabama -> SEC, etc.).
"""
import pytest

from app import create_app
from extensions import db
from games.cfb.services.game_logic import pool_teams_by_conference
from tests._cfb_fixtures import (
    make_enrollment,
    make_pick,
    make_team,
    make_user,
    make_week,
)


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


def _seed_pool():
    """SEC x3, Big Ten x2, Independent x1 -- distinct counts so the
    count-desc-then-name ordering is unambiguous. Returns {name: CfbTeam}."""
    names = [
        'Alabama', 'Georgia', 'Tennessee',   # SEC (3)
        'Michigan', 'Ohio State',            # Big Ten (2)
        'Notre Dame',                        # Independent (1)
    ]
    return {n: make_team(n) for n in names}


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id  # session identity is auth_id, not id
        sess['_fresh'] = True


# -- helper: grouping + ordering -----------------------------------------

def test_pool_teams_by_conference_groups_orders_and_counts(app):
    _seed_pool()
    db.session.commit()

    groups, total, conf_count = pool_teams_by_conference()

    assert total == 6
    assert conf_count == 3
    # Ordered by group size DESC, then conference name ASC.
    assert [(conf, count) for conf, _, count in groups] == [
        ('SEC', 3), ('Big Ten', 2), ('Independent', 1)
    ]
    # Teams within a group keep name order.
    sec_teams = next(tms for conf, tms, _ in groups if conf == 'SEC')
    assert [t.name for t in sec_teams] == ['Alabama', 'Georgia', 'Tennessee']


def test_pool_uses_stored_conference_for_offmaster_team(app):
    """A team off the master list groups by its stored conference column
    (CfbTeam.get_conference()), never dumped into 'Unknown'."""
    from games.cfb.models import CfbTeam
    db.session.add(CfbTeam(name='Directional State', conference='Big Sky'))
    db.session.commit()

    groups, total, conf_count = pool_teams_by_conference()

    assert total == 1
    assert [(conf, count) for conf, _, count in groups] == [('Big Sky', 1)]


def test_pool_teams_by_conference_empty_pool(app):
    """No seeded teams -> empty groups, zero totals (out-of-season / fresh DB)."""
    groups, total, conf_count = pool_teams_by_conference()
    assert groups == []
    assert total == 0
    assert conf_count == 0


# -- render: the pool section on /cfb/ ------------------------------------

def test_index_renders_pool_section_for_anonymous(client, app):
    _seed_pool()
    db.session.commit()

    html = client.get('/cfb/').get_data(as_text=True)

    assert 'The Pool' in html
    assert '6' in html and 'eligible teams' in html
    # every team name is listed
    for name in ['Alabama', 'Georgia', 'Tennessee', 'Michigan',
                 'Ohio State', 'Notre Dame']:
        assert name in html
    # grouped under conference headers
    assert 'cfb-pool-conf-name">SEC<' in html
    assert 'cfb-pool-conf-name">Big Ten<' in html
    # anonymous viewer never sees a struck (used) chip
    assert 'cfb-team-chip is-out' not in html


def test_index_strikes_used_teams_for_enrolled_member(client, app):
    teams = _seed_pool()
    week = make_week(1, is_active=True)
    member = make_user('member')
    make_enrollment(member)
    make_enrollment(make_user('rival'))  # 2 active enrollments -> regular branch
    make_pick(member, week, teams['Georgia'])  # Georgia is now spent
    db.session.commit()

    _login(client, member)
    html = client.get('/cfb/').get_data(as_text=True)

    # the member's spent team is struck; an unused team is not
    assert 'cfb-team-chip is-out">Georgia</span>' in html
    assert 'cfb-team-chip is-out">Alabama' not in html
    assert 'cfb-team-chip">Alabama</span>' in html
    # the explanatory note appears only when the viewer has spent teams
    assert 'struck through' in html


def test_index_no_strike_for_member_without_picks(client, app):
    _seed_pool()
    make_week(1, is_active=True)  # active week so the used-set path runs
    member = make_user('member')
    make_enrollment(member)
    make_enrollment(make_user('rival'))
    db.session.commit()

    _login(client, member)
    html = client.get('/cfb/').get_data(as_text=True)

    assert 'cfb-team-chip is-out' not in html
    assert 'struck through' not in html
