"""add picks_open_notified flags to cfb_week and docket_week

Revision ID: d4e91a7c0b52
Revises: 1366fc218de3
Create Date: 2026-08-22

Adds the "Picks Are Open" announcement latch to both games' week tables.

Both tables carry live rows in prod, so the NOT NULL column is added with a
False server default to satisfy the constraint, then the default is dropped
so future inserts ride the model-side ``default=False``.

ASYMMETRIC BACKFILL — deliberate (see games/docket/models.py, games/cfb/
models.py, and the season-prep plan):

- docket_week: existing rows set True. The preview Week-1 row is hit by the
  already-enabled docket timers (docket-lines, Tue-Fri) before the Sep 1
  wipe; leaving it False would fire a premature announcement on a stale week.
  After the wipe, a fresh import (a new row, default False) announces.
- cfb_week: existing rows left False. The CFB preview week is REUSED on Sep 1
  (real spreads land on the same row; it is not wiped), so it must stay
  un-notified to announce when spreads arrive. No premature-fire risk: the
  trigger is spread-gated and cfb-spreads is held until launch week.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e91a7c0b52'
down_revision = '1366fc218de3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('cfb_week', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'picks_open_notified', sa.Boolean(), nullable=False,
            server_default=sa.false()))
    with op.batch_alter_table('docket_week', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'picks_open_notified', sa.Boolean(), nullable=False,
            server_default=sa.false()))

    # Docket-only backfill. A Core update() (not a raw `true` literal) so the
    # boolean compiles correctly on both SQLite (CI) and Postgres (prod).
    docket_week = sa.table(
        'docket_week', sa.column('picks_open_notified', sa.Boolean()))
    op.execute(docket_week.update().values(picks_open_notified=True))

    # Drop the server defaults; new rows ride the model-side default=False.
    with op.batch_alter_table('cfb_week', schema=None) as batch_op:
        batch_op.alter_column('picks_open_notified', server_default=None)
    with op.batch_alter_table('docket_week', schema=None) as batch_op:
        batch_op.alter_column('picks_open_notified', server_default=None)


def downgrade():
    with op.batch_alter_table('docket_week', schema=None) as batch_op:
        batch_op.drop_column('picks_open_notified')
    with op.batch_alter_table('cfb_week', schema=None) as batch_op:
        batch_op.drop_column('picks_open_notified')
