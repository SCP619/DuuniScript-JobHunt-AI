"""Outcome statistics (PRD FR-022): what leads to replies and interviews, and how fast."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.persistence.models import Application, ApplicationStatus, Job, JobSourceListing
from app.services import drafting

RESPONSE = ("interview", "rejected", "offer", "accepted", "declined")
INTERVIEW = ("interview", "offer", "accepted", "declined")
OFFER = ("offer", "accepted", "declined")


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def _group(rows: list[tuple[str, Application]]) -> list[dict]:
    groups: dict[str, list[Application]] = defaultdict(list)
    for key, app in rows:
        groups[key].append(app)
    out = []
    for key, apps in groups.items():
        responses = sum(1 for a in apps if a.outcome in RESPONSE)
        out.append({"key": key, "sent": len(apps), "responses": responses,
                    "interviews": sum(1 for a in apps if a.outcome in INTERVIEW),
                    "offers": sum(1 for a in apps if a.outcome in OFFER),
                    "response_rate": _rate(responses, len(apps))})
    return sorted(out, key=lambda g: (-g["sent"], g["key"]))


def role_word(title: str) -> str:
    """The main role word of a title: the last meaningful word ("Senior Data Analyst" → analyst)."""
    meaningful = drafting.words(title)  # a set: used only to filter, the title gives the order
    words = [w.lower() for w in re.findall(r"[^\W_]+", title or "")
             if w.lower() in meaningful and not w.isdigit() and w.lower() not in ("senior", "junior", "lead")]
    return words[-1] if words else "other"


def outcomes(session: Session) -> dict:
    apps = list(session.scalars(select(Application).where(Application.submitted_at.is_not(None))))
    jobs = {j.id: j for j in session.scalars(
        select(Job).where(Job.id.in_([a.job_id for a in apps])).options(selectinload(Job.listings).selectinload(JobSourceListing.source)))}
    by_source, by_role, days = [], [], []
    for app in apps:
        job = jobs.get(app.job_id)
        if job is None:
            continue
        sources = sorted({listing.source.key for listing in job.listings}) or ["unknown"]
        by_source += [(key, app) for key in sources]
        by_role.append((role_word(job.title), app))
        if app.outcome in RESPONSE and app.outcome_on and app.submitted_at:
            days.append((app.outcome_on - app.submitted_at.astimezone().date()).days)  # local date, like outcome_on
    sent = len(apps)
    responses = sum(1 for a in apps if a.outcome in RESPONSE)
    now = datetime.now(timezone.utc)
    weeks = []
    for back in range(11, -1, -1):
        start = now - timedelta(weeks=back + 1)
        end = now - timedelta(weeks=back)
        iso = end.isocalendar()
        weeks.append({"week": f"{iso.year}-W{iso.week:02d}",
                      "sent": sum(1 for a in apps if a.submitted_at and start < a.submitted_at <= end)})
    return {
        "sent": sent, "responses": responses,
        "interviews": sum(1 for a in apps if a.outcome in INTERVIEW),
        "offers": sum(1 for a in apps if a.outcome in OFFER),
        "response_rate": _rate(responses, sent),
        "interview_rate": _rate(sum(1 for a in apps if a.outcome in INTERVIEW), sent),
        "median_days_to_reply": float(median(days)) if days else None,
        "by_source": _group(by_source), "by_role": _group(by_role), "sent_per_week": weeks,
        "_withdrawn": sum(1 for a in apps if a.status == ApplicationStatus.WITHDRAWN.value),
    }
