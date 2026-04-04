"""
World Cup Fantasy Pool — CLI Commands
========================================
Flask CLI commands for World Cup management.
Commands are namespaced under the 'worldcup' AppGroup.

Usage:
    flask worldcup seed-teams     # Populate teams from world_cup_countries.py
    flask worldcup seed-matches   # Seed all 104 match shells
    flask worldcup init           # Seed teams + matches (fresh setup)
    flask worldcup recalc         # Recalculate all scores (idempotent)
    flask worldcup status         # Print tournament state summary
"""
from datetime import datetime

import click
from flask.cli import AppGroup

from extensions import db
from games.worldcup.models import WorldCupTeam, WorldCupMatch, WorldCupEnrollment

worldcup_cli = AppGroup('worldcup', help="World Cup Fantasy Pool management commands.")


@worldcup_cli.command('seed-teams')
def seed_teams_cmd():
    """Populate WorldCupTeam table from world_cup_countries.py."""
    from games.worldcup.world_cup_countries import TEAMS

    added = 0
    skipped = 0
    for code, data in TEAMS.items():
        existing = WorldCupTeam.query.filter_by(fifa_code=code).first()
        if existing:
            skipped += 1
            continue
        team = WorldCupTeam(
            fifa_code=data['fifa_code'],
            name=data['name'],
            display_name=data['display_name'],
            tier=data['tier'],
            multiplier=data['multiplier'],
            confederation=data['confederation'],
            group_letter=data['group'],
        )
        db.session.add(team)
        added += 1

    db.session.commit()
    click.echo(f'Added {added} teams, {skipped} already existed.')


@worldcup_cli.command('seed-matches')
def seed_matches_cmd():
    """Seed all 104 match shells from match_schedule.py."""
    from games.worldcup.match_schedule import MATCH_SCHEDULE

    added = 0
    skipped = 0
    for m in MATCH_SCHEDULE:
        existing = WorldCupMatch.query.filter_by(match_number=m['match_number']).first()
        if existing:
            skipped += 1
            continue

        home_team_id = None
        away_team_id = None
        if m['home_fifa_code']:
            home_team = WorldCupTeam.query.filter_by(fifa_code=m['home_fifa_code']).first()
            home_team_id = home_team.id if home_team else None
        if m['away_fifa_code']:
            away_team = WorldCupTeam.query.filter_by(fifa_code=m['away_fifa_code']).first()
            away_team_id = away_team.id if away_team else None

        kickoff = datetime.fromisoformat(m['kickoff_utc']) if m['kickoff_utc'] else None

        match = WorldCupMatch(
            match_number=m['match_number'],
            stage=m['stage'],
            group_letter=m['group_letter'],
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            kickoff_utc=kickoff,
            venue=m['venue'],
            city=m['city'],
        )
        db.session.add(match)
        added += 1

    db.session.commit()

    group_count = sum(1 for m in MATCH_SCHEDULE if m['stage'] == 'group')
    knockout_count = len(MATCH_SCHEDULE) - group_count
    click.echo(f'Added {added} matches ({group_count} group + {knockout_count} knockout), {skipped} already existed.')


@worldcup_cli.command('init')
def init_cmd():
    """Seed teams + matches (fresh setup convenience command)."""
    ctx = click.get_current_context()
    ctx.invoke(seed_teams_cmd)
    ctx.invoke(seed_matches_cmd)
    click.echo('World Cup initialization complete.')


@worldcup_cli.command('recalc')
def recalc_cmd():
    """Recalculate all scores (idempotent)."""
    try:
        from games.worldcup.services.scoring import recalculate_all_scores
        recalculate_all_scores()
        click.echo('Recalculation complete.')
    except NotImplementedError:
        click.echo('Scoring engine not yet implemented (Handoff 4B).')


@worldcup_cli.command('status')
def status_cmd():
    """Print tournament state summary."""
    total_teams = WorldCupTeam.query.count()
    total_matches = WorldCupMatch.query.count()
    completed_matches = WorldCupMatch.query.filter_by(is_completed=True).count()
    enrolled_players = WorldCupEnrollment.query.filter_by(season_year=2026).count()

    click.echo(f'\n=== World Cup Fantasy Pool — Status ===')
    click.echo(f'Teams:             {total_teams}')
    click.echo(f'Matches:           {total_matches} ({completed_matches} completed)')
    click.echo(f'Enrolled players:  {enrolled_players}')

    if enrolled_players > 0:
        top_players = (
            WorldCupEnrollment.query
            .filter_by(season_year=2026)
            .order_by(WorldCupEnrollment.total_score.desc())
            .limit(5)
            .all()
        )
        click.echo(f'\nTop 5:')
        for i, e in enumerate(top_players, 1):
            click.echo(f'  {i}. {e.get_display_name()} — {e.total_score:.1f} pts')
    click.echo('')


def register_worldcup_cli(app):
    """Register World Cup CLI commands with the Flask app."""
    app.cli.add_command(worldcup_cli)
