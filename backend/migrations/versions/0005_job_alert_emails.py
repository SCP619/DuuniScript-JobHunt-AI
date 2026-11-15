"""job alert emails: alert_email, job.possible_duplicate_of_id; seed alert sources

Revision ID: 5b7e2c94a0d1
Revises: 9c4f1d2a7b31
Create Date: 2026-11-10 15:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = '5b7e2c94a0d1'
down_revision: str | None = '9c4f1d2a7b31'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALERT_ACCESS = (
    "Reads job alert emails that the site itself sends to the user, from one mailbox label, "
    "read-only. The site is never visited by DuuniScript."
)
ALERT_POLICY = (
    "Only emails from the site's own domain with a passing DKIM check are read, and only "
    "links on that domain become jobs. Alert emails carry no description; open the original "
    "posting for the full advertisement."
)

# Frozen copy: migrations must not import application code that may change later.
SITES = [
    ("alert_linkedin", "LinkedIn job alerts", "linkedin.com"),
    ("alert_glassdoor", "Glassdoor job alerts", "glassdoor.com"),
    ("alert_duunitori", "Duunitori job alerts", "duunitori.fi"),
    ("alert_jobly", "Jobly job alerts", "jobly.fi"),
    ("alert_indeed", "Indeed job alerts", "indeed.com"),
    ("alert_oikotie", "Oikotie job alerts", "oikotie.fi"),
    ("alert_monster", "Monster job alerts", "monster.fi"),
    ("alert_kuntarekry", "Kuntarekry job alerts", "kuntarekry.fi"),
    ("alert_tyomarkkinatori", "Job Market Finland alerts", "tyomarkkinatori.fi"),
]
SOURCES = [
    {
        "id": "00000000-0000-4000-8000-000000000003",
        "key": "email_alerts",
        "name": "Job alert mailbox",
        "domain": None,
        "access_type": "user_provided",
        "access_method": "Read-only IMAP access to one mailbox label chosen by the user. Emails are never changed, moved or deleted.",
        "policy_notes": "The password is kept in Windows Credential Manager, never in files. Status of the last mailbox check.",
    },
] + [
    {
        "id": f"00000000-0000-4000-8000-{n:012d}",
        "key": key,
        "name": name,
        "domain": domain,
        "access_type": "user_provided",
        "access_method": ALERT_ACCESS,
        "policy_notes": ALERT_POLICY,
    }
    for n, (key, name, domain) in enumerate(SITES, start=4)
]


def upgrade() -> None:
    op.create_table('alert_email',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('message_key', sa.String(length=300), nullable=False),
    sa.Column('source_key', sa.String(length=50), nullable=True),
    sa.Column('result', sa.String(length=20), nullable=False),
    sa.Column('received_at', sa.DateTime(), nullable=True),
    sa.Column('processed_at', sa.DateTime(), nullable=False),
    sa.Column('jobs_found', sa.Integer(), nullable=False),
    sa.Column('jobs_created', sa.Integer(), nullable=False),
    sa.Column('jobs_merged', sa.Integer(), nullable=False),
    sa.Column('jobs_known', sa.Integer(), nullable=False),
    sa.Column('unreadable_cards', sa.Integer(), nullable=False),
    sa.CheckConstraint("result IN ('parsed', 'no_jobs', 'unknown_sender', 'unverified_sender', 'too_large')", name=op.f('ck_alert_email_result')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_alert_email')),
    sa.UniqueConstraint('message_key', name=op.f('uq_alert_email_message_key'))
    )
    with op.batch_alter_table('alert_email', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alert_email_processed_at'), ['processed_at'], unique=False)

    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.add_column(sa.Column('possible_duplicate_of_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_job_possible_duplicate_of_id'), ['possible_duplicate_of_id'], unique=False)
        batch_op.create_foreign_key(
            batch_op.f('fk_job_possible_duplicate_of_id_job'), 'job', ['possible_duplicate_of_id'], ['id'],
            ondelete='SET NULL',
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    table = sa.table(
        'job_source',
        sa.column('id', sa.String), sa.column('key', sa.String), sa.column('name', sa.String),
        sa.column('domain', sa.String), sa.column('access_type', sa.String),
        sa.column('access_method', sa.String), sa.column('policy_notes', sa.Text),
        sa.column('enabled', sa.Boolean), sa.column('created_at', sa.DateTime), sa.column('updated_at', sa.DateTime),
    )
    op.bulk_insert(table, [{**s, "enabled": True, "created_at": now, "updated_at": now} for s in SOURCES])


def downgrade() -> None:
    keys = [s["key"] for s in SOURCES]
    source_ids = sa.select(sa.table('job_source', sa.column('id'), sa.column('key')).c.id).where(
        sa.column('key').in_(keys)
    )
    listing = sa.table('job_source_listing', sa.column('source_id'))
    op.execute(listing.delete().where(listing.c.source_id.in_(source_ids)))
    job_source = sa.table('job_source', sa.column('key'))
    op.execute(job_source.delete().where(job_source.c.key.in_(keys)))

    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_job_possible_duplicate_of_id_job'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_job_possible_duplicate_of_id'))
        batch_op.drop_column('possible_duplicate_of_id')

    with op.batch_alter_table('alert_email', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alert_email_processed_at'))
    op.drop_table('alert_email')
