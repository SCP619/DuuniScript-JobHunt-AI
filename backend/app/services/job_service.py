"""Job intake, listing and status rules (AFD 4, BSD 8-9, DBD 7).

- Manual entry and user-initiated URL import create a canonical job plus a source listing.
- Publication date and deadline are only what the source (or user) states; never inferred.
- Duplicate detection, stage 1: identical canonical URL, or the same source external ID.
  Stage 2 (job_matching): the same company and title, with listing date, location and
  description not contradicting it. A clear match is merged into the existing job as another
  listing; a near match is kept as a new job flagged ``possible_duplicate_of`` for the user.
- URL import reads only published JobPosting structured data. If there is none, the user
  is asked to enter the job manually; nothing is guessed from page text.
- Job content is untrusted data. It is stored and displayed, never executed or obeyed.
- English first: if a posting is not in English and the page itself declares an English
  version on the same site, that version is fetched once and used only if its advertisement
  text really is English. ``language`` is what the page states, or what the text clearly is.
"""

from __future__ import annotations

import hashlib
from datetime import date, timezone

from sqlalchemy import Select, and_, func, literal_column, or_, select
from sqlalchemy.orm import Session, selectinload

from app.adapters.job_sources.jsonld import PARSER_VERSION, NoJobPosting, ParsedJob, parse_job_posting
from app.adapters.job_sources.language import alternate_url
from app.adapters.web_fetch import FetchError, FetchResult, SafeFetcher
from app.core.errors import AppError, not_found
from app.domain import schemas
from app.persistence.models import (
    Job,
    JobSource,
    JobMatch,
    JobSourceListing,
    JobStatus,
    ListingStatus,
    new_id,
    utcnow,
)
from app.services import audit, eligibility
from app.services.job_matching import Posting, find_match
from app.services.storage import FileStore
from app.services.urls import canonicalize_url, domain_of, validate_http_url

MANUAL_SOURCE = "manual"
SCREENSHOT_SOURCE = "screenshot_import"
URL_IMPORT_SOURCE = "url_import"

CONTENT_FIELDS = (
    "title", "company", "description", "location", "employment_type", "work_mode",
    "salary_text", "language", "application_url", "published_on", "deadline_on", "deadline_at",
)
HASHED_FIELDS = ("company", "title", "location", "description")

NO_STRUCTURED_DATA_MESSAGE = (
    "This page does not publish job details in a format DuuniScript can read reliably. "
    "Add the job manually instead."
)
# Readable explanation of the last import failure, shown in Settings (max 200 characters).
IMPORT_FAILURE_MESSAGES = {
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

SORTS = {
    # rowid: jobs created in the same instant keep their insertion order.
    "newest": (Job.first_seen_at.desc(), literal_column("job.rowid").desc()),
    "published": (Job.published_on.is_(None), Job.published_on.desc(), Job.first_seen_at.desc(), Job.id),
    "deadline": (Job.deadline_on.is_(None), Job.deadline_on.asc(), Job.first_seen_at.desc(), Job.id),
    "company": (func.lower(Job.company), func.lower(Job.title), Job.id),
    "title": (func.lower(Job.title), func.lower(Job.company), Job.id),
    # Best match first; jobs without a score last (JobMatch is joined in list_jobs).
    "match": (JobMatch.score.is_(None), JobMatch.score.desc(), Job.first_seen_at.desc(), Job.id),
}


def content_hash(values: dict) -> str:
    normalized = "\x1f".join(" ".join(str(values.get(f) or "").lower().split()) for f in HASHED_FIELDS)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_source(session: Session, key: str) -> JobSource:
    source = session.scalar(select(JobSource).where(JobSource.key == key))
    if source is None:
        raise AppError(500, "source_missing", "A built-in job source is missing; run database migrations.")
    return source


def _ensure_not_duplicate_url(session: Session, *canonical_urls: str | None) -> None:
    urls = [u for u in canonical_urls if u]
    if not urls:
        return
    existing = session.scalar(select(Job.id).where(Job.canonical_url.in_(urls)))
    if existing:
        raise AppError(409, "duplicate_job", "This job is already in your list.", {"job_id": existing})


def _ensure_not_duplicate_external(session: Session, source: JobSource, external_id: str | None) -> None:
    if not external_id:
        return
    existing = session.scalar(
        select(JobSourceListing.job_id).where(
            JobSourceListing.source_id == source.id, JobSourceListing.external_id == external_id
        )
    )
    if existing:
        raise AppError(409, "duplicate_job", "This job is already in your list.", {"job_id": existing})


def _content_values(data: schemas.JobContentFields | schemas.JobCreate) -> dict:
    values = data.model_dump(include=set(CONTENT_FIELDS))
    for key in ("employment_type", "work_mode"):
        if values.get(key) is not None:
            values[key] = values[key].value
    if values.get("application_url"):
        validate_http_url(values["application_url"], "application_url")
    if values.get("deadline_at"):
        if not values.get("deadline_on"):
            # The calendar date in the timezone the deadline was stated in; derived, not guessed.
            values["deadline_on"] = values["deadline_at"].date()
        values["deadline_at"] = values["deadline_at"].astimezone(timezone.utc)
    return values


# ---------- Matching and merging ----------

MERGE_FILL_FIELDS = (
    "description", "location", "employment_type", "work_mode", "salary_text", "language",
    "application_url", "published_on", "deadline_on", "deadline_at",
)


def posting_of(values: dict, seen_on: date) -> Posting:
    return Posting(
        company=values["company"],
        title=values["title"],
        location=values.get("location"),
        description=values.get("description"),
        listed_on=values.get("published_on") or seen_on,
    )


def fill_blanks(job: Job, values: dict) -> list[str]:
    """Copy details the existing job lacks; never overwrite what it already has."""
    filled = []
    for name in MERGE_FILL_FIELDS:
        if getattr(job, name) is None and values.get(name) is not None:
            setattr(job, name, values[name])
            filled.append(name)
    if job.available_from_finland in (None, eligibility.UNKNOWN):
        known = values.get("available_from_finland")
        if known in (eligibility.YES, eligibility.NO):
            job.available_from_finland = known
            filled.append("available_from_finland")
        elif "location" in filled:
            job.available_from_finland = eligibility.assess(job.location)
    if any(name in HASHED_FIELDS for name in filled):
        job.content_hash = content_hash({f: getattr(job, f) for f in HASHED_FIELDS})
    return filled


def set_canonical_if_free(session: Session, job: Job, canonical: str | None) -> None:
    if job.canonical_url or not canonical:
        return
    if session.scalar(select(Job.id).where(Job.canonical_url == canonical)) is None:
        job.canonical_url = canonical


# ---------- Create ----------


def create_manual(session: Session, data: schemas.JobCreate) -> Job:
    canonical = None
    if data.url:
        validate_http_url(data.url)
        canonical = canonicalize_url(data.url)
    _ensure_not_duplicate_url(session, canonical)
    source_key = SCREENSHOT_SOURCE if data.added_from == "screenshots" else MANUAL_SOURCE
    source = get_source(session, source_key)
    values = _content_values(data)
    values["available_from_finland"] = eligibility.assess(values.get("location"))
    apply_manually = data.apply_manually if data.apply_manually is not None else data.added_from == "screenshots"
    now = utcnow()
    # Typed in by the user: never merged automatically, but a likely duplicate is flagged.
    _, match = find_match(session, posting_of(values, now.date()))
    job = Job(
        **values,
        canonical_url=canonical,
        content_hash=content_hash(values),
        possible_duplicate_of_id=match.id if match else None,
        apply_manually=apply_manually,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(job)
    session.flush()
    session.add(
        JobSourceListing(
            job_id=job.id,
            source_id=source.id,
            source_url=data.url,
            source_published_on=data.published_on,
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    audit.record(
        session, "job.created", "job", job.id, {"source": source_key, "possible_duplicate": match is not None}
    )
    session.commit()
    return get_job(session, job.id)


def import_from_url(
    session: Session, store: FileStore, fetcher: SafeFetcher, url: str, enabled: bool
) -> tuple[Job, bool]:
    """Returns the job and whether it is new (False: added to a job already in the list)."""
    if not enabled:
        raise AppError(403, "url_import_disabled", "URL import is turned off in settings.")
    validate_http_url(url)
    requested_canonical = canonicalize_url(url)
    _ensure_not_duplicate_url(session, requested_canonical)
    source = get_source(session, URL_IMPORT_SOURCE)
    if not source.enabled:
        raise AppError(403, "source_disabled", "URL import is paused.")

    try:
        page = fetcher.fetch_html(url)
        parsed = parse_job_posting(page.text)
    except FetchError as exc:
        _record_failure(session, source, url, exc.reason)
        raise
    except NoJobPosting as exc:
        _record_failure(session, source, url, exc.reason)
        raise AppError(422, "no_structured_job_data", NO_STRUCTURED_DATA_MESSAGE, {"reason": exc.reason}) from exc

    other_language_url = None
    if parsed.language != "en":
        english = _english_version(fetcher, page, parsed)
        if english is not None:
            other_language_url = page.final_url
            page, parsed = english

    final_canonical = canonicalize_url(page.final_url)
    _ensure_not_duplicate_url(session, final_canonical)
    domain = domain_of(page.final_url)
    external_id = f"{domain}:{parsed.external_id}"[:300] if parsed.external_id else None
    _ensure_not_duplicate_external(session, source, external_id)

    values = {
        "title": parsed.title,
        "company": parsed.company,
        "description": parsed.description,
        "location": parsed.location,
        "employment_type": parsed.employment_type.value if parsed.employment_type else None,
        "work_mode": parsed.work_mode.value if parsed.work_mode else None,
        "salary_text": parsed.salary_text,
        "language": parsed.language,
        "application_url": None,
        "published_on": parsed.published_on,
        "deadline_on": parsed.deadline_on,
        "deadline_at": parsed.deadline_at,
    }
    values["available_from_finland"] = eligibility.assess(values["location"])
    now = utcnow()
    verdict, match = find_match(session, posting_of(values, now.date()))
    listing_id = new_id()
    snapshot = store.write_snapshot(
        listing_id,
        {
            "captured_at": now.isoformat(),
            "requested_url": url,
            "final_url": page.final_url,
            "parser_version": PARSER_VERSION,
            "other_language_url": other_language_url,
            "job_posting": parsed.raw,
        },
    )
    try:
        if verdict == "same":
            job = match
            filled = fill_blanks(job, values)
            set_canonical_if_free(session, job, final_canonical)
            job.last_seen_at = now
        else:
            filled = []
            job = Job(
                **values,
                canonical_url=final_canonical,
                content_hash=content_hash(values),
                possible_duplicate_of_id=match.id if match else None,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(job)
            session.flush()
        session.add(
            JobSourceListing(
                id=listing_id,
                job_id=job.id,
                source_id=source.id,
                external_id=external_id,
                source_url=page.final_url,
                source_published_on=parsed.published_on,
                first_seen_at=now,
                last_seen_at=now,
                listing_status=ListingStatus.ACTIVE.value,
                snapshot_path=snapshot.relative_path,
                snapshot_hash=snapshot.sha256,
                captured_at=now,
                parser_version=PARSER_VERSION,
            )
        )
        source.last_success_at = now
        audit.record(
            session,
            "job.imported",
            "job",
            job.id,
            {
                "source": URL_IMPORT_SOURCE,
                "domain": domain,
                "parser_version": PARSER_VERSION,
                "english_version_used": other_language_url is not None,
                "match": verdict,
                "filled_fields": filled,
            },
        )
        session.commit()
    except BaseException:
        session.rollback()
        store.delete(snapshot.relative_path)
        raise
    return get_job(session, job.id), verdict != "same"


def _english_version(
    fetcher: SafeFetcher, page: FetchResult, parsed: ParsedJob
) -> tuple[FetchResult, ParsedJob] | None:
    """The page's own declared English version of the same posting, if its text is English.

    Only same-site alternates are followed, the usual safety and robots rules apply, and any
    failure keeps the original. An "English" page whose advertisement is still Finnish is not
    used: it would only look like a translation.
    """
    candidate = alternate_url(page.text, page.final_url, "en")
    if not candidate or domain_of(candidate) != domain_of(page.final_url):
        return None
    if canonicalize_url(candidate) == canonicalize_url(page.final_url):
        return None
    try:
        english_page = fetcher.fetch_html(candidate)
        english = parse_job_posting(english_page.text)
    except (AppError, NoJobPosting):
        return None
    if english.language != "en" or domain_of(english_page.final_url) != domain_of(page.final_url):
        return None
    if parsed.external_id and english.external_id and parsed.external_id != english.external_id:
        return None  # declared as an alternate, but it is a different posting
    return english_page, english


def _record_failure(session: Session, source: JobSource, url: str, reason: str) -> None:
    source.last_error_at = utcnow()
    source.last_error = IMPORT_FAILURE_MESSAGES.get(reason, "The last import failed.")
    audit.record(
        session,
        "job.import_failed",
        "job_source",
        source.id,
        {"domain": domain_of(url), "reason": reason},
        result="failure",
    )
    session.commit()


# ---------- Read ----------


def _with_listings(query: Select) -> Select:
    return query.options(selectinload(Job.listings).selectinload(JobSourceListing.source))


def get_job(session: Session, job_id: str) -> Job:
    job = session.scalar(_with_listings(select(Job).where(Job.id == job_id)))
    if job is None:
        raise not_found("job")
    return job


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_jobs(session: Session, f: JobFilters) -> schemas.Page[schemas.JobSummary]:
    from app.services import match_service

    match_service.refresh(session)
    query = select(Job).outerjoin(JobMatch, JobMatch.job_id == Job.id)
    conditions = []
    if f.min_match is not None:
        conditions.append(JobMatch.score >= f.min_match)
    if not f.include_archived:
        conditions.append(Job.archived_at.is_(None))
    if f.q:
        pattern = f"%{_escape_like(f.q.lower())}%"
        conditions.append(
            or_(
                func.lower(Job.title).like(pattern, escape="\\"),
                func.lower(Job.company).like(pattern, escape="\\"),
                func.lower(Job.description).like(pattern, escape="\\"),
            )
        )
    if f.company:
        conditions.append(func.lower(Job.company).like(f"%{_escape_like(f.company.lower())}%", escape="\\"))
    if f.location:
        conditions.append(func.lower(Job.location).like(f"%{_escape_like(f.location.lower())}%", escape="\\"))
    if f.status:
        conditions.append(Job.status.in_([s.value for s in f.status]))
    if f.employment_type:
        conditions.append(Job.employment_type == f.employment_type.value)
    if f.work_mode:
        conditions.append(Job.work_mode == f.work_mode.value)
    if f.available_from_finland:
        conditions.append(Job.available_from_finland.in_([a.value for a in f.available_from_finland]))
    if f.language == "unknown":
        conditions.append(Job.language.is_(None))
    elif f.language:
        language = func.lower(Job.language)
        conditions.append(or_(language == f.language, language.like(f"{f.language}-%")))
    if f.published_from:
        conditions.append(Job.published_on >= f.published_from)
    if f.published_to:
        conditions.append(Job.published_on <= f.published_to)
    if f.deadline_from:
        conditions.append(Job.deadline_on >= f.deadline_from)
    if f.deadline_to:
        conditions.append(Job.deadline_on <= f.deadline_to)
    if f.hidden is not None:
        conditions.append(Job.hidden.is_(f.hidden))
    if f.source:
        conditions.append(
            Job.id.in_(
                select(JobSourceListing.job_id)
                .join(JobSource, JobSource.id == JobSourceListing.source_id)
                .where(JobSource.key == f.source)
            )
        )
    if conditions:
        query = query.where(and_(*conditions))

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    jobs = session.scalars(
        _with_listings(query).order_by(*SORTS[f.sort]).limit(f.limit).offset(f.offset)
    ).all()
    matches = match_service.matches_for(session, [j.id for j in jobs])
    return schemas.Page[schemas.JobSummary](
        items=[to_summary(j, matches.get(j.id)) for j in jobs], total=total, limit=f.limit, offset=f.offset
    )


class JobFilters:
    def __init__(
        self,
        q: str | None = None,
        company: str | None = None,
        location: str | None = None,
        source: str | None = None,
        status: list[JobStatus] | None = None,
        employment_type=None,  # noqa: ANN001
        work_mode=None,  # noqa: ANN001
        language: str | None = None,
        available_from_finland=None,  # noqa: ANN001 - list[Availability] | None
        published_from: date | None = None,
        published_to: date | None = None,
        deadline_from: date | None = None,
        deadline_to: date | None = None,
        hidden: bool | None = False,
        min_match: int | None = None,
        include_archived: bool = False,
        sort: str = "newest",
        limit: int = 50,
        offset: int = 0,
    ) -> None:
        self.q = q.strip() if q and q.strip() else None
        self.company, self.location, self.source = company, location, source
        self.status = status
        self.employment_type, self.work_mode = employment_type, work_mode
        self.language = language.lower() if language else None
        self.available_from_finland = available_from_finland
        self.published_from, self.published_to = published_from, published_to
        self.deadline_from, self.deadline_to = deadline_from, deadline_to
        self.hidden, self.sort, self.limit, self.offset = hidden, sort, limit, offset
        self.min_match = min_match
        self.include_archived = include_archived


def _source_keys(job: Job) -> list[str]:
    return sorted({listing.source.key for listing in job.listings})


def _columns(job: Job, model: type[schemas.BaseModel]) -> dict:
    """Plain column values for a response model; relationships are mapped explicitly."""
    skip = ("sources", "listings", "possible_duplicate_of", "match_score", "match_has_blockers", "archived")
    values = {name: getattr(job, name) for name in model.model_fields if name not in skip}
    return {**values, "possible_duplicate_of": job.possible_duplicate_of_id, "archived": job.archived_at is not None}


def _match_fields(match: JobMatch | None) -> dict:
    if match is None:
        return {"match_score": None, "match_has_blockers": False}
    return {"match_score": match.score, "match_has_blockers": match.has_blockers}


def to_summary(job: Job, match: JobMatch | None = None) -> schemas.JobSummary:
    return schemas.JobSummary(**_columns(job, schemas.JobSummary), sources=_source_keys(job), **_match_fields(match))


def to_read(job: Job, match: JobMatch | None = None) -> schemas.JobRead:
    read = schemas.JobRead(**_columns(job, schemas.JobRead), sources=_source_keys(job), **_match_fields(match))
    read.listings = [
        schemas.JobListingRead(
            source_key=listing.source.key,
            source_name=listing.source.name,
            source_url=listing.source_url,
            external_id=listing.external_id,
            source_published_on=listing.source_published_on,
            first_seen_at=listing.first_seen_at,
            last_seen_at=listing.last_seen_at,
            listing_status=listing.listing_status,
            captured_at=listing.captured_at,
            parser_version=listing.parser_version,
        )
        for listing in sorted(job.listings, key=lambda item: item.first_seen_at)
    ]
    return read


# ---------- Update ----------


def update_job(session: Session, job_id: str, data: schemas.JobUpdate) -> Job:
    job = get_job(session, job_id)
    changes = data.model_dump(exclude_unset=True)
    if "possible_duplicate_of" in changes:
        changes["possible_duplicate_of_id"] = changes.pop("possible_duplicate_of")  # only null is accepted
    for required in ("title", "company", "status", "hidden"):
        if required in changes and changes[required] is None:
            raise AppError(422, "validation_error", f"{required} cannot be null.")
    if changes.get("application_url"):
        validate_http_url(changes["application_url"], "application_url")
    if changes.get("deadline_at"):
        changes["deadline_at"] = changes["deadline_at"].astimezone(timezone.utc)

    changed: list[str] = []
    old_status = job.status
    for key, value in changes.items():
        stored = value.value if hasattr(value, "value") else value
        if getattr(job, key) != stored:
            setattr(job, key, stored)
            changed.append(key)

    if not changed:
        return job
    if "location" in changed:
        job.available_from_finland = eligibility.assess(job.location)
    if any(k in HASHED_FIELDS for k in changed):
        job.content_hash = content_hash({f: getattr(job, f) for f in HASHED_FIELDS})
    job.updated_at = utcnow()
    if "possible_duplicate_of_id" in changed:
        audit.record(session, "job.duplicate_dismissed", "job", job.id, {})
        changed.remove("possible_duplicate_of_id")
    if "status" in changed:
        audit.record(session, "job.status_changed", "job", job.id, {"from": old_status, "to": job.status})
    other = sorted(k for k in changed if k != "status")
    if other:
        audit.record(session, "job.updated", "job", job.id, {"fields": other})
    session.commit()
    return get_job(session, job.id)


# ---------- Merge ----------

STATUS_PROGRESS = ("new", "reviewed", "saved", "drafting", "applied")


def merge_jobs(session: Session, job_id: str, into_job_id: str, actor: str = "user") -> Job:
    """The user confirmed two jobs are the same posting: keep ``into_job_id``.

    Listings move over, missing details are copied, notes are kept, and the further
    application status wins, so an application is never lost or repeated.
    """
    if job_id == into_job_id:
        raise AppError(422, "validation_error", "A job cannot be merged into itself.")
    duplicate, target = get_job(session, job_id), get_job(session, into_job_id)
    filled = fill_blanks(target, {name: getattr(duplicate, name) for name in MERGE_FILL_FIELDS})
    for listing in list(duplicate.listings):
        listing.job_id = target.id
    from app.persistence.models import Application

    # Applications follow the job they were made for, so none is lost (job_id is RESTRICT).
    for application in session.scalars(select(Application).where(Application.job_id == duplicate.id)):
        application.job_id = target.id
    if duplicate.user_notes:
        target.user_notes = "\n\n".join(n for n in (target.user_notes, duplicate.user_notes) if n)
    if duplicate.status in STATUS_PROGRESS and target.status in STATUS_PROGRESS:
        if STATUS_PROGRESS.index(duplicate.status) > STATUS_PROGRESS.index(target.status):
            target.status = duplicate.status
    if duplicate.deadline_on and (target.deadline_on is None or duplicate.deadline_on > target.deadline_on):
        target.deadline_on, target.deadline_at = duplicate.deadline_on, duplicate.deadline_at
    if target.status == "expired" and duplicate.status in STATUS_PROGRESS:
        target.status = duplicate.status  # listed again: open again
    if target.archived_at and not duplicate.archived_at:
        target.archived_at = None
    canonical = duplicate.canonical_url
    if target.possible_duplicate_of_id == duplicate.id:
        target.possible_duplicate_of_id = None
    for other in session.scalars(select(Job).where(Job.possible_duplicate_of_id == duplicate.id, Job.id != target.id)):
        other.possible_duplicate_of_id = target.id
    target.first_seen_at = min(target.first_seen_at, duplicate.first_seen_at)
    target.last_seen_at = max(target.last_seen_at, duplicate.last_seen_at)
    session.flush()
    session.expire(duplicate, ["listings"])
    session.expire(target, ["listings"])
    session.delete(duplicate)
    session.flush()
    set_canonical_if_free(session, target, canonical)
    target.updated_at = utcnow()
    audit.record(session, "job.merged", "job", target.id, {"merged_job_id": job_id, "filled_fields": filled}, actor=actor)
    session.commit()
    return get_job(session, target.id)


def merge_reposts(session: Session) -> int:
    """Merge jobs that are clearly the same posting listed again (same company, title and place,
    nothing contradicting it). The job with the most progress, else the oldest, is kept. Jobs
    that only *possibly* match are flagged ``possible_duplicate_of`` for the user to decide. Returns how many jobs were merged away."""
    from collections import defaultdict

    from app.persistence.models import Application
    from app.services.job_matching import Posting, company_key, compare, listed_on, title_key, _fold

    groups: dict[tuple[str, str, str], list[Job]] = defaultdict(list)
    for job in session.scalars(select(Job).order_by(Job.first_seen_at)):
        groups[(company_key(job.company), title_key(job.title), _fold(job.location))].append(job)
    with_application = set(session.scalars(select(Application.job_id)))
    merged = 0
    for jobs in groups.values():
        if len(jobs) < 2:
            continue
        def rank(j: Job) -> tuple:
            progress = STATUS_PROGRESS.index(j.status) if j.status in STATUS_PROGRESS else -1
            return (j.id in with_application, progress, -j.first_seen_at.timestamp())
        keeper = max(jobs, key=rank)
        keep = Posting(keeper.company, keeper.title, keeper.location, keeper.description, listed_on(keeper))
        ids = [j.id for j in jobs if j is not keeper]
        for job_id in ids:
            other = session.get(Job, job_id)
            if other is None:
                continue
            posting = Posting(other.company, other.title, other.location, other.description, listed_on(other))
            verdict = compare(posting, keep)
            if verdict == "same":
                merge_jobs(session, other.id, keeper.id, actor="system")
                merged += 1
            elif verdict == "possible" and other.possible_duplicate_of_id is None:
                other.possible_duplicate_of_id = keeper.id  # the user decides (merge banner)
    session.commit()
    return merged


# ---------- Sources ----------


def list_sources(session: Session) -> list[JobSource]:
    return list(session.scalars(select(JobSource).order_by(JobSource.name)))
