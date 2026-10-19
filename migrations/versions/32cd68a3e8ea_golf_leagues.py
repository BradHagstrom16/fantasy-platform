"""golf leagues: golf_league + league_id on enrollment, pick and usage (ADR-075)

Revision ID: 32cd68a3e8ea
Revises: 8a05e7e5c96f
Create Date: 2026-10-19

The Pay Sheet becomes two leagues inside one game. ``golf_league`` holds one
row per league, seeded here with the two leagues of
``games/golf/constants.py::LEAGUE_SEED`` (written out as literals, so this
file never changes when the constant does): Handicap is the house league
(ordinal 1), Pollyanna the second. Fee 25 and penalty 15 are the
``ENTRY_FEE`` default and ``PENALTY_PER_INCIDENT`` on the day this shipped.

Every enrollment, pick and golfer usage row belongs to one league. The
column is added nullable, every existing row is backfilled to Handicap (all
golf history so far is Handicap's; production's golf tables were empty when
this shipped), then it is made NOT NULL. Each table's unique key gains the
league, under the same constraint name, so one member can hold a line, a
pick and a spent golfer in each league.

The three old uniques were created named (9744be4c108a), so both dialects
drop them by name. The foreign keys are named as Postgres would name them
(``<table>_league_id_fkey``) because SQLite's batch mode cannot create an
unnamed one; ``flask db check`` compares foreign keys by their columns and
referent, not their name, so the unnamed model FKs still match.

The downgrade refuses while any row belongs to a league other than Handicap:
dropping the column would otherwise quietly file that row as Handicap history.
"""
from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '32cd68a3e8ea'
down_revision = '8a05e7e5c96f'
branch_labels = None
depends_on = None

# table -> (unique constraint name, its columns before, its columns after)
SCOPED = {
    'golf_enrollment': (
        'unique_golf_enrollment',
        ['user_id', 'season_year'],
        ['user_id', 'league_id', 'season_year'],
    ),
    'golf_pick': (
        'unique_golf_user_tournament_pick',
        ['user_id', 'tournament_id'],
        ['user_id', 'league_id', 'tournament_id'],
    ),
    'golf_season_player_usage': (
        'unique_golf_player_usage',
        ['user_id', 'player_id', 'season_year'],
        ['user_id', 'league_id', 'player_id', 'season_year'],
    ),
}


def _handicap_id():
    league = sa.table('golf_league', sa.column('id'), sa.column('slug'))
    return sa.select(league.c.id).where(league.c.slug == 'handicap').scalar_subquery()


def upgrade():
    golf_league = op.create_table(
        'golf_league',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('entry_fee', sa.Integer(), nullable=False),
        sa.Column('penalty_per_incident', sa.Integer(), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ordinal'),
        sa.UniqueConstraint('slug'),
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    op.bulk_insert(golf_league, [
        {'slug': 'handicap', 'name': 'Handicap Pay Sheet', 'ordinal': 1,
         'entry_fee': 25, 'penalty_per_incident': 15, 'created_at': now},
        {'slug': 'pollyanna', 'name': 'Pollyanna Pay Sheet', 'ordinal': 2,
         'entry_fee': 25, 'penalty_per_incident': 15, 'created_at': now},
    ])

    handicap = _handicap_id()
    for table, (unique, _before, after) in SCOPED.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('league_id', sa.Integer(), nullable=True))

        op.execute(sa.table(table, sa.column('league_id')).update().values(league_id=handicap))

        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('league_id', existing_type=sa.Integer(), nullable=False)
            batch_op.drop_constraint(unique, type_='unique')
            batch_op.create_unique_constraint(unique, after)
            batch_op.create_index(batch_op.f(f'ix_{table}_league_id'), ['league_id'], unique=False)
            batch_op.create_foreign_key(
                f'{table}_league_id_fkey', 'golf_league', ['league_id'], ['id'])


def downgrade():
    # The old keys hold one league only: refuse while any row is another
    # league's (delete those rows first), rather than relabel it Handicap.
    bind = op.get_bind()
    handicap = _handicap_id()
    for table in SCOPED:
        rows = sa.table(table, sa.column('league_id'))
        others = bind.execute(
            sa.select(sa.func.count()).select_from(rows).where(rows.c.league_id != handicap)
        ).scalar()
        if others:
            raise RuntimeError(
                f'{table} holds {others} row(s) outside the Handicap league; '
                'delete them before downgrading past 32cd68a3e8ea'
            )

    for table, (unique, before, _after) in reversed(SCOPED.items()):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f'{table}_league_id_fkey', type_='foreignkey')
            batch_op.drop_index(batch_op.f(f'ix_{table}_league_id'))
            batch_op.drop_constraint(unique, type_='unique')
            batch_op.create_unique_constraint(unique, before)
            batch_op.drop_column('league_id')

    op.drop_table('golf_league')
