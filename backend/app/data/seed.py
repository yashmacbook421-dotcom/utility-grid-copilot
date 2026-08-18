"""One-shot seed script: ingests real California demand history from EIA and
sample grid operating procedures into pgvector. Run after the DB is up:

    cd backend && python -m app.data.seed
"""

import glob
import logging
import os

import pandas as pd
import requests
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.init_db import init_db
from app.services import eia_ingest, rag, weather_ingest

PROCEDURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "procedures")
CUSTOMER_SERVICE_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "customer_service")

# Load-bearing, not cosmetic: customer_service_agent.check_escalation() forces
# an escalation whenever a retrieved source has document_type="safety_procedure".
_SAFETY_DOC_FILENAMES = {
    "safety-procedures.md",
    "downed-power-line-procedures.md",
    "emergency-response-procedures.md",
}

logger = logging.getLogger(__name__)


def seed_eia_demand(region: str, days: int = 90) -> None:
    settings = get_settings()
    if not settings.eia_api_key:
        print(f"EIA_API_KEY not configured, skipping {region} region")
        return

    with engine.begin() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM demand_readings WHERE region = :region"), {"region": region}
        ).scalar()
        if count:
            print(f"{region} demand_readings already has {count} rows, skipping re-ingest")
            return

    try:
        df = eia_ingest.fetch_demand(region, days=days)
    except requests.exceptions.RequestException:
        # A bad/expired/rejected key is caught here rather than left to
        # propagate: this runs from FastAPI's synchronous startup hook, so an
        # uncaught exception here would crash the whole app on boot over one
        # optional region's data source, not just skip it — worse than
        # having no key configured at all (see the `not settings.eia_api_key`
        # branch above, which already degrades gracefully).
        logger.exception("EIA API request failed, skipping %s region", region)
        return

    if df.empty:
        print(f"EIA API returned no {region} rows, skipping")
        return

    with engine.begin() as conn:
        df.to_sql("demand_readings", conn, if_exists="append", index=False)
    print(f"seeded {len(df)} {region} demand readings from EIA")


def backfill_weather(region: str) -> None:
    """One-time fill of temperature_c on demand_readings rows ingested
    before weather_ingest existed (or before this region had a coordinate
    mapped). Naturally idempotent: only rows still NULL get selected, so a
    region that's already backfilled is a fast no-op on every later boot.
    """
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT time FROM demand_readings WHERE region = :region AND temperature_c IS NULL ORDER BY time"),
            {"region": region},
        ).fetchall()
    if not rows:
        print(f"{region}: no rows need a temperature backfill")
        return

    start, end = rows[0][0], rows[-1][0]
    try:
        weather = weather_ingest.fetch_historical_temperature(region, start, end)
    except requests.exceptions.RequestException:
        logger.exception("Weather backfill request failed for %s, skipping", region)
        return

    if weather.empty:
        print(f"{region}: weather API returned no historical data, skipping backfill")
        return

    temps_by_hour = weather.set_index("time")["temperature_c"]
    updated = 0
    with engine.begin() as conn:
        for (time_val,) in rows:
            temp = temps_by_hour.get(pd.Timestamp(time_val).floor("h"))
            if temp is None or pd.isna(temp):
                continue
            conn.execute(
                text("UPDATE demand_readings SET temperature_c = :temp WHERE region = :region AND time = :time"),
                {"temp": float(temp), "region": region, "time": time_val},
            )
            updated += 1
    print(f"{region}: backfilled temperature for {updated}/{len(rows)} rows")


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


def seed_customer_service_docs() -> None:
    db = SessionLocal()
    try:
        count = db.execute(
            text("SELECT count(*) FROM documents WHERE organization = 'customer_service'")
        ).scalar()
        if count:
            print(f"customer_service documents already ingested ({count}), skipping re-ingest")
            return

        for path in sorted(glob.glob(os.path.join(CUSTOMER_SERVICE_DOCS_DIR, "*.md"))):
            filename = os.path.basename(path)
            title = os.path.splitext(filename)[0].replace("-", " ").title()
            document_type = "safety_procedure" if filename in _SAFETY_DOC_FILENAMES else "customer_service_procedure"
            with open(path, encoding="utf-8") as f:
                content = f.read()
            chunks = rag.ingest_document(
                db,
                source=filename,
                title=title,
                content=content,
                organization="customer_service",
                document_type=document_type,
            )
            print(f"ingested {path} -> {len(chunks)} chunks ({document_type})")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    seed_eia_demand("california")
    seed_eia_demand("smud")
    seed_eia_demand("georgia")
    backfill_weather("california")
    backfill_weather("smud")
    backfill_weather("georgia")
    seed_procedures()
    seed_customer_service_docs()
