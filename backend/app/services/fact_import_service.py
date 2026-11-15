"""Turn a CV's extracted text into fact suggestions, and save the ones the user picks.

Saved facts always start ``unverified`` and carry the CV as document evidence with the
excerpt they were read from. Verifying is a separate, explicit user action (also in bulk).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain import schemas
from app.persistence.models import (
    EvidenceSourceType,
    ExtractionStatus,
    ProfileEvidence,
    ProfileFact,
    VerificationStatus,
    utcnow,
)
from app.services import audit, cv_facts, document_service, profile_service
from app.services.storage import FileStore


def _existing_keys(session: Session, profile_id: str) -> set[tuple[str, str, str]]:
    rows = session.execute(
        select(ProfileFact.category, ProfileFact.subject, ProfileFact.value_text).where(
            ProfileFact.profile_id == profile_id
        )
    ).all()
    return {cv_facts.fact_key(c, s, v) for c, s, v in rows}


def suggestions(session: Session, store: FileStore, document_id: str) -> schemas.FactSuggestionList:
    document = document_service.get(session, document_id)
    if document.extraction_status != ExtractionStatus.SUCCEEDED.value or not document.extracted_text_path:
        raise AppError(
            409,
            "no_extracted_text",
            "This document has no extracted text to read facts from. Re-run extraction, or add facts by hand.",
        )
    text = store.read_text(document.extracted_text_path)
    existing = _existing_keys(session, document.profile_id)
    items = [
        schemas.FactSuggestion(
            category=s.category,
            subject=s.subject,
            value_text=s.value_text,
            valid_from=s.valid_from,
            valid_until=s.valid_until,
            excerpt=s.excerpt,
            already_in_profile=cv_facts.fact_key(s.category.value, s.subject, s.value_text) in existing,
        )
        for s in cv_facts.suggest_facts(text)
    ]
    return schemas.FactSuggestionList(document_id=document.id, parser_version=cv_facts.PARSER_VERSION, items=items)


def import_facts(session: Session, data: schemas.FactImportRequest) -> schemas.FactImportResult:
    profile = profile_service.require_profile(session)
    document_service.validate_evidence_document(session, data.document_id)
    existing = _existing_keys(session, profile.id)
    created: list[ProfileFact] = []
    skipped = 0
    for item in data.items:
        if item.valid_from and item.valid_until and item.valid_from > item.valid_until:
            raise AppError(422, "invalid_date_range", f"The end date of “{item.subject[:80]}” is before its start date.")
        key = cv_facts.fact_key(item.category.value, item.subject, item.value_text)
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        fact = ProfileFact(
            profile_id=profile.id,
            category=item.category.value,
            subject=item.subject,
            value_text=item.value_text,
            valid_from=item.valid_from,
            valid_until=item.valid_until,
            verification_status=VerificationStatus.UNVERIFIED.value,
        )
        session.add(fact)
        session.flush()
        session.add(
            ProfileEvidence(
                fact_id=fact.id,
                document_id=data.document_id,
                source_type=EvidenceSourceType.DOCUMENT.value,
                excerpt=item.excerpt or item.value_text[:2000],
                verification_status=VerificationStatus.UNVERIFIED.value,
            )
        )
        created.append(fact)
    audit.record(
        session,
        "facts.imported",
        "document",
        data.document_id,
        {"created": len(created), "skipped_existing": skipped, "parser_version": cv_facts.PARSER_VERSION},
    )
    session.commit()
    facts = [profile_service.to_fact_read(f, 1) for f in created]
    return schemas.FactImportResult(created=len(created), skipped_existing=skipped, facts=facts)


def verify_facts(session: Session, data: schemas.FactVerifyRequest) -> schemas.FactVerifyResult:
    """The user confirmed these facts are true. Unknown IDs are refused as a whole."""
    profile = profile_service.require_profile(session)
    ids = list(dict.fromkeys(data.fact_ids))
    facts = list(
        session.scalars(select(ProfileFact).where(ProfileFact.id.in_(ids), ProfileFact.profile_id == profile.id))
    )
    if len(facts) != len(ids):
        raise AppError(404, "fact_not_found", "One or more facts were not found.")
    now = utcnow()
    changed = 0
    for fact in facts:
        if fact.verification_status != VerificationStatus.VERIFIED.value:
            audit.record(
                session,
                "fact.verification_changed",
                "profile_fact",
                fact.id,
                {"from": fact.verification_status, "to": VerificationStatus.VERIFIED.value, "content_changed": False},
            )
            fact.verification_status = VerificationStatus.VERIFIED.value
            fact.verified_at = now
            fact.updated_at = now
            changed += 1
    session.commit()
    order = {fid: i for i, fid in enumerate(ids)}
    facts.sort(key=lambda f: order[f.id])
    reads = [profile_service.fact_read(session, f) for f in facts]
    return schemas.FactVerifyResult(verified=changed, facts=reads)
