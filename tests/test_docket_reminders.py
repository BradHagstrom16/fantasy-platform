"""The Docket deadline reminders (D24), as the Club Desk sends them.

The lock this file exists for is no-double-send: the reminder timer fires
hourly and each tier's window is 70 minutes wide, so a run inside an
already-sent tier MUST send nothing. That guarantee has to live in
DocketWeek.last_reminder_tier and not in the schedule, because a schedule is
one deploy away from changing.

Since ADR-065 step 9 the send loop is the desk's (games/club_desk.py) and
this module supplies the tiers, recipients and letter; a Docket-only firing
(`--anchor docket`, no rides) is the legacy pass's exact contract. The
cross-game rules (riders, pre-marks) live in tests/test_club_desk*.py.

Mail is faked at games.club_desk.send_platform_email — the read site, per the
platform mocking convention. Patching utils.email would be a silent no-op.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from extensions import db
from games.club_desk import run_desk
from games.docket.models import DocketPick, DocketTiebreakerPrediction
from games.docket.services.reminders import active_window, outstanding
from tests._docket_fixtures import (
    WEEK1_DEADLINE_UTC,
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

KICK = datetime(2026, 9, 5, 18, 0)
DESK_SEND = 'games.club_desk.send_platform_email'
NO_PUSH = 'games.docket.services.reminders.send_push'

# Instants inside each tier's window, as naive UTC (deadline is Sun Sep 6
# 12:00 CT == 17:00 UTC).
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


def _pass(now_naive_utc):
    """One Docket-only desk firing at ``now`` (naive UTC, like the deadline
    column). Returns the run: ``anchors`` empty means no tier was due or
    the due tier is already sent; ``exit_code`` 1 means the tier reached
    nobody; ``latched`` names what was recorded."""
    with patch(NO_PUSH):
        return run_desk(now_naive_utc.replace(tzinfo=UTC),
                        anchors=('docket',), rides=())


@pytest.fixture()
def sent():
    """Collect (recipient, subject) for every accepted send."""
    calls = []

    def fake(to, subject, plain, html):
        calls.append((to, subject))
        return True

    with patch(DESK_SEND, side_effect=fake):
        yield calls


def test_two_runs_in_one_tier_send_once(app, sent):
    """THE D24 lock. The hourly timer lands in a 70-minute window more than
    once; the sent flag is what makes the second landing silent."""
    week, _games = _seed()
    user = make_user('unfinished')
    make_enrollment(user)
    db.session.commit()

    first = _pass(AT_48H)
    second = _pass(AT_48H + timedelta(minutes=30))

    assert first.delivered == {'docket': 1} and first.latched == {'docket': '48h'}
    assert second.anchors == [] and second.delivered == {}
    assert len(sent) == 1, 'the same tier must never mail a player twice'
    assert week.last_reminder_tier == '48h'


def test_each_tier_sends_once_as_the_deadline_closes(app, sent):
    week, _games = _seed()
    user = make_user('unfinished')
    make_enrollment(user)
    db.session.commit()

    latched = [_pass(instant).latched.get('docket')
               for instant in (AT_48H, AT_24H, AT_2H)]

    assert latched == ['48h', '24h', '2h']
    assert len(sent) == 3
    assert week.last_reminder_tier == '2h'


def test_a_later_run_never_reopens_an_earlier_tier(app, sent):
    """Ordering, not equality: once 2h has gone out, a 48h-window run (a
    Persistent=true catch-up firing after a reboot) must stay silent."""
    week, _games = _seed()
    user = make_user('unfinished')
    make_enrollment(user)
    db.session.commit()

    _pass(AT_2H)
    replay = _pass(AT_48H)

    assert replay.anchors == []
    assert len(sent) == 1
    assert week.last_reminder_tier == '2h'


def test_finished_sheet_is_not_a_recipient(app, sent):
    week, games = _seed()
    done = make_user('finished')
    make_enrollment(done)
    db.session.commit()
    _finish_sheet(done, week, games)

    run = _pass(AT_48H)

    assert [a.tier for a in run.anchors] == ['48h'], 'the tier was due'
    assert sent == [] and run.exit_code == 0
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

    run = _pass(AT_24H)

    assert run.recipients == {'docket': 1} and run.delivered == {'docket': 1}
    assert run.latched == {'docket': '24h'}
    assert [to for to, _subject in sent] == [short.email]


def test_total_send_failure_leaves_the_tier_open(app):
    """A mail outage must not be recorded as delivery, or the next hourly
    run would skip the tier and nobody would ever be told."""
    week, _games = _seed()
    user = make_user('unfinished')
    make_enrollment(user)
    db.session.commit()

    with patch(DESK_SEND, return_value=False):
        failed = _pass(AT_48H)
    assert failed.exit_code == 1 and failed.delivered == {}
    assert week.last_reminder_tier is None

    with patch(DESK_SEND, return_value=True):
        retried = _pass(AT_48H + timedelta(minutes=20))
    assert retried.exit_code == 0 and retried.latched == {'docket': '48h'}
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

    with patch(DESK_SEND, side_effect=fake):
        run = _pass(AT_48H)

    assert run.recipients == {'docket': 2} and run.delivered == {'docket': 1}
    assert run.exit_code == 0
    assert week.last_reminder_tier == '48h'
    assert accepted == ['bob@test.com']


def test_a_closed_week_sends_nothing(app, sent):
    week, _games = _seed()
    make_enrollment(make_user('unfinished'))
    db.session.commit()

    run = _pass(WEEK1_DEADLINE_UTC)

    assert run.anchors == [] and sent == []
    assert week.last_reminder_tier is None


def test_between_tiers_sends_nothing(app, sent):
    week, _games = _seed()
    make_enrollment(make_user('unfinished'))
    db.session.commit()

    run = _pass(WEEK1_DEADLINE_UTC - timedelta(hours=12))

    assert run.anchors == [] and sent == []
    assert week.last_reminder_tier is None


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
