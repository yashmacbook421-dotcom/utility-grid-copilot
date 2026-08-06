"""Ingests real California grid demand from the EIA's open API (Form EIA-930,
"Hourly Electric Grid Monitor") — the "california" region's data source,
in contrast to the other regions' synthetic data.

Verified live against the real API before writing this (2026-07-28):
GET https://api.eia.gov/v2/electricity/rto/region-data/data/ with
facets[respondent][]=CISO, facets[type][]=D, frequency=hourly returns rows
like {"period": "2026-07-21T00", "value": "38775", ...} — period is UTC,
value is a numeric string in megawatthours (equal to average MW for an
hourly reading), capped at 5000 rows per request with a `total` count for
pagination.
"""

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from app.config import get_settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
_RESPONDENT = "CISO"
_PAGE_SIZE = 5000


def fetch_ciso_demand(days: int = 90) -> pd.DataFrame:
    settings = get_settings()
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)

    rows: list[dict] = []
    offset = 0
    while True:
        response = requests.get(
            _BASE_URL,
            params={
                "api_key": settings.eia_api_key,
                "frequency": "hourly",
                "data[0]": "value",
                "facets[respondent][]": _RESPONDENT,
                "facets[type][]": "D",
                "start": start.strftime("%Y-%m-%dT%H"),
                "end": end.strftime("%Y-%m-%dT%H"),
                "sort[0][column]": "period",
                "sort[0][direction]": "asc",
                "offset": offset,
                "length": _PAGE_SIZE,
            },
            timeout=30,
        )
        response.raise_for_status()
        page = response.json()["response"]["data"]
        rows.extend(page)
        if len(page) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE

    if not rows:
        logger.warning("EIA API returned no rows for CISO demand in the requested window")
        return pd.DataFrame(columns=["time", "region", "demand_mw", "temperature_c", "solar_generation_mw", "ev_load_mw", "is_holiday"])

    out = pd.DataFrame(
        {
            "time": [pd.Timestamp(r["period"], tz="UTC") for r in rows],
            "region": "california",
            "demand_mw": [float(r["value"]) for r in rows],
            # Explicit float64 dtype: a column of all-None defaults to pandas'
            # `object` dtype, which to_sql then binds as VARCHAR — breaking
            # the insert against the Float column.
            "temperature_c": pd.Series([None] * len(rows), dtype="float64"),
            "solar_generation_mw": 0.0,
            "ev_load_mw": 0.0,
        }
    )
    out["is_holiday"] = out["time"].apply(lambda t: t.month == 12 and t.day in (25, 26))
    return out
