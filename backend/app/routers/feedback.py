from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AnswerFeedback, RequestLog
from app.schemas import FeedbackRequest, FeedbackResponse, FeedbackSummaryResponse

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest, db: Session = Depends(get_db)):
    if db.get(RequestLog, payload.request_log_id) is None:
        raise HTTPException(status_code=404, detail=f"No request with id '{payload.request_log_id}'.")

    entry = AnswerFeedback(
        request_log_id=payload.request_log_id,
        rating=payload.rating,
        reason=payload.reason,
        note=payload.note,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/summary", response_model=FeedbackSummaryResponse)
def feedback_summary(db: Session = Depends(get_db)):
    rows = db.execute(select(AnswerFeedback.rating, AnswerFeedback.reason)).all()

    up = sum(1 for rating, _ in rows if rating == "up")
    down = sum(1 for rating, _ in rows if rating == "down")
    reasons: dict[str, int] = {}
    for rating, reason in rows:
        if rating == "down" and reason:
            reasons[reason] = reasons.get(reason, 0) + 1

    return FeedbackSummaryResponse(total=len(rows), up=up, down=down, reasons=reasons)
