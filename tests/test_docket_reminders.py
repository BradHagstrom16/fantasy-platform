"""The Docket deadline reminders (D24).

The lock this file exists for is no-double-send: the reminder timer fires
hourly and each tier's window is 70 minutes wide, so a run inside an
already-sent tier MUST send nothing. That guarantee has to live in
DocketWeek.last_reminder_tier and not in the schedule, because a schedule is
one deploy away from changing.

Mail is faked at games.docket.services.notifications.send_platform_email —
the read site, per the platform mocking convention. Patching utils.email
would be a silent no-op here.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from extensions import db
from games.docket.models import DocketPick, DocketTiebreakerPrediction
from games.docket.services.reminders import (
    active_window,
    outstanding,
    run_reminder_pass,
)
from tests._docket_fixtures import (
    WEEK1_DEADLINE_UTC,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

KICK = datetime(2026, 9, 5, 18, 0)

# Instants inside each tier's window, as naive UTC (deadline is Sat Sep 5
# 11:00 CT == 16:00 UTC).
AT_48H = WEEK1_DEADLINE_UTC - timedelta(hours=48)
AT_24H = WEEK1_DEADLINE_UTC - timedelta(hours=24)
AT_2H = WEEK1_DEADLINE_UTC - timedelta(hours=2)


def _seed(games=9):
    week = make_week(1)
    rows = [
        make_game(week, kickoff=KICK, home=f'Home {i}', away=f'Away {i}',
                  home_spread=-(3.5 + i), total=40.5 + i)
        for i in range(games)
    ]
    week.tiebreaker_game_id = rows[0].id
    db.session.commit()
    return week, rows


def _hold(user, week, game, slot, *, is_best=False):
    db.session.add(DocketPick(
        user_id=user.id, week_id=week.id, game_id=game.id,
        market='spread', side='home', slot=slot, is_best=is_best,
        is_autopick=False, line_value=game.home_spread,
        book=game.spread_book))


def _finish_sheet(user, week, games):
    """Eight sides, a headliner, and a number: nothing outstanding."""
    for slot, game in enumerate(games[:8], start=1):
        _hold(user, week, game, slot, is_best=(slot == 1))
    db.session.add(DocketTiebreakerPrediction(
        user_id=user.id, week_id=week.id, prediction_tenths=515))
    db.session.commit()


@pytest.fixture()
def sent():
    """Collect (recipient, subject) for every accepted send."""
    calls = []

    def fake(to, subject, plain, html):
        calls.append((to, subject))
        return True

    with patch('games.docket.services.notifications.send_platform_email',
               side_effect=fake):
        yield calls


def test_two_runs_in_one_tier_send_once(app, sent):
    """THE D24 lock. The hourly timer lands in a 70-minute window more than
    once; the sent flag is what makes the second landing silent."""
    week, _games = _seed()
    user = make_user('unfinished')
    make_enrollment(user)
    db.session.commit()

    first = run_reminder_pass(week, now=AT_48H)
    second = run_reminder_pass(week, now=AT_48H + timedelta(minutes=30))

    assert first['status'] == 'sent'
    assert first['sent'] == 1
    assert second['status'] == 'already_sent'
    assert len(sent) == 1, 'the same tier must never mail a player twice'
    assert week.last_reminder_tier == '48h'


def test_each_tier_sends_once_as_the_deadline_closes(app, sent):
    week, _games = _seed()
    user = make_user('unfinished')
    make_enrollment(user)
    db.session.commit()

    statuses = [run_reminder_pass(week, now=instant)['status']
                for instant in (AT_48H, AT_24H, AT_2H)]

    assert statuses == ['sent', 'sent', 'sent']
    assert len(sent) == 3
    assert week.last_reminder_tier == '2h'


def test_a_later_run_never_reopens_an_earlier_tier(app, sent):
    """Ordering, not equality: once 2h has gone out, a 48h-window run (a
    Persistent=true catch-up firing after a reboot) must stay silent."""
    week, _games = _seed()
    user = make_user('unfinished')
    make_enrollment(user)
    db.session.commit()

    run_reminder_pass(week, now=AT_2H)
    replay = run_reminder_pass(week, now=AT_48H)

    assert replay['status'] == 'already_sent'
    assert len(sent) == 1


def test_finished_sheet_is_not_a_recipient(app, sent):
    week, games = _seed()
    done = make_user('finished')
    make_enrollment(done)
    db.session.commit()
    _finish_sheet(done, week, games)

    result = run_reminder_pass(week, now=AT_48H)

    assert result['status'] == 'all_complete'
    assert sent == []
    assert week.last_reminder_tier is None, (
        'nothing was mailed, so the tier stays open for a player who '
        'withdraws a side later in the same window')


def test_only_unfinished_sheets_are_mailed(app, sent):
    week, games = _seed()
    done = make_user('finished')
    short = make_user('unfinished')
    make_enrollment(done)
    make_enrollment(short)
    db.session.commit()
    _finish_sheet(done, week, games)

    result = run_reminder_pass(week, now=AT_24H)

    assert result == {'status': 'sent', 'week_number': 1, 'tier': '24h',
                      'recipients': 1, 'sent': 1}
    assert [to for to, _subject in sent] == [short.email]


def test_total_send_failure_leaves_the_tier_open(app):
    """A mail outage must not be recorded as delivery, or the next hourly
    run would skip the tier and nobody would ever be told."""
    week, _games = _seed()
    user = make_user('unfinished')
    make_enrollment(user)
    db.session.commit()

    with patch('games.docket.services.notifications.send_platform_email',
               return_value=False):
        failed = run_reminder_pass(week, now=AT_48H)
    assert failed['status'] == 'send_failed'
    assert week.last_reminder_tier is None

    with patch('games.docket.services.notifications.send_platform_email',
               return_value=True):
        retried = run_reminder_pass(week, now=AT_48H + timedelta(minutes=20))
    assert retried['status'] == 'sent'
    assert week.last_reminder_tier == '48h'


def test_partial_send_failure_still_records_the_tier(app):
    """One permanently bad address must not hold the tier open: that would
    re-mail every good recipient on the next firing (Golf's reasoning)."""
    week, _games = _seed()
    for name in ('alice', 'bob'):
        make_enrollment(make_user(name))
    db.session.commit()

    accepted = []

    def fake(to, subject, plain, html):
        ok = to != 'alice@test.com'
        if ok:
            accepted.append(to)
        return ok

    with patch('games.docket.services.notifications.send_platform_email',
               side_effect=fake):
        result = run_reminder_pass(week, now=AT_48H)

    assert result['sent'] == 1 and result['recipients'] == 2
    assert week.last_reminder_tier == '48h'
    assert accepted == ['bob@test.com']


def test_a_closed_week_sends_nothing(app, sent):
    week, _games = _seed()
    make_enrollment(make_user('unfinished'))
    db.session.commit()

    result = run_reminder_pass(week, now=WEEK1_DEADLINE_UTC)

    assert result['status'] == 'closed'
    assert sent == []


def test_between_tiers_sends_nothing(app, sent):
    week, _games = _seed()
    make_enrollment(make_user('unfinished'))
    db.session.commit()

    result = run_reminder_pass(week, now=WEEK1_DEADLINE_UTC
                               - timedelta(hours=12))

    assert result['status'] == 'no_window'
    assert sent == []


@pytest.mark.parametrize('hours,expected', [
    (49, None), (48, '48h'), (47.5, '48h'),
    (24, '24h'), (12, None), (2, '2h'), (0.25, None),
])
def test_active_window_boundaries(hours, expected):
    now = WEEK1_DEADLINE_UTC - timedelta(hours=hours)
    window = active_window(WEEK1_DEADLINE_UTC, now)
    assert (window['tier'] if window else None) == expected


def test_outstanding_lists_the_three_obligations(app):
    """The reserve is prudence, not an obligation (DESIGN.md 1.5): a sheet
    with eight sides, a headliner and a number owes nothing even with slot 9
    empty."""
    empty = {'scoring_count': 0, 'best': None, 'prediction': None}
    assert outstanding(empty) == [
        'Sides committed: 0 of 8.',
        'No headliner named.',
        'No combined-score number recorded.',
    ]
    complete = {'scoring_count': 8, 'best': {'slot': 1}, 'prediction': '51.5'}
    assert outstanding(complete) == []
