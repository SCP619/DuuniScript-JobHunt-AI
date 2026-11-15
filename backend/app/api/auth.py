from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.domain import schemas
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
SessionDep = Annotated[Session, Depends(get_session)]
ERRORS = {
    401: {"model": schemas.ErrorResponse, "description": "Wrong passphrase"},
    409: {"model": schemas.ErrorResponse, "description": "Not allowed now"},
    422: {"model": schemas.ErrorResponse, "description": "Validation error"},
    429: {"model": schemas.ErrorResponse, "description": "Too many attempts"},
}


def bearer(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    return header[7:].strip() if header.lower().startswith("bearer ") else None


@router.get("/status", response_model=schemas.AuthStatus, summary="Is a passphrase set, and is this browser signed in?")
def status(request: Request, session: SessionDep) -> schemas.AuthStatus:
    return schemas.AuthStatus(
        password_set=auth_service.password_set(session),
        signed_in=auth_service.session_for(session, bearer(request)) is not None,
    )


@router.post("/setup", response_model=schemas.AuthToken, responses=ERRORS,
             summary="Create the sign-in passphrase (only when none exists) and sign in")
def setup(data: schemas.PasswordSet, request: Request, session: SessionDep) -> schemas.AuthToken:
    token, expires = auth_service.setup(session, data.password, request.app.state.settings.auth_session_days)
    return schemas.AuthToken(token=token, expires_at=expires)


@router.post("/login", response_model=schemas.AuthToken, responses=ERRORS, summary="Sign in")
def login(data: schemas.PasswordSet, request: Request, session: SessionDep) -> schemas.AuthToken:
    token, expires = auth_service.login(session, data.password, request.app.state.settings.auth_session_days)
    return schemas.AuthToken(token=token, expires_at=expires)


@router.post("/logout", status_code=204, summary="Sign out this browser")
def logout(request: Request, session: SessionDep) -> None:
    auth_service.logout(session, bearer(request))


@router.post("/change", status_code=204, responses=ERRORS,
             summary="Change the passphrase (signs out every other browser)")
def change(data: schemas.PasswordChange, request: Request, session: SessionDep) -> None:
    auth_service.change(session, bearer(request), data.current_password, data.new_password)
