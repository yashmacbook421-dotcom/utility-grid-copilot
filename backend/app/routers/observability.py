from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RequestLog

router = APIRouter(prefix="/api/observability", tags=["observability"])


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


@router.get("/requests")
def list_requests(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    stmt = select(RequestLog).order_by(RequestLog.created_at.desc()).limit(limit)
    rows = db.execute(stmt).scalars().all()

    error_count = sum(1 for r in rows if r.status == "error")
    cache_hit_count = sum(1 for r in rows if r.status == "cache_hit")
    ok_rows = [r for r in rows if r.status == "ok"]  # exclude errors + cache hits from latency averages
    input_tokens = [r.input_tokens for r in rows if r.input_tokens is not None]
    output_tokens = [r.output_tokens for r in rows if r.output_tokens is not None]
    costs = [r.estimated_cost_usd for r in rows if r.estimated_cost_usd is not None]

    summary = {
        "count": len(rows),
        "error_count": error_count,
        "cache_hit_count": cache_hit_count,
        "avg_total_ms": _mean([r.total_ms for r in ok_rows if r.total_ms is not None]),
        "avg_retrieval_ms": _mean([r.retrieval_ms for r in ok_rows if r.retrieval_ms is not None]),
        "avg_generation_ms": _mean([r.generation_ms for r in ok_rows if r.generation_ms is not None]),
        "total_input_tokens": sum(input_tokens),
        "total_output_tokens": sum(output_tokens),
        "total_estimated_cost_usd": sum(costs),
    }

    requests = [
        {
            "id": str(r.id),
            "created_at": r.created_at,
            "region": r.region,
            "question": (r.question[:120] + "…") if r.question and len(r.question) > 120 else r.question,
            "retrieval_ms": r.retrieval_ms,
            "forecast_ms": r.forecast_ms,
            "generation_ms": r.generation_ms,
            "total_ms": r.total_ms,
            "retrieved_sources": r.retrieved_sources,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "estimated_cost_usd": r.estimated_cost_usd,
            "status": r.status,
            "error_message": r.error_message,
        }
        for r in rows
    ]

    return {"summary": summary, "requests": requests}
