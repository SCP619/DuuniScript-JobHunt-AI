"""Home dashboard summary (PRD 6, "Home"): counts, upcoming deadlines, best matches, status."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain import schemas
from app.persistence.models import Application, ApplicationStatus, Job, JobMatch, JobSource, JobStatus
from app.services import backup_service, match_service

OPEN_STATUSES = (JobStatus.NEW.value, JobStatus.REVIEWED.value, JobStatus.SAVED.value, JobStatus.DRAFTING.value)
DEADLINE_DAYS = 7


def _count(session: Session, query) -> int:  # noqa: ANN001
    return int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)


def summary(session: Session, settings: Settings, today: date | None = None) -> schemas.DashboardSummary:
    today = today or date.today()
    match_service.refresh(session, today)
    visible = select(Job.id).where(Job.hidden.is_(False))
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    counts = schemas.DashboardCounts(
        jobs=_count(session, visible),
        jobs_new_this_week=_count(session, visible.where(Job.first_seen_at >= week_ago)),
        jobs_saved=_count(session, visible.where(Job.status == JobStatus.SAVED.value)),
        jobs_good_match=_count(
            session,
            visible.join(JobMatch, JobMatch.job_id == Job.id).where(
                JobMatch.score >= 60, JobMatch.has_blockers.is_(False), Job.status.in_(OPEN_STATUSES)
            ),
        ),
        applications_drafting=_count(session, select(Application.id).where(Application.status == ApplicationStatus.DRAFT.value)),
        applications_ready=_count(session, select(Application.id).where(Application.status == ApplicationStatus.READY.value)),
        applications_sent=_count(session, select(Application.id).where(Application.status == ApplicationStatus.SUBMITTED.value)),
        interviews=_count(session, select(Application.id).where(Application.outcome == "interview")),
        offers=_count(session, select(Application.id).where(Application.outcome.in_(("offer", "accepted")))),
    )

    soon = session.execute(
        select(Job, JobMatch.score)
        .outerjoin(JobMatch, JobMatch.job_id == Job.id)
        .where(
            Job.hidden.is_(False),
            Job.status.in_(OPEN_STATUSES),
            Job.deadline_on >= today,
            Job.deadline_on <= today + timedelta(days=DEADLINE_DAYS),
        )
        .order_by(Job.deadline_on, Job.title)
        .limit(10)
    ).all()
    best = session.execute(
        select(Job, JobMatch.score)
        .join(JobMatch, JobMatch.job_id == Job.id)
        .where(
            Job.hidden.is_(False),
            Job.status.in_((JobStatus.NEW.value, JobStatus.REVIEWED.value, JobStatus.SAVED.value)),
            JobMatch.score.is_not(None),
            JobMatch.has_blockers.is_(False),
        )
        .order_by(JobMatch.score.desc(), Job.first_seen_at.desc())
        .limit(5)
    ).all()

    sources = list(session.scalars(select(JobSource).where(JobSource.key.like("feed_%") | (JobSource.key == "email_alerts"))))
    failing = [s for s in sources if s.last_error_at and (not s.last_success_at or s.last_error_at > s.last_success_at)]
    last_check = max((s.last_success_at for s in sources if s.last_success_at), default=None)
    backups = backup_service.list_backups(settings)

    return schemas.DashboardSummary(
        counts=counts,
        deadlines_soon=[_item(job, score) for job, score in soon],
        best_matches=[_item(job, score) for job, score in best],
        status=schemas.DashboardStatus(
            last_source_check_at=last_check,
            sources_turned_off=sorted(s.name for s in sources if not s.enabled),
            sources_failing=sorted(s.name for s in failing if s.enabled),
            last_backup_at=backups[0].created_at if backups else None,
            automatic_backups=bool(settings.backup_interval_hours),
        ),
    )


def _item(job: Job, score: int | None) -> schemas.DashboardJob:
    return schemas.DashboardJob(
        id=job.id, title=job.title, company=job.company, location=job.location,
        deadline_on=job.deadline_on, status=JobStatus(job.status), match_score=score,
    )
