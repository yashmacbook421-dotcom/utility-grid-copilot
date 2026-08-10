from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.generate_synthetic_data import REGION_PROFILES
from app.db import get_db
from app.schemas import ForecastResponse, WhatIfRequest, WhatIfResponse
from app.services import forecasting, rag, surge_watcher
from app.services.auth import Principal, require_operator

router = APIRouter(prefix="/api/forecast", tags=["forecast"])

settings = get_settings()
_client: Anthropic | None = (
    Anthropic(api_key=settings.anthropic_api_key, timeout=45.0) if settings.anthropic_api_key else None
)


@router.get("", response_model=ForecastResponse)
def get_forecast(
    region: str = Query(..., description="Grid region id, e.g. 'coastal-metro'"),
    horizon_hours: int = Query(default=24, ge=1, le=72),
    db: Session = Depends(get_db),
):
    if region not in REGION_PROFILES:
        raise HTTPException(status_code=404, detail=f"Unknown region '{region}'. Valid: {list(REGION_PROFILES)}")

    try:
        result = forecasting.forecast(db, region, REGION_PROFILES[region], horizon_hours)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return result


@router.get("/regions")
def list_regions():
    return {"regions": list(REGION_PROFILES.keys())}


@router.post("/whatif", response_model=WhatIfResponse)
def whatif_forecast(
    payload: WhatIfRequest, db: Session = Depends(get_db), _: Principal = Depends(require_operator)
):
    """"What if demand is X% higher" — scales the existing trained model's
    forecast (forecasting.forecast_whatif), then reuses the same surge
    threshold + RAG-grounded-explanation pattern as the background
    surge-watcher (surge_watcher.check_region_for_surge) to explain what an
    operator should do *if* this scenario actually happened — without
    creating a real SurgeEvent or notifying anyone, since this is
    hypothetical.
    """
    if payload.region not in REGION_PROFILES:
        raise HTTPException(status_code=404, detail=f"Unknown region '{payload.region}'. Valid: {list(REGION_PROFILES)}")

    try:
        result = forecasting.forecast_whatif(
            db, payload.region, REGION_PROFILES[payload.region], payload.demand_multiplier, payload.horizon_hours
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    history = forecasting.load_history(db, payload.region, days=surge_watcher._BASELINE_WINDOW_DAYS)
    baseline_p95 = float(history["demand_mw"].quantile(0.95)) if not history.empty else 0.0
    would_exceed = bool(baseline_p95 > 0 and result["peak_forecast_mw"] >= baseline_p95 * surge_watcher._SURGE_THRESHOLD_RATIO)

    explanation = None
    sources = []
    if would_exceed and _client is not None:
        question = (
            f"A what-if scenario projects demand up to {result['peak_forecast_mw']:.0f} MW at "
            f"{result['peak_forecast_time']} for {payload.region} (a {payload.demand_multiplier}x demand "
            f"scenario), above the typical range (this region's normal high end is around "
            f"{baseline_p95:.0f} MW). What should the operator do to prepare?"
        )
        sources = rag.retrieve(db, question, top_k=4)
        forecast_summary = rag.summarize_forecast(result)
        generation = rag.generate_answer(
            client=_client,
            model=settings.claude_model,
            question=question,
            region=payload.region,
            sources=sources,
            forecast_summary=forecast_summary,
        )
        explanation = generation.answer

    return WhatIfResponse(
        region=payload.region,
        demand_multiplier=payload.demand_multiplier,
        forecast=result["forecast"],
        peak_forecast_mw=result["peak_forecast_mw"],
        peak_forecast_time=result["peak_forecast_time"],
        baseline_p95_mw=baseline_p95,
        would_exceed_baseline=would_exceed,
        explanation=explanation,
        sources=sources,
    )
