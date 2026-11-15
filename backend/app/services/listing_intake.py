"""Adding a job seen on a source (alert email, job feed) without ever creating a duplicate.

1. the same source posting seen before -> only "last seen" is updated (and missing details filled);
2. the same posting address as a job in the list -> added to that job as another listing;
3. the same company and title, nothing contradicting it (job_matching) -> added likewise; on
   the same site this needs the same location too (a repost), as sites list one job per city;
4. otherwise a new job, flagged ``possible_duplicate_of`` when it resembles one in the list.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import Job, JobSource, JobSourceListing, ListingStatus, new_id, utcnow
from app.services import eligibility
from app.services.job_matching import find_match, same_place, title_key
from app.services.job_service import content_hash, fill_blanks, posting_of, set_canonical_if_free
from app.services.storage import FileStore

OUTCOMES = ("known", "merged", "created", "possible")
ACTED_ON = ("drafting", "applied")


def add_posting(
    session: Session,
    store: FileStore,
    source: JobSource,
    *,
    external_id: str,
    link: str | None,
    canonical_url: str | None,
    values: dict[str, Any],
    seen_on: date,
    snapshot: dict[str, Any],
    parser_version: str,
    snapshots: list[str],
) -> tuple[str, Job]:
    """Returns the outcome (one of ``OUTCOMES``) and the job the posting now belongs to.

    ``values`` holds Job columns (title and company required). Written snapshot paths are
    appended to ``snapshots`` so the caller can delete them if its transaction fails.
    """
    now = utcnow()
    if values.get("available_from_finland") is None:
        values = {**values, "available_from_finland": eligibility.assess(values.get("location"))}
    listing = session.scalar(
        select(JobSourceListing).where(
            JobSourceListing.source_id == source.id, JobSourceListing.external_id == external_id
        )
    )
    if listing is not None:
        listing.last_seen_at = now
        listing.listing_status = ListingStatus.ACTIVE.value
        listing.job.last_seen_at = now
        fill_blanks(listing.job, values)
        return "known", listing.job

    job = session.scalar(select(Job).where(Job.canonical_url == canonical_url)) if canonical_url else None
    verdict, match = ("same", job) if job else find_match(session, posting_of(values, seen_on))
    if job is None and match is not None and any(item.source_id == source.id for item in match.listings):
        # The same site lists both as separate postings (e.g. one per city or region), so they
        # are different jobs. The same place too means a repost (a new posting ID for the same
        # job), which is merged (or flagged when unsure). Otherwise they are only flagged when the user has already applied
        # to (or is writing an application for) the other one.
        if same_place(values.get("location"), match.location) and title_key(values.get("title")) == title_key(match.title):
            pass  # "same" is merged; "possible" is flagged for the user
        elif match.status in ACTED_ON:
            verdict = "possible"
        else:
            verdict, match = "different", None

    if verdict == "same":
        job = match
        fill_blanks(job, values)
        set_canonical_if_free(session, job, canonical_url)
        job.last_seen_at = now
        job.archived_at = None  # listed again, so back in the list
        outcome = "merged"
    else:
        job = Job(
            **values,
            canonical_url=canonical_url,
            content_hash=content_hash(values),
            possible_duplicate_of_id=match.id if match else None,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(job)
        session.flush()
        outcome = "possible" if match else "created"

    listing_id = new_id()
    written = store.write_snapshot(listing_id, {"captured_at": now.isoformat(), **snapshot})
    snapshots.append(written.relative_path)
    session.add(
        JobSourceListing(
            id=listing_id,
            job_id=job.id,
            source_id=source.id,
            external_id=external_id,
            source_url=link,
            source_published_on=values.get("published_on"),
            first_seen_at=now,
            last_seen_at=now,
            listing_status=ListingStatus.ACTIVE.value,
            snapshot_path=written.relative_path,
            snapshot_hash=written.sha256,
            captured_at=now,
            parser_version=parser_version,
        )
    )
    session.flush()
    return outcome, job
