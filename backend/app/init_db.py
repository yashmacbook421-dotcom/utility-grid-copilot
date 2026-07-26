import logging

from sqlalchemy import text

from app.db import Base, engine
from app.models import DemandReading, ProcedureDocument  # noqa: F401  (register models)

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Create tables, then apply Timescale/pgvector-specific setup that SQLAlchemy can't express."""
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

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

        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS procedure_documents_embedding_idx
                ON procedure_documents
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
                """
            )
        )

    logger.info("Database initialized: hypertable + vector index ready")
