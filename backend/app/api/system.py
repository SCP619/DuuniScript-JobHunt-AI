from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.errors import AppError
from app.domain import schemas
from app.services import backup_service, dashboard_service, notification_service

router = APIRouter(tags=["system"])

SessionDep = Annotated[Session, Depends(get_session)]
NotificationId = Annotated[str, Path(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")]
BackupName = Annotated[str, Path(max_length=80, pattern=r"^DuuniScript-backup-\d{8}-\d{6}(?:-\d+)?\.zip$")]
ERRORS = {
    404: {"model": schemas.ErrorResponse, "description": "Not found"},
    409: {"model": schemas.ErrorResponse, "description": "Not allowed now"},
}


def _read(info: backup_service.BackupInfo) -> schemas.BackupRead:
    return schemas.BackupRead(name=info.name, size_bytes=info.size_bytes, created_at=info.created_at)


@router.get("/api/v1/dashboard", response_model=schemas.DashboardSummary, summary="Home dashboard summary")
def dashboard(request: Request, session: SessionDep) -> schemas.DashboardSummary:
    return dashboard_service.summary(session, request.app.state.settings)


@router.get("/api/v1/notifications", response_model=schemas.NotificationList, summary="Notifications, unread first")
def list_notifications(session: SessionDep, include_dismissed: bool = False, limit: int = 50) -> schemas.NotificationList:
    items, unread = notification_service.list_notifications(session, include_dismissed, max(1, min(limit, 200)))
    return schemas.NotificationList(unread=unread, items=[schemas.NotificationRead.model_validate(n) for n in items])


@router.post("/api/v1/notifications/read-all", summary="Mark all notifications read")
def read_all_notifications(session: SessionDep) -> dict:
    return {"marked": notification_service.mark_all_read(session)}


@router.post("/api/v1/notifications/{notification_id}/read", response_model=schemas.NotificationRead, responses=ERRORS,
             summary="Mark a notification read")
def read_notification(notification_id: NotificationId, session: SessionDep) -> schemas.NotificationRead:
    return schemas.NotificationRead.model_validate(notification_service.mark_read(session, notification_id))


@router.post("/api/v1/notifications/{notification_id}/dismiss", response_model=schemas.NotificationRead,
             responses=ERRORS, summary="Dismiss a notification (it will not come back)")
def dismiss_notification(notification_id: NotificationId, session: SessionDep) -> schemas.NotificationRead:
    return schemas.NotificationRead.model_validate(notification_service.dismiss(session, notification_id))


@router.get("/api/v1/ai", response_model=schemas.AiStatus, summary="Is the optional local AI available?")
def ai_status(request: Request, session: SessionDep) -> schemas.AiStatus:
    from app.services import rag_service

    llm = request.app.state.llm
    state = llm.status()
    rag = rag_service.status(session, llm)
    return schemas.AiStatus(enabled=state.enabled, model=state.model, reachable=state.reachable, message=state.message,
                            embedding_model=rag["model"], embeddings_reachable=rag["available"],
                            facts_indexed=rag["facts_indexed"], jobs_indexed=rag["jobs_indexed"])


@router.post("/api/v1/ai/index", response_model=schemas.AiIndexResult,
             summary="Update the local search index (verified facts and jobs) now")
def ai_index(request: Request, session: SessionDep) -> schemas.AiIndexResult:
    from app.services import rag_service

    return schemas.AiIndexResult(**rag_service.index(session, request.app.state.llm))


@router.get("/api/v1/backups", response_model=schemas.BackupsStatus, summary="List backups")
def list_backups(request: Request) -> schemas.BackupsStatus:
    settings = request.app.state.settings
    return schemas.BackupsStatus(
        interval_hours=settings.backup_interval_hours,
        keep=settings.backup_keep,
        backups=[_read(b) for b in backup_service.list_backups(settings)],
    )


@router.post(
    "/api/v1/backups",
    response_model=schemas.BackupRead,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    summary="Make a backup now (database, documents and snapshots)",
    description="Stored in the private data folder; older backups beyond the kept number are removed.",
)
def create_backup(request: Request) -> schemas.BackupRead:
    return _read(backup_service.create(request.app.state.settings))


@router.get(
    "/api/v1/backups/{name}",
    response_class=FileResponse,
    responses={**ERRORS, 200: {"description": "The backup zip", "content": {"application/zip": {}}}},
    summary="Download a backup (contains personal data)",
)
def download_backup(name: BackupName, request: Request) -> FileResponse:
    path = backup_service.path_of(request.app.state.settings, name)
    return FileResponse(
        path, media_type="application/zip", filename=name, content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )


@router.delete(
    "/api/v1/backups/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORS,
    summary="Delete a backup (requires confirm=true)",
)
def delete_backup(name: BackupName, request: Request, confirm: bool = False) -> Response:
    if not confirm:
        raise AppError(409, "confirmation_required", "Deleting a backup cannot be undone. Repeat with confirm=true.")
    backup_service.delete(request.app.state.settings, name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
