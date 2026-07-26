import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.db import Base

settings = get_settings()


class DemandReading(Base):
    """A single demand/telemetry sample for one grid region, at one point in time.

    This table is converted into a TimescaleDB hypertable (partitioned on `time`)
    by the init SQL, so queries over large ranges stay fast as data grows.
    """

    __tablename__ = "demand_readings"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    region: Mapped[str] = mapped_column(String(64), primary_key=True)
    demand_mw: Mapped[float] = mapped_column(Float, nullable=False)
    temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    solar_generation_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ev_load_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_holiday: Mapped[bool] = mapped_column(default=False)


class ProcedureDocument(Base):
    """A chunk of a grid operating procedure / incident playbook, embedded for RAG retrieval."""

    __tablename__ = "procedure_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(settings.embedding_dim), nullable=False)
    doc_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
