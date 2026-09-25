"""Upload a document and read it back after it has been indexed."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.deps import get_pipeline
from app.errors import DocumentNotFound, EmptyDocument, InvalidDocument, UnsupportedDocument
from app.ingestion.parser import content_type_for_filename
from app.schemas.document import Document, DocumentUploadResponse

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile,
    pipeline=Depends(get_pipeline),
) -> DocumentUploadResponse:
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="A filename is required")
    data = await file.read()
    if len(data) > pipeline.settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the 20 MB upload limit")
    try:
        content_type = content_type_for_filename(filename)
        return pipeline.ingest(filename, data, content_type)
    except UnsupportedDocument as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except (InvalidDocument, EmptyDocument) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{document_id}", response_model=Document)
def read_document(document_id: str, pipeline=Depends(get_pipeline)) -> Document:
    try:
        return pipeline.get_document(document_id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' was not found") from exc
