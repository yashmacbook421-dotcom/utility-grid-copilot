"""Simulated outage-management-system tool.

A real utility's OMS would answer this from live crew/SCADA telemetry. This
is a synthetic stand-in with the same shape (see GET /api/outages/{area} in
routers/customer_service.py) — `restoration_eta_minutes`/`reported_minutes_ago`
are fixed offsets in the fixture data, resolved to real timestamps relative
to "now" on every call, so the demo stays plausible whenever it's actually
run rather than showing a stale hardcoded date.
"""

from datetime import datetime, timedelta, timezone

from app.data.customer_service_demo_data import OUTAGES, SERVICE_AREAS


def _normalize(service_area: str) -> str | None:
    """Case/whitespace-insensitive match against the known service areas —
    a rep typing "folsom" or "FOLSOM " should hit the same fixture as
    "Folsom". Returns None (not KeyError) for a genuinely unknown area, so
    the caller can say so rather than crash.
    """
    target = service_area.strip().lower()
    for area in SERVICE_AREAS:
        if area.lower() == target:
            return area
    return None


def get_outage_status(service_area: str) -> dict | None:
    """Returns None for an unrecognized service area — the agent must then
    say it doesn't have outage data for that area rather than inventing one.
    """
    area = _normalize(service_area)
    if area is None:
        return None

    record = OUTAGES[area]
    now = datetime.now(timezone.utc)

    last_updated = (
        now - timedelta(minutes=record["reported_minutes_ago"])
        if record["reported_minutes_ago"] is not None
        else None
    )
    estimated_restoration = (
        now + timedelta(minutes=record["restoration_eta_minutes"])
        if record["restoration_eta_minutes"] is not None
        else None
    )
    resolved_at = (
        now - timedelta(minutes=record["resolved_minutes_ago"])
        if record.get("resolved_minutes_ago") is not None
        else None
    )

    return {
        "area": area,
        "status": record["status"],
        "customers_affected": record["customers_affected"],
        "cause": record["cause"],
        "crew_status": record["crew_status"],
        "estimated_restoration": estimated_restoration.isoformat() if estimated_restoration else None,
        "last_updated": last_updated.isoformat() if last_updated else None,
        "resolved_at": resolved_at.isoformat() if resolved_at else None,
    }
