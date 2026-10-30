"""cfb_enrollment: the week whose elimination the member has seen (ADR-078)

Revision ID: a4d81c6e2f57
Revises: e79308879acb
Create Date: 2026-10-30

The Observer's Seat (games/cfb/DESIGN.md §6.14) plays once per member, the
first room view after their elimination is final. ``elimination_seen_week``
records the week it played for, so it never plays twice.

Every member already out when this ships counts as having seen theirs: the
backfill files each eliminated enrollment under its elimination week, read
from the outcome snapshots the way ``get_elimination_weeks`` reads them (the
earliest week with is_eliminated AND lost_life). An eliminated member with no
such snapshot keeps NULL; theirs is still being played, or never had one.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4d81c6e2f57'
down_revision = 'e79308879acb'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('cfb_enrollment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('elimination_seen_week', sa.Integer(), nullable=True))

    enrollment = sa.table(
        'cfb_enrollment', sa.column('user_id', sa.Integer),
        sa.column('season_year', sa.Integer), sa.column('is_eliminated', sa.Boolean),
        sa.column('elimination_seen_week', sa.Integer))
    outcome = sa.table(
        'cfb_week_outcome', sa.column('user_id', sa.Integer), sa.column('week_id', sa.Integer),
        sa.column('is_eliminated', sa.Boolean), sa.column('lost_life', sa.Boolean))
    week = sa.table(
        'cfb_week', sa.column('id', sa.Integer), sa.column('week_number', sa.Integer),
        sa.column('season_year', sa.Integer))
    out_week = (
        sa.select(sa.func.min(week.c.week_number))
        .select_from(outcome.join(week, outcome.c.week_id == week.c.id))
        .where(
            outcome.c.user_id == enrollment.c.user_id,
            week.c.season_year == enrollment.c.season_year,
            outcome.c.is_eliminated.is_(True),
            outcome.c.lost_life.is_(True),
        )
        .scalar_subquery()
    )
    op.execute(enrollment.update()
               .where(enrollment.c.is_eliminated.is_(True))
               .values(elimination_seen_week=out_week))


def downgrade():
    with op.batch_alter_table('cfb_enrollment', schema=None) as batch_op:
        batch_op.drop_column('elimination_seen_week')
