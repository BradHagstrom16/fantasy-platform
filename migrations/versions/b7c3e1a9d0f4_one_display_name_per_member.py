"""one display name per member (ADR-057)

Revision ID: b7c3e1a9d0f4
Revises: d4e91a7c0b52
Create Date: 2026-08-31

Retires the per-pool ``display_name`` on ``cfb_enrollment`` and
``docket_enrollment``. Nothing could edit those after the join, and the
enrollment helpers fell back to the raw username rather than the platform
name, so most members showed as their login name on the standings.

Data step first: every per-pool name that was ever set is promoted to the
member's one ``users.display_name`` — and it OVERWRITES a platform name the
member already had, by decision: where a member set more than one name, the
most recently created enrollment's wins, because that is what the active
standings show today (the ≤6 prod members affected were reviewed read-only
before deploy; any of them is a ten-second fix on /admin/users afterward).
Names are collapsed the way ``utils/display_name`` will validate them; a
name that would case-fold onto ANOTHER member's username or standing display
name is skipped (printed), so the holder can always re-save on /profile.
Then the two columns are dropped (batch mode, for SQLite).

The World Cup enrollment's column is left untouched: the WC room is frozen
and its ``get_display_name()`` still prefers that column where set.

Downgrade re-adds the two nullable columns EMPTY — the promoted names stay on
``users.display_name`` and are not copied back.
"""
import re
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c3e1a9d0f4'
down_revision = 'd4e91a7c0b52'
branch_labels = None
depends_on = None


def _fold(raw):
    return (raw or '').strip().casefold()


def _enrollment_table(name):
    return sa.table(
        name,
        sa.column('user_id', sa.Integer),
        sa.column('display_name', sa.String),
        sa.column('created_at', sa.DateTime),
    )


def _promote_per_pool_names(conn):
    """users.display_name <- the latest-joined pool's name, per member."""
    users = sa.table('users', sa.column('id', sa.Integer),
                     sa.column('username', sa.String),
                     sa.column('display_name', sa.String))
    selects = []
    for table in ('cfb_enrollment', 'docket_enrollment'):
        t = _enrollment_table(table)
        selects.append(
            sa.select(t.c.user_id, t.c.display_name, t.c.created_at)
            .where(t.c.display_name.is_not(None)))
    latest = {}   # user_id -> (created_at, name)
    for user_id, name, created_at in conn.execute(sa.union_all(*selects)):
        name = re.sub(r'\s+', ' ', name or '').strip()
        if not name:
            continue
        stamp = created_at or datetime.min
        if user_id not in latest or stamp > latest[user_id][0]:
            latest[user_id] = (stamp, name)
    if not latest:
        return

    # The names every promoted value must stay clear of (the validator's
    # rule): every other member's username, and the display name of every
    # other member who is NOT themselves being re-promoted here.
    usernames, display_names = {}, {}
    for uid, username, display_name in conn.execute(
            sa.select(users.c.id, users.c.username, users.c.display_name)):
        usernames[uid] = _fold(username)
        if display_name and uid not in latest:
            display_names[uid] = _fold(display_name)

    promoted = set()   # folded names already taken by an earlier promotion
    for user_id, (_, name) in sorted(latest.items()):
        folded = _fold(name)
        clash = (folded in promoted
                 or any(f == folded for uid, f in usernames.items() if uid != user_id)
                 or any(f == folded for uid, f in display_names.items()
                        if uid != user_id))
        if clash:
            print(f'  skipped user {user_id}: {name!r} collides with another '
                  f'member; set it by hand on /admin/users if wanted')
            continue
        conn.execute(users.update()
                     .where(users.c.id == user_id)
                     .values(display_name=name))
        promoted.add(folded)


def upgrade():
    _promote_per_pool_names(op.get_bind())
    with op.batch_alter_table('cfb_enrollment', schema=None) as batch_op:
        batch_op.drop_column('display_name')
    with op.batch_alter_table('docket_enrollment', schema=None) as batch_op:
        batch_op.drop_column('display_name')


def downgrade():
    with op.batch_alter_table('docket_enrollment', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('display_name', sa.String(length=80), nullable=True))
    with op.batch_alter_table('cfb_enrollment', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('display_name', sa.String(length=80), nullable=True))
