"""Create scan_jobs table.

Revision ID: 0002_scan_jobs
Revises: 0001_baseline
Create Date: 2026-11-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_scan_jobs'
down_revision: Union[str, None] = '0001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scan_jobs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('domain_id', sa.Integer(), nullable=True),
        sa.Column('requested_by_user_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=32), nullable=False, server_default='manual'),
        sa.Column('target_hostname', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='queued'),
        sa.Column('progress', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('scan_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['domain_id'], ['domains.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scan_jobs_status'), 'scan_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_scan_jobs_domain_id'), 'scan_jobs', ['domain_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_scan_jobs_domain_id'), table_name='scan_jobs')
    op.drop_index(op.f('ix_scan_jobs_status'), table_name='scan_jobs')
    op.drop_table('scan_jobs')
