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
    InvalidBoard,
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


def _print_boards(rows, suffix=''):
    """A season's rows, one board per division under its name; a game with
    one board (a blank division) prints it bare."""
    boards = {}
    for row in rows:
        boards.setdefault(row.division, []).append(row)
    for division, board in boards.items():
        if division:
            click.echo(f'{board[0].division_name}: {len(board)} finishers{suffix}')
        _print_board(board)


@records_cli.command('close')
@click.argument('game', type=click.Choice([entry.slug for entry in GAMES]))
@click.argument('year', type=int)
@click.option('--force', is_flag=True, help='Rewrite a season already on record.')
def close(game, year, force):
    """Put a finished season's board on record through the game's registry seam.

    Refuses while the game says the season still runs, a board the record
    will not hold (empty, not a competition rank, a name or member twice),
    and a season already on record unless --force. A game with more than
    one board a season (golf's leagues) closes every one of them at once,
    and --force rewrites them all. Survivor 2025 reads the frozen archive
    plus games/cfb/data/season_2025_links.json. Both games'
    live reads are season-scoped (ADR-069), so a past season closes from
    its own rows.
    """
    entry = get_entry(game)
    if entry.season_finishes is None:
        click.echo(f'{entry.display_name} has no records seam yet.', err=True)
        sys.exit(1)
    try:
        rows = record_season(game, year, entry.season_finishes(year), force=force)
    except (SeasonNotClosed, InvalidBoard) as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)
    except SeasonAlreadyOnRecord as exc:
        click.echo(f'{exc}. Pass --force to rewrite it.', err=True)
        sys.exit(1)
    click.echo(f'{entry.display_name} {year}: {len(rows)} finishers on record.')
    _print_boards(rows, suffix=' on record')
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
        for slug, season_year, division, _division_name in seasons:
            count = len(finishes_for(slug, season_year, division=division))
            board = f' {division}' if division else ''
            click.echo(f'{slug} {season_year}{board}: {count} finishers')
        return
    rows = finishes_for(game, year)
    if not rows:
        click.echo(f'{get_entry(game).display_name} {year}: nothing on record.')
        return
    click.echo(f'{get_entry(game).display_name} {year}: {len(rows)} finishers.')
    _print_boards(rows)


def register_records_cli(app):
    app.cli.add_command(records_cli)
