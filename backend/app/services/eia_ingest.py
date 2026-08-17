"""Ingests real grid demand from the EIA's open API (Form EIA-930, "Hourly
Electric Grid Monitor") for every region this app tracks.

Each region maps to a real EIA balancing-authority respondent code:
- "california" -> CISO (California ISO — statewide, covers most of
  PG&E/SCE/SDG&E's footprint).
- "smud" -> BANC (Balancing Authority of Northern California). Not a
  SMUD-only figure — BANC is an aggregate that also includes a few smaller
  Sacramento-area municipal utilities (Roseville Electric, Modesto
  Irrigation District, etc.) that SMUD operates the balancing authority
  for — but it's the closest real, publicly available proxy for Sacramento
  service-area demand, and SMUD is by far its dominant load.
- "georgia" -> SOCO (Southern Company Services). Not Atlanta- or
  Georgia-only — SOCO is Southern Company's whole transmission footprint
  (Georgia Power + Alabama Power + Mississippi Power combined). There is
  no separate EIA respondent for Georgia Power alone, so this is the
  finest real grain available; Atlanta (Georgia Power's largest load
  center) is not separable from it, same limitation as PG&E-in-Sacramento.

Verified live against the real API before writing this (2026-07-28 for
CISO, 2026-08-14 for BANC and SOCO): GET
https://api.eia.gov/v2/electricity/rto/region-data/data/ with
facets[respondent][]=<code>, facets[type][]=D, frequency=hourly returns rows
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
_PAGE_SIZE = 5000

EIA_RESPONDENTS = {
    "california": "CISO",
    "smud": "BANC",
    "georgia": "SOCO",
}


def fetch_demand(region: str, days: int = 90) -> pd.DataFrame:
    respondent = EIA_RESPONDENTS[region]
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
                "facets[respondent][]": respondent,
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
        logger.warning("EIA API returned no rows for %s (%s) demand in the requested window", region, respondent)
        return pd.DataFrame(columns=["time", "region", "demand_mw", "temperature_c", "solar_generation_mw", "ev_load_mw", "is_holiday"])

    out = pd.DataFrame(
        {
            "time": [pd.Timestamp(r["period"], tz="UTC") for r in rows],
            "region": region,
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
