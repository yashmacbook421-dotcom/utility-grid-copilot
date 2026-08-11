"""Keeps `demand_readings` current, not just seeded once.

Without this, an operator opening the app days or weeks after the container
was first started would see forecasts anchored to real "now" (forecasting.py
fixes that separately) but built from demand *patterns* that stopped
updating the moment seeding finished — the model equivalent of a weather app
that only ever shows last month's conditions. Two different refresh
mechanisms, because "current" means something different for each region
type:

- **California** is real data (EIA/CAISO) — refresh means pulling whatever
  new real hours exist since the last one we have, same source as initial
  seeding.
- **The three synthetic regions** have no real sensor to poll — refresh
  means extending the same generator (generate_synthetic_data.py) forward
  to cover the gap, so "current demand" for a synthetic region is at least
  internally consistent with its own historical pattern, not frozen.

Both are idempotent and safe to call on a timer or at startup: each only
inserts rows strictly after whatever's already stored, so calling this
often (or after a long gap) never creates duplicates.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data.generate_synthetic_data import REGIONS, generate_region
from app.db import engine
from app.models import DemandReading
from app.services import eia_ingest

logger = logging.getLogger(__name__)


def _latest_time(db: Session, region: str) -> datetime | None:
    return db.execute(select(func.max(DemandReading.time)).where(DemandReading.region == region)).scalar()


def refresh_synthetic_demand(db: Session) -> int:
    now = datetime.now(timezone.utc)
    inserted = 0

    for region in REGIONS:
        latest = _latest_time(db, region)
        if latest is None:
            continue  # not seeded yet at all — seed.py's job, not a refresh
        gap_hours = (now - latest).total_seconds() / 3600
        if gap_hours < 1:
            continue  # already current to within the hour

        start = latest + timedelta(hours=1)
        days_needed = int(gap_hours // 24) + 1
        df = generate_region(region, start=start, days=days_needed)
        df = df[df["time"] <= now]
        if df.empty:
            continue

        with engine.begin() as conn:
            df.to_sql("demand_readings", conn, if_exists="append", index=False)
        inserted += len(df)
        logger.info("Refreshed %s: %d new synthetic rows through %s", region, len(df), df["time"].max())

    return inserted


def refresh_california_demand(db: Session) -> int:
    latest = _latest_time(db, "california")
    if latest is None:
        return 0  # not seeded yet at all — seed.py's job (needs EIA_API_KEY check), not a refresh

    now = datetime.now(timezone.utc)
    gap_hours = (now - latest).total_seconds() / 3600
    if gap_hours < 1:
        return 0

    # A little slack past the exact gap in case EIA's own data has a
    # reporting lag — cheap to over-fetch, the dedup filter below handles it.
    days_needed = max(1, int(gap_hours // 24) + 1)
    try:
        df = eia_ingest.fetch_ciso_demand(days=days_needed)
    except Exception:
        logger.exception("EIA refresh request failed, will retry next cycle")
        return 0

    df = df[df["time"] > latest]
    if df.empty:
        return 0

    with engine.begin() as conn:
        df.to_sql("demand_readings", conn, if_exists="append", index=False)
    logger.info("Refreshed california: %d new EIA rows through %s", len(df), df["time"].max())
    return len(df)


def refresh_all(db: Session) -> None:
    synthetic_count = refresh_synthetic_demand(db)
    california_count = refresh_california_demand(db)
    if synthetic_count or california_count:
        logger.info(
            "Data refresh complete: %d synthetic rows, %d california rows added",
            synthetic_count,
            california_count,
        )
