"""add users.auth_id identity token

Revision ID: f99903200f45
Revises: d44ccf51e702
Create Date: 2026-06-01 21:01:39.057974

Adds the random per-user `auth_id` used as the Flask-Login session/remember-cookie
identity (User.get_id). Postgres-only (the sole deploy target): the column is added
with a *volatile* server-side default so every existing row — and any insert that
races this migration before the app restarts — gets a distinct value and no row is
left NULL. The default is then dropped (the app model has none) and NOT NULL + the
unique index are enforced.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f99903200f45'
down_revision = 'd44ccf51e702'
branch_labels = None
depends_on = None


# A volatile Postgres expression yielding 32 hex chars (uuid4().hex shape) —
# evaluated per row, so every row/insert gets a distinct value.
_AUTH_ID_DEFAULT = sa.text("replace(gen_random_uuid()::text, '-', '')")


def upgrade():
    # 1. Add nullable WITH a volatile server-side default. Postgres fills every
    #    existing row with a distinct value at ADD COLUMN time, and any insert
    #    that races this migration (e.g. from the not-yet-restarted app) also
    #    gets one — so no row can be left NULL.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auth_id', sa.String(length=32),
                                      nullable=True, server_default=_AUTH_ID_DEFAULT))

    # 2. Idempotent safety net: fill any row still NULL (distinct value per row).
    bind = op.get_bind()
    users = sa.table('users',
                     sa.column('id', sa.Integer),
                     sa.column('auth_id', sa.String))
    bind.execute(
        users.update().where(users.c.auth_id.is_(None)).values(auth_id=_AUTH_ID_DEFAULT)
    )

    # 3. Drop the temporary default (the app model has none — keep DB in sync),
    #    enforce NOT NULL, and add the unique index.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('auth_id', existing_type=sa.String(length=32),
                              server_default=None, nullable=False)
        batch_op.create_index(batch_op.f('ix_users_auth_id'), ['auth_id'], unique=True)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_auth_id'))
        batch_op.drop_column('auth_id')
