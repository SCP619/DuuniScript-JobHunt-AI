"""job match, OCR, Valtiolle alerts: job_match; document.extraction_method; seed alert_valtiolle

Revision ID: c58e2d71f0a4
Revises: a41c6e0b9d27
Create Date: 2026-11-11 00:10:00
"""
from __future__ import annotations

from collections.abc import Sequence

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision: str = 'c58e2d71f0a4'
down_revision: str | None = 'a41c6e0b9d27'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy: migrations must not import application code that may change later.
VALTIOLLE = {
    "id": "00000000-0000-4000-8000-000000000022",
    "key": "alert_valtiolle",
    "name": "Valtiolle job alerts",
    "domain": "valtiolle.fi",
    "access_type": "user_provided",
    "access_method": (
        "Reads job alert emails that the site itself sends to the user, from one mailbox label, "
        "read-only. The site is never visited by DuuniScript."
    ),
    "terms_url": None,
    "policy_notes": (
        "Only emails from the site's own domain with a passing DKIM check are read, and only "
        "links on that domain become jobs. Alert emails carry no description; open the original "
        "posting for the full advertisement."
    ),
    "rate_limit": None,
}


def upgrade() -> None:
    op.create_table('job_match',
    sa.Column('job_id', sa.String(length=36), nullable=False),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('has_blockers', sa.Boolean(), nullable=False),
    sa.Column('scoring_version', sa.String(length=20), nullable=False),
    sa.Column('profile_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('job_hash', sa.String(length=80), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('computed_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('score IS NULL OR (score >= 0 AND score <= 100)', name=op.f('ck_job_match_score_range')),
    sa.ForeignKeyConstraint(['job_id'], ['job.id'], name=op.f('fk_job_match_job_id_job'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('job_id', name=op.f('pk_job_match'))
    )
    with op.batch_alter_table('job_match', schema=None) as batch_op:
        batch_op.create_index('ix_job_match_score', ['score'], unique=False)

    with op.batch_alter_table('document', schema=None) as batch_op:
        batch_op.add_column(sa.Column('extraction_method', sa.String(length=10), nullable=True))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    table = sa.table(
        'job_source',
        sa.column('id', sa.String), sa.column('key', sa.String), sa.column('name', sa.String),
        sa.column('domain', sa.String), sa.column('access_type', sa.String),
        sa.column('access_method', sa.String), sa.column('terms_url', sa.String),
        sa.column('policy_notes', sa.Text), sa.column('rate_limit', sa.JSON),
        sa.column('enabled', sa.Boolean), sa.column('created_at', sa.DateTime), sa.column('updated_at', sa.DateTime),
    )
    op.bulk_insert(table, [{**VALTIOLLE, "enabled": True, "created_at": now, "updated_at": now}])


def downgrade() -> None:
    source_ids = sa.select(sa.table('job_source', sa.column('id'), sa.column('key')).c.id).where(
        sa.column('key') == VALTIOLLE["key"]
    )
    listing = sa.table('job_source_listing', sa.column('source_id'))
    op.execute(listing.delete().where(listing.c.source_id.in_(source_ids)))
    job_source = sa.table('job_source', sa.column('key'))
    op.execute(job_source.delete().where(job_source.c.key == VALTIOLLE["key"]))
    with op.batch_alter_table('document', schema=None) as batch_op:
        batch_op.drop_column('extraction_method')

    with op.batch_alter_table('job_match', schema=None) as batch_op:
        batch_op.drop_index('ix_job_match_score')

    op.drop_table('job_match')
