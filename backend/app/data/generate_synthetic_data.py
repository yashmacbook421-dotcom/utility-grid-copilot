"""Generates a synthetic but realistic grid demand dataset for local dev/demo use.

Models the effects that make modern grid forecasting hard:
- daily + weekly seasonality (work-day peaks vs weekend troughs)
- temperature-driven HVAC load (both heating and cooling ends)
- a solar "duck curve" that hollows out midday demand and steepens the evening ramp
- growing EV charging load concentrated in evening hours
"""

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

REGIONS = ["north-valley", "coastal-metro", "high-desert"]

REGION_PROFILES = {
    "north-valley": {"base_mw": 1800, "temp_mean_c": 14, "temp_amplitude": 10, "solar_capacity_mw": 400, "ev_capacity_mw": 150},
    "coastal-metro": {"base_mw": 3200, "temp_mean_c": 17, "temp_amplitude": 6, "solar_capacity_mw": 500, "ev_capacity_mw": 400},
    "high-desert": {"base_mw": 900, "temp_mean_c": 19, "temp_amplitude": 16, "solar_capacity_mw": 600, "ev_capacity_mw": 80},
}

RNG = np.random.default_rng(42)


def _daily_shape(hour: float) -> float:
    """Base load shape across a day: morning ramp, midday plateau, evening peak."""
    morning = 0.15 * math.exp(-((hour - 8) ** 2) / 6)
    evening = 0.35 * math.exp(-((hour - 19) ** 2) / 8)
    base = 0.55 + 0.1 * math.sin((hour - 6) / 24 * 2 * math.pi)
    return base + morning + evening


def _solar_shape(hour: float) -> float:
    if hour < 6 or hour > 19:
        return 0.0
    return max(0.0, math.sin((hour - 6) / 13 * math.pi)) ** 1.3


def _ev_shape(hour: float) -> float:
    return 0.2 + 0.8 * math.exp(-((hour - 20) ** 2) / 10)


def generate_region(region: str, start: datetime, days: int) -> pd.DataFrame:
    profile = REGION_PROFILES[region]
    timestamps = pd.date_range(start=start, periods=days * 24, freq="h", tz=timezone.utc)

    rows = []
    for ts in timestamps:
        hour = ts.hour + ts.minute / 60
        day_of_year = ts.timetuple().tm_yday
        is_weekend = ts.weekday() >= 5
        is_holiday = ts.month == 12 and ts.day in (25, 26)

        seasonal_temp_swing = profile["temp_amplitude"] * math.sin((day_of_year / 365) * 2 * math.pi - math.pi / 2)
        temperature_c = profile["temp_mean_c"] + seasonal_temp_swing + 4 * math.sin(hour / 24 * 2 * math.pi) + RNG.normal(0, 1.2)

        # HVAC load rises when it's cold (heating) or hot (cooling) relative to ~18C comfort point
        hvac_factor = 1 + 0.018 * max(0, 18 - temperature_c) + 0.028 * max(0, temperature_c - 24)

        weekday_factor = 0.8 if is_weekend else 1.0
        holiday_factor = 0.7 if is_holiday else 1.0

        base_demand = profile["base_mw"] * _daily_shape(hour) * hvac_factor * weekday_factor * holiday_factor
        noise = RNG.normal(0, profile["base_mw"] * 0.015)

        solar_mw = profile["solar_capacity_mw"] * _solar_shape(hour) * max(0.3, RNG.normal(0.9, 0.15))
        ev_mw = profile["ev_capacity_mw"] * _ev_shape(hour) * weekday_factor * max(0.5, RNG.normal(0.9, 0.1))

        net_demand = max(0.0, base_demand + ev_mw - solar_mw * 0.6 + noise)

        rows.append(
            {
                "time": ts,
                "region": region,
                "demand_mw": round(net_demand, 2),
                "temperature_c": round(temperature_c, 2),
                "solar_generation_mw": round(max(0.0, solar_mw), 2),
                "ev_load_mw": round(max(0.0, ev_mw), 2),
                "is_holiday": bool(is_holiday),
            }
        )

    return pd.DataFrame(rows)


def generate_all(days: int = 120, start: datetime | None = None) -> pd.DataFrame:
    start = start or (datetime.now(timezone.utc) - timedelta(days=days))
    frames = [generate_region(region, start, days) for region in REGIONS]
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    df = generate_all()
    out_path = "backend/app/data/synthetic_demand.csv"
    df.to_csv(out_path, index=False)
    print(f"wrote {len(df)} rows to {out_path}")
