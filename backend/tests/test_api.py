"""FastAPI endpoint tests via TestClient — HTTP-level behavior, not just
the underlying service functions.
"""

from sqlalchemy import delete

from app.config import get_settings
from app.models import Document, DocumentChunk


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_forecast_regions_includes_seeded_regions(client):
    response = client.get("/api/forecast/regions")
    assert response.status_code == 200
    regions = response.json()["regions"]
    assert "north-valley" in regions
    assert "coastal-metro" in regions


def test_forecast_unknown_region_is_404(client):
    response = client.get("/api/forecast", params={"region": "not-a-real-region"})
    assert response.status_code == 404


def test_rag_source_lookup_404_for_unknown_document(client):
    response = client.get("/api/rag/sources/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_rag_source_lookup_returns_real_document_with_chunks(client, db):
    doc = db.query(Document).filter(Document.organization == "NERC").first()
    if doc is None:
        import pytest

        pytest.skip("No NERC document ingested yet — run knowledge_base/download_and_ingest.py first.")

    response = client.get(f"/api/rag/sources/{doc.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["organization"] == "NERC"
    assert len(body["chunks"]) > 0
    assert body["chunks"][0]["page_number"] is not None


def test_ingest_raw_text_document_round_trip(client, db):
    response = client.post(
        "/api/ingest/documents",
        json={"source": "test-fixture.md", "title": "[test] API Ingest Fixture", "content": "This is a short test procedure about nothing in particular. It exists only to verify the ingest endpoint round-trips correctly."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ingested"] == 1

    doc = db.query(Document).filter(Document.title == "[test] API Ingest Fixture").first()
    assert doc is not None
    try:
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
        assert len(chunks) == 1
    finally:
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        db.execute(delete(Document).where(Document.id == doc.id))
        db.commit()


def test_ingest_directory_404_for_missing_directory(client):
    response = client.post(
        "/api/ingest/directory",
        json={"directory_path": "knowledge_base/does-not-exist", "organization": "test", "document_type": "test"},
    )
    assert response.status_code == 404


def test_ingest_directory_rejects_paths_outside_the_managed_corpus(client):
    response = client.post(
        "/api/ingest/directory",
        json={"directory_path": "/tmp", "organization": "test", "document_type": "test"},
    )
    assert response.status_code == 403


def test_ingest_pdf_rejects_non_pdf_upload(client):
    response = client.post(
        "/api/ingest/pdf",
        data={
            "title": "Not a PDF",
            "organization": "test",
            "document_type": "test",
            "source_url": "https://example.invalid/not-a-pdf",
        },
        files={"file": ("notes.txt", b"not a PDF", "text/plain")},
    )
    assert response.status_code == 415


def test_auth_required_rejects_missing_or_invalid_api_key(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "operator_api_key", "operator-test-key")
    monkeypatch.setattr(settings, "admin_api_key", "admin-test-key")

    assert client.get("/api/observability/requests").status_code == 401
    assert client.get("/api/observability/requests", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/observability/requests", headers={"X-API-Key": "operator-test-key"}).status_code == 200


def test_auth_roles_restrict_ingestion_to_admin(client, db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "operator_api_key", "operator-test-key")
    monkeypatch.setattr(settings, "admin_api_key", "admin-test-key")
    payload = {"source": "test.md", "title": "[test] Role Test Fixture", "content": "A test document."}

    assert client.post("/api/ingest/documents", json=payload, headers={"X-API-Key": "operator-test-key"}).status_code == 403
    assert client.post("/api/ingest/documents", json=payload, headers={"X-API-Key": "admin-test-key"}).status_code == 200

    doc = db.query(Document).filter(Document.title == payload["title"]).first()
    assert doc is not None
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    db.execute(delete(Document).where(Document.id == doc.id))
    db.commit()
