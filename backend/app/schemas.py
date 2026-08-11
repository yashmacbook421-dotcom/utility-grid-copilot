import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class DemandPoint(BaseModel):
    time: datetime
    demand_mw: float
    temperature_c: float | None = None
    solar_generation_mw: float | None = None
    ev_load_mw: float | None = None


class ForecastPoint(BaseModel):
    time: datetime
    predicted_demand_mw: float
    lower_bound_mw: float
    upper_bound_mw: float


class ForecastResponse(BaseModel):
    region: str
    generated_at: datetime
    history: list[DemandPoint]
    forecast: list[ForecastPoint]
    peak_forecast_mw: float
    peak_forecast_time: datetime


class RecommendationRequest(BaseModel):
    region: str
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Operator's question, e.g. 'How should we handle tonight's peak?'",
    )
    top_k: int = Field(default=4, ge=1, le=10)
    source_organization: str | None = Field(default=None, description="Optional filter, e.g. 'NERC' or 'CAISO'.")
    source_document_type: str | None = Field(default=None, description="Optional filter, e.g. 'reliability_standard'.")
    source_region: str | None = Field(default=None, description="Optional filter, e.g. 'California'.")


class SourceCitation(BaseModel):
    title: str
    source: str
    excerpt: str
    similarity: float
    document_id: uuid.UUID | None = None
    page_number: int | None = None
    section: str | None = None
    source_url: str | None = None
    organization: str | None = None


class RecommendationResponse(BaseModel):
    region: str
    question: str
    answer: str
    sources: list[SourceCitation]
    forecast_context: ForecastResponse | None = None
    warnings: list[str] = Field(default_factory=list)
    request_log_id: uuid.UUID | None = None


class WhatIfRequest(BaseModel):
    region: str
    demand_multiplier: float = Field(..., gt=0, le=3, description="e.g. 1.10 for +10% demand, 0.90 for -10%")
    horizon_hours: int = Field(default=24, ge=1, le=72)


class WhatIfResponse(BaseModel):
    region: str
    demand_multiplier: float
    forecast: list[ForecastPoint]
    peak_forecast_mw: float
    peak_forecast_time: datetime
    baseline_p95_mw: float
    would_exceed_baseline: bool
    explanation: str | None = None
    sources: list[SourceCitation] = Field(default_factory=list)


class RegionStatusResponse(BaseModel):
    region: str
    status: str  # "normal" | "elevated" | "surge"
    forecast_peak_mw: float
    baseline_p95_mw: float
    ratio: float
    latest_solar_generation_mw: float | None = None


class DashboardRegionsResponse(BaseModel):
    regions: list[RegionStatusResponse]


class IngestDocumentsResponse(BaseModel):
    ingested: int
    chunks: list[str]


class PdfIngestResponse(BaseModel):
    status: str
    document_id: uuid.UUID | None = None
    title: str
    chunks_created: int
    error_message: str | None = None


class DirectoryIngestResponse(BaseModel):
    results: list[PdfIngestResponse]


class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    chunk_index: int
    page_number: int | None
    section: str | None
    content: str

    model_config = {"from_attributes": True}


class DocumentSourceResponse(BaseModel):
    id: uuid.UUID
    title: str
    organization: str
    document_type: str
    source_url: str
    publication_date: date | None = None
    region: str | None = None
    chunks: list[DocumentChunkResponse]

    model_config = {"from_attributes": True}


class ToolCallSummary(BaseModel):
    tool: str
    input: dict
    summary: str


class AgenticRecommendationResponse(BaseModel):
    region: str
    question: str
    answer: str
    tool_calls: list[ToolCallSummary]
    sources: list[SourceCitation]
    forecast_context: ForecastResponse | None = None
    warnings: list[str] = Field(default_factory=list)
    iterations: int
    request_log_id: uuid.UUID | None = None


class SurgeEventResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    region: str
    forecast_peak_mw: float
    baseline_p95_mw: float
    peak_forecast_time: datetime
    recommended_action: str
    sources: list[SourceCitation]
    status: str
    severity: str
    notified: bool
    notification_error: str | None = None
    resolved_at: datetime | None = None
    resolved_note: str | None = None

    model_config = {"from_attributes": True}


class SurgeResolutionRequest(BaseModel):
    note: str | None = None


class FeedbackRequest(BaseModel):
    request_log_id: uuid.UUID
    rating: str = Field(..., pattern="^(up|down)$")
    reason: str | None = None
    note: str | None = None


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    request_log_id: uuid.UUID
    rating: str
    reason: str | None = None
    note: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackSummaryResponse(BaseModel):
    total: int
    up: int
    down: int
    reasons: dict[str, int]


class MonitoringDashboardResponse(BaseModel):
    rag: dict
    alerts: dict
    feedback: dict
    budget: dict
