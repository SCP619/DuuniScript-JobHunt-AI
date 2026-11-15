"""jobs from screenshots and RAG: job.apply_manually; embedding; seed screenshot_import source

Revision ID: b6d40e9c2a17
Revises: f2c71d58ab93
Create Date: 2026-11-14 23:30:00
"""
from __future__ import annotations

from collections.abc import Sequence

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision: str = 'b6d40e9c2a17'
down_revision: str | None = 'f2c71d58ab93'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE = {
    "id": "00000000-0000-4000-8000-000000000025", "key": "screenshot_import", "name": "Screenshots",
    "domain": None, "access_type": "user_provided",
    "access_method": "Screenshots the user took of a posting, read on this computer with Windows OCR; the user checks every field before saving.",
    "terms_url": None,
    "policy_notes": "Nothing is fetched from the site. Jobs added this way are tagged 'Apply yourself'.",
    "rate_limit": None,
}


def upgrade() -> None:
    op.create_table('embedding',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('ref_id', sa.String(length=36), nullable=False),
    sa.Column('model', sa.String(length=100), nullable=False),
    sa.Column('text_hash', sa.String(length=64), nullable=False),
    sa.Column('dim', sa.Integer(), nullable=False),
    sa.Column('vector', sa.LargeBinary(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint("kind IN ('fact', 'job')", name=op.f('ck_embedding_kind')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_embedding')),
    sa.UniqueConstraint('kind', 'ref_id', name='uq_embedding_kind_ref')
    )
    with op.batch_alter_table('embedding', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_embedding_ref_id'), ['ref_id'], unique=False)

    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.add_column(sa.Column('apply_manually', sa.Boolean(), server_default='0', nullable=False))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    table = sa.table(
        'job_source',
        sa.column('id', sa.String), sa.column('key', sa.String), sa.column('name', sa.String),
        sa.column('domain', sa.String), sa.column('access_type', sa.String),
        sa.column('access_method', sa.String), sa.column('terms_url', sa.String),
        sa.column('policy_notes', sa.Text), sa.column('rate_limit', sa.JSON),
        sa.column('enabled', sa.Boolean), sa.column('created_at', sa.DateTime), sa.column('updated_at', sa.DateTime),
    )
    op.bulk_insert(table, [{**SOURCE, "enabled": True, "created_at": now, "updated_at": now}])


def downgrade() -> None:
    source_ids = sa.select(sa.table('job_source', sa.column('id'), sa.column('key')).c.id).where(sa.column('key') == SOURCE["key"])
    listing = sa.table('job_source_listing', sa.column('source_id'))
    op.execute(listing.delete().where(listing.c.source_id.in_(source_ids)))
    job_source = sa.table('job_source', sa.column('key'))
    op.execute(job_source.delete().where(job_source.c.key == SOURCE["key"]))
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.drop_column('apply_manually')

    with op.batch_alter_table('embedding', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_embedding_ref_id'))

    op.drop_table('embedding')
