"""One-shot seed script: generates synthetic demand history and ingests sample
grid operating procedures into pgvector. Run after the DB is up:

    cd backend && python -m app.data.seed
"""

import glob
import logging
import os

import requests
from sqlalchemy import text

from app.config import get_settings
from app.data.generate_synthetic_data import generate_all
from app.db import SessionLocal, engine
from app.init_db import init_db
from app.services import eia_ingest, rag

PROCEDURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "procedures")

logger = logging.getLogger(__name__)


def seed_demand_data(days: int = 120) -> None:
    with engine.begin() as conn:
        count = conn.execute(text("SELECT count(*) FROM demand_readings")).scalar()
        if count:
            print(f"demand_readings already has {count} rows, skipping regeneration")
            return

    df = generate_all(days=days)
    with engine.begin() as conn:
        df.to_sql("demand_readings", conn, if_exists="append", index=False)
    print(f"seeded {len(df)} demand readings across {df['region'].nunique()} regions")


def seed_california_demand(days: int = 90) -> None:
    settings = get_settings()
    if not settings.eia_api_key:
        print("EIA_API_KEY not configured, skipping california region")
        return

    with engine.begin() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM demand_readings WHERE region = 'california'")
        ).scalar()
        if count:
            print(f"california demand_readings already has {count} rows, skipping re-ingest")
            return

    try:
        df = eia_ingest.fetch_ciso_demand(days=days)
    except requests.exceptions.RequestException:
        # A bad/expired/rejected key is caught here rather than left to
        # propagate: this runs from FastAPI's synchronous startup hook, so an
        # uncaught exception here would crash the whole app on boot over one
        # optional region's data source, not just skip it — worse than
        # having no key configured at all (see the `not settings.eia_api_key`
        # branch above, which already degrades gracefully).
        logger.exception("EIA API request failed, skipping california region")
        return

    if df.empty:
        print("EIA API returned no california rows, skipping")
        return

    with engine.begin() as conn:
        df.to_sql("demand_readings", conn, if_exists="append", index=False)
    print(f"seeded {len(df)} california demand readings from EIA")


def seed_procedures() -> None:
    db = SessionLocal()
    try:
        count = db.execute(
            text("SELECT count(*) FROM documents WHERE organization = 'synthetic'")
        ).scalar()
        if count:
            print(f"synthetic documents already ingested ({count}), skipping re-ingest")
            return

        for path in sorted(glob.glob(os.path.join(PROCEDURES_DIR, "*.md"))):
            title = os.path.splitext(os.path.basename(path))[0].replace("-", " ").title()
            with open(path, encoding="utf-8") as f:
                content = f.read()
            chunks = rag.ingest_document(db, source=os.path.basename(path), title=title, content=content)
            print(f"ingested {path} -> {len(chunks)} chunks")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    seed_demand_data()
    seed_california_demand()
    seed_procedures()
