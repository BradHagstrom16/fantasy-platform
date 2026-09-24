"""add announcements sent_page_html and week_number (The Tribune)

Revision ID: b7c4e2a91d05
Revises: aca46ca62591
Create Date: 2026-09-24 18:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c4e2a91d05'
down_revision = 'aca46ca62591'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('announcements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sent_page_html', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('week_number', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('announcements', schema=None) as batch_op:
        batch_op.drop_column('week_number')
        batch_op.drop_column('sent_page_html')
