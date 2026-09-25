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
from games.cfb.services.reminders import _push_pick_nag
from games.cfb.utils import make_aware
from games.club_desk import run_desk
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
    assert kw['body'] == 'Last call for Week 1. No pick on file.'


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
    assert kw['body'] == 'One day to go. Sides still open.'


def test_docket_nag_2h_body_differs(app):
    week = dkf.make_week(1)
    db.session.commit()
    now_naive = week.deadline_at - timedelta(hours=2)
    with patch(_DK_PUSH) as sp:
        _push_deadline_nag(week, '2h', now_naive, [7])
    kw = sp.call_args.kwargs
    assert kw['title'] == 'Docket closes in 2 hrs'
    assert kw['body'] == 'Last call for Week 1. Sides still open.'


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


# ---- The one-line title grammar (layout pass 2026-09-25) --------------------
# iOS stacks title / "from CCC" / body, and truncates the title to one line.
# The title carries the whole message and the body stays one short line: at a
# 375pt phone that is about 33 characters of title beside the timestamp and 44
# of body.

TITLE_BUDGET = 33
BODY_BUDGET = 44


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
    """The longest real copy of each tier: an 11:30 kickoff-shaped deadline
    and the widest time-left phrase either final window can print."""
    cfb_week = cfbf.make_week(14, deadline=datetime(2026, 11, 28, 11, 30))
    dk_week = dkf.make_week(1)
    db.session.commit()
    deadline = make_aware(cfb_week.deadline)
    payloads = []
    with patch(_CFB_PUSH) as cfb_sp, patch(_DK_PUSH) as dk_sp:
        _push_pick_nag(cfb_week, {'type': 'warning'}, deadline,
                       deadline - timedelta(hours=25), [7])
        _push_pick_nag(cfb_week, {'type': 'final'}, deadline,
                       deadline - timedelta(hours=2, minutes=30), [7])
        for tier, back in (('48h', 48), ('24h', 24), ('2h', 2.5)):
            _push_deadline_nag(dk_week, tier,
                               dk_week.deadline_at - timedelta(hours=back), [7])
    payloads = [c.kwargs for c in cfb_sp.call_args_list + dk_sp.call_args_list]
    assert len(payloads) == 5
    for kw in payloads:
        assert len(kw['title']) <= TITLE_BUDGET, kw['title']
        assert len(kw['body']) <= BODY_BUDGET, kw['body']
