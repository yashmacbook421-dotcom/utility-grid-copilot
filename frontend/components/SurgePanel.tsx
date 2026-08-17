"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { approveSurge, listPendingSurges, rejectSurge, triggerDemoSurge } from "@/lib/api";
import { SurgeEvent } from "@/lib/types";
import SourceCard from "@/components/SourceCard";
import { splitBottomLine } from "@/lib/answerFormat";
import { formatRegionLabel } from "@/components/RegionSelect";

const POLL_INTERVAL_MS = 30_000;

export default function SurgePanel({ region }: { region: string }) {
  const [surges, setSurges] = useState<SurgeEvent[]>([]);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    function poll() {
      listPendingSurges(region)
        .then((list) => {
          if (!cancelled) setSurges(list);
        })
        .catch(() => {
          // Silent: this is a background convenience panel, not a critical path —
          // a failed poll just tries again next interval.
        });
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [region]);

  async function handleDemoTrigger() {
    setTriggering(true);
    setTriggerError(null);
    try {
      await triggerDemoSurge(region);
      const list = await listPendingSurges(region);
      setSurges(list);
    } catch (err) {
      setTriggerError(err instanceof Error ? err.message : "Failed to trigger a demo surge.");
    } finally {
      setTriggering(false);
    }
  }

  async function handleResolve(id: string, action: "approve" | "reject") {
    setResolvingId(id);
    try {
      if (action === "approve") await approveSurge(id);
      else await rejectSurge(id);
      setSurges((prev) => prev.filter((s) => s.id !== id));
    } catch {
      // Leave it in the list — the next poll will reconcile the true state.
    } finally {
      setResolvingId(null);
    }
  }

  return (
    <div className={`card surge-panel${surges.length === 0 ? " surge-panel-idle" : ""}`}>
      <div className="surge-panel-header">
        <p className="step-label" style={{ margin: 0 }}>
          {surges.length > 0 ? "Grid Copilot noticed something" : "No active alerts"}
        </p>
        <button className="button button-outline button-small" onClick={handleDemoTrigger} disabled={triggering}>
          {triggering ? "Triggering…" : `Trigger demo surge (${formatRegionLabel(region)})`}
        </button>
      </div>
      {triggerError && <div className="error-banner" style={{ marginTop: 12 }}>{triggerError}</div>}

      {surges.map((surge) => {
        const deviationPct = (surge.forecast_peak_mw / surge.baseline_p95_mw - 1) * 100;
        return (
        <div className="surge-card" key={surge.id}>
          <div className="surge-headline-row">
            <p className="surge-headline">
              Demand surge expected for <strong>{formatRegionLabel(surge.region)}</strong> —{" "}
              {Math.round(surge.forecast_peak_mw).toLocaleString()} MW around{" "}
              {new Date(surge.peak_forecast_time).toLocaleString(undefined, {
                weekday: "long",
                hour: "numeric",
                minute: "2-digit",
              })}
              , above its typical high end (~{Math.round(surge.baseline_p95_mw).toLocaleString()} MW).
            </p>
            <span className={`severity-badge severity-${surge.severity}`}>{surge.severity} severity</span>
          </div>

          <details className="details-toggle">
            <summary>Why this alert triggered</summary>
            <div className="details-body why-alert-grid">
              <div>
                <span className="why-alert-label">Forecast peak</span>
                <span className="why-alert-value">{Math.round(surge.forecast_peak_mw).toLocaleString()} MW</span>
              </div>
              <div>
                <span className="why-alert-label">Normal high end (95th percentile, 30d)</span>
                <span className="why-alert-value">{Math.round(surge.baseline_p95_mw).toLocaleString()} MW</span>
              </div>
              <div>
                <span className="why-alert-label">Deviation</span>
                <span className="why-alert-value">+{deviationPct.toFixed(1)}%</span>
              </div>
              <div>
                <span className="why-alert-label">Forecast model</span>
                <span className="why-alert-value">HistGradientBoostingRegressor</span>
              </div>
              <div>
                <span className="why-alert-label">Notification</span>
                <span className="why-alert-value">
                  {surge.notified ? "Sent" : surge.notification_error ? "Failed" : "Not configured"}
                </span>
              </div>
            </div>
          </details>

          {(() => {
            const { headline, rest } = splitBottomLine(surge.recommended_action);
            if (!headline) {
              return (
                <div className="surge-recommendation markdown-body">
                  <ReactMarkdown>{surge.recommended_action}</ReactMarkdown>
                </div>
              );
            }
            return (
              <div className="surge-recommendation">
                <div className="answer-headline markdown-body">
                  <ReactMarkdown>{headline}</ReactMarkdown>
                </div>
                {rest && (
                  <details className="details-toggle">
                    <summary>Show full reasoning</summary>
                    <div className="details-body markdown-body">
                      <ReactMarkdown>{rest}</ReactMarkdown>
                    </div>
                  </details>
                )}
              </div>
            );
          })()}

          {surge.sources.length > 0 && (
            <details className="details-toggle">
              <summary>Show how this was found ({surge.sources.length} source{surge.sources.length === 1 ? "" : "s"})</summary>
              <div className="details-body">
                {surge.sources.map((source, i) => (
                  <SourceCard source={source} key={`${source.source}-${i}`} />
                ))}
              </div>
            </details>
          )}

          <div className="surge-actions">
            <button
              className="button"
              disabled={resolvingId === surge.id}
              onClick={() => handleResolve(surge.id, "approve")}
            >
              Approve
            </button>
            <button
              className="button button-outline"
              disabled={resolvingId === surge.id}
              onClick={() => handleResolve(surge.id, "reject")}
            >
              Reject
            </button>
          </div>
        </div>
        );
      })}
    </div>
  );
}
