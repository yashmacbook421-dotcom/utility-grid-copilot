import glob
import os
import uuid
from pathlib import Path

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
from app.services.auth import Principal, require_admin

router = APIRouter(prefix="/api/ingest", tags=["ingest"])
rag_router = APIRouter(prefix="/api/rag", tags=["rag"])

# API-uploaded PDFs land here, separate from the curated knowledge_base/
# subfolders (which are populated by knowledge_base/download_and_ingest.py
# from download_manifest.py) — keeps "documents we sourced and vetted" and
# "documents someone uploaded through the API" visibly distinct on disk.
_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base", "uploads")
_KNOWLEDGE_BASE_DIR = Path(os.path.dirname(_UPLOAD_DIR)).resolve()
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_UPLOAD_CHUNK_BYTES = 1024 * 1024


class IngestDocumentRequest(BaseModel):
    source: str
    title: str
    content: str


def _is_within_knowledge_base(path: Path) -> bool:
    """Only allow server-local ingestion from the managed corpus directory.

    This endpoint is useful for a local operator dropping PDFs into the
    project corpus, but must not become a remote arbitrary-file reader.
    Resolving first also rejects a symlink that points outside that directory.
    """
    try:
        path.resolve().relative_to(_KNOWLEDGE_BASE_DIR)
        return True
    except ValueError:
        return False


async def _save_uploaded_pdf(file: UploadFile) -> str:
    """Stream, validate, and safely name an API-uploaded PDF."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=415, detail="Only .pdf uploads are supported.")

    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    destination = Path(_UPLOAD_DIR) / f"{uuid.uuid4().hex}.pdf"
    bytes_written = 0
    first_chunk = True
    try:
        with destination.open("xb") as saved_file:
            while data := await file.read(_UPLOAD_CHUNK_BYTES):
                if first_chunk:
                    first_chunk = False
                    if not data.startswith(b"%PDF-"):
                        raise HTTPException(status_code=415, detail="Uploaded file is not a valid PDF.")
                bytes_written += len(data)
                if bytes_written > _MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="PDF exceeds the 25 MB upload limit.")
                saved_file.write(data)
        if first_chunk:
            raise HTTPException(status_code=422, detail="Uploaded PDF is empty.")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    return str(destination)


@router.post("/documents", response_model=IngestDocumentsResponse)
def ingest_document(
    payload: IngestDocumentRequest, db: Session = Depends(get_db), _: Principal = Depends(require_admin)
):
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
    _: Principal = Depends(require_admin),
):
    dest_path = await _save_uploaded_pdf(file)

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
def ingest_directory(
    payload: IngestDirectoryRequest, db: Session = Depends(get_db), _: Principal = Depends(require_admin)
):
    """Ingests every PDF in a server-local directory — the 'add documents
    without touching application code' path: drop PDFs in a folder, call
    this endpoint (or re-run knowledge_base/download_and_ingest.py for
    manifest-tracked documents).
    """
    directory = Path(payload.directory_path)
    if not _is_within_knowledge_base(directory):
        raise HTTPException(status_code=403, detail="Directory ingestion is limited to the managed knowledge_base directory.")
    if not directory.is_dir():
        raise HTTPException(status_code=404, detail=f"No such directory: '{payload.directory_path}'.")

    results = []
    for pdf_path in sorted(glob.glob(os.path.join(str(directory.resolve()), "*.pdf"))):
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
