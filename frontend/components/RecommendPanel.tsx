"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { getAgenticRecommendation, getRecommendation, submitFeedback } from "@/lib/api";
import { AgenticRecommendationResponse, RecommendationResponse } from "@/lib/types";
import SourceCard from "@/components/SourceCard";
import { splitBottomLine } from "@/lib/answerFormat";

const DOWN_REASONS = ["Wrong information", "Poor source", "Missing information", "Irrelevant answer", "Other"];

type Mode = "deterministic" | "agentic";

export default function RecommendPanel({ region }: { region: string }) {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<Mode>("deterministic");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RecommendationResponse | AgenticRecommendationResponse | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<"up" | "down" | null>(null);
  const [showDownReasons, setShowDownReasons] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    setFeedbackGiven(null);
    setShowDownReasons(false);
    try {
      const res =
        mode === "agentic"
          ? await getAgenticRecommendation(region, question.trim())
          : await getRecommendation(region, question.trim());
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get a recommendation.");
    } finally {
      setLoading(false);
    }
  }

  async function handleFeedback(rating: "up" | "down", reason?: string) {
    if (!result?.request_log_id) return;
    if (rating === "down" && !reason) {
      setShowDownReasons(true);
      return;
    }
    setFeedbackGiven(rating);
    setShowDownReasons(false);
    try {
      await submitFeedback(result.request_log_id, rating, reason);
    } catch {
      // Non-critical — the UI already shows "thanks," no need to surface a retry.
    }
  }

  return (
    <div className="card">
      <p className="step-label">Step 2 · Ask your question</p>
      <p className="card-subtitle">e.g. &ldquo;How should we handle tonight&rsquo;s peak?&rdquo;</p>

      <div className="mode-toggle" role="radiogroup" aria-label="Recommendation mode">
        <button
          type="button"
          className={`mode-toggle-button${mode === "deterministic" ? " mode-toggle-active" : ""}`}
          onClick={() => setMode("deterministic")}
          aria-pressed={mode === "deterministic"}
        >
          Deterministic
        </button>
        <button
          type="button"
          className={`mode-toggle-button${mode === "agentic" ? " mode-toggle-active" : ""}`}
          onClick={() => setMode("agentic")}
          aria-pressed={mode === "agentic"}
        >
          Agentic (Claude picks its own tools)
        </button>
      </div>
      <p className="mode-toggle-hint">
        {mode === "agentic"
          ? "Claude decides for itself whether to search procedures and/or check the forecast, and how many times — usually slower and costlier, shown here to demonstrate the tradeoff."
          : "Retrieval and forecast are always both fetched first, then one Claude call — predictable cost and latency."}
      </p>

      <form className="recommend-form" onSubmit={handleSubmit}>
        <input
          className="recommend-input"
          type="text"
          placeholder="Type your question here"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          spellCheck
          autoCorrect="on"
          autoCapitalize="sentences"
          lang="en"
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
          {result.sources.length === 0 && (
            <div className="error-banner">
              <p>No matching procedures were found for this question — double-check the spelling, or try rephrasing it.</p>
            </div>
          )}

          {(() => {
            const { headline, rest } = splitBottomLine(result.answer);
            if (!headline) {
              return (
                <div className="recommend-answer markdown-body">
                  <ReactMarkdown>{result.answer}</ReactMarkdown>
                </div>
              );
            }
            return (
              <div className="recommend-answer">
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

          {"tool_calls" in result && (
            <details className="details-toggle">
              <summary>
                Show tool-use trace ({result.tool_calls.length} call{result.tool_calls.length === 1 ? "" : "s"},{" "}
                {result.iterations} iteration{result.iterations === 1 ? "" : "s"})
              </summary>
              <div className="details-body">
                {result.tool_calls.length === 0 ? (
                  <p className="empty-state">Claude answered without calling any tools.</p>
                ) : (
                  <ol className="tool-call-trace">
                    {result.tool_calls.map((call, i) => (
                      <li key={i}>
                        <span className="tool-call-name">{call.tool}</span>
                        <code className="tool-call-input">{JSON.stringify(call.input)}</code>
                        <span className="tool-call-summary">{call.summary}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </details>
          )}

          {result.sources.length > 0 && (
            <details className="details-toggle">
              <summary>Show how this answer was found ({result.sources.length} source{result.sources.length === 1 ? "" : "s"})</summary>
              <div className="details-body">
                {result.sources.map((source, i) => (
                  <SourceCard source={source} key={`${source.source}-${i}`} />
                ))}
              </div>
            </details>
          )}

          {result.request_log_id && (
            <div className="feedback-row">
              {feedbackGiven ? (
                <p className="feedback-thanks">Thanks for your feedback.</p>
              ) : (
                <>
                  <span className="feedback-label">Was this answer helpful?</span>
                  <button className="feedback-button" onClick={() => handleFeedback("up")} aria-label="Helpful">
                    👍
                  </button>
                  <button className="feedback-button" onClick={() => handleFeedback("down")} aria-label="Not helpful">
                    👎
                  </button>
                </>
              )}
              {showDownReasons && !feedbackGiven && (
                <div className="feedback-reasons">
                  {DOWN_REASONS.map((reason) => (
                    <button key={reason} className="feedback-reason-button" onClick={() => handleFeedback("down", reason)}>
                      {reason}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
