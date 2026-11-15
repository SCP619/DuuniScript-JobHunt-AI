"""baseline profile facts evidence audit

Revision ID: 5b09faeb4cc8
Revises: 
Create Date: 2026-11-10 03:13:34.261541
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '5b09faeb4cc8'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed baseline. Timestamps are stored as naive UTC (see UTCDateTime in models).
    op.create_table('audit_event',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('actor', sa.String(length=50), nullable=False),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.String(length=36), nullable=True),
    sa.Column('result', sa.String(length=20), nullable=False),
    sa.Column('details', sa.JSON(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_event'))
    )
    with op.batch_alter_table('audit_event', schema=None) as batch_op:
        batch_op.create_index('ix_audit_event_entity_time', ['entity_type', 'entity_id', 'occurred_at'], unique=False)

    op.create_table('user_profile',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_name', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('location', sa.String(length=200), nullable=True),
    sa.Column('professional_summary', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_profile'))
    )
    op.create_table('profile_fact',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('profile_id', sa.String(length=36), nullable=False),
    sa.Column('category', sa.String(length=40), nullable=False),
    sa.Column('subject', sa.String(length=300), nullable=False),
    sa.Column('value_text', sa.Text(), nullable=False),
    sa.Column('verification_status', sa.String(length=20), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=True),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('verified_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint("category IN ('contact', 'summary', 'education', 'work_experience', 'skill', 'project', 'certification', 'language', 'publication', 'reference', 'achievement', 'preference', 'other')", name=op.f('ck_profile_fact_category')),
    sa.CheckConstraint("verification_status IN ('unverified', 'verified', 'rejected', 'expired')", name=op.f('ck_profile_fact_verification_status')),
    sa.CheckConstraint('valid_from IS NULL OR valid_until IS NULL OR valid_from <= valid_until', name=op.f('ck_profile_fact_valid_range')),
    sa.ForeignKeyConstraint(['profile_id'], ['user_profile.id'], name=op.f('fk_profile_fact_profile_id_user_profile'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_profile_fact'))
    )
    with op.batch_alter_table('profile_fact', schema=None) as batch_op:
        batch_op.create_index('ix_profile_fact_category_status', ['category', 'verification_status'], unique=False)
        batch_op.create_index(batch_op.f('ix_profile_fact_profile_id'), ['profile_id'], unique=False)

    op.create_table('profile_evidence',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('fact_id', sa.String(length=36), nullable=False),
    sa.Column('document_id', sa.String(length=36), nullable=True),
    sa.Column('source_type', sa.String(length=30), nullable=False),
    sa.Column('source_reference', sa.String(length=2000), nullable=True),
    sa.Column('excerpt', sa.Text(), nullable=True),
    sa.Column('verification_status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint("source_type IN ('document', 'user_input', 'url', 'integration')", name=op.f('ck_profile_evidence_source_type')),
    sa.CheckConstraint("verification_status IN ('unverified', 'verified', 'rejected', 'expired')", name=op.f('ck_profile_evidence_verification_status')),
    sa.ForeignKeyConstraint(['fact_id'], ['profile_fact.id'], name=op.f('fk_profile_evidence_fact_id_profile_fact'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_profile_evidence'))
    )
    with op.batch_alter_table('profile_evidence', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_profile_evidence_fact_id'), ['fact_id'], unique=False)



def downgrade() -> None:
    # Reviewed baseline. Timestamps are stored as naive UTC (see UTCDateTime in models).
    with op.batch_alter_table('profile_evidence', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_profile_evidence_fact_id'))

    op.drop_table('profile_evidence')
    with op.batch_alter_table('profile_fact', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_profile_fact_profile_id'))
        batch_op.drop_index('ix_profile_fact_category_status')

    op.drop_table('profile_fact')
    op.drop_table('user_profile')
    with op.batch_alter_table('audit_event', schema=None) as batch_op:
        batch_op.drop_index('ix_audit_event_entity_time')

    op.drop_table('audit_event')
