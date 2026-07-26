from datetime import datetime

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
    question: str = Field(..., description="Operator's question, e.g. 'How should we handle tonight's peak?'")
    top_k: int = Field(default=4, ge=1, le=10)


class SourceCitation(BaseModel):
    title: str
    source: str
    excerpt: str
    similarity: float


class RecommendationResponse(BaseModel):
    region: str
    question: str
    answer: str
    sources: list[SourceCitation]
    forecast_context: ForecastResponse | None = None


class IngestDocumentsResponse(BaseModel):
    ingested: int
    chunks: list[str]
