"""``flask tribune backfill``: file the letters sent before the announce desk
kept a copy (core/tribune/pre_desk.py), then store the page copy on letters
sent before The Tribune existed. Idempotent; sends nothing."""
import click
from flask.cli import AppGroup

tribune_cli = AppGroup('tribune', help='The Tribune (the Club Letter archive).')


@tribune_cli.command('backfill')
def backfill():
    """File the pre-desk letters, then render and store the page copy for
    every sent letter that lacks one."""
    from core.tribune.pre_desk import file_pre_desk_letters
    from core.tribune.services import backfill_page_html
    filed = file_pre_desk_letters()
    click.echo(f'Filed {filed} letter{"" if filed == 1 else "s"} sent before the desk kept copies.')
    count, skipped = backfill_page_html()
    click.echo(f'Backfilled {count} issue{"" if count == 1 else "s"}.')
    if count:
        click.echo('Live boards in those letters show the field as of now, '
                   'not as of the send date.')
    if skipped:
        ids = ', '.join(f'#{row_id}' for row_id in skipped)
        click.echo(f'Skipped {ids}: the body no longer parses (logged). '
                   'Those issues read as their mailed plain copy.')


def register_tribune_cli(app):
    app.cli.add_command(tribune_cli)
