"""add docket_pick.is_auto_best

Records that a week's best-pick designation was assigned by the deadline
pass rather than chosen by the player. Distinct from is_autopick because
auto-designation evaluates the final 8-slot set and can therefore land the
double on a pick the player made themselves, where is_autopick stays False.

The column carries a server default so the NOT NULL can land on tables that
already hold picks, and KEEPS it, matching the sibling booleans on
docket_game (is_final, no_contest — 04298e2415e9). Alembic is configured
without compare_server_default, so a retained default produces no drift.

Downgrade caveat: is_auto_best is not recomputable once dropped. The
deadline pass short-circuits on any player who already has a headliner, and
is_best survives the drop, so a downgrade/upgrade cycle on a graded week
silently re-labels assigned headliners as player-chosen. Harmless while the
docket tables are empty (through Tue Sep 1); destructive after Week 1.

Revision ID: b60fec9363dd
Revises: 4088a03c16ce
Create Date: 2026-08-12 17:20:17.018392

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b60fec9363dd'
down_revision = '4088a03c16ce'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('docket_pick', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_auto_best', sa.Boolean(),
                                      nullable=False,
                                      server_default=sa.false()))
        # is_auto_best marks HOW a designation was made, so it cannot exist
        # without one. Added here, while the table is effectively empty.
        batch_op.create_check_constraint(
            'ck_docket_pick_auto_best_implies_best',
            'NOT is_auto_best OR is_best')


def downgrade():
    with op.batch_alter_table('docket_pick', schema=None) as batch_op:
        batch_op.drop_constraint('ck_docket_pick_auto_best_implies_best',
                                 type_='check')
        batch_op.drop_column('is_auto_best')
