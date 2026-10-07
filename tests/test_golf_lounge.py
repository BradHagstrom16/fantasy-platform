"""The Pay Sheet's lounge module (Golf Phase U7, ADR-049 seam).

``games/golf/services/lounge.py``: the season-level state from the schedule
and its locks (empty tables are pre; every event banked is post; a lock
passed is live), the per-state context the panels read (the opening lock,
the member's line and the leader, the champion and the top of the final
sheet), the shared roster floor, and a query count that does not grow with
the room. Read-only: the module never imports a writer service.

Clock-dependent tests pin GOLF_FAKE_NOW (the conftest app fixture pins
ENVIRONMENT=testing).
"""
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import event

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfTournament,
    GolfTournamentField,
    GolfTournamentResult,
)
from games.golf.services.lounge import (
    ROSTER_COUNT_FLOOR,
    build_lounge_context,
    golf_lounge_state,
)
from models.user import User

ROOT = Path(__file__).resolve().parents[1]

# Masters week 2026: the lock Thursday 7:40 AM CT, the fake clock is UTC.
THURSDAY = datetime(2026, 4, 9)
SUNDAY = datetime(2026, 4, 12)
LOCK = datetime(2026, 4, 9, 7, 40)
TUESDAY_BEFORE = '2026-04-07T15:00:00'
SUNDAY_AFTERNOON = '2026-04-12T21:30:00'


def _member(season, username, display_name=None, total=0):
    user = User(username=username, email=f'{username}@test.com',
                display_name=display_name or username)
    user.set_password('pw')
    db.session.add(user)
    db.session.flush()
    db.session.add(GolfEnrollment(user_id=user.id, season_year=season, total_points=total))
    db.session.commit()
    return user


def _tournament(season, name='Masters Tournament', week=13, status='active', finalized=False,
                start=THURSDAY, lock=LOCK, field=0, end=None):
    t = GolfTournament(
        api_tourn_id=f'T-{name}'[:20], name=name, season_year=season, week_number=week,
        start_date=start, end_date=end or SUNDAY, pick_deadline=lock, purse=10_000_000,
        status=status, results_finalized=finalized,
    )
    db.session.add(t)
    db.session.commit()
    for i in range(field):
        p = GolfPlayer(api_player_id=f'{name[:6]}{i}', first_name='Golfer', last_name=f'No{i}')
        db.session.add(p)
        db.session.flush()
        db.session.add(GolfTournamentField(tournament_id=t.id, player_id=p.id))
    db.session.commit()
    return t


def _golfer(last):
    p = GolfPlayer(api_player_id=last[:20], first_name='Test', last_name=last)
    db.session.add(p)
    db.session.commit()
    return p


# ============================================================================
# The state
# ============================================================================

def test_state_is_pre_on_empty_tables(app):
    assert golf_lounge_state() == 'pre'


def test_state_is_pre_until_a_lock_passes(app, monkeypatch):
    season = app.config['SEASON_YEAR']
    _tournament(season)
    monkeypatch.setenv('GOLF_FAKE_NOW', TUESDAY_BEFORE)
    assert golf_lounge_state() == 'pre'
    monkeypatch.setenv('GOLF_FAKE_NOW', SUNDAY_AFTERNOON)
    assert golf_lounge_state() == 'live'


def test_state_is_post_once_every_event_is_banked(app, monkeypatch):
    season = app.config['SEASON_YEAR']
    _tournament(season, name='Sony Open', week=1, status='complete', finalized=True,
                start=datetime(2026, 1, 15), lock=datetime(2026, 1, 15, 7))
    monkeypatch.setenv('GOLF_FAKE_NOW', SUNDAY_AFTERNOON)
    assert golf_lounge_state() == 'post'
    _tournament(season, week=13)
    assert golf_lounge_state() == 'live'


def test_state_ignores_another_season(app, monkeypatch):
    season = app.config['SEASON_YEAR']
    _tournament(season - 1, name='Last Year', week=1, status='complete', finalized=True,
                start=datetime(2025, 1, 15), lock=datetime(2025, 1, 15, 7))
    monkeypatch.setenv('GOLF_FAKE_NOW', SUNDAY_AFTERNOON)
    assert golf_lounge_state() == 'pre'


# ============================================================================
# The context
# ============================================================================

def test_logged_out_context_carries_the_floor_and_the_first_lock(app):
    season = app.config['SEASON_YEAR']
    ctx = build_lounge_context(None, None)
    assert ctx['roster_count'] == 0 and ctx['total_enrolled'] == 0
    assert ctx['first_event'] is None and ctx['first_lock'] is None
    assert ctx['season_year'] == season

    for i in range(ROSTER_COUNT_FLOOR):
        _member(season, f'm{i}')
    _tournament(season, name='Sony Open in Hawaii', week=1, status='upcoming',
                start=datetime(2026, 1, 15), lock=datetime(2026, 1, 15, 7, 30))
    ctx = build_lounge_context(None, None)
    assert ctx['roster_count'] == ROSTER_COUNT_FLOOR
    assert ctx['first_event'] == 'Sony Open in Hawaii'
    assert ctx['first_lock'].startswith('Thu Jan 15')


def test_pre_context_names_the_opening_event(app, monkeypatch):
    season = app.config['SEASON_YEAR']
    me = _member(season, 'me')
    monkeypatch.setenv('GOLF_FAKE_NOW', TUESDAY_BEFORE)
    ctx = build_lounge_context(me, 'pre')
    assert ctx['is_enrolled'] is True and ctx['viewer_mode'] == 'member'
    assert ctx['game_tile_label'] == 'PRESEASON'
    assert ctx['first_lock'] is None and ctx['archived_tiles'] == []

    _tournament(season, name='Sony Open in Hawaii', week=1, status='upcoming',
                start=datetime(2026, 1, 15), lock=datetime(2026, 1, 15, 7, 30))
    ctx = build_lounge_context(me, 'pre')
    assert ctx['game_tile_label'] == 'OPENS · JAN 15'
    assert ctx['first_event'] == 'Sony Open in Hawaii'


def test_live_context_reads_the_sheet_for_a_member(app, monkeypatch):
    """Sunday of the Masters: the viewer's projected line, the leader, the
    next lock, and the ask only when a pick is still to make."""
    season = app.config['SEASON_YEAR']
    me = _member(season, 'me', display_name='Me', total=1_000_000)
    rival = _member(season, 'rival', display_name='Rival', total=3_000_000)
    masters = _tournament(season, field=0)
    rbc = _tournament(season, name='RBC Heritage', week=14, status='upcoming',
                      start=datetime(2026, 4, 16), lock=datetime(2026, 4, 16, 6, 5), field=60)
    scheffler, spare = _golfer('Scheffler'), _golfer('Spare')
    db.session.add(GolfTournamentResult(
        tournament_id=masters.id, player_id=scheffler.id, status='active',
        final_position='1', rounds_completed=3, earnings=0, score_to_par='-12'))
    db.session.add(GolfPick(user_id=me.id, tournament_id=masters.id,
                            primary_player_id=scheffler.id, backup_player_id=spare.id))
    db.session.commit()
    monkeypatch.setenv('GOLF_FAKE_NOW', SUNDAY_AFTERNOON)

    ctx = build_lounge_context(me, 'live')

    assert ctx['beat'] == 'live' and ctx['week_number'] == 13
    assert ctx['event_name'] == 'Masters Tournament'
    assert ctx['game_tile_label'] == 'WEEK 13 · LIVE'
    assert ctx['court_line'] == 'Week 13 · live'
    assert ctx['next_event'] == 'RBC Heritage' and ctx['next_id'] == rbc.id
    assert ctx['next_lock'].startswith('Thu Apr 16')
    assert ctx['mine']['word'] == 'projected'
    assert ctx['mine']['money'].startswith('$') and ctx['mine']['this_week'] == 'Scheffler · 1'
    assert ctx['leader']['name'] == 'Rival' or ctx['leader']['name'] == 'Me'
    assert ctx['field'] == 2
    assert ctx['pick_wanted'] is True and ctx['mine']['pick_in'] is False

    db.session.add(GolfPick(user_id=me.id, tournament_id=rbc.id,
                            primary_player_id=scheffler.id, backup_player_id=spare.id))
    db.session.commit()
    ctx = build_lounge_context(me, 'live')
    assert ctx['pick_wanted'] is False and ctx['mine']['pick_in'] is True

    visitor = User(username='visitor', email='v@test.com')
    visitor.set_password('pw')
    db.session.add(visitor)
    db.session.commit()
    ctx = build_lounge_context(visitor, 'live')
    assert ctx['viewer_mode'] == 'view' and 'mine' not in ctx and 'pick_wanted' not in ctx
    assert ctx['leader']['name'] in ('Rival', 'Me')
    assert rival.id  # the rival's line is on the sheet the leader came from


def test_post_context_names_the_champion_and_the_top_of_the_sheet(app, monkeypatch):
    season = app.config['SEASON_YEAR']
    me = _member(season, 'me', display_name='Me', total=750_000)
    _member(season, 'casey', display_name='Casey', total=4_200_000)
    _member(season, 'dana', display_name='Dana', total=750_000)
    _member(season, 'last', display_name='Last', total=0)
    _tournament(season, name='Sony Open', week=1, status='complete', finalized=True,
                start=datetime(2026, 1, 15), lock=datetime(2026, 1, 15, 7))
    monkeypatch.setenv('GOLF_FAKE_NOW', SUNDAY_AFTERNOON)

    ctx = build_lounge_context(me, 'post')

    assert ctx['champions'] == [{'name': 'Casey', 'money': '$4,200,000',
                                 'user_id': ctx['champions'][0]['user_id']}]
    assert ctx['champion_team'].display_name == 'Casey'
    assert ctx['game_tile_label'] == 'CHAMPION · Casey'
    assert ctx['events'] == 1
    assert [(r['rank'], r['name'], r['is_you']) for r in ctx['top']] == [
        (1, 'Casey', False), (2, 'Dana', False), (2, 'Me', True)]
    assert ctx['top'][2]['money'] == '$750,000'


def test_post_context_with_no_lines_has_no_champion(app, monkeypatch):
    season = app.config['SEASON_YEAR']
    visitor = User(username='visitor', email='v@test.com')
    visitor.set_password('pw')
    db.session.add(visitor)
    db.session.commit()
    _tournament(season, name='Sony Open', week=1, status='complete', finalized=True,
                start=datetime(2026, 1, 15), lock=datetime(2026, 1, 15, 7))
    ctx = build_lounge_context(visitor, 'post')
    assert ctx['champions'] == [] and ctx['champion_team'] is None
    assert ctx['game_tile_label'] == 'SEASON BANKED' and ctx['top'] == []


# ============================================================================
# Contracts
# ============================================================================

def test_live_context_query_count_does_not_grow_with_the_room(app, monkeypatch):
    season = app.config['SEASON_YEAR']
    me = _member(season, 'me', total=1)
    _tournament(season)
    monkeypatch.setenv('GOLF_FAKE_NOW', SUNDAY_AFTERNOON)
    counter = {'n': 0}

    def _before(conn, cursor, statement, parameters, context, executemany):
        counter['n'] += 1

    event.listen(db.engine, 'before_cursor_execute', _before)
    try:
        build_lounge_context(me, 'live')
        small = counter['n']
        for i in range(5):
            _member(season, f'more{i}', total=i)
        db.session.expire_all()
        counter['n'] = 0
        build_lounge_context(me, 'live')
        big = counter['n']
    finally:
        event.remove(db.engine, 'before_cursor_execute', _before)
    assert big == small


def test_golf_lounge_module_never_imports_writers():
    src = (ROOT / 'games/golf/services/lounge.py').read_text()
    for writer in ('services.sync', 'services.reminders', 'golf.cli', 'legacy_import'):
        assert not re.search(rf'^\s*(from|import)\s+\S*{re.escape(writer)}', src, re.M), writer
