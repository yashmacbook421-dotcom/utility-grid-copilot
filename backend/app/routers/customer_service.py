"""Customer Service Agent Assist API.

Mirrors routers/recommend.py's structure (rate-limit -> budget check ->
pipeline -> observability.log_request -> response) — see that file for the
grid-ops equivalent of this same pattern.
"""

import logging
import time
import uuid

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.customer_service_demo_data import SERVICE_AREAS
from app.db import get_db
from app.models import CustomerCase
from app.schemas import (
    AskCaseRequest,
    AskCaseResponse,
    BillInfoResponse,
    CaseSummaryResponse,
    CustomerCaseResponse,
    CustomerDetailResponse,
    CustomerInfoResponse,
    EscalationInfo,
    OpenCaseRequest,
    OutageStatusResponse,
    ToolCallSummary,
)
from app.services import billing_tool, budget, customer_data, customer_service_agent, observability, outage_tool, rag, rate_limiter
from app.services.auth import Principal, require_operator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/customer-service", tags=["customer-service"])
outage_router = APIRouter(prefix="/api/outages", tags=["customer-service"])

settings = get_settings()
_client: Anthropic | None = (
    Anthropic(api_key=settings.anthropic_api_key, timeout=45.0) if settings.anthropic_api_key else None
)


@outage_router.get("/{service_area}", response_model=OutageStatusResponse)
def get_outage(service_area: str):
    data = outage_tool.get_outage_status(service_area)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No outage data for service area '{service_area}'. Known areas: {SERVICE_AREAS}",
        )
    return data


@router.get("/customers", response_model=list[CustomerInfoResponse])
def list_customers():
    return customer_data.list_customers()


@router.get("/customers/{customer_id}", response_model=CustomerDetailResponse)
def get_customer(customer_id: str):
    customer = customer_data.get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"No customer with id '{customer_id}'.")
    bill = billing_tool.get_customer_bill(customer_id)
    return CustomerDetailResponse(customer=customer, bill=bill)


def _get_case(db: Session, case_id: uuid.UUID) -> CustomerCase:
    case = db.get(CustomerCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"No case with id '{case_id}'.")
    return case


@router.post("/cases", response_model=CustomerCaseResponse)
def open_case(payload: OpenCaseRequest, db: Session = Depends(get_db), _: Principal = Depends(require_operator)):
    if payload.customer_id and customer_data.get_customer(payload.customer_id) is None:
        raise HTTPException(status_code=404, detail=f"No customer with id '{payload.customer_id}'.")

    case = CustomerCase(
        agent_id=payload.agent_id,
        customer_id=payload.customer_id,
        service_area=payload.service_area,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@router.get("/cases", response_model=list[CustomerCaseResponse])
def list_cases(db: Session = Depends(get_db), _: Principal = Depends(require_operator)):
    stmt = select(CustomerCase).order_by(CustomerCase.created_at.desc()).limit(100)
    return db.execute(stmt).scalars().all()


@router.get("/cases/{case_id}", response_model=CustomerCaseResponse)
def get_case(case_id: uuid.UUID, db: Session = Depends(get_db), _: Principal = Depends(require_operator)):
    return _get_case(db, case_id)


@router.post("/cases/{case_id}/ask", response_model=AskCaseResponse)
def ask_case(
    case_id: uuid.UUID,
    payload: AskCaseRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_operator),
):
    rate_limiter.enforce(request)

    if _client is None:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured on the backend.")

    budget.enforce(db)

    case = _get_case(db, case_id)
    if case.status == "closed":
        raise HTTPException(status_code=409, detail="This case is closed. Open a new case to continue.")

    start = time.perf_counter()
    try:
        if payload.mode == "routed":
            result = customer_service_agent.run_customer_service_turn_routed(
                db,
                _client,
                settings.claude_router_model,
                settings.claude_model,
                payload.question,
                customer_id=case.customer_id,
                service_area=case.service_area,
            )
        else:
            result = customer_service_agent.run_customer_service_turn(
                db, _client, settings.claude_model, case, payload.question
            )
    except Exception as exc:
        observability.log_request(
            db,
            endpoint="/api/customer-service/ask",
            region=case.service_area,
            question=payload.question,
            total_ms=(time.perf_counter() - start) * 1000,
            status="error",
            error_message=str(exc),
        )
        raise
    total_ms = (time.perf_counter() - start) * 1000

    warnings: list[str] = []
    _, fabricated_citations = rag.extract_citations(result.raw_answer, [s.title for s in result.sources])
    if fabricated_citations:
        warnings.append(
            "This answer cites a source that wasn't in the retrieved documents — verify it manually before "
            "repeating it to the customer."
        )
        logger.warning("Fabricated citation(s) in /api/customer-service/ask response for case=%s: %s", case_id, fabricated_citations)

    if result.escalation.required and result.escalation.reason == "safety" and not any(
        s.document_type == "safety_procedure" for s in result.sources
    ):
        warnings.append(
            "This question was flagged as safety-related, but no approved safety procedure was retrieved to "
            "ground the answer — verify manually before responding."
        )

    if result.escalation.required and not case.escalated:
        case.escalated = True
        case.escalation_reason = result.escalation.reason

    if payload.mode == "routed":
        # Two models, two price tables — price each phase at its own rate
        # rather than the whole turn at one model's rate.
        router_cost = observability.estimate_cost_usd(
            result.router_model, result.router_input_tokens, result.router_output_tokens
        )
        answer_cost = observability.estimate_cost_usd(
            result.answer_model, result.answer_input_tokens, result.answer_output_tokens
        )
        cost = None if router_cost is None or answer_cost is None else router_cost + answer_cost
    else:
        cost = observability.estimate_cost_usd(settings.claude_model, result.input_tokens, result.output_tokens)

    request_log_id = observability.log_request(
        db,
        endpoint="/api/customer-service/ask",
        region=case.service_area,
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
                "document_type": s.document_type,
            }
            for s in result.sources
        ],
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost_usd=cost,
        status="ok",
    )

    case.request_log_ids = [*case.request_log_ids, str(request_log_id)]
    db.add(case)
    db.commit()

    return AskCaseResponse(
        case_id=case.id,
        question=payload.question,
        mode=payload.mode,
        internal_analysis=result.internal_analysis,
        customer_response=result.customer_response,
        confidence=result.confidence,
        sources=result.sources,
        tool_calls=[ToolCallSummary(tool=t.tool, input=t.input, summary=t.summary) for t in result.tool_calls],
        escalation=EscalationInfo(required=result.escalation.required, reason=result.escalation.reason),
        warnings=warnings,
        iterations=result.iterations,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost_usd=cost,
        request_log_id=request_log_id,
    )


@router.post("/cases/{case_id}/summary", response_model=CaseSummaryResponse)
def summarize_case(
    case_id: uuid.UUID, request: Request, db: Session = Depends(get_db), _: Principal = Depends(require_operator)
):
    rate_limiter.enforce(request)

    if _client is None:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured on the backend.")

    budget.enforce(db)

    case = _get_case(db, case_id)

    start = time.perf_counter()
    try:
        result = customer_service_agent.generate_case_summary(_client, settings.claude_model, case)
    except Exception as exc:
        observability.log_request(
            db,
            endpoint="/api/customer-service/summary",
            region=case.service_area,
            total_ms=(time.perf_counter() - start) * 1000,
            status="error",
            error_message=str(exc),
        )
        raise
    total_ms = (time.perf_counter() - start) * 1000

    cost = observability.estimate_cost_usd(settings.claude_model, result.input_tokens, result.output_tokens)
    observability.log_request(
        db,
        endpoint="/api/customer-service/summary",
        region=case.service_area,
        total_ms=total_ms,
        generation_ms=total_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost_usd=cost,
        status="ok",
    )

    case.summary = result.summary
    case.status = "closed"
    db.add(case)
    db.commit()

    return CaseSummaryResponse(case_id=case.id, summary=case.summary, status=case.status)
