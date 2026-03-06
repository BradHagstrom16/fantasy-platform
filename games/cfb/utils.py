"""
CFB Survivor Pool — Utilities
================================
Timezone helpers and display/CFP helper functions.

Timezone helpers are game-specific for now (per ADR-016). After Phase 2,
these will be candidates for refactoring into shared platform utils.

Display helpers handle week name formatting and CFP team tracking.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import current_app


# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------

def _get_pool_tz():
    """Get the pool timezone from app config."""
    tz_name = current_app.config.get('PLATFORM_TIMEZONE', 'America/Chicago')
    return ZoneInfo(tz_name)


def get_current_time():
    """Get current time in the pool's timezone (aware)."""
    return datetime.now(_get_pool_tz())


def get_utc_time():
    """Get current UTC time (aware)."""
    return datetime.now(timezone.utc)


def make_aware(dt, tz=None):
    """Convert naive datetime to aware in specified timezone.

    If no timezone is given, assumes the pool timezone.
    """
    if dt is None:
        return None
    if tz is None:
        tz = _get_pool_tz()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt


def to_utc(dt):
    """Convert any datetime to UTC."""
    if dt is None:
        return None
    dt_aware = make_aware(dt)
    return dt_aware.astimezone(timezone.utc)


def to_pool_time(dt):
    """Convert any datetime to pool timezone."""
    if dt is None:
        return None
    # If naive, assume UTC (from database)
    dt_aware = make_aware(dt, timezone.utc)
    return dt_aware.astimezone(_get_pool_tz())


def deadline_has_passed(deadline):
    """Check if a deadline has passed."""
    deadline_aware = make_aware(deadline)
    current = get_current_time()
    return current > deadline_aware


def format_deadline(deadline):
    """Format deadline for display in pool timezone."""
    if deadline is None:
        return 'TBD'
    pool_tz = _get_pool_tz()
    if deadline.tzinfo is not None:
        deadline_local = deadline.astimezone(pool_tz)
    else:
        deadline_local = deadline.replace(tzinfo=pool_tz)
    return deadline_local.strftime('%B %d, %Y at %I:%M %p %Z')


def parse_form_datetime(datetime_str):
    """Parse datetime from HTML form input and make it timezone-aware in pool timezone."""
    naive_dt = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M')
    return naive_dt.replace(tzinfo=_get_pool_tz())


def safe_is_after(dt1, dt2):
    """Safely compare two datetimes, handling mixed naive/aware.

    Returns True if dt1 is after dt2.
    """
    if dt1 is None or dt2 is None:
        return False
    dt1_aware = make_aware(dt1)
    dt2_aware = make_aware(dt2)
    return dt1_aware > dt2_aware


# ---------------------------------------------------------------------------
# Display helpers — week names and CFP tracking
# ---------------------------------------------------------------------------

def get_week_display_name(week):
    """Get the full display name for a week.

    Returns "Week 1"–"Week 14" for regular season,
    or the custom round_name for special weeks.
    """
    if not week:
        return "Unknown Week"
    if hasattr(week, 'round_name') and week.round_name:
        return week.round_name
    return f"Week {week.week_number}"


def get_week_short_label(week):
    """Get the short label for a week (used in navigation buttons).

    Returns "W1"–"W14" for regular season,
    "CCW", "R1", "QF", "SF", "F" for special weeks.
    """
    if not week:
        return "?"
    if hasattr(week, 'round_name') and week.round_name:
        label_map = {
            "Conference Championship Week": "CCW",
            "CFP Round 1": "R1",
            "CFP Quarterfinals": "QF",
            "CFP Semifinals": "SF",
            "CFP Championship": "F",
        }
        return label_map.get(week.round_name, f"W{week.week_number}")
    return f"W{week.week_number}"


def is_week_playoff(week):
    """Check if a week is a playoff week."""
    if not week:
        return False
    if hasattr(week, 'is_playoff_week'):
        return week.is_playoff_week
    # Fallback: week 16+ are playoffs
    return week.week_number >= 16


def format_week_for_title(week):
    """Format week name for page titles and headers."""
    if not week:
        return "Unknown Week"
    display = get_week_display_name(week)
    if display.startswith("Week "):
        return display
    return display


def get_playoff_teams():
    """Return the list of teams in the CFP field.

    NOTE: This is currently hardcoded for the 2025 season. In a future
    version, this should be stored in the database and admin-managed.
    """
    return [
        'Ohio State', 'Georgia', 'Oregon', 'Alabama', 'Miami', 'Oklahoma',
        'Texas A&M', 'Indiana', 'Ole Miss', 'Texas Tech', 'Tulane',
        'James Madison',
    ]


def get_cfp_eliminated_teams():
    """Return team names that have been eliminated from the CFP.

    A team is eliminated if they lost in any game during a playoff week
    where results have been recorded.
    """
    # Lazy imports to avoid circular dependency
    from extensions import db
    from games.cfb.models import CfbGame, CfbWeek, CfbTeam

    eliminated = set()

    playoff_games = (
        db.session.query(CfbGame)
        .join(CfbWeek)
        .filter(CfbWeek.is_playoff_week == True, CfbGame.home_team_won != None)
        .all()
    )

    for game in playoff_games:
        if game.home_team_won:
            if game.away_team:
                eliminated.add(game.away_team.name)
            elif game.away_team_name:
                eliminated.add(game.away_team_name)
        else:
            if game.home_team:
                eliminated.add(game.home_team.name)
            elif game.home_team_name:
                eliminated.add(game.home_team_name)

    return eliminated


def get_cfp_active_teams():
    """Return playoff teams that are still in contention (not eliminated)."""
    all_playoff = set(get_playoff_teams())
    eliminated = get_cfp_eliminated_teams()
    return list(all_playoff - eliminated)


def get_cfp_teams_in_week(week):
    """Return the team names that have a game scheduled in a specific playoff week."""
    if not week:
        return set()

    from games.cfb.models import CfbGame

    teams_playing = set()
    games = CfbGame.query.filter_by(week_id=week.id).all()

    for game in games:
        if game.home_team:
            teams_playing.add(game.home_team.name)
        elif game.home_team_name:
            teams_playing.add(game.home_team_name)
        if game.away_team:
            teams_playing.add(game.away_team.name)
        elif game.away_team_name:
            teams_playing.add(game.away_team_name)

    return teams_playing


def get_cfp_teams_on_bye(week):
    """Return active playoff teams that don't have a game this week (on bye)."""
    if not week:
        return []
    active = set(get_cfp_active_teams())
    playing = get_cfp_teams_in_week(week)
    return list(active - playing)


def get_cfp_available_teams_for_user(user_id, week):
    """Return playoff teams available for a specific user to pick in a week.

    A team is available if it is: in the CFP field, not eliminated,
    has a game this week, and hasn't been picked by this user in a
    previous CFP week.
    """
    if not week:
        return []

    from extensions import db
    from games.cfb.models import CfbTeam, CfbPick, CfbWeek as CfbWeekModel

    playoff_team_names = set(get_playoff_teams())
    eliminated_names = get_cfp_eliminated_teams()
    teams_playing_names = get_cfp_teams_in_week(week)

    used_in_cfp = (
        db.session.query(CfbPick.team_id)
        .join(CfbWeekModel)
        .filter(
            CfbPick.user_id == user_id,
            CfbWeekModel.is_playoff_week == True,
            CfbPick.week_id != week.id,
        )
        .all()
    )
    used_team_ids = {t[0] for t in used_in_cfp}

    available = []
    for team in CfbTeam.query.all():
        if team.name not in playoff_team_names:
            continue
        if team.name in eliminated_names:
            continue
        if team.name not in teams_playing_names:
            continue
        if team.id in used_team_ids:
            continue
        available.append(team)

    return available


def get_display_helpers():
    """Return a dict of display helper functions for use as template context.

    Register this on the cfb blueprint's context processor.
    """
    return {
        'get_week_display_name': get_week_display_name,
        'get_week_short_label': get_week_short_label,
        'is_week_playoff': is_week_playoff,
        'format_week_for_title': format_week_for_title,
    }
