from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_store
from app.domain import schemas
from app.services import feed_service
from app.services.storage import FileStore

router = APIRouter(tags=["job feeds"])

SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[FileStore, Depends(get_store)]
SourceKey = Annotated[str, Path(max_length=50, pattern=r"^[a-z0-9_]+$")]
ERRORS = {
    404: {"model": schemas.ErrorResponse, "description": "No such feed"},
    409: {"model": schemas.ErrorResponse, "description": "The feed is turned off, or a check is already running"},
    429: {"model": schemas.ErrorResponse, "description": "Checked too recently (details.next_allowed_at)"},
    502: {"model": schemas.ErrorResponse, "description": "The feed could not be read (details.reason)"},
}


@router.get(
    "/api/v1/feeds",
    response_model=schemas.FeedsStatus,
    summary="Job feeds and their status",
    description="Official job feeds and public job APIs that DuuniScript reads, how often, and the last result.",
)
def get_status(request: Request, session: SessionDep) -> schemas.FeedsStatus:
    return feed_service.status(session, request.app.state.settings)


@router.post(
    "/api/v1/feeds/sync",
    response_model=list[schemas.FeedSyncResult],
    summary="Check every feed that is due now",
    description="Feeds checked too recently are left out (each site sets its own minimum interval).",
)
def sync_due(request: Request, session: SessionDep, store: StoreDep) -> list[schemas.FeedSyncResult]:
    state = request.app.state
    return feed_service.sync_due(session, store, state.feed_fetcher, state.settings, actor="user")


@router.post(
    "/api/v1/feeds/{key}/sync",
    response_model=schemas.FeedSyncResult,
    responses=ERRORS,
    summary="Check one feed now",
)
def sync_one(key: SourceKey, request: Request, session: SessionDep, store: StoreDep) -> schemas.FeedSyncResult:
    state = request.app.state
    site = feed_service.site_or_404(key)
    return feed_service.sync_feed(session, store, state.feed_fetcher, site, state.settings)


@router.patch(
    "/api/v1/sources/{key}",
    response_model=schemas.SourceRead,
    responses={404: {"model": schemas.ErrorResponse, "description": "No such source"}},
    tags=["sources"],
    summary="Turn a job source on or off",
    description="A turned-off feed is not read, automatically or by request. Jobs already added stay.",
)
def update_source(key: SourceKey, data: schemas.SourceUpdate, session: SessionDep) -> schemas.SourceRead:
    return schemas.SourceRead.model_validate(feed_service.set_enabled(session, key, data.enabled))
