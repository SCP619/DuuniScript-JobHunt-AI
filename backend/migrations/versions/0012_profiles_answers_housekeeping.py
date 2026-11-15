"""CV profiles, saved answers, job attachments, job.archived_at, notification.toasted_at, application.cv_profile_id

Revision ID: d17c3b85e9a2
Revises: b6d40e9c2a17
Create Date: 2026-11-15 12:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'd17c3b85e9a2'
down_revision: str | None = 'b6d40e9c2a17'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('cv_profile',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('focus', sa.Text(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('cv_template', sa.String(length=40), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cv_profile')),
    sa.UniqueConstraint('name', name=op.f('uq_cv_profile_name'))
    )
    op.create_table('saved_answer',
    sa.Column('key', sa.String(length=50), nullable=False),
    sa.Column('answer', sa.Text(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_saved_answer'))
    )
    op.create_table('job_attachment',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('job_id', sa.String(length=36), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('storage_path', sa.String(length=500), nullable=False),
    sa.Column('media_type', sa.String(length=50), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['job.id'], name=op.f('fk_job_attachment_job_id_job'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_job_attachment'))
    )
    with op.batch_alter_table('job_attachment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_job_attachment_job_id'), ['job_id'], unique=False)

    with op.batch_alter_table('application', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cv_profile_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_application_cv_profile_id_cv_profile'), 'cv_profile', ['cv_profile_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.add_column(sa.Column('archived_at', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_job_archived_at'), ['archived_at'], unique=False)

    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.add_column(sa.Column('toasted_at', sa.DateTime(), nullable=True))



def downgrade() -> None:
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_column('toasted_at')

    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_job_archived_at'))
        batch_op.drop_column('archived_at')

    with op.batch_alter_table('application', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_application_cv_profile_id_cv_profile'), type_='foreignkey')
        batch_op.drop_column('cv_profile_id')

    with op.batch_alter_table('job_attachment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_job_attachment_job_id'))

    op.drop_table('job_attachment')
    op.drop_table('saved_answer')
    op.drop_table('cv_profile')
