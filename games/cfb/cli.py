"""
CFB Survivor Pool — CLI Commands
===================================
Flask CLI commands for CFB management.
Commands are namespaced under the 'cfb' AppGroup.

Usage:
    flask cfb populate-teams    # Seed dev teams (2025 season list)
"""
import click
from flask.cli import AppGroup

from extensions import db
from games.cfb.models import CfbTeam
from games.cfb.constants import DEV_SEED_TEAMS, TEAM_CONFERENCES

cfb_cli = AppGroup('cfb', help="CFB Survivor Pool management commands.")


@cfb_cli.command('populate-teams')
def populate_teams_cmd():
    """Seed the CfbTeam table with the 2025 season's 49 teams.

    This is a dev/test convenience command. In production, teams are
    managed via the admin Manage Teams page.
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


def register_cfb_cli(app):
    """Register CFB CLI commands with the Flask app."""
    app.cli.add_command(cfb_cli)
