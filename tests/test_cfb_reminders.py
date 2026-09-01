"""CFB reminder/recap email locks (pre-launch audit §8.17–18 + §2 ripples).

Covers the recap autopick timezone bug (created_at is naive UTC and must
convert via to_pool_time, not make_aware — §7 HIGH: any manual pick within
~6h of the deadline was mislabeled AUTOPICK), the user_id-keyed
eliminated-this-week detection, DQ-5 recipient gating, the DQ-2
"No pick: life lost" outcome line, and the T-25h/T-1h ±35min reminder
windows (driven through the CFB_FAKE_NOW seam).
"""
import os
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from extensions import db
from games.cfb.services.game_logic import process_week_results
from games.cfb.services.reminders import (
    get_active_reminder_window,
    get_users_without_picks,
    run_reminder_check,
    send_weekly_recap_email,
)
from tests._cfb_fixtures import (
    make_enrollment,
    make_game,
    make_pick,
    make_team,
    make_user,
    make_week,
)

# Deadline is naive pool-tz wall clock: Sat Jan 3, 2026 11:00 CST (UTC-6).
DEADLINE_POOL = datetime(2026, 1, 3, 11, 0)

# 06:00 CST on deadline day, stored as naive UTC per the column contract.
MANUAL_PICK_UTC = datetime(2026, 1, 3, 12, 0)
# 11:30 CST — genuinely after the 11:00 deadline (an autopick).
AUTOPICK_UTC = datetime(2026, 1, 3, 17, 30)


def _capture_emails():
    """Patch send_platform_email at the reminders read-site; capture calls."""
    sent = []

    def fake_send(to, subject, body, html=None):
        sent.append({'to': to, 'subject': subject, 'body': body, 'html': html})
        return True

    return sent, patch(
        'games.cfb.services.reminders.send_platform_email',
        side_effect=fake_send,
    )


def _seed_completed_week(*, pick_created_at):
    """One user, one decided week; the user's winning pick at the given time."""
    week = make_week(1, deadline=DEADLINE_POOL, is_complete=True)
    home = make_team('Home U')
    away = make_team('Away St')
    make_game(week, home, away, spread=-7.0, winner='home')
    user = make_user('p1')
    make_enrollment(user)
    make_pick(user, week, home, created_at=pick_created_at, is_correct=True)
    db.session.commit()
    return week, user


# ── §8.17 — autopick detection uses UTC→pool conversion ──────────────────

def test_recap_manual_pick_hours_before_deadline_not_flagged_autopick(app):
    """A 6am-CT pick (stored as noon UTC) is manual, not an autopick.

    The old make_aware(created_at) read the UTC timestamp as Chicago
    wall clock, shifting it past the 11:00 deadline.
    """
    week, user = _seed_completed_week(pick_created_at=MANUAL_PICK_UTC)
    sent, patcher = _capture_emails()

    with patcher:
        send_weekly_recap_email(week.id)

    assert len(sent) == 1
    assert '(autopick)' not in sent[0]['body']
    assert 'AUTOPICK' not in sent[0]['html']


def test_recap_pick_after_deadline_flagged_autopick(app):
    """A pick stamped after the deadline (pool time) still flags AUTOPICK."""
    week, user = _seed_completed_week(pick_created_at=AUTOPICK_UTC)
    sent, patcher = _capture_emails()

    with patcher:
        send_weekly_recap_email(week.id)

    assert len(sent) == 1
    assert '(autopick)' in sent[0]['body']
    assert 'AUTOPICK' in sent[0]['html']


# ── §2 ripples — recap correctness (user_id keying, DQ-5, DQ-2) ───────────

def _seed_graded_week(number=1):
    """Decided week (away won) ready for process_week_results."""
    week = make_week(number, deadline=DEADLINE_POOL)
    home = make_team(f'Home{number}')
    away = make_team(f'Away{number}')
    make_game(week, home, away, spread=-7.0, winner='away')
    return week, home, away


def _recap(week):
    """Process the week, then send the recap with emails captured."""
    result = process_week_results(week.id)
    assert result['success'] is True
    sent, patcher = _capture_emails()
    with patcher:
        send_weekly_recap_email(week.id)
    return {e['to']: e for e in sent}


def test_recap_elimination_keyed_by_user_id_not_display_name(app):
    """Two players sharing a display name: only the one actually
    eliminated gets the elimination email (audit §2 — display names
    have no uniqueness constraint)."""
    doomed = make_user('usera')
    make_enrollment(doomed, lives=1, display_name='Same Name')
    survivor = make_user('userb')
    make_enrollment(survivor, lives=2, display_name='Same Name')
    week, home, away = _seed_graded_week()
    make_pick(doomed, week, home)      # loser
    make_pick(survivor, week, away)    # winner
    db.session.commit()

    by_to = _recap(week)

    assert "You've been eliminated" in by_to['usera@test.com']['subject']
    assert 'You survived' in by_to['userb@test.com']['subject']


def test_recap_rank_follows_the_official_order(app):
    """The recap's 'Rank' line comes from the central official order
    (games/cfb/DESIGN.md 10.5): the underdog pick (+7.0) ranks above the
    favorite pick (-3.0) on equal lives, never the reverse."""
    dog_picker = make_user('dogpicker')
    make_enrollment(dog_picker, lives=2)
    fav_picker = make_user('favpicker')
    make_enrollment(fav_picker, lives=2)
    week, home, away = _seed_graded_week()          # away (+7.0) wins
    home2, away2 = make_team('Home2'), make_team('Away2')
    make_game(week, home2, away2, spread=-3.0, winner='home')
    make_pick(dog_picker, week, away)               # +7.0
    make_pick(fav_picker, week, home2)              # -3.0
    db.session.commit()

    by_to = _recap(week)

    assert '1 of 2 active' in by_to['dogpicker@test.com']['body']
    assert '2 of 2 active' in by_to['favpicker@test.com']['body']


def test_recap_skips_players_eliminated_in_prior_weeks(app):
    """DQ-5: recipients are active players plus this week's eliminations
    only — a player eliminated last week gets no further recaps."""
    prior = make_user('prior')
    make_enrollment(prior, lives=1)
    active = make_user('active')
    make_enrollment(active, lives=2)
    doomed = make_user('doomed')
    make_enrollment(doomed, lives=1)

    week1, home1, away1 = _seed_graded_week(1)
    make_pick(prior, week1, home1)     # loser — eliminated week 1
    make_pick(active, week1, away1)
    make_pick(doomed, week1, away1)
    db.session.commit()
    assert process_week_results(week1.id)['completed'] is True

    week2, home2, away2 = _seed_graded_week(2)
    make_pick(active, week2, away2)    # winner
    make_pick(doomed, week2, home2)    # loser — eliminated week 2
    db.session.commit()

    by_to = _recap(week2)

    assert set(by_to) == {'active@test.com', 'doomed@test.com'}
    assert "You've been eliminated" in by_to['doomed@test.com']['subject']


def test_recap_no_pick_life_loss_line(app):
    """DQ-2: an active player penalized for not picking sees
    'No pick: life lost', not the old no-consequence framing."""
    ghost = make_user('ghost')
    make_enrollment(ghost, lives=2)
    active = make_user('active')
    make_enrollment(active, lives=2)
    week, home, away = _seed_graded_week()
    make_pick(active, week, away)
    db.session.commit()

    by_to = _recap(week)

    body = by_to['ghost@test.com']['body']
    assert 'No pick: life lost' in body
    assert 'No pick submitted' not in body
    assert 'No pick' in by_to['ghost@test.com']['html']
    assert 'life lost' in by_to['ghost@test.com']['html']


def test_recap_no_pick_elimination_detected_and_announced(app):
    """A no-pick elimination (DQ-2) gets the elimination email and
    appears in other players' eliminated-this-week list."""
    ghost = make_user('ghost')
    make_enrollment(ghost, lives=1, display_name='Ghost Gary')
    active = make_user('active')
    make_enrollment(active, lives=2)
    week, home, away = _seed_graded_week()
    make_pick(active, week, away)
    db.session.commit()

    by_to = _recap(week)

    assert "You've been eliminated" in by_to['ghost@test.com']['subject']
    assert 'Ghost Gary' in by_to['active@test.com']['body']
    assert 'Eliminated this week' in by_to['active@test.com']['body']


# ── §8.18 — reminder windows: T-25h / T-1h ± 35 min ───────────────────────

# Deadline: Sat Jan 3, 2026 11:00 CST = 17:00 UTC.
# 25h target: Fri Jan 2 10:00 CST = 16:00 UTC; 1h target: Sat 10:00 CST.
DEADLINE_AWARE = datetime(2026, 1, 3, 11, 0, tzinfo=ZoneInfo('America/Chicago'))


def _window_at(fake_utc_iso):
    """Resolve the active reminder window at a faked instant (UTC ISO)."""
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'CFB_FAKE_NOW': fake_utc_iso}):
        return get_active_reminder_window(DEADLINE_AWARE)


@pytest.mark.parametrize('instant', [
    '2026-01-02T15:25:00+00:00',  # target -35min (inclusive edge)
    '2026-01-02T16:00:00+00:00',  # exactly T-25h
    '2026-01-02T16:35:00+00:00',  # target +35min (inclusive edge)
])
def test_25h_warning_window_inclusive_boundaries(app, instant):
    window = _window_at(instant)
    assert window is not None and window['type'] == 'warning'


@pytest.mark.parametrize('instant', [
    '2026-01-02T15:24:59+00:00',  # 1s before the window opens
    '2026-01-02T16:35:01+00:00',  # 1s after the window closes
])
def test_just_outside_25h_window_sends_nothing(app, instant):
    assert _window_at(instant) is None


@pytest.mark.parametrize('instant', [
    '2026-01-03T15:25:00+00:00',  # target -35min (inclusive edge)
    '2026-01-03T16:00:00+00:00',  # exactly T-1h
    '2026-01-03T16:35:00+00:00',  # target +35min (25 min before deadline)
])
def test_1h_final_window_inclusive_boundaries(app, instant):
    window = _window_at(instant)
    assert window is not None and window['type'] == 'final'


def test_between_windows_sends_nothing(app):
    assert _window_at('2026-01-03T03:00:00+00:00') is None


def test_at_or_past_deadline_sends_nothing(app):
    assert _window_at('2026-01-03T17:00:00+00:00') is None
    assert _window_at('2026-01-03T18:00:00+00:00') is None


# ── §8.18 — reminder recipients ───────────────────────────────────────────

def test_reminder_recipients_exclude_eliminated_and_picked(app):
    """Only active enrollments without a pick this week get reminders;
    eliminated players, players with picks, and other seasons don't."""
    week = make_week(1, deadline=DEADLINE_POOL)
    team = make_team('Team A')

    needs = make_user('needs')
    make_enrollment(needs)
    picked = make_user('picked')
    make_enrollment(picked)
    make_pick(picked, week, team)
    out = make_user('out')
    make_enrollment(out, lives=0, eliminated=True)
    other_season = make_user('otherseason')
    make_enrollment(other_season, season=2027)
    db.session.commit()

    recipients = get_users_without_picks(week.id, 2026)

    assert [(e.user_id, u.id) for e, u in recipients] == [(needs.id, needs.id)]


# ── sent-flag de-dup (CfbWeek.last_reminder_type) ─────────────────────────
# The guarantee that lets cfb-remind.timer run hourly: each window mails at
# most once per week, regardless of cadence, catch-up firings, or hand-runs.

WARNING_INSTANT = '2026-01-02T16:00:00+00:00'  # exactly T-25h
LATER_IN_WARNING_WINDOW = '2026-01-02T16:20:00+00:00'  # +20min, same window
FINAL_INSTANT = '2026-01-03T16:00:00+00:00'    # exactly T-1h


def _seed_reminder_week():
    """One active week, one enrolled user with no pick."""
    week = make_week(1, deadline=DEADLINE_POOL, is_active=True)
    user = make_user('needs')
    make_enrollment(user)
    db.session.commit()
    return week, user


def _run_reminders_at(fake_utc_iso):
    with patch.dict(os.environ, {'ENVIRONMENT': 'testing',
                                 'CFB_FAKE_NOW': fake_utc_iso}):
        run_reminder_check()


def test_first_send_records_the_window(app):
    week, _ = _seed_reminder_week()
    assert week.last_reminder_type is None  # fresh week starts unset
    sent, patcher = _capture_emails()
    with patcher:
        _run_reminders_at(WARNING_INSTANT)
    assert len(sent) == 1
    assert week.last_reminder_type == 'warning'


def test_second_firing_in_the_same_window_sends_nothing(app):
    """The hourly-cadence contract: a re-fire inside an already-mailed
    window (catch-up, hand-run, faster timer) is a no-op."""
    week, _ = _seed_reminder_week()
    sent, patcher = _capture_emails()
    with patcher:
        _run_reminders_at(WARNING_INSTANT)
        _run_reminders_at(LATER_IN_WARNING_WINDOW)
    assert len(sent) == 1
    assert week.last_reminder_type == 'warning'


def test_final_still_sends_after_warning(app):
    week, _ = _seed_reminder_week()
    week.last_reminder_type = 'warning'
    db.session.commit()
    sent, patcher = _capture_emails()
    with patcher:
        _run_reminders_at(FINAL_INSTANT)
    assert len(sent) == 1
    assert 'FINAL' in sent[0]['subject']
    assert week.last_reminder_type == 'final'


def test_warning_never_resends_after_final(app):
    """Order gate, not equality: once 'final' is recorded, a stray firing
    that lands in the (earlier-ranked) warning window stays silent."""
    week, _ = _seed_reminder_week()
    week.last_reminder_type = 'final'
    db.session.commit()
    sent, patcher = _capture_emails()
    with patcher:
        _run_reminders_at(WARNING_INSTANT)
    assert sent == []
    assert week.last_reminder_type == 'final'


def test_all_picked_leaves_the_window_open(app):
    """Nothing mailed -> nothing recorded: a player who withdraws a pick
    later in the same window must still be reachable."""
    week, user = _seed_reminder_week()
    team = make_team('Team A')
    make_pick(user, week, team)
    db.session.commit()
    sent, patcher = _capture_emails()
    with patcher:
        _run_reminders_at(WARNING_INSTANT)
    assert sent == []
    assert week.last_reminder_type is None


def test_total_send_failure_leaves_the_window_open_for_retry(app):
    """A full mail outage must not swallow the window; the next hourly
    firing retries and the flag records only when a send succeeds."""
    week, _ = _seed_reminder_week()
    with patch('games.cfb.services.reminders.send_platform_email',
               return_value=False):
        _run_reminders_at(WARNING_INSTANT)
    assert week.last_reminder_type is None

    sent, patcher = _capture_emails()
    with patcher:
        _run_reminders_at(LATER_IN_WARNING_WINDOW)
    assert len(sent) == 1
    assert week.last_reminder_type == 'warning'


def test_unknown_stored_value_does_not_block_sends(app):
    """A legacy/corrupt stored tier ranks -1 and must never suppress mail."""
    week, _ = _seed_reminder_week()
    week.last_reminder_type = 'legacy'
    db.session.commit()
    sent, patcher = _capture_emails()
    with patcher:
        _run_reminders_at(FINAL_INSTANT)
    assert len(sent) == 1
    assert week.last_reminder_type == 'final'
