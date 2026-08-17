import logging

from sqlalchemy import text

from app.db import Base, engine
from app.models import (  # noqa: F401  (register models)
    AnswerFeedback,
    CustomerCase,
    DemandReading,
    Document,
    DocumentChunk,
    IngestionRun,
    RequestLog,
    SurgeEvent,
)

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Create tables, then apply Timescale/pgvector-specific setup that SQLAlchemy can't express."""
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # procedure_documents (flat, title-only citations) replaced by the
        # documents/document_chunks hierarchy (page/section-aware citations,
        # real + synthetic documents in one schema). Safe to drop: rag.py's
        # ingestion re-seeds the synthetic docs into the new tables, and no
        # other table has a foreign key into procedure_documents.
        conn.execute(text("DROP TABLE IF EXISTS procedure_documents"))

        # Real-data regions (e.g. california/EIA) have no paired temperature
        # reading. No migration tool in this project, so schema evolution on
        # an already-existing table is applied here — ALTER COLUMN DROP NOT
        # NULL is a no-op (safe to re-run) once already nullable.
        conn.execute(text("ALTER TABLE demand_readings ALTER COLUMN temperature_c DROP NOT NULL"))

        # New column on an already-existing table — create_all() only creates
        # missing tables, it won't alter one that's already there. IF NOT
        # EXISTS makes this safe to re-run.
        conn.execute(text("ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS embedding_ms FLOAT"))
        conn.execute(text("ALTER TABLE surge_events ADD COLUMN IF NOT EXISTS severity VARCHAR(16) NOT NULL DEFAULT 'medium'"))
        conn.execute(text("ALTER TABLE surge_events ADD COLUMN IF NOT EXISTS notified BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE surge_events ADD COLUMN IF NOT EXISTS notification_error TEXT"))

        conn.execute(
            text(
                """
                SELECT create_hypertable(
                    'demand_readings', 'time',
                    if_not_exists => TRUE,
                    migrate_data => TRUE
                )
                """
            )
        )

        # Enforces "at most one pending surge event per region" at the DB
        # level — the application-level check in surge_watcher.py has a race
        # window (two near-simultaneous checks could both pass it), this
        # closes it. A partial unique index rather than a plain one since
        # multiple *resolved* (approved/rejected) events per region are fine.
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_surge_events_pending_region
                ON surge_events (region) WHERE status = 'pending'
                """
            )
        )

    logger.info("Database initialized: hypertable ready")
