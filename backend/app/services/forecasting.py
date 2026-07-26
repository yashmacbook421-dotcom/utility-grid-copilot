"""Short-horizon demand forecasting.

Trains a gradient-boosted quantile regressor per region on historical demand
readings (time-of-day / day-of-week / temperature -> demand), then projects
forward using an estimated future temperature curve. Median + 10/90th
percentile models give a forecast band instead of a single point estimate,
which is what makes the output usable for grid-balancing decisions.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DemandReading

FEATURE_COLUMNS = ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos", "temperature_c", "is_holiday"]


@dataclass
class RegionModels:
    median: HistGradientBoostingRegressor
    lower: HistGradientBoostingRegressor
    upper: HistGradientBoostingRegressor
    trained_rows: int


_MODEL_CACHE: dict[str, RegionModels] = {}


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    hour = df["time"].dt.hour + df["time"].dt.minute / 60
    dow = df["time"].dt.dayofweek
    month = df["time"].dt.month

    return pd.DataFrame(
        {
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "dow_sin": np.sin(2 * np.pi * dow / 7),
            "dow_cos": np.cos(2 * np.pi * dow / 7),
            "month_sin": np.sin(2 * np.pi * month / 12),
            "month_cos": np.cos(2 * np.pi * month / 12),
            "temperature_c": df["temperature_c"],
            "is_holiday": df["is_holiday"].astype(float),
        }
    )


def estimate_future_temperature(region_profile: dict, ts: pd.Timestamp) -> float:
    """Deterministic seasonal + diurnal temperature estimate (no noise) for forecasting horizon."""
    day_of_year = ts.timetuple().tm_yday
    hour = ts.hour + ts.minute / 60
    seasonal_swing = region_profile["temp_amplitude"] * math.sin((day_of_year / 365) * 2 * math.pi - math.pi / 2)
    return region_profile["temp_mean_c"] + seasonal_swing + 4 * math.sin(hour / 24 * 2 * math.pi)


def load_history(db: Session, region: str, days: int = 60) -> pd.DataFrame:
    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(DemandReading)
        .where(DemandReading.region == region, DemandReading.time >= cutoff)
        .order_by(DemandReading.time)
    )
    rows = db.execute(stmt).scalars().all()
    return pd.DataFrame(
        [
            {
                "time": pd.Timestamp(r.time),
                "demand_mw": r.demand_mw,
                "temperature_c": r.temperature_c,
                "solar_generation_mw": r.solar_generation_mw,
                "ev_load_mw": r.ev_load_mw,
                "is_holiday": r.is_holiday,
            }
            for r in rows
        ]
    )


def get_or_train_models(region: str, history: pd.DataFrame) -> RegionModels:
    cached = _MODEL_CACHE.get(region)
    if cached is not None and cached.trained_rows == len(history):
        return cached

    X = _build_features(history)
    y = history["demand_mw"]

    median_model = HistGradientBoostingRegressor(loss="squared_error", max_depth=6, random_state=42)
    lower_model = HistGradientBoostingRegressor(loss="quantile", quantile=0.1, max_depth=6, random_state=42)
    upper_model = HistGradientBoostingRegressor(loss="quantile", quantile=0.9, max_depth=6, random_state=42)

    median_model.fit(X, y)
    lower_model.fit(X, y)
    upper_model.fit(X, y)

    models = RegionModels(median=median_model, lower=lower_model, upper=upper_model, trained_rows=len(history))
    _MODEL_CACHE[region] = models
    return models


def forecast(db: Session, region: str, region_profile: dict, horizon_hours: int = 24) -> dict:
    history = load_history(db, region)
    if history.empty:
        raise ValueError(f"No historical demand data for region '{region}'. Seed the database first.")

    models = get_or_train_models(region, history)

    last_time = history["time"].max()
    future_times = pd.date_range(start=last_time + timedelta(hours=1), periods=horizon_hours, freq="h")

    future_df = pd.DataFrame(
        {
            "time": future_times,
            "temperature_c": [estimate_future_temperature(region_profile, t) for t in future_times],
            "is_holiday": [t.month == 12 and t.day in (25, 26) for t in future_times],
        }
    )

    X_future = _build_features(future_df)
    median_pred = models.median.predict(X_future)
    lower_pred = np.minimum(models.lower.predict(X_future), median_pred)
    upper_pred = np.maximum(models.upper.predict(X_future), median_pred)

    forecast_points = [
        {
            "time": t.to_pydatetime(),
            "predicted_demand_mw": round(float(m), 2),
            "lower_bound_mw": round(float(lo), 2),
            "upper_bound_mw": round(float(hi), 2),
        }
        for t, m, lo, hi in zip(future_times, median_pred, lower_pred, upper_pred)
    ]

    peak_idx = int(np.argmax(median_pred))

    recent_history = history.tail(48)
    history_points = [
        {
            "time": row.time.to_pydatetime(),
            "demand_mw": row.demand_mw,
            "temperature_c": row.temperature_c,
            "solar_generation_mw": row.solar_generation_mw,
            "ev_load_mw": row.ev_load_mw,
        }
        for row in recent_history.itertuples()
    ]

    return {
        "region": region,
        "generated_at": datetime.utcnow(),
        "history": history_points,
        "forecast": forecast_points,
        "peak_forecast_mw": forecast_points[peak_idx]["predicted_demand_mw"],
        "peak_forecast_time": forecast_points[peak_idx]["time"],
    }
