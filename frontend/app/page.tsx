"use client";

import { useEffect, useState } from "react";
import { getForecast, listRegions } from "@/lib/api";
import { ForecastResponse } from "@/lib/types";
import RegionSelect from "@/components/RegionSelect";
import ForecastCards from "@/components/ForecastCards";
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
      <header className="hero">
        <h1>Grid Copilot</h1>
        <p>Ask a question in plain English and get a clear answer about your grid.</p>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <p className="step-label">Step 1 · Choose your area</p>
        {regions.length > 0 && <RegionSelect regions={regions} value={region} onChange={setRegion} />}

        {loading && !forecast && <p className="empty-state" style={{ marginTop: 16 }}>Loading forecast…</p>}

        {forecast && (
          <div className="forecast-summary">
            <p className="forecast-summary-text">
              Expected peak demand is <strong>{Math.round(forecast.peak_forecast_mw).toLocaleString()} MW</strong>,
              around{" "}
              <strong>
                {new Date(forecast.peak_forecast_time).toLocaleString(undefined, {
                  weekday: "long",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </strong>
              .
            </p>
          </div>
        )}

        {forecast && (
          <details className="details-toggle">
            <summary>Show hour-by-hour forecast</summary>
            <div className="details-body">
              <ForecastCards data={forecast} />
            </div>
          </details>
        )}
      </div>

      {region && <RecommendPanel region={region} />}
    </div>
  );
}
