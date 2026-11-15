"""Document intake, extraction and lifecycle rules (AFD 6, DBD 6).

- Only PDF, DOCX, TXT, Markdown, HTML, PNG and JPEG, verified by content signature. Images
  (and scanned PDFs without a text layer) are read with the Windows OCR engine when available. HTML is only ever
  reduced to text (scripts and styles dropped); it is never rendered, and downloads are
  always sent as attachments with nosniff.
- Originals are stored once, read-only, under internal names; they are never modified.
- The same file (SHA-256) cannot be uploaded twice for a profile.
- Archiving hides a document without deleting it. Permanent deletion needs explicit
  confirmation and is refused while profile evidence still references the document.
"""

from __future__ import annotations

from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.domain import schemas
from app.persistence.models import (
    Document,
    DocumentCategory,
    ExtractionStatus,
    ProfileEvidence,
    new_id,
    utcnow,
)
from app.services import audit
from app.services.extraction import EXTRACTOR_VERSION, extract_text
from app.services.file_types import file_type_for, sanitize_filename, verify_signature
from app.services.profile_service import require_profile
from app.services.storage import FileStore


def upload(
    session: Session,
    store: FileStore,
    source: BinaryIO,
    filename: str | None,
    category: DocumentCategory,
    display_name: str | None,
    max_bytes: int,
) -> Document:
    profile = require_profile(session)
    original_name = sanitize_filename(filename)
    file_type = file_type_for(original_name)
    doc_id = new_id()

    stored = store.save_original(doc_id, file_type.extension, source, max_bytes)
    created_paths = [stored.relative_path]
    try:
        verify_signature(store.resolve(stored.relative_path), file_type)

        existing = session.scalar(
            select(Document.id).where(Document.profile_id == profile.id, Document.sha256 == stored.sha256)
        )
        if existing:
            raise AppError(
                409,
                "duplicate_document",
                "This file has already been uploaded.",
                {"document_id": existing},
            )

        document = Document(
            id=doc_id,
            profile_id=profile.id,
            category=category.value,
            display_name=(display_name or original_name)[:255],
            original_filename=original_name,
            storage_path=stored.relative_path,
            file_extension=file_type.extension,
            mime_type=file_type.mime_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            extraction_status=ExtractionStatus.PENDING.value,
        )
        session.add(document)
        session.flush()
        audit.record(
            session,
            "document.uploaded",
            "document",
            document.id,
            {"category": document.category, "extension": document.file_extension, "size_bytes": document.size_bytes},
        )
        _run_extraction(session, store, document)
        if document.extracted_text_path:
            created_paths.append(document.extracted_text_path)
        session.commit()
    except BaseException:
        session.rollback()
        for path in created_paths:
            store.delete(path)
        raise
    session.refresh(document)
    return document


def _run_extraction(session: Session, store: FileStore, document: Document) -> None:
    result = extract_text(store.resolve(document.storage_path), document.file_extension)
    old_text_path = document.extracted_text_path
    document.extraction_status = result.status.value
    document.extraction_error = result.error
    document.extractor_version = EXTRACTOR_VERSION
    document.extraction_method = result.method
    document.extracted_at = utcnow()
    if result.status == ExtractionStatus.SUCCEEDED:
        document.extracted_text_path = store.write_extracted_text(document.id, result.text)
        document.extracted_char_count = len(result.text)
    else:
        document.extracted_text_path = None
        document.extracted_char_count = None
        if old_text_path:
            store.delete(old_text_path)
    audit.record(
        session,
        "document.extracted",
        "document",
        document.id,
        {"status": result.status.value, "error": result.error, "extractor_version": EXTRACTOR_VERSION,
         "method": result.method},
    )


def get(session: Session, document_id: str) -> Document:
    profile = require_profile(session)
    document = session.get(Document, document_id)
    if document is None or document.profile_id != profile.id:
        raise not_found("document")
    return document


def list_documents(
    session: Session,
    category: DocumentCategory | None,
    include_archived: bool,
    limit: int,
    offset: int,
) -> schemas.Page[schemas.DocumentRead]:
    profile = require_profile(session)
    query = select(Document).where(Document.profile_id == profile.id)
    if category:
        query = query.where(Document.category == category.value)
    if not include_archived:
        query = query.where(Document.archived_at.is_(None))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    docs = session.scalars(
        query.order_by(Document.created_at.desc(), Document.id).limit(limit).offset(offset)
    ).all()
    return schemas.Page[schemas.DocumentRead](
        items=[schemas.DocumentRead.model_validate(d) for d in docs], total=total, limit=limit, offset=offset
    )


def update(session: Session, document_id: str, data: schemas.DocumentUpdate) -> Document:
    document = get(session, document_id)
    changes = data.model_dump(exclude_unset=True)
    for required in ("display_name", "category", "archived"):
        if required in changes and changes[required] is None:
            raise AppError(422, "validation_error", f"{required} cannot be null.")

    changed: list[str] = []
    if "display_name" in changes and changes["display_name"] != document.display_name:
        document.display_name = changes["display_name"]
        changed.append("display_name")
    if "category" in changes and changes["category"].value != document.category:
        document.category = changes["category"].value
        changed.append("category")
    if changed:
        audit.record(session, "document.updated", "document", document.id, {"fields": sorted(changed)})

    if "archived" in changes:
        archived = bool(changes["archived"])
        if archived and document.archived_at is None:
            document.archived_at = utcnow()
            audit.record(session, "document.archived", "document", document.id)
            changed.append("archived")
        elif not archived and document.archived_at is not None:
            document.archived_at = None
            audit.record(session, "document.unarchived", "document", document.id)
            changed.append("archived")

    if changed:
        document.updated_at = utcnow()
    session.commit()
    session.refresh(document)
    return document


def reextract(session: Session, store: FileStore, document_id: str) -> Document:
    document = get(session, document_id)
    _run_extraction(session, store, document)
    document.updated_at = utcnow()
    session.commit()
    session.refresh(document)
    return document


def extracted_text(session: Session, store: FileStore, document_id: str) -> schemas.DocumentText:
    document = get(session, document_id)
    text = store.read_text(document.extracted_text_path) if document.extracted_text_path else None
    return schemas.DocumentText(
        document_id=document.id,
        extraction_status=ExtractionStatus(document.extraction_status),
        extraction_error=document.extraction_error,
        extractor_version=document.extractor_version,
        text=text,
    )


def evidence_count(session: Session, document_id: str) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(ProfileEvidence).where(ProfileEvidence.document_id == document_id)
        )
        or 0
    )


def delete(session: Session, store: FileStore, document_id: str, confirm: bool) -> None:
    document = get(session, document_id)
    refs = evidence_count(session, document.id)
    if refs:
        raise AppError(
            409,
            "document_in_use",
            "This document supports profile evidence. Remove that evidence first, or archive the document instead.",
            {"evidence": refs},
        )
    from app.persistence.models import ApplicationDraft

    used = session.scalar(
        select(func.count()).select_from(ApplicationDraft).where(ApplicationDraft.document_id == document.id)
    )
    if used:
        raise AppError(
            409,
            "document_in_use",
            "This document is part of an application. Archive it instead.",
            {"applications": int(used)},
        )
    if not confirm:
        raise AppError(
            409,
            "confirmation_required",
            "Deleting a document permanently removes the original file and its extracted text. "
            "Repeat the request with confirm=true, or archive the document instead.",
        )
    paths = [document.storage_path, document.extracted_text_path]
    audit.record(session, "document.deleted", "document", document.id, {"category": document.category})
    session.delete(document)
    session.commit()
    for path in paths:
        store.delete(path)


def validate_evidence_document(session: Session, document_id: str) -> None:
    """Evidence may only reference an existing, non-archived document of the current profile."""
    document = get(session, document_id)
    if document.archived_at is not None:
        raise AppError(422, "document_archived", "Archived documents cannot be used as new evidence.")


def file_paths_for_profile(session: Session, profile_id: str) -> list[str]:
    rows = session.execute(
        select(Document.storage_path, Document.extracted_text_path).where(Document.profile_id == profile_id)
    ).all()
    return [p for row in rows for p in row if p]
