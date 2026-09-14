"""`flask push *` — web push admin/debug commands.

`push test --user <name>` hand-fires the fixed test dispatch to every device a
member has armed, so the commish can confirm a real phone before the Club
Letter without waiting for a game to go final.
"""
import click
from flask.cli import AppGroup
from sqlalchemy import func, select

from extensions import db
from models import User
from utils.identifier import normalize_identifier
from utils.push import send_push

push_cli = AppGroup('push', help='Web push admin/debug commands.')


@push_cli.command('test')
@click.option('--user', 'identifier', required=True,
              help='Username or email of the member to send to.')
def test(identifier):
    """Send the fixed test dispatch to every device the member has subscribed."""
    folded = normalize_identifier(identifier)
    user = db.session.scalar(
        select(User).where(func.lower(User.username) == folded))
    if user is None:
        user = db.session.scalar(
            select(User).where(func.lower(User.email) == folded))
    if user is None:
        click.echo(f'No member matching {identifier!r}.')
        return
    delivered = send_push(
        [user.id],
        title='Message from the wire.',
        body='See you Saturday. Tap to come back.',
        url='/app',
        tag='test',
        ttl=600,
        urgency='high',
    )
    click.echo(f'Delivered {delivered} push(es) to {user.username}.')


def register_push_cli(app):
    app.cli.add_command(push_cli)
