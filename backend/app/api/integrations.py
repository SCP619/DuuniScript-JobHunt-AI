from __future__ import annotations

import html
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_store
from app.core.errors import AppError
from app.domain import schemas
from app.services import alert_service, integration_service as svc
from app.services.storage import FileStore

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[FileStore, Depends(get_store)]
ERRORS = {
    409: {"model": schemas.ErrorResponse, "description": "Not set up or not connected"},
    502: {"model": schemas.ErrorResponse, "description": "The provider refused or failed"},
}


def _state(request: Request) -> svc.Integrations:
    return request.app.state.integrations


def _provider_status(session: Session, integrations: svc.Integrations, provider: str, configured: bool) -> schemas.ProviderStatus:
    row = svc._row(session, provider)
    return schemas.ProviderStatus(
        configured=configured,
        connected=svc.connected(session, integrations, provider),
        account=row.account if row else None,
        connected_at=row.connected_at if row else None,
        last_sync_at=row.last_sync_at if row else None,
        last_error=row.last_error if row else None,
    )


@router.get("", response_model=schemas.IntegrationsStatus, summary="Connected accounts")
def status(request: Request, session: SessionDep) -> schemas.IntegrationsStatus:
    integrations = _state(request)
    device = integrations.device
    return schemas.IntegrationsStatus(
        google=_provider_status(session, integrations, svc.GOOGLE, integrations.google_client() is not None),
        microsoft=_provider_status(session, integrations, svc.MICROSOFT, bool(integrations.settings.ms_client_id)),
        microsoft_sign_in=schemas.DeviceSignInRead(
            status=device.status, user_code=device.user_code, verification_uri=device.verification_uri,
            expires_at=device.expires_at, message=device.message,
        ),
    )


@router.post("/google/connect", response_model=schemas.ConnectUrl, responses=ERRORS,
             summary="Start connecting Gmail: open the returned URL in a new tab")
def google_connect(request: Request) -> schemas.ConnectUrl:
    return schemas.ConnectUrl(url=svc.google_start(_state(request)))


@router.get("/google/callback", response_class=HTMLResponse, include_in_schema=False)
def google_callback(request: Request, session: SessionDep, state: str | None = None, code: str | None = None,
                    error: str | None = None) -> HTMLResponse:
    ok, message = svc.google_finish(session, _state(request), state, code, error)
    page = (
        "<!doctype html><meta charset='utf-8'><title>DuuniScript</title>"
        "<body style='font-family:system-ui;max-width:32rem;margin:4rem auto'>"
        f"<h1>{'Connected' if ok else 'Not connected'}</h1><p>{html.escape(message)}</p></body>"
    )
    return HTMLResponse(page, status_code=200 if ok else 400, headers={"Cache-Control": "no-store"})


@router.post("/microsoft/connect", response_model=schemas.DeviceSignInRead, responses=ERRORS,
             summary="Start connecting a Microsoft 365 mailbox (e.g. UTU)",
             description="Show `user_code` and open `verification_uri`; the user signs in there, including 2FA. "
                         "Poll `GET /api/v1/integrations` until `microsoft_sign_in.status` is connected or failed.")
def microsoft_connect(request: Request) -> schemas.DeviceSignInRead:
    sign_in = svc.microsoft_start(_state(request), request.app.state.session_factory)
    return schemas.DeviceSignInRead(status=sign_in.status, user_code=sign_in.user_code,
                                    verification_uri=sign_in.verification_uri, expires_at=sign_in.expires_at,
                                    message=sign_in.message)


@router.post("/{provider}/sync", response_model=schemas.AlertSyncResult, responses=ERRORS,
             summary="Read new job alert emails from a connected mailbox now")
def sync(provider: Literal["google", "microsoft"], request: Request, session: SessionDep,
         store: StoreDep) -> schemas.AlertSyncResult:
    integrations = _state(request)
    if not svc.connected(session, integrations, provider):
        raise AppError(409, "not_connected", "Connect this account first.")
    mailbox = integrations.gmail_mailbox() if provider == svc.GOOGLE else integrations.graph_mailbox()
    source = alert_service.MAILBOX_SOURCE if provider == svc.GOOGLE else svc.MICROSOFT_SOURCE
    try:
        result = alert_service.sync_mailbox(session, store, mailbox, request.app.state.settings, source_key=source)
    except AppError as exc:
        svc.record_sync(session, provider, exc.message)
        raise
    svc.record_sync(session, provider, None)
    return result


@router.delete("/{provider}", status_code=204, summary="Disconnect and delete the stored sign-in")
def disconnect(provider: Literal["google", "microsoft"], request: Request, session: SessionDep) -> None:
    svc.disconnect(session, _state(request), provider)
