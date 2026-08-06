"""Downloads (if not already cached) and ingests every document listed in
download_manifest.py. Run after the DB is up:

    cd backend && python -m knowledge_base.download_and_ingest

Safe to re-run: skips downloading a file that's already on disk, and
pdf_ingest.ingest_pdf's caller here checks for an existing Document with
the same title+organization before re-ingesting (see main()).
"""

import os

import requests
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Document
from app.services import pdf_ingest
from knowledge_base.download_manifest import MANIFEST

KNOWLEDGE_BASE_DIR = os.path.dirname(__file__)


def _download(url: str, dest_path: str) -> None:
    if os.path.exists(dest_path):
        print(f"  already downloaded: {dest_path}")
        return
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(response.content)
    print(f"  downloaded {len(response.content):,} bytes -> {dest_path}")


def main() -> None:
    db = SessionLocal()
    try:
        for entry in MANIFEST:
            print(f"=== {entry.title} ({entry.organization}) ===")

            existing = db.execute(
                select(Document.id).where(Document.title == entry.title, Document.organization == entry.organization)
            ).first()
            if existing:
                print("  already ingested, skipping")
                continue

            dest_path = os.path.join(KNOWLEDGE_BASE_DIR, entry.subfolder, entry.filename)
            _download(entry.source_url, dest_path)

            run = pdf_ingest.ingest_pdf(
                db,
                pdf_path=dest_path,
                title=entry.title,
                organization=entry.organization,
                document_type=entry.document_type,
                source_url=entry.source_url,
                publication_date=entry.publication_date,
                region=entry.region,
            )
            if run.status == "ok":
                print(f"  ingested: {run.chunks_created} chunks")
            else:
                print(f"  FAILED: {run.error_message}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
