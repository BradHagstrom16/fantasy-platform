"""
CFB Survivor Pool — Automation Service
========================================
Orchestrates weekly operations: setup, spread updates, score fetching,
and admin notifications.
"""

import logging
from datetime import datetime, timedelta, timezone

from zoneinfo import ZoneInfo
from flask import current_app

from utils.email import send_platform_email

from extensions import db
from games.cfb.models import CfbTeam, CfbWeek, CfbGame, CfbEnrollment, CfbPick
from games.cfb.constants import (
    API_BASE_URL, TEAM_NAME_MAP, SHORT_TO_API, SEASON_SCHEDULE,
)
from games.cfb.services.odds_api import odds_api_get
from games.cfb.services.score_fetcher import ScoreFetcher
from games.cfb.utils import deadline_has_passed, get_current_time, make_aware

logger = logging.getLogger(__name__)

CHICAGO_TZ = ZoneInfo('America/Chicago')

# A week still incomplete this long past its deadline has fallen out of the
# scores API's daysFrom=3 window (or needs a manual ruling) — escalate it
# in the admin summary instead of re-reporting 'partial' forever (§5.1).
STUCK_WEEK_ALERT_DAYS = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _send_admin_email(subject: str, body: str) -> bool:
    """Send a plain-text admin notification to a real admin inbox.

    Prefers ADMIN_EMAIL; falls back to EMAIL_ADDRESS for dev setups where
    that is a real account (in prod it's the Brevo SMTP login, not an inbox).
    """
    recipient = (current_app.config.get('ADMIN_EMAIL', '')
                 or current_app.config.get('EMAIL_ADDRESS', ''))
    if not recipient:
        logger.warning("Neither ADMIN_EMAIL nor EMAIL_ADDRESS configured; "
                       "skipping admin email.")
        return False
    return send_platform_email(
        recipient,
        f'[CFB Survivor] {subject}',
        body,
    )


def _calculate_week_dates(week_number):
    """Compute start_date and deadline for a given week number.

    Returns (start_date, deadline) as timezone-aware Chicago datetimes.
    """
    week_1_start = datetime.strptime(SEASON_SCHEDULE['week_1_start'], '%Y-%m-%d')
    start_date = week_1_start + timedelta(weeks=week_number - 1)

    # Deadline: Saturday at configured hour
    deadline_hour = SEASON_SCHEDULE['default_deadline_hour']
    deadline_minute = SEASON_SCHEDULE['default_deadline_minute']

    # Find the Saturday of the week starting on Thursday
    days_until_saturday = (5 - start_date.weekday()) % 7
    saturday = start_date + timedelta(days=days_until_saturday)
    deadline = saturday.replace(hour=deadline_hour, minute=deadline_minute, second=0, microsecond=0)

    start_aware = start_date.replace(tzinfo=CHICAGO_TZ)
    deadline_aware = deadline.replace(tzinfo=CHICAGO_TZ)

    return start_aware, deadline_aware


def _lowest_orphan_week():
    """Lowest-numbered incomplete week with 0 games — a prior setup run's
    failed import that must be retried before advancing (audit §5.2)."""
    weeks = (CfbWeek.query.filter_by(is_complete=False)
             .order_by(CfbWeek.week_number).all())
    for week in weeks:
        if CfbGame.query.filter_by(week_id=week.id).count() == 0:
            return week
    return None


def _unresolvable_team_names():
    """CfbTeam names that no Odds API name maps to (master-list drift).

    A team whose name is absent from SHORT_TO_API can never be matched to
    an API event, so its games are silently never imported or scored.
    """
    return sorted(
        t.name for t in CfbTeam.query.all() if t.name not in SHORT_TO_API
    )


def _extract_home_spread(event):
    """Pick the home-team spread from an /odds event's bookmakers.

    Prefers DraftKings, else the first bookmaker that actually carries a
    spreads market with a usable home point (§5.5 — selection used to happen
    before market inspection, dropping spreads other bookmakers carried).
    A missing 'point' is skipped, never coerced to 0.0.
    Returns (point, bookmaker_key) or (None, None).
    """
    bookmakers = event.get('bookmakers', [])
    ordered = sorted(bookmakers, key=lambda bm: bm.get('key') != 'draftkings')
    for bm in ordered:
        for market in bm.get('markets', []):
            if market.get('key') != 'spreads':
                continue
            for outcome in market.get('outcomes', []):
                if outcome.get('name') == event.get('home_team'):
                    point = outcome.get('point')
                    if point is None:
                        continue
                    return float(point), bm.get('key')
    return None, None


def _get_special_week_info(week_number):
    """Return special week info if applicable.

    Returns dict with 'is_playoff' and 'round_name', or None for regular weeks.
    """
    special = SEASON_SCHEDULE.get('special_weeks', {}).get(week_number)
    if special:
        return {
            'is_playoff': special.get('is_playoff', False),
            'round_name': special.get('name'),
        }
    return None


def _import_games_for_week(week, start_date, end_date):
    """Fetch events from The Odds API and create CfbGame records.

    Returns the number of games imported.
    """
    api_key = current_app.config.get('ODDS_API_KEY', '')
    if not api_key:
        logger.warning("ODDS_API_KEY not configured; cannot import games.")
        return 0

    start_utc = start_date.astimezone(timezone.utc)
    end_utc = end_date.astimezone(timezone.utc)

    params = {
        'apiKey': api_key,
        'commenceTimeFrom': start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'commenceTimeTo': end_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

    try:
        url = f"{API_BASE_URL}/events"
        response = odds_api_get(url, params=params)
        if response.status_code != 200:
            logger.error("Events API returned status %d", response.status_code)
            return 0
        events = response.json()
    except Exception as e:
        logger.error("Events API request failed: %s", e)
        return 0

    # Build team lookup
    teams_by_name = {t.name: t for t in CfbTeam.query.all()}

    imported = 0
    skipped_untracked = []
    for event in events:
        api_home = event.get('home_team', '')
        api_away = event.get('away_team', '')
        event_id = event.get('id', '')
        commence_time = event.get('commence_time', '')

        # Map API names to short names
        home_short = TEAM_NAME_MAP.get(api_home, api_home)
        away_short = TEAM_NAME_MAP.get(api_away, api_away)

        # Look up team records
        home_team = teams_by_name.get(home_short)
        away_team = teams_by_name.get(away_short)

        # Skip if neither team is tracked
        if not home_team and not away_team:
            skipped_untracked.append(f'{away_short} @ {home_short}')
            continue

        # Skip duplicates
        if event_id:
            existing = CfbGame.query.filter_by(
                week_id=week.id, api_event_id=event_id
            ).first()
            if existing:
                continue

        # Parse game time
        game_time = None
        if commence_time:
            try:
                game_time = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
                game_time = game_time.astimezone(CHICAGO_TZ).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass

        game = CfbGame(
            week_id=week.id,
            home_team_id=home_team.id if home_team else None,
            away_team_id=away_team.id if away_team else None,
            home_team_name=home_short if not home_team else None,
            away_team_name=away_short if not away_team else None,
            api_event_id=event_id or None,
            game_time=game_time,
        )
        db.session.add(game)
        imported += 1

    if skipped_untracked:
        # Visibility for §5.4 silent drops: a tracked team falling through
        # TEAM_NAME_MAP shows up here as an "untracked" skip.
        logger.info("Skipped %d event(s) with no tracked team: %s",
                    len(skipped_untracked), '; '.join(skipped_untracked))

    if imported:
        db.session.commit()

    return imported


# ---------------------------------------------------------------------------
# Main automation functions
# ---------------------------------------------------------------------------

def run_setup():
    """Create (or retry) the next week, import games, and activate it.

    The lowest-numbered incomplete week with 0 games — a prior run whose
    import failed — is retried before advancing to a new week number, so a
    transient API failure can't permanently orphan a week (audit §5.2).
    Returns a status dict.
    """
    week = _lowest_orphan_week()
    if week:
        next_week_num = week.week_number
        # Stored as naive pool-tz wall clock; make_aware also tolerates the
        # aware round-trip SQLite gives back for automation-created weeks.
        start_date = make_aware(week.start_date)
        logger.info("Retrying game import for orphaned Week %d", next_week_num)
    else:
        last_week = CfbWeek.query.order_by(CfbWeek.week_number.desc()).first()
        next_week_num = (last_week.week_number + 1) if last_week else 1

        max_weeks = SEASON_SCHEDULE['regular_season_weeks']
        special_weeks = SEASON_SCHEDULE.get('special_weeks', {})
        max_week = max(max_weeks, max(special_weeks.keys()) if special_weeks else max_weeks)

        if next_week_num > max_week:
            return {'status': 'skipped', 'details': f'Season complete (max week {max_week})'}

        start_date, deadline = _calculate_week_dates(next_week_num)
        special = _get_special_week_info(next_week_num)
        week = CfbWeek(
            week_number=next_week_num,
            start_date=start_date,
            deadline=deadline,
            is_active=False,
            is_playoff_week=special['is_playoff'] if special else False,
            round_name=special['round_name'] if special else None,
        )
        db.session.add(week)
        db.session.commit()
        logger.info("Created Week %d", next_week_num)

    display_name = week.round_name or f'Week {next_week_num}'

    # Surface master-list drift before importing: a CfbTeam name absent
    # from SHORT_TO_API can never match an API event (§5.4).
    unresolvable = _unresolvable_team_names()
    if unresolvable:
        logger.error("CfbTeam name(s) resolve to no Odds API name: %s",
                     ', '.join(unresolvable))
        _send_admin_email(
            'Team name coverage problem',
            'These CfbTeam names match no Odds API team name, so their games '
            'can never be imported or scored:\n\n  '
            + '\n  '.join(unresolvable)
            + '\n\nFix the names on Manage Teams or update FBS_MASTER_TEAMS.',
        )

    # Import games across the full Thu→Wed week; minus 1s so the boundary
    # instant can't import into two weeks (event dedupe is week-scoped).
    end_date = start_date + timedelta(days=7) - timedelta(seconds=1)
    _import_games_for_week(week, start_date, end_date)

    game_count = CfbGame.query.filter_by(week_id=week.id).count()

    if game_count == 0:
        logger.error("Week %d created but has 0 games - NOT activating", next_week_num)
        _send_admin_email(
            f'Week setup failed — {display_name} has no games',
            f'{display_name} exists but no games were imported, so it was '
            'NOT activated. The next setup run retries this week '
            'automatically; to recover sooner, re-run '
            '`flask cfb sync --mode setup` or add games via Manage Games.',
        )
        return {
            'status': 'error',
            'details': f'{display_name} created but no games were imported. Week NOT activated.',
            'week_number': next_week_num,
            'game_count': 0,
            'unresolvable_teams': unresolvable,
        }

    # Activate the week (deactivate others)
    CfbWeek.query.update({'is_active': False})
    week.is_active = True
    db.session.commit()

    return {
        'status': 'created',
        'details': f'{display_name} created with {game_count} games and activated',
        'week_number': next_week_num,
        'game_count': game_count,
        'unresolvable_teams': unresolvable,
    }


def run_spread_update():
    """Fetch latest odds and update spreads for the active week's games.

    Skips games where spread_locked_at is already set.
    Returns a status dict.
    """
    week = CfbWeek.query.filter_by(is_active=True).first()
    if not week:
        return {'status': 'skipped', 'details': 'No active week found'}

    if week.is_complete:
        return {'status': 'skipped', 'details': f'Week {week.week_number} is already complete'}

    games = CfbGame.query.filter_by(week_id=week.id).all()
    if not games:
        return {'status': 'skipped', 'details': f'Week {week.week_number} has no games'}

    # Fetch odds from API
    api_key = current_app.config.get('ODDS_API_KEY', '')

    # Build date range from the week's games
    game_times = [g.game_time for g in games if g.game_time]
    if not game_times:
        return {'status': 'skipped', 'details': 'No game times available'}

    earliest = min(game_times)
    latest = max(game_times)

    # Ensure timezone-aware for API
    if earliest.tzinfo is None:
        earliest = earliest.replace(tzinfo=CHICAGO_TZ)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=CHICAGO_TZ)

    start_utc = earliest.astimezone(timezone.utc) - timedelta(hours=6)
    end_utc = latest.astimezone(timezone.utc) + timedelta(hours=6)

    params = {
        'apiKey': api_key,
        'regions': 'us',
        'markets': 'spreads',
        'oddsFormat': 'american',
        'commenceTimeFrom': start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'commenceTimeTo': end_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

    try:
        url = f"{API_BASE_URL}/odds"
        response = odds_api_get(url, params=params)
        if response.status_code != 200:
            return {'status': 'error', 'details': f'API returned status {response.status_code}'}
        api_events = response.json()
        credits_remaining = response.headers.get('x-requests-remaining', 'unknown')
    except Exception as e:
        return {'status': 'error', 'details': f'API request failed: {e}'}

    # Build event lookup
    events_by_id = {e.get('id'): e for e in api_events}
    events_by_teams = {}
    for e in api_events:
        home_short = TEAM_NAME_MAP.get(e.get('home_team', ''), e.get('home_team', ''))
        away_short = TEAM_NAME_MAP.get(e.get('away_team', ''), e.get('away_team', ''))
        events_by_teams[(home_short, away_short)] = e

    updated = 0
    locked = 0
    now = datetime.now(timezone.utc)

    for game in games:
        if game.spread_locked_at:
            locked += 1
            continue

        # Match API event
        event = None
        if game.api_event_id:
            event = events_by_id.get(game.api_event_id)

        if not event:
            home_name = game.get_home_team_display()
            away_name = game.get_away_team_display()
            event = events_by_teams.get((home_name, away_name))

        if not event:
            continue

        new_spread, bm_key = _extract_home_spread(event)
        if new_spread is None:
            logger.warning(
                "No usable spreads market for %s @ %s",
                game.get_away_team_display(), game.get_home_team_display())
            continue
        if bm_key != 'draftkings':
            logger.info(
                "Using fallback bookmaker '%s' for %s @ %s", bm_key,
                game.get_away_team_display(), game.get_home_team_display())
        game.home_team_spread = new_spread
        game.spread_locked_at = now
        updated += 1

    db.session.commit()

    # Surface games still without a spread — both teams are unpickable
    # until one arrives, which was previously silent (§5.5/§1).
    games_without_spread = [
        f'{g.get_away_team_display()} @ {g.get_home_team_display()}'
        for g in games if g.home_team_spread is None
    ]
    if games_without_spread:
        listing = '\n  '.join(games_without_spread)
        logger.warning("Games without spreads after update: %s",
                       '; '.join(games_without_spread))
        _send_admin_email(
            f'Games without spreads — Week {week.week_number}',
            'These games still have no spread, so BOTH teams are unpickable '
            'until one arrives (the next spread run fills gaps, or enter one '
            'via Manage Games):\n\n  ' + listing,
        )

    return {
        'status': 'updated',
        'details': (f'{updated} spreads updated, {locked} already locked, '
                    f'{len(games_without_spread)} without spreads'),
        'api_credits_remaining': credits_remaining,
        'updated': updated,
        'locked': locked,
        'games_without_spread': games_without_spread,
    }


def run_scores():
    """Find incomplete weeks past deadline and auto-process scores.

    Returns a status dict with results for each week processed.
    """
    weeks = CfbWeek.query.filter_by(is_complete=False).all()
    results = []
    stuck_weeks = []

    for week in weeks:
        deadline = make_aware(week.deadline)
        if not deadline_has_passed(deadline):
            continue

        fetcher = ScoreFetcher()
        result = fetcher.auto_process_week(week.id)
        entry = {
            'week_number': week.week_number,
            **result,
        }
        overdue = get_current_time() - deadline > timedelta(days=STUCK_WEEK_ALERT_DAYS)
        if result.get('status') not in ('completed', 'already_complete') and overdue:
            entry['stuck'] = True
            stuck_weeks.append(week.week_number)
        results.append(entry)

        # Send weekly recap email (once per week)
        week = db.session.get(CfbWeek, week.id)
        if week and week.is_complete and not week.recap_email_sent:
            try:
                from games.cfb.services.reminders import send_weekly_recap_email
                emails_sent = send_weekly_recap_email(week.id)
                if emails_sent > 0:
                    week.recap_email_sent = True
                    db.session.commit()
                    logger.info("Sent weekly recap to %s users for Week %s",
                                emails_sent, week.week_number)
            except Exception as e:
                logger.error("Failed to send recap for Week %s: %s",
                             week.week_number, e)

    if not results:
        summary = 'No incomplete weeks past deadline'
    else:
        lines = []
        for r in results:
            lines.append(f"Week {r['week_number']}: {r['status']} - {r['details']}")
            if r.get('stuck'):
                lines.append(
                    f"  STUCK: more than {STUCK_WEEK_ALERT_DAYS} days past "
                    "deadline without completing — the scores API window "
                    "(daysFrom=3) may have passed. Mark results or enter "
                    "scores via the admin pages."
                )
        summary = '\n'.join(lines)

    # Send admin email with summary
    if results:
        subject = 'Score Sync Results'
        if stuck_weeks:
            subject += f' — {len(stuck_weeks)} week(s) STUCK'
        try:
            _send_admin_email(
                subject,
                f'Score sync completed at {datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d %I:%M %p CT")}\n\n{summary}',
            )
        except Exception as e:
            logger.warning("Failed to send admin email: %s", e)

    return {
        'status': 'processed' if results else 'skipped',
        'details': summary,
        'week_results': results,
    }


def run_status():
    """Print season summary info.

    Returns a status dict with season overview.
    """
    weeks = CfbWeek.query.order_by(CfbWeek.week_number).all()
    active_week = CfbWeek.query.filter_by(is_active=True).first()

    season_year = current_app.config.get('CFB_SEASON_YEAR', 2026)
    total_enrollments = CfbEnrollment.query.filter_by(season_year=season_year).count()
    active_enrollments = CfbEnrollment.query.filter_by(
        is_eliminated=False, season_year=season_year
    ).count()

    total_games = CfbGame.query.count()
    total_picks = CfbPick.query.count()
    complete_weeks = sum(1 for w in weeks if w.is_complete)

    lines = [
        f"Season Overview ({season_year})",
        f"  Weeks created: {len(weeks)}",
        f"  Weeks complete: {complete_weeks}",
        f"  Active week: {active_week.week_number if active_week else 'None'}",
        f"  Total games: {total_games}",
        f"  Total picks: {total_picks}",
        f"  Total enrollments: {total_enrollments} ({active_enrollments} active)",
    ]

    return {
        'status': 'ok',
        'details': '\n'.join(lines),
        'active_week': active_week.week_number if active_week else None,
        'total_weeks': len(weeks),
        'complete_weeks': complete_weeks,
        'total_enrollments': total_enrollments,
        'active_enrollments': active_enrollments,
        'total_games': total_games,
    }
