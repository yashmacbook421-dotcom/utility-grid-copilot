"""Real weather data via Open-Meteo (open-meteo.com) — free, no API key
required for non-commercial use. Two endpoints:

- /v1/archive (historical) — backfills `temperature_c` on already-ingested
  EIA demand readings, which arrive with no temperature at all (see
  eia_ingest.fetch_demand).
- /v1/forecast (forecast) — feeds forecasting.forecast()'s future
  temperature feature. This replaces the old formula-based estimate
  (region mean + seasonal/diurnal sine waves pretending to be a forecast).

Each region maps to a single representative lat/lon point, not a
load-weighted composite across the whole territory (which is closer to what
a utility's own weather desk would use) — same single-point-standing-in-
for-a-whole-region honesty caveat as eia_ingest.py's BANC/SOCO mapping.

Verified live against the real API before writing this (2026-08-17):
GET https://api.open-meteo.com/v1/forecast?latitude=38.58&longitude=-121.49&hourly=temperature_2m&timezone=UTC
returns {"hourly": {"time": [...], "temperature_2m": [...]}}, no auth needed.
"""

import logging
from datetime import datetime

import pandas as pd
import requests

from app.services import cache

logger = logging.getLogger(__name__)

_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

REGION_COORDS = {
    # Fresno — a rough geographic center of CAISO's footprint, not a
    # load-weighted composite of CA's major demand centers.
    "california": (36.75, -119.77),
    "smud": (38.58, -121.49),  # Sacramento
    "georgia": (33.75, -84.39),  # Atlanta — SOCO's largest load center
}


def fetch_historical_temperature(region: str, start: datetime, end: datetime) -> pd.DataFrame:
    lat, lon = REGION_COORDS[region]
    response = requests.get(
        _ARCHIVE_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": start.date().isoformat(),
            "end_date": end.date().isoformat(),
            "hourly": "temperature_2m",
            "timezone": "UTC",
        },
        timeout=30,
    )
    response.raise_for_status()
    hourly = response.json()["hourly"]
    return pd.DataFrame(
        {
            "time": pd.to_datetime(hourly["time"], utc=True),
            "temperature_c": hourly["temperature_2m"],
        }
    )


def _fetch_forecast_df(region: str) -> pd.DataFrame:
    # Cached (see app.services.cache): the regional status dashboard polls
    # forecasting.forecast() every 30s per open tab, and weather doesn't
    # change meaningfully faster than the cache's 5-minute TTL — without
    # this, that polling would hit Open-Meteo on every tick.
    cache_key = cache.make_key("weather-forecast", region)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    lat, lon = REGION_COORDS[region]
    response = requests.get(
        _FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m",
            "forecast_days": 3,  # covers the 72h max horizon (routers/forecast.py) with margin
            "timezone": "UTC",
        },
        timeout=15,
    )
    response.raise_for_status()
    hourly = response.json()["hourly"]
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(hourly["time"], utc=True),
            "temperature_c": hourly["temperature_2m"],
        }
    )
    cache.set(cache_key, df)
    return df


def get_future_temperatures(region: str, future_times: pd.DatetimeIndex) -> list[float]:
    """Real forecasted temperature for each of `future_times`, or NaN (with
    a logged reason) for any hour the weather API didn't cover or couldn't
    be reached — matches forecasting.py's has_temperature=False behavior
    for that hour rather than crashing the whole /api/forecast request.
    """
    try:
        df = _fetch_forecast_df(region)
    except requests.exceptions.RequestException:
        logger.exception("Weather forecast request failed for %s, forecasting without temperature this cycle", region)
        return [float("nan")] * len(future_times)

    series = df.set_index("time")["temperature_c"]
    return [float(series.get(t, float("nan"))) for t in future_times]
