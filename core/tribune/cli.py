"""``flask tribune backfill``: store the page copy on letters sent before
The Tribune existed. One-shot, idempotent."""
import click
from flask.cli import AppGroup

tribune_cli = AppGroup('tribune', help='The Tribune (the Club Letter archive).')


@tribune_cli.command('backfill')
def backfill():
    """Render and store the page copy for every sent letter that lacks one."""
    from core.tribune.services import backfill_page_html
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
