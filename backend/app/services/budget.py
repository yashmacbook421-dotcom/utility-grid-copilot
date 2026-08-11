"""A real, enforced daily spend cap on Claude usage — not just a number on
the observability dashboard. `estimated_cost_usd` is already recorded per
request (observability.py); this module sums today's total and gives every
Claude-calling call site a cheap way to check it *before* spending more,
rather than only noticing after the fact.

Two call patterns, because the call sites aren't all HTTP requests:
- `enforce(db)` — for FastAPI routes: raises HTTPException(503) so the
  request fails loudly and the client sees exactly why.
- `is_over_budget(db)` — for the background surge-watcher loop, which has
  no request to fail: callers skip the Claude call and log a warning
  instead, the same graceful-skip pattern already used when
  ANTHROPIC_API_KEY isn't configured.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import RequestLog


def today_spend_usd(db: Session) -> float:
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.coalesce(func.sum(RequestLog.estimated_cost_usd), 0.0)).where(
        RequestLog.created_at >= start_of_day
    )
    return float(db.execute(stmt).scalar())


def is_over_budget(db: Session) -> bool:
    cap = get_settings().daily_spend_cap_usd
    if cap <= 0:
        return False  # cap disabled
    return today_spend_usd(db) >= cap


def enforce(db: Session) -> None:
    cap = get_settings().daily_spend_cap_usd
    if cap <= 0:
        return
    spent = today_spend_usd(db)
    if spent >= cap:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Daily Claude spend cap of ${cap:.2f} has been reached (${spent:.2f} spent today). "
                "This endpoint will be available again after the cap resets at midnight UTC."
            ),
        )
