"""``flask records close GAME YEAR [--force]`` and ``flask records show``.

Hand-run at season end, never a timer: the Commish closes a season once
its game says it is final, reads the board back, and links any name the
season could not (the 2025 Survivor archive) before re-running with
``--force``. Nothing here sends mail or touches a game's own tables.
"""
import sys

import click
from flask.cli import AppGroup

from games.registry import GAMES, get_entry
from models.records import (
    SeasonAlreadyOnRecord,
    SeasonNotClosed,
    finishes_for,
    record_season,
    seasons_on_record,
)

records_cli = AppGroup('records', help="The club's permanent record (ADR-068).")


def _print_board(rows):
    for row in rows:
        detail = f'  {row.detail}' if row.detail else ''
        linked = '' if row.user_id is not None else '  (no account)'
        click.echo(f'{row.place:>3}  {row.name}{detail}{linked}')


@records_cli.command('close')
@click.argument('game', type=click.Choice([entry.slug for entry in GAMES]))
@click.argument('year', type=int)
@click.option('--force', is_flag=True, help='Rewrite a season already on record.')
def close(game, year, force):
    """Put a finished season's board on record through the game's registry seam.

    Refuses while the game says the season still runs, and refuses a season
    already on record unless --force. A Survivor close of 2026 or later needs
    the season-scoped outcome reads (PR 3 of the §E sequence); a Docket close
    needs its scoped ledger (PR 4). Survivor 2025 reads the frozen archive
    plus games/cfb/data/season_2025_links.json.
    """
    entry = get_entry(game)
    if entry.season_finishes is None:
        click.echo(f'{entry.display_name} has no records seam yet.')
        sys.exit(1)
    try:
        drafts = entry.season_finishes(year)
    except (SeasonNotClosed, LookupError) as exc:
        click.echo(str(exc))
        sys.exit(1)
    try:
        rows = record_season(game, year, drafts, force=force)
    except SeasonAlreadyOnRecord as exc:
        click.echo(f'{exc}. Pass --force to rewrite it.')
        sys.exit(1)
    click.echo(f'{entry.display_name} {year}: {len(rows)} finishers on record.')
    _print_board(rows)
    unlinked = [row.name for row in rows if row.user_id is None]
    if unlinked:
        click.echo(f'{len(unlinked)} names without an account: {", ".join(unlinked)}')
        click.echo('Name any who have one in the link map and re-run with --force.')


@records_cli.command('show')
@click.argument('game', required=False,
                type=click.Choice([entry.slug for entry in GAMES]))
@click.argument('year', type=int, required=False)
def show(game, year):
    """Read the record: every season on it, or one season's board."""
    if (game is None) != (year is None):
        raise click.UsageError('Pass both GAME and YEAR, or neither.')
    if game is None:
        seasons = seasons_on_record()
        if not seasons:
            click.echo('Nothing on record yet.')
            return
        for slug, season_year in seasons:
            count = len(finishes_for(slug, season_year))
            click.echo(f'{slug} {season_year}: {count} finishers')
        return
    rows = finishes_for(game, year)
    if not rows:
        click.echo(f'{get_entry(game).display_name} {year}: nothing on record.')
        return
    click.echo(f'{get_entry(game).display_name} {year}: {len(rows)} finishers.')
    _print_board(rows)


def register_records_cli(app):
    app.cli.add_command(records_cli)
