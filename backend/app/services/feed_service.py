"""Official job feeds and public job APIs -> jobs.

- A feed is read only when it is due: never more often than its site asks
  (``FeedSite.min_interval_hours``), whether the check is automatic or from "Check now".
- One check at a time per site; a failed check is recorded as a readable sentence and the
  next one waits for the usual interval (no immediate retries).
- Every job goes through ``listing_intake.add_posting``, so a posting seen on several feeds,
  alert emails or URL imports is one job and can only be applied to once.
- Remote jobs that say they are only for other countries are skipped (``FEED_SKIP_UNAVAILABLE``).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.job_sources.feeds import PARSER_VERSION, SITES, SITES_BY_KEY, FeedFormatError, FeedJob, FeedSite
from app.adapters.web_fetch import FetchError, SafeFetcher
from app.core.config import Settings
from app.core.errors import AppError, not_found
from app.domain import schemas
from app.persistence.models import JobSource, JobSourceListing, utcnow
from app.services import audit, eligibility
from app.services.job_service import get_source
from app.services.listing_intake import add_posting
from app.services.storage import FileStore
from app.services.urls import canonicalize_url

logger = logging.getLogger("duuniscript.feeds")

FEED_FAILURE_MESSAGES = {
    "robots_disallowed": "The site's robots.txt no longer allows reading this feed, so it was not read.",
    "http_status": "The feed could not be retrieved. The site may be down or may have moved it.",
    "not_feed": "The address did not return a job feed. The site may have changed it.",
    "too_large": "The feed was larger than expected and was not read.",
    "timeout": "The feed took too long to respond.",
    "network_error": "The feed could not be reached. Check your internet connection.",
    "dns_failed": "The feed's address could not be found.",
    "blocked_address": "The feed's address pointed to a private network and was refused.",
    "not_json": "The feed was not in the expected format. The site may have changed it.",
    "not_xml": "The feed was not in the expected format. The site may have changed it.",
    "unexpected_shape": "The feed was not in the expected format. The site may have changed it.",
    "dtd_not_allowed": "The feed contained a document type declaration, which is not accepted.",
}
_LOCKS = {site.key: threading.Lock() for site in SITES}


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def next_allowed_at(source: JobSource, site: FeedSite) -> datetime | None:
    """When the feed may be read again (None: now). Failed checks count too."""
    last = max((t for t in (_aware(source.last_success_at), _aware(source.last_error_at)) if t), default=None)
    if last is None:
        return None
    allowed = last + timedelta(hours=site.min_interval_hours)
    return allowed if allowed > datetime.now(timezone.utc) else None


def _wanted(job: FeedJob, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{job.title}\n{job.description or ''}".lower()
    return any(word in haystack for word in keywords)


def sync_feed(
    session: Session,
    store: FileStore,
    fetcher: SafeFetcher,
    site: FeedSite,
    settings: Settings,
    actor: str = "user",
) -> schemas.FeedSyncResult:
    source = get_source(session, site.key)
    report = schemas.FeedSyncResult(key=site.key, name=site.name)
    if not source.enabled:
        raise AppError(409, "source_disabled", f"{site.name} is turned off.")
    wait_until = next_allowed_at(source, site)
    if wait_until is not None:
        raise AppError(
            429,
            "too_soon",
            f"{site.name} asks not to be read more often than every {site.min_interval_hours:g} hours.",
            {"next_allowed_at": wait_until.isoformat()},
        )
    lock = _LOCKS[site.key]
    if not lock.acquire(blocking=False):
        raise AppError(409, "sync_in_progress", f"{site.name} is already being checked.")
    try:
        jobs: list[FeedJob] = []
        try:
            for url in site.urls:
                page = fetcher.fetch_feed(url, honour_robots=site.honour_robots)
                jobs += site.parse(page.content)
        except (FetchError, FeedFormatError) as exc:
            reason = exc.reason if isinstance(exc, FetchError) else str(exc)
            _record_failure(session, source, reason, actor)
            raise AppError(
                502, "feed_error", FEED_FAILURE_MESSAGES.get(reason, "The feed check failed."), {"reason": reason}
            ) from exc

        keywords = settings.feed_keyword_list
        snapshots: list[str] = []
        seen: set[str] = set()
        try:
            for job in jobs:
                if job.external_id in seen:
                    continue
                seen.add(job.external_id)
                report.jobs_found += 1
                if eligibility.title_restriction(job.title):
                    job.available_from_finland = eligibility.NO
                if settings.feed_skip_unavailable and job.available_from_finland == eligibility.NO:
                    report.skipped_not_available += 1
                    continue
                if not _wanted(job, keywords):
                    report.skipped_keywords += 1
                    continue
                outcome = _add_job(session, store, source, site, job, snapshots)
                if outcome in ("created", "possible"):
                    report.jobs_created += 1
                    report.possible_duplicates += outcome == "possible"
                elif outcome == "merged":
                    report.jobs_merged += 1
                else:
                    report.jobs_already_known += 1
            source.last_success_at = utcnow()
            source.last_error = None
            source.last_error_at = None
            audit.record(session, "feed.synced", "job_source", source.id, report.model_dump(), actor=actor)
            session.commit()
        except BaseException:
            session.rollback()
            for path in snapshots:
                store.delete(path)
            raise
        return report
    finally:
        lock.release()


def _add_job(
    session: Session, store: FileStore, source: JobSource, site: FeedSite, job: FeedJob, snapshots: list[str]
) -> str:
    values = {
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "location": job.location,
        "employment_type": job.employment_type,
        "work_mode": job.work_mode,
        "salary_text": job.salary_text,
        "language": job.language,
        "published_on": job.published_on,
        "deadline_on": job.deadline_on,
        "deadline_at": job.deadline_at,
        "available_from_finland": job.available_from_finland,
    }
    outcome, _ = add_posting(
        session,
        store,
        source,
        external_id=job.external_id,
        link=job.link,
        canonical_url=canonicalize_url(job.link),
        values=values,
        seen_on=datetime.now(timezone.utc).date(),
        snapshot={"source": site.key, "parser_version": PARSER_VERSION, "feed_item": job.raw},
        parser_version=PARSER_VERSION,
        snapshots=snapshots,
    )
    return outcome


def _record_failure(session: Session, source: JobSource, reason: str, actor: str) -> None:
    source.last_error_at = utcnow()
    source.last_error = FEED_FAILURE_MESSAGES.get(reason, "The feed check failed.")
    audit.record(session, "feed.sync_failed", "job_source", source.id, {"reason": reason}, actor=actor,
                 result="failure")
    session.commit()


def sync_due(
    session: Session, store: FileStore, fetcher: SafeFetcher, settings: Settings, actor: str = "system"
) -> list[schemas.FeedSyncResult]:
    """Read every enabled feed that is due. One site failing does not stop the others."""
    results = []
    for site in SITES:
        source = get_source(session, site.key)
        if not source.enabled or next_allowed_at(source, site) is not None:
            continue
        try:
            results.append(sync_feed(session, store, fetcher, site, settings, actor))
        except AppError as exc:
            results.append(schemas.FeedSyncResult(key=site.key, name=site.name, error=exc.message))
    return results


def site_or_404(key: str) -> FeedSite:
    site = SITES_BY_KEY.get(key)
    if site is None:
        raise not_found("feed")
    return site


def status(session: Session, settings: Settings) -> schemas.FeedsStatus:
    counts = dict(
        session.execute(
            select(JobSource.key, func.count(func.distinct(JobSourceListing.job_id)))
            .join(JobSourceListing, JobSourceListing.source_id == JobSource.id)
            .where(JobSource.key.in_([s.key for s in SITES]))
            .group_by(JobSource.key)
        ).all()
    )
    feeds = []
    for site in SITES:
        source = get_source(session, site.key)
        feeds.append(
            schemas.FeedRead(
                key=site.key,
                name=site.name,
                domain=site.domain,
                enabled=source.enabled,
                access_method=site.access_method,
                terms_url=site.terms_url,
                attribution=site.attribution,
                min_interval_hours=site.min_interval_hours,
                last_success_at=source.last_success_at,
                last_error_at=source.last_error_at,
                last_error=source.last_error,
                next_allowed_at=next_allowed_at(source, site),
                jobs=counts.get(site.key, 0),
            )
        )
    return schemas.FeedsStatus(
        check_interval_minutes=settings.feed_sync_interval_minutes,
        skip_unavailable=settings.feed_skip_unavailable,
        keywords=settings.feed_keyword_list,
        feeds=feeds,
    )


def set_enabled(session: Session, key: str, enabled: bool) -> JobSource:
    source = session.scalar(select(JobSource).where(JobSource.key == key))
    if source is None:
        raise not_found("source")
    if source.enabled != enabled:
        source.enabled = enabled
        audit.record(session, "source.enabled_changed", "job_source", source.id, {"enabled": enabled})
        session.commit()
    return source
