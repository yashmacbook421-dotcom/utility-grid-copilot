import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
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
    # Nullable: EIA demand rows arrive with no temperature at all (see
    # eia_ingest.fetch_demand); app.data.seed.backfill_weather fills this in
    # from app.services.weather_ingest after ingest. HistGradientBoosting-
    # Regressor (forecasting.py) natively handles NaN features, so any row
    # that a weather backfill couldn't cover just degrades gracefully.
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    solar_generation_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ev_load_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_holiday: Mapped[bool] = mapped_column(default=False)


class Document(Base):
    """A single source document (real, e.g. a NERC/CAISO/FERC/CPUC PDF, or
    synthetic, one of the original hand-written procedure files) that's been
    ingested for RAG retrieval. A document has many DocumentChunks.

    `organization="synthetic"` marks the original 4 hand-written procedure
    docs — kept alongside real documents in the same schema/retrieval path
    rather than a separate table, so there's one retrieval code path, not two.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    organization: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DocumentChunk(Base):
    """One retrievable, embedded chunk of a Document. `page_number`/`section`
    are nullable — real PDFs have them, the synthetic markdown docs don't.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(settings.embedding_dim), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(500), nullable=True)


class IngestionRun(Base):
    """One attempt to ingest a document (success or failure) — an audit
    trail for the ingestion pipeline itself, separate from the documents it
    produces.
    """

    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    source_path_or_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    chunks_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RequestLog(Base):
    """Per-request telemetry for /api/recommend: stage latency, token usage, cost, retrieval."""

    __tablename__ = "request_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)

    embedding_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieval_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecast_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    generation_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    retrieved_sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class SurgeEvent(Base):
    """A demand surge the background watcher detected and drafted a
    recommendation for — awaiting human approval/rejection. See
    app/services/surge_watcher.py for the detection + generation logic.
    """

    __tablename__ = "surge_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    region: Mapped[str] = mapped_column(String(64), nullable=False)

    forecast_peak_mw: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_p95_mw: Mapped[float] = mapped_column(Float, nullable=False)
    peak_forecast_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # "medium"/"high" — a reasoned first-pass split on how far the forecast
    # exceeds baseline_p95_mw, not calibrated against a large real sample
    # (surges are rare by design). Informational only — every severity
    # still requires human approval; this doesn't gate that.
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    notified: Mapped[bool] = mapped_column(default=False)
    notification_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class CustomerCase(Base):
    """One customer-service interaction: the audit trail and conversation
    memory for the Customer Service Agent Assist module (see
    app/services/customer_service_agent.py). `messages` is the running
    Claude conversation for this case (raw Anthropic message dicts) — DB-
    backed rather than an in-memory dict so memory survives a backend
    restart, same reasoning as everything else in this project that's meant
    to be a real audit trail rather than a convenience cache.

    Distinct from RequestLog: RequestLog is generic per-call telemetry
    (latency/tokens/cost) shared across every Claude-calling endpoint in the
    app; this table is the case-level domain object, analogous to how
    SurgeEvent is the domain object for surge detection while also being
    logged through RequestLog for its own Claude calls.
    """

    __tablename__ = "customer_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # Not a real FK — customer/outage/bill data is a static synthetic
    # fixture (app/data/customer_service_demo_data.py), not a DB table.
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    service_area: Mapped[str | None] = mapped_column(String(100), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")  # "open" | "closed"
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    escalated: Mapped[bool] = mapped_column(default=False)
    escalation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Links back to the granular per-turn RequestLog rows for this case.
    request_log_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class AnswerFeedback(Base):
    """A thumbs up/down on a specific answer, referenced by the RequestLog
    row it came from — reuses that row's region/question/answer/sources
    rather than duplicating them here.
    """

    __tablename__ = "answer_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_log_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("request_logs.id"), nullable=False)
    rating: Mapped[str] = mapped_column(String(8), nullable=False)  # "up" | "down"
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
