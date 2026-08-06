import glob
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Document, DocumentChunk
from app.schemas import (
    DirectoryIngestResponse,
    DocumentChunkResponse,
    DocumentSourceResponse,
    IngestDocumentsResponse,
    PdfIngestResponse,
)
from app.services import pdf_ingest, rag

router = APIRouter(prefix="/api/ingest", tags=["ingest"])
rag_router = APIRouter(prefix="/api/rag", tags=["rag"])

# API-uploaded PDFs land here, separate from the curated knowledge_base/
# subfolders (which are populated by knowledge_base/download_and_ingest.py
# from download_manifest.py) — keeps "documents we sourced and vetted" and
# "documents someone uploaded through the API" visibly distinct on disk.
_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base", "uploads")


class IngestDocumentRequest(BaseModel):
    source: str
    title: str
    content: str


@router.post("/documents", response_model=IngestDocumentsResponse)
def ingest_document(payload: IngestDocumentRequest, db: Session = Depends(get_db)):
    """Raw-text ingestion — unchanged from before the PDF pipeline existed,
    kept for backward compatibility (this is what seed.py's synthetic
    procedure docs go through).
    """
    chunks = rag.ingest_document(db, payload.source, payload.title, payload.content)
    return IngestDocumentsResponse(ingested=len(chunks), chunks=chunks)


def _to_pdf_response(run, title: str) -> PdfIngestResponse:
    return PdfIngestResponse(
        status=run.status,
        document_id=run.document_id,
        title=title,
        chunks_created=run.chunks_created,
        error_message=run.error_message,
    )


@router.post("/pdf", response_model=PdfIngestResponse)
async def ingest_pdf_upload(
    file: UploadFile = File(...),
    title: str = Form(...),
    organization: str = Form(...),
    document_type: str = Form(...),
    source_url: str = Form(...),
    region: str | None = Form(None),
    db: Session = Depends(get_db),
):
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    dest_path = os.path.join(_UPLOAD_DIR, file.filename)
    with open(dest_path, "wb") as f:
        f.write(await file.read())

    run = pdf_ingest.ingest_pdf(
        db,
        pdf_path=dest_path,
        title=title,
        organization=organization,
        document_type=document_type,
        source_url=source_url,
        region=region,
    )
    return _to_pdf_response(run, title)


class IngestDirectoryRequest(BaseModel):
    directory_path: str
    organization: str
    document_type: str
    region: str | None = None


@router.post("/directory", response_model=DirectoryIngestResponse)
def ingest_directory(payload: IngestDirectoryRequest, db: Session = Depends(get_db)):
    """Ingests every PDF in a server-local directory — the 'add documents
    without touching application code' path: drop PDFs in a folder, call
    this endpoint (or re-run knowledge_base/download_and_ingest.py for
    manifest-tracked documents).
    """
    if not os.path.isdir(payload.directory_path):
        raise HTTPException(status_code=404, detail=f"No such directory: '{payload.directory_path}'.")

    results = []
    for pdf_path in sorted(glob.glob(os.path.join(payload.directory_path, "*.pdf"))):
        title = os.path.splitext(os.path.basename(pdf_path))[0].replace("-", " ").replace("_", " ").title()
        run = pdf_ingest.ingest_pdf(
            db,
            pdf_path=pdf_path,
            title=title,
            organization=payload.organization,
            document_type=payload.document_type,
            source_url=pdf_path,
            region=payload.region,
        )
        results.append(_to_pdf_response(run, title))
    return DirectoryIngestResponse(results=results)


@rag_router.get("/sources/{document_id}", response_model=DocumentSourceResponse)
def get_document_source(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """Citation drill-down: given a document_id from a SourceCitation, see
    the full document's metadata and every chunk that was made from it.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"No document with id '{document_id}'.")

    chunks = (
        db.execute(select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index))
        .scalars()
        .all()
    )

    return DocumentSourceResponse(
        id=document.id,
        title=document.title,
        organization=document.organization,
        document_type=document.document_type,
        source_url=document.source_url,
        publication_date=document.publication_date,
        region=document.region,
        chunks=[
            DocumentChunkResponse(
                id=c.id, chunk_index=c.chunk_index, page_number=c.page_number, section=c.section, content=c.content
            )
            for c in chunks
        ],
    )
