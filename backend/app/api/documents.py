from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_store
from app.domain import schemas
from app.persistence.models import DocumentCategory
from app.services import document_service as svc
from app.services.storage import FileStore

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[FileStore, Depends(get_store)]
DocumentId = Annotated[str, Path(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")]

ERRORS = {
    404: {"model": schemas.ErrorResponse, "description": "Not found"},
    422: {"model": schemas.ErrorResponse, "description": "Validation error"},
}


@router.post(
    "",
    response_model=schemas.DocumentRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        **ERRORS,
        409: {"model": schemas.ErrorResponse, "description": "Duplicate document"},
        413: {"model": schemas.ErrorResponse, "description": "File too large"},
        415: {"model": schemas.ErrorResponse, "description": "Unsupported file type"},
    },
    summary="Upload a PDF, DOCX, TXT, Markdown, HTML, PNG or JPEG document",
    description=(
        "The original file is stored unchanged and read-only. Text is extracted immediately; "
        "check `extraction_status`. Extracted text is never treated as verified facts."
    ),
)
def upload_document(
    request: Request,
    session: SessionDep,
    store: StoreDep,
    file: Annotated[UploadFile, File(description="PDF, DOCX, TXT, Markdown, HTML (e.g. a saved web CV page), PNG or JPEG (read with OCR)")],
    category: Annotated[DocumentCategory, Form()],
    display_name: Annotated[str | None, Form(max_length=200)] = None,
) -> schemas.DocumentRead:
    max_bytes = request.app.state.settings.max_upload_bytes
    name = display_name.strip() if display_name and display_name.strip() else None
    document = svc.upload(session, store, file.file, file.filename, category, name, max_bytes)
    return schemas.DocumentRead.model_validate(document)


@router.get("", response_model=schemas.Page[schemas.DocumentRead], responses=ERRORS, summary="List documents")
def list_documents(
    session: SessionDep,
    category: DocumentCategory | None = None,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.Page[schemas.DocumentRead]:
    return svc.list_documents(session, category, include_archived, limit, offset)


@router.get("/{document_id}", response_model=schemas.DocumentRead, responses=ERRORS, summary="Get document metadata")
def get_document(document_id: DocumentId, session: SessionDep) -> schemas.DocumentRead:
    return schemas.DocumentRead.model_validate(svc.get(session, document_id))


@router.patch(
    "/{document_id}",
    response_model=schemas.DocumentRead,
    responses=ERRORS,
    summary="Rename, recategorize, archive or unarchive a document",
)
def update_document(
    document_id: DocumentId, data: schemas.DocumentUpdate, session: SessionDep
) -> schemas.DocumentRead:
    return schemas.DocumentRead.model_validate(svc.update(session, document_id, data))


@router.get(
    "/{document_id}/content",
    response_class=FileResponse,
    responses={**ERRORS, 200: {"description": "The original file as uploaded", "content": {"application/octet-stream": {}}}},
    summary="Download the original file",
)
def download_document(document_id: DocumentId, session: SessionDep, store: StoreDep) -> FileResponse:
    document = svc.get(session, document_id)
    return FileResponse(
        store.resolve(document.storage_path),
        media_type=document.mime_type,
        filename=document.original_filename,
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )


@router.get(
    "/{document_id}/text",
    response_model=schemas.DocumentText,
    responses=ERRORS,
    summary="Get the extracted text",
)
def get_document_text(document_id: DocumentId, session: SessionDep, store: StoreDep) -> schemas.DocumentText:
    return svc.extracted_text(session, store, document_id)


@router.post(
    "/{document_id}/extract",
    response_model=schemas.DocumentRead,
    responses=ERRORS,
    summary="Re-run text extraction (the original file is not changed)",
)
def reextract_document(document_id: DocumentId, session: SessionDep, store: StoreDep) -> schemas.DocumentRead:
    return schemas.DocumentRead.model_validate(svc.reextract(session, store, document_id))


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**ERRORS, 409: {"model": schemas.ErrorResponse, "description": "Confirmation required or in use"}},
    summary="Permanently delete a document and its stored files",
    description="Requires `confirm=true`. Refused while profile evidence references the document; archive instead.",
)
def delete_document(document_id: DocumentId, session: SessionDep, store: StoreDep, confirm: bool = False) -> Response:
    svc.delete(session, store, document_id, confirm)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{document_id}/fact-suggestions",
    response_model=schemas.FactSuggestionList,
    responses={**ERRORS, 409: {"model": schemas.ErrorResponse, "description": "No extracted text"}},
    summary="Suggest profile facts read from this document's text",
    description=(
        "Nothing is saved. Show the suggestions for review; save the chosen ones with "
        "`POST /api/v1/profile/facts/import`. Suggestions are read by simple rules and can be wrong."
    ),
)
def fact_suggestions(document_id: DocumentId, session: SessionDep, store: StoreDep) -> schemas.FactSuggestionList:
    from app.services import fact_import_service

    return fact_import_service.suggestions(session, store, document_id)
