"""The Sheet (/golf/) and The Board (/golf/tournament/<id>): Golf Phase U1 + U3.

Locks the builders in ``games/golf/services/sheet.py`` and what the two pages
render from them (games/golf/DESIGN.md §2, §7, §9):

- competition rank, never dense rank or loop order (1, 1, 3, 4; "T1");
- pencil and ink: a figure is PROJECTED only while a live projection is in it,
  BANKED otherwise, and a board is one or the other;
- the sheet is in true rank order with the member's own row marked once;
- the board is ranked by the week's figure, not by username;
- before the lock no other member's golfer reaches the response.

Every clock-dependent test pins GOLF_FAKE_NOW (the conftest app fixture pins
ENVIRONMENT=testing), so none of them reads the real date.
"""
from datetime import datetime
from pathlib import Path

import pytest

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfPlayer,
    GolfTournament,
    GolfTournamentField,
    GolfTournamentResult,
)
from games.golf.services.sheet import (
    build_board,
    build_sheet,
    competition_ranks,
    live_event,
    ordinal,
    week_lines,
)
from games.golf.utils import get_current_time
from models.user import User
from tests._registry_helpers import set_status

TEMPLATES = Path(__file__).parent.parent / 'games' / 'golf' / 'templates' / 'golf'

# Masters week 2026 on the league's wall clock; the fake clock is UTC.
THURSDAY = datetime(2026, 4, 9)
SUNDAY = datetime(2026, 4, 12)
LOCK = datetime(2026, 4, 9, 7, 40)
SUNDAY_430_PM_CT = '2026-04-12T21:30:00'
TUESDAY_BEFORE = '2026-04-07T15:00:00'


@pytest.fixture()
def season(app):
    return app.config['SEASON_YEAR']


@pytest.fixture()
def sunday(monkeypatch):
    monkeypatch.setenv('GOLF_FAKE_NOW', SUNDAY_430_PM_CT)


# --- seed helpers (run inside the fixture's app context) --------------------

def _member(season, username, display_name=None, total=0, has_paid=True):
    user = User(username=username, email=f'{username}@test.com',
                display_name=display_name or username)
    user.set_password('pw')
    db.session.add(user)
    db.session.flush()
    db.session.add(GolfEnrollment(user_id=user.id, season_year=season,
                                  total_points=total, has_paid=has_paid))
    db.session.commit()
    return user


def _tournament(season, name='Masters Tournament', status='active', finalized=False,
                is_major=False, purse=10_000_000, start=THURSDAY, end=SUNDAY,
                lock=LOCK, week=13):
    t = GolfTournament(
        api_tourn_id=f'T-{name}'[:20], name=name, season_year=season,
        start_date=start, end_date=end, pick_deadline=lock, purse=purse,
        is_major=is_major, status=status, results_finalized=finalized,
        week_number=week,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _golfer(last, api_id=None):
    player = GolfPlayer(api_player_id=api_id or last[:20], first_name='Test', last_name=last)
    db.session.add(player)
    db.session.commit()
    return player


def _result(tournament, player, position='1', status='active', rounds=3, earnings=0,
            score=None, updated_at=None):
    result = GolfTournamentResult(
        tournament_id=tournament.id, player_id=player.id, status=status,
        final_position=position, rounds_completed=rounds, earnings=earnings,
        score_to_par=score,
    )
    if updated_at is not None:
        result.updated_at = updated_at
    db.session.add(result)
    db.session.commit()
    return result


def _pick(user, tournament, primary, backup, **kwargs):
    pick = GolfPick(user_id=user.id, tournament_id=tournament.id,
                    primary_player_id=primary.id, backup_player_id=backup.id, **kwargs)
    db.session.add(pick)
    db.session.commit()
    return pick


def _lines(tournament):
    picks = GolfPick.query.filter_by(tournament_id=tournament.id).all()
    results = GolfTournamentResult.query.filter_by(tournament_id=tournament.id).all()
    return week_lines(tournament, picks, results)


def _login(client, user):
    with client.session_transaction() as sess:
        sess['_user_id'] = user.auth_id
        sess['_fresh'] = True


# ============================================================================
# Competition rank
# ============================================================================

def test_competition_ranks_share_and_gap():
    assert competition_ranks([900, 900, 500, 100]) == [
        (1, 'T1'), (1, 'T1'), (3, '3'), (4, '4'),
    ]


def test_competition_ranks_all_alone():
    assert competition_ranks([3, 2, 1]) == [(1, '1'), (2, '2'), (3, '3')]


def test_ordinal():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23)] == [
        '1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '23rd',
    ]


# ============================================================================
# week_lines: every member week state
# ============================================================================

def test_week_line_live_projection_is_pencil(app, season, sunday):
    member = _member(season, 'm')
    t = _tournament(season)
    primary, backup = _golfer('Leader'), _golfer('Spare')
    # The stored earnings are never the figure before the event banks: the
    # projection is re-derived from position.
    _result(t, primary, position='1', earnings=999, score=-11)
    _pick(member, t, primary, backup)

    line = _lines(t)[member.id]
    assert line.golfer.id == primary.id
    assert line.figure == 1_800_000            # 18% of a $10M purse
    assert line.in_pencil and not line.banked
    assert line.position == '1' and line.to_par == '-11'
    assert line.place == '1st'                 # held alone: a place; 'T9' stays 'T9'
    assert line.deduction is None and line.replaces is None and not line.used


def test_week_line_major_projection_carries_the_multiplier_once(app, season, sunday):
    member = _member(season, 'm')
    t = _tournament(season, is_major=True)
    primary, backup = _golfer('Leader'), _golfer('Spare')
    _result(t, primary, position='1')
    _pick(member, t, primary, backup)

    assert _lines(t)[member.id].figure == 2_700_000


@pytest.mark.parametrize('status, word', [('cut', 'Cut'), ('CUT', 'Cut'), ('wd', 'WD'), ('dq', 'DQ')])
def test_week_line_deduction_is_a_certain_zero(app, season, sunday, status, word):
    member = _member(season, 'm')
    t = _tournament(season)
    primary, backup = _golfer('Gone'), _golfer('Spare')
    # rounds=2: a withdrawal after round 2 keeps the primary as the golfer who counts.
    _result(t, primary, position=status.upper(), status=status, rounds=2)
    _result(t, backup, position='T5')
    _pick(member, t, primary, backup)

    line = _lines(t)[member.id]
    assert line.golfer.id == primary.id
    assert line.deduction == word
    assert line.figure == 0 and not line.in_pencil
    assert line.position == ''


def test_week_line_backup_counts_when_primary_withdraws_early(app, season, sunday):
    member = _member(season, 'm')
    t = _tournament(season)
    primary, backup = _golfer('Withdrew'), _golfer('Stepped')
    _result(t, primary, position='WD', status='wd', rounds=1)
    _result(t, backup, position='1')
    _pick(member, t, primary, backup)

    line = _lines(t)[member.id]
    assert line.golfer.id == backup.id
    assert line.replaces.id == primary.id
    assert line.place == '1st'
    assert line.idle.id == primary.id
    assert line.figure == 1_800_000 and line.in_pencil


def test_week_line_both_withdrew_early_keeps_the_primary(app, season, sunday):
    member = _member(season, 'm')
    t = _tournament(season)
    primary, backup = _golfer('Withdrew'), _golfer('Also')
    _result(t, primary, position='WD', status='wd', rounds=1)
    _result(t, backup, position='WD', status='wd', rounds=0)
    _pick(member, t, primary, backup)

    line = _lines(t)[member.id]
    assert line.golfer.id == primary.id and line.replaces is None
    assert line.deduction == 'WD' and line.figure == 0


def test_week_line_before_the_first_read(app, season, sunday):
    member = _member(season, 'm')
    t = _tournament(season)
    primary, backup = _golfer('Unread'), _golfer('Spare')
    _pick(member, t, primary, backup)

    line = _lines(t)[member.id]
    assert line.figure is None and not line.in_pencil
    assert line.position == '' and line.to_par is None


def test_week_line_banked_reads_points_earned_only(app, season, sunday):
    member = _member(season, 'm')
    t = _tournament(season, status='complete', finalized=True)
    primary, backup = _golfer('Banked'), _golfer('Spare')
    _result(t, primary, position='1', status='complete', rounds=4, earnings=1)
    _pick(member, t, primary, backup, active_player_id=primary.id,
          points_earned=250_000, primary_used=True)

    line = _lines(t)[member.id]
    assert line.figure == 250_000
    assert line.banked and not line.in_pencil and line.used


def test_week_line_settling_is_still_a_projection(app, season, sunday):
    """Played out, results not final: pencil, from position, never stored earnings."""
    member = _member(season, 'm')
    t = _tournament(season, status='complete', finalized=False)
    primary, backup = _golfer('Settling'), _golfer('Spare')
    _result(t, primary, position='1', status='complete', rounds=4, earnings=5)
    _pick(member, t, primary, backup)

    line = _lines(t)[member.id]
    assert line.figure == 1_800_000 and line.in_pencil


def test_live_event_is_the_latest_locked_week_not_yet_banked():
    banked = GolfTournament(name='Banked', status='complete', results_finalized=True)
    settling = GolfTournament(name='Settling', status='complete', results_finalized=False)
    live = GolfTournament(name='Live', status='upcoming', results_finalized=False)

    # The status is never read: a just-locked week the hook still holds as
    # 'upcoming' outranks last week's settling one.
    assert live_event([banked, settling, live]) is live
    assert live_event([banked, settling]) is settling
    assert live_event([banked]) is None
    assert live_event([]) is None


def test_week_lines_fire_no_query_per_pick(app, season, sunday):
    from sqlalchemy import event

    t = _tournament(season)
    for i in range(4):
        primary, backup = _golfer(f'P{i}'), _golfer(f'B{i}')
        _result(t, primary, position='WD', status='wd', rounds=1)
        _result(t, backup, position=f'T{i + 2}')
        _pick(_member(season, f'm{i}'), t, primary, backup)

    from sqlalchemy.orm import joinedload
    picks = (GolfPick.query
             .options(joinedload(GolfPick.user), joinedload(GolfPick.primary_player),
                      joinedload(GolfPick.backup_player))
             .filter_by(tournament_id=t.id).all())
    results = GolfTournamentResult.query.filter_by(tournament_id=t.id).all()

    statements = []
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(db.engine, 'before_cursor_execute', listener)
    try:
        lines = week_lines(t, picks, results)
        assert all(line.replaces is not None for line in lines.values())
    finally:
        event.remove(db.engine, 'before_cursor_execute', listener)
    assert statements == []


# ============================================================================
# build_sheet / build_board
# ============================================================================

def test_sheet_orders_by_projected_total_and_names_each_state(app, season, sunday):
    leader = _member(season, 'leader', total=2_500_000)      # golfer cut: stays banked
    chaser = _member(season, 'chaser', total=1_000_000)      # +1.8M projected: passes
    idle = _member(season, 'idle', total=400_000)            # no pick
    t = _tournament(season)
    hot, cold, spare = _golfer('Hot'), _golfer('Cold'), _golfer('Spare')
    _result(t, hot, position='1')
    _result(t, cold, position='CUT', status='cut', rounds=2)
    _pick(leader, t, cold, spare)
    _pick(chaser, t, hot, spare)

    enrollments = GolfEnrollment.query.filter_by(season_year=season).all()
    sheet = build_sheet(enrollments, viewer_id=leader.id, lines=_lines(t))

    assert [(r.user.id, r.total, r.projected) for r in sheet.rows] == [
        (chaser.id, 2_800_000, True),
        (leader.id, 2_500_000, False),
        (idle.id, 400_000, False),
    ]
    assert [r.rank_label for r in sheet.rows] == ['1', '2', '3']
    assert sheet.mine.user.id == leader.id and sheet.mine.place == '2nd'
    assert [u.id for u in sheet.didnt_pick] == [idle.id]
    assert sheet.projected


def test_sheet_between_events_is_all_banked_with_shared_ranks(app, season):
    a = _member(season, 'bravo', total=900)
    b = _member(season, 'alpha', total=900)
    c = _member(season, 'charlie', total=100, has_paid=False)

    sheet = build_sheet(GolfEnrollment.query.filter_by(season_year=season).all())

    # Ties share the rank, break by name, and the next rank gaps.
    assert [(r.user.id, r.rank_label) for r in sheet.rows] == [
        (b.id, 'T1'), (a.id, 'T1'), (c.id, '3'),
    ]
    assert sheet.rows[0].place == 'Tied 1st'
    assert not sheet.projected and sheet.didnt_pick == [] and sheet.mine is None
    assert [r.unpaid for r in sheet.rows] == [False, False, True]


def test_sheet_never_counts_a_resolved_week_twice(app, season, sunday):
    """A Commish override resolves a pick on a settling event: its points are
    already in total_points, so the projection is not added on top."""
    member = _member(season, 'm', total=300_000)
    t = _tournament(season, status='complete', finalized=False)
    primary, backup = _golfer('Resolved'), _golfer('Spare')
    _result(t, primary, position='1', status='complete', rounds=4)
    _pick(member, t, primary, backup, active_player_id=primary.id, points_earned=300_000)

    sheet = build_sheet(GolfEnrollment.query.filter_by(season_year=season).all(),
                        lines=_lines(t))
    assert sheet.rows[0].total == 300_000 and not sheet.rows[0].projected


def test_board_ranks_by_the_weeks_figure_not_the_username(app, season, sunday):
    low = _member(season, 'aaa_low')
    high = _member(season, 'zzz_high')
    tied = _member(season, 'mmm_tied')
    absent = _member(season, 'absent')
    t = _tournament(season)
    first, tenth, spare = _golfer('First'), _golfer('Tenth'), _golfer('Spare')
    _result(t, first, position='1')
    _result(t, tenth, position='10')
    _pick(low, t, tenth, spare)
    _pick(high, t, first, spare)
    _pick(tied, t, first, spare)

    enrollments = GolfEnrollment.query.filter_by(season_year=season).all()
    board = build_board(_lines(t), enrollments, viewer_id=low.id)

    assert [(r.user.id, r.rank_label) for r in board.rows] == [
        (tied.id, 'T1'), (high.id, 'T1'), (low.id, '3'),
    ]
    assert board.mine.user.id == low.id
    assert [u.id for u in board.didnt_pick] == [absent.id]
    assert board.penalties == 0


# ============================================================================
# /golf/ — The Sheet
# ============================================================================

def _live_week(season):
    """Three members on a live major: one in the money, one cut, one with no pick."""
    me = _member(season, 'viewer', display_name='ViewerLine', total=1_000_000)
    rival = _member(season, 'rival', display_name='RivalLine', total=2_500_000)
    idle = _member(season, 'idle', display_name='IdleLine', total=50_000)
    t = _tournament(season, is_major=True)
    hot, cold, spare = _golfer('Hotgolfer'), _golfer('Coldgolfer'), _golfer('Sparegolfer')
    # Both stamped by the 4 PM CT read (21:00 UTC); the first is an hour stale.
    _result(t, hot, position='1', updated_at=datetime(2026, 4, 12, 17, 0))
    _result(t, cold, position='CUT', status='cut', rounds=2,
            updated_at=datetime(2026, 4, 12, 21, 0))
    _pick(me, t, hot, spare)
    _pick(rival, t, cold, spare, penalty_triggered=True)
    return me, rival, idle, t


def test_sheet_page_live(app, client, season, sunday):
    me, rival, idle, t = _live_week(season)
    _login(client, me)

    body = client.get('/golf/').get_data(as_text=True)

    # The context line: event, round, and how fresh the pencil is.
    assert 'Masters Tournament' in body and 'Round 4' in body
    assert 'as of 4:00 PM CT' in body
    # Your line, in pencil, at its real place.
    assert 'Your line' in body
    assert 'golf-hero-figure--projected">~$3,700,000' in body
    assert '<strong>1st</strong> of 3' in body
    # True rank order, and exactly one marked row in the rendered page.
    assert body.index('ViewerLine') < body.index('RivalLine') < body.index('IdleLine')
    assert body.count('golf-sheet-row--me') == 1
    # Both money states, named in words; the cut golfer's line stays banked.
    assert 'golf-money--projected">~$3,700,000' in body
    assert 'golf-money--banked">$2,500,000' in body
    assert '>Projected<' in body and '>Banked<' in body
    # The pencil pick line and its marks.
    assert 'Hotgolfer · 1 · ~$2,700,000' in body
    assert 'golf-chip--deduction">Cut<' in body
    assert 'badge-penalty' in body
    assert "Didn't pick (1)" in body
    assert 'No pick' in body


def test_sheet_page_pot_line(app, client, season, sunday):
    _live_week(season)
    body = client.get('/golf/').get_data(as_text=True)

    assert 'Prize Pool' in body
    assert 'Entry $25 × 3' in body
    assert '<dd>$75</dd>' in body       # entry fees
    assert '<dd>$15</dd>' in body       # one flagged pick
    assert '<dd>$90</dd>' in body       # in the pool


def test_sheet_page_signed_out_has_no_line(app, client, season, sunday):
    _live_week(season)
    body = client.get('/golf/').get_data(as_text=True)

    assert 'Your line' not in body
    assert 'golf-sheet-row--me' not in body
    assert 'ViewerLine' in body


def test_sheet_page_next_pick_during_live_play(app, client, season, sunday):
    me, *_ = _live_week(season)
    _tournament(season, name='RBC Heritage', status='upcoming', week=14,
                start=datetime(2026, 4, 16), end=datetime(2026, 4, 19),
                lock=datetime(2026, 4, 16, 6, 5))
    _login(client, me)

    body = client.get('/golf/').get_data(as_text=True)
    assert 'Next pick' in body and 'RBC Heritage' in body
    assert 'The field publishes Tuesday' in body
    assert 'Spend a golfer' not in body


def _open_field(season, monkeypatch):
    monkeypatch.setenv('GOLF_FAKE_NOW', TUESDAY_BEFORE)
    t = _tournament(season, status='upcoming')
    players = [GolfPlayer(api_player_id=f'F{i}', first_name='Field', last_name=f'Player{i}')
               for i in range(50)]
    db.session.add_all(players)
    db.session.flush()
    db.session.add_all(GolfTournamentField(tournament_id=t.id, player_id=p.id) for p in players)
    db.session.commit()
    return t, players


def test_sheet_page_open_pick_offers_the_action(app, client, season, monkeypatch):
    t, _players = _open_field(season, monkeypatch)
    me = _member(season, 'viewer', total=10)
    _login(client, me)

    body = client.get('/golf/').get_data(as_text=True)
    assert 'picks lock Thu Apr 9 · 7:40 AM CT' in body
    assert body.count(f'/golf/pick/{t.id}') == 2     # the line's link and the margin action
    assert 'Spend a golfer' in body
    # Between events every line is banked and says so once, over the column.
    assert 'golf-money--projected">~$' not in body
    assert '>Banked<' in body


def test_sheet_page_made_pick_offers_change(app, client, season, monkeypatch):
    t, players = _open_field(season, monkeypatch)
    me = _member(season, 'viewer', total=10)
    _pick(me, t, players[0], players[1])
    _login(client, me)

    body = client.get('/golf/').get_data(as_text=True)
    assert 'Field Player0' in body and 'backup Field Player1' in body
    assert '>Change<' in body
    assert 'golf-btn' not in body


def test_sheet_page_offers_a_seat_only_while_the_room_takes_them(app, client, season, monkeypatch):
    _member(season, 'seated', display_name='SeatedLine')
    visitor = User(username='visitor', email='visitor@test.com', display_name='Visitor')
    visitor.set_password('pw')
    db.session.add(visitor)
    db.session.commit()
    _login(client, visitor)

    # coming_soon (the registry's shipped status): no seat on offer.
    assert 'Take a seat' not in client.get('/golf/').get_data(as_text=True)

    set_status(monkeypatch, 'golf', 'open')
    body = client.get('/golf/').get_data(as_text=True)
    assert 'Take a seat' in body and '/golf/join' in body
    assert 'Your line' not in body


def test_sheet_page_empty_state(app, client, season):
    body = client.get('/golf/').get_data(as_text=True)
    assert 'Nobody has a line yet' in body
    assert '<table' not in body


# ============================================================================
# /golf/tournament/<id> — The Board
# ============================================================================

def test_board_page_live(app, client, season, sunday):
    me, rival, idle, t = _live_week(season)
    _tournament(season, name='Valero Texas Open', status='complete', finalized=True,
                week=12, start=datetime(2026, 4, 2), end=datetime(2026, 4, 5),
                lock=datetime(2026, 4, 2, 7, 30))
    _login(client, me)

    body = client.get(f'/golf/tournament/{t.id}').get_data(as_text=True)

    assert '<h1 class="golf-title golf-title--page">The Board: Masters Tournament</h1>' in body
    assert 'Major ×1.5' in body
    # The pager: this leaf's neighbour in the Season Book.
    assert 'Week 13 of 13' in body and 'Valero Texas Open' in body
    # Your pick, in pencil.
    assert 'Your pick' in body
    assert 'golf-hero-figure--projected">~$2,700,000' in body
    # Ranked by the week's figure: the viewer leads, the cut golfer follows.
    assert body.index('ViewerLine') < body.index('RivalLine')
    assert body.count('golf-sheet-row--me') == 1
    assert 'Penalties assessed: <strong>1</strong> · $15 to the pot' in body
    assert 'Reads at noon, 4 PM and 8 PM CT' in body and 'last read 4:00 PM CT' in body
    assert "Didn't pick (1)" in body and 'IdleLine' in body
    # An unbanked board is a projection and never says otherwise.
    assert '>Projected<' in body and '>Banked<' not in body and 'Earnings' not in body


def test_board_page_banked(app, client, season, sunday):
    me = _member(season, 'viewer', display_name='ViewerLine')
    t = _tournament(season, status='complete', finalized=True)
    primary, backup = _golfer('Bankedgolfer'), _golfer('Sparegolfer')
    _result(t, primary, position='T3', status='complete', rounds=4, score=-9)
    _pick(me, t, primary, backup, active_player_id=primary.id,
          points_earned=640_000, primary_used=True, admin_override=True,
          admin_override_note='Phoned it in')
    _login(client, me)

    body = client.get(f'/golf/tournament/{t.id}').get_data(as_text=True)

    assert 'golf-hero-figure--banked">$640,000' in body
    assert '<strong>Test Bankedgolfer</strong> · T3 · backup Sparegolfer unused' in body
    assert 'golf-money--banked">$640,000' in body
    assert 'Bankedgolfer · T3 · −9' in body          # to par, with a true minus
    assert 'golf-chip--pen">Used<' in body
    assert 'title="Phoned it in">Commish<' in body
    assert '>Banked<' in body and '>Projected<' not in body
    assert 'Reads at noon' not in body
    assert 'Penalties assessed' not in body          # not a major


def test_board_page_without_a_pick_leads_with_the_purse(app, client, season, sunday):
    _me, _rival, _idle, t = _live_week(season)
    body = client.get(f'/golf/tournament/{t.id}').get_data(as_text=True)

    assert 'Your pick' not in body
    assert '>Purse<' in body and 'golf-hero-figure">$10,000,000' in body
    assert '2 picks on the board' in body


def test_board_page_hides_every_other_pick_until_the_lock(app, client, season, monkeypatch):
    t, players = _open_field(season, monkeypatch)
    me = _member(season, 'viewer', display_name='ViewerLine')
    rival = _member(season, 'rival', display_name='RivalLine')
    mine, spare = _golfer('Minegolfer'), _golfer('Mysparegolfer')
    theirs, their_spare = _golfer('Secretgolfer'), _golfer('Hiddenspare')
    _pick(me, t, mine, spare)
    _pick(rival, t, theirs, their_spare)
    _login(client, me)

    body = client.get(f'/golf/tournament/{t.id}').get_data(as_text=True)

    assert 'Minegolfer' in body and 'Mysparegolfer' in body
    assert 'Secretgolfer' not in body and 'Hiddenspare' not in body
    assert 'RivalLine' not in body
    assert '2 picks are in' in body
    assert 'Every pick stays hidden until the lock' in body
    assert '<table' not in body


def _masters_inside_the_refresh(app, client, season, monkeypatch, status, now):
    """The Masters (first tee 7:40 AM CT) read at ``now`` with ``status`` held.

    Inside the request hook's refresh interval, so the status a sync wrote (or
    the hook has yet to correct) is the status the page reads.
    """
    monkeypatch.setenv('GOLF_FAKE_NOW', now)
    monkeypatch.setitem(app.config, '_GOLF_LAST_STATUS_REFRESH', get_current_time())
    t = _tournament(season, status=status)
    me = _member(season, 'viewer', display_name='ViewerLine')
    rival = _member(season, 'rival', display_name='RivalLine')
    _pick(me, t, _golfer('Minegolfer'), _golfer('Mysparegolfer'))
    _pick(rival, t, _golfer('Secretgolfer'), _golfer('Hiddenspare'))
    _login(client, me)
    return t


def _synced_active_before_the_lock(app, client, season, monkeypatch):
    """A sync marked the Masters active at Thursday midnight; it is 6:00 AM CT."""
    return _masters_inside_the_refresh(app, client, season, monkeypatch,
                                       status='active', now='2026-04-09T11:00:00')


def test_board_page_opens_at_the_lock_not_at_a_synced_status(app, client, season, monkeypatch):
    t = _synced_active_before_the_lock(app, client, season, monkeypatch)

    body = client.get(f'/golf/tournament/{t.id}').get_data(as_text=True)

    assert 'Minegolfer' in body
    assert 'Secretgolfer' not in body and 'Hiddenspare' not in body
    assert '2 picks are in' in body
    assert '<table' not in body


def test_sheet_page_pencils_a_week_only_past_its_lock(app, client, season, monkeypatch):
    _synced_active_before_the_lock(app, client, season, monkeypatch)

    body = client.get('/golf/').get_data(as_text=True)

    assert 'Secretgolfer' not in body and 'Hiddenspare' not in body
    assert 'golf-pick-line' not in body and "Didn't pick (" not in body
    assert 'RivalLine' in body                                  # the line itself still shows


def test_sheet_page_turns_over_at_the_lock_before_the_status_does(app, client, season, monkeypatch):
    # 8:00 AM CT Thursday, twenty minutes past the lock; the hook has not yet
    # moved the Masters off 'upcoming', and its field is published.
    t = _masters_inside_the_refresh(app, client, season, monkeypatch,
                                    status='upcoming', now='2026-04-09T13:00:00')
    players = [GolfPlayer(api_player_id=f'F{i}', first_name='Field', last_name=f'Player{i}')
               for i in range(50)]
    db.session.add_all(players)
    db.session.flush()
    db.session.add_all(GolfTournamentField(tournament_id=t.id, player_id=p.id) for p in players)
    db.session.commit()

    body = client.get('/golf/').get_data(as_text=True)

    # No pick action on a locked week, and no lock stated in the past tense.
    assert f'/golf/pick/{t.id}' not in body
    assert 'Thu Apr 9 · 7:40 AM CT' not in body
    # The week is the sheet's: every pick open, in its first round.
    assert 'Secretgolfer' in body and 'Minegolfer' in body
    assert 'Round 1' in body and 'first read at noon CT' in body


def test_board_page_open_field_offers_the_action(app, client, season, monkeypatch):
    t, _players = _open_field(season, monkeypatch)
    me = _member(season, 'viewer')
    _login(client, me)

    body = client.get(f'/golf/tournament/{t.id}').get_data(as_text=True)
    assert 'Spend a golfer' in body and f'/golf/pick/{t.id}' in body
    assert 'No picks are in yet' in body


# ============================================================================
# Template source: what U1 + U3 retired stays retired
# ============================================================================

@pytest.mark.parametrize('name', ['index.html', 'tournament_detail.html'])
def test_sheet_templates_carry_no_pre_u1_markup(name):
    source = (TEMPLATES / name).read_text()
    for retired in ('table-golf', 'row-leader', 'col-divider', 'golf-pool',
                    'hero-progress', 'golf-pick-cta', 'text-gold', 'page-hero',
                    'row-current-user', 'loop.index', 'style="', 'card'):
        assert retired not in source, f'{name} still carries {retired!r}'
    # Copy discipline: no em dashes or double hyphens in the room's copy.
    assert '—' not in source and ' -- ' not in source
