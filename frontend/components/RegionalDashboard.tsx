"use client";

import { useEffect, useState } from "react";
import { getRegionStatuses } from "@/lib/api";
import { RegionStatus } from "@/lib/types";
import { formatRegionLabel } from "@/components/RegionSelect";

const POLL_INTERVAL_MS = 30_000;

const STATUS_LABEL: Record<RegionStatus["status"], string> = {
  normal: "Normal",
  elevated: "Elevated",
  surge: "Surge",
};

export default function RegionalDashboard({ onSelectRegion }: { onSelectRegion: (region: string) => void }) {
  const [statuses, setStatuses] = useState<RegionStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    function poll() {
      getRegionStatuses()
        .then((list) => {
          if (!cancelled) {
            setStatuses(list);
            setError(null);
          }
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load region statuses.");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="card">
      <p className="step-label">California Grid — Regional Status</p>
      <p className="card-subtitle">Click a region to see its forecast, ask a question, or review alerts.</p>

      {loading && <p className="empty-state">Loading region statuses…</p>}
      {error && <div className="error-banner">{error}</div>}

      <div className="region-grid">
        {statuses.map((s) => (
          <button
            key={s.region}
            className={`region-tile region-tile-${s.status}`}
            onClick={() => onSelectRegion(s.region)}
          >
            <span className="region-tile-name">{formatRegionLabel(s.region)}</span>
            <span className="region-tile-status">
              <span className={`level-dot level-${s.status === "normal" ? "low" : s.status === "elevated" ? "medium" : "high"}`} />
              {STATUS_LABEL[s.status]}
            </span>
            <span className="region-tile-peak">{Math.round(s.forecast_peak_mw).toLocaleString()} MW forecast peak</span>
          </button>
        ))}
      </div>
    </div>
  );
}
