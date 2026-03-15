"""
CFB Survivor Pool — Reminder & Notification Service
======================================================
Email pick reminders and weekly results recap.

Reminder windows:
  - 25 hours before deadline (typically Friday)
  - 1 hour before deadline (typically Saturday -- FINAL reminder)

Results recap:
  - Sent once per week after results are processed (gated by recap_email_sent)

All functions run inside the existing Flask app context (called from CLI).
"""

import logging
import smtplib
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

from extensions import db
from models import User
from games.cfb.models import CfbEnrollment, CfbWeek, CfbPick, CfbGame
from games.cfb.utils import (
    get_current_time, make_aware, get_week_display_name, is_week_playoff,
)

logger = logging.getLogger(__name__)

# Reminder windows (hours before deadline)
REMINDER_WINDOWS = [
    {'hours': 25, 'type': 'warning', 'label': '25-hour'},
    {'hours': 1, 'type': 'final', 'label': '1-hour FINAL'},
]

# Tolerance window (minutes) - send reminder if within this window of the target time
TOLERANCE_MINUTES = 35

# ============================================================================
# Inline style constants — Gmail-safe, no <style> blocks
# ============================================================================
CFB_EMAIL = {
    "primary":       "#C5050C",
    "primary_dark":  "#0f0f1a",
    "primary_light": "#e8282f",
    "accent":        "#FFFFFF",
    "bg_body":       "#1a1a2e",
    "bg_card":       "#ffffff",
    "text_primary":  "#1a1a1a",
    "text_secondary": "#4a5568",
    "text_muted":    "#8b95a2",
    "text_on_dark":  "#f7f8f9",
    "survived":      "#22c55e",
    "lost_life":     "#ef4444",
    "font_heading":  "Georgia, 'Times New Roman', serif",
    "font_body":     "-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
}


# ============================================================================
# HTML Email Infrastructure
# ============================================================================

def _cfb_html_wrapper(content_html: str, season_year: int) -> str:
    """Wrap email content in the CFB Survivor Pool HTML shell."""
    c = CFB_EMAIL
    site_url = current_app.config.get('SITE_URL', 'http://localhost:5000')
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CFB Survivor Pool</title>
<!--[if mso]><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: {c['bg_body']}; font-family: {c['font_body']}; -webkit-font-smoothing: antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: {c['bg_body']};">
<tr><td align="center" style="padding: 24px 16px;">

<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%; background-color: {c['bg_card']};">

<!-- HEADER -->
<tr><td style="background-color: {c['primary_dark']}; padding: 22px 32px; text-align: center;">
<span style="font-family: {c['font_heading']}; font-size: 22px; font-weight: 700; color: {c['text_on_dark']}; letter-spacing: 0.01em;">&#127944; CFB Survivor Pool</span>
</td></tr>

<!-- CRIMSON ACCENT BAR -->
<tr><td style="background-color: {c['primary']}; height: 3px; font-size: 0; line-height: 0;">&nbsp;</td></tr>

<!-- CONTENT -->
<tr><td style="padding: 32px 32px 24px 32px;">
{content_html}
</td></tr>

<!-- FOOTER -->
<tr><td style="background-color: {c['primary_dark']}; padding: 20px 32px; text-align: center;">
<p style="margin: 0; font-size: 13px; color: rgba(247,248,249,0.6); font-family: {c['font_body']};">
CFB Survivor Pool {season_year} &middot; <a href="{site_url}" style="color: {c['primary_light']}; text-decoration: none;">The Commissioner&#8217;s Club</a>
</p>
</td></tr>

</table>

</td></tr>
</table>
</body>
</html>'''


def _cfb_html_button(url: str, text: str, bg_color: str | None = None) -> str:
    """Render a CTA button as a styled <a> tag (Gmail-safe)."""
    c = CFB_EMAIL
    bg = bg_color or c['primary']
    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td align="center" style="padding: 8px 0 16px 0;">
<a href="{url}" style="display: inline-block; background-color: {bg}; color: {c['text_on_dark']}; font-family: {c['font_body']}; font-size: 16px; font-weight: 600; text-decoration: none; padding: 14px 36px; border-radius: 6px;">{text} &rarr;</a>
</td></tr>
</table>'''


def _cfb_html_week_card(week_name: str, deadline_str: str,
                        accent_color: str | None = None) -> str:
    """Render a week info card with left accent border."""
    c = CFB_EMAIL
    accent = accent_color or c['primary']
    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-left: 4px solid {accent}; background-color: #f8f8fa; margin-bottom: 24px;">
<tr><td style="padding: 20px 24px;">
<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em;">This Week</p>
<p style="margin: 0 0 14px 0; font-family: {c['font_heading']}; font-size: 20px; font-weight: 700; color: {c['text_primary']};">{week_name}</p>
<p style="margin: 0; font-size: 11px; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.03em;">Deadline</p>
<p style="margin: 2px 0 0 0; font-size: 16px; font-weight: 700; color: {c['text_primary']};">{deadline_str}</p>
</td></tr>
</table>'''


# ============================================================================
# Email Sending
# ============================================================================

def _send_email(to_addr, subject, body, html_body=None):
    """Send an email with plain text and optional HTML body."""
    email_address = current_app.config.get('EMAIL_ADDRESS', '')
    email_password = current_app.config.get('EMAIL_PASSWORD', '')
    smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = current_app.config.get('SMTP_PORT', 587)

    if not email_address or not email_password:
        logger.warning("Email credentials not configured; skipping.")
        return False

    msg = MIMEMultipart('alternative')
    msg['From'] = email_address
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    if html_body:
        msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)
        logger.info("Email sent to %s", to_addr)
        return True
    except Exception as e:
        logger.error("Failed to send to %s: %s", to_addr, e)
        return False


# ============================================================================
# Utility Functions
# ============================================================================

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


# ============================================================================
# PICK REMINDER EMAILS
# ============================================================================

def _build_reminder_html(display_name, week_name, deadline_str, time_remaining,
                         lives_remaining, cumulative_spread, pick_url, window,
                         season_year):
    """Build HTML body for a pick reminder email."""
    c = CFB_EMAIL

    if window['type'] == 'final':
        accent = c['lost_life']
        urgency_bg = "#fef2f2"
        urgency_label = "FINAL REMINDER"
        urgency_msg = "Less than 1 hour left. Make your pick NOW or risk elimination."
    else:
        accent = c['primary']
        urgency_bg = "#f8f8fa"
        urgency_label = "HEADS UP"
        urgency_msg = f"About {time_remaining} left. You&#8217;ll get one more reminder at 1 hour."

    # Lives visual
    lives_dots = ""
    for _ in range(lives_remaining):
        lives_dots += f'<span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: {c["survived"]}; margin-right: 4px;"></span>'
    for _ in range(2 - lives_remaining):
        lives_dots += f'<span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; border: 2px solid #d1d5db; margin-right: 4px;"></span>'

    content = f'''<!-- Urgency banner -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: {urgency_bg}; border-left: 4px solid {accent}; margin-bottom: 24px;">
<tr><td style="padding: 16px 20px;">
<p style="margin: 0 0 2px 0; font-size: 11px; font-weight: 700; color: {accent}; text-transform: uppercase; letter-spacing: 0.06em;">{urgency_label}</p>
<p style="margin: 0; font-size: 15px; font-weight: 600; color: {c['text_primary']};">{urgency_msg}</p>
</td></tr>
</table>

<h2 style="margin: 0 0 6px 0; font-family: {c['font_heading']}; font-size: 22px; color: {c['text_primary']};">You Haven&#8217;t Picked Yet</h2>
<p style="margin: 0 0 24px 0; font-size: 15px; color: {c['text_secondary']};">Hi {display_name}, the clock is ticking.</p>

{_cfb_html_week_card(week_name, deadline_str, accent_color=accent)}

<!-- Status -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 24px;">
<tr>
<td width="50%" style="padding-right: 8px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f8fa; text-align: center; border-radius: 8px;">
<tr><td style="padding: 16px;">
<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em;">Lives</p>
<p style="margin: 0;">{lives_dots}</p>
</td></tr>
</table>
</td>
<td width="50%" style="padding-left: 8px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f8fa; text-align: center; border-radius: 8px;">
<tr><td style="padding: 16px;">
<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em;">Spread</p>
<p style="margin: 0; font-family: {c['font_heading']}; font-size: 22px; font-weight: 700; color: {c['text_primary']};">{cumulative_spread:.1f}</p>
</td></tr>
</table>
</td>
</tr>
</table>

{_cfb_html_button(pick_url, "Make Your Pick", bg_color=accent if window['type'] == 'final' else None)}'''

    return _cfb_html_wrapper(content, season_year)


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

    # Get users needing reminders
    recipients = get_users_without_picks(week.id, season_year)
    if not recipients:
        print(f"\nAll active users have picks for {week_name}")
        return

    print(f"Users without picks: {len(recipients)}")

    hours_left = int((deadline - now).total_seconds() // 3600)
    deadline_str = deadline.strftime('%A, %B %d at %I:%M %p %Z')
    time_remaining = format_time_remaining(deadline)

    success_count = 0
    for enrollment, user in recipients:
        display_name = enrollment.get_display_name()
        pick_url = f"{site_url}/cfb/pick/{week.week_number}"

        if window['type'] == 'final':
            subject = f"FINAL: {week_name} pick due in ~1 hour!"
        else:
            subject = f"{week_name} pick due tomorrow"

        # Plain text
        body = f"""Hi {display_name},

You still need to make your {week_name} pick!

Deadline: {deadline_str}
Time remaining: ~{hours_left} hour(s)

Make your pick now: {pick_url}

Your status:
- Lives remaining: {enrollment.lives_remaining}
- Cumulative spread: {enrollment.cumulative_spread:.1f}

{'This is your FINAL reminder! Make your pick NOW or risk elimination.' if window['type'] == 'final' else 'You will get one more reminder before the deadline.'}

Good luck!
"""

        # HTML
        html = _build_reminder_html(
            display_name=display_name,
            week_name=week_name,
            deadline_str=deadline_str,
            time_remaining=time_remaining,
            lives_remaining=enrollment.lives_remaining,
            cumulative_spread=enrollment.cumulative_spread,
            pick_url=pick_url,
            window=window,
            season_year=season_year,
        )

        if _send_email(user.email, subject, body, html_body=html):
            success_count += 1

    print(f"\nSummary: {success_count}/{len(recipients)} reminders sent")
    print("=" * 60)


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
    print(f"\nSending Weekly Results Recap emails...")

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

    # ---- Identify eliminations this week ----
    # Users eliminated this week: had an incorrect pick AND now have 0 lives
    all_enrollments = CfbEnrollment.query.filter_by(season_year=season_year).all()
    enrollment_by_user = {e.user_id: e for e in all_enrollments}
    active_count = sum(1 for e in all_enrollments if not e.is_eliminated)

    eliminated_this_week = []
    for pick in all_picks:
        if pick.is_correct is False:
            enrollment = enrollment_by_user.get(pick.user_id)
            if enrollment and enrollment.is_eliminated:
                eliminated_this_week.append(enrollment.get_display_name())

    # ---- Calculate rankings (non-eliminated, sorted by lives desc then spread asc) ----
    ranked = sorted(
        [e for e in all_enrollments if not e.is_eliminated],
        key=lambda e: (-e.lives_remaining, e.cumulative_spread),
    )
    rank_by_user: dict[int, int] = {}
    for i, enrollment in enumerate(ranked):
        rank_by_user[enrollment.user_id] = i + 1

    # ---- Send personalized recap to each enrolled user ----
    success_count = 0

    for enrollment in all_enrollments:
        user = db.session.get(User, enrollment.user_id)
        if not user or not user.email:
            continue

        display_name = enrollment.get_display_name()
        pick = pick_by_user.get(enrollment.user_id)

        # Detect autopick (created after deadline)
        is_autopick = False
        if pick and pick.created_at:
            pick_time = make_aware(pick.created_at)
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
        was_eliminated_this_week = display_name in eliminated_this_week

        # Subject line
        if was_eliminated_this_week:
            subject = f"{week_name}: You've been eliminated"
        elif outcome == "SURVIVED":
            subject = f"{week_name}: You survived"
        else:
            subject = f"{week_name} Results"

        # Build emails
        plain = _build_recap_plain_text(
            display_name, week_name, team_name, outcome, spread,
            is_autopick, lives, cumulative_spread, rank, active_count,
            correct_count, incorrect_count, len(all_picks),
            eliminated_this_week, was_eliminated_this_week,
            is_playoff, site_url, week.week_number,
        )
        html = _build_recap_html(
            display_name, week_name, team_name, outcome, spread,
            is_autopick, lives, cumulative_spread, rank, active_count,
            correct_count, incorrect_count, len(all_picks),
            eliminated_this_week, was_eliminated_this_week,
            is_playoff, site_url, week.week_number, season_year,
        )

        if _send_email(user.email, subject, plain, html_body=html):
            success_count += 1

    print(f"\nResults Recap Summary: {success_count}/{len(all_enrollments)} emails sent")
    return success_count


def _build_recap_plain_text(display_name, week_name, team_name, outcome, spread,
                            is_autopick, lives, cumulative_spread, rank,
                            active_count, correct_count, incorrect_count,
                            total_picks, eliminated_names, was_eliminated,
                            is_playoff, site_url, week_number):
    """Build plain-text fallback for the weekly recap email."""
    lines = [f"Hi {display_name},\n"]
    lines.append(f"Here's your {week_name} recap.\n")

    # Your pick
    if team_name:
        autopick_note = " (autopick)" if is_autopick else ""
        lines.append(f"Your Pick: {team_name}{autopick_note}")
        if spread is not None:
            lines.append(f"Spread: {spread:+.1f}")
        lines.append(f"Result: {outcome}")
    else:
        lines.append("Your Pick: No pick submitted")

    lines.append("")

    # Status
    if was_eliminated:
        lines.append(f"You've been eliminated from the pool.")
        lines.append(f"Final spread: {cumulative_spread:.1f}")
    else:
        life_visual = ("*" * lives) + ("o" * (2 - lives))
        lines.append(f"Lives: {life_visual} ({lives} remaining)")
        lines.append(f"Cumulative spread: {cumulative_spread:.1f}")
        if rank:
            lines.append(f"Rank: {rank} of {active_count} active")

    lines.append("")

    # Week summary
    lines.append(f"Week Summary:")
    lines.append(f"- {total_picks} picks submitted")
    lines.append(f"- {correct_count} correct, {incorrect_count} incorrect")

    if eliminated_names:
        lines.append(f"\nEliminated this week: {', '.join(eliminated_names)}")
    else:
        lines.append(f"\nNo eliminations this week — everyone survived!")

    lines.append(f"\n{active_count} players remaining in the pool.")

    if is_playoff:
        lines.append("\nNote: CFP phase — all teams have been reset.")

    lines.append(f"\nView full results: {site_url}/cfb/results/{week_number}")
    lines.append("")

    return "\n".join(lines)


def _build_recap_html(display_name, week_name, team_name, outcome, spread,
                      is_autopick, lives, cumulative_spread, rank,
                      active_count, correct_count, incorrect_count,
                      total_picks, eliminated_names, was_eliminated,
                      is_playoff, site_url, week_number, season_year):
    """Build the HTML body for the weekly recap email."""
    c = CFB_EMAIL

    # ---- Your Pick Result Card ----
    if team_name:
        if outcome == "SURVIVED":
            outcome_color = c['survived']
            outcome_bg = "#f0fdf4"
        elif outcome == "LOST A LIFE":
            outcome_color = c['lost_life']
            outcome_bg = "#fef2f2"
        else:
            outcome_color = "#d97706"
            outcome_bg = "#fffbeb"

        autopick_badge = ""
        if is_autopick:
            autopick_badge = f' <span style="display: inline-block; background-color: rgba(217,119,6,0.1); color: #d97706; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px; vertical-align: middle;">AUTOPICK</span>'

        spread_text = ""
        if spread is not None:
            spread_text = f'<p style="margin: 0; font-size: 11px; color: {c["text_muted"]}; text-transform: uppercase; letter-spacing: 0.03em;">Spread</p><p style="margin: 2px 0 0 0; font-size: 16px; font-weight: 700; color: {c["text_primary"]};">{spread:+.1f}</p>'

        pick_card = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: {outcome_bg}; border-left: 4px solid {outcome_color}; margin-bottom: 24px;">
<tr><td style="padding: 20px 24px;">
<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em;">Your Pick</p>
<p style="margin: 0 0 12px 0; font-family: {c['font_heading']}; font-size: 20px; font-weight: 700; color: {c['text_primary']};">{team_name}{autopick_badge}</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
<td style="padding-right: 32px;">
<p style="margin: 0; font-size: 11px; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.03em;">Result</p>
<p style="margin: 2px 0 0 0; font-size: 18px; font-weight: 700; color: {outcome_color};">{outcome}</p>
</td>
<td>{spread_text}</td>
</tr></table>
</td></tr>
</table>'''
    else:
        pick_card = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f1f3f5; border-left: 4px solid {c['text_muted']}; margin-bottom: 24px;">
<tr><td style="padding: 20px 24px;">
<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em;">Your Pick</p>
<p style="margin: 0; font-family: {c['font_heading']}; font-size: 18px; color: {c['text_muted']};">No pick submitted</p>
</td></tr>
</table>'''

    # ---- Your Status ----
    lives_dots = ""
    for _ in range(lives):
        lives_dots += f'<span style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; background: {c["survived"]}; margin-right: 4px;"></span>'
    for _ in range(2 - lives):
        lives_dots += f'<span style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #d1d5db; margin-right: 4px;"></span>'

    rank_display = f"{rank} of {active_count}" if rank else "&mdash;"

    status_card = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 28px;">
<tr>
<td width="33%" style="padding-right: 6px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f8fa; text-align: center; border-radius: 8px;">
<tr><td style="padding: 16px 8px;">
<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em;">Lives</p>
<p style="margin: 0;">{lives_dots}</p>
</td></tr>
</table>
</td>
<td width="33%" style="padding: 0 3px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f8fa; text-align: center; border-radius: 8px;">
<tr><td style="padding: 16px 8px;">
<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em;">Spread</p>
<p style="margin: 0; font-family: {c['font_heading']}; font-size: 22px; font-weight: 700; color: {c['text_primary']};">{cumulative_spread:.1f}</p>
</td></tr>
</table>
</td>
<td width="33%" style="padding-left: 6px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f8fa; text-align: center; border-radius: 8px;">
<tr><td style="padding: 16px 8px;">
<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em;">Rank</p>
<p style="margin: 0; font-family: {c['font_heading']}; font-size: 22px; font-weight: 700; color: {c['text_primary']};">{rank_display}</p>
</td></tr>
</table>
</td>
</tr>
</table>'''

    # ---- Eliminations (the drama) ----
    elim_section = ""
    if eliminated_names:
        elim_badges = ""
        for name in eliminated_names:
            elim_badges += f'<span style="display: inline-block; background-color: {c["lost_life"]}; color: #fff; font-family: {c["font_body"]}; font-size: 14px; font-weight: 600; padding: 6px 14px; border-radius: 4px; margin: 3px 4px 3px 0;">{name}</span>'

        elim_section = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #fef2f2; border-left: 4px solid {c['lost_life']}; margin-bottom: 24px;">
<tr><td style="padding: 20px 24px;">
<p style="margin: 0 0 10px 0; font-family: {c['font_heading']}; font-size: 18px; font-weight: 700; color: {c['lost_life']};">Eliminated This Week</p>
<p style="margin: 0;">{elim_badges}</p>
</td></tr>
</table>'''
    else:
        elim_section = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f0fdf4; border-left: 4px solid {c['survived']}; margin-bottom: 24px;">
<tr><td style="padding: 16px 24px;">
<p style="margin: 0; font-size: 15px; font-weight: 600; color: {c['survived']};">Everyone survived this week. Impressive.</p>
</td></tr>
</table>'''

    # ---- Week summary stats ----
    summary = f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 24px;">
<tr>
<td width="33%" style="text-align: center; padding: 8px;">
<p style="margin: 0; font-family: {c['font_heading']}; font-size: 28px; font-weight: 700; color: {c['text_primary']};">{total_picks}</p>
<p style="margin: 2px 0 0 0; font-size: 11px; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em;">Picks</p>
</td>
<td width="33%" style="text-align: center; padding: 8px;">
<p style="margin: 0; font-family: {c['font_heading']}; font-size: 28px; font-weight: 700; color: {c['survived']};">{correct_count}</p>
<p style="margin: 2px 0 0 0; font-size: 11px; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em;">Correct</p>
</td>
<td width="33%" style="text-align: center; padding: 8px;">
<p style="margin: 0; font-family: {c['font_heading']}; font-size: 28px; font-weight: 700; color: {c['lost_life']};">{incorrect_count}</p>
<p style="margin: 2px 0 0 0; font-size: 11px; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.05em;">Incorrect</p>
</td>
</tr>
</table>'''

    # ---- Playoff note ----
    playoff_note = ""
    if is_playoff:
        playoff_note = f'''<p style="margin: 0 0 16px 0; font-size: 13px; color: {c['text_muted']}; text-align: center; font-style: italic;">College Football Playoff &mdash; all teams have been reset.</p>'''

    # ---- Pool status ----
    pool_line = f'''<p style="margin: 0 0 24px 0; font-size: 14px; color: {c['text_secondary']}; text-align: center;"><strong>{active_count}</strong> players remaining in the pool.</p>'''

    # ---- Assemble ----
    results_url = f"{site_url}/cfb/results/{week_number}"

    if was_eliminated:
        header_text = f"End of the road, {display_name}."
        sub_text = f"Your {week_name} journey is over. It was a good run."
    else:
        header_text = f"{week_name} Recap"
        sub_text = f"Here&#8217;s how the week went down, {display_name}."

    content = f'''<h2 style="margin: 0 0 6px 0; font-family: {c['font_heading']}; font-size: 24px; color: {c['text_primary']};">{header_text}</h2>
<p style="margin: 0 0 24px 0; font-size: 15px; color: {c['text_secondary']};">{sub_text}</p>

{pick_card}
{status_card}
{elim_section}
{summary}
{playoff_note}
{pool_line}
{_cfb_html_button(results_url, "View Full Results")}'''

    return _cfb_html_wrapper(content, season_year)
