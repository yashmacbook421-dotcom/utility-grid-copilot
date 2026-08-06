"""PDF ingestion pipeline: extract text page-by-page, detect section
headings with regulatory-document-shaped regex heuristics, chunk within
page boundaries (never across a page, so page-number citations stay
accurate), embed, and store as Document + DocumentChunk rows.

PDF library: pypdf — pure Python, no C extensions, MIT license. Chosen
over PyMuPDF (AGPL, heavier) and pdfplumber (built for table extraction
this project doesn't need) for the smallest footprint that does the one
thing actually required: extract text, keep page boundaries. Consistent
with the CPU-only-torch lesson from earlier — don't add weight the task
doesn't need.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, IngestionRun
from app.services import rag
from app.services.embeddings import embed_texts

logger = logging.getLogger(__name__)

# Regulatory documents (NERC standards, CAISO BPMs, FERC/CPUC reports) are
# formulaic enough for regex section detection to work reasonably: numbered
# requirements ("R1.", "R2."), lettered parts ("A. Introduction"), roman-
# numeral parts ("II. LOAD FORECAST" — CAISO's convention), "Section 4",
# and short ALL-CAPS header lines. Tuned against the actual downloaded
# documents, not assumed correct on paper: the roman-numeral pattern was
# added after checking real CAISO output and finding sections got "stuck"
# past "I." (a single capital letter matched the lettered-part pattern by
# coincidence; "II.", "III." did not, since that pattern only allows one
# letter before the period).
_SECTION_PATTERNS = [
    re.compile(r"^(R\d+\.)\s"),
    re.compile(r"^([A-Z]\.\s+[A-Z][a-zA-Z ]{2,60})$"),
    re.compile(r"^([IVXLCDM]{1,8}\.\s+[A-Za-z][A-Za-z ]{2,60})$"),
    re.compile(r"^(Section\s+\d+[:.]?\s*[A-Za-z ]{0,60})$", re.IGNORECASE),
    re.compile(r"^([A-Z][A-Z0-9 &/\-]{6,70})$"),
]


@dataclass
class PageText:
    page_number: int  # 1-indexed — matches how a human would cite it
    text: str


def extract_pages(pdf_path: str) -> list[PageText]:
    reader = PdfReader(pdf_path)
    return [PageText(page_number=i, text=page.extract_text() or "") for i, page in enumerate(reader.pages, start=1)]


def _detect_section(line: str) -> str | None:
    line = line.strip()
    if not line:
        return None
    for pattern in _SECTION_PATTERNS:
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return None


@dataclass
class Chunk:
    content: str
    page_number: int
    section: str | None


def chunk_document(pages: list[PageText], chunk_size: int = 900, overlap: int = 150) -> list[Chunk]:
    """Chunks within page boundaries only — a chunk never straddles two
    pages, so its page-number citation is always exactly right. `section`
    carries forward from the last page that had a detected heading, so a
    page that's mid-section (no heading of its own) still inherits the
    right label.
    """
    chunks: list[Chunk] = []
    current_section: str | None = None

    for page in pages:
        if not page.text.strip():
            continue

        for line in page.text.split("\n"):
            detected = _detect_section(line)
            if detected:
                current_section = detected
                break  # first heading found on the page sets this page's section

        for piece in rag.chunk_text(page.text, chunk_size=chunk_size, overlap=overlap):
            chunks.append(Chunk(content=piece, page_number=page.page_number, section=current_section))

    return chunks


def ingest_pdf(
    db: Session,
    pdf_path: str,
    title: str,
    organization: str,
    document_type: str,
    source_url: str,
    publication_date: date | None = None,
    region: str | None = None,
    chunk_size: int = 900,
    overlap: int = 150,
) -> IngestionRun:
    started_at = datetime.utcnow()
    try:
        pages = extract_pages(pdf_path)
        chunks = chunk_document(pages, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            raise ValueError(f"No extractable text found in {pdf_path}")

        document = Document(
            title=title,
            organization=organization,
            document_type=document_type,
            source_url=source_url,
            publication_date=publication_date,
            region=region,
        )
        db.add(document)
        db.flush()  # assigns document.id without committing yet

        vectors = embed_texts([c.content for c in chunks])
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=i,
                    content=chunk.content,
                    embedding=vector,
                    page_number=chunk.page_number,
                    section=chunk.section,
                )
            )

        run = IngestionRun(
            document_id=document.id,
            source_path_or_url=pdf_path,
            status="ok",
            chunks_created=len(chunks),
            started_at=started_at,
            finished_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
        logger.info("Ingested '%s': %d chunks across %d pages", title, len(chunks), len(pages))
        return run

    except Exception as exc:
        db.rollback()
        run = IngestionRun(
            document_id=None,
            source_path_or_url=pdf_path,
            status="error",
            chunks_created=0,
            error_message=str(exc),
            started_at=started_at,
            finished_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
        logger.exception("Failed to ingest %s", pdf_path)
        return run
