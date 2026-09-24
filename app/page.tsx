"use client";

import { useEffect, useState } from "react";
import { Activity, Compass, Headphones, LayoutGrid, Zap } from "lucide-react";
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
import DeliveryAssistPanel from "@/components/DeliveryAssistPanel";

type Tab = "dashboard" | "ask" | "customer-service" | "delivery-assist" | "monitoring";

const NAV_ITEMS: { tab: Tab; label: string; icon: typeof Zap }[] = [
  { tab: "dashboard", label: "Command center", icon: LayoutGrid },
  { tab: "ask", label: "Grid Copilot", icon: Zap },
  { tab: "customer-service", label: "Customer Support", icon: Headphones },
  { tab: "delivery-assist", label: "Delivery Assist", icon: Compass },
  { tab: "monitoring", label: "Observability", icon: Activity },
];

export default function Home() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);
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

  const activeLabel = NAV_ITEMS.find((item) => item.tab === tab)?.label ?? "";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark" aria-hidden="true">
            <Zap size={18} strokeWidth={2.4} />
          </span>
          <div>
            <p className="brand-name">Utility AI</p>
            <p className="brand-sub">Platform · internal</p>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = tab === item.tab;
            return (
              <button
                key={item.tab}
                className={`sidebar-nav-item${active ? " sidebar-nav-item-active" : ""}`}
                onClick={() => setTab(item.tab)}
                aria-current={active ? "page" : undefined}
              >
                <Icon size={16} strokeWidth={active ? 2.4 : 2} />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="copilot-status-card">
            <p className="csc-label">Copilot status</p>
            <p className="csc-title">Human in the loop</p>
            <p className="csc-body">AI drafts only — nothing acts on physical infrastructure without approval.</p>
          </div>
          <p className="sidebar-note">Data: EIA · Open-Meteo · seeded customer records</p>
        </div>
      </aside>

      <div className="shell-main">
        <header className="page-header">
          <div>
            <p className="page-eyebrow">Internal · employee-facing demo</p>
            <h1 className="page-title">{activeLabel}</h1>
          </div>
          <div className="page-header-right">
            <span className="status-pill status-pill-ok">
              <span className="dot" /> System nominal
            </span>
            {now && (
              <span className="page-timestamp">
                {now.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
              </span>
            )}
          </div>
        </header>

        <main className="page-content">
          {error && <div className="error-banner">{error}</div>}

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

      {tab === "delivery-assist" && <DeliveryAssistPanel />}

      {tab === "monitoring" && <MonitoringDashboard />}
        </main>
      </div>
    </div>
  );
}
