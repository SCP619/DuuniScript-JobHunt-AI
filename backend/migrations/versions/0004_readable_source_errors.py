"""job_source.last_error: replace internal reason codes with readable sentences

Data-only. Earlier versions stored codes such as ``robots_disallowed``; the UI shows this
text to the user, so it is now a short English sentence.

Revision ID: 9c4f1d2a7b31
Revises: e86da255d9e2
Create Date: 2026-11-10 09:30:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '9c4f1d2a7b31'
down_revision: str | None = 'e86da255d9e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy: migrations must not import application code that may change later.
MESSAGES = {
    "no_structured_data": "The last page had no job details DuuniScript can read, so it had to be added manually.",
    "no_job_posting": "The last page had no job details DuuniScript can read, so it had to be added manually.",
    "missing_title_or_company": "The last page's job details had no job title or company name.",
    "robots_disallowed": "The last site does not allow automated access, so the job had to be added manually.",
    "blocked_address": "The last address pointed to a local or private network and was refused.",
    "blocked_port": "The last address used a non-standard port and was refused.",
    "dns_failed": "The last address could not be found. Check the link.",
    "http_status": "The last page could not be retrieved. It may have been removed.",
    "not_html": "The last address was not a web page.",
    "too_large": "The last page was too large to import.",
    "timeout": "The last page took too long to respond.",
    "network_error": "The last page could not be reached. Check your internet connection.",
    "bad_redirect": "The last page redirected without a destination.",
    "too_many_redirects": "The last page redirected too many times.",
}


def upgrade() -> None:
    table = sa.table("job_source", sa.column("last_error", sa.String))
    for code, message in MESSAGES.items():
        op.execute(table.update().where(table.c.last_error == code).values(last_error=message))


def downgrade() -> None:
    pass  # the sentences are still valid text; nothing to undo
