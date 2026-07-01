"""
Golf Pick 'Em — CLI Commands
===============================
Flask CLI commands for API sync, data processing, and maintenance.
All commands are namespaced under the 'golf' AppGroup to avoid
collision with other game commands.

Usage:
    flask golf seed-schedule
    flask golf force-schedule-sync
    flask golf sync-run --mode field
    flask golf sync-run --mode results
    flask golf check-wd
    flask golf remind
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import click
from flask import current_app
from flask.cli import AppGroup

from extensions import db
from games.golf.models import GolfTournament, GolfTournamentField, GolfEnrollment
from games.golf.utils import GOLF_LEAGUE_TZ
from games.golf.services.sync import (
    SlashGolfAPI,
    TournamentSync,
    seed_schedule,
    get_upcoming_tournament,
    get_upcoming_tournaments_window,
    get_active_tournaments,
    get_recently_completed_tournaments,
    get_tournaments_pending_finalization,
)

# Create a CLI group so commands are: flask golf sync-run, flask golf check-wd, etc.
golf_cli = AppGroup('golf', help="Golf Pick 'Em management commands.")


def _make_api_and_sync():
    """Build SlashGolfAPI + TournamentSync from current app config."""
    api_key = current_app.config.get('SLASHGOLF_API_KEY')
    if not api_key:
        click.echo("Error: SLASHGOLF_API_KEY not set")
        sys.exit(1)
    sync_mode = current_app.config.get('SYNC_MODE', 'standard').lower()
    fallback_deadline_hour = current_app.config.get('FIXED_DEADLINE_HOUR_CT', 7)
    api = SlashGolfAPI(api_key, sync_mode=sync_mode)
    sync = TournamentSync(api, sync_mode=sync_mode, fallback_deadline_hour=fallback_deadline_hour)
    return api, sync


@golf_cli.command('sync-run')
@click.option('--mode', type=click.Choice([
    'schedule', 'field', 'live', 'live-with-wd',
    'withdrawals', 'results', 'earnings', 'remind', 'all'
]), required=True)
def sync_run_cmd(mode):
    """Unified automation entrypoint for scheduled tasks."""
    # Reminders never touch the API — short-circuit before building the client
    # so 'remind' works with no SLASHGOLF_API_KEY set (it's the golf-remind timer
    # entrypoint; the standalone `flask golf remind` stays as an alias).
    if mode == 'remind':
        from games.golf.services.reminders import run_reminder_check
        run_reminder_check()
        return

    # '--mode all' chains schedule/field/live/withdrawals/results/earnings with
    # only partial weekday gates — a broad recurring job that over-calls the API
    # and can fire emails at unintended times. It stays a dev/manual convenience;
    # production schedules the individual modes via the golf-* systemd timers.
    if mode == 'all' and os.environ.get('ENVIRONMENT', '').lower() == 'production':
        click.echo(
            "'--mode all' is disabled in production — schedule the individual "
            "modes via the golf-* systemd timers instead."
        )
        sys.exit(1)

    api, sync = _make_api_and_sync()
    sync_mode = current_app.config.get('SYNC_MODE', 'standard').lower()
    year = current_app.config.get('SEASON_YEAR', datetime.now(timezone.utc).year)
    exit_code = 0

    free_tier_blocked = set()  # withdrawal sync now permitted on free tier
    if sync_mode == 'free' and mode in free_tier_blocked:
        click.echo(f"Free tier mode: '{mode}' sync disabled to stay within RapidAPI limits")
        sys.exit(0)

    # Determine timing for admin alert logic
    now = datetime.now(GOLF_LEAGUE_TZ)
    is_wednesday = now.weekday() == 2  # 0=Mon, 1=Tue, 2=Wed
    is_evening = now.hour >= 17  # 5 PM CT or later
    is_wednesday_evening = is_wednesday and is_evening

    try:
        if mode in ('schedule', 'all'):
            # Only sync schedule on Mondays to conserve API calls
            if datetime.now(GOLF_LEAGUE_TZ).weekday() != 0:  # 0 = Monday
                click.echo("Schedule sync runs Mondays only (skipping today)")
            else:
                imported = sync.sync_schedule(year)
                click.echo(f"Schedule sync complete ({imported} imported/updated)")

        if mode in ('field', 'all'):
            # Allow field syncs on Tuesday (1) and Wednesday (2)
            weekday = datetime.now(GOLF_LEAGUE_TZ).weekday()
            if sync_mode == 'free' and weekday not in (1, 2):
                click.echo("Free tier: field sync limited to Tue/Wed to control API usage")
            else:
                upcoming = get_upcoming_tournaments_window()
                if not upcoming:
                    click.echo("No upcoming tournaments to sync field for")
                for tournament in upcoming:
                    new_players, _ = sync.sync_tournament_field(tournament, is_wednesday_evening=is_wednesday_evening)
                    total_field = GolfTournamentField.query.filter_by(tournament_id=tournament.id).count()
                    if new_players > 0:
                        click.echo(f"Synced {new_players} new players for {tournament.name} (total: {total_field})")
                    else:
                        click.echo(f"Field up-to-date for {tournament.name} (total: {total_field} players)")

        if mode in ('live', 'all'):
            active = get_active_tournaments()
            if not active:
                click.echo("No active tournaments for live sync")
            for tournament in active:
                updated = sync.sync_live_leaderboard(tournament)
                if updated:
                    click.echo(f"Updated {updated} leaderboard entries with projected earnings for {tournament.name}")

        if mode == 'live-with-wd':
            # Combined live update + withdrawal check (for Friday 8 PM critical timing)
            active = get_active_tournaments()
            if not active:
                click.echo("No active tournaments for live+WD sync")
            for tournament in active:
                # First update leaderboard
                updated = sync.sync_live_leaderboard(tournament)
                if updated:
                    click.echo(f"Updated {updated} leaderboard entries for {tournament.name}")

                # Then check for withdrawals (force=True to bypass free tier guard)
                withdrawals = sync.check_withdrawals(tournament, force=True)
                if withdrawals:
                    click.echo(f"Withdrawals detected for {tournament.name}: {len(withdrawals)}")
                    # Log critical R2 withdrawals
                    for wd in withdrawals:
                        if wd['wd_before_r2']:
                            click.echo(f"  WARNING: {wd['name']} - WD before R2 complete (backup activation possible)")

        if mode in ('withdrawals', 'all'):
            active = get_active_tournaments()
            if not active:
                click.echo("No active tournaments for withdrawal checks")
            for tournament in active:
                withdrawals = sync.check_withdrawals(tournament, force=True)
                if withdrawals:
                    click.echo(f"Withdrawals detected for {tournament.name}: {len(withdrawals)}")

        if mode in ('results', 'all'):
            if sync_mode == 'free' and datetime.now(GOLF_LEAGUE_TZ).weekday() not in (0, 6):
                click.echo("Free tier: results sync runs Sunday night or Monday morning only")
            else:
                recent = get_recently_completed_tournaments()
                if not recent:
                    click.echo("No recently completed tournaments to process")
                for tournament in recent:
                    results_count = sync.sync_tournament_results(tournament)
                    if results_count:
                        sync.process_tournament_picks(tournament)

        if mode in ('earnings', 'all'):
            # Specifically for finalizing earnings on Monday
            pending = get_tournaments_pending_finalization()

            # Safety net: also catch "active" tournaments that are past their
            # end date but were never transitioned to "complete" by a results
            # sync.  This prevents tournaments from getting stuck as "active"
            # indefinitely if the results sync didn't run or failed.
            stale_active = GolfTournament.query.filter(
                GolfTournament.status == "active",
                GolfTournament.end_date < datetime.now(GOLF_LEAGUE_TZ) - timedelta(hours=12),
                GolfTournament.results_finalized == False
            ).order_by(GolfTournament.end_date.desc()).all()

            if stale_active:
                click.echo(f"Found {len(stale_active)} stale active tournament(s) past end date — attempting finalization")
                for tournament in stale_active:
                    click.echo(f"Finalizing stale tournament {tournament.name}...")
                    results_count = sync.sync_tournament_results(tournament)
                    if results_count:
                        sync.process_tournament_picks(tournament)
                        click.echo(f"  Finalized {results_count} results for {tournament.name}")
                    else:
                        click.echo(f"  {tournament.name} not ready (API status not Complete/Official yet)")

            if not pending and not stale_active:
                click.echo("No tournaments pending earnings finalization")
            for tournament in pending:
                click.echo(f"Finalizing earnings for {tournament.name}...")
                results_count = sync.sync_tournament_results(tournament)
                if results_count:
                    sync.process_tournament_picks(tournament)
                    click.echo(f"  Finalized {results_count} results")
                else:
                    click.echo(f"  Not ready (API status not Complete/Official yet)")

    except Exception:
        import logging
        logging.getLogger(__name__).exception("sync-run failed")
        exit_code = 1

    sys.exit(exit_code)


@golf_cli.command('seed-schedule')
def seed_schedule_cmd():
    """Seed the locked season schedule (no API call).

    Creates the 32 league tournaments for the configured season so a fresh
    platform season isn't empty (sync_schedule only *updates* existing rows).
    Idempotent — safe to re-run; a real API purse already written is preserved.

    Seeded rows carry a placeholder api_tourn_id (``YYYY_NN``) and purse 0
    (displayed via effective_purse until the API provides the official number).
    Run ``flask golf force-schedule-sync`` next: it links each seeded row to its
    real SlashGolf tourn id by name. Any event whose API name differs from our
    locked name won't auto-link and needs a one-off manual id fix.
    """
    year = current_app.config.get('SEASON_YEAR', 2026)
    try:
        created, updated = seed_schedule(year)
    except ValueError as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)
    click.echo(f"Seeded golf schedule for {year}: {created} created, {updated} updated")


@golf_cli.command('force-schedule-sync')
def force_schedule_sync_cmd():
    """Run sync_schedule() now, bypassing the Monday-only gate in sync-run.

    Use to pick up a purse/format announced mid-week (e.g. a major purse going
    live during tournament week), and to link seeded placeholder rows to their
    real SlashGolf tourn ids by name after ``seed-schedule``.
    """
    _, sync = _make_api_and_sync()
    year = current_app.config.get('SEASON_YEAR', 2026)
    updated = sync.sync_schedule(year)
    click.echo(f"Force schedule sync complete ({updated} tournaments updated)")


@golf_cli.command('sync-schedule')
def sync_schedule_cmd():
    """Import season schedule from API."""
    _, sync = _make_api_and_sync()
    year = current_app.config.get('SEASON_YEAR', 2026)
    sync.sync_schedule(year)


@golf_cli.command('sync-field')
def sync_field_cmd():
    """Sync field for upcoming tournament."""
    _, sync = _make_api_and_sync()
    tournament = get_upcoming_tournament()
    if not tournament:
        click.echo("No upcoming tournament found")
        return
    sync.sync_tournament_field(tournament)


@golf_cli.command('sync-results')
def sync_results_cmd():
    """Sync results for just-completed tournament."""
    _, sync = _make_api_and_sync()
    tournament = GolfTournament.query.filter_by(status="active").first()
    if not tournament:
        click.echo("No active tournament to process")
        return
    sync.sync_tournament_results(tournament)
    sync.process_tournament_picks(tournament)


@golf_cli.command('sync-earnings')
def sync_earnings_cmd():
    """Finalize earnings for completed tournaments that haven't been finalized yet."""
    _, sync = _make_api_and_sync()
    pending = get_tournaments_pending_finalization()

    # Safety net: also catch "active" tournaments that are past their
    # end date but were never transitioned to "complete" by a results
    # sync.  This prevents tournaments from getting stuck as "active"
    # indefinitely if the results sync didn't run or failed.
    stale_active = GolfTournament.query.filter(
        GolfTournament.status == "active",
        GolfTournament.end_date < datetime.now(GOLF_LEAGUE_TZ) - timedelta(hours=12),
        GolfTournament.results_finalized == False
    ).order_by(GolfTournament.end_date.desc()).all()

    if stale_active:
        click.echo(f"Found {len(stale_active)} stale active tournament(s) past end date — attempting finalization")
        for tournament in stale_active:
            click.echo(f"Attempting to finalize stale tournament {tournament.name}...")
            results_count = sync.sync_tournament_results(tournament)
            if results_count > 0:
                sync.process_tournament_picks(tournament)
                click.echo(f"  Finalized {results_count} results for {tournament.name}")
            else:
                click.echo(f"  {tournament.name} not ready or failed (API may not have official results yet)")

    if not pending and not stale_active:
        click.echo("No tournaments pending earnings finalization")
        return

    for tournament in pending:
        click.echo(f"Attempting to finalize earnings for {tournament.name}...")
        results_count = sync.sync_tournament_results(tournament)
        if results_count > 0:
            sync.process_tournament_picks(tournament)
            click.echo(f"  Finalized {results_count} results")
        else:
            click.echo(f"  Not ready or failed (API may not have official results yet)")


@golf_cli.command('check-wd')
def check_wd_cmd():
    """Check for withdrawals in active tournament."""
    _, sync = _make_api_and_sync()
    tournament = GolfTournament.query.filter_by(status="active").first()
    if not tournament:
        click.echo("No active tournament")
        return

    withdrawals = sync.check_withdrawals(tournament)

    if withdrawals:
        click.echo(f"\nWithdrawals in {tournament.name}:")
        for wd in withdrawals:
            status = "BEFORE R2" if wd["wd_before_r2"] else f"after R{wd['rounds_completed']}"
            click.echo(f"  - {wd['name']}: WD {status}")
    else:
        click.echo("No withdrawals")


@golf_cli.command('refresh-live-penalties')
def refresh_live_penalties_cmd():
    """Re-evaluate GolfPick.penalty_triggered for active/complete majors.

    Useful for local testing before the live sync has run, or to backfill after
    a fresh DB drop. The live-leaderboard sync already refreshes penalties for
    active majors on its own cadence; this is the manual equivalent (ADR-034).
    """
    from games.golf.services.sync import refresh_tournament_penalties
    year = current_app.config.get('SEASON_YEAR', 2026)
    tournaments = (
        GolfTournament.query
        .filter_by(is_major=True, season_year=year)
        .filter(GolfTournament.status.in_(['active', 'complete']))
        .all()
    )
    total = sum(refresh_tournament_penalties(t) for t in tournaments)
    db.session.commit()
    click.echo(f"Refreshed penalties across {len(tournaments)} majors. {total} picks flagged.")


@golf_cli.command('remind')
def remind_cmd():
    """Run reminder check for upcoming tournaments."""
    from games.golf.services.reminders import run_reminder_check
    run_reminder_check()


def register_golf_cli(app):
    """Register golf CLI commands with the Flask app."""
    app.cli.add_command(golf_cli)
