"""Add contest report config table

Revision ID: 3a4e96d4e7d3
Revises: 9e96c431b1e1
Create Date: 2024-10-22 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3a4e96d4e7d3'
down_revision: str | Sequence[str] | None = '9e96c431b1e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'contest_report_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('contest_ids', sa.String(), nullable=False, server_default=''),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_contest_report_configs_id'), 'contest_report_configs', ['id'], unique=False)
    op.create_unique_constraint('uq_contest_report_configs_user_id', 'contest_report_configs', ['user_id'])


def downgrade() -> None:
    op.drop_constraint('uq_contest_report_configs_user_id', 'contest_report_configs', type_='unique')
    op.drop_index(op.f('ix_contest_report_configs_id'), table_name='contest_report_configs')
    op.drop_table('contest_report_configs')
