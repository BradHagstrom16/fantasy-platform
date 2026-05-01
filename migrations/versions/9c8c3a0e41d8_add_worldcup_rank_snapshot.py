"""add worldcup rank snapshot

Revision ID: 9c8c3a0e41d8
Revises: 6ca93808bcd2
Create Date: 2026-04-30 15:41:21.317687

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c8c3a0e41d8'
down_revision = '6ca93808bcd2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('worldcup_rank_snapshot',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('enrollment_id', sa.Integer(), nullable=False),
    sa.Column('captured_date', sa.Date(), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('total_score', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['enrollment_id'], ['worldcup_enrollment.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('enrollment_id', 'captured_date', name='unique_worldcup_snapshot_per_day')
    )
    with op.batch_alter_table('worldcup_rank_snapshot', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_worldcup_rank_snapshot_captured_date'), ['captured_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_worldcup_rank_snapshot_enrollment_id'), ['enrollment_id'], unique=False)


def downgrade():
    with op.batch_alter_table('worldcup_rank_snapshot', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_worldcup_rank_snapshot_enrollment_id'))
        batch_op.drop_index(batch_op.f('ix_worldcup_rank_snapshot_captured_date'))

    op.drop_table('worldcup_rank_snapshot')
