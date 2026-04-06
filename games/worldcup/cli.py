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
from games.worldcup.constants import SEASON_YEAR
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
    """Recalculate all scores from match results (idempotent)."""
    from games.worldcup.services.scoring import recalculate_all_scores
    result = recalculate_all_scores()
    click.echo(f"Recalculation complete:")
    click.echo(f"  Teams updated:       {result['teams_updated']}")
    click.echo(f"  Picks updated:       {result['picks_updated']}")
    click.echo(f"  Enrollments updated: {result['enrollments_updated']}")

    top = (
        WorldCupEnrollment.query
        .filter_by(season_year=SEASON_YEAR)
        .order_by(WorldCupEnrollment.total_score.desc())
        .limit(5)
        .all()
    )
    if top:
        click.echo(f"\nTop 5:")
        for i, e in enumerate(top, 1):
            click.echo(f"  {i}. {e.get_display_name()} — {e.total_score:.1f} pts")


@worldcup_cli.command('status')
def status_cmd():
    """Print tournament state summary."""
    total_teams = WorldCupTeam.query.count()
    total_matches = WorldCupMatch.query.count()
    completed_matches = WorldCupMatch.query.filter_by(is_completed=True).count()
    enrolled_players = WorldCupEnrollment.query.filter_by(season_year=SEASON_YEAR).count()

    click.echo(f'\n=== World Cup Fantasy Pool — Status ===')
    click.echo(f'Teams:             {total_teams}')
    click.echo(f'Matches:           {total_matches} ({completed_matches} completed)')
    click.echo(f'Enrolled players:  {enrolled_players}')

    if enrolled_players > 0:
        top_players = (
            WorldCupEnrollment.query
            .filter_by(season_year=SEASON_YEAR)
            .order_by(WorldCupEnrollment.total_score.desc())
            .limit(5)
            .all()
        )
        click.echo(f'\nTop 5:')
        for i, e in enumerate(top_players, 1):
            click.echo(f'  {i}. {e.get_display_name()} — {e.total_score:.1f} pts')
    click.echo('')


@worldcup_cli.command('process-match')
@click.option('--match', 'match_number', required=True, type=int, help='Match number (1-104)')
@click.option('--home-score', required=True, type=int, help='Home team score')
@click.option('--away-score', required=True, type=int, help='Away team score')
@click.option('--winner', 'winner_code', default=None, help='FIFA code of winning team')
@click.option('--draw', 'is_draw', is_flag=True, default=False, help='Mark as draw (group stage)')
@click.option('--extra-time', is_flag=True, default=False, help='Match went to extra time')
@click.option('--penalties', is_flag=True, default=False, help='Match decided by penalties')
def process_match_cmd(match_number, home_score, away_score, winner_code,
                      is_draw, extra_time, penalties):
    """Enter a match result and recalculate scores."""
    from games.worldcup.services.scoring import process_match_result

    match = WorldCupMatch.query.filter_by(match_number=match_number).first()
    if not match:
        click.echo(f'Error: Match #{match_number} not found.')
        return

    result = process_match_result(
        match_id=match.id,
        home_score=home_score,
        away_score=away_score,
        winner_fifa_code=winner_code,
        is_draw=is_draw,
        extra_time=extra_time,
        penalties=penalties,
    )

    if 'error' in result:
        click.echo(f"Error: {result['error']}")
        return

    click.echo(f"Match #{result['match_number']}: {result['result']}")

    # Print updated scores for both teams
    from extensions import db
    db.session.refresh(match)
    if match.home_team:
        ht = match.home_team
        click.echo(f"  {ht.display_name}: {ht.base_points:.1f} base / {ht.multiplied_points:.1f} multiplied")
    if match.away_team:
        at = match.away_team
        click.echo(f"  {at.display_name}: {at.base_points:.1f} base / {at.multiplied_points:.1f} multiplied")


def register_worldcup_cli(app):
    """Register World Cup CLI commands with the Flask app."""
    app.cli.add_command(worldcup_cli)
