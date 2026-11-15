from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_store
from app.domain import schemas
from app.persistence.models import ApplicationStatus, DraftKind
from app.services import application_service as svc
from app.services.storage import FileStore

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])

SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[FileStore, Depends(get_store)]
AppId = Annotated[str, Path(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")]
JobIdQuery = Annotated[str | None, Query(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")]

ERRORS = {
    404: {"model": schemas.ErrorResponse, "description": "Not found"},
    409: {"model": schemas.ErrorResponse, "description": "Not allowed in the application's current state"},
    422: {"model": schemas.ErrorResponse, "description": "Validation error"},
}
FILE_HEADERS = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}


def _download(data: bytes, filename: str, media_type: str) -> Response:
    ascii_name = filename.encode("ascii", "replace").decode("ascii").replace("?", "_").replace('"', "")
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    return Response(content=data, media_type=media_type, headers={**FILE_HEADERS, "Content-Disposition": disposition})


@router.get("/templates", response_model=list[schemas.TemplateRead], summary="CV and cover letter templates")
def list_templates() -> list[schemas.TemplateRead]:
    return svc.templates()


@router.get("", response_model=schemas.Page[schemas.ApplicationSummary], responses=ERRORS, summary="List applications")
def list_applications(
    session: SessionDep,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    job_id: JobIdQuery = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.Page[schemas.ApplicationSummary]:
    return svc.list_applications(session, status_filter, job_id, limit, offset)


@router.post(
    "",
    response_model=schemas.ApplicationRead,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    summary="Start an application for a job",
    description=(
        "Creates a CV (built from verified facts with a template, or an uploaded CV sent unchanged) and, "
        "optionally, a cover letter draft. 409 `no_verified_facts` when nothing is verified yet; 409 "
        "`application_exists` when the job already has one in progress."
    ),
)
def create_application(data: schemas.ApplicationCreate, session: SessionDep) -> schemas.ApplicationRead:
    return svc.to_read(session, svc.create(session, data))


@router.get("/{application_id}", response_model=schemas.ApplicationRead, responses=ERRORS, summary="Get an application")
def get_application(application_id: AppId, session: SessionDep) -> schemas.ApplicationRead:
    return svc.to_read(session, svc.get(session, application_id))


@router.patch(
    "/{application_id}", response_model=schemas.ApplicationRead, responses=ERRORS, summary="Include or leave out the cover letter; notes"
)
def update_application(application_id: AppId, data: schemas.ApplicationUpdate, session: SessionDep) -> schemas.ApplicationRead:
    return svc.to_read(session, svc.update(session, application_id, data))


@router.delete(
    "/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORS,
    summary="Delete an application that was never sent (requires confirm=true)",
)
def delete_application(application_id: AppId, session: SessionDep, confirm: bool = False) -> Response:
    svc.delete(session, application_id, confirm)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Drafts ----------


@router.put(
    "/{application_id}/drafts/{kind}",
    response_model=schemas.DraftRead,
    responses=ERRORS,
    summary="Save an edited draft, or choose an uploaded CV instead",
    description="Editing an approved version creates a new draft version. The result includes the claim check `issues`.",
)
def edit_draft(application_id: AppId, kind: DraftKind, data: schemas.DraftUpdate, session: SessionDep) -> schemas.DraftRead:
    draft = svc.edit(session, application_id, kind, data)
    return svc.draft_read(session, svc.get(session, application_id), draft)


@router.post(
    "/{application_id}/drafts/{kind}/regenerate",
    response_model=schemas.DraftRead,
    responses=ERRORS,
    summary="Build a new version from verified facts, optionally with another template",
)
def regenerate_draft(
    application_id: AppId, kind: DraftKind, data: schemas.DraftRegenerate, session: SessionDep
) -> schemas.DraftRead:
    draft = svc.regenerate(session, application_id, kind, data)
    return svc.draft_read(session, svc.get(session, application_id), draft)


@router.post(
    "/{application_id}/drafts/{kind}/approve",
    response_model=schemas.DraftRead,
    responses=ERRORS,
    summary="Approve the current version",
    description=(
        "422 `draft_has_errors` (e.g. a [placeholder] left, an unknown email address); 409 "
        "`warnings_not_acknowledged` when statements lack a verified fact and `acknowledge_warnings` is false. "
        "`details.issues` lists them."
    ),
)
def approve_draft(application_id: AppId, kind: DraftKind, data: schemas.DraftApprove, session: SessionDep) -> schemas.DraftRead:
    draft = svc.approve(session, application_id, kind, data)
    return svc.draft_read(session, svc.get(session, application_id), draft)


@router.post(
    "/{application_id}/drafts/{kind}/polish",
    response_model=schemas.PolishResult,
    responses={**ERRORS, 502: {"model": schemas.ErrorResponse, "description": "Local model error"}},
    summary="Suggest nicer wording with the local AI model (not saved)",
    description="Off unless Ollama runs locally (409 `ai_unavailable`). The suggestion is claim-checked; "
                "save it with PUT .../drafts/{kind} if you want it.",
)
def polish_draft(application_id: AppId, kind: DraftKind, request: Request, session: SessionDep) -> schemas.PolishResult:
    suggestion, issues = svc.polish(session, request.app.state.llm, application_id, kind)
    return schemas.PolishResult(suggestion=suggestion, issues=[svc._issue(i) for i in issues])


@router.get(
    "/{application_id}/drafts/{kind}/export",
    response_class=Response,
    responses={**ERRORS, 200: {"description": "The draft as a file", "content": {"application/octet-stream": {}}}},
    summary="Download the current version as PDF, Word, Markdown or text",
    description="An uploaded CV is always returned as the original file. Unapproved versions are named '(draft)'.",
)
def export_draft(
    application_id: AppId,
    kind: DraftKind,
    session: SessionDep,
    store: StoreDep,
    format: Literal["pdf", "docx", "md", "txt"] = "pdf",  # noqa: A002
) -> Response:
    application = svc.get(session, application_id)
    draft = svc.current(application, kind)
    if draft is None:
        from app.core.errors import not_found

        raise not_found("draft")
    data, filename, media = svc.render(session, store, application, draft, format)
    return _download(data, filename, media)


# ---------- Sending (by the user) ----------


@router.get(
    "/{application_id}/package",
    response_model=schemas.PackageRead,
    responses=ERRORS,
    summary="What to send, and where: the final review before the user sends it",
)
def get_package(application_id: AppId, session: SessionDep, store: StoreDep) -> schemas.PackageRead:
    return svc.package(session, store, application_id)


@router.get(
    "/{application_id}/package.zip",
    response_class=Response,
    responses={**ERRORS, 200: {"description": "Approved files (PDF and Word) and a README", "content": {"application/zip": {}}}},
    summary="Download the approved package",
)
def download_package(application_id: AppId, session: SessionDep, store: StoreDep) -> Response:
    data, filename = svc.package_zip(session, store, application_id)
    return _download(data, filename, "application/zip")


@router.get(
    "/{application_id}/email.eml",
    response_class=Response,
    responses={**ERRORS, 200: {"description": "Unsent email draft with the files attached", "content": {"message/rfc822": {}}}},
    summary="Download an unsent email draft to open in your mail program",
    description=(
        "Nothing is sent. `To` is filled only when the posting itself states exactly one email address. "
        "Open the file, check it, and send it yourself."
    ),
)
def download_email(application_id: AppId, session: SessionDep, store: StoreDep) -> Response:
    data, filename = svc.email_draft(session, store, application_id)
    return _download(data, filename, "message/rfc822")


@router.post(
    "/{application_id}/gmail-draft",
    response_model=schemas.GmailDraftResult,
    responses={**ERRORS, 502: {"model": schemas.ErrorResponse, "description": "Gmail error"}},
    summary="Put the application email in your Gmail Drafts (nothing is sent)",
)
def gmail_draft(application_id: AppId, request: Request, session: SessionDep, store: StoreDep) -> schemas.GmailDraftResult:
    draft_id = svc.gmail_draft(session, store, request.app.state.integrations, application_id)
    return schemas.GmailDraftResult(draft_id=draft_id, open_url="https://mail.google.com/mail/u/0/#drafts")


@router.post(
    "/{application_id}/send-email",
    response_model=schemas.ApplicationRead,
    responses={**ERRORS, 502: {"model": schemas.ErrorResponse, "description": "Gmail error (not retried)"}},
    summary="Send the application from your Gmail after your explicit approval",
    description=(
        "Needs `confirm: true`, the `package_hash` you reviewed and the recipient. On success the application "
        "is recorded as sent by email. A failure is never retried automatically."
    ),
)
def send_email(application_id: AppId, data: schemas.EmailSend, request: Request, session: SessionDep,
               store: StoreDep) -> schemas.ApplicationRead:
    return svc.to_read(session, svc.send_email(session, store, request.app.state.integrations, application_id, data))


@router.post(
    "/{application_id}/submission",
    response_model=schemas.ApplicationRead,
    responses=ERRORS,
    summary="Record that you sent the application",
    description=(
        "DuuniScript never submits. Call this after you sent it yourself, with the `package_hash` you reviewed. "
        "409 `package_changed` if the documents changed since."
    ),
)
def record_submission(application_id: AppId, data: schemas.SubmissionRecord, session: SessionDep) -> schemas.ApplicationRead:
    return svc.to_read(session, svc.record_submission(session, application_id, data))


@router.put(
    "/{application_id}/outcome",
    response_model=schemas.ApplicationRead,
    responses=ERRORS,
    summary="Record what happened after sending (interview, rejected, offer…)",
    description="Only for applications recorded as sent (409 `application_not_sent`). Null clears it.",
)
def record_outcome(application_id: AppId, data: schemas.OutcomeUpdate, session: SessionDep) -> schemas.ApplicationRead:
    return svc.to_read(session, svc.record_outcome(session, application_id, data))


@router.post("/{application_id}/withdraw", response_model=schemas.ApplicationRead, responses=ERRORS, summary="Withdraw an application")
def withdraw_application(application_id: AppId, session: SessionDep) -> schemas.ApplicationRead:
    return svc.to_read(session, svc.withdraw(session, application_id))


@router.get(
    "/{application_id}/events",
    response_model=list[schemas.ApplicationEventRead],
    responses=ERRORS,
    summary="Approvals and submission history",
)
def list_events(application_id: AppId, session: SessionDep) -> list[schemas.ApplicationEventRead]:
    return [schemas.ApplicationEventRead.model_validate(e) for e in svc.events(session, application_id)]
