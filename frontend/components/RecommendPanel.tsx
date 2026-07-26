"use client";

import { useState } from "react";
import { getRecommendation } from "@/lib/api";
import { RecommendationResponse } from "@/lib/types";

export default function RecommendPanel({ region }: { region: string }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RecommendationResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getRecommendation(region, question.trim());
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get a recommendation.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <p className="card-title">Ask the grid copilot</p>
      <p className="card-subtitle">Grounded in operating procedures and the current forecast for this region.</p>

      <form className="recommend-form" onSubmit={handleSubmit}>
        <input
          className="recommend-input"
          type="text"
          placeholder="e.g. How should we handle tonight's peak?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="button" type="submit" disabled={loading || !question.trim()}>
          {loading ? "Asking…" : "Ask"}
        </button>
      </form>

      {error && <div className="error-banner">{error}</div>}

      {!error && !result && !loading && <p className="empty-state">Ask a question to get a grounded recommendation.</p>}

      {result && (
        <div>
          <p className="recommend-answer">{result.answer}</p>
          {result.sources.length > 0 && (
            <div>
              <p className="sources-title">Sources</p>
              {result.sources.map((source, i) => (
                <div className="source-card" key={`${source.source}-${i}`}>
                  <div className="source-head">
                    <span className="source-title">{source.title}</span>
                    <span className="source-similarity">{Math.round(source.similarity * 100)}% match</span>
                  </div>
                  <p className="source-name">{source.source}</p>
                  <p className="source-excerpt">{source.excerpt}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
