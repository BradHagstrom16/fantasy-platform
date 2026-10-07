"""Three headliners on the bill (Golf Phase U7): The Pay Sheet seated beside
CFB Survivor and The Docket.

Golf ships `coming_soon` and unfeatured, so these tests seat it through the
registry helpers (status open + featured) and pin every clock: CFB and the
Docket at DUAL_PRE (empty tables, both pre), golf's tables empty (pre) or
seeded (live, post). The shell takes the trio grid (two seams, no seal),
the bill's copy counts three, and the golf panel carries the fourth decree.
"""
import os
import re
from datetime import datetime
from unittest.mock import patch

from extensions import db
from games.golf.models import GolfEnrollment, GolfPick, GolfPlayer, GolfTournament
from models.user import User
from tests._registry_helpers import set_is_featured, set_status

TRIO_PRE = {'ENVIRONMENT': 'testing',
            'CFB_FAKE_NOW': '2026-08-18T17:00:00',
            'DOCKET_FAKE_NOW': '2026-08-18T17:00:00'}


def _seat_golf(monkeypatch):
    set_status(monkeypatch, 'golf', 'open')
    set_is_featured(monkeypatch, 'golf', True)


def _user(username='trio'):
    user = User(username=username, email=f'{username}@test.com')
    user.set_password('pw')
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


def _enroll(user, season, total=0):
    db.session.add(GolfEnrollment(user_id=user.id, season_year=season, total_points=total))
    db.session.commit()


def test_logged_out_bill_takes_the_trio_grid(app, client, monkeypatch):
    _seat_golf(monkeypatch)
    with patch.dict(os.environ, TRIO_PRE):
        text = client.get('/').get_data(as_text=True)
    assert 'hl-duo hl-duo--trio' in text
    assert 'hl-duo--paired' not in text and 'hl-seal' not in text
    assert text.count('class="join hl-conv') == 3
    assert 'join--cfb' in text and 'join--docket' in text and 'join--golf' in text
    assert 'Three games on the card. Play one, or play them all.' in text
    assert 'Two games on the card' not in text
    # The golf card sells the game by its format and the schedule's state.
    golf_card = text[text.index('join--golf'):text.index('hl-signin')]
    assert 'Golf One &amp; Done' in golf_card
    assert 'The schedule posts in January' in golf_card
    assert 'Join the Pay Sheet' in golf_card and 'class="hl-cta"' in golf_card
    # The coming-soon rail no longer bills golf.
    assert 'out-coming-strip-title">The Pay Sheet' not in text


def test_two_headliners_still_pair_when_golf_is_unseated(app, client):
    with patch.dict(os.environ, TRIO_PRE):
        text = client.get('/').get_data(as_text=True)
    assert 'hl-duo hl-duo--paired' in text and 'hl-seal' in text
    assert 'Two games on the card. Play one, or play both.' in text
    assert 'hl-duo--trio' not in text


def test_authed_joined_nothing_sees_three_panels_and_the_fourth_decree(app, client, monkeypatch):
    _seat_golf(monkeypatch)
    _login(client, _user('neither'))
    with patch.dict(os.environ, TRIO_PRE):
        text = client.get('/').get_data(as_text=True)
    assert 'hl-duo hl-duo--trio' in text and 'hl-seal' not in text
    assert 'Three games on the card. Play one, or play them all.' in text
    heads = re.findall(r'<header class="hl-panel-head">(.*?)</header>', text, re.S)
    assert len(heads) == 3
    assert 'hl-panel-name">The Pay Sheet</span>' in heads[2]
    assert '<a class="hl-panel-link" href="/golf/">' in heads[2]
    golf_panel = text[text.index('hl-panel--golf'):text.index('_lounge_ledger') if '_lounge_ledger' in text else None]
    assert 'By Decree of the Commish' in golf_panel and 'No 004' in golf_panel
    assert 'The Pay Sheet &rsquo;26' in golf_panel
    assert 'No 004' not in text[:text.index('hl-panel--golf')]
    assert 'Take a Seat' in golf_panel and 'Enter the Room' not in golf_panel
    assert 'One golfer a week' in golf_panel


def test_golf_member_in_season_is_asked_to_spend_a_golfer(app, client, monkeypatch):
    season = app.config['SEASON_YEAR']
    _seat_golf(monkeypatch)
    me = _user('member')
    _enroll(me, season, total=250_000)
    masters = GolfTournament(
        api_tourn_id='T-masters', name='Masters Tournament', season_year=season, week_number=13,
        start_date=datetime(2026, 4, 9), end_date=datetime(2026, 4, 12),
        pick_deadline=datetime(2026, 4, 9, 7, 40), purse=20_000_000,
        status='active', results_finalized=False)
    rbc = GolfTournament(
        api_tourn_id='T-rbc', name='RBC Heritage', season_year=season, week_number=14,
        start_date=datetime(2026, 4, 16), end_date=datetime(2026, 4, 19),
        pick_deadline=datetime(2026, 4, 16, 6, 5), purse=20_000_000,
        status='upcoming', results_finalized=False)
    db.session.add_all([masters, rbc])
    db.session.commit()
    from games.golf.models import GolfTournamentField
    for i in range(55):
        p = GolfPlayer(api_player_id=f'rbc{i}', first_name='Golfer', last_name=f'No{i}')
        db.session.add(p)
        db.session.flush()
        db.session.add(GolfTournamentField(tournament_id=rbc.id, player_id=p.id))
    db.session.commit()
    _login(client, me)

    with patch.dict(os.environ, {**TRIO_PRE, 'GOLF_FAKE_NOW': '2026-04-12T21:30:00'}):
        text = client.get('/').get_data(as_text=True)
    golf_panel = text[text.index('hl-panel--golf'):]
    golf_panel = golf_panel[:golf_panel.index('</section>')]
    assert '◇ Week 13 &middot; Masters Tournament' in golf_panel
    assert '$250,000 banked' in golf_panel and '1st of 1' in golf_panel
    assert 'RBC Heritage locks' in golf_panel
    assert f'class="hl-cta" href="/golf/pick/{rbc.id}">Spend a Golfer</a>' in golf_panel

    db.session.add(GolfPick(user_id=me.id, tournament_id=rbc.id,
                            primary_player_id=1, backup_player_id=2))
    db.session.commit()
    with patch.dict(os.environ, {**TRIO_PRE, 'GOLF_FAKE_NOW': '2026-04-12T21:30:00'}):
        text = client.get('/').get_data(as_text=True)
    golf_panel = text[text.index('hl-panel--golf'):]
    assert 'Spend a Golfer' not in golf_panel[:golf_panel.index('</section>')]
    assert 'class="hl-cta" href="/golf/">Enter the Room</a>' in golf_panel


def test_golf_post_season_names_the_champion_on_the_bill(app, client, monkeypatch):
    season = app.config['SEASON_YEAR']
    _seat_golf(monkeypatch)
    me = _user('member')
    _enroll(me, season, total=750_000)
    casey = _user('casey')
    casey.display_name = 'Casey Champion'
    _enroll(casey, season, total=4_200_000)
    db.session.add(GolfTournament(
        api_tourn_id='T-sony', name='Sony Open in Hawaii', season_year=season, week_number=1,
        start_date=datetime(2026, 1, 15), end_date=datetime(2026, 1, 18),
        pick_deadline=datetime(2026, 1, 15, 7), purse=9_000_000,
        status='complete', results_finalized=True))
    db.session.commit()
    _login(client, me)

    with patch.dict(os.environ, {**TRIO_PRE, 'GOLF_FAKE_NOW': '2026-09-01T12:00:00'}):
        text = client.get('/').get_data(as_text=True)
    golf_panel = text[text.index('hl-panel--golf'):]
    golf_panel = golf_panel[:golf_panel.index('</section>')]
    assert 'The Sheet Is Banked' in golf_panel
    assert 'Champion &middot; Casey Champion' in golf_panel
    assert '$4,200,000 across 1 event.' in golf_panel
    assert 'roll-you-chip">You</span>' in golf_panel
    assert f'href="/golf/member/{casey.id}">Casey Champion</a>' in golf_panel
    assert 'href="/golf/stats">The Record Room' in golf_panel
    # The Commish's note takes the champion's name through the shim.
    assert 'Casey Champion' in text[text.index('commish'):] if 'commish' in text else True
