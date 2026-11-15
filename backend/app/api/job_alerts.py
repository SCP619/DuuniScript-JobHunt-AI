from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.adapters.job_sources.email_alerts import MAX_EMAIL_BYTES
from app.api.deps import get_session, get_store
from app.core.errors import AppError
from app.domain import schemas
from app.services import alert_service
from app.services.storage import FileStore

router = APIRouter(tags=["job alerts"])

SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[FileStore, Depends(get_store)]
ERRORS = {
    409: {"model": schemas.ErrorResponse, "description": "Not set up yet, or a check is already running"},
    502: {"model": schemas.ErrorResponse, "description": "The mailbox could not be read (details.reason)"},
}
MAX_FILES = 50


@router.get(
    "/api/v1/job-alerts",
    response_model=schemas.JobAlertStatus,
    summary="Job alert email status",
    description="Whether the alert mailbox is set up, when it was last checked, and what each site has sent.",
)
def get_status(request: Request, session: SessionDep) -> schemas.JobAlertStatus:
    settings = request.app.state.settings
    configured = request.app.state.mailbox_factory() is not None
    return alert_service.status(session, settings, configured)


@router.post(
    "/api/v1/job-alerts/sync",
    response_model=schemas.AlertSyncResult,
    responses=ERRORS,
    summary="Check the alert mailbox now",
    description=(
        "Reads new job alert emails from the configured mailbox label (read-only) and adds their jobs. "
        "Jobs already in the list are matched instead of added twice."
    ),
)
def sync_now(request: Request, session: SessionDep, store: StoreDep) -> schemas.AlertSyncResult:
    mailbox = request.app.state.mailbox_factory()
    return alert_service.sync_mailbox(session, store, mailbox, request.app.state.settings)


@router.post(
    "/api/v1/job-alerts/emails",
    response_model=schemas.AlertSyncResult,
    responses={422: {"model": schemas.ErrorResponse, "description": "Not an email file, or too large"}},
    summary="Add jobs from saved alert emails (.eml)",
    description="For alert emails saved from the mail program (Gmail: More > Download message). Works without mailbox access.",
)
async def upload_emails(
    session: SessionDep,
    store: StoreDep,
    files: Annotated[list[UploadFile], File(description="One or more .eml files")],
) -> schemas.AlertSyncResult:
    if len(files) > MAX_FILES:
        raise AppError(422, "too_many_files", f"Upload at most {MAX_FILES} emails at a time.")
    report = schemas.AlertSyncResult()
    for upload in files:
        if not (upload.filename or "").lower().endswith(".eml"):
            raise AppError(422, "unsupported_file_type", "Only .eml email files can be added here.")
        raw = await upload.read(MAX_EMAIL_BYTES + 1)
        if len(raw) > MAX_EMAIL_BYTES:
            raise AppError(422, "file_too_large", "An email file is larger than 5 MB.")
        alert_service.ingest_email(session, store, raw, report)
    return report
