from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import IngestDocumentsResponse
from app.services import rag

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


class IngestDocumentRequest(BaseModel):
    source: str
    title: str
    content: str


@router.post("/documents", response_model=IngestDocumentsResponse)
def ingest_document(payload: IngestDocumentRequest, db: Session = Depends(get_db)):
    chunks = rag.ingest_document(db, payload.source, payload.title, payload.content)
    return IngestDocumentsResponse(ingested=len(chunks), chunks=chunks)
