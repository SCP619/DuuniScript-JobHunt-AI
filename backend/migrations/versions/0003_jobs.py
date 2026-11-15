"""jobs: job, job_source, job_source_listing; seed built-in sources

Revision ID: e86da255d9e2
Revises: 280277d2f799
Create Date: 2026-11-10 04:11:21.848883
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision: str = 'e86da255d9e2'
down_revision: str | None = '280277d2f799'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('job',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('canonical_url', sa.String(length=2000), nullable=True),
    sa.Column('company', sa.String(length=300), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('location', sa.String(length=300), nullable=True),
    sa.Column('employment_type', sa.String(length=20), nullable=True),
    sa.Column('work_mode', sa.String(length=10), nullable=True),
    sa.Column('salary_text', sa.String(length=300), nullable=True),
    sa.Column('language', sa.String(length=10), nullable=True),
    sa.Column('application_url', sa.String(length=2000), nullable=True),
    sa.Column('published_on', sa.Date(), nullable=True),
    sa.Column('deadline_on', sa.Date(), nullable=True),
    sa.Column('deadline_at', sa.DateTime(), nullable=True),
    sa.Column('first_seen_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('user_notes', sa.Text(), nullable=True),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint("employment_type IS NULL OR employment_type IN ('full_time', 'part_time', 'contract', 'temporary', 'internship', 'volunteer', 'per_diem', 'other')", name=op.f('ck_job_employment_type')),
    sa.CheckConstraint("status IN ('new', 'reviewed', 'saved', 'not_relevant', 'drafting', 'applied', 'closed', 'expired')", name=op.f('ck_job_status')),
    sa.CheckConstraint("work_mode IS NULL OR work_mode IN ('onsite', 'hybrid', 'remote')", name=op.f('ck_job_work_mode')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_job')),
    sa.UniqueConstraint('canonical_url', name=op.f('uq_job_canonical_url'))
    )
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_job_company'), ['company'], unique=False)
        batch_op.create_index(batch_op.f('ix_job_content_hash'), ['content_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_job_deadline_on'), ['deadline_on'], unique=False)
        batch_op.create_index(batch_op.f('ix_job_first_seen_at'), ['first_seen_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_job_published_on'), ['published_on'], unique=False)
        batch_op.create_index('ix_job_status_hidden', ['status', 'hidden'], unique=False)
        batch_op.create_index(batch_op.f('ix_job_title'), ['title'], unique=False)

    op.create_table('job_source',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('key', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('domain', sa.String(length=253), nullable=True),
    sa.Column('access_type', sa.String(length=40), nullable=False),
    sa.Column('access_method', sa.String(length=200), nullable=False),
    sa.Column('terms_url', sa.String(length=2000), nullable=True),
    sa.Column('policy_notes', sa.Text(), nullable=True),
    sa.Column('rate_limit', sa.JSON(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('last_success_at', sa.DateTime(), nullable=True),
    sa.Column('last_error_at', sa.DateTime(), nullable=True),
    sa.Column('last_error', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint("access_type IN ('official_api', 'official_feed', 'public_structured_data', 'public_page_uncertain', 'supported_authenticated', 'user_provided', 'restricted')", name=op.f('ck_job_source_access_type')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_job_source')),
    sa.UniqueConstraint('key', name=op.f('uq_job_source_key'))
    )
    op.create_table('job_source_listing',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('job_id', sa.String(length=36), nullable=False),
    sa.Column('source_id', sa.String(length=36), nullable=False),
    sa.Column('external_id', sa.String(length=300), nullable=True),
    sa.Column('source_url', sa.String(length=2000), nullable=True),
    sa.Column('source_published_on', sa.Date(), nullable=True),
    sa.Column('source_updated_at', sa.DateTime(), nullable=True),
    sa.Column('first_seen_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.Column('listing_status', sa.String(length=20), nullable=False),
    sa.Column('snapshot_path', sa.String(length=500), nullable=True),
    sa.Column('snapshot_hash', sa.String(length=64), nullable=True),
    sa.Column('captured_at', sa.DateTime(), nullable=True),
    sa.Column('parser_version', sa.String(length=20), nullable=True),
    sa.CheckConstraint("listing_status IN ('active', 'removed', 'unknown')", name=op.f('ck_job_source_listing_listing_status')),
    sa.ForeignKeyConstraint(['job_id'], ['job.id'], name=op.f('fk_job_source_listing_job_id_job'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_id'], ['job_source.id'], name=op.f('fk_job_source_listing_source_id_job_source'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_job_source_listing')),
    sa.UniqueConstraint('source_id', 'external_id', name='uq_job_source_listing_source_external')
    )
    with op.batch_alter_table('job_source_listing', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_job_source_listing_job_id'), ['job_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_job_source_listing_source_id'), ['source_id'], unique=False)

    _seed_builtin_sources()


# Built-in sources. Fixed IDs so every installation agrees. Automated source adapters
# are added in later migrations only after their access policy is documented (BSD 4).
BUILTIN_SOURCES = [
    {
        "id": "00000000-0000-4000-8000-000000000001",
        "key": "manual",
        "name": "Manual entry",
        "access_type": "user_provided",
        "access_method": "Job details typed or pasted by the user. Nothing is fetched.",
        "policy_notes": "Always available. Used when a page cannot be imported.",
    },
    {
        "id": "00000000-0000-4000-8000-000000000002",
        "key": "url_import",
        "name": "URL import",
        "access_type": "user_provided",
        "access_method": (
            "Single fetch of a URL the user supplies, reading only schema.org JobPosting "
            "structured data. No crawling, no login, no scheduled retrieval."
        ),
        "policy_notes": (
            "User-initiated, one page at a time. Refuses private network addresses. "
            "If a page has no structured data, the user enters the job manually."
        ),
    },
]


def _seed_builtin_sources() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    table = sa.table(
        'job_source',
        sa.column('id', sa.String), sa.column('key', sa.String), sa.column('name', sa.String),
        sa.column('access_type', sa.String), sa.column('access_method', sa.String),
        sa.column('policy_notes', sa.Text), sa.column('enabled', sa.Boolean),
        sa.column('created_at', sa.DateTime), sa.column('updated_at', sa.DateTime),
    )
    op.bulk_insert(table, [{**s, "enabled": True, "created_at": now, "updated_at": now} for s in BUILTIN_SOURCES])


def downgrade() -> None:
    with op.batch_alter_table('job_source_listing', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_job_source_listing_source_id'))
        batch_op.drop_index(batch_op.f('ix_job_source_listing_job_id'))

    op.drop_table('job_source_listing')
    op.drop_table('job_source')
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_job_title'))
        batch_op.drop_index('ix_job_status_hidden')
        batch_op.drop_index(batch_op.f('ix_job_published_on'))
        batch_op.drop_index(batch_op.f('ix_job_first_seen_at'))
        batch_op.drop_index(batch_op.f('ix_job_deadline_on'))
        batch_op.drop_index(batch_op.f('ix_job_content_hash'))
        batch_op.drop_index(batch_op.f('ix_job_company'))

    op.drop_table('job')
