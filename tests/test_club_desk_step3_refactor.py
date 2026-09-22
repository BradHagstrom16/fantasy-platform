"""Club Desk step 3: the seams the refactor added, behind the golden net.

``tests/test_club_desk_step3_regression.py`` holds the letters byte for
byte. This file proves the surface the desk (step 4) builds on:

- ``games.docket.services.opener.open_week`` opens a week with or without
  the announcement (``announce=``), and reports what it did;
- ``run_spread_update(announce=False)`` opens Survivor's week silently and
  leaves the latch for the Paper;
- each game's ``reminder_recipients`` / ``reminder_context`` /
  ``reminder_letter`` build exactly the letter the desk sends (since step 9
  the desk is the only sender; these were the legacy pass's letters);
- the explicit-``now`` Survivor window reader never touches a clock
  (eng review 7A).
"""
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from extensions import db
from games.cfb.models import CfbWeek
from games.cfb.services import reminders as cfb_reminders
from games.cfb.services.reminders import (
    active_reminder_window_at,
    format_time_remaining,
)
from games.club_desk import run_desk
from games.docket.models import DocketWeek
from games.docket.services import reminders as docket_reminders
from games.docket.services.opener import OpenResult, open_week
from tests import _cfb_fixtures as cfb
from tests import _docket_fixtures as docket
from tests.test_cfb_automation import (
    _api_response,
    _bm,
    _odds_event,
    _seed_open_candidates,
)
from utils.email_layout import render_letter

KICK = datetime(2026, 9, 5, 18, 0)
CFB_DEADLINE = datetime(2026, 1, 3, 11, 0)
WARNING_AT = '2026-01-02T16:00:00+00:00'
DOCKET_DEADLINE_UTC = datetime(2026, 9, 6, 17, 0, tzinfo=UTC)


def _capture(target):
    calls = []

    def fake(to, subject, plain, html=None):
        calls.append({'to': to, 'subject': subject, 'plain': plain,
                      'html': html})
        return True

    return calls, patch(target, side_effect=fake)


# ═══════════════════════════════════════════════════════════════════════════
# The Docket opener
# ═══════════════════════════════════════════════════════════════════════════

def _seed_docket_week(monkeypatch):
    """Week 1 with a rule-eligible Labor Day game and one unpaid member,
    the clock pinned at the Tuesday freeze so the rule designates."""
    docket.at(monkeypatch, '2026-09-01T11:05:00')
    week = docket.make_week(1)
    docket.make_game(week, kickoff=KICK, home='Florida State', away='SMU')
    docket.make_game(week, kickoff=datetime(2026, 9, 8, 0, 30),
                     home='Miami', away='LSU', total=47.5)
    docket.make_enrollment(docket.make_user('clerk'))
    db.session.commit()
    return week


def test_open_week_without_announce_imports_designates_and_mails_nobody(
        app, monkeypatch):
    week = _seed_docket_week(monkeypatch)
    sent, patcher = _capture(
        'games.docket.services.notifications.send_platform_email')
    importer = lambda n, force_odds: {'status': 'ok', 'week': n}  # noqa: E731

    with patcher:
        result = open_week(1, announce=False, importer=importer)

    assert isinstance(result, OpenResult)
    assert result.summary == {'status': 'ok', 'week': 1}
    assert result.week is week
    assert result.rule_outcome['status'] == 'designated'
    assert week.tiebreaker_game.away_team == 'LSU'
    assert result.problems == ()
    assert result.announced == 0
    assert sent == []
    assert db.session.get(DocketWeek, week.id).picks_open_notified is False


def test_open_week_with_announce_mails_and_latches(app, monkeypatch):
    week = _seed_docket_week(monkeypatch)
    sent, patcher = _capture(
        'games.docket.services.notifications.send_platform_email')

    with patcher:
        first = open_week(1, importer=lambda n, force_odds: {'status': 'ok'})
        second = open_week(1, importer=lambda n, force_odds: {'status': 'ok'})

    assert first.announced == 1 and second.announced == 0
    assert len(sent) == 1
    assert sent[0]['subject'] == 'Picks are open: The Docket, Week 1'
    assert db.session.get(DocketWeek, week.id).picks_open_notified is True


@pytest.mark.parametrize('status', ['error', 'partial'])
def test_open_week_never_announces_a_failed_or_half_import(
        status, app, monkeypatch):
    week = _seed_docket_week(monkeypatch)
    sent, patcher = _capture(
        'games.docket.services.notifications.send_platform_email')

    with patcher:
        result = open_week(
            1, importer=lambda n, force_odds: {'status': status,
                                               'errors': ['ncaaf down']})

    assert result.week is week          # the rule still ran
    assert result.announced == 0 and sent == []
    assert week.picks_open_notified is False


def test_open_week_reports_no_week_when_the_import_created_none(app):
    result = open_week(3, importer=lambda n, force_odds: {'status': 'error'})
    assert result.week is None
    assert result.rule_outcome is None
    assert result.problems == ()
    assert result.announced == 0


def test_open_week_reports_designation_problems(app, monkeypatch):
    docket.at(monkeypatch, '2026-09-01T11:05:00')
    week = docket.make_week(1)
    docket.make_game(week, kickoff=KICK)      # before the deadline: ineligible
    db.session.commit()

    result = open_week(1, announce=False,
                       importer=lambda n, force_odds: {'status': 'ok'})

    assert result.rule_outcome['status'] == 'none'
    assert result.problems == ('week 1 has no designated tiebreaker game',)


# ═══════════════════════════════════════════════════════════════════════════
# The Survivor opener
# ═══════════════════════════════════════════════════════════════════════════

@patch('games.cfb.services.reminders.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.odds_api.requests.get')
def test_spread_update_without_announce_opens_silently_and_keeps_the_latch(
        mock_get, mock_admin, mock_letter, app):
    from games.cfb.services.automation import run_spread_update
    done, week, game = _seed_open_candidates(app)
    mock_get.return_value = _api_response([
        _odds_event([_bm('draftkings', point=-7.5)]),
    ])

    result = run_spread_update(announce=False)

    assert result['opened'] is True
    assert db.session.get(CfbWeek, week.id).is_active is True
    assert db.session.get(CfbWeek, done.id).is_active is False
    assert game.home_team_spread == -7.5
    assert week.picks_open_notified is False
    assert mock_letter.call_count == 0


@patch('games.cfb.services.reminders.send_platform_email', return_value=True)
@patch('games.cfb.services.automation.send_platform_email', return_value=True)
@patch('games.cfb.services.odds_api.requests.get')
def test_spread_update_default_still_announces(
        mock_get, mock_admin, mock_letter, app):
    """The timers pass nothing: the default is today's behavior."""
    from games.cfb.services.automation import run_spread_update
    _done, week, _game = _seed_open_candidates(app)
    mock_get.return_value = _api_response([
        _odds_event([_bm('draftkings', point=-7.5)]),
    ])

    run_spread_update()

    assert week.picks_open_notified is True
    assert mock_letter.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# Shared reminder builders: the same Letter the legacy pass sends
# ═══════════════════════════════════════════════════════════════════════════

def test_cfb_builders_reproduce_the_desk_reminder(app):
    app.config['SITE_URL'] = 'https://cccfantasy.com'
    week = cfb.make_week(2, deadline=CFB_DEADLINE, is_active=True)
    user = cfb.make_user('needs')
    enrollment = cfb.make_enrollment(user, lives=1)
    enrollment.cumulative_spread = 18.5
    picked = cfb.make_user('picked')
    cfb.make_enrollment(picked)
    cfb.make_pick(picked, week, cfb.make_team('Team A'))
    db.session.commit()

    now = datetime.fromisoformat(WARNING_AT)
    recipients = cfb_reminders.reminder_recipients(week, 'warning', now)
    assert [(e.user_id, u.username) for e, u in recipients] == [
        (user.id, 'needs')]
    context = cfb_reminders.reminder_context(week, now)
    assert context['week_name'] == 'Week 2'
    assert context['deadline_short'] == 'Saturday, Jan 3 · 11:00 AM CT'
    assert context['pick_url'] == 'https://cccfantasy.com/cfb/pick/2'
    built = render_letter(
        cfb_reminders.reminder_letter(recipients[0], context, 'warning'))

    sent, patcher = _capture('games.club_desk.send_platform_email')
    with patcher:
        run_desk(now, anchors=('cfb',), rides=())
    assert [m['to'] for m in sent] == ['needs@test.com']
    desk = sent[0]
    assert desk['subject'] == 'Pick due tomorrow: CFB Survivor, Week 2'
    assert (desk['plain'], desk['html']) == built
    assert 'Lives: 1 of 2' in built[0] and 'Cumulative spread: 18.5' in built[0]


def test_docket_builders_reproduce_the_desk_reminder(app):
    app.config['SITE_URL'] = 'https://cccfantasy.com'
    week = docket.make_week(1)
    docket.make_game(week, kickoff=KICK)
    user = docket.make_user('clerk')
    docket.make_enrollment(user)
    db.session.commit()

    now = (DOCKET_DEADLINE_UTC - timedelta(hours=24)).replace(tzinfo=None)
    recipients = docket_reminders.reminder_recipients(week, '24h', now)
    assert [(u.id, items) for u, items in recipients] == [
        (user.id, ['Sides committed: 0 of 8.', 'No headliner named.',
                   'No combined-score number recorded.'])]
    context = docket_reminders.reminder_context(week)
    assert context['deadline'] == 'Sunday, Sep 6 · 12:00 PM CT'
    assert context['link'] == 'https://cccfantasy.com/docket/'
    built = render_letter(
        docket_reminders.reminder_letter(recipients[0], context, '24h'))

    sent, patcher = _capture('games.club_desk.send_platform_email')
    with patcher:
        run = run_desk(DOCKET_DEADLINE_UTC - timedelta(hours=24),
                       anchors=('docket',), rides=())
    assert run.latched == {'docket': '24h'}
    assert sent[0]['subject'] == 'Closes tomorrow: The Docket, Week 1'
    assert (sent[0]['plain'], sent[0]['html']) == built


def test_docket_recipients_honour_the_narrowed_roster(app):
    week = docket.make_week(1)
    docket.make_game(week, kickoff=KICK)
    a, b = docket.make_user('a'), docket.make_user('b')
    docket.make_enrollment(a)
    docket.make_enrollment(b)
    db.session.commit()

    only_b = docket_reminders.reminder_recipients(
        week, '48h', datetime(2026, 9, 4, 17, 0), user_ids=[b.id])
    assert [u.id for u, _ in only_b] == [b.id]
    everyone = docket_reminders.reminder_recipients(
        week, '48h', datetime(2026, 9, 4, 17, 0))
    assert [u.id for u, _ in everyone] == [a.id, b.id]


# ═══════════════════════════════════════════════════════════════════════════
# The explicit-now window reader never reads a clock (7A)
# ═══════════════════════════════════════════════════════════════════════════

def _clock_forbidden():
    return patch('games.cfb.services.reminders.get_current_time',
                 side_effect=AssertionError('hidden clock read'))


@pytest.mark.parametrize('offset, expected', [
    (timedelta(hours=26, minutes=36), None),
    (timedelta(hours=26, minutes=35), 'warning'),
    (timedelta(hours=25), 'warning'),
    (timedelta(hours=24, minutes=25), 'warning'),
    (timedelta(hours=24, minutes=24), None),
    (timedelta(hours=12), None),
    (timedelta(hours=2, minutes=36), None),
    (timedelta(hours=2, minutes=35), 'final'),
    (timedelta(hours=1), 'final'),
    (timedelta(minutes=25), 'final'),
    (timedelta(minutes=24), None),
    (timedelta(0), None),
    (-timedelta(minutes=1), None),
])
def test_explicit_reader_matches_the_windows_without_a_clock(
        offset, expected):
    deadline = datetime(2026, 1, 3, 17, 0, tzinfo=UTC)
    with _clock_forbidden():
        window = active_reminder_window_at(deadline, deadline - offset)
    assert (window['type'] if window else None) == expected


def test_format_time_remaining_takes_an_explicit_now():
    deadline = datetime(2026, 1, 3, 17, 0, tzinfo=UTC)
    with _clock_forbidden():
        assert format_time_remaining(
            deadline, deadline - timedelta(hours=26, minutes=5)) == \
            '1 day, 2 hours'
        assert format_time_remaining(
            deadline, deadline - timedelta(minutes=55)) == '55 minutes'


def test_legacy_readers_still_read_the_pool_clock(app):
    """The wrappers the legacy pass and tests/test_cfb_time_seam.py use keep
    reading get_current_time (through the CFB_FAKE_NOW seam)."""
    deadline = datetime(2026, 1, 3, 17, 0, tzinfo=UTC)
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'CFB_FAKE_NOW': '2026-01-03T16:00:00+00:00'}):
        assert cfb_reminders.get_active_reminder_window(deadline)['type'] == 'final'
        assert cfb_reminders.should_send_reminder(deadline, 1) is True
        assert cfb_reminders.format_time_remaining(deadline) == '1 hour, 0 minutes'
