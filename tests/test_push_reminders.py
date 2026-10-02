"""Deadline-nag pushes for both games (PR 4, T11).

The nag buzzes the same recipients as the reminder email, regardless of the
email outcome (a mail outage is exactly when push matters), carrying the red
badge (app_badge=1), a per-week tag that replaces an earlier tier on the
device, a topic that collapses queued messages, and a TTL to the deadline.
send_push and email are patched; nothing here needs VAPID or SMTP.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

import tests._cfb_fixtures as cfbf
import tests._docket_fixtures as dkf
from extensions import db
from games.cfb.constants import season_schedule
from games.cfb.services.reminders import _push_pick_nag
from games.cfb.utils import make_aware
from games.club_desk import run_desk
from games.docket.models import DocketPick
from games.docket.services.reminders import _push_deadline_nag
from utils.time import format_deadline_compact, format_time_left_compact

_CFB_PUSH = 'games.cfb.services.reminders.send_push'
_DK_PUSH = 'games.docket.services.reminders.send_push'
# Both games' reminders send from the Club Desk (ADR-065 step 9); the push
# still goes out from each game's own module.
_DESK_SEND = 'games.club_desk.send_platform_email'
_CFB_DEADLINE = datetime(2026, 1, 3, 11, 0)          # pool wall clock
_CFB_WARNING_NOW = '2026-01-02T16:00:00+00:00'       # exactly T-25h


# ---- CFB nag payload -------------------------------------------------------

def test_cfb_nag_payload_warning(app):
    week = cfbf.make_week(1, deadline=_CFB_DEADLINE)
    db.session.commit()
    deadline = make_aware(week.deadline)
    now = deadline - timedelta(hours=25)
    with patch(_CFB_PUSH) as sp:
        _push_pick_nag(week, {'type': 'warning'}, deadline, now, [7])
    kw = sp.call_args.kwargs
    assert sp.call_args.args[0] == [7]
    assert kw['tag'] == 'cfb-w1-nag'
    assert kw['topic'] == 'cfb-w1'
    assert kw['app_badge'] == 1
    assert kw['urgency'] == 'normal'
    assert kw['ttl'] > 0
    assert kw['url'] == '/cfb/pick/1'
    # The title carries the message on one line; the body is one short line.
    assert kw['title'] == 'CFB pick due Sat 11 AM CT'
    assert kw['body'] == 'Week 1: no pick on file yet.'


def test_cfb_nag_payload_final_changes_the_body(app):
    week = cfbf.make_week(1, deadline=_CFB_DEADLINE)
    db.session.commit()
    deadline = make_aware(week.deadline)
    now = deadline - timedelta(hours=1)
    with patch(_CFB_PUSH) as sp:
        _push_pick_nag(week, {'type': 'final'}, deadline, now, [7])
    kw = sp.call_args.kwargs
    assert kw['title'] == 'CFB pick locks in 1 hr'
    # The final states what a miss costs, in MISS_RULE's voice.
    assert kw['body'] == ('No pick for Week 1. Miss it and the Commish picks '
                          'your biggest favorite left.')


def test_cfb_nag_empty_recipients_is_noop(app):
    week = cfbf.make_week(1, deadline=_CFB_DEADLINE)
    db.session.commit()
    with patch(_CFB_PUSH) as sp:
        _push_pick_nag(week, {'type': 'warning'}, make_aware(week.deadline),
                       make_aware(week.deadline) - timedelta(hours=25), [])
    sp.assert_not_called()


def test_cfb_nag_fires_even_when_email_fails(app):
    cfbf.make_week(1, deadline=_CFB_DEADLINE, is_active=True)
    user = cfbf.make_user('needs')
    cfbf.make_enrollment(user)
    db.session.commit()
    with patch(_DESK_SEND, return_value=False), patch(_CFB_PUSH) as sp:
        run = run_desk(datetime.fromisoformat(_CFB_WARNING_NOW),
                       anchors=('cfb',), rides=())
    # The email outage is loud (exit 1), but the buzz still went out.
    assert run.exit_code == 1 and run.delivered == {}
    assert sp.call_count == 1
    assert sp.call_args.args[0] == [user.id]
    assert sp.call_args.kwargs['app_badge'] == 1
    assert sp.call_args.kwargs['tag'] == 'cfb-w1-nag'


# ---- Docket nag payload ----------------------------------------------------

def test_docket_nag_payload(app):
    week = dkf.make_week(1)
    db.session.commit()
    now_naive = week.deadline_at - timedelta(hours=24)
    with patch(_DK_PUSH) as sp:
        _push_deadline_nag(week, '24h', now_naive, [7])
    kw = sp.call_args.kwargs
    assert sp.call_args.args[0] == [7]
    assert kw['tag'] == 'docket-w1-nag'
    assert kw['topic'] == 'docket-w1'
    assert kw['app_badge'] == 1
    assert kw['urgency'] == 'normal'
    assert kw['ttl'] > 0
    assert kw['url'] == '/docket/'
    assert kw['title'] == 'Docket closes Sun 12 PM CT'
    # The body is this member's next step, in the sheet's words.
    assert kw['body'] == 'Week 1: no sides picked yet.'


def test_docket_nag_2h_body_differs(app):
    week = dkf.make_week(1)
    db.session.commit()
    now_naive = week.deadline_at - timedelta(hours=2)
    with patch(_DK_PUSH) as sp:
        _push_deadline_nag(week, '2h', now_naive, [7])
    kw = sp.call_args.kwargs
    assert kw['title'] == 'Docket closes in 2 hrs'
    assert kw['body'] == 'Last call for Week 1. No sides picked yet.'


def _dk_sheet(user, week, sides, *, best=False):
    """A sheet with ``sides`` scoring picks, one per game, the first as x2
    when ``best``."""
    for slot in range(1, sides + 1):
        game = dkf.make_game(week, kickoff=week.deadline_at + timedelta(hours=1))
        db.session.add(DocketPick(
            user_id=user.id, week_id=week.id, game_id=game.id,
            market='spread', side='home', slot=slot, line_value=-3.5,
            book='draftkings', is_best=best and slot == 1))
    db.session.flush()


def test_docket_nag_body_is_each_members_next_step(app):
    """One push per member, each naming what that sheet still owes: sides
    first, then the x2, then the tiebreaker number (picks.next_step's
    ladder)."""
    week = dkf.make_week(1)
    short, no_x2, no_number = (dkf.make_user(n)
                               for n in ('short', 'nox2', 'nonumber'))
    _dk_sheet(short, week, 7)
    _dk_sheet(no_x2, week, 8)
    _dk_sheet(no_number, week, 8, best=True)
    db.session.commit()
    now_naive = week.deadline_at - timedelta(hours=48)
    with patch(_DK_PUSH) as sp:
        _push_deadline_nag(week, '48h', now_naive,
                           [short.id, no_x2.id, no_number.id])
    bodies = {c.args[0][0]: c.kwargs['body'] for c in sp.call_args_list}
    assert bodies == {
        short.id: 'Week 1: 1 more side to pick.',
        no_x2.id: 'Week 1: now pick your x2.',
        no_number.id: 'Week 1: now your tiebreaker number.',
    }


def test_docket_nag_fires_even_when_email_fails(app):
    week = dkf.make_week(1)
    user = dkf.make_user('needs')
    dkf.make_enrollment(user)
    db.session.commit()
    now = (week.deadline_at - timedelta(hours=24)).replace(tzinfo=UTC)
    with patch(_DESK_SEND, return_value=False), patch(_DK_PUSH) as sp:
        run = run_desk(now, anchors=('docket',), rides=())
    # The email outage is loud (exit 1), but the buzz still went out.
    assert run.exit_code == 1 and run.delivered == {}
    assert sp.call_count == 1
    assert sp.call_args.args[0] == [user.id]
    assert sp.call_args.kwargs['app_badge'] == 1
    assert sp.call_args.kwargs['tag'] == 'docket-w1-nag'


def test_docket_nag_skips_an_unreadable_sheet_and_never_raises(app):
    """The desk calls the push unguarded before it latches the tier, so a
    member whose sheet read fails is skipped, never raised."""
    week = dkf.make_week(1)
    db.session.commit()
    now_naive = week.deadline_at - timedelta(hours=24)
    reads = [RuntimeError('db hiccup'), {'scoring_count': 3, 'best': None}]
    with patch('games.docket.services.reminders.sheet_state',
               side_effect=reads), patch(_DK_PUSH) as sp:
        _push_deadline_nag(week, '24h', now_naive, [7, 8])
    assert [c.args[0] for c in sp.call_args_list] == [[8]]
    assert sp.call_args.kwargs['body'] == 'Week 1: 5 more sides to pick.'


# ---- The one-line title grammar (layout pass 2026-09-25) --------------------
# iOS stacks title / "from CCC" / body, and truncates the title to one line:
# at a 375pt phone that is about 33 characters beside the timestamp. The body
# wraps, and gets up to two lines of 44 (clarify pass 2026-09-29: a one-line
# body left "from CCC" as the loudest thing under the title, so the body now
# carries the member's own next step or what a miss costs).

TITLE_BUDGET = 33
BODY_BUDGET = 2 * 44


@pytest.mark.parametrize('when, compact', [
    (datetime(2026, 9, 26, 16, 0, tzinfo=UTC), 'Sat 11 AM CT'),
    (datetime(2026, 9, 26, 16, 30, tzinfo=UTC), 'Sat 11:30 AM CT'),
    (datetime(2026, 9, 27, 17, 0), 'Sun 12 PM CT'),        # naive = UTC
    (datetime(2026, 12, 5, 17, 0), 'Sat 11 AM CT'),        # CST folds to CT
])
def test_format_deadline_compact(when, compact):
    assert format_deadline_compact(when) == compact


@pytest.mark.parametrize('left, phrase', [
    (timedelta(hours=2), '2 hrs'),
    (timedelta(hours=2, minutes=30), '2 hrs 30 min'),
    (timedelta(hours=1), '1 hr'),
    (timedelta(hours=1, minutes=44), '1 hr 45 min'),
    (timedelta(minutes=25), '30 min'),
    (timedelta(minutes=3), '15 min'),                      # never "0 min"
])
def test_format_time_left_compact(left, phrase):
    deadline = datetime(2026, 9, 26, 16, 0)
    assert format_time_left_compact(deadline, deadline - left) == phrase


def test_every_nag_fits_the_one_line_budget(app):
    """The longest real copy of each tier: an 11:30 kickoff-shaped deadline,
    the widest time-left phrase either final window can print, and every
    CFB week name, the round names up to "Conference Championship Week"."""
    cfb_weeks = [cfbf.make_week(13, deadline=datetime(2026, 11, 28, 11, 30))]
    for number, special in season_schedule(2026)['special_weeks'].items():
        week = cfbf.make_week(number, deadline=datetime(2026, 11, 28, 11, 30))
        week.round_name = special['name']
        cfb_weeks.append(week)
    dk_week = dkf.make_week(1)
    db.session.commit()
    with patch(_CFB_PUSH) as cfb_sp, patch(_DK_PUSH) as dk_sp:
        for cfb_week in cfb_weeks:
            deadline = make_aware(cfb_week.deadline)
            _push_pick_nag(cfb_week, {'type': 'warning'}, deadline,
                           deadline - timedelta(hours=25), [7])
            _push_pick_nag(cfb_week, {'type': 'final'}, deadline,
                           deadline - timedelta(hours=2, minutes=30), [7])
        for tier, back in (('48h', 48), ('24h', 24), ('2h', 2.5)):
            _push_deadline_nag(dk_week, tier,
                               dk_week.deadline_at - timedelta(hours=back), [7])
    payloads = [c.kwargs for c in cfb_sp.call_args_list + dk_sp.call_args_list]
    assert len(payloads) == 2 * len(cfb_weeks) + 3
    bodies = {kw['body'] for kw in payloads}
    assert 'Conference Championship Week: no pick yet.' in bodies
    assert ('No pick yet. Miss it and the Commish picks your biggest '
            'favorite left.') in bodies
    for kw in payloads:
        assert len(kw['title']) <= TITLE_BUDGET, kw['title']
        assert len(kw['body']) <= BODY_BUDGET, kw['body']
