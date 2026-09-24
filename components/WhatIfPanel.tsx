"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { getWhatIfForecast } from "@/lib/api";
import { WhatIfResponse } from "@/lib/types";
import SourceCard from "@/components/SourceCard";
import { splitBottomLine } from "@/lib/answerFormat";

export default function WhatIfPanel({ region }: { region: string }) {
  const [percentChange, setPercentChange] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<WhatIfResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await getWhatIfForecast(region, 1 + percentChange / 100);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to compute the scenario.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <p className="step-label">Step 3 · What if demand changes?</p>
      <p className="card-subtitle">Scale tonight&rsquo;s forecast and see if it would trigger a surge.</p>

      <form className="recommend-form" onSubmit={handleSubmit}>
        <input
          className="recommend-input"
          type="number"
          step={5}
          value={percentChange}
          onChange={(e) => setPercentChange(Number(e.target.value))}
          aria-label="Percent demand change"
          style={{ flex: "0 0 100px" }}
        />
        <span className="whatif-suffix">% change in demand</span>
        <button className="button" type="submit" disabled={loading}>
          {loading ? "Calculating…" : "Run scenario"}
        </button>
      </form>

      {error && <div className="error-banner">{error}</div>}

      {result && (
        <div>
          <p className="forecast-summary-text">
            At <strong>{result.demand_multiplier}x</strong> demand, the forecast peak would be{" "}
            <strong>{Math.round(result.peak_forecast_mw).toLocaleString()} MW</strong> — this region&rsquo;s typical
            high end is around <strong>{Math.round(result.baseline_p95_mw).toLocaleString()} MW</strong>.
          </p>

          {result.would_exceed_baseline ? (
            <div className="error-banner">
              <p>⚠️ This scenario would exceed the normal range — likely a surge event.</p>
            </div>
          ) : (
            <p className="empty-state">This scenario stays within the normal range.</p>
          )}

          {result.explanation && (() => {
            const { headline, rest } = splitBottomLine(result.explanation);
            if (!headline) {
              return (
                <div className="markdown-body" style={{ marginTop: 16 }}>
                  <ReactMarkdown>{result.explanation}</ReactMarkdown>
                </div>
              );
            }
            return (
              <div style={{ marginTop: 16 }}>
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

          {result.sources.length > 0 && (
            <details className="details-toggle">
              <summary>Show how this was found ({result.sources.length} source{result.sources.length === 1 ? "" : "s"})</summary>
              <div className="details-body">
                {result.sources.map((source, i) => (
                  <SourceCard source={source} key={`${source.source}-${i}`} />
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
