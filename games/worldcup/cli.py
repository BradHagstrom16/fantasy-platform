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
from datetime import datetime, timedelta

import click
from flask.cli import AppGroup

from extensions import db
from games.worldcup.constants import SEASON_YEAR, WORLDCUP_TZ
from games.worldcup.services.state import now_utc
from games.worldcup.models import (
    WorldCupTeam,
    WorldCupMatch,
    WorldCupEnrollment,
    WorldCupRankSnapshot,
)

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


@worldcup_cli.command('simulate-group-stage')
@click.option('--dry-run', is_flag=True, default=False,
              help='Print the planned result for every match without writing.')
@click.option('--yes', '-y', is_flag=True, default=False,
              help='Skip the confirmation prompt (for scripted runs).')
def simulate_group_stage_cmd(dry_run: bool, yes: bool):
    """Fill in all 72 group-stage results with deterministic, tie-free standings.

    Testing aid for the production launch script: plays out the entire group
    stage in one run so team advancement can be exercised at /admin/advancement.
    Only touches stage='group' matches; knockout shells are never modified, and
    already-completed matches are skipped (re-runs are safe). Advancement
    confirmation stays a manual step — this command stops after group results.

    Destructive: writes results to incomplete group matches and recalculates
    every enrollment score. Prompts for confirmation unless --dry-run or --yes.

    Within each group the four teams are ranked 1-4 by (multiplier ASC,
    fifa_code ASC) — lower multiplier = favorite, so favorites finish higher
    (realistic when eyeballing results). Results are fixed by rank pair so every
    group ends with a clean 9/4/3/1 spread (rank 2 vs rank 4 is a draw to
    exercise draw scoring).
    """
    from games.worldcup.services.scoring import process_match_result

    # Intra-group rank: 1 = favorite (lowest multiplier). Sort once, then bucket.
    teams = (
        WorldCupTeam.query
        .filter(WorldCupTeam.group_letter.isnot(None))
        .all()
    )
    rank_by_team_id: dict[int, int] = {}
    for letter in sorted({t.group_letter for t in teams}):
        group = sorted(
            (t for t in teams if t.group_letter == letter),
            key=lambda t: (t.multiplier, t.fifa_code),
        )
        for rank, team in enumerate(group, start=1):
            rank_by_team_id[team.id] = rank

    matches = (
        WorldCupMatch.query
        .filter_by(stage='group')
        .order_by(WorldCupMatch.match_number)
        .all()
    )

    # Gate the destructive write path behind a confirmation (skipped for
    # --dry-run, which writes nothing, and --yes, for scripted runs).
    if not dry_run and not yes:
        pending = sum(1 for m in matches if not m.is_completed)
        if pending:
            click.confirm(
                f'This will write results to {pending} incomplete group '
                f'match(es) and recalculate every enrollment score. Continue?',
                abort=True,
            )

    processed = 0
    skipped = 0
    drawn = 0
    for match in matches:
        if match.is_completed:
            skipped += 1
            continue

        home_rank = rank_by_team_id.get(match.home_team_id)
        away_rank = rank_by_team_id.get(match.away_team_id)
        if home_rank is None or away_rank is None:
            click.echo(f'  ! Match #{match.match_number}: unranked team(s); skipped.')
            skipped += 1
            continue

        # rank 2 vs rank 4 is the designated draw; otherwise the higher rank
        # (lower number) wins 2-0.
        is_draw = {home_rank, away_rank} == {2, 4}
        if is_draw:
            home_score, away_score, winner_code = 1, 1, None
            drawn += 1
        elif home_rank < away_rank:
            home_score, away_score = 2, 0
            winner_code = match.home_team.fifa_code
        else:
            home_score, away_score = 0, 2
            winner_code = match.away_team.fifa_code

        home_name = match.home_team.display_name if match.home_team else '?'
        away_name = match.away_team.display_name if match.away_team else '?'
        line = (f'#{match.match_number:>2} [{match.group_letter}] '
                f'{home_name} {home_score}-{away_score} {away_name}'
                + (' (draw)' if is_draw else ''))

        if dry_run:
            click.echo(f'  would set {line}')
            processed += 1
            continue

        result = process_match_result(
            match_id=match.id,
            home_score=home_score,
            away_score=away_score,
            winner_fifa_code=winner_code,
            is_draw=is_draw,
        )
        if 'error' in result:
            click.echo(f"  ! Match #{match.match_number}: {result['error']}")
            skipped += 1
            continue
        click.echo(f'  set {line}')
        processed += 1

    verb = 'would process' if dry_run else 'processed'
    click.echo(
        f'\nGroup stage: {verb} {processed} matches '
        f'({drawn} draws), {skipped} skipped.'
    )

    if dry_run:
        return

    # Standings preview — who advances when the admin confirms each group.
    click.echo('\nGroup standings (1st / 2nd advance; 3rd = best-third candidate):')
    for letter in 'ABCDEFGHIJKL':
        standings = (
            WorldCupTeam.query
            .filter_by(group_letter=letter)
            .order_by(
                (WorldCupTeam.group_wins * 3 + WorldCupTeam.group_draws).desc(),
                WorldCupTeam.group_wins.desc(),
                WorldCupTeam.fifa_code.asc(),
            )
            .all()
        )
        if not standings:
            continue
        line = '  '.join(
            f'{i}.{t.fifa_code}({t.group_wins * 3 + t.group_draws})'
            for i, t in enumerate(standings, start=1)
        )
        click.echo(f'  {letter}: {line}')

    click.echo(
        '\nNext: confirm advancement per group at /worldcup/admin/advancement.'
    )


@worldcup_cli.command('snapshot-ranks')
@click.option('--backfill', type=int, default=0,
              help='Also backfill N past days using current rank/score (writes N+1 rows per enrollment: today + N prior)')
def snapshot_ranks(backfill: int):
    """Capture today's rank + score snapshot for every enrollment.

    Idempotent: re-running for the same day is a no-op.
    With --backfill N, also writes snapshots for the past N days using
    the current rank/score (best-effort backfill for first deploy).
    Net rows per enrollment: N+1 (today + N prior days).
    """
    if backfill < 0:
        raise click.BadParameter('--backfill must be >= 0')

    today_local = now_utc().astimezone(WORLDCUP_TZ).date()

    for days_ago in range(backfill, -1, -1):
        target_date = today_local - timedelta(days=days_ago)

        enrollments = (
            WorldCupEnrollment.query
            .filter_by(season_year=SEASON_YEAR)
            .order_by(
                WorldCupEnrollment.total_score.desc(),
                WorldCupEnrollment.id.asc(),
            )
            .all()
        )

        rows_added = 0
        for rank, enr in enumerate(enrollments, start=1):
            existing = WorldCupRankSnapshot.query.filter_by(
                enrollment_id=enr.id, captured_date=target_date
            ).first()
            if existing:
                continue
            db.session.add(WorldCupRankSnapshot(
                enrollment_id=enr.id,
                captured_date=target_date,
                rank=rank,
                total_score=enr.total_score,
            ))
            rows_added += 1

        db.session.commit()
        click.echo(f'Snapshot for {target_date} — {rows_added} new rows')


def register_worldcup_cli(app):
    """Register World Cup CLI commands with the Flask app."""
    app.cli.add_command(worldcup_cli)
