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
      <p className="step-label">Step 2 · Ask your question</p>
      <p className="card-subtitle">e.g. &ldquo;How should we handle tonight&rsquo;s peak?&rdquo;</p>

      <form className="recommend-form" onSubmit={handleSubmit}>
        <input
          className="recommend-input"
          type="text"
          placeholder="Type your question here"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="button" type="submit" disabled={loading || !question.trim()}>
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      {error && <div className="error-banner">{error}</div>}

      {!error && !result && !loading && <p className="empty-state">Ask a question above to get an answer.</p>}

      {result && (
        <div>
          {result.warnings.length > 0 && (
            <div className="error-banner">
              {result.warnings.map((warning, i) => (
                <p key={i}>{warning}</p>
              ))}
            </div>
          )}
          <p className="recommend-answer">{result.answer}</p>

          {result.sources.length > 0 && (
            <details className="details-toggle">
              <summary>Show how this answer was found ({result.sources.length} source{result.sources.length === 1 ? "" : "s"})</summary>
              <div className="details-body">
                {result.sources.map((source, i) => (
                  <div className="source-card" key={`${source.source}-${i}`}>
                    <div className="source-head">
                      <span className="source-title">{source.title}</span>
                      <span className="source-similarity">{Math.round(source.similarity * 100)}% relevant</span>
                    </div>
                    <p className="source-name">{source.source}</p>
                    <p className="source-excerpt">{source.excerpt}</p>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
