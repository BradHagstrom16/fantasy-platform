"""add season_year to docket_week (season scoping, ADR-069)

Revision ID: 8d3f6b1a2c95
Revises: 5a1c2e9d7b40
Create Date: 2026-09-29

The Docket half of 5a1c2e9d7b40 (Survivor's cfb_week / cfb_team), the same
recipe: every existing row is the 2026 season, so the NOT NULL column is
added with a '2026' server default that fills them, then the default is
dropped. The single-column unique on ``week_number`` was created unnamed
(39cbbef16b24):

- postgresql reflects its real name (``docket_week_week_number_key``); the
  ``[old] =`` unpack fails loudly if there is not exactly one.
- sqlite has no name for it, so batch mode takes a naming convention that
  gives the unnamed constraint a name it can drop.

Both then create the named season pair the model declares.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8d3f6b1a2c95'
down_revision = '5a1c2e9d7b40'
branch_labels = None
depends_on = None

TABLE = 'docket_week'
COLUMN = 'week_number'
PAIR = 'uq_docket_week_season_number'
# Postgres's default name for the old unnamed unique, restored on downgrade.
POSTGRES_OLD_NAME = 'docket_week_week_number_key'
SQLITE_NAMING = {'uq': 'uq_%(table_name)s_%(column_0_name)s'}


def upgrade():
    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'season_year', sa.Integer(), nullable=False, server_default='2026'))

    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table(
                TABLE, schema=None, naming_convention=SQLITE_NAMING) as batch_op:
            batch_op.alter_column('season_year', server_default=None)
            batch_op.drop_constraint(f'uq_{TABLE}_{COLUMN}', type_='unique')
            batch_op.create_unique_constraint(PAIR, ['season_year', COLUMN])
    else:
        [old] = [c['name'] for c in sa.inspect(bind).get_unique_constraints(TABLE)
                 if c['column_names'] == [COLUMN]]
        op.alter_column(TABLE, 'season_year', server_default=None)
        op.drop_constraint(old, TABLE, type_='unique')
        op.create_unique_constraint(PAIR, TABLE, ['season_year', COLUMN])


def downgrade():
    # Refuses (IntegrityError) once a second season's rows exist: the old
    # single-column unique cannot hold them. Delete the other season first.
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table(
                TABLE, schema=None, naming_convention=SQLITE_NAMING) as batch_op:
            batch_op.drop_constraint(PAIR, type_='unique')
            batch_op.create_unique_constraint(f'uq_{TABLE}_{COLUMN}', [COLUMN])
    else:
        op.drop_constraint(PAIR, TABLE, type_='unique')
        op.create_unique_constraint(POSTGRES_OLD_NAME, TABLE, [COLUMN])

    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.drop_column('season_year')
