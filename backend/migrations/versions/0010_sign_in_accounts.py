"""sign in and accounts: app_credential, app_session, integration; seed JobTeaser alerts and university mailbox

Revision ID: f2c71d58ab93
Revises: e93b4a07d1c6
Create Date: 2026-11-14 19:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision: str = 'f2c71d58ab93'
down_revision: str | None = 'e93b4a07d1c6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy: migrations must not import application code that may change later.
ALERT_ACCESS = (
    "Reads job alert emails that the site itself sends to the user, from one mailbox label, "
    "read-only. The site is never visited by DuuniScript."
)
ALERT_POLICY = (
    "Only emails from the site's own domain with a passing DKIM check are read, and only "
    "links on that domain become jobs. Alert emails carry no description; open the original "
    "posting for the full advertisement."
)
SOURCES = [
    {
        "id": "00000000-0000-4000-8000-000000000023", "key": "alert_jobteaser", "name": "JobTeaser job alerts",
        "domain": "jobteaser.com", "access_type": "user_provided", "access_method": ALERT_ACCESS,
        "terms_url": None, "policy_notes": ALERT_POLICY, "rate_limit": None,
    },
    {
        "id": "00000000-0000-4000-8000-000000000024", "key": "email_alerts_microsoft",
        "name": "University mailbox (Microsoft 365)", "domain": None, "access_type": "user_provided",
        "access_method": (
            "Read-only Microsoft Graph access (Mail.Read) to the user's own Microsoft 365 mailbox, after the "
            "user signed in on Microsoft's page. Only emails from known job sites are downloaded."
        ),
        "terms_url": None,
        "policy_notes": "The sign-in is kept in Windows Credential Manager, never in files. Status of the last check.",
        "rate_limit": None,
    },
]


def upgrade() -> None:
    op.create_table('app_credential',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('password_hash', sa.String(length=300), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_app_credential'))
    )
    op.create_table('app_session',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_used_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_app_session')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_app_session_token_hash'))
    )
    with op.batch_alter_table('app_session', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_app_session_expires_at'), ['expires_at'], unique=False)

    op.create_table('integration',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('provider', sa.String(length=30), nullable=False),
    sa.Column('account', sa.String(length=320), nullable=True),
    sa.Column('scopes', sa.String(length=1000), nullable=False),
    sa.Column('connected_at', sa.DateTime(), nullable=False),
    sa.Column('last_sync_at', sa.DateTime(), nullable=True),
    sa.Column('last_error_at', sa.DateTime(), nullable=True),
    sa.Column('last_error', sa.String(length=300), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_integration')),
    sa.UniqueConstraint('provider', name='uq_integration_provider')
    )


    now = datetime.now(timezone.utc).replace(tzinfo=None)
    table = sa.table(
        'job_source',
        sa.column('id', sa.String), sa.column('key', sa.String), sa.column('name', sa.String),
        sa.column('domain', sa.String), sa.column('access_type', sa.String),
        sa.column('access_method', sa.String), sa.column('terms_url', sa.String),
        sa.column('policy_notes', sa.Text), sa.column('rate_limit', sa.JSON),
        sa.column('enabled', sa.Boolean), sa.column('created_at', sa.DateTime), sa.column('updated_at', sa.DateTime),
    )
    op.bulk_insert(table, [{**src, "enabled": True, "created_at": now, "updated_at": now} for src in SOURCES])


def downgrade() -> None:
    keys = [src["key"] for src in SOURCES]
    source_ids = sa.select(sa.table('job_source', sa.column('id'), sa.column('key')).c.id).where(sa.column('key').in_(keys))
    listing = sa.table('job_source_listing', sa.column('source_id'))
    op.execute(listing.delete().where(listing.c.source_id.in_(source_ids)))
    job_source = sa.table('job_source', sa.column('key'))
    op.execute(job_source.delete().where(job_source.c.key.in_(keys)))
    op.drop_table('integration')
    with op.batch_alter_table('app_session', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_app_session_expires_at'))

    op.drop_table('app_session')
    op.drop_table('app_credential')
