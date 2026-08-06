"""Three answer-generation pipelines sharing one result shape, so the
comparison runner can score them identically: no-RAG baseline (isolates
what retrieval actually contributes), deterministic RAG (existing
/api/recommend path), and agentic tool-use (existing /api/recommend/agentic
path, which decides for itself whether to retrieve or check the forecast).
"""

import time
from dataclasses import dataclass, field
from typing import Callable

from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.data.generate_synthetic_data import REGION_PROFILES
from app.evals.golden_set import GoldenItem
from app.schemas import SourceCitation
from app.services import agentic, forecasting, rag


@dataclass
class PipelineResult:
    answer: str
    sources: list[SourceCitation] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    forecast_summary: str | None = None


def _forecast_summary_for(db: Session, item: GoldenItem) -> str | None:
    try:
        forecast_data = forecasting.forecast(db, item.region, REGION_PROFILES[item.region], horizon_hours=24)
        return rag.summarize_forecast(forecast_data)
    except ValueError:
        return None


def run_no_rag(db: Session, client: Anthropic, model: str, item: GoldenItem) -> PipelineResult:
    """Same generation call as deterministic RAG, but with no retrieved
    context — only retrieval is skipped, forecast grounding stays, so this
    isolates what retrieval specifically contributes.
    """
    start = time.perf_counter()
    forecast_summary = _forecast_summary_for(db, item)
    generation = rag.generate_answer(
        client=client, model=model, question=item.question, region=item.region, sources=[], forecast_summary=forecast_summary
    )
    latency_ms = (time.perf_counter() - start) * 1000
    return PipelineResult(
        answer=generation.answer,
        sources=[],
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
        latency_ms=latency_ms,
        forecast_summary=forecast_summary,
    )


def run_deterministic_rag(
    db: Session, client: Anthropic, model: str, item: GoldenItem, retrieve_fn: Callable = rag.retrieve, top_k: int = 4
) -> PipelineResult:
    start = time.perf_counter()
    sources = retrieve_fn(db, item.question, top_k=top_k)
    forecast_summary = _forecast_summary_for(db, item)
    generation = rag.generate_answer(
        client=client,
        model=model,
        question=item.question,
        region=item.region,
        sources=sources,
        forecast_summary=forecast_summary,
    )
    latency_ms = (time.perf_counter() - start) * 1000
    return PipelineResult(
        answer=generation.answer,
        sources=sources,
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
        latency_ms=latency_ms,
        forecast_summary=forecast_summary,
    )


def run_agentic(db: Session, client: Anthropic, model: str, item: GoldenItem) -> PipelineResult:
    start = time.perf_counter()
    result = agentic.run_agentic_recommend(db, client, model, item.region, item.question)
    latency_ms = (time.perf_counter() - start) * 1000

    deduped: dict[str, SourceCitation] = {}
    for s in result.sources:
        deduped.setdefault(s.title, s)

    return PipelineResult(
        answer=result.answer,
        sources=list(deduped.values()),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=latency_ms,
    )


PIPELINES = {
    "no-rag": run_no_rag,
    "deterministic-rag": run_deterministic_rag,
    "agentic": run_agentic,
}
