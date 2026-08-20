"""The eligible-team pool on the CFB room landing (/cfb/).

Covers the "which teams can I pick from?" surface added to the standings
page: the pure grouping helper (games/cfb/services/game_logic.
pool_teams_by_conference) and its render in games/cfb/templates/cfb/
index.html, including the viewer-aware "used team" strike-through.

Conference grouping is by constants.TEAM_CONFERENCES, so the seeded team
NAMES must be real short names (Alabama -> SEC, etc.).
"""
import re

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


# -- design lock: card headers use the .cfb-* vocabulary, not generic
#    Bootstrap .card + bi-* / semantic-alert headers (games/cfb/DESIGN.md
#    §7.8 Component prohibitions). Locks both render branches of index.html.
#    Each header is asserted per-section (title bound to the .cfb-field-head
#    primitive), not by a page-wide substring. Negative assertions stay scoped
#    to the exact icon/alert tokens removed -- a blanket 'bi bi-' would
#    false-fail on base.html navbar chrome (e.g. bi-gear-fill), which is why
#    bi-gear is deliberately not asserted.

def _has_field_head(html, title):
    """True when ``title`` renders as the <h5> of a .cfb-field-head header
    (the CFB native section-header primitive), tolerating the whitespace
    between the wrapper div and the heading."""
    return re.search(
        r'cfb-field-head">\s*<h5[^>]*>' + re.escape(title) + r'</h5>', html
    ) is not None


def test_index_regular_headers_use_cfb_field_head(client, app):
    """Regular-season landing: each section header renders via the native
    .cfb-field-head primitive, and the CFP notice is a crimson-identity
    card -- not a danger-red Bootstrap alert (crimson = identity, red =
    survivor-state; games/cfb/DESIGN.md §6.5/§7.8)."""
    _seed_pool()
    make_week(1, is_playoff=True, is_active=True)  # active -> current_week; playoff -> CFP notice
    make_enrollment(make_user('alice'))
    make_enrollment(make_user('bob'))  # 2 active, 0 eliminated -> regular-season branch
    db.session.commit()

    html = client.get('/cfb/').get_data(as_text=True)

    # Each header title is bound to the .cfb-field-head primitive.
    assert _has_field_head(html, 'Active Players')
    assert _has_field_head(html, 'Pool Rules')
    assert _has_field_head(html, 'Tiebreaker Rules')
    assert _has_field_head(html, 'College Football Playoff')
    # CFP notice is the crimson-identity card, not a danger-red alert.
    assert 'card border-primary' in html
    # The removed generic icons / semantic alerts are gone (section-specific).
    assert 'bi-people-fill' not in html       # Active Players
    assert 'bi-journal-text' not in html      # Pool Rules
    assert 'alert-info' not in html           # Tiebreaker Rules
    assert 'bi-info-circle' not in html       # Tiebreaker Rules
    assert 'alert-danger' not in html         # CFP notice
    assert 'bi-exclamation-triangle-fill' not in html  # CFP notice


def test_index_champion_headers_use_cfb_field_head(client, app):
    """Champion landing: Championship Journey / Fallen Competitors /
    Season Summary each use .cfb-field-head, not generic .card + bi-*."""
    champ = make_user('champ')
    make_enrollment(champ, display_name='Champ Carl')
    fallen = make_user('fallen')
    make_enrollment(fallen, lives=0, eliminated=True, display_name='Dino Dan')
    week = make_week(1, is_complete=True)
    make_pick(champ, week, make_team('Alabama'))  # champion_picks truthy -> Championship Journey renders
    db.session.commit()

    html = client.get('/cfb/').get_data(as_text=True)

    assert 'CFB Survivor Pool Champion' in html   # champion branch rendered
    # Each champion-view card header is bound to the .cfb-field-head primitive.
    assert _has_field_head(html, 'Championship Journey')
    assert _has_field_head(html, 'Fallen Competitors')
    assert _has_field_head(html, 'Season Summary')
    # The removed generic icons are gone (section-specific).
    assert 'bi-graph-up-arrow' not in html    # Championship Journey
    assert 'bi-people' not in html            # Fallen Competitors
    assert 'bi-bar-chart' not in html         # Season Summary
