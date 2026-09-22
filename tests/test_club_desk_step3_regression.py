"""Club Desk: every letter the desk sends standalone is byte-identical to the
letter the legacy pass sent.

Step 3 of ``docs/designs/unified-email.md`` promised the refactor changed no
letter, and captured every legacy letter into ``tests/golden/club_desk_step3/``
from the pre-refactor tree. Step 6 re-derived the Survivor final's "one hour"
copy (the one deliberate regen). Step 9 deleted the legacy passes, so the
goldens are now compared against the desk's own standalone firings
(``--anchor <game>``, no rides) at the same instants — the proof that the
desk reproduces the old letters, byte for byte, with no legacy code left to
compare against. The console goldens went with the legacy passes; the
Docket opener's console line stays, since ``_run_import`` still exists.

Regenerate ONLY when a later change deliberately alters copy:
``CLUB_DESK_UPDATE_GOLDENS=1 pytest tests/test_club_desk_step3_regression.py``
rewrites the files, and the diff in the PR is the review.

Fixed inputs: the same data shapes as ``tests/test_email_letter.py``, the
desk's explicit clock, the docket seam for the opener, and
``ASSET_VERSION=golden`` so the seal's cache-bust never drifts.
"""
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from extensions import db
from games.cfb.services.reminders import send_picks_open_email
from games.club_desk import run_desk
from games.docket.cli import _run_import
from games.docket.models import DocketWeek
from tests import _cfb_fixtures as cfb
from tests import _docket_fixtures as docket
from utils import email_layout

GOLDEN_DIR = Path(__file__).resolve().parent / 'golden' / 'club_desk_step3'
SITE = 'https://cccfantasy.com'
UPDATE = os.environ.get('CLUB_DESK_UPDATE_GOLDENS') == '1'
DESK_SEND = 'games.club_desk.send_platform_email'
NO_PUSH = (patch('games.cfb.services.reminders.send_push'),
           patch('games.docket.services.reminders.send_push'))

# CFB: Sat Jan 3 2026 11:00 CST (naive pool wall clock); T-25h / T-1h in UTC.
CFB_DEADLINE = datetime(2026, 1, 3, 11, 0)
CFB_INSTANTS = {'warning': '2026-01-02T16:00:00+00:00',
                'final': '2026-01-03T16:00:00+00:00'}
# Docket Week 1 deadline: Sun Sep 6 2026 12:00 CDT = 17:00 UTC.
DOCKET_INSTANTS = {'48h': '2026-09-04T17:00:00', '24h': '2026-09-05T17:00:00',
                   '2h': '2026-09-06T15:00:00'}


def _capture(target):
    calls = []

    def fake(to, subject, plain, html=None):
        calls.append({'to': to, 'subject': subject, 'plain': plain,
                      'html': html})
        return True

    return calls, patch(target, side_effect=fake)


def _check(name, actual: str):
    path = GOLDEN_DIR / name
    if UPDATE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual)
        return
    assert path.exists(), f'missing golden {path.name}; regenerate deliberately'
    expected = path.read_text()
    assert actual == expected, f'{name} drifted from the legacy golden'


def _check_letter(name, message):
    _check(f'{name}.subject.txt', message['subject'])
    _check(f'{name}.plain.txt', message['plain'])
    _check(f'{name}.html', message['html'])


@pytest.fixture()
def pinned(app, monkeypatch):
    app.config['SITE_URL'] = SITE
    monkeypatch.setenv('ASSET_VERSION', 'golden')
    email_layout._asset_version.cache_clear()
    yield
    email_layout._asset_version.cache_clear()


def test_cfb_letters_are_byte_identical(pinned):
    week = cfb.make_week(2, deadline=CFB_DEADLINE, is_active=True)
    ghost = cfb.make_user('ghost')
    enrollment = cfb.make_enrollment(ghost, lives=2, display_name='Ghost Gary')
    enrollment.has_paid = False
    db.session.commit()

    sent, patcher = _capture('games.cfb.services.reminders.send_platform_email')
    with patcher:
        send_picks_open_email(week.id)
    assert len(sent) == 1
    _check_letter('cfb-picks-open', sent[0])

    for tier, instant in CFB_INSTANTS.items():
        sent, patcher = _capture(DESK_SEND)
        with patcher, NO_PUSH[0]:
            run = run_desk(datetime.fromisoformat(instant),
                           anchors=('cfb',), rides=())
        assert run.latched == {'cfb': tier}, run
        assert len(sent) == 1, tier
        _check_letter(f'cfb-reminder-{tier}', sent[0])


@patch('games.docket.cli.import_week', return_value={'status': 'ok'})
def test_docket_letters_are_byte_identical(mock_import, pinned, capsys,
                                           monkeypatch):
    week = docket.make_week(1)
    docket.make_game(week, kickoff=datetime(2026, 9, 4, 0, 30),
                     home='Notre Dame', away='Wisconsin')
    docket.make_game(week, kickoff=datetime(2026, 9, 5, 18, 0),
                     home='Florida State', away='SMU', total=51.5)
    # Labor Day night, after the Sunday deadline: the rule's Week-1 pick.
    docket.make_game(week, kickoff=datetime(2026, 9, 8, 0, 30),
                     home='Miami', away='LSU', total=47.5)
    user = docket.make_user('clerk')
    enrollment = docket.make_enrollment(user, display_name='Clerk of Court')
    enrollment.has_paid = False
    db.session.commit()

    # The Tuesday line freeze: pre-deadline, so the rule designates the
    # latest game on the slate and the console shows the "designated" line.
    docket.at(monkeypatch, '2026-09-01T11:05:00')
    target = 'games.docket.services.notifications.send_platform_email'
    sent, patcher = _capture(target)
    capsys.readouterr()
    with patcher:
        _run_import(1, False, 'docket sync --mode setup (week 1)')
    console = capsys.readouterr().out
    assert len(sent) == 1
    assert db.session.get(DocketWeek, week.id).picks_open_notified is True
    _check_letter('docket-picks-open', sent[0])
    _check('docket-console-setup.txt', console)

    for tier, instant in DOCKET_INSTANTS.items():
        sent, patcher = _capture(DESK_SEND)
        with patcher, NO_PUSH[1]:
            run = run_desk(datetime.fromisoformat(instant).replace(tzinfo=UTC),
                           anchors=('docket',), rides=())
        assert run.latched == {'docket': tier}, run
        assert len(sent) == 1, tier
        _check_letter(f'docket-reminder-{tier}', sent[0])


def test_golden_set_is_complete():
    """Every file the two tests write exists, and nothing else lingers."""
    if UPDATE:
        return
    names = set()
    for base in ('cfb-picks-open', 'cfb-reminder-warning', 'cfb-reminder-final',
                 'docket-picks-open', 'docket-reminder-48h',
                 'docket-reminder-24h', 'docket-reminder-2h'):
        names |= {f'{base}.subject.txt', f'{base}.plain.txt', f'{base}.html'}
    names |= {'docket-console-setup.txt'}
    assert {p.name for p in GOLDEN_DIR.iterdir()} == names
