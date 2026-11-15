"""documents

Revision ID: 280277d2f799
Revises: 5b09faeb4cc8
Create Date: 2026-11-10 04:02:07.279021
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '280277d2f799'
down_revision: str | None = '5b09faeb4cc8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('document',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('profile_id', sa.String(length=36), nullable=False),
    sa.Column('category', sa.String(length=30), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('storage_path', sa.String(length=500), nullable=False),
    sa.Column('file_extension', sa.String(length=10), nullable=False),
    sa.Column('mime_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('extraction_status', sa.String(length=20), nullable=False),
    sa.Column('extraction_error', sa.String(length=50), nullable=True),
    sa.Column('extracted_text_path', sa.String(length=500), nullable=True),
    sa.Column('extracted_char_count', sa.Integer(), nullable=True),
    sa.Column('extractor_version', sa.String(length=20), nullable=True),
    sa.Column('extracted_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('archived_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint("category IN ('cv', 'cover_letter', 'certificate', 'transcript', 'portfolio', 'publication', 'reference', 'other')", name=op.f('ck_document_category')),
    sa.CheckConstraint("extraction_status IN ('pending', 'succeeded', 'no_text', 'failed')", name=op.f('ck_document_extraction_status')),
    sa.ForeignKeyConstraint(['profile_id'], ['user_profile.id'], name=op.f('fk_document_profile_id_user_profile'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document')),
    sa.UniqueConstraint('profile_id', 'sha256', name='uq_document_profile_sha256')
    )
    with op.batch_alter_table('document', schema=None) as batch_op:
        batch_op.create_index('ix_document_category_archived', ['category', 'archived_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_profile_id'), ['profile_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_document_sha256'), ['sha256'], unique=False)

    # Before this revision document_id was an unchecked reference and no document table
    # existed, so no stored value can point to a real document. Clear such values so the
    # new foreign key can be created.
    op.execute(
        "UPDATE profile_evidence SET document_id = NULL "
        "WHERE document_id IS NOT NULL AND document_id NOT IN (SELECT id FROM document)"
    )

    with op.batch_alter_table('profile_evidence', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_profile_evidence_document_id'), ['document_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_profile_evidence_document_id_document'), 'document', ['document_id'], ['id'], ondelete='RESTRICT')


def downgrade() -> None:
    with op.batch_alter_table('profile_evidence', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_profile_evidence_document_id_document'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_profile_evidence_document_id'))

    with op.batch_alter_table('document', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_sha256'))
        batch_op.drop_index(batch_op.f('ix_document_profile_id'))
        batch_op.drop_index('ix_document_category_archived')

    op.drop_table('document')
