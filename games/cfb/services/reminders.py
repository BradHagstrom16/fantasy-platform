"""
CFB Survivor Pool — Reminder & Notification Service
======================================================
Email pick reminders and weekly results recap.

Reminder windows:
  - 25 hours before deadline (typically Friday)
  - 1 hour before deadline (typically Saturday -- FINAL reminder)
  Each window is sent at most once per week, de-duped via
  CfbWeek.last_reminder_type — safe under any timer cadence (the hourly
  cfb-remind.timer, catch-up firings, and hand-runs all no-op once a
  window is recorded).

Results recap:
  - Sent once per week after results are processed (gated by recap_email_sent)

All functions run inside the existing Flask app context (called from CLI).
"""

import logging
from datetime import timedelta

from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from extensions import db
from games.cfb.models import (
    CfbEnrollment,
    CfbGame,
    CfbPick,
    CfbWeek,
    CfbWeekOutcome,
)
from games.cfb.services.payment import payment_nudge_for
from games.cfb.utils import (
    format_deadline_short,
    get_current_time,
    get_week_display_name,
    is_week_playoff,
    make_aware,
    to_pool_time,
)
from models import User
from utils.email import send_platform_email
from utils.email_layout import (
    Letter,
    items_block,
    render_letter,
    result_block,
    tab_block,
)
from utils.reminders import tier_already_sent

logger = logging.getLogger(__name__)

# Reminder windows (hours before deadline)
REMINDER_WINDOWS = [
    {'hours': 25, 'type': 'warning', 'label': '25-hour'},
    {'hours': 1, 'type': 'final', 'label': '1-hour FINAL'},
]

# De-dup ordering for CfbWeek.last_reminder_type. Higher = closer to the
# deadline; sending 'final' also closes 'warning' (a catch-up firing after
# the final went out must not send yesterday's warning).
REMINDER_ORDER = {'warning': 0, 'final': 1}

# Tolerance window (minutes) - send reminder if within this window of the target time
TOLERANCE_MINUTES = 35

# The consequence of a missed deadline, stated once per letter
# (game_logic.process_autopicks: the biggest eligible favorite among the
# teams the player has not used; a no-pick with nothing eligible costs a
# life, DQ-2). Commissioner voice reinforces the rule; the deadline fact
# still states the time itself (DESIGN.md 6.11).
MISS_RULE = ('Miss the deadline and the Commish picks for you: the biggest '
             'eligible favorite you have not used.')


# ============================================================================
# Utility Functions
# ============================================================================

def get_users_without_picks(week_id, season_year):
    """Return (enrollment, user) tuples for active enrollments missing picks this week."""
    active_enrollments = (
        CfbEnrollment.query
        .filter_by(is_eliminated=False, season_year=season_year)
        .options(joinedload(CfbEnrollment.user))  # avoid a User get per row
        .all()
    )

    picked_user_ids = {
        p.user_id for p in CfbPick.query.filter_by(week_id=week_id).all()
    }

    results = []
    for enrollment in active_enrollments:
        if enrollment.user_id not in picked_user_ids:
            user = enrollment.user
            if user:
                results.append((enrollment, user))

    return results


def should_send_reminder(deadline, window_hours):
    """Check if current time is within the tolerance window for this reminder."""
    now = get_current_time()
    target_time = deadline - timedelta(hours=window_hours)

    window_start = target_time - timedelta(minutes=TOLERANCE_MINUTES)
    window_end = target_time + timedelta(minutes=TOLERANCE_MINUTES)

    return window_start <= now <= window_end


def get_active_reminder_window(deadline):
    """Determine which reminder window (if any) is currently active."""
    now = get_current_time()

    if deadline <= now:
        return None

    for window in REMINDER_WINDOWS:
        if should_send_reminder(deadline, window['hours']):
            return window

    return None


def format_time_remaining(deadline):
    """Format the time remaining until deadline."""
    now = get_current_time()
    delta = deadline - now

    total_hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)

    if total_hours >= 24:
        days = total_hours // 24
        hours = total_hours % 24
        return f"{days} day{'s' if days != 1 else ''}, {hours} hour{'s' if hours != 1 else ''}"
    elif total_hours >= 1:
        return f"{total_hours} hour{'s' if total_hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
    else:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"


# ============================================================================
# PICK REMINDER EMAILS
# ============================================================================

def _reminder_letter(*, week_name, deadline_short, time_remaining, lives,
                     cumulative_spread, pick_url, window, season_year):
    """The T-25h / T-1h reminder as a Club Letter (a broadcast: no greeting).

    Calm and consequential (DESIGN.md 6.11): the deadline leads the fact
    block, lives and spread sit beside it with their labels, and the
    consequence of missing it is stated once. Both tiers keep distinct
    subjects so Gmail never threads them into one.
    """
    if window['type'] == 'final':
        subject = f'FINAL, 1 hour left: CFB Survivor, {week_name}'
        headline = 'Final call: one hour left'
        lede = [f'Your {week_name} pick is not in and the deadline is less '
                f'than an hour away.']
    else:
        subject = f'Pick due tomorrow: CFB Survivor, {week_name}'
        headline = f'Your {week_name} pick is due tomorrow'
        lede = [f'About {time_remaining} left. One more reminder comes at '
                f'one hour.']
    return Letter(
        subject=subject,
        headline=headline,
        eyebrow=f'CFB Survivor · {week_name}',
        game_slug='cfb',
        season=season_year,
        preheader=f'Deadline {deadline_short}.',
        lede=lede,
        facts=[('Deadline', deadline_short),
               ('Lives', f'{lives} of 2'),
               ('Cumulative spread', f'{cumulative_spread:.1f}')],
        cta=('Make your pick', pick_url),
        supporting=[MISS_RULE],
    )


def run_reminder_check():
    """Main reminder processing function. Called from CLI.

    De-dup gate (the guarantee lives in the flag, not the timer cadence):

        hourly firing ──► active week? ──no──► exit
                              │yes
                         deadline passed? ──yes──► exit
                              │no
                         window active? (T-25h/T-1h ±35m) ──no──► exit
                              │yes
                         tier_already_sent(week.last_reminder_type)? ──yes──► exit
                              │no
                         recipients w/o picks? ──none──► exit (flag NOT recorded)
                              │some
                         send each ──► 0 sent? ──yes──► log error, exit
                              │≥1 sent          (flag NOT recorded → retried)
                         week.last_reminder_type = window type; commit
    """
    now = get_current_time()
    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    site_url = current_app.config.get('SITE_URL', 'http://localhost:5000')

    print()
    print("=" * 60)
    print("CFB Survivor Pool Reminder Check")
    print(f"Time: {now.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
    print("=" * 60)

    # Find active week
    week = CfbWeek.query.filter_by(is_active=True).first()
    if not week:
        print("\nNo active week found")
        return

    deadline = make_aware(week.deadline)

    if deadline <= now:
        print(f"\nDeadline for Week {week.week_number} has passed")
        return

    week_name = get_week_display_name(week)
    print(f"\n{week_name}")
    print(f"Deadline: {deadline.strftime('%A, %B %d at %I:%M %p %Z')}")
    print(f"Time remaining: {format_time_remaining(deadline)}")

    # Check which reminder window is active
    window = get_active_reminder_window(deadline)
    if not window:
        print("\nNot within any reminder window")
        return

    print(f"\nActive window: {window['label']} ({window['type']})")

    if tier_already_sent(week.last_reminder_type, window['type'], REMINDER_ORDER):
        print(f"{window['label']} reminder already sent for {week_name} "
              f"(last sent: {week.last_reminder_type}). Skipping.")
        return

    # Get users needing reminders. Deliberately NOT recorded when empty:
    # nothing was mailed, so the window stays open — a player who withdraws
    # a pick later in the same window is still reachable, and the flag keeps
    # meaning "this window went out".
    recipients = get_users_without_picks(week.id, season_year)
    if not recipients:
        print(f"\nAll active users have picks for {week_name}")
        return

    print(f"Users without picks: {len(recipients)}")

    deadline_short = format_deadline_short(deadline)
    time_remaining = format_time_remaining(deadline)
    pick_url = f"{site_url}/cfb/pick/{week.week_number}"

    success_count = 0
    for enrollment, user in recipients:
        letter = _reminder_letter(
            week_name=week_name,
            deadline_short=deadline_short,
            time_remaining=time_remaining,
            lives=enrollment.lives_remaining,
            cumulative_spread=enrollment.cumulative_spread,
            pick_url=pick_url,
            window=window,
            season_year=season_year,
        )
        plain, html = render_letter(letter)
        if send_platform_email(user.email, letter.subject, plain, html):
            success_count += 1

    if success_count > 0:
        # Recorded once ANY send succeeds (Golf/Docket reasoning): gating on
        # all-recipient success would let one permanently bad address hold
        # the window open and re-mail every good recipient next firing.
        week.last_reminder_type = window['type']
        db.session.commit()
    else:
        # Every send failed: leave the window open so the next firing
        # retries — recording here would swallow a full mail outage.
        logger.error("Week %s: %s reminder reached nobody (%s recipients)",
                     week.week_number, window['type'], len(recipients))

    print(f"\nSummary: {success_count}/{len(recipients)} reminders sent")
    print("=" * 60)


# ============================================================================
# PICKS OPEN ANNOUNCEMENT EMAIL
# ============================================================================

def _picks_open_letter(*, week_name, deadline_short, pick_url, nudge,
                       season_year):
    """The season-open note as a Club Letter (a broadcast: no greeting).

    "Settle the tab" rides along for anyone who still owes the buy-in
    (gate: games/cfb/services/payment.py, unpaid only, never the Commish) as
    a text strip after the CTA, never a second button: "Make your pick"
    stays the CTA.
    """
    return Letter(
        subject=f'Picks are open: CFB Survivor, {week_name}',
        headline='Picks are open',
        eyebrow=f'CFB Survivor · {week_name}',
        game_slug='cfb',
        season=season_year,
        preheader=f'Deadline {deadline_short}.',
        lede=['The lines are set. Get your survivor pick in before the '
              'deadline.'],
        facts=[('Deadline', deadline_short)],
        cta=('Make your pick', pick_url),
        supporting=[
            'You are picking a team to win outright (not against the '
            'spread), and each team can be used once all season. You can '
            'change your pick until the deadline.',
            MISS_RULE,
        ],
        notes=[tab_block(nudge, 'cfb')],
    )


def send_picks_open_email(week_id: int) -> int:
    """Announce that picks are open to EVERY enrolled player for the season.

    Not gated on who has yet to pick (that is the deadline reminder's job):
    this is the season-open "it's live" note, sent once per week and latched
    by the caller (run_spread_update) on ``CfbWeek.picks_open_notified``.

    Returns the number of emails accepted.
    """
    config = current_app.config
    season_year = config.get('CFB_SEASON_YEAR', 2026)
    site_url = config.get('SITE_URL', 'http://localhost:5000')

    week = db.session.get(CfbWeek, week_id)
    if not week:
        logger.warning("Picks-open email: week id %s not found", week_id)
        return 0

    week_name = get_week_display_name(week)
    deadline_short = format_deadline_short(week.deadline)
    pick_url = f"{site_url}/cfb/pick/{week.week_number}"

    enrollments = db.session.scalars(
        select(CfbEnrollment)
        .filter_by(season_year=season_year)
        .options(joinedload(CfbEnrollment.user))  # avoid a User get per row
    ).all()

    success_count = 0
    for enrollment in enrollments:
        user = enrollment.user
        if not user or not user.email:
            continue
        letter = _picks_open_letter(
            week_name=week_name,
            deadline_short=deadline_short,
            pick_url=pick_url,
            nudge=payment_nudge_for(enrollment, bool(user.is_admin)),
            season_year=season_year,
        )
        plain, html = render_letter(letter)
        if send_platform_email(user.email, letter.subject, plain, html):
            success_count += 1

    logger.info("Picks-open email: %s/%s sent for week %s",
                success_count, len(enrollments), week.week_number)
    return success_count


# ============================================================================
# WEEKLY RESULTS RECAP EMAIL
# ============================================================================

def send_weekly_recap_email(week_id: int) -> int:
    """Send personalized weekly results recap to all enrolled users.

    Called after process_week_results() finalizes a week's results.

    Args:
        week_id: ID of the completed week

    Returns:
        Number of emails successfully sent
    """
    print("\nSending Weekly Results Recap emails...")

    config = current_app.config
    site_url = config.get('SITE_URL', 'http://localhost:5000')
    season_year = config.get('CFB_SEASON_YEAR', 2026)

    week = db.session.get(CfbWeek, week_id)
    if not week:
        print(f"  Week ID {week_id} not found")
        return 0

    week_name = get_week_display_name(week)
    deadline = make_aware(week.deadline)
    is_playoff = is_week_playoff(week)
    print(f"  Week: {week_name}")

    # ---- Gather all picks for this week ----
    all_picks = CfbPick.query.filter_by(week_id=week_id).all()
    pick_by_user: dict[int, CfbPick] = {p.user_id: p for p in all_picks}

    # ---- Build game results lookup (team_id -> game) ----
    games = CfbGame.query.filter_by(week_id=week_id).all()
    games_by_team: dict[int, CfbGame] = {}
    for game in games:
        if game.home_team_id:
            games_by_team[game.home_team_id] = game
        if game.away_team_id:
            games_by_team[game.away_team_id] = game

    # ---- Week summary stats ----
    correct_count = sum(1 for p in all_picks if p.is_correct is True)
    incorrect_count = sum(1 for p in all_picks if p.is_correct is False)

    # ---- Identify eliminations this week (keyed by user_id) ----
    # CfbWeekOutcome snapshots are the SSoT — they see no-pick
    # eliminations (DQ-2), which pick rows cannot. Display names are
    # not unique, so identity comparisons must never use them (audit §2).
    all_enrollments = CfbEnrollment.query.filter_by(season_year=season_year).all()
    enrollment_by_user = {e.user_id: e for e in all_enrollments}
    active_count = sum(1 for e in all_enrollments if not e.is_eliminated)

    outcome_by_user = {
        o.user_id: o
        for o in CfbWeekOutcome.query.filter_by(week_id=week_id).all()
    }
    if outcome_by_user:
        eliminated_this_week_ids = {
            uid for uid, o in outcome_by_user.items() if o.eliminated_this_week
        }
    else:
        # Week completed without snapshots (pre-snapshot data) — fall
        # back to pick-based detection; no-pick eliminations are
        # undetectable here, so log it rather than guess.
        logger.warning(
            "No CfbWeekOutcome rows for week %s — recap falling back to "
            "pick-based elimination detection", week_id,
        )
        eliminated_this_week_ids = {
            p.user_id for p in all_picks
            if p.is_correct is False
            and (e := enrollment_by_user.get(p.user_id)) is not None
            and e.is_eliminated
        }

    eliminated_this_week = sorted(
        enrollment_by_user[uid].get_display_name()
        for uid in eliminated_this_week_ids if uid in enrollment_by_user
    )

    # ---- Calculate rankings (non-eliminated, sorted by lives desc then spread asc) ----
    ranked = sorted(
        [e for e in all_enrollments if not e.is_eliminated],
        key=lambda e: (-e.lives_remaining, e.cumulative_spread),
    )
    rank_by_user: dict[int, int] = {}
    for i, enrollment in enumerate(ranked):
        rank_by_user[enrollment.user_id] = i + 1

    # ---- Send personalized recap (DQ-5 recipients) ----
    # Active players plus this week's eliminations only — a player
    # eliminated in a prior week already got their notice and gets
    # nothing further.
    recipients = [
        e for e in all_enrollments
        if not e.is_eliminated or e.user_id in eliminated_this_week_ids
    ]
    # Load every recipient's User in one query (was a get per recipient).
    users_by_id = {
        u.id: u for u in User.query.filter(
            User.id.in_([e.user_id for e in recipients])
        ).all()
    } if recipients else {}
    success_count = 0

    for enrollment in recipients:
        user = users_by_id.get(enrollment.user_id)
        if not user or not user.email:
            continue

        display_name = enrollment.get_display_name()
        pick = pick_by_user.get(enrollment.user_id)

        # Detect autopick (created after deadline). created_at is naive
        # UTC — convert via to_pool_time, never make_aware (which would
        # read it as pool wall clock and shift it +5/6h past the deadline).
        is_autopick = False
        if pick and pick.created_at:
            pick_time = to_pool_time(pick.created_at)
            if pick_time > deadline:
                is_autopick = True

        # Pick result details
        if pick:
            team_name = pick.team.name if pick.team else "Unknown"
            game = games_by_team.get(pick.team_id)
            spread = game.get_spread_for_team(pick.team_id) if game else None

            if pick.is_correct is True:
                outcome = "SURVIVED"
            elif pick.is_correct is False:
                outcome = "LOST A LIFE"
            else:
                outcome = "PENDING"
        else:
            team_name = None
            outcome = None
            spread = None

        # Current status
        lives = enrollment.lives_remaining
        cumulative_spread = enrollment.cumulative_spread
        rank = rank_by_user.get(enrollment.user_id)
        was_eliminated_this_week = enrollment.user_id in eliminated_this_week_ids
        outcome_row = outcome_by_user.get(enrollment.user_id)
        no_pick_lost_life = bool(outcome_row and outcome_row.no_pick)

        letter = _recap_letter(
            display_name=display_name,
            week_name=week_name,
            team_name=team_name,
            outcome=outcome,
            spread=spread,
            is_autopick=is_autopick,
            lives=lives,
            cumulative_spread=cumulative_spread,
            rank=rank,
            active_count=active_count,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            total_picks=len(all_picks),
            eliminated_names=eliminated_this_week,
            was_eliminated=was_eliminated_this_week,
            is_playoff=is_playoff,
            results_url=f"{site_url}/cfb/results/{week.week_number}",
            season_year=season_year,
            no_pick_lost_life=no_pick_lost_life,
        )
        plain, html = render_letter(letter)
        if send_platform_email(user.email, letter.subject, plain, html):
            success_count += 1

    print(f"\nResults Recap Summary: {success_count}/{len(recipients)} emails sent")
    return success_count


RESULT_WORDS = {'SURVIVED': 'Survived', 'LOST A LIFE': 'Lost a life',
                'PENDING': 'Pending'}


def _players_remain(count: int) -> str:
    """'3 players remain' / '1 player remains' (pluralization is a rule)."""
    if count == 1:
        return '1 player remains'
    return f'{count} players remain'


def _recap_letter(*, display_name, week_name, team_name, outcome, spread,
                  is_autopick, lives, cumulative_spread, rank, active_count,
                  correct_count, incorrect_count, total_picks,
                  eliminated_names, was_eliminated, is_playoff, results_url,
                  season_year, no_pick_lost_life=False):
    """The weekly verdict as a Club Letter (personal: greets by name).

    Results are said in words (Survived / Lost a life / Pending), never by
    colour (the Traffic-Light Ban, DESIGN.md 6.6); the standing and the
    week around the pool are labelled facts in result blocks, not a metric
    row. The eliminated are a list, not red badges.
    """
    if was_eliminated:
        subject = f"You've been eliminated: CFB Survivor, {week_name}"
        headline = 'End of the road'
        lede = [f'You have been eliminated. {_players_remain(active_count)}.']
    elif outcome == 'SURVIVED':
        subject = f'You survived: CFB Survivor, {week_name}'
        headline = f'You survived {week_name}'
        lede = [f'Here is how {week_name} went down.']
    else:
        subject = f'Results: CFB Survivor, {week_name}'
        headline = f'{week_name} results'
        lede = [f'Here is how {week_name} went down.']

    facts = []
    if team_name:
        facts.append(('Your pick', team_name,
                      'autopick' if is_autopick else None))
        facts.append(('Result', RESULT_WORDS[outcome]))
        if spread is not None:
            facts.append(('Spread', f'{spread:+.1f}'))
    elif no_pick_lost_life:
        # DQ-2: missing the deadline costs a life.
        facts.append(('Your pick', 'No pick: life lost'))
    else:
        facts.append(('Your pick', 'No pick submitted'))

    if was_eliminated:
        standing = [('Final cumulative spread', f'{cumulative_spread:.1f}')]
    else:
        standing = [('Lives', f'{lives} of 2'),
                    ('Cumulative spread', f'{cumulative_spread:.1f}')]
        if rank:
            standing.append(('Rank', f'{rank} of {active_count} active'))
    extras = [
        result_block('Your standing', standing),
        result_block(f'{week_name} around the pool', [
            ('Picks submitted', str(total_picks)),
            ('Correct', str(correct_count)),
            ('Incorrect', str(incorrect_count)),
            ('Players remaining', str(active_count)),
        ]),
    ]
    supporting = []
    if eliminated_names:
        extras.append(items_block(eliminated_names,
                                  title='Eliminated this week'))
    else:
        supporting.append('No eliminations this week. Everyone survived.')
    if is_playoff:
        supporting.append('College Football Playoff: every team has been '
                          'reset.')

    return Letter(
        subject=subject,
        headline=headline,
        eyebrow=f'CFB Survivor · {week_name} results',
        game_slug='cfb',
        season=season_year,
        preheader=lede[0],
        greeting=display_name,
        lede=lede,
        facts=facts,
        extras=extras,
        cta=('View results', results_url),
        supporting=supporting,
    )
