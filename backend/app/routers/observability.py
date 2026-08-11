from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import AnswerFeedback, RequestLog, SurgeEvent
from app.schemas import MonitoringDashboardResponse
from app.services import budget
from app.services.auth import Principal, require_operator

router = APIRouter(prefix="/api/observability", tags=["observability"])


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


@router.get("/requests")
def list_requests(
    limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), _: Principal = Depends(require_operator)
):
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


@router.get("/dashboard", response_model=MonitoringDashboardResponse)
def monitoring_dashboard(
    limit: int = Query(default=200, ge=1, le=2000), db: Session = Depends(get_db), _: Principal = Depends(require_operator)
):
    """Real, per-request/per-event numbers only — deliberately does not
    include eval-only metrics like recall@k or citation accuracy, which
    require a golden set with known-correct answers that live queries
    don't have. Showing an offline eval number here would misrepresent it
    as a live production stat.
    """
    log_rows = db.execute(select(RequestLog).order_by(RequestLog.created_at.desc()).limit(limit)).scalars().all()
    ok_rows = [r for r in log_rows if r.status == "ok"]
    costs = [r.estimated_cost_usd for r in ok_rows if r.estimated_cost_usd is not None]

    rag_stats = {
        "queries": len(log_rows),
        "errors": sum(1 for r in log_rows if r.status == "error"),
        "cache_hits": sum(1 for r in log_rows if r.status == "cache_hit"),
        "avg_latency_ms": _mean([r.total_ms for r in ok_rows if r.total_ms is not None]),
        "total_input_tokens": sum(r.input_tokens for r in ok_rows if r.input_tokens is not None),
        "total_output_tokens": sum(r.output_tokens for r in ok_rows if r.output_tokens is not None),
        "total_estimated_cost_usd": round(sum(costs), 4) if costs else 0.0,
        "avg_cost_per_query_usd": round(sum(costs) / len(costs), 6) if costs else None,
    }

    surge_rows = db.execute(select(SurgeEvent)).scalars().all()
    alerts_stats = {
        "surges_detected": len(surge_rows),
        "pending": sum(1 for s in surge_rows if s.status == "pending"),
        "approved": sum(1 for s in surge_rows if s.status == "approved"),
        "rejected": sum(1 for s in surge_rows if s.status == "rejected"),
        "high_severity": sum(1 for s in surge_rows if s.severity == "high"),
        "notifications_sent": sum(1 for s in surge_rows if s.notified),
        "notifications_failed": sum(1 for s in surge_rows if not s.notified and s.notification_error),
    }

    feedback_rows = db.execute(select(AnswerFeedback.rating)).scalars().all()
    feedback_stats = {
        "total": len(feedback_rows),
        "up": sum(1 for r in feedback_rows if r == "up"),
        "down": sum(1 for r in feedback_rows if r == "down"),
    }

    cap = get_settings().daily_spend_cap_usd
    spent_today = budget.today_spend_usd(db)
    budget_stats = {
        "daily_cap_usd": cap if cap > 0 else None,
        "spent_today_usd": round(spent_today, 4),
        "over_cap": budget.is_over_budget(db),
    }

    return MonitoringDashboardResponse(rag=rag_stats, alerts=alerts_stats, feedback=feedback_stats, budget=budget_stats)
