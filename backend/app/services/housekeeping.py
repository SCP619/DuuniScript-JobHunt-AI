"""Keep the job list tidy: expire jobs whose deadline passed, archive old ones never acted on.

- Expire: status new, reviewed or saved, and the stated deadline is before today → ``expired``.
- Merge reposts: the same company, title and place listed again → one job (job_service.merge_reposts).
- Archive: first seen more than ``JOB_ARCHIVE_DAYS`` ago (default 60), never saved, drafted or
  applied to, no application → ``archived_at`` is set; archived jobs leave the lists but are
  kept (duplicate detection still sees them, so they do not come back as "new").
Runs daily while the app runs; ``POST /api/v1/jobs/housekeeping`` runs it now.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import Application, Job, JobStatus, utcnow
from app.services import audit

OPEN = (JobStatus.NEW.value, JobStatus.REVIEWED.value, JobStatus.SAVED.value)
UNTOUCHED = (JobStatus.NEW.value, JobStatus.REVIEWED.value, JobStatus.NOT_RELEVANT.value, JobStatus.EXPIRED.value)


def run(session: Session, archive_days: int, today: date | None = None) -> dict:
    today = today or date.today()
    expired = 0
    for job in session.scalars(select(Job).where(Job.status.in_(OPEN), Job.deadline_on < today)):
        job.status = JobStatus.EXPIRED.value
        job.updated_at = utcnow()
        expired += 1
    archived = 0
    if archive_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=archive_days)
        with_application = select(Application.job_id)
        for job in session.scalars(select(Job).where(
            Job.archived_at.is_(None), Job.first_seen_at < cutoff, Job.status.in_(UNTOUCHED),
            Job.id.not_in(with_application),
        )):
            job.archived_at = utcnow()
            archived += 1
    if expired or archived:
        audit.record(session, "jobs.housekeeping", "job", None, {"expired": expired, "archived": archived}, actor="system")
    session.commit()
    from app.services.job_service import merge_reposts

    merged = merge_reposts(session)
    return {"expired": expired, "archived": archived, "merged": merged}
