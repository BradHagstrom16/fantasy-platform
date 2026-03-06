"""
Golf Pick 'Em — CLI Commands
===============================
Flask CLI commands for API sync, data processing, and maintenance.
All commands are namespaced under the 'golf' AppGroup to avoid
collision with other game commands.

Usage:
    flask golf sync-run --mode field
    flask golf sync-run --mode results
    flask golf check-wd
    flask golf remind
"""
import os
import sys
from datetime import datetime, timedelta

import click
from flask import current_app
from flask.cli import AppGroup

from extensions import db
from games.golf.models import GolfTournament, GolfTournamentField, GolfEnrollment
from games.golf.utils import GOLF_LEAGUE_TZ
from games.golf.services.sync import (
    SlashGolfAPI,
    TournamentSync,
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
    api_key = os.environ.get('SLASHGOLF_API_KEY')
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
    'withdrawals', 'results', 'earnings', 'all'
]), required=True)
def sync_run_cmd(mode):
    """Unified automation entrypoint for scheduled tasks."""
    api, sync = _make_api_and_sync()
    sync_mode = current_app.config.get('SYNC_MODE', 'standard').lower()
    year = current_app.config.get('SEASON_YEAR', datetime.now().year)
    exit_code = 0

    free_tier_blocked = {'withdrawals'}  # 'live' now allowed for projected earnings
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
                withdrawals = sync.check_withdrawals(tournament)
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


@golf_cli.command('remind')
def remind_cmd():
    """Run reminder check for upcoming tournaments."""
    from games.golf.services.reminders import run_reminder_check
    run_reminder_check()


def register_golf_cli(app):
    """Register golf CLI commands with the Flask app."""
    app.cli.add_command(golf_cli)
