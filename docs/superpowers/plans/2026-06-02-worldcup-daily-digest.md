# World Cup Daily Digest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the daily player digest feature by adding the test suite, systemd deploy units, and CLAUDE.md documentation — the email template, service, and CLI command are already shipped.

**Architecture:** The core implementation landed in commit `1b68508`: `games/worldcup/services/notifications.py` contains `send_daily_digests()`, the Jinja2 template lives at `games/worldcup/templates/worldcup/email/wc_daily_digest.j2`, and `flask worldcup send-digest` is registered in `games/worldcup/cli.py`. This plan adds the test coverage, two new systemd unit files in `deploy/`, and docs updates.

**Tech Stack:** Python / Flask / SQLAlchemy, pytest, unittest.mock, systemd (server-side deploy step), Jinja2 email template.

---

## File Map

| Action | Path | Purpose |
|---|---|---|
| Create | `tests/test_worldcup_notifications.py` | Full test suite for `send_daily_digests()` |
| Create | `deploy/worldcup-digest-player.timer` | systemd timer — fires 5am CT daily |
| Create | `deploy/worldcup-digest-player.service` | systemd oneshot service — runs `flask worldcup send-digest` |
| Modify | `CLAUDE.md` | Add `send-digest` CLI entry + player digest timer note |

---

## Task 1: Test suite — `tests/test_worldcup_notifications.py`

**Files:**
- Create: `tests/test_worldcup_notifications.py`

### Background

`send_daily_digests()` is in `games/worldcup/services/notifications.py`. It:
1. Looks at all `WorldCupMatch` rows with `is_completed=True` whose `updated_at` (UTC→CT) falls on "yesterday".
2. For each `WorldCupEnrollment` with `picks_submitted=True` in `SEASON_YEAR`, finds picks on teams that played.
3. Calls `points_for_pick_on_match(pick, match)` — returns `0.0` for losses.
4. Skips players with no scoring events (`pts <= 0`).
5. Calls `send_platform_email(to, subject, plain, html)` for players who did score.
6. Returns `{'status': ..., 'sent': int, 'skipped_no_match': int, 'skipped_no_score': int, 'skipped_no_email': int, 'errors': int, 'date': str}`.

Mock target for email: `games.worldcup.services.notifications.send_platform_email`

Key constants: `SEASON_YEAR = 2026` (from `games.worldcup.constants`).

Scoring constants: `GROUP_WIN = 3`, `GROUP_DRAW = 1`, multipliers live on `WorldCupTeam.multiplier`.

Test helpers from `test_worldcup_scoring.py` pattern — build users, enrollments, teams, matches, picks from scratch in each test using the shared `app` fixture.

- [ ] **Step 1: Create the test file with fixtures and helpers**

```python
# tests/test_worldcup_notifications.py
"""Tests for games/worldcup/services/notifications.send_daily_digests."""
from datetime import datetime, timezone, timedelta
from unittest import mock

import pytest

from app import create_app
from extensions import db
from models.user import User
from games.worldcup.models import (
    WorldCupEnrollment, WorldCupTeam, WorldCupMatch, WorldCupPick,
)
from games.worldcup.constants import SEASON_YEAR


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(session, username='player1', email='player1@example.com'):
    u = User(username=username, email=email)
    u.set_password('pw')
    session.add(u)
    session.flush()
    return u


def _make_enrollment(session, user, picks_submitted=True):
    e = WorldCupEnrollment(
        user_id=user.id,
        season_year=SEASON_YEAR,
        picks_submitted=picks_submitted,
        total_score=0.0,
    )
    session.add(e)
    session.flush()
    return e


def _make_team(session, fifa_code, tier=3, multiplier=2.5, group='A'):
    t = WorldCupTeam(
        fifa_code=fifa_code,
        name=fifa_code,
        display_name=fifa_code,
        tier=tier,
        multiplier=multiplier,
        confederation='TEST',
        group_letter=group,
    )
    session.add(t)
    session.flush()
    return t


def _make_match(session, home, away, match_number=1, completed=True,
                home_score=2, away_score=0, is_draw=False,
                updated_yesterday=True):
    """Create a completed match. updated_at defaults to yesterday UTC."""
    from games.worldcup.constants import WORLDCUP_TZ
    now_ct = datetime.now(WORLDCUP_TZ)
    yesterday_utc = (now_ct - timedelta(days=1)).replace(
        hour=20, minute=0, second=0, microsecond=0,
    ).astimezone(timezone.utc).replace(tzinfo=None)
    m = WorldCupMatch(
        match_number=match_number,
        stage='group',
        group_letter='A',
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=home_score,
        away_score=away_score,
        is_draw=is_draw,
        is_completed=completed,
        winner_team_id=home.id if (not is_draw and home_score > away_score) else (
            away.id if (not is_draw and away_score > home_score) else None
        ),
        updated_at=yesterday_utc if updated_yesterday else
            datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(m)
    session.flush()
    return m


def _make_pick(session, enrollment, team, tier=3):
    p = WorldCupPick(
        enrollment_id=enrollment.id,
        team_id=team.id,
        tier=tier,
    )
    session.add(p)
    session.flush()
    return p
```

- [ ] **Step 2: Run the file to confirm no import errors**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_notifications.py --collect-only -q
```

Expected: `no tests ran` (no test functions yet).

- [ ] **Step 3: Write and run `test_no_results_when_no_matches_yesterday`**

No completed matches whose `updated_at` falls on yesterday — function returns `no_results`.

```python
def test_no_results_when_no_matches_yesterday(app):
    """Returns no_results when no matches were completed yesterday (CT)."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        result = send_daily_digests()
    assert result['status'] == 'no_results'
```

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_notifications.py::test_no_results_when_no_matches_yesterday -v
```

Expected: PASS.

- [ ] **Step 4: Write and run `test_skips_player_whose_picks_did_not_play`**

A match was completed yesterday, but the enrolled player's pick was on a team that didn't play in it.

```python
def test_skips_player_whose_picks_did_not_play(app):
    """Player is skipped when none of their picks played yesterday."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        u = _make_user(db.session)
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'BRA', group='A')
        away = _make_team(db.session, 'MEX', group='A')
        other = _make_team(db.session, 'GER', group='B')
        _make_match(db.session, home, away, match_number=1)
        _make_pick(db.session, e, other)  # pick is on GER, not BRA or MEX
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email'
        ) as mock_send:
            result = send_daily_digests()

    assert result['skipped_no_match'] == 1
    assert result['sent'] == 0
    mock_send.assert_not_called()
```

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_notifications.py::test_skips_player_whose_picks_did_not_play -v
```

Expected: PASS.

- [ ] **Step 5: Write and run `test_skips_player_whose_pick_lost`**

Player's pick played but lost — `points_for_pick_on_match` returns 0.0 for a group loss. Player is skipped.

```python
def test_skips_player_whose_pick_lost(app):
    """Player is skipped when their pick played but earned 0 points (group loss)."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        u = _make_user(db.session)
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'BRA', group='A')
        away = _make_team(db.session, 'MEX', group='A')
        _make_match(db.session, home, away, home_score=2, away_score=0)
        _make_pick(db.session, e, away)  # MEX lost — 0 pts
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email'
        ) as mock_send:
            result = send_daily_digests()

    assert result['skipped_no_score'] == 1
    assert result['sent'] == 0
    mock_send.assert_not_called()
```

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_notifications.py::test_skips_player_whose_pick_lost -v
```

Expected: PASS.

- [ ] **Step 6: Write and run `test_sends_email_when_pick_won`**

Player's pick won a group match. Email sent; assert subject contains date, HTML contains team name and points string.

`GROUP_WIN = 3`, `multiplier = 2.5` → `3 * 2.5 = 7.5` pts → `points_str = '7.5'`.

```python
def test_sends_email_when_pick_won(app):
    """Sends one email when a pick scored from a group win."""
    from games.worldcup.services.notifications import send_daily_digests
    from games.worldcup.constants import WORLDCUP_TZ
    from datetime import date
    yesterday = (datetime.now(WORLDCUP_TZ) - timedelta(days=1)).date()
    date_str = yesterday.strftime('%B %-d')

    with app.app_context():
        u = _make_user(db.session, email='winner@example.com')
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'BRA', tier=3, multiplier=2.5, group='A')
        away = _make_team(db.session, 'MEX', tier=3, multiplier=2.5, group='A')
        _make_match(db.session, home, away, home_score=2, away_score=0)
        _make_pick(db.session, e, home)  # BRA won — 3 * 2.5 = 7.5 pts
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send:
            result = send_daily_digests()

    assert result['sent'] == 1
    assert result['errors'] == 0
    mock_send.assert_called_once()
    to, subject, plain, html = mock_send.call_args[0]
    assert to == 'winner@example.com'
    assert date_str in subject
    assert 'BRA' in html
    assert '7.5' in html
```

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_notifications.py::test_sends_email_when_pick_won -v
```

Expected: PASS.

- [ ] **Step 7: Write and run `test_sends_email_when_pick_drew`**

`GROUP_DRAW = 1`, `multiplier = 4.0` → `1 * 4.0 = 4` pts → `points_str = '4'`.

```python
def test_sends_email_when_pick_drew(app):
    """Sends email when a pick scored from a group draw."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        u = _make_user(db.session)
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'ARG', tier=4, multiplier=4.0, group='B')
        away = _make_team(db.session, 'POL', tier=4, multiplier=4.0, group='B')
        _make_match(db.session, home, away, home_score=1, away_score=1,
                    is_draw=True)
        _make_pick(db.session, e, home)  # ARG drew — 1 * 4.0 = 4 pts
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send:
            result = send_daily_digests()

    assert result['sent'] == 1
    mock_send.assert_called_once()
    _, _, plain, html = mock_send.call_args[0]
    assert '4' in html
    assert 'Draw' in html
```

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_notifications.py::test_sends_email_when_pick_drew -v
```

Expected: PASS.

- [ ] **Step 8: Write and run `test_skips_player_with_no_email`**

Enrollment exists but `user.email` is blank — player counted in `skipped_no_email`, no send.

```python
def test_skips_player_with_no_email(app):
    """Skips players whose user account has no email address."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        u = _make_user(db.session, email='')
        u.email = ''
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'BRA', group='A')
        away = _make_team(db.session, 'MEX', group='A')
        _make_match(db.session, home, away)
        _make_pick(db.session, e, home)
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email'
        ) as mock_send:
            result = send_daily_digests()

    assert result['skipped_no_email'] == 1
    assert result['sent'] == 0
    mock_send.assert_not_called()
```

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_notifications.py::test_skips_player_with_no_email -v
```

Expected: PASS.

- [ ] **Step 9: Write and run `test_rank_delta_none_omits_signal`**

When `compute_rank_delta` returns `None` (no snapshot history), the HTML should not contain the up-arrow entity `&#8593;` or down-arrow `&#8595;` — the rank signal is hidden.

```python
def test_rank_delta_none_omits_signal(app):
    """No rank signal in HTML when compute_rank_delta returns None."""
    from games.worldcup.services.notifications import send_daily_digests
    with app.app_context():
        u = _make_user(db.session)
        e = _make_enrollment(db.session, u)
        home = _make_team(db.session, 'BRA', group='A')
        away = _make_team(db.session, 'MEX', group='A')
        _make_match(db.session, home, away)
        _make_pick(db.session, e, home)
        db.session.commit()

        with mock.patch(
            'games.worldcup.services.notifications.send_platform_email',
            return_value=True,
        ) as mock_send, mock.patch(
            'games.worldcup.services.notifications.compute_rank_delta',
            return_value=None,
        ):
            send_daily_digests()

    _, _, _, html = mock_send.call_args[0]
    assert '8593' not in html  # ↑ up arrow entity absent
    assert '8595' not in html  # ↓ down arrow entity absent
```

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_notifications.py::test_rank_delta_none_omits_signal -v
```

Expected: PASS.

- [ ] **Step 10: Write and run `test_plain_body_rank_signals`**

Plain-text body should include "up 2 spots", "down 1 spot", and "steady" for the three delta cases. Test `_plain_body` directly.

```python
def test_plain_body_rank_signals(app):
    """Plain-text body includes correct rank signal phrasing."""
    from games.worldcup.services.notifications import _plain_body

    class FakeTeam:
        display_name = 'Brazil'; fifa_code = 'BRA'; iso_code = 'br'; multiplier = 3.0

    class FakeEnrollment:
        total_score = 100.0
        def get_display_name(self): return 'Tester'

    mr = [{
        'team': FakeTeam(), 'multiplier_str': '×3', 'match_score': 'BRA 2–0 MEX',
        'stage_label': 'Group Stage', 'result': 'won',
        'points_earned': 9.0, 'points_str': '9',
    }]

    with app.app_context():
        up = _plain_body(FakeEnrollment(), mr, '9', 4, 28, 2, 'June 1',
                         'https://cccfantasy.com')
        dn = _plain_body(FakeEnrollment(), mr, '9', 4, 28, -1, 'June 1',
                         'https://cccfantasy.com')
        eq = _plain_body(FakeEnrollment(), mr, '9', 4, 28, 0, 'June 1',
                         'https://cccfantasy.com')
        no = _plain_body(FakeEnrollment(), mr, '9', 4, 28, None, 'June 1',
                         'https://cccfantasy.com')

    assert 'up 2 spots' in up
    assert 'down 1 spot' in dn
    assert 'steady' in eq
    assert 'up' not in no and 'down' not in no and 'steady' not in no
```

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_notifications.py::test_plain_body_rank_signals -v
```

Expected: PASS.

- [ ] **Step 11: Run the full notifications test file**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/test_worldcup_notifications.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 12: Run the full suite to confirm no regressions**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: 1018 passed (1009 existing + 9 new), 0 failures.

- [ ] **Step 13: Commit**

```bash
git add tests/test_worldcup_notifications.py
git commit -m "test(worldcup): notification service test suite (9 tests)"
```

---

## Task 2: Systemd deploy units

**Files:**
- Create: `deploy/worldcup-digest-player.timer`
- Create: `deploy/worldcup-digest-player.service`

These mirror `deploy/worldcup-digest.timer` / `deploy/worldcup-digest.service` exactly, with the send time changed to 05:00 CT and the command changed to `flask worldcup send-digest`.

- [ ] **Step 1: Create `deploy/worldcup-digest-player.timer`**

```ini
# deploy/worldcup-digest-player.timer
# Runs the WC player daily digest once a day at 05:00 America/Chicago.
[Unit]
Description=Send World Cup player daily digest emails

[Timer]
# Timezone specified INLINE in OnCalendar (systemd v240+); no separate
# TimeZone= directive. 5am CT covers all matches from the previous CT
# calendar day with no edge cases.
OnCalendar=*-*-* 05:00:00 America/Chicago
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 2: Create `deploy/worldcup-digest-player.service`**

```ini
# deploy/worldcup-digest-player.service
# World Cup player daily digest — email each player whose picks scored
# yesterday (CT). Fired once daily by worldcup-digest-player.timer.

[Unit]
Description=World Cup player daily digest emails
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/fantasy-platform
EnvironmentFile=/home/deploy/fantasy-platform/.env
Environment=ENVIRONMENT=production
Environment=FLASK_APP=app.py
NoNewPrivileges=true
PrivateTmp=true
TimeoutStartSec=5m
ExecStart=/home/deploy/fantasy-platform/venv/bin/flask worldcup send-digest
```

- [ ] **Step 3: Commit the deploy files**

```bash
git add deploy/worldcup-digest-player.timer deploy/worldcup-digest-player.service
git commit -m "deploy(worldcup): add player digest systemd timer (5am CT daily)"
```

- [ ] **Step 4: Install on the server (run on the Droplet)**

SSH to the server, then:

```bash
sudo cp /home/deploy/fantasy-platform/deploy/worldcup-digest-player.timer \
        /etc/systemd/system/worldcup-digest-player.timer

sudo cp /home/deploy/fantasy-platform/deploy/worldcup-digest-player.service \
        /etc/systemd/system/worldcup-digest-player.service

sudo systemctl daemon-reload
sudo systemctl enable worldcup-digest-player.timer
sudo systemctl start worldcup-digest-player.timer
```

- [ ] **Step 5: Verify the timer is live**

```bash
sudo systemctl list-timers | grep worldcup
```

Expected output includes `worldcup-digest-player.timer` with a next trigger around tomorrow at 05:00 CT. Four timers total: `worldcup-sync`, `worldcup-advancement`, `worldcup-digest`, `worldcup-digest-player`.

- [ ] **Step 6: Dry-run the command manually to confirm it wires up**

Still on the server:

```bash
cd /home/deploy/fantasy-platform
ENVIRONMENT=production FLASK_APP=app.py venv/bin/flask worldcup send-digest
```

Expected output: `[send-digest] no_results  date=<yesterday>  sent=0 ...` (no matches completed yesterday, or a real send count if the tournament has started). Exit 0 unless there were errors.

---

## Task 3: CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md`

Two additions: the new CLI command in the World Cup CLI block, and a note in the Production ops section about the fourth WC timer.

- [ ] **Step 1: Add `send-digest` to the World Cup CLI block**

Find this line in `CLAUDE.md` (currently line ~61):
```
FLASK_APP=app.py venv/bin/flask worldcup sync --mode link|scores|advancement|digest|status  # football-data.org results sync (link maps fixtures→shells; scores auto-applies finals)
```

Add the new command immediately after it:
```
FLASK_APP=app.py venv/bin/flask worldcup send-digest  # Send player match-result digest emails (cron; 5am CT, only when picks scored)
```

- [ ] **Step 2: Add the timer note in the Results automation bullet**

Find this sentence in `CLAUDE.md` (in the World Cup scoring section):
```
- **Results automation:** `games/worldcup/services/sync.py` (`flask worldcup sync`, football-data.org free tier, 30-min systemd timer)
```

Append a sentence about the player digest timer so the four-timer set is documented together. Change the end of that bullet from:
```
...Don't add a parallel results-entry or scoring path. Spec: `docs/superpowers/specs/2026-06-02-worldcup-results-automation-design.md`.
```
to:
```
...Don't add a parallel results-entry or scoring path. Spec: `docs/superpowers/specs/2026-06-02-worldcup-results-automation-design.md`. Player daily digest (`flask worldcup send-digest`, `games/worldcup/services/notifications.py`) fires at 5am CT via `worldcup-digest-player.timer` — sends one email per player per day only when picks scored the previous CT calendar day. Spec: `docs/superpowers/specs/2026-06-02-worldcup-daily-digest-design.md`.
```

- [ ] **Step 3: Confirm no test suite breaks from the CLAUDE.md edit**

```bash
ENVIRONMENT=testing venv/bin/python -m pytest tests/ -q
```

Expected: 1018 passed, 0 failures.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(worldcup): document send-digest CLI and player digest timer"
```
