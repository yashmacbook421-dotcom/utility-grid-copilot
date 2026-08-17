"use client";

import { useEffect, useMemo, useState } from "react";
import { getRegionStatuses } from "@/lib/api";
import { RegionStatus } from "@/lib/types";
import { STATES, HierarchyNode } from "@/lib/regionHierarchy";

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
  // Empty path = the collapsed root screen (one icon per state). Drilling
  // in pushes onto the path; the breadcrumb's first segment is always the
  // selected state once expanded.
  const [path, setPath] = useState<HierarchyNode[]>([]);

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

  const statusByRegion = useMemo(() => {
    const map = new Map<string, RegionStatus>();
    statuses.forEach((s) => map.set(s.region, s));
    return map;
  }, [statuses]);

  const current = path[path.length - 1];
  const children = current?.children ?? [];

  function drillInto(node: HierarchyNode, index: number) {
    setPath([...path.slice(0, index + 1), node]);
  }

  function handleTileClick(node: HierarchyNode) {
    if (node.children && node.children.length > 0) {
      setPath([...path, node]);
    } else if (node.regionId) {
      onSelectRegion(node.regionId);
    }
  }

  return (
    <div className="card command-card">
      <div className="card-heading-row">
        <div>
          <p className="step-label">Regional pulse</p>
          <p className="card-title">Grid status at a glance</p>
        </div>
        <span className="refresh-note"><span /> refreshes every 30s</span>
      </div>
      <p className="card-subtitle">
        {!current
          ? "Explore live grid regions by state, down to the utility serving each area."
          : path.length === 1
            ? "Choose a service area to explore its forecast, investigate conditions, or review alerts."
            : `Sub-divisions of ${current.label}.`}
      </p>

      {loading && <p className="empty-state">Loading region statuses…</p>}
      {error && <div className="error-banner">{error}</div>}

      {!current && (
        <div className="region-grid">
          {STATES.map((state) => (
            <button key={state.id} className="region-tile region-tile-root" onClick={() => setPath([state])}>
              <span className="region-tile-name">{state.label}</span>
              <span className="region-tile-sublabel">{state.sublabel}</span>
              <span className="region-tile-hint">View regions →</span>
            </button>
          ))}
        </div>
      )}

      {current && (
        <>
          <nav className="breadcrumb-row" aria-label="Region breadcrumb">
            {path.map((node, i) => (
              <span key={node.id} className="breadcrumb-segment">
                {i > 0 && <span className="breadcrumb-sep">›</span>}
                {i === path.length - 1 ? (
                  <span className="breadcrumb-current">{node.label}</span>
                ) : (
                  <button className="breadcrumb-link" onClick={() => drillInto(node, i)}>
                    {node.label}
                  </button>
                )}
              </span>
            ))}
          </nav>

          {path.length === 1 && current.regionId && (
            <button className="statewide-link" onClick={() => onSelectRegion(current.regionId!)}>
              View statewide forecast
              {statusByRegion.has(current.regionId) && (
                <>
                  {" "}
                  — {Math.round(statusByRegion.get(current.regionId)!.forecast_peak_mw).toLocaleString()} MW forecast
                  peak
                </>
              )}
              <span aria-hidden="true"> →</span>
            </button>
          )}
        </>
      )}

      <div className="region-grid">
        {children.map((node) => {
          const status = node.regionId ? statusByRegion.get(node.regionId) : undefined;
          const isLive = Boolean(node.regionId);
          const isExplorable = Boolean(node.children && node.children.length > 0);
          const clickable = isLive || isExplorable;

          return (
            <button
              key={node.id}
              className={`region-tile${status ? ` region-tile-${status.status}` : ""}${clickable ? "" : " region-tile-disabled"}`}
              onClick={() => handleTileClick(node)}
              disabled={!clickable}
            >
              <span className="region-tile-name">{node.label}</span>
              {node.sublabel && <span className="region-tile-sublabel">{node.sublabel}</span>}

              {status && (
                <span className="region-tile-status">
                  <span
                    className={`level-dot level-${status.status === "normal" ? "low" : status.status === "elevated" ? "medium" : "high"}`}
                  />
                  {STATUS_LABEL[status.status]}
                </span>
              )}
              {status && (
                <span className="region-tile-peak">{Math.round(status.forecast_peak_mw).toLocaleString()} MW forecast peak</span>
              )}

              {isExplorable && !isLive && <span className="region-tile-hint">View sub-divisions →</span>}
              {!clickable && <span className="region-tile-hint">Data not yet available</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
