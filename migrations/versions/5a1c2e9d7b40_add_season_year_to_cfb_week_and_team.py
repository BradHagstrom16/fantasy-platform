"""add season_year to cfb_week and cfb_team (season scoping, ADR-069)

Revision ID: 5a1c2e9d7b40
Revises: e0cee073fa75
Create Date: 2026-09-29

A season is a column, never an archive-and-reseed (open-items §E). Every
existing row is the 2026 season, so the NOT NULL column is added with a
'2026' server default that fills them, then the default is dropped: a new
row must say its season.

The single-column uniques (``week_number``, ``name``) were created unnamed,
so each dialect finds its own to drop:

- postgresql reflects the real name (``cfb_week_week_number_key`` today);
  the ``[old] =`` unpack fails loudly if there is not exactly one.
- sqlite has no names for them, so batch mode takes a naming convention that
  gives the unnamed constraint a name it can drop (Alembic's documented
  recipe for unnamed constraints in batch mode).

Both then create the named season pair the models declare.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5a1c2e9d7b40'
down_revision = 'e0cee073fa75'
branch_labels = None
depends_on = None

# (table, the column that was unique alone, the new pair's name)
TABLES = (
    ('cfb_week', 'week_number', 'uq_cfb_week_season_number'),
    ('cfb_team', 'name', 'uq_cfb_team_season_name'),
)

# Postgres's default names for the old unnamed uniques, restored on downgrade.
POSTGRES_OLD_NAMES = {
    'cfb_week': 'cfb_week_week_number_key',
    'cfb_team': 'cfb_team_name_key',
}

SQLITE_NAMING = {'uq': 'uq_%(table_name)s_%(column_0_name)s'}


def upgrade():
    for table, _col, _pair in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column(
                'season_year', sa.Integer(), nullable=False,
                server_default='2026'))

    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        for table, col, pair in TABLES:
            with op.batch_alter_table(
                    table, schema=None,
                    naming_convention=SQLITE_NAMING) as batch_op:
                batch_op.alter_column('season_year', server_default=None)
                batch_op.drop_constraint(f'uq_{table}_{col}', type_='unique')
                batch_op.create_unique_constraint(pair, ['season_year', col])
    else:
        inspector = sa.inspect(bind)
        for table, col, pair in TABLES:
            [old] = [c['name'] for c in inspector.get_unique_constraints(table)
                     if c['column_names'] == [col]]
            op.alter_column(table, 'season_year', server_default=None)
            op.drop_constraint(old, table, type_='unique')
            op.create_unique_constraint(pair, table, ['season_year', col])


def downgrade():
    # Refuses (IntegrityError) once a second season's rows exist: the old
    # single-column unique cannot hold them. Delete the other season first.
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        for table, col, pair in TABLES:
            with op.batch_alter_table(
                    table, schema=None,
                    naming_convention=SQLITE_NAMING) as batch_op:
                batch_op.drop_constraint(pair, type_='unique')
                batch_op.create_unique_constraint(f'uq_{table}_{col}', [col])
    else:
        for table, col, pair in TABLES:
            op.drop_constraint(pair, table, type_='unique')
            op.create_unique_constraint(POSTGRES_OLD_NAMES[table], table, [col])

    for table, _col, _pair in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('season_year')
