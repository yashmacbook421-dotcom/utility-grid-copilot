"""Tests the PDF ingestion pipeline against a real downloaded document
(not a synthetic fixture) — the small CAISO duck-curve PDF already in
knowledge_base/, so these tests exercise real pypdf extraction and the
real regex section-detection heuristics, not a hand-crafted stand-in.
"""

import os

import pytest
from sqlalchemy import delete

from app.models import Document, DocumentChunk, IngestionRun
from app.services import pdf_ingest

_SAMPLE_PDF = os.path.join(
    os.path.dirname(__file__), "..", "knowledge_base", "renewable_energy", "caiso-duck-curve-fast-facts.pdf"
)


@pytest.fixture(autouse=True)
def _skip_if_sample_missing():
    if not os.path.exists(_SAMPLE_PDF):
        pytest.skip("Sample PDF not downloaded — run knowledge_base/download_and_ingest.py first.")


def test_extract_pages_returns_nonempty_text_per_page():
    pages = pdf_ingest.extract_pages(_SAMPLE_PDF)
    assert len(pages) > 0
    assert all(page.text.strip() for page in pages), "every page of this real PDF has extractable text"
    assert [p.page_number for p in pages] == list(range(1, len(pages) + 1)), "page numbers are 1-indexed, sequential"


def test_chunks_never_cross_a_page_boundary():
    """Every chunk is built from exactly one page's text (chunk_document
    calls chunk_text once per page). Checked via word-set containment
    rather than an exact substring match — chunk_text's overlap mechanism
    (see rag.py) legitimately reconstructs text as "tail + next paragraph",
    which isn't always a literal contiguous substring of the source even
    when every word in it genuinely came from that one page.
    """
    pages = pdf_ingest.extract_pages(_SAMPLE_PDF)
    chunks = pdf_ingest.chunk_document(pages)
    assert len(chunks) > 0

    # 8+ char words only — short/common words appear on every page (running
    # headers, "the", "and", ...) and would make this check meaningless.
    def distinctive_words(text: str) -> set[str]:
        return {w for w in text.split() if len(w) >= 8}

    words_by_page = {p.page_number: distinctive_words(p.text) for p in pages}
    for chunk in chunks:
        chunk_words = distinctive_words(chunk.content)
        leaked = chunk_words - words_by_page[chunk.page_number]
        assert not leaked, f"chunk tagged page {chunk.page_number} contains words not on that page: {leaked}"


def test_section_detection_finds_real_headings():
    pages = pdf_ingest.extract_pages(_SAMPLE_PDF)
    chunks = pdf_ingest.chunk_document(pages)
    sections_found = {c.section for c in chunks if c.section}
    assert sections_found, "expected at least one detected section heading in a real regulatory-style PDF"


def test_ingest_pdf_round_trip(db):
    run = pdf_ingest.ingest_pdf(
        db,
        pdf_path=_SAMPLE_PDF,
        title="[test] Duck Curve Fast Facts",
        organization="test_fixture",
        document_type="fast_facts",
        source_url="https://example.invalid/test",
    )
    try:
        assert run.status == "ok"
        assert run.chunks_created > 0
        assert run.document_id is not None

        stored_chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == run.document_id).all()
        assert len(stored_chunks) == run.chunks_created
        assert all(c.embedding is not None and len(c.embedding) == 384 for c in stored_chunks)
    finally:
        db.execute(delete(IngestionRun).where(IngestionRun.document_id == run.document_id))
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == run.document_id))
        db.execute(delete(Document).where(Document.id == run.document_id))
        db.commit()


def test_ingest_pdf_records_failure_for_a_bad_path(db):
    run = pdf_ingest.ingest_pdf(
        db,
        pdf_path="/nonexistent/path/does-not-exist.pdf",
        title="[test] Should Fail",
        organization="test_fixture",
        document_type="fast_facts",
        source_url="https://example.invalid/test",
    )
    assert run.status == "error"
    assert run.document_id is None
    assert run.error_message is not None
