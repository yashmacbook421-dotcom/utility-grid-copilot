"""Background surge detection: watches each region's forecast on its own,
and when the forecast peak looks like a genuine surge, drafts a grounded
recommendation automatically — but never acts on it. A human has to
explicitly approve or reject via app/routers/surges.py.

Distinct from the other two recommendation paths in this project: unlike
POST /api/recommend (deterministic RAG) and POST /api/recommend/agentic
(reactive tool-use loop), this one runs on its own schedule with no human
prompting it, and its output sits behind an approval gate rather than being
returned directly. Proactive trigger + bounded autonomy + human-in-the-loop.

Threshold picked empirically (2026-07-28), not guessed: for all 3 seeded
synthetic regions, the ordinary next-24h forecast peak sits at ~81-88% of
that region's own trailing-30-day 95th-percentile demand (north-valley
1352 vs p95 1659; coastal-metro 2477 vs p95 3048; high-desert 775 vs p95
881). So a forecast peak that outright *exceeds* the trailing p95 is
already a rare, top-5%-of-history event — no extra margin needed on top.
Same "measure, then pick the constant" approach as _MIN_SIMILARITY in rag.py.
"""

import logging

from anthropic import Anthropic
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.generate_synthetic_data import REGION_PROFILES
from app.models import SurgeEvent
from app.schemas import SourceCitation
from app.services import forecasting, notify, rag

logger = logging.getLogger(__name__)

_SURGE_THRESHOLD_RATIO = 1.0
_BASELINE_WINDOW_DAYS = 30

# Reasoned first pass, not calibrated against a large real sample — surges
# are rare by design (that's the whole point of _SURGE_THRESHOLD_RATIO), so
# there isn't a large sample of real ones to calibrate a split against yet.
_HIGH_SEVERITY_RATIO = 1.05

_STATUS_NORMAL_RATIO = 0.90
_STATUS_ELEVATED_RATIO = _SURGE_THRESHOLD_RATIO  # same line "surge" uses

settings = get_settings()
_client: Anthropic | None = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None


def _has_pending_event(db: Session, region: str) -> bool:
    stmt = select(SurgeEvent.id).where(SurgeEvent.region == region, SurgeEvent.status == "pending").limit(1)
    return db.execute(stmt).first() is not None


def check_region_for_surge(db: Session, region: str, region_profile: dict) -> SurgeEvent | None:
    if _has_pending_event(db, region):
        return None

    try:
        forecast_data = forecasting.forecast(db, region, region_profile, horizon_hours=24)
    except ValueError:
        return None  # no seeded demand data yet for this region

    history = forecasting.load_history(db, region, days=_BASELINE_WINDOW_DAYS)
    if history.empty:
        return None

    baseline_p95 = float(history["demand_mw"].quantile(0.95))
    peak = forecast_data["peak_forecast_mw"]

    if peak < baseline_p95 * _SURGE_THRESHOLD_RATIO:
        return None

    question = (
        f"We're forecasting a demand surge to {peak:.0f} MW at {forecast_data['peak_forecast_time']} "
        f"for {region}, above the typical range (this region's normal high end is around "
        f"{baseline_p95:.0f} MW). What should the operator do?"
    )
    sources: list[SourceCitation] = rag.retrieve(db, question, top_k=4)
    forecast_summary = rag.summarize_forecast(forecast_data)

    if _client is None:
        logger.warning("Surge detected for %s but ANTHROPIC_API_KEY is not configured; skipping recommendation", region)
        return None

    generation = rag.generate_answer(
        client=_client,
        model=settings.claude_model,
        question=question,
        region=region,
        sources=sources,
        forecast_summary=forecast_summary,
    )

    ratio = peak / baseline_p95
    severity = "high" if ratio >= _HIGH_SEVERITY_RATIO else "medium"

    event = SurgeEvent(
        region=region,
        forecast_peak_mw=peak,
        baseline_p95_mw=baseline_p95,
        peak_forecast_time=forecast_data["peak_forecast_time"],
        recommended_action=generation.answer,
        sources=[{"title": s.title, "source": s.source, "excerpt": s.excerpt, "similarity": s.similarity} for s in sources],
        status="pending",
        severity=severity,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # uq_surge_events_pending_region (init_db.py) — another check already
        # created a pending event for this region in the race window between
        # the _has_pending_event check above and this commit.
        db.rollback()
        logger.info("Surge event for %s lost the race to an existing pending event; skipping", region)
        return None
    db.refresh(event)
    logger.info("Surge event created for %s: forecast %.0f MW vs p95 %.0f MW (severity=%s)", region, peak, baseline_p95, severity)

    notified, notification_error = notify.notify_slack(
        f":rotating_light: *[{severity.upper()}] Demand surge forecast for {region}*\n"
        f"Peak {peak:.0f} MW at {forecast_data['peak_forecast_time']} "
        f"(normal high end ~{baseline_p95:.0f} MW). A recommendation is waiting for approval "
        f"in the Grid Copilot dashboard."
    )
    event.notified = notified
    event.notification_error = notification_error
    db.commit()
    db.refresh(event)
    return event


def compute_region_status(db: Session, region: str, region_profile: dict) -> dict | None:
    """Read-only twin of check_region_for_surge's threshold math — no
    Claude call, no SurgeEvent row, safe to poll from a dashboard. Returns
    None if there's no seeded demand data yet for this region.
    """
    try:
        forecast_data = forecasting.forecast(db, region, region_profile, horizon_hours=24)
    except ValueError:
        return None

    history = forecasting.load_history(db, region, days=_BASELINE_WINDOW_DAYS)
    if history.empty:
        return None

    baseline_p95 = float(history["demand_mw"].quantile(0.95))
    peak = forecast_data["peak_forecast_mw"]
    ratio = peak / baseline_p95 if baseline_p95 > 0 else 0.0

    if ratio >= _STATUS_ELEVATED_RATIO:
        status = "surge"
    elif ratio >= _STATUS_NORMAL_RATIO:
        status = "elevated"
    else:
        status = "normal"

    latest_solar = None
    if not history.empty and "solar_generation_mw" in history.columns:
        latest_solar = float(history.sort_values("time").iloc[-1]["solar_generation_mw"])

    return {
        "region": region,
        "status": status,
        "forecast_peak_mw": peak,
        "baseline_p95_mw": baseline_p95,
        "ratio": round(ratio, 4),
        "latest_solar_generation_mw": latest_solar,
    }


def run_surge_check_all_regions(db: Session) -> None:
    for region, region_profile in REGION_PROFILES.items():
        try:
            check_region_for_surge(db, region, region_profile)
        except Exception:
            logger.exception("Surge check failed for region=%s", region)
