"""
Golf Pick 'Em — Tournament Reminder & Notification Module
===========================================================

Handles three types of emails:
1. "Picks Are Open" - Sent when field is synced (called from services/sync.py)
2. Deadline Reminders - Sent at 24h, 12h, 1h before deadline
3. Results Recap - Sent once per tournament after earnings finalized

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
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
from models.user import User

logger = logging.getLogger(__name__)

# Reminder windows (hours before deadline)
REMINDER_WINDOWS = [
    {'hours': 24, 'type': 'warning', 'emoji': ''},
    {'hours': 12, 'type': 'reminder', 'emoji': ''},
    {'hours': 1, 'type': 'final', 'emoji': ''},
]

# Tolerance window (minutes) - send reminder if within this window of the target time
TOLERANCE_MINUTES = 35

# Minimum field size required for notifications
MIN_FIELD_SIZE = 50

# Admin contact for alerts
ADMIN_EMAIL = "bhagstrom0@gmail.com"
ADMIN_NAME = "Sun Day Regrets"

# ============================================================================
# Inline style constants — Gmail-safe, no <style> blocks
# ============================================================================
_FONT_DISPLAY = "Georgia, 'Times New Roman', serif"
_FONT_BODY = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif"

_GREEN_900 = "#00432e"
_GREEN_800 = "#005c3f"
_GREEN_700 = "#006747"
_GREEN_100 = "#e8f5ef"
_GREEN_50 = "#f0faf5"
_GOLD_500 = "#b8993e"
_GOLD_300 = "#d4be6a"
_GOLD_100 = "#faf3e0"
_CREAM = "#faf8f4"
_WHITE = "#ffffff"
_TEXT_PRIMARY = "#1a1f25"
_TEXT_SECONDARY = "#4a5568"
_TEXT_MUTED = "#8b95a2"
_TEXT_ON_DARK = "#f7f8f9"
_DANGER = "#b91c1c"
_WARNING = "#d97706"


# ============================================================================
# HTML Email Infrastructure
# ============================================================================

def _html_wrapper(content_html: str, season_year: int, site_url: str) -> str:
    """Wrap email content in the standard Golf Pick 'Em HTML shell."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Golf Pick 'Em</title>
<!--[if mso]><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: {_CREAM}; font-family: {_FONT_BODY}; -webkit-font-smoothing: antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: {_CREAM};">
<tr><td align="center" style="padding: 24px 16px;">

<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%; background-color: {_WHITE};">

<!-- HEADER -->
<tr><td style="background-color: {_GREEN_800}; padding: 22px 32px; text-align: center;">
<span style="font-family: {_FONT_DISPLAY}; font-size: 22px; font-weight: 700; color: {_TEXT_ON_DARK}; letter-spacing: 0.01em;">&#9971; Golf Pick &#8217;Em</span>
</td></tr>

<!-- GOLD ACCENT BAR -->
<tr><td style="background-color: {_GOLD_500}; height: 3px; font-size: 0; line-height: 0;">&nbsp;</td></tr>

<!-- CONTENT -->
<tr><td style="padding: 32px 32px 24px 32px;">
{content_html}
</td></tr>

<!-- FOOTER -->
<tr><td style="background-color: {_GREEN_900}; padding: 20px 32px; text-align: center;">
<p style="margin: 0; font-size: 13px; color: rgba(247,248,249,0.6); font-family: {_FONT_BODY};">
Golf Pick &#8217;Em {season_year} &middot; <a href="{site_url}" style="color: {_GOLD_300}; text-decoration: none;">The Commissioner&#8217;s Club</a>
</p>
</td></tr>

</table>

</td></tr>
</table>
</body>
</html>'''


def _html_button(url: str, label: str, bg_color: str | None = None) -> str:
    """Render a CTA button as a styled <a> tag (Gmail-safe)."""
    bg = bg_color or _GREEN_700
    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td align="center" style="padding: 8px 0 16px 0;">
<a href="{url}" style="display: inline-block; background-color: {bg}; color: {_TEXT_ON_DARK}; font-family: {_FONT_BODY}; font-size: 16px; font-weight: 600; text-decoration: none; padding: 14px 36px; border-radius: 6px;">{label} &rarr;</a>
</td></tr>
</table>'''


def _html_tournament_card(tournament_name: str, purse: int, deadline_str: str,
                          accent_color: str | None = None) -> str:
    """Render a tournament info card with left accent border."""
    accent = accent_color or _GREEN_700
    bg = _GREEN_50 if accent == _GREEN_700 else _CREAM
    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-left: 4px solid {accent}; background-color: {bg}; margin-bottom: 24px;">
<tr><td style="padding: 20px 24px;">
<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; color: {_TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.05em;">This Week</p>
<p style="margin: 0 0 14px 0; font-family: {_FONT_DISPLAY}; font-size: 20px; font-weight: 700; color: {_TEXT_PRIMARY};">{tournament_name}</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
<td style="padding-right: 32px;">
<p style="margin: 0; font-size: 11px; color: {_TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.03em;">Purse</p>
<p style="margin: 2px 0 0 0; font-size: 16px; font-weight: 700; color: {_TEXT_PRIMARY};">${purse:,}</p>
</td>
<td>
<p style="margin: 0; font-size: 11px; color: {_TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.03em;">Deadline</p>
<p style="margin: 2px 0 0 0; font-size: 16px; font-weight: 700; color: {_TEXT_PRIMARY};">{deadline_str}</p>
</td>
</tr></table>
</td></tr>
</table>'''


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


# ============================================================================
# Email Sending
# ============================================================================

def send_email(to_addr: str, subject: str, body: str,
               html_body: str | None = None) -> bool:
    """Send an email with plain text and optional HTML body."""
    config = current_app.config
    email_address = config.get('EMAIL_ADDRESS', '')
    email_password = config.get('EMAIL_PASSWORD', '')
    smtp_server = config.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = config.get('SMTP_PORT', 587)
    commissioner_name = config.get('COMMISSIONER_NAME', 'The Commissioner')

    if not email_address or not email_password:
        logger.warning("Cannot send to %s: Email credentials not configured", to_addr)
        return False

    msg = MIMEMultipart('alternative')
    msg["From"] = f"{commissioner_name} <{email_address}>"
    msg["To"] = to_addr
    msg["Subject"] = subject

    # Plain text first (lowest priority in 'alternative')
    msg.attach(MIMEText(body, "plain"))

    # HTML second (highest priority — email clients prefer this)
    if html_body:
        msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)
        print(f"  Email sent to {to_addr}")
        return True
    except Exception as e:
        print(f"  Failed to send to {to_addr}: {e}")
        return False


# =============================================================================
# PICKS OPEN NOTIFICATION (Called from sync.py after field sync)
# =============================================================================

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

    print(f"\nSending 'Picks Are Open' notifications...")

    config = current_app.config
    email_address = config.get('EMAIL_ADDRESS', '')
    email_password = config.get('EMAIL_PASSWORD', '')
    if not email_address or not email_password:
        print("  Cannot send: Email credentials not configured")
        return 0

    site_url = config.get('SITE_URL', 'http://localhost:5000')
    commissioner_name = config.get('COMMISSIONER_NAME', 'The Commissioner')

    # Re-query tournament to ensure it's bound to this session
    tournament = db.session.get(GolfTournament, tournament_id)
    if not tournament:
        print(f"  Tournament ID {tournament_id} not found")
        return 0

    print(f"  Tournament: {tournament.name}")

    # Get deadline for display
    deadline = tournament.pick_deadline
    if deadline and deadline.tzinfo is None:
        deadline = GOLF_LEAGUE_TZ.localize(deadline)

    deadline_str = deadline.strftime('%A, %B %d at %I:%M %p CT') if deadline else "TBD"

    # Build email
    pick_url = f"{site_url}/golf/pick/{tournament.id}"
    subject = f"Picks Are Open: {tournament.name}"
    season_year = tournament.season_year
    tournament_name = tournament.name
    purse = tournament.purse or 0

    # Query users directly within this context
    users = User.query.all()
    success_count = 0

    for user in users:
        display_name = user.get_display_name()
        user_email = user.email

        # Get golf-specific stats from enrollment
        enrollment = GolfEnrollment.query.filter_by(
            user_id=user.id,
            season_year=season_year
        ).first()
        total_points = enrollment.total_points if enrollment else 0
        golfers_used = len(enrollment.get_used_player_ids()) if enrollment else 0

        # Plain text
        plain = f"""Hi {display_name},

The field for {tournament_name} is now available, and picks are open!

Tournament: {tournament_name}
Purse: ${purse:,}
Pick Deadline: {deadline_str}

Make your pick now: {pick_url}

Remember:
- Pick a primary golfer and a backup
- Each golfer can only be used once this season
- Points = actual prize money earned

Your Season Stats:
- Total Points: ${total_points:,}
- Golfers Used: {golfers_used}

Good luck this week!
{commissioner_name}

---
Golf Pick 'Em {season_year}
{site_url}
"""

        # HTML
        content = f'''<h2 style="margin: 0 0 6px 0; font-family: {_FONT_DISPLAY}; font-size: 24px; color: {_TEXT_PRIMARY};">Picks Are Open</h2>
<p style="margin: 0 0 24px 0; font-size: 15px; color: {_TEXT_SECONDARY};">Hi {display_name}, the field is set. Time to make your pick.</p>

{_html_tournament_card(tournament_name, purse, deadline_str)}
{_html_button(pick_url, "Make Your Pick")}

<p style="margin: 16px 0 0 0; font-size: 13px; color: {_TEXT_MUTED}; text-align: center;">Remember: each golfer can only be used once this season.</p>'''

        html = _html_wrapper(content, season_year, site_url)

        if send_email(user_email, subject, plain, html_body=html):
            success_count += 1

    print(f"\nPicks Open Summary: {success_count}/{len(users)} emails sent")
    return success_count


# =============================================================================
# DEADLINE REMINDER EMAILS
# =============================================================================

def build_reminder_email(user_display_name, user_total_points, user_golfers_used,
                         tournament_name, tournament_id, tournament_purse, tournament_season_year,
                         deadline, window, site_url, commissioner_name):
    """
    Build the email subject, plain-text body, and HTML body for a deadline reminder.

    Takes primitive values instead of ORM objects to avoid session issues.

    Returns:
        Tuple of (subject, plain_body, html_body)
    """
    time_remaining = format_time_remaining(deadline)
    pick_url = f"{site_url}/golf/pick/{tournament_id}"
    deadline_str = deadline.strftime('%A, %B %d at %I:%M %p %Z')

    # Subject line based on urgency
    if window['type'] == 'final':
        subject = f"FINAL REMINDER: {tournament_name} pick due in ~1 hour!"
    elif window['type'] == 'reminder':
        subject = f"Reminder: {tournament_name} pick due in ~12 hours"
    else:
        subject = f"Reminder: {tournament_name} pick due in ~24 hours"

    # --- Plain text body ---
    plain = f"""Hi {user_display_name},

You haven't made your pick for {tournament_name} yet!

Tournament: {tournament_name}
Purse: ${tournament_purse:,}
Deadline: {deadline_str}
Time Remaining: {time_remaining}

Make your pick now: {pick_url}

Your Season Stats:
- Total Points: ${user_total_points:,}
- Golfers Used: {user_golfers_used}

"""

    # Add urgency message based on window type
    if window['type'] == 'final':
        plain += """WARNING: THIS IS YOUR FINAL REMINDER!
The deadline is less than 1 hour away. Make your pick NOW to avoid missing out!

"""
    elif window['type'] == 'reminder':
        plain += """You have about 12 hours left. You'll receive one more reminder
1 hour before the deadline.

"""
    else:
        plain += """You have about 24 hours left. You'll receive additional reminders
at 12 hours and 1 hour before the deadline.

"""

    plain += f"""Good luck!
{commissioner_name}

---
Golf Pick 'Em {tournament_season_year}
{site_url}
"""

    # --- HTML body ---
    # Urgency-based styling
    if window['type'] == 'final':
        accent_color = _DANGER
        urgency_bg = "#fef2f2"
        urgency_label = "FINAL REMINDER"
        urgency_msg = "Less than 1 hour left. Make your pick NOW."
    elif window['type'] == 'reminder':
        accent_color = _WARNING
        urgency_bg = _GOLD_100
        urgency_label = "REMINDER"
        urgency_msg = f"About {time_remaining} left. One more reminder at 1 hour."
    else:
        accent_color = _GREEN_700
        urgency_bg = _GREEN_100
        urgency_label = "HEADS UP"
        urgency_msg = f"About {time_remaining} left. More reminders at 12h and 1h."

    content = f'''<!-- Urgency banner -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: {urgency_bg}; border-left: 4px solid {accent_color}; margin-bottom: 24px;">
<tr><td style="padding: 16px 20px;">
<p style="margin: 0 0 2px 0; font-size: 11px; font-weight: 700; color: {accent_color}; text-transform: uppercase; letter-spacing: 0.06em;">{urgency_label}</p>
<p style="margin: 0; font-size: 15px; font-weight: 600; color: {_TEXT_PRIMARY};">{urgency_msg}</p>
</td></tr>
</table>

<h2 style="margin: 0 0 6px 0; font-family: {_FONT_DISPLAY}; font-size: 22px; color: {_TEXT_PRIMARY};">Don&#8217;t Miss Out</h2>
<p style="margin: 0 0 24px 0; font-size: 15px; color: {_TEXT_SECONDARY};">Hi {user_display_name}, you haven&#8217;t made your pick yet.</p>

{_html_tournament_card(tournament_name, tournament_purse, deadline_str, accent_color=accent_color)}
{_html_button(pick_url, "Make Your Pick Now", bg_color=accent_color if window['type'] == 'final' else None)}'''

    html = _html_wrapper(content, tournament_season_year, site_url)
    return subject, plain, html


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

    print(f"\nSending admin alert...")

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

    # Get deadline for display
    deadline = tournament.pick_deadline
    if deadline and deadline.tzinfo is None:
        deadline = GOLF_LEAGUE_TZ.localize(deadline)

    deadline_str = deadline.strftime('%A, %B %d at %I:%M %p CT') if deadline else "TBD"

    subject = f"ADMIN ALERT: Field sync issue for {tournament.name}"

    body = f"""Hi {ADMIN_NAME},

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

---
Golf Pick 'Em Automated Alert System
"""

    return send_email(ADMIN_EMAIL, subject, body)


# =============================================================================
# RESULTS RECAP EMAIL (Called from sync.py after earnings finalization)
# =============================================================================

def send_results_recap_email(tournament_id: int) -> int:
    """
    Send personalized results recap to all league members.
    Called after process_tournament_picks() finalizes earnings.

    Args:
        tournament_id: ID of the finalized tournament

    Returns:
        Number of emails successfully sent
    """
    print(f"\nSending Results Recap emails...")

    config = current_app.config
    site_url = config.get('SITE_URL', 'http://localhost:5000')
    commissioner_name = config.get('COMMISSIONER_NAME', 'The Commissioner')

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
        if enrollment.total_points != prev_points:
            rank = i + 1
        else:
            rank = prev_rank
        standings[enrollment.user_id] = {
            'rank': rank,
            'total_points': enrollment.total_points,
        }
        rank_counts[rank] = rank_counts.get(rank, 0) + 1
        prev_points = enrollment.total_points
        prev_rank = rank

    # ---- Send personalized recap to each user ----
    users = User.query.all()
    success_count = 0

    subject = f"Results: {tournament_name}"

    for user in users:
        display_name = user.get_display_name()
        user_email = user.email

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
            position = result.final_position if result else "—"
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

        plain = _build_recap_plain_text(
            display_name, tournament_name, golfer_name, position,
            earnings, backup_activated, rank_display, season_total,
            top_3, user.id, season_year, site_url, commissioner_name
        )
        html = _build_recap_html(
            display_name, tournament_name, golfer_name, position,
            score, earnings, backup_activated, rank_display, season_total,
            top_3, user.id, season_year, site_url
        )

        if send_email(user_email, subject, plain, html_body=html):
            success_count += 1

    print(f"\nResults Recap Summary: {success_count}/{len(users)} emails sent")
    return success_count


def _build_recap_plain_text(display_name, tournament_name, golfer_name, position,
                            earnings, backup_activated, rank_display, season_total,
                            top_3, user_id, season_year, site_url, commissioner_name):
    """Build plain-text fallback for the results recap email."""
    backup_note = " (backup activated)" if backup_activated else ""

    if golfer_name:
        pick_line = f"Your Pick: {golfer_name}{backup_note}"
        position_line = f"Finish: {position}"
        earnings_line = f"Earnings: ${earnings:,}"
    else:
        pick_line = "Your Pick: No pick submitted"
        position_line = ""
        earnings_line = "Earnings: $0"

    top3_lines = ""
    for i, entry in enumerate(top_3, 1):
        marker = " <-- YOU" if entry['user_id'] == user_id else ""
        score_part = f" ({entry['score_to_par']})" if entry['score_to_par'] else ""
        top3_lines += f"  {i}. {entry['user_name']} -- {entry['golfer_name']}{score_part} -- ${entry['earnings']:,}{marker}\n"

    text = f"""Hi {display_name},

Here's your recap for {tournament_name}.

{pick_line}
{position_line}
{earnings_line}

Your Standing: {rank_display}
Season Total: ${season_total:,}

This Week's Top 3:
{top3_lines}
View full standings: {site_url}/golf/

Good luck next week!
{commissioner_name}

---
Golf Pick 'Em {season_year}
{site_url}
"""
    return text


def _build_recap_html(display_name, tournament_name, golfer_name, position,
                      score, earnings, backup_activated, rank_display, season_total,
                      top_3, user_id, season_year, site_url):
    """Build the HTML body for the results recap email."""

    # --- Your Pick Result Card ---
    if golfer_name:
        backup_badge = ""
        if backup_activated:
            backup_badge = f' <span style="display: inline-block; background-color: rgba(37,99,235,0.1); color: #2563eb; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px; vertical-align: middle;">BACKUP</span>'

        earnings_color = _GREEN_700 if earnings > 0 else _DANGER

        score_text = f' <span style="color: {_TEXT_MUTED}; font-size: 14px; font-weight: 400;">({score})</span>' if score else ""

        pick_card = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: {_CREAM}; border-left: 4px solid {_GREEN_700}; margin-bottom: 24px;">
<tr><td style="padding: 20px 24px;">
<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; color: {_TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.05em;">Your Pick</p>
<p style="margin: 0 0 12px 0; font-family: {_FONT_DISPLAY}; font-size: 20px; font-weight: 700; color: {_TEXT_PRIMARY};">{golfer_name}{backup_badge}</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
<td style="padding-right: 32px;">
<p style="margin: 0; font-size: 11px; color: {_TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.03em;">Finish</p>
<p style="margin: 2px 0 0 0; font-size: 18px; font-weight: 700; color: {_TEXT_PRIMARY};">{position}{score_text}</p>
</td>
<td>
<p style="margin: 0; font-size: 11px; color: {_TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.03em;">Earnings</p>
<p style="margin: 2px 0 0 0; font-size: 18px; font-weight: 700; color: {earnings_color};">${earnings:,}</p>
</td>
</tr></table>
</td></tr>
</table>'''
    else:
        pick_card = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f1f3f5; border-left: 4px solid {_TEXT_MUTED}; margin-bottom: 24px;">
<tr><td style="padding: 20px 24px;">
<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; color: {_TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.05em;">Your Pick</p>
<p style="margin: 0; font-family: {_FONT_DISPLAY}; font-size: 18px; color: {_TEXT_MUTED};">No pick submitted &mdash; $0</p>
</td></tr>
</table>'''

    # --- Your Standing ---
    standing_card = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 28px;">
<tr>
<td width="50%" style="padding-right: 8px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: {_GREEN_100}; text-align: center; border-radius: 8px;">
<tr><td style="padding: 16px;">
<p style="margin: 0 0 2px 0; font-size: 11px; font-weight: 600; color: {_TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.05em;">Rank</p>
<p style="margin: 0; font-family: {_FONT_DISPLAY}; font-size: 26px; font-weight: 700; color: {_GREEN_700};">{rank_display}</p>
</td></tr>
</table>
</td>
<td width="50%" style="padding-left: 8px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: {_GOLD_100}; text-align: center; border-radius: 8px;">
<tr><td style="padding: 16px;">
<p style="margin: 0 0 2px 0; font-size: 11px; font-weight: 600; color: {_TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.05em;">Season Total</p>
<p style="margin: 0; font-family: {_FONT_DISPLAY}; font-size: 26px; font-weight: 700; color: {_GOLD_500};">${season_total:,}</p>
</td></tr>
</table>
</td>
</tr>
</table>'''

    # --- Top 3 Weekly Leaderboard ---
    top3_rows = ""
    for i, entry in enumerate(top_3):
        is_self = entry['user_id'] == user_id
        row_bg = _GOLD_100 if is_self else (_CREAM if i % 2 == 1 else _WHITE)
        bold = "font-weight: 700;" if is_self else ""
        self_marker = f' <span style="color: {_GOLD_500}; font-size: 11px; font-weight: 700;">*</span>' if is_self else ""
        score_part = f' <span style="color: {_TEXT_MUTED}; font-size: 12px;">({entry["score_to_par"]})</span>' if entry['score_to_par'] else ""

        top3_rows += f'''<tr>
<td style="padding: 10px 12px; border-bottom: 1px solid rgba(0,67,46,0.06); background-color: {row_bg}; {bold} font-size: 14px; color: {_TEXT_PRIMARY}; text-align: center; width: 36px;">{i + 1}</td>
<td style="padding: 10px 12px; border-bottom: 1px solid rgba(0,67,46,0.06); background-color: {row_bg}; {bold} font-size: 14px; color: {_TEXT_PRIMARY};">{entry['user_name']}{self_marker}</td>
<td style="padding: 10px 12px; border-bottom: 1px solid rgba(0,67,46,0.06); background-color: {row_bg}; font-size: 14px; color: {_TEXT_SECONDARY};">{entry['golfer_name']}{score_part}</td>
<td style="padding: 10px 12px; border-bottom: 1px solid rgba(0,67,46,0.06); background-color: {row_bg}; {bold} font-size: 14px; color: {_GREEN_700}; text-align: right;">${entry['earnings']:,}</td>
</tr>'''

    leaderboard = f'''<p style="margin: 0 0 12px 0; font-family: {_FONT_DISPLAY}; font-size: 18px; color: {_TEXT_PRIMARY};">This Week&#8217;s Top 3</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse: collapse; margin-bottom: 24px;">
<tr>
<td style="background-color: {_GREEN_800}; color: {_TEXT_ON_DARK}; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; padding: 10px 12px; text-align: center; width: 36px;">#</td>
<td style="background-color: {_GREEN_800}; color: {_TEXT_ON_DARK}; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; padding: 10px 12px;">Member</td>
<td style="background-color: {_GREEN_800}; color: {_TEXT_ON_DARK}; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; padding: 10px 12px;">Golfer</td>
<td style="background-color: {_GREEN_800}; color: {_TEXT_ON_DARK}; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; padding: 10px 12px; text-align: right;">Earned</td>
</tr>
{top3_rows}
</table>'''

    # --- Assemble ---
    content = f'''<h2 style="margin: 0 0 6px 0; font-family: {_FONT_DISPLAY}; font-size: 24px; color: {_TEXT_PRIMARY};">{tournament_name}</h2>
<p style="margin: 0 0 24px 0; font-size: 15px; color: {_TEXT_SECONDARY};">Here&#8217;s how your week went, {display_name}.</p>

{pick_card}
{standing_card}
{leaderboard}
{_html_button(site_url + "/golf/", "View Full Standings")}'''

    return _html_wrapper(content, season_year, site_url)


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

    # Find tournaments with a future deadline, regardless of upcoming/active status
    tournament = GolfTournament.query.filter(
        GolfTournament.status != 'complete',
        GolfTournament.pick_deadline.isnot(None)
    ).order_by(GolfTournament.pick_deadline).first()

    if not tournament:
        return None, None

    # Make deadline timezone-aware if needed
    deadline = tournament.pick_deadline
    if deadline.tzinfo is None:
        deadline = GOLF_LEAGUE_TZ.localize(deadline)

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


def get_users_without_picks(tournament_id):
    """
    Get users who haven't made a pick for this tournament.

    Returns:
        List of User objects (still attached to session)
    """
    all_users = User.query.all()
    picked_user_ids = {
        p.user_id for p in GolfPick.query.filter_by(tournament_id=tournament_id)
    }
    return [u for u in all_users if u.id not in picked_user_ids]


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
    print(f"Golf Pick 'Em Reminder Check")
    print(f"Time: {now.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
    print("=" * 60)

    config = current_app.config
    email_address = config.get('EMAIL_ADDRESS', '')
    email_password = config.get('EMAIL_PASSWORD', '')
    site_url = config.get('SITE_URL', 'http://localhost:5000')
    commissioner_name = config.get('COMMISSIONER_NAME', 'The Commissioner')

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
        print(f"\nNot within any reminder window")
        print(f"   Next windows: 24h, 12h, 1h before deadline")
        return

    print(f"\nActive reminder window: {window['hours']}-hour ({window['type']})")

    # Get users who need reminders (returns ORM objects attached to this context)
    users_without_picks = get_users_without_picks(tournament.id)

    if not users_without_picks:
        print(f"\nAll users have made their picks for {tournament.name}!")
        return

    print(f"\nUsers without picks: {len(users_without_picks)}")

    # Extract tournament data we need for emails (primitives, not ORM references)
    tournament_name = tournament.name
    tournament_id = tournament.id
    tournament_purse = tournament.purse
    tournament_season_year = tournament.season_year

    # Send reminders - extract user data while still in context
    success_count = 0
    for user in users_without_picks:
        # Extract all user data we need (while ORM object is attached)
        user_email = user.email
        user_display_name = user.get_display_name()

        # Get golf-specific stats from enrollment
        enrollment = GolfEnrollment.query.filter_by(
            user_id=user.id,
            season_year=tournament_season_year
        ).first()
        user_total_points = enrollment.total_points if enrollment else 0
        user_golfers_used = len(enrollment.get_used_player_ids()) if enrollment else 0

        # Build email with primitive values
        subject, plain, html = build_reminder_email(
            user_display_name=user_display_name,
            user_total_points=user_total_points,
            user_golfers_used=user_golfers_used,
            tournament_name=tournament_name,
            tournament_id=tournament_id,
            tournament_purse=tournament_purse,
            tournament_season_year=tournament_season_year,
            deadline=deadline,
            window=window,
            site_url=site_url,
            commissioner_name=commissioner_name,
        )

        if send_email(user_email, subject, plain, html_body=html):
            success_count += 1

    print()
    print("-" * 60)
    print(f"Summary: {success_count}/{len(users_without_picks)} reminders sent")
    print("=" * 60)
