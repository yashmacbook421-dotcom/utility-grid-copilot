from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.generate_synthetic_data import REGION_PROFILES
from app.db import get_db
from app.schemas import RecommendationRequest, RecommendationResponse
from app.services import forecasting, rag

router = APIRouter(prefix="/api/recommend", tags=["recommend"])

settings = get_settings()
_client: Anthropic | None = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None


def _summarize_forecast(forecast_data: dict) -> str:
    peak = forecast_data["peak_forecast_mw"]
    peak_time = forecast_data["peak_forecast_time"]
    first = forecast_data["forecast"][0]
    return (
        f"Next forecast point: {first['predicted_demand_mw']} MW "
        f"(range {first['lower_bound_mw']}-{first['upper_bound_mw']} MW) at {first['time']}. "
        f"Forecast peak: {peak} MW at {peak_time}."
    )


@router.post("", response_model=RecommendationResponse)
def recommend(payload: RecommendationRequest, db: Session = Depends(get_db)):
    if _client is None:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured on the backend.")

    if payload.region not in REGION_PROFILES:
        raise HTTPException(status_code=404, detail=f"Unknown region '{payload.region}'. Valid: {list(REGION_PROFILES)}")

    sources = rag.retrieve(db, payload.question, top_k=payload.top_k)

    forecast_data = None
    forecast_summary = None
    try:
        forecast_data = forecasting.forecast(db, payload.region, REGION_PROFILES[payload.region], horizon_hours=24)
        forecast_summary = _summarize_forecast(forecast_data)
    except ValueError:
        pass  # no seeded demand data yet; still answer from procedures alone

    answer = rag.generate_answer(
        client=_client,
        model=settings.claude_model,
        question=payload.question,
        region=payload.region,
        sources=sources,
        forecast_summary=forecast_summary,
    )

    return RecommendationResponse(
        region=payload.region,
        question=payload.question,
        answer=answer,
        sources=sources,
        forecast_context=forecast_data,
    )
