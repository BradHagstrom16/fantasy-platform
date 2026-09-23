"""The player card: ``/cfb/player/<enrollment_id>``, one member's season
read by anyone (public, like standings and results), and the member-name
links that lead to it from every room and lounge surface.

Visibility contract (games/cfb/DESIGN.md 9.9, 9.10): a week shows a pick
only once its deadline has passed; the open pick week reads "Hidden until
deadline" for an active player, for the owner too, and the picked team
never reaches the page (ledger, spent grid, or the record line's counts)
before the deadline.
"""
import re
from datetime import datetime

from extensions import db
from games.cfb.models import CfbEnrollment, CfbTeam, CfbWeek
from games.cfb.services.card import build_player_card
from games.cfb.services.game_logic import process_week_results
from games.cfb.utils import is_autopick
from models.user import User
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)

WEEK1_DEADLINE = datetime(2026, 9, 5, 11, 0)   # naive pool wall clock
WEEK2_DEADLINE = datetime(2026, 9, 12, 11, 0)
WEEK3_DEADLINE = datetime(2026, 9, 19, 11, 0)
W1_PICKED_AT = datetime(2026, 9, 4, 15, 0)       # naive UTC, before 11:00 CT Sat
W1_AUTOPICK_AT = datetime(2026, 9, 5, 16, 30)   # naive UTC, after 11:00 CT
W2_PICKED_AT = datetime(2026, 9, 10, 15, 0)
WEEK2_OPEN = '2026-09-10T12:00:00'               # W1 complete, W2 open
WEEK2_LOCKED = '2026-09-12T18:00:00'             # W2 locked, games pending
MONDAY_NIGHT = '2026-09-07T22:00:00'             # W1 past deadline, unfinished


def _as(app, username):
    """A fresh client logged in as ``username`` (auth_id, never str(id))."""
    client = app.test_client()
    user = db.session.scalar(db.select(User).filter_by(username=username))
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True
    return client


def _season(*, monday_final=True):
    """Week 1 complete (Georgia lost to Clemson; Florida State beat SMU),
    Week 2 open with Zebra Tech at Georgia and SMU at Clemson.

    Returns {name: enrollment id}. Members: ``loser`` (Georgia, one life), ``waiter`` (Florida State, two
    lives, holds Zebra Tech for Week 2), ``auto`` (Clemson, written after
    the deadline), ``idle`` (no Week 1 pick: the penalty).
    """
    week1 = make_week(1, deadline=WEEK1_DEADLINE)
    georgia, clemson = make_team('Georgia'), make_team('Clemson')
    fsu, smu = make_team('Florida State'), make_team('SMU')
    zebra = make_team('Zebra Tech')
    make_game(week1, georgia, clemson, spread=-7.0, winner='away')
    make_game(week1, fsu, smu, spread=-3.5, winner='home' if monday_final else None)
    members = {}
    for name in ('loser', 'waiter', 'auto', 'idle'):
        user = make_user(name)
        members[name] = make_enrollment(user, display_name=name.title() + ' Member')
    make_pick(members['loser'].user, week1, georgia, created_at=W1_PICKED_AT)
    make_pick(members['waiter'].user, week1, fsu, created_at=W1_PICKED_AT)
    make_pick(members['auto'].user, week1, clemson, created_at=W1_AUTOPICK_AT)
    week2 = make_week(2, deadline=WEEK2_DEADLINE, is_active=True)
    make_game(week2, georgia, zebra, spread=-4.0)
    make_game(week2, clemson, smu, spread=-10.0)
    make_pick(members['waiter'].user, week2, zebra, created_at=W2_PICKED_AT)
    db.session.commit()
    assert process_week_results(week1.id)['success'] is True
    return {name: e.id for name, e in members.items()}


def _page(app, client, enrollment_id):
    """GET the card inside its own app context.

    Flask-Login caches the loaded user on ``g``, and a request made under
    the fixture's app context shares that ``g`` with every other request
    in the test, so an anonymous read would pin every later viewer to
    anonymous. A context per read keeps each viewer honest; the teardown
    removes the session, which is why the helpers pass ids, not rows.
    """
    with app.app_context():
        resp = client.get(f'/cfb/player/{enrollment_id}')
        assert resp.status_code == 200
        return resp.get_data(as_text=True)


def test_card_renders_publicly_with_the_display_name(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_OPEN)
    with app.app_context():
        m = _season()
        html = _page(app, client, m['loser'])
    assert '<h1>' in html and 'Loser Member' in html
    assert '>loser<' not in html
    assert 'The Card' in html


def test_card_404s_for_unknown_and_other_season_ids(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_OPEN)
    with app.app_context():
        stale = make_enrollment(make_user('stale'), season=2025)
        db.session.commit()
        assert client.get('/cfb/player/999999').status_code == 404
        assert client.get(f'/cfb/player/{stale.id}').status_code == 404


def _assert_hidden(html):
    assert 'Hidden until deadline' in html
    assert 'cfb-team-name">Zebra Tech<' not in html     # not in the ledger
    assert not re.search(r'cfb-used-team">\s*Zebra Tech', html)   # not in the spent grid
    assert 'cfb-team-chip">Zebra Tech<' in html         # still on the board: unspent, as far as anyone can see
    assert 'Pending' not in html                        # the record line must not count it
    assert '1 call' in html


def test_open_week_pick_never_leaks(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_OPEN)
    with app.app_context():
        m = _season()
        html = _page(app, client, m['waiter'])
        _assert_hidden(html)
        # The owner sees the same hidden row: one visibility rule.
        _assert_hidden(_page(app, _as(app, 'waiter'), m['waiter']))
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_LOCKED)
    with app.app_context():
        html = _page(app, client, m['waiter'])
        assert 'cfb-team-name">Zebra Tech<' in html
        assert 'cfb-team-chip">Zebra Tech<' not in html
        assert 'Hidden until deadline' not in html
        assert '>TBD<' in html


def test_revealed_pick_shows_team_signed_spread_and_result(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_OPEN)
    with app.app_context():
        m = _season()
        html = _page(app, client, m['loser'])
        assert 'Georgia' in html and '-7.0' in html
        assert 'badge-lost-life">L<' in html
        assert 'vs Clemson' in html
        html = _page(app, client, m['waiter'])
        assert 'Florida State' in html and '-3.5' in html
        assert 'badge-survived">W<' in html


def test_no_contest_pick_reads_nc(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', MONDAY_NIGHT)
    with app.app_context():
        week1 = make_week(1, deadline=WEEK1_DEADLINE)
        a, b = make_team('Aardvark U'), make_team('Badger State')
        make_game(week1, a, b, spread=-2.0, no_contest=True)
        e = make_enrollment(make_user('pushed'))
        make_pick(e.user, week1, a, created_at=W1_PICKED_AT)
        db.session.commit()
        html = _page(app, client, e.id)
    assert 'badge-pending">NC<' in html


def test_no_pick_completed_week_row_and_lives_drop(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_OPEN)
    with app.app_context():
        m = _season()
        html = _page(app, client, m['idle'])
    assert 'cfb-row-nopick' in html
    assert 'No pick submitted' in html
    assert 'NO PICK' in html
    assert '1 life left' in html


def test_unfinished_reveal_week_without_a_pick(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', MONDAY_NIGHT)
    with app.app_context():
        m = _season(monday_final=False)
        html = _page(app, client, m['idle'])
    assert 'No pick submitted' in html
    assert 'NO PICK' not in html          # nothing charged until the week completes


def test_autopick_tag(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_OPEN)
    with app.app_context():
        m = _season()
        assert 'cfb-auto-tag">Auto<' in _page(app, client, m['auto'])
        assert 'cfb-auto-tag' not in _page(app, client, m['loser'])


def test_eliminated_player_shows_the_out_week(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', '2026-09-16T12:00:00')   # W2 complete, W3 open
    with app.app_context():
        m = _season()
        week2 = db.session.scalar(db.select(CfbWeek).filter_by(week_number=2))
        smu = db.session.scalar(db.select(CfbTeam).filter_by(name="SMU"))
        loser = db.session.get(CfbEnrollment, m['loser'])
        make_pick(loser.user, week2, smu, created_at=W2_PICKED_AT)
        for game in week2.games:
            game.home_team_won = True             # Georgia and Clemson win; SMU loses
        week2.is_active = False
        week3 = make_week(3, deadline=WEEK3_DEADLINE, is_active=True)
        georgia = db.session.scalar(db.select(CfbTeam).filter_by(name="Georgia"))
        make_game(week3, georgia, smu, spread=-6.0)
        db.session.commit()
        assert process_week_results(week2.id)['success'] is True
        db.session.expire_all()
        assert db.session.get(CfbEnrollment, m['loser']).is_eliminated
        html = _page(app, client, m['loser'])
    assert 'Out in Week 2' in html
    assert 'is-lost' in html
    assert 'cfb-field-out">Out<' in html
    assert 'Hidden until deadline' not in html
    assert '<strong>Week 3</strong>' not in html   # no row for the open week; the eyebrow may name it


def test_you_tag_and_review_link_only_for_the_owner(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_OPEN)
    with app.app_context():
        m = _season()
        html = _page(app, client, m['loser'])
        assert 'cfb-you-tag' not in html and 'Review Your Card' not in html
        html = _page(app, _as(app, 'waiter'), m['loser'])
        assert 'cfb-you-tag' not in html and 'Review Your Card' not in html
        html = _page(app, _as(app, 'loser'), m['loser'])
        assert 'cfb-you-tag">You<' in html
        assert 'Review Your Card' in html and '/cfb/my-picks' in html


def test_spread_line_spent_grid_and_flat_board(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_OPEN)
    with app.app_context():
        m = _season()
        html = _page(app, client, m['loser'])
    assert 'Cumulative spread' in html
    assert re.search(r'cfb-used-team">\s*Georgia', html)
    assert 'conferenceAccordion' not in html
    assert 'cfb-pool-conf-name">ACC<' in html and 'Clemson' in html
    assert 'Review Your Card' not in html


def test_standings_pill_is_active_on_the_card(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_OPEN)
    with app.app_context():
        m = _season()
        html = _page(app, client, m['loser'])
    assert re.search(r'subnav-pill active"\s+href="/cfb/"', html)


def test_builder_keeps_the_my_picks_contract(app, client, monkeypatch):
    monkeypatch.setenv('CFB_FAKE_NOW', WEEK2_OPEN)
    with app.app_context():
        m = _season()
        waiter = db.session.get(CfbEnrollment, m['waiter'])
        keys = set(build_player_card(waiter.user_id, waiter))
        assert keys >= {
            'lead_week_id', 'enrollment', 'user_picks', 'used_teams', 'available_teams',
            'teams_by_conference', 'conference_status', 'conference_warnings',
            'conferences_with_teams', 'total_conferences', 'current_week',
            'current_week_display', 'in_cfp', 'phase_description', 'total_picks',
            'correct_picks', 'incorrect_picks', 'pending_picks',
            'cfp_eliminated_teams', 'cfp_teams_on_bye',
        }
        html = _as(app, 'waiter').get('/cfb/my-picks').get_data(as_text=True)
    assert 'Zebra Tech' in html            # the owner's own open pick stays on Your Card


class _Stub:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_is_autopick_reads_created_at_against_the_pool_deadline(app):
    # Deadline Sat 11:00 AM CT == 16:00 UTC in September; created_at is
    # naive UTC (the model's audit timestamp).
    week = _Stub(deadline=datetime(2026, 9, 5, 11, 0))
    late = _Stub(created_at=datetime(2026, 9, 5, 16, 1))
    early = _Stub(created_at=datetime(2026, 9, 5, 15, 59))
    with app.app_context():
        assert is_autopick(late, week) is True
        assert is_autopick(early, week) is False
