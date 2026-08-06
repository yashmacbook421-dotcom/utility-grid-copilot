from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SurgeEvent
from app.schemas import SurgeEventResponse, SurgeResolutionRequest

router = APIRouter(prefix="/api/surges", tags=["surges"])


@router.get("", response_model=list[SurgeEventResponse])
def list_surges(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(SurgeEvent).order_by(SurgeEvent.created_at.desc())
    if status:
        stmt = stmt.where(SurgeEvent.status == status)
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


@router.post("/{surge_id}/approve", response_model=SurgeEventResponse)
def approve_surge(surge_id: str, payload: SurgeResolutionRequest = SurgeResolutionRequest(), db: Session = Depends(get_db)):
    return _resolve(surge_id, "approved", payload, db)


@router.post("/{surge_id}/reject", response_model=SurgeEventResponse)
def reject_surge(surge_id: str, payload: SurgeResolutionRequest = SurgeResolutionRequest(), db: Session = Depends(get_db)):
    return _resolve(surge_id, "rejected", payload, db)
