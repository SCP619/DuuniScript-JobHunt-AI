from __future__ import annotations

from fastapi import APIRouter, Request

from app import __version__
from app.domain.schemas import HealthResponse
from app.persistence.db import check_database

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness and database check")
def health(request: Request) -> HealthResponse:
    db_ok = check_database(request.app.state.engine)
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=__version__,
        database="ok" if db_ok else "unavailable",
    )
