"""The Docket — the "Picks Are Open" announcement email.

When a week is imported (the Tuesday setup/lines run), the whole roster is
told picks are open — exactly once, latched on
``DocketWeek.picks_open_notified``. The latch is also what protects the
preview Week-1 row: the migration back-fills it True so an enabled timer
does not announce a stale week before the Sep 1 wipe, and after the wipe a
fresh import (a new row, default False) announces correctly. That
"skip when already notified" behavior is the regression this file locks.

Mail is faked at the notifications read-site
(``games.docket.services.notifications``), per the platform convention.
"""
from datetime import datetime
from unittest.mock import patch

from extensions import db
from games.docket.cli import _run_import
from games.docket.models import DocketWeek
from games.docket.services.notifications import notify_picks_open
from tests._docket_fixtures import (
    make_enrollment,
    make_game,
    make_user,
    make_week,
)

KICK = datetime(2026, 9, 5, 18, 0)


def _capture():
    """Patch the picks-open send-site; collect each message."""
    calls = []

    def fake(to, subject, plain, html=None):
        calls.append({'to': to, 'subject': subject, 'html': html})
        return True

    return calls, patch(
        'games.docket.services.notifications.send_platform_email',
        side_effect=fake)


# ── Sender: reaches the whole roster ─────────────────────────────────────

def test_notify_picks_open_reaches_the_whole_roster(app):
    week = make_week(1)
    make_game(week, kickoff=KICK)
    u1, u2 = make_user('a'), make_user('b')
    db.session.commit()

    calls, patcher = _capture()
    with patcher:
        sent = notify_picks_open(week, [(u1, None), (u2, None)])

    assert sent == 2
    assert {c['to'] for c in calls} == {'a@test.com', 'b@test.com'}
    assert calls[0]['subject'] == 'Picks are open: The Docket, Week 1'


def test_notify_picks_open_links_the_sheet(app):
    app.config['SITE_URL'] = 'https://cccfantasy.com'
    week = make_week(1)
    db.session.commit()

    calls, patcher = _capture()
    with patcher:
        notify_picks_open(week, [(make_user('a'), None)])

    assert 'https://cccfantasy.com/docket/' in calls[0]['html']


# ── Trigger: fires on a fresh import, once ───────────────────────────────

@patch('games.docket.cli.import_week', return_value={'status': 'ok'})
def test_import_fires_picks_open_once(mock_import, app):
    week = make_week(1)
    make_game(week, kickoff=KICK)
    make_enrollment(make_user('p1'))
    db.session.commit()

    calls, patcher = _capture()
    with patcher:
        _run_import(1, False, 'setup')
        assert len(calls) == 1
        assert db.session.get(DocketWeek, week.id).picks_open_notified is True
        _run_import(1, False, 'lines')       # already notified
        assert len(calls) == 1               # no second announcement


@patch('games.docket.cli.import_week', return_value={'status': 'ok'})
def test_import_skips_picks_open_when_already_notified(mock_import, app):
    """The backfilled preview-week lock: a week marked notified is never
    re-announced by a later import run."""
    week = make_week(1)
    week.picks_open_notified = True
    make_game(week, kickoff=KICK)
    make_enrollment(make_user('p1'))
    db.session.commit()

    calls, patcher = _capture()
    with patcher:
        _run_import(1, False, 'lines')

    assert calls == []


@patch('games.docket.cli.import_week', return_value={'status': 'ok'})
def test_import_does_not_announce_without_games(mock_import, app):
    """An import that landed no games (e.g. a hard failure) does not
    announce — has-games gates the send alongside the latch."""
    make_week(1)
    make_enrollment(make_user('p1'))
    db.session.commit()

    calls, patcher = _capture()
    with patcher:
        _run_import(1, False, 'setup')

    assert calls == []


def test_new_week_starts_unnotified(app):
    """The latch column defaults False for a freshly created week."""
    week = make_week(1)
    db.session.commit()
    assert week.picks_open_notified is False
