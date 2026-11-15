"""In-app notifications (PRD FR-020): new good matches, near deadlines, approved but unsent
applications, and sent applications with no outcome after two weeks.

Notifications are derived from the data: ``refresh`` creates the ones that apply (each kind once
per job or application) and never re-creates one the user dismissed. Texts name the job and
employer only; no personal details.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.persistence.models import (
    Application,
    ApplicationStatus,
    Job,
    JobMatch,
    JobStatus,
    Notification,
    NotificationKind,
    utcnow,
)
from app.services import match_service

GOOD_MATCH = 70
GOOD_MATCH_RECENT_DAYS = 14
DEADLINE_DAYS = 3
READY_DAYS = 2
FOLLOW_UP_DAYS = 14


def _existing(session: Session) -> set[tuple[str, str]]:
    return {(n.kind, n.entity_id) for n in session.scalars(select(Notification))}


def refresh(session: Session, today: date | None = None) -> int:
    today = today or date.today()
    now = datetime.now(timezone.utc)
    match_service.refresh(session, today)
    seen = _existing(session)
    created = 0

    def add(kind: NotificationKind, entity_type: str, entity_id: str, title: str, message: str, link: str) -> None:
        nonlocal created
        if (kind.value, entity_id) in seen:
            return
        seen.add((kind.value, entity_id))
        session.add(Notification(kind=kind.value, entity_type=entity_type, entity_id=entity_id,
                                 title=title[:300], message=message[:600], link=link))
        created += 1

    good = session.execute(
        select(Job, JobMatch.score)
        .join(JobMatch, JobMatch.job_id == Job.id)
        .where(
            Job.hidden.is_(False),
            Job.status == JobStatus.NEW.value,
            Job.first_seen_at >= now - timedelta(days=GOOD_MATCH_RECENT_DAYS),
            JobMatch.score >= GOOD_MATCH,
            JobMatch.has_blockers.is_(False),
        )
    ).all()
    for job, score in good:
        add(NotificationKind.GOOD_MATCH, "job", job.id, f"Good match: {job.title}",
            f"{job.company} · match {score}/100.", f"/jobs/{job.id}")

    soon = session.scalars(
        select(Job).where(
            Job.hidden.is_(False),
            Job.status.in_((JobStatus.SAVED.value, JobStatus.DRAFTING.value)),
            Job.deadline_on >= today,
            Job.deadline_on <= today + timedelta(days=DEADLINE_DAYS),
        )
    )
    for job in soon:
        days = (job.deadline_on - today).days
        when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
        add(NotificationKind.DEADLINE_SOON, "job", job.id, f"Deadline {when}: {job.title}",
            f"{job.company} · apply by {job.deadline_on.isoformat()}.", f"/jobs/{job.id}")

    ready = session.execute(
        select(Application, Job).join(Job, Job.id == Application.job_id).where(
            Application.status == ApplicationStatus.READY.value,
            Application.ready_at <= now - timedelta(days=READY_DAYS),
        )
    ).all()
    for application, job in ready:
        add(NotificationKind.READY_NOT_SENT, "application", application.id, f"Approved but not sent: {job.title}",
            f"{job.company} · your documents are ready. Send them, then record it.", f"/applications/{application.id}")

    waiting = session.execute(
        select(Application, Job).join(Job, Job.id == Application.job_id).where(
            Application.status == ApplicationStatus.SUBMITTED.value,
            Application.outcome.is_(None),
            Application.submitted_at <= now - timedelta(days=FOLLOW_UP_DAYS),
        )
    ).all()
    for application, job in waiting:
        add(NotificationKind.FOLLOW_UP, "application", application.id, f"Any news from {job.company}?",
            f"{job.title} · sent two weeks ago. Record the outcome, or consider a short follow-up.",
            f"/applications/{application.id}")

    if created:
        session.commit()
    return created


def list_notifications(session: Session, include_dismissed: bool, limit: int) -> tuple[list[Notification], int]:
    refresh(session)
    query = select(Notification)
    if not include_dismissed:
        query = query.where(Notification.dismissed_at.is_(None))
    items = list(session.scalars(query.order_by(Notification.read_at.is_not(None), Notification.created_at.desc()).limit(limit)))
    unread = len(list(session.scalars(
        select(Notification.id).where(Notification.read_at.is_(None), Notification.dismissed_at.is_(None))
    )))
    return items, unread


def _get(session: Session, notification_id: str) -> Notification:
    item = session.get(Notification, notification_id)
    if item is None:
        raise not_found("notification")
    return item


def mark_read(session: Session, notification_id: str) -> Notification:
    item = _get(session, notification_id)
    item.read_at = item.read_at or utcnow()
    session.commit()
    return item


def mark_all_read(session: Session) -> int:
    items = list(session.scalars(select(Notification).where(Notification.read_at.is_(None))))
    now = utcnow()
    for item in items:
        item.read_at = now
    session.commit()
    return len(items)


def dismiss(session: Session, notification_id: str) -> Notification:
    item = _get(session, notification_id)
    now = utcnow()
    item.dismissed_at = item.dismissed_at or now
    item.read_at = item.read_at or now
    session.commit()
    return item
