"""add record_notified latch to docket_week

Revision ID: f3a7c2d9e815
Revises: e8be63eb6392
Create Date: 2026-09-21

The weekly record letter's latch (games/docket/services/record.py, Club
Desk step 1, docs/designs/unified-email.md): the daily scores run mails
every graded member their record once and sets this flag.

The column is NOT NULL with a False server default; the model keeps the
same server default so new rows land False whichever side inserts them.

BACKFILL — deliberate, the picks_open_notified precedent (d4e91a7c0b52):
weeks already graded when this ships are marked True. The pass mails any
graded, un-notified week, so leaving them False would send every member a
record for each week that closed before the letter existed on the first
scores run after deploy. A week still open at deploy time stays False and
gets its record when it grades.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3a7c2d9e815'
down_revision = 'e8be63eb6392'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('docket_week', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'record_notified', sa.Boolean(), nullable=False,
            server_default=sa.false()))

    # A Core update() (not a raw literal) so the boolean compiles on both
    # SQLite (CI) and Postgres (prod).
    docket_week = sa.table(
        'docket_week',
        sa.column('record_notified', sa.Boolean()),
        sa.column('default_error_tenths', sa.Integer()))
    op.execute(
        docket_week.update()
        .where(docket_week.c.default_error_tenths.is_not(None))
        .values(record_notified=True))


def downgrade():
    with op.batch_alter_table('docket_week', schema=None) as batch_op:
        batch_op.drop_column('record_notified')
