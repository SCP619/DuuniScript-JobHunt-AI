"""Profile, fact and evidence business rules.

Rules:
- There is a single local profile.
- New facts and evidence start ``unverified``. Only an explicit user action verifies them.
- Changing the content of a verified fact resets it to ``unverified`` unless the same
  request explicitly re-verifies it.
- Profile deletion requires explicit confirmation and reports dependent records.
- Every change is audited without recording personal values.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.domain import schemas
from app.persistence.models import (
    Document,
    EvidenceSourceType,
    FactCategory,
    ProfileEvidence,
    ProfileFact,
    UserProfile,
    VerificationStatus,
    utcnow,
)
from app.services import audit
from app.services.storage import FileStore

CONTENT_FIELDS = ("category", "subject", "value_text", "valid_from", "valid_until")


# ---------- Profile ----------


def get_profile(session: Session) -> UserProfile | None:
    return session.scalars(select(UserProfile).order_by(UserProfile.created_at).limit(1)).first()


def require_profile(session: Session) -> UserProfile:
    profile = get_profile(session)
    if profile is None:
        raise not_found("profile")
    return profile


def upsert_profile(session: Session, data: schemas.ProfileUpsert) -> tuple[UserProfile, bool]:
    profile = get_profile(session)
    created = profile is None
    values = data.model_dump()
    if profile is None:
        profile = UserProfile(**values)
        session.add(profile)
        session.flush()
        audit.record(session, "profile.created", "user_profile", profile.id)
    else:
        changed = [k for k, v in values.items() if getattr(profile, k) != v]
        for key, value in values.items():
            setattr(profile, key, value)
        if changed:
            profile.updated_at = utcnow()
            audit.record(session, "profile.updated", "user_profile", profile.id, {"fields": sorted(changed)})
    session.commit()
    session.refresh(profile)
    return profile, created


def _fact_ids(profile_id: str):  # noqa: ANN202
    return select(ProfileFact.id).where(ProfileFact.profile_id == profile_id)


def profile_dependents(session: Session, profile_id: str) -> dict[str, int]:
    facts = session.scalar(select(func.count()).select_from(ProfileFact).where(ProfileFact.profile_id == profile_id))
    evidence = session.scalar(
        select(func.count()).select_from(ProfileEvidence).where(ProfileEvidence.fact_id.in_(_fact_ids(profile_id)))
    )
    documents = session.scalar(select(func.count()).select_from(Document).where(Document.profile_id == profile_id))
    return {"facts": int(facts or 0), "evidence": int(evidence or 0), "documents": int(documents or 0)}


def delete_profile(session: Session, confirm: bool, store: FileStore) -> schemas.ProfileDeleteResult:
    from app.services.document_service import file_paths_for_profile

    profile = require_profile(session)
    counts = profile_dependents(session, profile.id)
    if not confirm:
        raise AppError(
            409,
            "confirmation_required",
            "Deleting the profile permanently removes it and all of its facts, evidence and documents "
            "(including the stored files). Repeat the request with confirm=true to proceed.",
            counts,
        )
    profile_id = profile.id
    paths = file_paths_for_profile(session, profile_id)
    # Evidence and applications first: they reference documents with ON DELETE RESTRICT.
    from app.persistence.models import Application

    session.execute(delete(ProfileEvidence).where(ProfileEvidence.fact_id.in_(_fact_ids(profile_id))))
    for application in session.scalars(select(Application).where(Application.profile_id == profile_id)):
        session.delete(application)
    session.flush()
    session.delete(profile)
    audit.record(
        session,
        "profile.deleted",
        "user_profile",
        profile_id,
        {f"deleted_{k}": v for k, v in counts.items()},
    )
    session.commit()
    for path in paths:
        store.delete(path)
    return schemas.ProfileDeleteResult(
        deleted=True,
        deleted_facts=counts["facts"],
        deleted_evidence=counts["evidence"],
        deleted_documents=counts["documents"],
    )


# ---------- Facts ----------


def _evidence_counts(session: Session, fact_ids: list[str]) -> dict[str, int]:
    if not fact_ids:
        return {}
    rows = session.execute(
        select(ProfileEvidence.fact_id, func.count())
        .where(ProfileEvidence.fact_id.in_(fact_ids))
        .group_by(ProfileEvidence.fact_id)
    ).all()
    return {fact_id: count for fact_id, count in rows}


def to_fact_read(fact: ProfileFact, evidence_count: int) -> schemas.FactRead:
    read = schemas.FactRead.model_validate(fact)
    read.evidence_count = evidence_count
    return read


def list_facts(
    session: Session,
    category: FactCategory | None,
    status: VerificationStatus | None,
    limit: int,
    offset: int,
) -> schemas.Page[schemas.FactRead]:
    profile = require_profile(session)
    query = select(ProfileFact).where(ProfileFact.profile_id == profile.id)
    if category:
        query = query.where(ProfileFact.category == category.value)
    if status:
        query = query.where(ProfileFact.verification_status == status.value)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    facts = session.scalars(
        query.order_by(ProfileFact.category, ProfileFact.created_at, ProfileFact.id).limit(limit).offset(offset)
    ).all()
    counts = _evidence_counts(session, [f.id for f in facts])
    return schemas.Page[schemas.FactRead](
        items=[to_fact_read(f, counts.get(f.id, 0)) for f in facts], total=total, limit=limit, offset=offset
    )


def get_fact(session: Session, fact_id: str) -> ProfileFact:
    profile = require_profile(session)
    fact = session.get(ProfileFact, fact_id)
    if fact is None or fact.profile_id != profile.id:
        raise not_found("fact")
    return fact


def fact_read(session: Session, fact: ProfileFact) -> schemas.FactRead:
    return to_fact_read(fact, _evidence_counts(session, [fact.id]).get(fact.id, 0))


def _check_date_range(valid_from, valid_until) -> None:
    if valid_from and valid_until and valid_from > valid_until:
        raise AppError(
            422,
            "invalid_date_range",
            "The end date must be on or after the start date.",
            {"fields": [{"loc": ["body", "valid_until"], "msg": "Must be on or after the start date.", "type": "date_range"}]},
        )


def _field_error(field: str, message: str) -> AppError:
    return AppError(
        422,
        "validation_error",
        message,
        {"fields": [{"loc": ["body", field], "msg": message, "type": "value_error"}]},
    )


def create_fact(session: Session, data: schemas.FactCreate) -> ProfileFact:
    profile = require_profile(session)
    _check_date_range(data.valid_from, data.valid_until)
    fact = ProfileFact(
        profile_id=profile.id,
        category=data.category.value,
        subject=data.subject,
        value_text=data.value_text,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        verification_status=VerificationStatus.UNVERIFIED.value,
    )
    session.add(fact)
    session.flush()
    audit.record(session, "fact.created", "profile_fact", fact.id, {"category": fact.category})
    session.commit()
    session.refresh(fact)
    return fact


def update_fact(session: Session, fact_id: str, data: schemas.FactUpdate) -> ProfileFact:
    fact = get_fact(session, fact_id)
    changes = data.model_dump(exclude_unset=True)
    requested_status = changes.pop("verification_status", None)

    if "category" in changes and changes["category"] is None:
        raise AppError(422, "validation_error", "category cannot be null.")
    for required in ("subject", "value_text"):
        if required in changes and changes[required] is None:
            raise AppError(422, "validation_error", f"{required} cannot be null.")

    _check_date_range(changes.get("valid_from", fact.valid_from), changes.get("valid_until", fact.valid_until))

    changed_fields: list[str] = []
    for key, value in changes.items():
        stored = value.value if isinstance(value, FactCategory) else value
        if getattr(fact, key) != stored:
            setattr(fact, key, stored)
            changed_fields.append(key)

    old_status = fact.verification_status
    new_status = old_status
    if requested_status is not None:
        new_status = VerificationStatus(requested_status).value
    elif changed_fields and old_status == VerificationStatus.VERIFIED.value:
        # Content changed without explicit re-verification: the old verification no longer applies.
        new_status = VerificationStatus.UNVERIFIED.value

    if new_status != old_status or (requested_status == VerificationStatus.VERIFIED and changed_fields):
        fact.verification_status = new_status
        if new_status == VerificationStatus.VERIFIED.value:
            fact.verified_at = utcnow()
        elif new_status in (VerificationStatus.UNVERIFIED.value, VerificationStatus.REJECTED.value):
            fact.verified_at = None
        # ``expired`` keeps the historical verified_at.
        audit.record(
            session,
            "fact.verification_changed",
            "profile_fact",
            fact.id,
            {"from": old_status, "to": new_status, "content_changed": bool(changed_fields)},
        )

    if changed_fields:
        fact.updated_at = utcnow()
        audit.record(session, "fact.updated", "profile_fact", fact.id, {"fields": sorted(changed_fields)})
    elif new_status != old_status:
        fact.updated_at = utcnow()

    session.commit()
    session.refresh(fact)
    return fact


def delete_fact(session: Session, fact_id: str) -> None:
    fact = get_fact(session, fact_id)
    audit.record(session, "fact.deleted", "profile_fact", fact.id, {"category": fact.category})
    session.delete(fact)
    session.commit()


# ---------- Evidence ----------


def list_evidence(session: Session, fact_id: str) -> list[ProfileEvidence]:
    fact = get_fact(session, fact_id)
    return list(
        session.scalars(
            select(ProfileEvidence)
            .where(ProfileEvidence.fact_id == fact.id)
            .order_by(ProfileEvidence.created_at, ProfileEvidence.id)
        )
    )


def add_evidence(session: Session, fact_id: str, data: schemas.EvidenceCreate) -> ProfileEvidence:
    from app.services.document_service import validate_evidence_document

    fact = get_fact(session, fact_id)
    if data.source_type == EvidenceSourceType.DOCUMENT and not data.document_id:
        raise _field_error("document_id", "Choose a document.")
    if data.source_type == EvidenceSourceType.URL and not (data.source_reference or "").lower().startswith(
        ("https://", "http://")
    ):
        raise _field_error("source_reference", "Enter a web address starting with http:// or https://.")
    if data.document_id:
        validate_evidence_document(session, data.document_id)
    evidence = ProfileEvidence(
        fact_id=fact.id,
        source_type=data.source_type.value,
        source_reference=data.source_reference,
        document_id=data.document_id,
        excerpt=data.excerpt,
        verification_status=VerificationStatus.UNVERIFIED.value,
    )
    session.add(evidence)
    session.flush()
    # Adding evidence never changes the fact's verification status.
    audit.record(
        session, "evidence.created", "profile_evidence", evidence.id, {"fact_id": fact.id, "source_type": evidence.source_type}
    )
    session.commit()
    session.refresh(evidence)
    return evidence
