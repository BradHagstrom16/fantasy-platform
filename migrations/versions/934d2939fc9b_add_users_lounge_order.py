"""users: the member's own lounge order

Revision ID: 934d2939fc9b
Revises: a4d81c6e2f57
Create Date: 2026-11-20

``lounge_order`` holds comma-joined game slugs, first leads, written from
/profile (POST /profile/lounge-order) and read by
``games.registry.in_member_order``. Nullable with no backfill: NULL keeps
registry order, which is every member's lounge today.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '934d2939fc9b'
down_revision = 'a4d81c6e2f57'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lounge_order', sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('lounge_order')
