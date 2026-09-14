"""Deadline-nag pushes for both games (PR 4, T11).

The nag buzzes the same recipients as the reminder email, regardless of the
email outcome (a mail outage is exactly when push matters), carrying the red
badge (app_badge=1), a per-week tag that replaces an earlier tier on the
device, a topic that collapses queued messages, and a TTL to the deadline.
send_push and email are patched; nothing here needs VAPID or SMTP.
"""
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import tests._cfb_fixtures as cfbf
import tests._docket_fixtures as dkf
from extensions import db
from games.cfb.services.reminders import _push_pick_nag, run_reminder_check
from games.cfb.utils import make_aware
from games.docket.services.reminders import _push_deadline_nag, run_reminder_pass

_CFB_PUSH = 'games.cfb.services.reminders.send_push'
_DK_PUSH = 'games.docket.services.reminders.send_push'
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
    assert 'due' in kw['title'].lower()


def test_cfb_nag_payload_final_changes_the_body(app):
    week = cfbf.make_week(1, deadline=_CFB_DEADLINE)
    db.session.commit()
    deadline = make_aware(week.deadline)
    now = deadline - timedelta(hours=1)
    with patch(_CFB_PUSH) as sp:
        _push_pick_nag(week, {'type': 'final'}, deadline, now, [7])
    kw = sp.call_args.kwargs
    assert 'Last call' in kw['title']
    assert 'hour' in kw['body']


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
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'CFB_FAKE_NOW': _CFB_WARNING_NOW}), \
            patch('games.cfb.services.reminders.send_platform_email',
                  return_value=False), \
            patch(_CFB_PUSH) as sp:
        run_reminder_check()
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


def test_docket_nag_2h_body_differs(app):
    week = dkf.make_week(1)
    db.session.commit()
    now_naive = week.deadline_at - timedelta(hours=2)
    with patch(_DK_PUSH) as sp:
        _push_deadline_nag(week, '2h', now_naive, [7])
    assert 'Last call' in sp.call_args.kwargs['title']


def test_docket_nag_fires_even_when_email_fails(app):
    week = dkf.make_week(1)
    user = dkf.make_user('needs')
    dkf.make_enrollment(user)
    db.session.commit()
    now = (week.deadline_at - timedelta(hours=24)).replace(tzinfo=UTC)
    with patch('games.docket.services.reminders.send_each', return_value=0), \
            patch(_DK_PUSH) as sp:
        result = run_reminder_pass(week, now=now, user_ids=[user.id])
    # The email pass reports the outage, but the buzz still went out.
    assert result['status'] == 'send_failed'
    assert sp.call_count == 1
    assert sp.call_args.args[0] == [user.id]
    assert sp.call_args.kwargs['app_badge'] == 1
    assert sp.call_args.kwargs['tag'] == 'docket-w1-nag'
