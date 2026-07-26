from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.data.generate_synthetic_data import REGION_PROFILES
from app.db import get_db
from app.schemas import ForecastResponse
from app.services import forecasting

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


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
