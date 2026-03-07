"""
CFB Survivor Pool — Reminder Service
=======================================
Email pick reminders with window-based scheduling.

Reminder windows:
  - 25 hours before deadline (typically Friday)
  - 1 hour before deadline (typically Saturday -- FINAL reminder)

All functions run inside the existing Flask app context (called from CLI).
"""

import logging
import smtplib
from datetime import timedelta
from email.mime.text import MIMEText

from flask import current_app

from extensions import db
from models import User
from games.cfb.models import CfbEnrollment, CfbWeek, CfbPick
from games.cfb.utils import get_current_time, make_aware

logger = logging.getLogger(__name__)

# Reminder windows (hours before deadline)
REMINDER_WINDOWS = [
    {'hours': 25, 'type': 'warning', 'label': '25-hour'},
    {'hours': 1, 'type': 'final', 'label': '1-hour FINAL'},
]

# Tolerance window (minutes) - send reminder if within this window of the target time
TOLERANCE_MINUTES = 35


def _send_email(to_addr, subject, body):
    """Send a plain-text email using platform SMTP config."""
    email_address = current_app.config.get('EMAIL_ADDRESS', '')
    email_password = current_app.config.get('EMAIL_PASSWORD', '')
    smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = current_app.config.get('SMTP_PORT', 587)

    if not email_address or not email_password:
        logger.warning("Email credentials not configured; skipping reminder.")
        return False

    msg = MIMEText(body)
    msg['From'] = email_address
    msg['To'] = to_addr
    msg['Subject'] = subject

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)
        logger.info("Reminder sent to %s", to_addr)
        return True
    except Exception as e:
        logger.error("Failed to send reminder to %s: %s", to_addr, e)
        return False


def get_users_without_picks(week_id, season_year):
    """Return (enrollment, user) tuples for active enrollments missing picks this week."""
    active_enrollments = CfbEnrollment.query.filter_by(
        is_eliminated=False, season_year=season_year
    ).all()

    picked_user_ids = {
        p.user_id for p in CfbPick.query.filter_by(week_id=week_id).all()
    }

    results = []
    for enrollment in active_enrollments:
        if enrollment.user_id not in picked_user_ids:
            user = db.session.get(User, enrollment.user_id)
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


def run_reminder_check():
    """Main reminder processing function. Called from CLI."""
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

    print(f"\nWeek {week.week_number}")
    print(f"Deadline: {deadline.strftime('%A, %B %d at %I:%M %p %Z')}")
    print(f"Time remaining: {format_time_remaining(deadline)}")

    # Check which reminder window is active
    window = get_active_reminder_window(deadline)
    if not window:
        print("\nNot within any reminder window")
        return

    print(f"\nActive window: {window['label']} ({window['type']})")

    # Get users needing reminders
    recipients = get_users_without_picks(week.id, season_year)
    if not recipients:
        print(f"\nAll active users have picks for Week {week.week_number}")
        return

    print(f"Users without picks: {len(recipients)}")

    hours_left = int((deadline - now).total_seconds() // 3600)

    success_count = 0
    for enrollment, user in recipients:
        if window['type'] == 'final':
            subject = f"FINAL: Week {week.week_number} pick due in ~1 hour!"
        else:
            subject = f"Week {week.week_number} pick due tomorrow"

        body = f"""Hi {enrollment.get_display_name()},

You still need to make your Week {week.week_number} pick!

Deadline: {deadline.strftime('%A at %I:%M %p %Z')}
Time remaining: ~{hours_left} hour(s)

Make your pick now: {site_url}/cfb/pick/{week.week_number}

Your status:
- Lives remaining: {enrollment.lives_remaining}
- Cumulative spread: {enrollment.cumulative_spread:.1f}

{
'This is your FINAL reminder!' if window['type'] == 'final'
else 'You will get one more reminder before the deadline.'
}

Good luck!
"""

        if _send_email(user.email, subject, body):
            success_count += 1

    print(f"\nSummary: {success_count}/{len(recipients)} reminders sent")
    print("=" * 60)
