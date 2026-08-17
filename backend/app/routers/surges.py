from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.regions import REGION_PROFILES
from app.db import get_db
from app.models import SurgeEvent
from app.schemas import SurgeEventResponse, SurgeResolutionRequest
from app.services import surge_watcher
from app.services.auth import Principal, require_operator

router = APIRouter(prefix="/api/surges", tags=["surges"])


@router.get("", response_model=list[SurgeEventResponse])
def list_surges(
    status: str | None = None,
    region: str | None = None,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_operator),
):
    stmt = select(SurgeEvent).order_by(SurgeEvent.created_at.desc())
    if status:
        stmt = stmt.where(SurgeEvent.status == status)
    if region:
        stmt = stmt.where(SurgeEvent.region == region)
    return db.execute(stmt).scalars().all()


def _resolve(surge_id: str, new_status: str, payload: SurgeResolutionRequest, db: Session) -> SurgeEvent:
    event = db.get(SurgeEvent, surge_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No surge event with id '{surge_id}'.")
    event.status = new_status
    event.resolved_at = datetime.utcnow()
    event.resolved_note = payload.note
    db.commit()
    db.refresh(event)
    return event


@router.post("/demo-trigger", response_model=SurgeEventResponse)
def demo_trigger_surge(
    region: str,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_operator),
):
    """Forces a real surge-detection pass for `region`, skipping the
    peak-vs-baseline threshold gate — for live demos, not part of normal
    operation (the background loop in main.py never calls this). Everything
    downstream is genuinely real: retrieval, the Claude call, the DB row,
    and Slack/SMS notifications all fire exactly as they would for an
    organic detection, just without waiting for one to happen naturally.
    """
    if region not in REGION_PROFILES:
        raise HTTPException(status_code=404, detail=f"Unknown region '{region}'.")
    event = surge_watcher.check_region_for_surge(db, region, REGION_PROFILES[region], force=True)
    if event is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Could not trigger a demo surge — a pending event may already exist for this "
                "region (approve/reject it first), or there's no seeded demand data yet."
            ),
        )
    return event


@router.post("/{surge_id}/approve", response_model=SurgeEventResponse)
def approve_surge(
    surge_id: str,
    payload: SurgeResolutionRequest = SurgeResolutionRequest(),
    db: Session = Depends(get_db),
    _: Principal = Depends(require_operator),
):
    return _resolve(surge_id, "approved", payload, db)


@router.post("/{surge_id}/reject", response_model=SurgeEventResponse)
def reject_surge(
    surge_id: str,
    payload: SurgeResolutionRequest = SurgeResolutionRequest(),
    db: Session = Depends(get_db),
    _: Principal = Depends(require_operator),
):
    return _resolve(surge_id, "rejected", payload, db)
