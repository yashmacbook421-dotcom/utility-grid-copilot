"""Per-request telemetry for the RAG recommendation pipeline: cost estimation
and persistence of stage latency / token usage / retrieval to `request_logs`.
"""

from sqlalchemy.orm import Session

from app.models import RequestLog

# claude-sonnet-5 introductory pricing (in effect through 2026-08-31); reverts
# to $3.00 / $15.00 per MTok after that — update this table when it does.
PRICING = {
    "claude-sonnet-5": {"input_per_mtok": 2.00, "output_per_mtok": 10.00},
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    rates = PRICING.get(model)
    if rates is None:
        return None
    return (input_tokens / 1_000_000) * rates["input_per_mtok"] + (output_tokens / 1_000_000) * rates["output_per_mtok"]


def log_request(
    db: Session,
    *,
    endpoint: str,
    region: str | None = None,
    question: str | None = None,
    retrieval_ms: float | None = None,
    forecast_ms: float | None = None,
    generation_ms: float | None = None,
    total_ms: float | None = None,
    retrieved_sources: list[dict] | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    status: str,
    error_message: str | None = None,
) -> None:
    db.add(
        RequestLog(
            endpoint=endpoint,
            region=region,
            question=question,
            retrieval_ms=retrieval_ms,
            forecast_ms=forecast_ms,
            generation_ms=generation_ms,
            total_ms=total_ms,
            retrieved_sources=retrieved_sources or [],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            status=status,
            error_message=error_message,
        )
    )
    db.commit()
