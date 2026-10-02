"""The Docket sheet receipt: one per sitting, through the hourly desk
(Brad, 2026-10-02, amending the 2026-09-04 "Filed only" ruling).

Every member edit of the current week's sheet stamps the member's
``docket_sheet_receipt`` row (``touched_at``); no route mails. The Club
Desk's hourly firing mails each owed, FILED sheet (eight sides the member
held) as it stands, once, after a ten-minute quiet period, and stamps
``sent_at``. The noon firing waives the quiet period and words the letter
as closed; an autopicked sheet never gets one; a reminder in the same
firing satisfies the receipt; a refused send is retried next hour; a
change after a receipt says so in the subject.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from extensions import db
from games.club_desk import run_desk
from games.docket.models import DocketPick, DocketSheetReceipt
from games.docket.services import receipts
from models.sync_run import SyncRun
from tests._club_desk_fixtures import F_AT, capture, seed
from tests._docket_fixtures import (
    at,
    login,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

# Week 1 (naive UTC): boundary Tue Sep 1 06:00 CT, deadline Sun Sep 6
# 12:00 PM CT = 17:00 UTC. Every case kicks off after the close, so nothing
# locks before the deadline and the number stays open all week.
KICK = datetime(2026, 9, 6, 20, 0)
SITTING = datetime(2026, 9, 2, 12, 0)          # Wednesday, the seam clock
DEADLINE = datetime(2026, 9, 6, 17, 0)
JSON = {'Accept': 'application/json'}
SEND = 'games.club_desk.send_platform_email'


@pytest.fixture()
def member(app, client):
    user = make_user('member')
    make_enrollment(user)
    db.session.commit()
    login(client, user)
    return user


def _week_with_games(n=10):
    week = make_week(1)
    games = [make_game(week, kickoff=KICK, home=f'Home {i}', away=f'Away {i}')
             for i in range(n)]
    week.tiebreaker_game_id = games[-1].id
    db.session.commit()
    return week, games


def _post(client, path, **data):
    data.setdefault('csrf_token', 'x')
    resp = client.post(path, data=data, headers=JSON)
    assert resp.get_json()['ok'] is True, resp.get_json()
    return resp


def _file(client, game, side='home', **extra):
    return _post(client, '/docket/picks/set', game_id=game.id,
                 market='spread', side=side, **extra)


def _remove(client, game):
    return _post(client, '/docket/picks/remove', game_id=game.id,
                 market='spread')


def _x2(client, game):
    return _post(client, '/docket/best', game_id=game.id, market='spread')


def _clear_x2(client):
    return _post(client, '/docket/best', clear='1')


def _number(client, value='53.7'):
    return _post(client, '/docket/tiebreaker', prediction=value)


def _sitting(client, games, monkeypatch, when=SITTING, *, x2=True,
             number=True, reserve=True):
    """The common sitting, in the ladder's order: eight sides, the x2, the
    number, the reserve."""
    at(monkeypatch, when.isoformat())
    for game in games[:8]:
        _file(client, game)
    if x2:
        _x2(client, games[2])
    if number:
        _number(client)
    if reserve:
        _file(client, games[8], backup='1')


def _row(user):
    return db.session.scalar(
        select(DocketSheetReceipt).filter_by(user_id=user.id))


def _rows():
    return db.session.scalar(select(func.count(DocketSheetReceipt.id)))


def _fire(when, **kwargs):
    """One desk firing at the naive-UTC instant; the captured letters."""
    calls, patched = capture()
    with patched:
        run = run_desk(when.replace(tzinfo=UTC),
                       anchors=kwargs.pop('anchors', ('docket',)), **kwargs)
    return calls, run


# ── the touch ──────────────────────────────────────────────────────────────

def test_every_edit_stamps_the_sheet_and_no_route_mails(
        client, member, monkeypatch):
    _week, games = _week_with_games()
    edits = [
        lambda: _file(client, games[0]),
        lambda: _file(client, games[0], side='away'),     # a move
        lambda: _remove(client, games[0]),
        lambda: _file(client, games[1]),
        lambda: _x2(client, games[1]),
        lambda: _clear_x2(client),
        lambda: _number(client),
        lambda: _number(client, ''),                      # cleared
        lambda: _file(client, games[9], backup='1'),      # the reserve
    ]
    with patch(SEND, side_effect=AssertionError('a route mailed')):
        for minutes, edit in enumerate(edits):
            when = SITTING + timedelta(minutes=minutes)
            at(monkeypatch, when.isoformat())
            edit()
            row = _row(member)
            assert row.touched_at == when
            assert row.sent_at is None
    assert _rows() == 1
    # The receipt module has no send site of its own: only the desk mails.
    assert 'send_platform_email' not in vars(receipts)


def test_a_racing_insert_lands_on_the_one_row(app, member):
    week, _games = _week_with_games()
    receipts.touch(member.id, week, now=SITTING)
    real = receipts._receipt_row
    reads = iter([lambda *a: None, real])     # first read misses, as in a race
    with patch('games.docket.services.receipts._receipt_row',
               side_effect=lambda *a: next(reads)(*a)):
        receipts.touch(member.id, week, now=SITTING + timedelta(minutes=1))
    assert _rows() == 1
    assert _row(member).touched_at == SITTING + timedelta(minutes=1)


def test_a_failed_stamp_never_refuses_the_pick(client, member, monkeypatch):
    _week, games = _week_with_games()
    at(monkeypatch, SITTING.isoformat())
    with patch('games.docket.services.receipts._stamp',
               side_effect=RuntimeError('database away')):
        resp = _file(client, games[0])
    assert resp.get_json()['sheet']['scoring_count'] == 1
    assert _row(member) is None


# ── the drain ──────────────────────────────────────────────────────────────

def test_a_sitting_is_one_receipt_with_the_whole_sheet(
        client, member, monkeypatch):
    _week, games = _week_with_games()
    _sitting(client, games, monkeypatch)

    calls, run = _fire(SITTING + timedelta(minutes=15))

    assert run.exit_code == 0
    assert len(calls) == 1
    letter = calls[0]
    assert letter['to'] == member.email
    assert letter['subject'] == 'Sheet filed: The Docket, Week 1'
    plain = letter['plain']
    assert 'The Docket, Week 1: your sheet is filed' in plain
    for i in range(8):
        assert f'{i + 1}. Home {i} -3.5' in plain
    assert '3. Home 2 -3.5 · x2' in plain
    assert '53.7' in plain
    assert 'Reserve. Home 8 -3.5' in plain
    assert 'Still open' not in plain
    assert 'Sunday, Sep 6' in plain
    assert '/docket/' in plain
    assert 'Home 0 -3.5' in letter['html']
    assert _row(member).sent_at == SITTING + timedelta(minutes=15)
    assert run.delivered_receipts == {'docket': 1}

    # Once: the next hour has nothing to add.
    calls, _run = _fire(SITTING + timedelta(minutes=75))
    assert calls == []


def test_a_firing_inside_the_quiet_period_waits(client, member, monkeypatch):
    _week, games = _week_with_games()
    _sitting(client, games, monkeypatch)
    calls, _run = _fire(SITTING + timedelta(minutes=5))
    assert calls == []
    assert _row(member).sent_at is None
    calls, _run = _fire(SITTING + receipts.RECEIPT_QUIET)
    assert len(calls) == 1


def test_a_short_sheet_stays_owed_until_it_is_filed(
        client, member, monkeypatch):
    _week, games = _week_with_games()
    at(monkeypatch, SITTING.isoformat())
    for game in games[:7]:
        _file(client, game)
    calls, _run = _fire(SITTING + timedelta(hours=1))
    assert calls == []
    assert _row(member).sent_at is None

    later = SITTING + timedelta(hours=2)
    at(monkeypatch, later.isoformat())
    _file(client, games[7])
    calls, _run = _fire(later + timedelta(minutes=15))
    assert len(calls) == 1
    assert calls[0]['subject'] == 'Sheet filed: The Docket, Week 1'
    # An hour on, the open items are truly still open.
    assert 'Still open on your sheet' in calls[0]['plain']
    assert 'No headliner named.' in calls[0]['plain']
    assert 'No combined-score number recorded.' in calls[0]['plain']


def test_a_change_after_a_receipt_resends_once_as_updated(
        client, member, monkeypatch):
    _week, games = _week_with_games()
    _sitting(client, games, monkeypatch)
    _fire(SITTING + timedelta(minutes=15))

    later = SITTING + timedelta(hours=3)
    at(monkeypatch, later.isoformat())
    _file(client, games[0], side='away')                   # a move
    calls, _run = _fire(later + timedelta(minutes=15))
    assert len(calls) == 1
    assert calls[0]['subject'] == 'Sheet updated: The Docket, Week 1'
    assert 'after your latest change' in calls[0]['plain']
    assert '1. Away 0 +3.5' in calls[0]['plain']
    calls, _run = _fire(later + timedelta(minutes=75))
    assert calls == []


def test_a_removal_after_a_receipt_waits_for_the_sheet_to_refill(
        client, member, monkeypatch):
    _week, games = _week_with_games()
    _sitting(client, games, monkeypatch)
    _fire(SITTING + timedelta(minutes=15))

    later = SITTING + timedelta(hours=3)
    at(monkeypatch, later.isoformat())
    _remove(client, games[3])
    calls, _run = _fire(later + timedelta(minutes=15))
    assert calls == []

    at(monkeypatch, (later + timedelta(minutes=30)).isoformat())
    _file(client, games[9])
    calls, _run = _fire(later + timedelta(minutes=45))
    assert len(calls) == 1
    assert calls[0]['subject'] == 'Sheet updated: The Docket, Week 1'
    assert 'Home 9 -3.5' in calls[0]['plain']


def test_the_noon_firing_waives_the_quiet_period_and_reads_closed(
        client, member, monkeypatch):
    _week, games = _week_with_games()
    _sitting(client, games, monkeypatch, when=DEADLINE - timedelta(minutes=2),
             x2=False, reserve=False)

    calls, run = _fire(DEADLINE)

    assert run.exit_code == 0
    assert len(calls) == 1
    assert calls[0]['subject'] == 'Sheet filed: The Docket, Week 1'
    plain = calls[0]['plain']
    assert 'The docket has closed. This is the sheet you filed.' in plain
    assert 'Closed: Sunday, Sep 6' in plain
    assert 'Deadline:' not in plain
    assert 'Still open when the docket closed' in plain
    assert 'No headliner named.' in plain
    assert 'Still open on your sheet' not in plain
    assert 'change anything until' not in plain
    assert 'filled for you from the locked lines' in plain
    assert _row(member).sent_at == DEADLINE


def test_an_autopicked_sheet_never_gets_a_receipt(client, member, monkeypatch):
    week, games = _week_with_games()
    at(monkeypatch, (DEADLINE - timedelta(minutes=2)).isoformat())
    for game in games[:7]:
        _file(client, game)
    # The deadline pass dealt the eighth side before a late firing read it.
    db.session.add(DocketPick(
        user_id=member.id, week_id=week.id, game_id=games[7].id,
        market='spread', side='home', slot=8, is_autopick=True,
        line_value=games[7].home_spread, book='draftkings'))
    db.session.commit()

    calls, _run = _fire(DEADLINE + timedelta(minutes=5))

    assert calls == []
    assert _row(member).sent_at is None


def test_a_reminder_in_the_same_firing_satisfies_the_receipt(
        client, member, monkeypatch):
    """Eight sides and no x2 is both filed (a receipt is owed) and short (a
    2h reminder is due): the reminder goes, the receipt is marked sent."""
    _week, games = _week_with_games()
    firing = DEADLINE - timedelta(hours=2)
    _sitting(client, games, monkeypatch, when=firing - timedelta(minutes=30),
             x2=False, number=False, reserve=False)

    calls, run = _fire(firing)

    assert [c['subject'] for c in calls] == ['Two hours left: The Docket, Week 1']
    assert run.latched == {'docket': '2h'}
    assert run.delivered_receipts == {}
    assert _row(member).sent_at == firing


def test_a_refused_reminder_leaves_the_receipt_it_would_have_satisfied_owed(
        client, member, monkeypatch):
    """The reminder satisfies the receipt only once it is accepted; a
    refused reminder letter leaves the row owed, so the member is not left
    with neither."""
    _week, games = _week_with_games()
    firing = DEADLINE - timedelta(hours=2)
    _sitting(client, games, monkeypatch, when=firing - timedelta(minutes=30),
             x2=False, number=False, reserve=False)

    calls, patched = capture(accept=lambda to: False)
    with patched:
        run_desk(firing.replace(tzinfo=UTC), anchors=('docket',))

    assert [c['subject'] for c in calls] == ['Two hours left: The Docket, Week 1']
    assert _row(member).sent_at is None


def test_a_dry_run_at_a_reminder_tier_stages_no_receipt_mark(
        client, member, monkeypatch):
    _week, games = _week_with_games()
    firing = DEADLINE - timedelta(hours=2)
    _sitting(client, games, monkeypatch, when=firing - timedelta(minutes=30),
             x2=False, number=False, reserve=False)

    with patch(SEND, side_effect=AssertionError('sent')):
        run = run_desk(firing.replace(tzinfo=UTC), anchors=('docket',),
                       dry_run=True)

    assert [c.letter.subject for c in run.composed] == [
        'Two hours left: The Docket, Week 1']
    assert run.receipts == []
    assert _row(member).sent_at is None


def test_a_refused_send_leaves_the_receipt_owed_for_the_next_firing(
        client, member, monkeypatch):
    _week, games = _week_with_games()
    _sitting(client, games, monkeypatch)

    calls, patched = capture(accept=lambda to: False)
    with patched:
        run = run_desk((SITTING + timedelta(minutes=15)).replace(tzinfo=UTC),
                       anchors=('docket',))
    assert len(calls) == 1
    assert run.exit_code == 0
    assert run.delivered_receipts == {}
    assert _row(member).sent_at is None

    calls, _run = _fire(SITTING + timedelta(minutes=75))
    assert len(calls) == 1
    assert _row(member).sent_at == SITTING + timedelta(minutes=75)


def test_a_firing_without_a_docket_week_drains_nothing(app):
    calls, patched = capture()
    with patched:
        run = run_desk(SITTING.replace(tzinfo=UTC), anchors=('docket',),
                       scheduled=True)
    assert calls == []
    assert run.exit_code == 0
    assert run.receipts == []


def test_a_receipt_is_its_own_letter_beside_another_games_reminder(app):
    """Friday's Survivor warning firing, production flags: a complete Docket
    sheet edited an hour earlier gets its receipt as a second letter; the
    Survivor letter and its latch are the matrix's."""
    seeded = seed('owes', 'complete')
    db.session.add(DocketSheetReceipt(
        user_id=seeded.user.id, week_id=seeded.docket.week4.id,
        touched_at=(F_AT - timedelta(hours=1)).replace(tzinfo=None)))
    db.session.commit()

    calls, patched = capture()
    with patched, patch('games.cfb.services.reminders.send_push'), \
            patch('games.docket.services.reminders.send_push'):
        run = run_desk(F_AT, anchors=('cfb', 'docket'), rides=('F', 'S'))

    assert run.exit_code == 0
    assert [c['subject'] for c in calls] == [
        'Pick due tomorrow: CFB Survivor, Week 4',
        'Sheet filed: The Docket, Week 4',
    ]
    assert run.latched == {'cfb': 'warning'}
    assert run.delivered_receipts == {'docket': 1}


# ── the CLI ────────────────────────────────────────────────────────────────

def test_dry_run_prints_the_receipt_and_writes_nothing(
        app, client, member, monkeypatch):
    _week, games = _week_with_games()
    _sitting(client, games, monkeypatch)
    runner = app.test_cli_runner()
    with patch(SEND, side_effect=AssertionError('sent')):
        result = runner.invoke(args=['club', 'desk', '--dry-run',
                                     '--now', '2026-09-02T07:15',
                                     '--anchor', 'cfb,docket', '--ride', 'F,S'])
    assert result.exit_code == 0, result.output
    assert ('receipt -> member <member@test.com>: '
            '"Sheet filed: The Docket, Week 1"') in result.output
    assert 'would send 0 letter(s) and 1 receipt(s)' in result.output
    assert _row(member).sent_at is None


def test_a_live_run_with_only_receipts_records_ok(
        app, client, member, monkeypatch):
    _week, games = _week_with_games()
    _sitting(client, games, monkeypatch)
    runner = app.test_cli_runner()
    calls, patched = capture()
    with patched:
        result = runner.invoke(args=['club', 'desk',
                                     '--now', '2026-09-02T07:15',
                                     '--anchor', 'cfb,docket', '--ride', 'F,S'])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert 'receipt -> member #' in result.output
    assert 'receipts: 1' in result.output
    run = db.session.scalar(select(SyncRun).order_by(SyncRun.id.desc()))
    assert run.job == 'club-remind'
    assert run.outcome == 'ok'
    assert '1 receipt(s)' in run.summary
