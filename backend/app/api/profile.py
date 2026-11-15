from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_store
from app.domain import schemas
from app.persistence.models import FactCategory, VerificationStatus
from app.services import profile_service as svc
from app.services.storage import FileStore

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])

SessionDep = Annotated[Session, Depends(get_session)]
FactId = Annotated[str, Path(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")]

ERRORS = {
    404: {"model": schemas.ErrorResponse, "description": "Not found"},
    422: {"model": schemas.ErrorResponse, "description": "Validation error"},
}


# ---------- Profile ----------


@router.get("", response_model=schemas.ProfileRead, responses=ERRORS, summary="Get the local profile")
def get_profile(session: SessionDep) -> schemas.ProfileRead:
    return schemas.ProfileRead.model_validate(svc.require_profile(session))


@router.put(
    "",
    response_model=schemas.ProfileRead,
    responses={**ERRORS, 201: {"model": schemas.ProfileRead, "description": "Profile created"}},
    summary="Create or replace the local profile",
)
def put_profile(data: schemas.ProfileUpsert, session: SessionDep, response: Response) -> schemas.ProfileRead:
    profile, created = svc.upsert_profile(session, data)
    if created:
        response.status_code = status.HTTP_201_CREATED
    return schemas.ProfileRead.model_validate(profile)


@router.delete(
    "",
    response_model=schemas.ProfileDeleteResult,
    responses={**ERRORS, 409: {"model": schemas.ErrorResponse, "description": "Confirmation required"}},
    summary="Permanently delete the profile and its facts, evidence and documents",
    description="Without `confirm=true` this returns 409 with the number of dependent records.",
)
def delete_profile(
    session: SessionDep, store: Annotated[FileStore, Depends(get_store)], confirm: bool = False
) -> schemas.ProfileDeleteResult:
    return svc.delete_profile(session, confirm, store)


# ---------- Facts ----------


@router.get("/facts", response_model=schemas.Page[schemas.FactRead], responses=ERRORS, summary="List profile facts")
def list_facts(
    session: SessionDep,
    category: FactCategory | None = None,
    verification_status: VerificationStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.Page[schemas.FactRead]:
    return svc.list_facts(session, category, verification_status, limit, offset)


@router.post(
    "/facts",
    response_model=schemas.FactRead,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    summary="Create a fact (always starts unverified)",
)
def create_fact(data: schemas.FactCreate, session: SessionDep) -> schemas.FactRead:
    return svc.fact_read(session, svc.create_fact(session, data))


@router.get("/facts/{fact_id}", response_model=schemas.FactRead, responses=ERRORS, summary="Get a fact")
def get_fact(fact_id: FactId, session: SessionDep) -> schemas.FactRead:
    return svc.fact_read(session, svc.get_fact(session, fact_id))


@router.patch(
    "/facts/{fact_id}",
    response_model=schemas.FactRead,
    responses=ERRORS,
    summary="Edit a fact or change its verification status",
    description=(
        "Editing the content of a verified fact resets it to `unverified` unless the same "
        "request sets `verification_status` to `verified`."
    ),
)
def update_fact(fact_id: FactId, data: schemas.FactUpdate, session: SessionDep) -> schemas.FactRead:
    return svc.fact_read(session, svc.update_fact(session, fact_id, data))


@router.delete(
    "/facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS, summary="Delete a fact"
)
def delete_fact(fact_id: FactId, session: SessionDep) -> Response:
    svc.delete_fact(session, fact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Evidence ----------


@router.get(
    "/facts/{fact_id}/evidence",
    response_model=list[schemas.EvidenceRead],
    responses=ERRORS,
    summary="List evidence for a fact",
)
def list_evidence(fact_id: FactId, session: SessionDep) -> list[schemas.EvidenceRead]:
    return [schemas.EvidenceRead.model_validate(e) for e in svc.list_evidence(session, fact_id)]


@router.post(
    "/facts/{fact_id}/evidence",
    response_model=schemas.EvidenceRead,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    summary="Attach evidence to a fact (does not verify the fact)",
)
def add_evidence(fact_id: FactId, data: schemas.EvidenceCreate, session: SessionDep) -> schemas.EvidenceRead:
    return schemas.EvidenceRead.model_validate(svc.add_evidence(session, fact_id, data))


# ---------- Facts from documents ----------


@router.post(
    "/facts/import",
    response_model=schemas.FactImportResult,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    summary="Save chosen fact suggestions from a document",
    description=(
        "Each item becomes an unverified fact with the document as evidence (the excerpt it was read "
        "from). Items identical to an existing fact are skipped."
    ),
)
def import_facts(data: schemas.FactImportRequest, session: SessionDep) -> schemas.FactImportResult:
    from app.services import fact_import_service

    return fact_import_service.import_facts(session, data)


@router.post(
    "/facts/verify",
    response_model=schemas.FactVerifyResult,
    responses=ERRORS,
    summary="Mark several facts as verified (the user confirmed each is true)",
)
def verify_facts(data: schemas.FactVerifyRequest, session: SessionDep) -> schemas.FactVerifyResult:
    from app.services import fact_import_service

    return fact_import_service.verify_facts(session, data)
