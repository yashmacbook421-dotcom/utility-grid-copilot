"""Keeps `demand_readings` current, not just seeded once.

Without this, an operator opening the app days or weeks after the container
was first started would see forecasts anchored to real "now" (forecasting.py
fixes that separately) but built from demand *patterns* that stopped
updating the moment seeding finished — the model equivalent of a weather app
that only ever shows last month's conditions. Every region here is real EIA
data (see app.services.eia_ingest.EIA_RESPONDENTS) — refresh means pulling
whatever new real hours exist since the last one we have, same source as
initial seeding.

Idempotent and safe to call on a timer or at startup: it only inserts rows
strictly after whatever's already stored, so calling this often (or after a
long gap) never creates duplicates.
"""

import logging
from datetime import datetime, timezone

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import DemandReading
from app.services import eia_ingest, weather_ingest

logger = logging.getLogger(__name__)


def _latest_time(db: Session, region: str) -> datetime | None:
    return db.execute(select(func.max(DemandReading.time)).where(DemandReading.region == region)).scalar()


def refresh_eia_demand(db: Session, region: str) -> int:
    latest = _latest_time(db, region)
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
        df = eia_ingest.fetch_demand(region, days=days_needed)
    except Exception:
        logger.exception("EIA refresh request failed for %s, will retry next cycle", region)
        return 0

    df = df[df["time"] > latest]
    if df.empty:
        return 0

    # eia_ingest.fetch_demand leaves temperature_c null on every row; without
    # this, freshly-refreshed rows would sit alongside a backfilled history
    # of real values, and pandas silently turns those nulls into NaN the
    # moment the column has other floats in it — not valid JSON (see
    # forecasting.py's history_points serialization).
    try:
        weather = weather_ingest.fetch_historical_temperature(region, df["time"].min(), df["time"].max())
        temps_by_hour = weather.set_index("time")["temperature_c"]
        df["temperature_c"] = df["time"].dt.floor("h").map(temps_by_hour)
    except requests.exceptions.RequestException:
        logger.exception("Weather refresh request failed for %s, new rows will keep temperature_c null this cycle", region)

    with engine.begin() as conn:
        df.to_sql("demand_readings", conn, if_exists="append", index=False)
    logger.info("Refreshed %s: %d new EIA rows through %s", region, len(df), df["time"].max())
    return len(df)


def refresh_all(db: Session) -> None:
    for region in eia_ingest.EIA_RESPONDENTS:
        count = refresh_eia_demand(db, region)
        if count:
            logger.info("Data refresh complete for %s: %d rows added", region, count)
