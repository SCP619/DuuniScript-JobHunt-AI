from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Path, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_store
from app.domain import schemas
from app.persistence.models import Availability, EmploymentType, JobStatus, WorkMode
from app.services import job_service as svc
from app.services.storage import FileStore

router = APIRouter(tags=["jobs"])

SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[FileStore, Depends(get_store)]
JobId = Annotated[str, Path(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")]

ERRORS = {
    404: {"model": schemas.ErrorResponse, "description": "Not found"},
    422: {"model": schemas.ErrorResponse, "description": "Validation error"},
}
DUPLICATE = {409: {"model": schemas.ErrorResponse, "description": "Job already exists (details.job_id)"}}


@router.post(
    "/api/v1/jobs",
    response_model=schemas.JobRead,
    status_code=status.HTTP_201_CREATED,
    responses={**ERRORS, **DUPLICATE},
    summary="Add a job manually",
    description="Use when a page cannot be imported. Nothing is fetched; `url` is kept for reference and duplicate checks.",
)
def create_job(data: schemas.JobCreate, session: SessionDep, store: StoreDep) -> schemas.JobRead:
    job = svc.create_manual(session, data)
    if data.screenshot_draft_id:
        from app.services import job_attachments

        job_attachments.attach_pending(session, store, data.screenshot_draft_id, job.id)
    return svc.to_read(job)


@router.post(
    "/api/v1/jobs/import",
    response_model=schemas.JobRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        **ERRORS,
        **DUPLICATE,
        403: {"model": schemas.ErrorResponse, "description": "URL import disabled"},
        200: {"model": schemas.JobRead, "description": "Same posting as a job already in the list; added to that job"},
        502: {"model": schemas.ErrorResponse, "description": "Page could not be fetched (details.reason)"},
        504: {"model": schemas.ErrorResponse, "description": "Page timed out"},
    },
    summary="Import a job from a URL (single user-initiated fetch)",
    description=(
        "Fetches the page once and reads its schema.org JobPosting structured data. "
        "If the page has none, returns 422 `no_structured_job_data`; add the job manually instead. "
        "Private and local network addresses are refused. If the posting is already in the list "
        "(same company and title, e.g. from a job alert email), it is added to that job and 200 is returned."
    ),
)
def import_job(
    data: schemas.JobImportRequest, request: Request, response: Response, session: SessionDep, store: StoreDep
) -> schemas.JobRead:
    settings = request.app.state.settings
    job, created = svc.import_from_url(session, store, request.app.state.fetcher, data.url, settings.url_import_enabled)
    if not created:
        response.status_code = status.HTTP_200_OK
    return svc.to_read(job)


@router.post(
    "/api/v1/jobs/from-screenshots",
    response_model=schemas.ScreenshotDraftRead,
    responses={**ERRORS, 409: {"model": schemas.ErrorResponse, "description": "Text recognition unavailable"},
               413: {"model": schemas.ErrorResponse, "description": "Too large"},
               415: {"model": schemas.ErrorResponse, "description": "Not an image"}},
    summary="Read a job posting from screenshots (nothing is saved)",
    description=(
        "Up to 10 PNG/JPEG screenshots of one posting, in order. Returns the form values to check, the text read "
        "and warnings. Save with POST /api/v1/jobs and `added_from: \"screenshots\"` (tagged 'Apply yourself')."
    ),
)
def read_screenshots(request: Request, files: Annotated[list[UploadFile], File(description="Screenshots, in order")]) -> schemas.ScreenshotDraftRead:
    from app.services import screenshot_import

    from app.services import job_attachments

    payload = [(f.filename or "screenshot", f.file.read(screenshot_import.MAX_FILE_BYTES + 1)) for f in files[: screenshot_import.MAX_FILES + 1]]
    draft = screenshot_import.read(payload, request.app.state.llm)
    # Kept until the job is saved (then attached to it) or for one day.
    draft_id = job_attachments.keep_pending(request.app.state.store, payload)
    return schemas.ScreenshotDraftRead(fields={**draft.fields, "screenshot_draft_id": draft_id}, text=draft.text,
                                       method=draft.method, warnings=draft.warnings, images=draft.images,
                                       screenshot_draft_id=draft_id)


@router.post(
    "/api/v1/jobs/from-text",
    response_model=schemas.ScreenshotDraftRead,
    responses=ERRORS,
    summary="Read a job posting from pasted text (nothing is saved)",
    description="Same as from-screenshots, for text copied from a posting. Save with POST /api/v1/jobs.",
)
def read_pasted_text(data: schemas.PastedPosting, request: Request) -> schemas.ScreenshotDraftRead:
    from app.services import screenshot_import

    draft = screenshot_import.extract(data.text, request.app.state.llm)
    return schemas.ScreenshotDraftRead(fields=draft.fields, text=draft.text, method=draft.method,
                                       warnings=draft.warnings, images=0)


@router.get("/api/v1/jobs/{job_id}/attachments", response_model=list[schemas.JobAttachmentRead], responses=ERRORS,
            summary="Screenshots kept with a job")
def list_attachments(job_id: JobId, session: SessionDep) -> list[schemas.JobAttachmentRead]:
    from app.services import job_attachments

    svc.get_job(session, job_id)
    return [schemas.JobAttachmentRead.model_validate(a) for a in job_attachments.list_for(session, job_id)]


@router.get("/api/v1/jobs/{job_id}/attachments/{attachment_id}", response_class=Response, responses=ERRORS,
            summary="Download a kept screenshot")
def get_attachment(job_id: JobId, attachment_id: JobId, session: SessionDep, store: StoreDep) -> Response:
    from app.services import job_attachments

    data, media = job_attachments.read(session, store, job_id, attachment_id)
    return Response(content=data, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="screenshot-{attachment_id[:8]}.{media.split("/")[-1]}"',
        "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.post("/api/v1/jobs/housekeeping", response_model=schemas.HousekeepingResult,
             summary="Expire jobs whose deadline passed and archive old untouched jobs now")
def run_housekeeping(request: Request, session: SessionDep, store: StoreDep) -> schemas.HousekeepingResult:
    from app.services import housekeeping, job_attachments

    job_attachments.clean_pending(store)
    return schemas.HousekeepingResult(**housekeeping.run(session, request.app.state.settings.job_archive_days))


@router.get(
    "/api/v1/jobs",
    response_model=schemas.Page[schemas.JobSummary],
    responses=ERRORS,
    summary="Search, filter and sort jobs",
    description="Hidden jobs are excluded unless `hidden=true` (only hidden) or `include_hidden=true` (all).",
)
def list_jobs(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=200, description="Text search in title, company and description")] = None,
    company: Annotated[str | None, Query(max_length=200)] = None,
    location: Annotated[str | None, Query(max_length=200)] = None,
    source: Annotated[str | None, Query(max_length=50, description="Source key, e.g. manual or url_import")] = None,
    job_status: Annotated[list[JobStatus] | None, Query(alias="status")] = None,
    employment_type: EmploymentType | None = None,
    work_mode: WorkMode | None = None,
    language: Annotated[
        str | None,
        Query(
            pattern=r"^([A-Za-z]{2,3}|unknown)$",
            description="Posting language: `en`, `fi`, `sv`… (also matches `en-GB`). `unknown` lists jobs with no known language.",
        ),
    ] = None,
    available_from_finland: Annotated[
        list[Availability] | None,
        Query(description="yes / no / unknown; repeat to combine, e.g. yes and unknown."),
    ] = None,
    published_from: date | None = None,
    published_to: date | None = None,
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    hidden: bool = False,
    include_hidden: bool = False,
    include_archived: Annotated[bool, Query(description="Also list jobs archived as old and untouched.")] = False,
    min_match: Annotated[int | None, Query(ge=0, le=100, description="Only jobs with at least this match score.")] = None,
    sort: Literal["newest", "published", "deadline", "company", "title", "match"] = "newest",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.Page[schemas.JobSummary]:
    filters = svc.JobFilters(
        q=q,
        company=company,
        location=location,
        source=source,
        status=job_status,
        employment_type=employment_type,
        work_mode=work_mode,
        language=language,
        available_from_finland=available_from_finland,
        published_from=published_from,
        published_to=published_to,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        hidden=None if include_hidden else hidden,
        min_match=min_match,
        include_archived=include_archived,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return svc.list_jobs(session, filters)


@router.get("/api/v1/jobs/{job_id}", response_model=schemas.JobRead, responses=ERRORS, summary="Get a job")
def get_job(job_id: JobId, session: SessionDep) -> schemas.JobRead:
    from app.services import match_service

    match_service.refresh(session)
    job = svc.get_job(session, job_id)
    return svc.to_read(job, match_service.matches_for(session, [job.id]).get(job.id))


@router.get(
    "/api/v1/jobs/{job_id}/match",
    response_model=schemas.JobMatchRead,
    responses=ERRORS,
    summary="Why this job got its match score",
    description="Computed from verified facts only. A ranking aid, not a judgement of eligibility.",
)
def get_job_match(job_id: JobId, session: SessionDep) -> schemas.JobMatchRead:
    from app.services import match_service

    job = svc.get_job(session, job_id)
    match_service.refresh(session)
    match = match_service.matches_for(session, [job.id])[job.id]
    details = match.details or {}
    return schemas.JobMatchRead(
        job_id=job.id,
        score=match.score,
        scoring_version=match.scoring_version,
        reasons=details.get("reasons", []),
        matched_skills=details.get("matched_skills", []),
        missing_terms=details.get("missing_terms", []),
        blockers=details.get("blockers", []),
        parts=details.get("parts") or {},
        computed_at=match.computed_at,
    )


@router.patch(
    "/api/v1/jobs/{job_id}",
    response_model=schemas.JobRead,
    responses=ERRORS,
    summary="Change status, hide, add notes or correct job details",
)
def update_job(job_id: JobId, data: schemas.JobUpdate, session: SessionDep) -> schemas.JobRead:
    return svc.to_read(svc.update_job(session, job_id, data))


@router.post(
    "/api/v1/jobs/{job_id}/merge",
    response_model=schemas.JobRead,
    responses=ERRORS,
    summary="Merge a duplicate into another job",
    description=(
        "Use when two jobs are the same posting. The job in the path is removed; its listings, missing "
        "details and notes move to `into_job_id`, and the further application status is kept."
    ),
)
def merge_job(job_id: JobId, data: schemas.JobMergeRequest, session: SessionDep) -> schemas.JobRead:
    return svc.to_read(svc.merge_jobs(session, job_id, data.into_job_id))


@router.get(
    "/api/v1/sources",
    response_model=list[schemas.SourceRead],
    tags=["sources"],
    summary="List job sources and their access policy",
)
def list_sources(session: SessionDep) -> list[schemas.SourceRead]:
    return [schemas.SourceRead.model_validate(s) for s in svc.list_sources(session)]
