from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.data.regions import REGION_PROFILES
from app.db import get_db
from app.schemas import DashboardRegionsResponse, RegionStatusResponse
from app.services import surge_watcher

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/regions", response_model=DashboardRegionsResponse)
def get_all_region_statuses(db: Session = Depends(get_db)):
    """Read-only status for every region — safe to poll from the dashboard
    (no Claude call, no side effects), unlike the background surge-watcher
    it shares its threshold math with. Regions with no seeded data yet are
    simply omitted rather than erroring.
    """
    statuses = []
    for region, profile in REGION_PROFILES.items():
        status = surge_watcher.compute_region_status(db, region, profile)
        if status is not None:
            statuses.append(RegionStatusResponse(**status))
    return DashboardRegionsResponse(regions=statuses)
