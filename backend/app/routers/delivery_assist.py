"""Delivery Assist API — single-turn grounded Q&A for delivery consultants.
Simpler than routers/customer_service.py on purpose: no case object, no
conversation memory, no tool-use loop. It's the exact same retrieve-then-
generate shape as the original grid-ops /api/recommend, pointed at a third
document corpus (see app/services/delivery_assist.py).
"""

import logging
import time

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.schemas import DeliveryAskRequest, DeliveryAskResponse, EscalationInfo
from app.services import budget, delivery_assist, observability, rag, rate_limiter
from app.services.auth import Principal, require_operator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/delivery-assist", tags=["delivery-assist"])

settings = get_settings()
_client: Anthropic | None = (
    Anthropic(api_key=settings.anthropic_api_key, timeout=45.0) if settings.anthropic_api_key else None
)


@router.get("/areas", response_model=list[str])
def list_areas(_: Principal = Depends(require_operator)):
    return list(delivery_assist.AREA_DOCUMENT_TYPES.keys())


@router.post("/ask", response_model=DeliveryAskResponse)
def ask(
    payload: DeliveryAskRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_operator),
):
    rate_limiter.enforce(request)

    if _client is None:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured on the backend.")
    if payload.area not in delivery_assist.AREA_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown area '{payload.area}'. Known areas: {list(delivery_assist.AREA_DOCUMENT_TYPES)}",
        )

    budget.enforce(db)

    start = time.perf_counter()
    try:
        result = delivery_assist.answer_question(db, _client, settings.claude_model, payload.area, payload.question)
    except Exception as exc:
        observability.log_request(
            db,
            endpoint="/api/delivery-assist/ask",
            question=payload.question,
            total_ms=(time.perf_counter() - start) * 1000,
            status="error",
            error_message=str(exc),
        )
        raise
    total_ms = (time.perf_counter() - start) * 1000

    warnings: list[str] = []
    _, fabricated_citations = rag.extract_citations(result.answer, [s.title for s in result.sources])
    if fabricated_citations:
        warnings.append(
            "This answer cites a source that was not retrieved — verify it with a subject-matter expert before "
            "using it with a client."
        )
        logger.warning("Fabricated citation(s) in /api/delivery-assist/ask: %s", fabricated_citations)

    cost = observability.estimate_cost_usd(settings.claude_model, result.input_tokens, result.output_tokens)
    request_log_id = observability.log_request(
        db,
        endpoint="/api/delivery-assist/ask",
        question=payload.question,
        generation_ms=total_ms,
        total_ms=total_ms,
        retrieved_sources=[
            {"title": s.title, "similarity": s.similarity, "document_type": s.document_type} for s in result.sources
        ],
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost_usd=cost,
        status="ok",
    )

    return DeliveryAskResponse(
        area=payload.area,
        question=payload.question,
        answer=result.answer,
        confidence=result.confidence,
        sources=result.sources,
        escalation=EscalationInfo(required=result.escalation.required, reason=result.escalation.reason),
        warnings=warnings,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost_usd=cost,
        request_log_id=request_log_id,
    )
