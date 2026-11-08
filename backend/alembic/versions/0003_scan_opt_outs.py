"""Create scan_opt_outs table.

Revision ID: 0003_scan_opt_outs
Revises: 0002_scan_jobs
Create Date: 2026-11-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003_scan_opt_outs'
down_revision: Union[str, None] = '0002_scan_jobs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scan_opt_outs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scan_opt_outs_hostname'), 'scan_opt_outs', ['hostname'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_scan_opt_outs_hostname'), table_name='scan_opt_outs')
    op.drop_table('scan_opt_outs')
