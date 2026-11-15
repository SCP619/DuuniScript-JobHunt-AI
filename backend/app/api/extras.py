from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.errors import AppError, not_found
from app.domain import schemas
from app.persistence.models import CvProfile, DraftKind, utcnow
from app.services import application_service as apps
from app.services import form_answers, stats_service

router = APIRouter(tags=["applications"])
SessionDep = Annotated[Session, Depends(get_session)]
Id = Annotated[str, Path(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")]
ERRORS = {404: {"model": schemas.ErrorResponse, "description": "Not found"},
          409: {"model": schemas.ErrorResponse, "description": "Not allowed now"},
          422: {"model": schemas.ErrorResponse, "description": "Validation error"}}


# ---------- Form answers ----------


@router.get("/api/v1/applications/{application_id}/form-answers", response_model=list[schemas.FormAnswerRead],
            responses=ERRORS, summary="Answers to common application-form questions, ready to copy")
def get_form_answers(application_id: Id, session: SessionDep) -> list[schemas.FormAnswerRead]:
    application = apps.get(session, application_id)
    person, facts, _ = apps._views(session, application)
    job = apps._job(session, application)
    return [schemas.FormAnswerRead(**a.__dict__) for a in form_answers.answers(session, application, person, facts, job)]


@router.put("/api/v1/form-answers/{key}", status_code=204, responses=ERRORS,
            summary="Save your own answer (availability, salary, notice_period, references, relocation, why_us:<application id>)")
def put_saved_answer(key: Annotated[str, Path(max_length=60)], data: schemas.SavedAnswerWrite, session: SessionDep) -> Response:
    form_answers.save(session, key, data.answer)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- AI-written fit paragraphs ----------


@router.post("/api/v1/applications/{application_id}/drafts/cover_letter/ai-write", response_model=schemas.AiFitResult,
             responses={**ERRORS, 502: {"model": schemas.ErrorResponse, "description": "Local model error"}},
             summary="Let the local AI write the 'how I fit' paragraphs from your most relevant verified facts (not saved)")
def ai_write(application_id: Id, request: Request, session: SessionDep) -> schemas.AiFitResult:
    suggestion, issues, fact_ids = apps.ai_fit(session, request.app.state.llm, application_id)
    return schemas.AiFitResult(suggestion=suggestion, issues=[apps._issue(i) for i in issues], fact_ids=fact_ids)


# ---------- CV profiles ----------


def _check_template(template: str | None) -> None:
    if template:
        apps._require_template(DraftKind.CV, template)


@router.get("/api/v1/cv-profiles", response_model=list[schemas.CvProfileRead], summary="CV profiles")
def list_profiles(session: SessionDep) -> list[schemas.CvProfileRead]:
    return [schemas.CvProfileRead.model_validate(p) for p in session.scalars(select(CvProfile).order_by(CvProfile.name))]


@router.post("/api/v1/cv-profiles", response_model=schemas.CvProfileRead, status_code=201, responses=ERRORS,
             summary="Create a CV profile")
def create_profile(data: schemas.CvProfileWrite, session: SessionDep) -> schemas.CvProfileRead:
    _check_template(data.cv_template)
    if session.scalar(select(CvProfile).where(CvProfile.name == data.name)):
        raise AppError(409, "cv_profile_exists", "A CV profile with this name exists.")
    profile = CvProfile(**data.model_dump())
    session.add(profile)
    session.commit()
    return schemas.CvProfileRead.model_validate(profile)


@router.put("/api/v1/cv-profiles/{profile_id}", response_model=schemas.CvProfileRead, responses=ERRORS,
            summary="Change a CV profile")
def update_profile(profile_id: Id, data: schemas.CvProfileWrite, session: SessionDep) -> schemas.CvProfileRead:
    profile = session.get(CvProfile, profile_id)
    if profile is None:
        raise not_found("cv_profile")
    _check_template(data.cv_template)
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    profile.updated_at = utcnow()
    session.commit()
    return schemas.CvProfileRead.model_validate(profile)


@router.delete("/api/v1/cv-profiles/{profile_id}", status_code=204, responses=ERRORS, summary="Delete a CV profile")
def delete_profile(profile_id: Id, session: SessionDep) -> Response:
    profile = session.get(CvProfile, profile_id)
    if profile is None:
        raise not_found("cv_profile")
    session.delete(profile)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Statistics ----------


@router.get("/api/v1/stats/outcomes", response_model=schemas.OutcomeStats, summary="What leads to replies and interviews")
def outcome_stats(session: SessionDep) -> schemas.OutcomeStats:
    data = stats_service.outcomes(session)
    data.pop("_withdrawn", None)
    return schemas.OutcomeStats(**data)
