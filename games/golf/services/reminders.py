"""
Golf Pick 'Em — Tournament Reminder & Notification Module
===========================================================

Handles three types of member emails, all Club Letters (ADR-058:
utils/email_layout owns the markup; this module supplies words and facts):

1. "Picks Are Open" - Sent when field is synced (called from services/sync.py)
2. Deadline Reminders - Sent at 24h, 12h, 1h before deadline
3. Results Recap - Sent once per tournament after earnings finalized

Plus the admin field alert, which stays plain text (ops mail, not a letter).

Reminder Schedule:
  - 24 hours before deadline
  - 12 hours before deadline
  - 1 hour before deadline (FINAL)

IMPORTANT: Reminders are ONLY sent if the field is synced (>=50 players).
           If field is not ready, no reminders go out.

All functions run inside the existing Flask app context — do NOT wrap in
app.app_context(). They are called from CLI commands (cli.py) which
already have an app context.
"""

import logging
from datetime import datetime, timedelta

from flask import current_app

from extensions import db
from games.golf.models import (
    GolfEnrollment,
    GolfPick,
    GolfTournament,
    GolfTournamentField,
    GolfTournamentResult,
)
from games.golf.utils import GOLF_LEAGUE_TZ, format_score_to_par
from utils.email import send_platform_email
from utils.email_layout import (
    Letter,
    format_deadline_short,
    render_letter,
    result_block,
)
from utils.reminders import tier_already_sent

logger = logging.getLogger(__name__)

# Reminder windows (hours before deadline)
REMINDER_WINDOWS = [
    {'hours': 24, 'type': 'warning'},
    {'hours': 12, 'type': 'reminder'},
    {'hours': 1, 'type': 'final'},
]

# De-dup ordering for GolfTournament.last_reminder_type. Higher = closer to the
# deadline. A run whose active tier is <= the last recorded tier is a repeat (the
# hourly cron re-landing in the same window) and is skipped. Keys match the
# f"{window['hours']}h" tier tags recorded after a successful send.
REMINDER_ORDER = {'24h': 0, '12h': 1, '1h': 2}

# Tolerance window (minutes) - send reminder if within this window of the target time
TOLERANCE_MINUTES = 35

# Minimum field size required for notifications
MIN_FIELD_SIZE = 50

# CCC-branded salutation for admin alert emails (replaces the standalone
# "Sun Day Regrets" league name).
ADMIN_ALERT_NAME = "Commish"

# The one rule every golf letter restates (picks-open in full, reminders in
# brief). Golf has no payment gate (ADR-056 covers CFB + Docket only), so no
# tab strip rides these letters.
PICK_RULE = ('Pick a primary golfer and a backup. Each golfer can be used '
             'once this season. Points are the actual prize money your '
             'golfer earns.')
PICK_RULE_BRIEF = ('Pick a primary golfer and a backup before the deadline. '
                   'Each golfer can be used once this season.')


def _admin_alert_recipient() -> str:
    """Resolve the admin-alert inbox: ADMIN_EMAIL, else EMAIL_ADDRESS (dev).

    Mirrors CFB's automation._send_admin_email. In prod EMAIL_ADDRESS is the
    Brevo SMTP login (not an inbox), so ADMIN_EMAIL must be a real mailbox
    there; the fallback keeps dev working where EMAIL_ADDRESS is a real account.
    """
    config = current_app.config
    return config.get('ADMIN_EMAIL', '') or config.get('EMAIL_ADDRESS', '')


def _deadline_short(deadline) -> str:
    """'Thursday, Jun 4 · 7:00 AM CT' for a golf pick deadline.

    Golf's naive datetime columns are league wall clock (America/Chicago),
    so a naive value gains GOLF_LEAGUE_TZ before the platform formatter
    (whose naive convention is UTC) sees it.
    """
    if deadline is None:
        return 'TBD'
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=GOLF_LEAGUE_TZ)
    return format_deadline_short(deadline, tz=GOLF_LEAGUE_TZ)


# ============================================================================
# Utility Functions
# ============================================================================

def get_current_time():
    """Get current time in Central timezone."""
    return datetime.now(GOLF_LEAGUE_TZ)


def get_field_count(tournament_id):
    """Get the number of players in a tournament's field."""
    return GolfTournamentField.query.filter_by(tournament_id=tournament_id).count()


def is_field_ready(tournament_id, minimum=MIN_FIELD_SIZE):
    """Check if tournament field has enough players for picks to be open."""
    return get_field_count(tournament_id) >= minimum


# =============================================================================
# PICKS OPEN NOTIFICATION (Called from sync.py after field sync)
# =============================================================================

def _picks_open_letter(*, tournament_name, deadline_short, purse, pick_url,
                       season_total, golfers_used, season_year):
    """The field-is-set note as a Club Letter (a broadcast: no greeting).

    The season block is the letter's per-recipient depth: the casual reader
    stops at the deadline and the button; the analyst gets their running
    total and how much of their bench is spent.
    """
    return Letter(
        subject=f'Picks are open: Golf, {tournament_name}',
        headline='Picks are open',
        eyebrow=f"Golf Pick 'Em · {tournament_name}",
        game_slug='golf',
        season=season_year,
        preheader=f'Deadline {deadline_short}.',
        lede=['The field is set. Time to make your pick.'],
        facts=[('Deadline', deadline_short), ('Purse', f'${purse:,}')],
        extras=[result_block('Your season', [
            ('Season total', f'${season_total:,}'),
            ('Golfers used', str(golfers_used)),
        ])],
        cta=('Make your pick', pick_url),
        supporting=[PICK_RULE],
    )


def send_picks_open_email(tournament_id_or_obj) -> int:
    """
    Send "Picks Are Open" notification to all users.
    Called from services/sync.py after successful field sync.

    Args:
        tournament_id_or_obj: GolfTournament ID (int) or GolfTournament object

    Returns:
        Number of emails successfully sent
    """
    # Accept either tournament object or ID to avoid session issues
    if isinstance(tournament_id_or_obj, int):
        tournament_id = tournament_id_or_obj
    else:
        tournament_id = tournament_id_or_obj.id

    print("\nSending 'Picks Are Open' notifications...")

    config = current_app.config
    email_address = config.get('EMAIL_ADDRESS', '')
    email_password = config.get('EMAIL_PASSWORD', '')
    if not email_address or not email_password:
        print("  Cannot send: Email credentials not configured")
        return 0

    site_url = config.get('SITE_URL', 'http://localhost:5000')

    # Re-query tournament to ensure it's bound to this session
    tournament = db.session.get(GolfTournament, tournament_id)
    if not tournament:
        print(f"  Tournament ID {tournament_id} not found")
        return 0

    print(f"  Tournament: {tournament.name}")

    deadline_short = _deadline_short(tournament.pick_deadline)
    pick_url = f"{site_url}/golf/pick/{tournament.id}"
    season_year = tournament.season_year
    tournament_name = tournament.name
    purse = tournament.purse or 0

    # Enrollment-scoped (audit §6): mail only current-season golf enrollees, never
    # every platform user (World Cup / CFB-only accounts must not get golf mail).
    enrollments = GolfEnrollment.query.filter_by(season_year=season_year).all()
    success_count = 0

    for enrollment in enrollments:
        user = enrollment.user
        if not user or not user.email:
            continue

        letter = _picks_open_letter(
            tournament_name=tournament_name,
            deadline_short=deadline_short,
            purse=purse,
            pick_url=pick_url,
            season_total=enrollment.total_points or 0,
            golfers_used=len(enrollment.get_used_player_ids()),
            season_year=season_year,
        )
        plain, html = render_letter(letter)
        if send_platform_email(user.email, letter.subject, plain, html):
            success_count += 1

    print(f"\nPicks Open Summary: {success_count}/{len(enrollments)} emails sent")
    return success_count


# =============================================================================
# DEADLINE REMINDER EMAILS
# =============================================================================

def _reminder_letter(*, tournament_name, deadline_short, time_remaining,
                     purse, golfers_used, pick_url, window, season_year):
    """The 24h / 12h / 1h reminder as a Club Letter (a broadcast: no greeting).

    Each tier keeps a distinct subject so Gmail never threads three
    reminders into one conversation.
    """
    if window['type'] == 'final':
        subject = f'FINAL, 1 hour left: Golf, {tournament_name}'
        headline = 'Final call: one hour left'
        lede = [f'Your pick for {tournament_name} is not in and the deadline '
                f'is less than an hour away.']
    elif window['type'] == 'reminder':
        subject = f'Pick due in 12 hours: Golf, {tournament_name}'
        headline = 'Your pick is due in 12 hours'
        lede = [f'About {time_remaining} left. One more reminder comes at '
                f'one hour.']
    else:
        subject = f'Pick due in 24 hours: Golf, {tournament_name}'
        headline = 'Your pick is due in 24 hours'
        lede = [f'About {time_remaining} left. More reminders come at 12 '
                f'hours and at one hour.']
    return Letter(
        subject=subject,
        headline=headline,
        eyebrow=f"Golf Pick 'Em · {tournament_name}",
        game_slug='golf',
        season=season_year,
        preheader=f'Deadline {deadline_short}.',
        lede=lede,
        facts=[('Deadline', deadline_short),
               ('Purse', f'${purse:,}'),
               ('Golfers used', str(golfers_used))],
        cta=('Make your pick', pick_url),
        supporting=[PICK_RULE_BRIEF],
    )


# =============================================================================
# ADMIN ALERT (Called from sync.py on Wednesday if field not ready)
# =============================================================================

def send_admin_field_alert(tournament_id_or_obj, field_count: int) -> bool:
    """
    Send alert to admin when field sync fails on Wednesday.

    Args:
        tournament_id_or_obj: GolfTournament ID (int) or GolfTournament object
        field_count: Current number of players in field

    Returns:
        True if email sent successfully
    """
    # Accept either tournament object or ID to avoid session issues
    if isinstance(tournament_id_or_obj, int):
        tournament_id = tournament_id_or_obj
    else:
        tournament_id = tournament_id_or_obj.id

    print("\nSending admin alert...")

    config = current_app.config
    email_address = config.get('EMAIL_ADDRESS', '')
    email_password = config.get('EMAIL_PASSWORD', '')
    if not email_address or not email_password:
        print("  Cannot send: Email credentials not configured")
        return False

    site_url = config.get('SITE_URL', 'http://localhost:5000')

    # Re-query tournament to ensure it's bound to this session
    tournament = db.session.get(GolfTournament, tournament_id)
    if not tournament:
        print(f"  Tournament ID {tournament_id} not found")
        return False

    print(f"  Tournament: {tournament.name}")

    deadline_str = _deadline_short(tournament.pick_deadline)

    recipient = _admin_alert_recipient()
    if not recipient:
        print("  Cannot send: No admin recipient configured (ADMIN_EMAIL/EMAIL_ADDRESS)")
        return False

    subject = f"ADMIN ALERT: Field sync issue for {tournament.name}"

    body = f"""Hi {ADMIN_ALERT_NAME},

This is an automated alert from Golf Pick 'Em.

FIELD SYNC ISSUE DETECTED

Tournament: {tournament.name}
Current Field Size: {field_count} players (minimum required: {MIN_FIELD_SIZE})
Pick Deadline: {deadline_str}
Tournament Start: {tournament.start_date.strftime('%A, %B %d')}

What this means:
- The Wednesday field confirmation pass did not find enough players
- Users will NOT receive "Picks Are Open" emails
- Deadline reminder emails will NOT be sent
- Users cannot make picks without a synced field

Recommended Actions:
1. Check if the API has field data available
2. Try running a manual field sync: flask golf sync-field
3. Check SlashGolf API status for any outages
4. If the tournament is cancelled/postponed, update the database

Admin Dashboard: {site_url}/admin

This alert will only be sent once per tournament.

Corrupt Commish Club · Golf Pick 'Em Automated Alert System
"""

    return send_platform_email(recipient, subject, body)


# =============================================================================
# RESULTS RECAP EMAIL (Called from sync.py after earnings finalization)
# =============================================================================

def _recap_letter(*, display_name, tournament_name, golfer_name, position,
                  score, earnings, backup_activated, rank_display,
                  season_total, top_3, user_id, results_url, season_year):
    """The tournament recap as a Club Letter (personal: greets by name).

    The pick, its finish, and its earnings are labelled facts; the standing
    and the week's top 3 are result blocks. A backup that came off the
    bench is a quiet tag, not a badge.
    """
    facts = []
    if golfer_name:
        facts.append(('Your pick', golfer_name,
                      'backup' if backup_activated else None))
        if position is not None:
            finish = str(position)
            if score:
                finish = f'{finish} ({score})'
            facts.append(('Finish', finish))
        facts.append(('Earnings', f'${earnings:,}'))
    else:
        facts.append(('Your pick', 'No pick submitted'))
        facts.append(('Earnings', '$0'))

    top3_rows = []
    for i, entry in enumerate(top_3, 1):
        label = f"{i}. {entry['user_name']}"
        if entry['user_id'] == user_id:
            label += ' (you)'
        value = entry['golfer_name']
        if entry['score_to_par']:
            value += f" ({entry['score_to_par']})"
        value += f", ${entry['earnings']:,}"
        top3_rows.append((label, value))

    extras = [result_block('Your standing', [
        ('Rank', rank_display),
        ('Season total', f'${season_total:,}'),
    ])]
    if top3_rows:
        extras.append(result_block("This week's top 3", top3_rows))

    return Letter(
        subject=f'Results: Golf, {tournament_name}',
        headline='Results are in',
        eyebrow=f"Golf Pick 'Em · {tournament_name}",
        game_slug='golf',
        season=season_year,
        preheader=f'{tournament_name}: your week, settled.',
        greeting=display_name,
        lede=['Here is how your week went.'],
        facts=facts,
        extras=extras,
        cta=('View standings', results_url),
    )


def send_results_recap_email(tournament_id: int) -> int:
    """
    Send personalized results recap to all league members.
    Called after process_tournament_picks() finalizes earnings.

    Args:
        tournament_id: ID of the finalized tournament

    Returns:
        Number of emails successfully sent
    """
    print("\nSending Results Recap emails...")

    config = current_app.config
    site_url = config.get('SITE_URL', 'http://localhost:5000')

    tournament = db.session.get(GolfTournament, tournament_id)
    if not tournament:
        print(f"  Tournament ID {tournament_id} not found")
        return 0

    print(f"  Tournament: {tournament.name}")

    season_year = tournament.season_year
    tournament_name = tournament.name

    # ---- Gather all picks for this tournament ----
    all_picks = GolfPick.query.filter_by(tournament_id=tournament_id).all()
    pick_by_user: dict[int, GolfPick] = {pick.user_id: pick for pick in all_picks}

    # ---- Build weekly results for top-3 and per-user display ----
    weekly_results = []
    for pick in all_picks:
        earnings = pick.points_earned or 0
        active = pick.active_player
        backup_activated = (
            pick.active_player_id is not None
            and pick.active_player_id == pick.backup_player_id
        )

        result = None
        if pick.active_player_id:
            result = GolfTournamentResult.query.filter_by(
                tournament_id=tournament_id,
                player_id=pick.active_player_id
            ).first()

        weekly_results.append({
            'user_id': pick.user_id,
            'user_name': pick.user.get_display_name(),
            'golfer_name': f"{active.first_name} {active.last_name}" if active else "N/A",
            'earnings': earnings,
            'position': result.final_position if result else None,
            'score_to_par': format_score_to_par(result.score_to_par) if result else None,
            'backup_activated': backup_activated,
        })

    # Sort by earnings desc for top-3
    weekly_results.sort(key=lambda x: x['earnings'], reverse=True)
    top_3 = weekly_results[:3]

    # ---- Calculate standings with tied ranks ----
    enrollments = GolfEnrollment.query.filter_by(
        season_year=season_year
    ).order_by(GolfEnrollment.total_points.desc(), GolfEnrollment.user_id).all()
    total_users = len(enrollments)

    standings: dict[int, dict] = {}
    prev_points = None
    prev_rank = 0
    rank_counts: dict[int, int] = {}

    for i, enrollment in enumerate(enrollments):
        pts = enrollment.total_points or 0
        rank = i + 1 if pts != prev_points else prev_rank
        standings[enrollment.user_id] = {
            'rank': rank,
            'total_points': pts,
        }
        rank_counts[rank] = rank_counts.get(rank, 0) + 1
        prev_points = pts
        prev_rank = rank

    # ---- Send personalized recap to each enrolled member (audit §6) ----
    # Enrollment-scoped: reuse the season enrollments built for standings so a
    # non-golf platform account never receives a golf recap.
    success_count = 0

    for enrollment in enrollments:
        user = enrollment.user
        if not user or not user.email:
            continue

        pick = pick_by_user.get(user.id)
        user_standing = standings.get(user.id, {'rank': total_users, 'total_points': 0})
        rank = user_standing['rank']
        is_tied = rank_counts.get(rank, 1) > 1
        rank_str = f"T{rank}" if is_tied else str(rank)
        rank_display = f"{rank_str} of {total_users}"
        season_total = user_standing['total_points']

        # User's pick details
        if pick and pick.active_player_id:
            active = pick.active_player
            golfer_name = f"{active.first_name} {active.last_name}" if active else "N/A"
            earnings = pick.points_earned or 0
            backup_activated = (pick.active_player_id == pick.backup_player_id)
            result = GolfTournamentResult.query.filter_by(
                tournament_id=tournament_id,
                player_id=pick.active_player_id
            ).first()
            position = result.final_position if result else 'Pending'
            score = format_score_to_par(result.score_to_par) if result else None
        elif pick:
            # Pick exists but no active player resolved (both WD edge case)
            golfer_name = f"{pick.primary_player.first_name} {pick.primary_player.last_name}"
            earnings = pick.points_earned or 0
            backup_activated = False
            position = "WD"
            score = None
        else:
            # No pick submitted
            golfer_name = None
            earnings = 0
            backup_activated = False
            position = None
            score = None

        letter = _recap_letter(
            display_name=user.get_display_name(),
            tournament_name=tournament_name,
            golfer_name=golfer_name,
            position=position,
            score=score,
            earnings=earnings,
            backup_activated=backup_activated,
            rank_display=rank_display,
            season_total=season_total,
            top_3=top_3,
            user_id=user.id,
            results_url=f"{site_url}/golf/",
            season_year=season_year,
        )
        plain, html = render_letter(letter)
        if send_platform_email(user.email, letter.subject, plain, html):
            success_count += 1

    print(f"\nResults Recap Summary: {success_count}/{len(enrollments)} emails sent")
    return success_count


# =============================================================================
# REMINDER CHECK (Runs hourly via CLI: flask golf remind)
# =============================================================================

def get_upcoming_tournament_for_reminders():
    """
    Find the next tournament that:
    - Has a pick_deadline in the future
    - Has a deadline within the next 24 hours + tolerance (for reminders)
    - Has a synced field (>=50 players)
    - Is NOT already complete

    NOTE: We intentionally do NOT filter on status == 'upcoming' because
    the tournament can flip to 'active' (via start_date) before the
    pick deadline. Reminders should keep firing until the deadline passes.

    Returns:
        Tuple of (tournament, aware_deadline) or (None, None)
    """
    now = get_current_time()
    max_future = now + timedelta(hours=24, minutes=TOLERANCE_MINUTES)

    # Find tournaments with a future deadline, regardless of upcoming/active status.
    # Season-scoped like the sync.py automation queries (PR #106): this takes the
    # EARLIEST-deadline row and bails if that deadline has passed, so one stale
    # non-complete row from a prior season (e.g. an archived season imported
    # beside the live one) would otherwise sort first and suppress every
    # reminder for the current season.
    season_year = current_app.config['SEASON_YEAR']
    tournament = GolfTournament.query.filter(
        GolfTournament.season_year == season_year,
        GolfTournament.status != 'complete',
        GolfTournament.pick_deadline.isnot(None)
    ).order_by(GolfTournament.pick_deadline).first()

    if not tournament:
        return None, None

    # Make deadline timezone-aware if needed
    deadline = tournament.pick_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=GOLF_LEAGUE_TZ)

    # Check if deadline is in the future and within our reminder window
    if deadline <= now:
        return None, None  # Deadline already passed

    if deadline > max_future:
        return None, None  # Too far in the future for reminders

    # Check if field is ready
    if not is_field_ready(tournament.id):
        print(f"Field not ready for {tournament.name} ({get_field_count(tournament.id)} players)")
        print(f"   Reminders will not be sent until field has >={MIN_FIELD_SIZE} players")
        return None, None

    return tournament, deadline


def get_users_without_picks(tournament_id, season_year):
    """
    Enrolled users (current season) who haven't picked for this tournament.

    Scoped to GolfEnrollment (audit §6) so non-golf platform accounts never
    receive golf reminder mail; mirrors CFB get_users_without_picks(week, season).

    Returns:
        List of User objects (still attached to session)
    """
    picked_user_ids = {
        p.user_id for p in GolfPick.query.filter_by(tournament_id=tournament_id)
    }
    enrollments = GolfEnrollment.query.filter_by(season_year=season_year).all()
    return [
        e.user for e in enrollments
        if e.user and e.user.email and e.user_id not in picked_user_ids
    ]


def should_send_reminder(deadline, window_hours):
    """
    Check if we should send a reminder for this window.
    Returns True if current time is within TOLERANCE_MINUTES of the window.
    """
    now = get_current_time()
    target_time = deadline - timedelta(hours=window_hours)

    # Check if we're within the tolerance window
    window_start = target_time - timedelta(minutes=TOLERANCE_MINUTES)
    window_end = target_time + timedelta(minutes=TOLERANCE_MINUTES)

    return window_start <= now <= window_end


def get_active_reminder_window(deadline):
    """
    Determine which reminder window (if any) is currently active.
    Returns the window dict or None.
    """
    now = get_current_time()

    # Check if deadline hasn't passed
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


def run_reminder_check():
    """Main reminder processing function. Runs inside existing app context."""
    now = get_current_time()

    print()
    print("=" * 60)
    print("Golf Pick 'Em Reminder Check")
    print(f"Time: {now.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
    print("=" * 60)

    config = current_app.config
    email_address = config.get('EMAIL_ADDRESS', '')
    email_password = config.get('EMAIL_PASSWORD', '')
    site_url = config.get('SITE_URL', 'http://localhost:5000')

    if not email_address or not email_password:
        print("\nCannot proceed without email configuration")
        return

    # Get tournament (returns ORM object attached to this context)
    tournament, deadline = get_upcoming_tournament_for_reminders()

    if not tournament:
        print("\nNo upcoming tournaments within reminder window (or field not ready)")
        return

    print(f"\nTournament: {tournament.name}")
    print(f"Deadline: {deadline.strftime('%A, %B %d at %I:%M %p %Z')}")
    print(f"Time remaining: {format_time_remaining(deadline)}")
    print(f"Field size: {get_field_count(tournament.id)} players")

    # Check which reminder window is active
    window = get_active_reminder_window(deadline)

    if not window:
        print("\nNot within any reminder window")
        print("   Next windows: 24h, 12h, 1h before deadline")
        return

    print(f"\nActive reminder window: {window['hours']}-hour ({window['type']})")

    # De-dup: skip if this tier (or a later/closer tier) was already sent for this
    # tournament. Lets the reminder cron run hourly across the 24h window without
    # re-sending — the tolerance windows overlap an hourly cadence (audit §6).
    current_tier = f"{window['hours']}h"
    if tier_already_sent(tournament.last_reminder_type, current_tier,
                         REMINDER_ORDER):
        print(f"\n{current_tier} reminder already sent "
              f"(last sent: {tournament.last_reminder_type}). Skipping.")
        return

    # Get users who need reminders (returns ORM objects attached to this context)
    users_without_picks = get_users_without_picks(tournament.id, tournament.season_year)

    if not users_without_picks:
        print(f"\nAll users have made their picks for {tournament.name}!")
        return

    print(f"\nUsers without picks: {len(users_without_picks)}")

    # Extract tournament data we need for emails (primitives, not ORM references)
    tournament_name = tournament.name
    tournament_id = tournament.id
    tournament_purse = tournament.effective_purse or 0
    tournament_season_year = tournament.season_year
    deadline_short = _deadline_short(deadline)
    time_remaining = format_time_remaining(deadline)
    pick_url = f"{site_url}/golf/pick/{tournament_id}"

    # Send reminders
    success_count = 0
    for user in users_without_picks:
        user_email = user.email

        # Golf-specific stats from enrollment
        enrollment = GolfEnrollment.query.filter_by(
            user_id=user.id,
            season_year=tournament_season_year
        ).first()
        golfers_used = len(enrollment.get_used_player_ids()) if enrollment else 0

        letter = _reminder_letter(
            tournament_name=tournament_name,
            deadline_short=deadline_short,
            time_remaining=time_remaining,
            purse=tournament_purse,
            golfers_used=golfers_used,
            pick_url=pick_url,
            window=window,
            season_year=tournament_season_year,
        )
        plain, html = render_letter(letter)
        if send_platform_email(user_email, letter.subject, plain, html):
            success_count += 1

    # Record the tier once ANY send succeeds (standalone parity), so a total
    # failure leaves the tournament un-marked and the next run retries this tier.
    # We deliberately DON'T gate on all-recipient success: a single permanently
    # bad address would then keep the tier un-recorded forever and re-spam every
    # good recipient on the hourly cron — the exact duplicate-storm the de-dup
    # exists to prevent (audit §6). A transiently-failed recipient still receives
    # the next tier (24h→12h→1h); true per-recipient delivery tracking (the fully
    # correct fix) is a deferred enhancement, matching the recap-email trade-off.
    if success_count > 0:
        tournament.last_reminder_type = current_tier
        db.session.commit()
        print(f"Recorded {current_tier} reminder as sent")
    else:
        print(f"No emails sent successfully — not recording {current_tier} as sent")

    print()
    print("-" * 60)
    print(f"Summary: {success_count}/{len(users_without_picks)} reminders sent")
    print("=" * 60)
