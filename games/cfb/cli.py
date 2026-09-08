"""
CFB Survivor Pool — CLI Commands
===================================
Flask CLI commands for CFB management.
Commands are namespaced under the 'cfb' AppGroup.

Usage:
    flask cfb populate-teams          # Seed the 2026 season team pool (one-shot)
    flask cfb sync --mode setup       # Create next week + import games
    flask cfb sync --mode spreads     # Update spreads from API
    flask cfb sync --mode scores      # Fetch scores + auto-process
    flask cfb sync --mode autopick    # Process missed-deadline auto-picks
    flask cfb sync --mode remind      # Send pick reminders
    flask cfb sync --mode status      # Print season summary
    flask cfb recalc-spreads          # Recompute every cumulative spread under the current rule
    flask cfb repair-week-dates --week N   # Re-derive a regular-season week's start/deadline from SEASON_SCHEDULE

On the droplet, hand-fire a reminder pass with ``sudo systemctl start
cfb-remind.service`` rather than ``flask cfb sync --mode remind`` in a shell:
systemd merges a manual start with an in-flight timer firing of the same
oneshot unit, which is what keeps the sent-flag de-dup race-free — there is
deliberately no lock in code (PR #169).
"""
import click
from flask.cli import AppGroup

from extensions import db
from games.cfb.constants import DEV_SEED_TEAMS, TEAM_CONFERENCES
from games.cfb.models import CfbEnrollment, CfbTeam

cfb_cli = AppGroup('cfb', help="CFB Survivor Pool management commands.")


@cfb_cli.command('populate-teams')
def populate_teams_cmd():
    """Seed the CfbTeam table with the 2026 season's 49 teams.

    One-shot initial seed for a fresh season (refuses if the table is
    non-empty) — used both for dev/test databases and the deliberate
    first prod seed. Later corrections go through the admin Manage
    Teams page.
    """
    existing = CfbTeam.query.count()
    if existing > 0:
        click.echo(f'CfbTeam table already has {existing} teams. Skipping.')
        return

    added = 0
    for name in DEV_SEED_TEAMS:
        conference = TEAM_CONFERENCES.get(name, 'Unknown')
        team = CfbTeam(name=name, conference=conference)
        db.session.add(team)
        added += 1

    db.session.commit()
    click.echo(f'Added {added} teams to cfb_team table.')


def _run_mode(mode):
    """Execute a sync mode and print results."""
    if mode == 'setup':
        from games.cfb.services.automation import run_setup
        result = run_setup()
    elif mode == 'spreads':
        from games.cfb.services.automation import run_spread_update
        result = run_spread_update()
    elif mode == 'scores':
        from games.cfb.services.automation import run_scores
        result = run_scores()
    elif mode == 'autopick':
        from games.cfb.services.game_logic import check_and_process_autopicks
        results = check_and_process_autopicks()
        result = {
            'status': 'processed',
            'details': '\n'.join(results) if results else 'No auto-picks needed',
        }
    elif mode == 'remind':
        from games.cfb.services.reminders import run_reminder_check
        run_reminder_check()
        return  # run_reminder_check handles its own output
    elif mode == 'status':
        from games.cfb.services.automation import run_status
        result = run_status()
    else:
        click.echo(f"Unknown mode: {mode}")
        return

    click.echo(f"\n[cfb sync --mode {mode}]")
    click.echo(result.get('details', str(result)))


@cfb_cli.command('sync')
@click.option('--mode', required=True,
              type=click.Choice(['setup', 'spreads', 'scores', 'autopick', 'remind', 'status']),
              help='Sync mode to run.')
def sync_cmd(mode):
    """Unified CFB automation CLI -- run weekly tasks by mode."""
    _run_mode(mode)


@cfb_cli.command('setup')
def setup_cmd():
    """Create next week and import games (never activates — ADR-062)."""
    _run_mode('setup')


@cfb_cli.command('scores')
def scores_cmd():
    """Fetch scores, auto-process completed weeks, retry the open."""
    _run_mode('scores')


@cfb_cli.command('spreads')
def spreads_cmd():
    """Open the next week with its lines, or gap-fill the open week."""
    _run_mode('spreads')


@cfb_cli.command('autopick')
def autopick_cmd():
    """Process auto-picks for users who missed the deadline."""
    _run_mode('autopick')


@cfb_cli.command('remind')
def remind_cmd():
    """Send pick reminders for the active week."""
    _run_mode('remind')


@cfb_cli.command('status')
def status_cmd():
    """Print season summary."""
    _run_mode('status')


@cfb_cli.command('recalc-spreads')
def recalc_spreads_cmd():
    """Recompute every enrollment's cumulative spread from its picks.

    Idempotent operator repair (the 2026-09-01 rule fix: a pick's spread
    counts only once its week deadline passes, and higher is better).
    Prints old -> new per member and commits.
    """
    from games.cfb.services.game_logic import settle_cumulative_spreads

    before = {e.id: (e.cumulative_spread or 0.0) for e in CfbEnrollment.query.all()}
    settled = settle_cumulative_spreads()
    changed = 0
    for enrollment in sorted(settled, key=lambda e: e.get_display_name().lower()):
        old, new = before.get(enrollment.id, 0.0), enrollment.cumulative_spread
        moved = old != new
        changed += moved
        click.echo(f"  {enrollment.get_display_name()}: {old:.1f} -> {new:.1f}"
                   f"{'  (changed)' if moved else ''}")
    click.echo(f"\n[cfb recalc-spreads] {len(settled)} enrollments recalculated, "
               f"{changed} changed")


@cfb_cli.command('repair-week-dates')
@click.option('--week', 'week_number', required=True, type=int,
              help='Regular-season week number to re-derive.')
def repair_week_dates_cmd(week_number):
    """Re-derive one week's start_date/deadline from SEASON_SCHEDULE.

    Operator repair for the 2026-09-07 incident: run_setup handed aware
    Chicago datetimes to naive columns and Postgres cast them in its GMT
    session, so Week 2's 11:00 AM CT deadline was stored as 16:00. The model
    now normalizes on assignment; this rewrites a row that was stored before
    that fix. Prints old -> new per column and commits. Idempotent.

    Refuses (exit 1, no write) a playoff or named-round week — those are
    hand-scheduled, and SEASON_SCHEDULE's rigid Saturday cadence is wrong for
    them — and a completed week, whose dates are history.
    """
    from games.cfb.models import CfbWeek
    from games.cfb.services.automation import _calculate_week_dates

    week = CfbWeek.query.filter_by(week_number=week_number).first()
    if week is None:
        click.echo(f"[cfb repair-week-dates] no Week {week_number} exists")
        raise SystemExit(1)
    label = week.round_name or f'Week {week_number}'
    if week.is_playoff_week or week.round_name:
        click.echo(f"[cfb repair-week-dates] {label} is hand-scheduled "
                   "(playoff / named round); not rewriting it from the schedule")
        raise SystemExit(1)
    if week.is_complete:
        click.echo(f"[cfb repair-week-dates] {label} is complete; its dates are history")
        raise SystemExit(1)

    start_date, deadline = _calculate_week_dates(week_number)
    changed = 0
    for column, new_value in (('start_date', start_date), ('deadline', deadline)):
        old_value = getattr(week, column)
        setattr(week, column, new_value)  # the model strips the aware value
        new_value = getattr(week, column)
        moved = old_value != new_value
        changed += moved
        click.echo(f"  {column}: {old_value:%Y-%m-%d %H:%M} -> {new_value:%Y-%m-%d %H:%M}"
                   f"{'  (changed)' if moved else ''}")
    db.session.commit()
    click.echo(f"\n[cfb repair-week-dates] {label}: "
               f"{'unchanged' if not changed else f'{changed} column(s) rewritten'}")


def register_cfb_cli(app):
    """Register CFB CLI commands with the Flask app."""
    app.cli.add_command(cfb_cli)
