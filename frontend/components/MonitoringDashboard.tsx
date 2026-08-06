"use client";

import { useEffect, useState } from "react";
import { getMonitoringDashboard } from "@/lib/api";
import { MonitoringDashboard as MonitoringDashboardData } from "@/lib/types";

const POLL_INTERVAL_MS = 30_000;

function StatRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat-row-item">
      <span className="stat-row-label">{label}</span>
      <span className="stat-row-value">{value}</span>
    </div>
  );
}

export default function MonitoringDashboard() {
  const [data, setData] = useState<MonitoringDashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    function poll() {
      getMonitoringDashboard()
        .then((d) => {
          if (!cancelled) {
            setData(d);
            setError(null);
          }
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load monitoring data.");
        });
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return <p className="empty-state">Loading monitoring data…</p>;

  return (
    <div>
      <p className="monitoring-caveat">
        Real numbers from live requests only — this intentionally does not show retrieval accuracy or recall,
        since those require a golden set with known-correct answers, not something a live query has. See the eval
        suite (<code>python -m app.evals.run</code>) for those.
      </p>

      <div className="monitoring-grid">
        <div className="card">
          <p className="card-title">RAG / LLM</p>
          <StatRow label="Queries (last 200)" value={data.rag.queries} />
          <StatRow label="Errors" value={data.rag.errors} />
          <StatRow label="Cache hits" value={data.rag.cache_hits} />
          <StatRow label="Avg latency" value={data.rag.avg_latency_ms ? `${Math.round(data.rag.avg_latency_ms).toLocaleString()} ms` : "—"} />
          <StatRow label="Total tokens (in/out)" value={`${data.rag.total_input_tokens.toLocaleString()} / ${data.rag.total_output_tokens.toLocaleString()}`} />
          <StatRow label="Total cost" value={`$${data.rag.total_estimated_cost_usd.toFixed(4)}`} />
          <StatRow label="Avg cost / query" value={data.rag.avg_cost_per_query_usd ? `$${data.rag.avg_cost_per_query_usd.toFixed(6)}` : "—"} />
        </div>

        <div className="card">
          <p className="card-title">Alerts</p>
          <StatRow label="Surges detected" value={data.alerts.surges_detected} />
          <StatRow label="Pending" value={data.alerts.pending} />
          <StatRow label="Approved" value={data.alerts.approved} />
          <StatRow label="Rejected" value={data.alerts.rejected} />
          <StatRow label="High severity" value={data.alerts.high_severity} />
          <StatRow label="Notifications sent" value={data.alerts.notifications_sent} />
          <StatRow label="Notifications failed" value={data.alerts.notifications_failed} />
        </div>

        <div className="card">
          <p className="card-title">Feedback</p>
          <StatRow label="Total ratings" value={data.feedback.total} />
          <StatRow label="👍 Helpful" value={data.feedback.up} />
          <StatRow label="👎 Not helpful" value={data.feedback.down} />
        </div>
      </div>
    </div>
  );
}
