"""season_finishes: a division per board (golf's two leagues, ADR-075)

Revision ID: e79308879acb
Revises: 32cd68a3e8ea
Create Date: 2026-10-19

A golf season now closes as one board per league, so the record learns the
board within a season: ``division`` (the league slug, '' for a game with one
board) and ``division_name`` (the league's name, frozen beside the slug so
the record never asks the game what it was called). Both columns are added
nullable, backfilled, then made NOT NULL with a '' server default.

The backfill files every golf row as the Handicap Pay Sheet (all golf
history so far is Handicap's; production has never closed a golf season, so
it is expected to touch nothing there) and every other game's row as ''.
The names are written out as literals, so this file never changes when
``games/golf/constants.py::LEAGUE_SEED`` does.

The two uniques gain the division, under the same names, so one member may
finish on both leagues' boards of a season. They were created named in
e0cee073fa75, so both dialects drop them by name.

The downgrade refuses while any row belongs to a division other than '' or
'handicap': the old keys hold one board per season, and dropping the column
would quietly merge a Pollyanna board into the Handicap one.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e79308879acb'
down_revision = '32cd68a3e8ea'
branch_labels = None
depends_on = None

# unique constraint name -> its last column (after game, season_year[, division])
UNIQUES = {
    'uq_season_finish_game_year_name': 'name',
    'uq_season_finish_game_year_user': 'user_id',
}


def upgrade():
    with op.batch_alter_table('season_finishes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('division', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('division_name', sa.String(length=60), nullable=True))

    finishes = sa.table('season_finishes', sa.column('game'), sa.column('division'),
                        sa.column('division_name'))
    op.execute(finishes.update().where(finishes.c.game == 'golf')
               .values(division='handicap', division_name='Handicap Pay Sheet'))
    op.execute(finishes.update().where(finishes.c.game != 'golf')
               .values(division='', division_name=''))

    with op.batch_alter_table('season_finishes', schema=None) as batch_op:
        batch_op.alter_column('division', existing_type=sa.String(length=20),
                              nullable=False, server_default='')
        batch_op.alter_column('division_name', existing_type=sa.String(length=60),
                              nullable=False, server_default='')
        for unique, last in UNIQUES.items():
            batch_op.drop_constraint(unique, type_='unique')
            batch_op.create_unique_constraint(unique, ['game', 'season_year', 'division', last])


def downgrade():
    # The old keys hold one board per season: refuse while a second board is
    # on record (delete those rows first), rather than merge it into Handicap's.
    finishes = sa.table('season_finishes', sa.column('division'))
    others = op.get_bind().execute(
        sa.select(sa.func.count()).select_from(finishes)
        .where(finishes.c.division.not_in(['', 'handicap']))
    ).scalar()
    if others:
        raise RuntimeError(
            f'season_finishes holds {others} row(s) outside the Handicap league; '
            'delete them before downgrading past e79308879acb'
        )

    with op.batch_alter_table('season_finishes', schema=None) as batch_op:
        for unique, last in UNIQUES.items():
            batch_op.drop_constraint(unique, type_='unique')
            batch_op.create_unique_constraint(unique, ['game', 'season_year', last])
        batch_op.drop_column('division_name')
        batch_op.drop_column('division')
