"""job feeds: job.available_from_finland; seed feed sources and two more alert senders

Revision ID: 7d3a9f15c2e8
Revises: 5b7e2c94a0d1
Create Date: 2026-11-10 19:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = '7d3a9f15c2e8'
down_revision: str | None = '5b7e2c94a0d1'
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
FEED_POLICY = (
    "Read no more often than the site asks; each job keeps its link to the original posting and "
    "names the site as its source. Jobs are shown only to this one user and never passed on."
)

# Frozen copy: migrations must not import application code that may change later.
FEEDS = [
    # key, name, domain, access_type, access_method, terms_url, min_interval_hours
    ("feed_remotive", "Remotive", "remotive.com", "official_api", "Public remote jobs API",
     "https://remotive.com/api-documentation", 6),
    ("feed_jobspresso", "Jobspresso", "jobspresso.co", "official_feed", "Public job RSS feed",
     "https://jobspresso.co/terms-and-conditions/", 2),
    ("feed_weworkremotely", "We Work Remotely", "weworkremotely.com", "official_feed", "Public job RSS feed",
     "https://weworkremotely.com/terms-of-service", 2),
    ("feed_himalayas", "Himalayas", "himalayas.app", "official_api", "Public jobs API (search, jobs open to Finland)",
     "https://himalayas.app/api", 6),
    ("feed_jobicy", "Jobicy", "jobicy.com", "official_api", "Public remote jobs API (Finland and Europe)",
     "https://jobicy.com/jobs-rss-feed", 6),
    ("feed_arbeitnow", "Arbeitnow", "arbeitnow.com", "official_api", "Public job board API (remote jobs only)",
     "https://www.arbeitnow.com/api/job-board-api", 6),
    ("feed_abo_akademi", "Åbo Akademi", "abo.rekrytointi.com", "official_feed", "Official vacancies RSS feed",
     "https://abo.rekrytointi.com/paikat/?o=A_LOJ&list=1", 2),
]
ALERTS = [
    ("alert_europeremotely", "Europe Remotely job alerts", "europeremotely.com"),
    ("alert_ziprecruiter", "ZipRecruiter job alerts", "ziprecruiter.com"),
]
SOURCES = [
    {
        "id": f"00000000-0000-4000-8000-{n:012d}",
        "key": key,
        "name": name,
        "domain": domain,
        "access_type": access_type,
        "access_method": method,
        "terms_url": terms,
        "policy_notes": FEED_POLICY,
        "rate_limit": {"min_interval_hours": hours},
    }
    for n, (key, name, domain, access_type, method, terms, hours) in enumerate(FEEDS, start=13)
] + [
    {
        "id": f"00000000-0000-4000-8000-{n:012d}",
        "key": key,
        "name": name,
        "domain": domain,
        "access_type": "user_provided",
        "access_method": ALERT_ACCESS,
        "terms_url": None,
        "policy_notes": ALERT_POLICY,
        "rate_limit": None,
    }
    for n, (key, name, domain) in enumerate(ALERTS, start=13 + len(FEEDS))
]
FINNISH_PLACES = ("finland", "suomi", "turku", "åbo", "helsinki", "espoo", "vantaa", "tampere", "oulu")


def upgrade() -> None:
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('available_from_finland', sa.String(length=10), server_default='unknown', nullable=False)
        )
        batch_op.create_index(batch_op.f('ix_job_available_from_finland'), ['available_from_finland'], unique=False)
        batch_op.create_check_constraint(
            'available_from_finland', "available_from_finland IN ('yes', 'no', 'unknown')"
        )

    # Existing jobs: a stated location in Finland is enough to say yes; everything else stays
    # unknown until the job is seen again (the application reassesses it then).
    job = sa.table('job', sa.column('location', sa.String), sa.column('available_from_finland', sa.String))
    location = sa.func.lower(sa.func.coalesce(job.c.location, ''))
    op.execute(
        job.update()
        .where(sa.or_(location == 'fi', *[location.like(f'%{place}%') for place in FINNISH_PLACES]))
        .values(available_from_finland='yes')
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
        batch_op.drop_constraint('available_from_finland', type_='check')
        batch_op.drop_index(batch_op.f('ix_job_available_from_finland'))
        batch_op.drop_column('available_from_finland')
