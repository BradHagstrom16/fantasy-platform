"""add users.auth_id identity token

Revision ID: f99903200f45
Revises: d44ccf51e702
Create Date: 2026-06-01 21:01:39.057974

Adds the random per-user `auth_id` used as the Flask-Login session/remember-cookie
identity (User.get_id). Three steps so it works on a table with existing rows:
add the column nullable, backfill a unique uuid per row, then enforce NOT NULL +
the unique index.

"""
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f99903200f45'
down_revision = 'd44ccf51e702'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add nullable so existing rows don't violate the constraint.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auth_id', sa.String(length=32), nullable=True))

    # 2. Backfill a unique random token per existing user (DB-agnostic Python loop).
    bind = op.get_bind()
    users = sa.table('users',
                     sa.column('id', sa.Integer),
                     sa.column('auth_id', sa.String))
    rows = bind.execute(sa.select(users.c.id)).fetchall()
    for (user_id,) in rows:
        bind.execute(
            users.update()
            .where(users.c.id == user_id)
            .values(auth_id=uuid.uuid4().hex)
        )

    # 3. Enforce NOT NULL + unique index now that every row has a value.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('auth_id', existing_type=sa.String(length=32),
                              nullable=False)
        batch_op.create_index(batch_op.f('ix_users_auth_id'), ['auth_id'], unique=True)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_auth_id'))
        batch_op.drop_column('auth_id')
