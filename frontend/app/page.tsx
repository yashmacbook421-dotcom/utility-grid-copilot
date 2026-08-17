"use client";

import { useEffect, useState } from "react";
import { getForecast, listRegions } from "@/lib/api";
import { ForecastResponse } from "@/lib/types";
import RegionSelect from "@/components/RegionSelect";
import ForecastCards from "@/components/ForecastCards";
import RecommendPanel from "@/components/RecommendPanel";
import SurgePanel from "@/components/SurgePanel";
import RegionalDashboard from "@/components/RegionalDashboard";
import WhatIfPanel from "@/components/WhatIfPanel";
import MonitoringDashboard from "@/components/MonitoringDashboard";
import CustomerServicePanel from "@/components/CustomerServicePanel";

type Tab = "dashboard" | "ask" | "customer-service" | "monitoring";

export default function Home() {
  const [tab, setTab] = useState<Tab>("dashboard");
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

  function handleSelectRegion(selected: string) {
    setRegion(selected);
    setTab("ask");
  }

  return (
    <main className="container app-shell">
      <header className="hero">
        <div className="hero-topline">
          <div className="brand-lockup">
            <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
            <span>UTILITY INTELLIGENCE</span>
          </div>
          <div className="live-indicator"><span /> Systems live</div>
        </div>
        <div className="hero-copy">
          <p className="hero-eyebrow">Grid operations, made legible</p>
          <h1>See the signal.<br /><em>Act with context.</em></h1>
          <p>Forecast demand, investigate grid conditions, and get source-backed operational guidance in one focused workspace.</p>
        </div>
        <div className="hero-orbit" aria-hidden="true"><span /><span /><span /></div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <nav className="tab-row">
        <button className={`tab-button${tab === "dashboard" ? " tab-button-active" : ""}`} onClick={() => setTab("dashboard")}>
          <span aria-hidden="true">◫</span> Command center
        </button>
        <button className={`tab-button${tab === "ask" ? " tab-button-active" : ""}`} onClick={() => setTab("ask")}>
          <span aria-hidden="true">✦</span> Copilot
        </button>
        <button
          className={`tab-button${tab === "customer-service" ? " tab-button-active" : ""}`}
          onClick={() => setTab("customer-service")}
        >
          <span aria-hidden="true">☎</span> Customer Service
        </button>
        <button className={`tab-button${tab === "monitoring" ? " tab-button-active" : ""}`} onClick={() => setTab("monitoring")}>
          <span aria-hidden="true">◌</span> Observability
        </button>
      </nav>

      {tab === "dashboard" && <RegionalDashboard onSelectRegion={handleSelectRegion} />}

      {tab === "ask" && (
        <>
          {region && <SurgePanel region={region} />}

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
          {region && <WhatIfPanel region={region} />}
        </>
      )}

      {tab === "customer-service" && <CustomerServicePanel />}

      {tab === "monitoring" && <MonitoringDashboard />}
    </main>
  );
}
