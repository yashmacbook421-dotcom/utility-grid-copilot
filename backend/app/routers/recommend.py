import logging
import time

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.regions import REGION_PROFILES
from app.db import get_db
from app.schemas import AgenticRecommendationResponse, RecommendationRequest, RecommendationResponse, ToolCallSummary
from app.services import agentic, budget, cache, forecasting, observability, rag, rate_limiter
from app.services.auth import Principal, require_operator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommend", tags=["recommend"])

settings = get_settings()
# 45s is generous for a single ~1024-token completion but far tighter than the
# SDK's 10-minute default, which is sized for long agentic/streaming workloads
# we don't have here — a hung request shouldn't tie up a worker for 10 minutes.
_client: Anthropic | None = (
    Anthropic(api_key=settings.anthropic_api_key, timeout=45.0) if settings.anthropic_api_key else None
)


@router.post("", response_model=RecommendationResponse)
def recommend(
    payload: RecommendationRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_operator),
):
    rate_limiter.enforce(request)

    cache_key = cache.make_key(
        payload.region,
        payload.question,
        str(payload.top_k),
        payload.source_organization or "",
        payload.source_document_type or "",
        payload.source_region or "",
    )
    cached = cache.get(cache_key)
    if cached is not None:
        observability.log_request(
            db,
            endpoint="/api/recommend",
            region=payload.region,
            question=payload.question,
            total_ms=0.0,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0.0,
            status="cache_hit",
        )
        return cached

    if _client is None:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured on the backend.")

    budget.enforce(db)

    if payload.region not in REGION_PROFILES:
        raise HTTPException(status_code=404, detail=f"Unknown region '{payload.region}'. Valid: {list(REGION_PROFILES)}")

    start = time.perf_counter()
    try:
        retrieval_timing: dict = {}
        sources = rag.retrieve(
            db,
            payload.question,
            top_k=payload.top_k,
            timing=retrieval_timing,
            organization=payload.source_organization,
            document_type=payload.source_document_type,
            region=payload.source_region,
        )
        embedding_ms = retrieval_timing.get("embedding_ms")
        retrieval_ms = retrieval_timing.get("search_ms")

        forecast_data = None
        forecast_summary = None
        forecast_start = time.perf_counter()
        try:
            forecast_data = forecasting.forecast(db, payload.region, REGION_PROFILES[payload.region], horizon_hours=24)
            forecast_summary = rag.summarize_forecast(forecast_data)
        except ValueError:
            pass  # no seeded demand data yet; still answer from procedures alone
        forecast_ms = (time.perf_counter() - forecast_start) * 1000

        generation_start = time.perf_counter()
        generation = rag.generate_answer(
            client=_client,
            model=settings.claude_model,
            question=payload.question,
            region=payload.region,
            sources=sources,
            forecast_summary=forecast_summary,
        )
        generation_ms = (time.perf_counter() - generation_start) * 1000

        warnings: list[str] = []
        _, fabricated_citations = rag.extract_citations(generation.answer, [s.title for s in sources])
        if fabricated_citations:
            warnings.append(
                "This answer cites a source that wasn't in the retrieved procedures — "
                "verify it manually before acting on it."
            )
            logger.warning(
                "Fabricated citation(s) in /api/recommend response for region=%s: %s",
                payload.region,
                fabricated_citations,
            )
    except Exception as exc:
        observability.log_request(
            db,
            endpoint="/api/recommend",
            region=payload.region,
            question=payload.question,
            total_ms=(time.perf_counter() - start) * 1000,
            status="error",
            error_message=str(exc),
        )
        raise

    total_ms = (time.perf_counter() - start) * 1000
    cost = observability.estimate_cost_usd(settings.claude_model, generation.input_tokens, generation.output_tokens)

    request_log_id = observability.log_request(
        db,
        endpoint="/api/recommend",
        region=payload.region,
        question=payload.question,
        embedding_ms=embedding_ms,
        retrieval_ms=retrieval_ms,
        forecast_ms=forecast_ms,
        generation_ms=generation_ms,
        total_ms=total_ms,
        retrieved_sources=[
            {
                "title": s.title,
                "similarity": s.similarity,
                "page_number": s.page_number,
                "section": s.section,
                "organization": s.organization,
            }
            for s in sources
        ],
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
        estimated_cost_usd=cost,
        status="ok",
    )

    response = RecommendationResponse(
        region=payload.region,
        question=payload.question,
        answer=generation.answer,
        sources=sources,
        forecast_context=forecast_data,
        warnings=warnings,
        request_log_id=request_log_id,
    )
    cache.set(cache_key, response)
    return response


@router.post("/agentic", response_model=AgenticRecommendationResponse)
def recommend_agentic(
    payload: RecommendationRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_operator),
):
    """Same job as POST /api/recommend, but Claude decides for itself whether to
    search procedures and/or fetch a forecast, instead of both being pre-fetched.
    Not cached — the point is to see its tool-choice behavior on every call.
    """
    rate_limiter.enforce(request)

    if _client is None:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured on the backend.")

    budget.enforce(db)

    if payload.region not in REGION_PROFILES:
        raise HTTPException(status_code=404, detail=f"Unknown region '{payload.region}'. Valid: {list(REGION_PROFILES)}")

    start = time.perf_counter()
    try:
        result = agentic.run_agentic_recommend(db, _client, settings.claude_model, payload.region, payload.question)
    except Exception as exc:
        observability.log_request(
            db,
            endpoint="/api/recommend/agentic",
            region=payload.region,
            question=payload.question,
            total_ms=(time.perf_counter() - start) * 1000,
            status="error",
            error_message=str(exc),
        )
        raise
    total_ms = (time.perf_counter() - start) * 1000

    # Dedupe sources by title (multiple search_procedures calls can overlap).
    deduped_sources = {}
    for s in result.sources:
        deduped_sources.setdefault(s.title, s)
    sources = list(deduped_sources.values())

    warnings: list[str] = []
    _, fabricated_citations = rag.extract_citations(result.answer, [s.title for s in sources])
    if fabricated_citations:
        warnings.append(
            "This answer cites a source that wasn't in the retrieved procedures — "
            "verify it manually before acting on it."
        )
        logger.warning(
            "Fabricated citation(s) in /api/recommend/agentic response for region=%s: %s",
            payload.region,
            fabricated_citations,
        )

    cost = observability.estimate_cost_usd(settings.claude_model, result.input_tokens, result.output_tokens)
    request_log_id = observability.log_request(
        db,
        endpoint="/api/recommend/agentic",
        region=payload.region,
        question=payload.question,
        generation_ms=total_ms,
        total_ms=total_ms,
        retrieved_sources=[
            {
                "title": s.title,
                "similarity": s.similarity,
                "page_number": s.page_number,
                "section": s.section,
                "organization": s.organization,
            }
            for s in sources
        ],
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost_usd=cost,
        status="ok",
    )

    return AgenticRecommendationResponse(
        region=payload.region,
        question=payload.question,
        answer=result.answer,
        tool_calls=[ToolCallSummary(tool=t.tool, input=t.input, summary=t.summary) for t in result.tool_calls],
        sources=sources,
        forecast_context=result.forecast_context,
        warnings=warnings,
        iterations=result.iterations,
        request_log_id=request_log_id,
    )
