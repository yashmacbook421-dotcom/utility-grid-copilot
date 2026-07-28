"use client";

import { ForecastResponse } from "@/lib/types";

function formatHour(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { hour: "numeric" });
}

function levelFor(value: number, min: number, max: number): "low" | "medium" | "high" {
  if (max === min) return "low";
  const ratio = (value - min) / (max - min);
  if (ratio < 0.34) return "low";
  if (ratio < 0.67) return "medium";
  return "high";
}

export default function ForecastCards({ data }: { data: ForecastResponse }) {
  const points = data.forecast;
  if (points.length === 0) return null;

  const values = points.map((p) => p.predicted_demand_mw);
  const min = Math.min(...values);
  const max = Math.max(...values);

  return (
    <div>
      <div className="legend-row">
        <span className="legend-item">
          <span className="level-dot level-low" /> Quiet
        </span>
        <span className="legend-item">
          <span className="level-dot level-medium" /> Busy
        </span>
        <span className="legend-item">
          <span className="level-dot level-high" /> Peak
        </span>
      </div>
      <div className="forecast-cards-row">
        {points.map((p) => {
          const isPeak = p.time === data.peak_forecast_time;
          return (
            <div className={`forecast-card${isPeak ? " forecast-card-peak" : ""}`} key={p.time}>
              <p className="forecast-card-time">{formatHour(p.time)}</p>
              <span className={`level-dot level-${levelFor(p.predicted_demand_mw, min, max)}`} />
              <p className="forecast-card-value">
                {Math.round(p.predicted_demand_mw).toLocaleString()}
                <span className="unit">MW</span>
              </p>
              {isPeak && <p className="forecast-card-peak-label">Peak</p>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
