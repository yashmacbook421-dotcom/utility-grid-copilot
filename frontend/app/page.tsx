"use client";

import { useEffect, useState } from "react";
import { getForecast, listRegions } from "@/lib/api";
import { ForecastResponse } from "@/lib/types";
import RegionSelect from "@/components/RegionSelect";
import StatTile from "@/components/StatTile";
import ForecastChart from "@/components/ForecastChart";
import RecommendPanel from "@/components/RecommendPanel";

export default function Home() {
  const [regions, setRegions] = useState<string[]>([]);
  const [region, setRegion] = useState<string>("");
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listRegions()
      .then((list) => {
        setRegions(list);
        if (list.length > 0) setRegion(list[0]);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load regions."));
  }, []);

  useEffect(() => {
    if (!region) return;
    setLoading(true);
    setError(null);
    getForecast(region)
      .then(setForecast)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load forecast."))
      .finally(() => setLoading(false));
  }, [region]);

  return (
    <div className="container">
      <div className="header">
        <div>
          <h1>Utility Grid Copilot</h1>
          <p>Short-horizon demand forecasting and grid-ops recommendations</p>
        </div>
        {regions.length > 0 && <RegionSelect regions={regions} value={region} onChange={setRegion} />}
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        {forecast && (
          <div className="stat-row">
            <StatTile label="Forecast peak" value={Math.round(forecast.peak_forecast_mw).toLocaleString()} unit="MW" />
            <StatTile
              label="Peak expected"
              value={new Date(forecast.peak_forecast_time).toLocaleString(undefined, {
                weekday: "short",
                hour: "numeric",
                minute: "2-digit",
              })}
            />
          </div>
        )}
        {loading && !forecast && <p className="empty-state">Loading forecast…</p>}
        {forecast && <ForecastChart data={forecast} />}
      </div>

      {region && <RecommendPanel region={region} />}
    </div>
  );
}
