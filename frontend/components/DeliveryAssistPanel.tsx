"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { askDeliveryAssist } from "@/lib/api";
import { DeliveryAskResponse } from "@/lib/types";
import SourceCard from "@/components/SourceCard";
import { splitBottomLine } from "@/lib/answerFormat";

const AREAS = ["Billing & Payments", "Rate Configuration", "Meter Data Management", "Work & Asset Management"];

// One example per area, chosen so the demo shows both a well-covered
// question (high/medium confidence) and the one area's corpus that
// deliberately doesn't cover crew scheduling (see
// work-order-prioritization-basics.md) — a real low-confidence escalation,
// not a staged one.
const EXAMPLE_QUESTIONS: Record<string, string> = {
  "Billing & Payments": "What's the standard approach for a fixed monthly service charge?",
  "Rate Configuration": "How is a mid-cycle rate schedule change typically handled?",
  "Meter Data Management": "How should we handle failed usage validations during the meter-data load?",
  "Work & Asset Management": "How do we configure crew shift patterns across overlapping emergency work orders?",
};

const CONFIDENCE_PILL: Record<DeliveryAskResponse["confidence"], string> = {
  high: "status-pill-ok",
  medium: "status-pill-watch",
  low: "status-pill-alert",
};

export default function DeliveryAssistPanel() {
  const [area, setArea] = useState(AREAS[0]!);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<DeliveryAskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flagged, setFlagged] = useState(false);

  async function handleAsk(askedArea: string, q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setFlagged(false);
    try {
      const data = await askDeliveryAssist(askedArea, q);
      setResult(data);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Failed to get an answer.");
    } finally {
      setLoading(false);
    }
  }

  function handleExample(exampleArea: string) {
    const q = EXAMPLE_QUESTIONS[exampleArea]!;
    setArea(exampleArea);
    setQuestion(q);
    handleAsk(exampleArea, q);
  }

  const { headline, rest } = result ? splitBottomLine(result.answer) : { headline: "", rest: "" };

  return (
    <div className="card">
      <p className="step-label">Product area</p>
      <div className="mode-toggle">
        {AREAS.map((a) => (
          <button
            key={a}
            className={`mode-toggle-button${area === a ? " mode-toggle-active" : ""}`}
            onClick={() => {
              setArea(a);
              setResult(null);
            }}
          >
            {a}
          </button>
        ))}
      </div>

      <form
        className="recommend-form"
        style={{ marginTop: 16 }}
        onSubmit={(e) => {
          e.preventDefault();
          handleAsk(area, question);
        }}
      >
        <input
          className="recommend-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a configuration or process question…"
        />
        <button className="button" type="submit" disabled={loading || !question.trim()}>
          {loading ? "Asking…" : "Ask"}
        </button>
      </form>

      {error && (
        <div className="error-banner" style={{ marginTop: 16 }}>
          {error}
        </div>
      )}

      {!result && !loading && !error && (
        <div className="empty-state">
          <p style={{ marginBottom: 8 }}>Try an example:</p>
          <div className="example-question-row">
            {AREAS.map((a) => (
              <button key={a} className="button button-outline button-small" onClick={() => handleExample(a)}>
                {a}
              </button>
            ))}
          </div>
        </div>
      )}

      {result && (
        <div style={{ marginTop: 20 }}>
          {result.escalation.required && (
            <div className="feature-panel" style={{ marginBottom: 16 }}>
              <p className="feature-panel-title">Outside verified scope — flag for SME review</p>
              <p className="feature-panel-body">
                Confidence is low, or this question is outside what this area&apos;s knowledge base covers. Treat
                the answer below as a starting point only — a subject-matter expert should verify it before it
                reaches the client.
              </p>
              {!flagged ? (
                <button className="feature-panel-action" onClick={() => setFlagged(true)}>
                  Flag for SME review
                </button>
              ) : (
                <p className="feature-panel-flagged">Flagged — queued for SME review</p>
              )}
            </div>
          )}

          {result.warnings.length > 0 && (
            <div className="error-banner" style={{ marginBottom: 16 }}>
              {result.warnings.join(" ")}
            </div>
          )}

          <div className="row-between">
            <p className="step-label" style={{ margin: 0 }}>
              Grounded answer · {result.area}
            </p>
            <span className={`status-pill ${CONFIDENCE_PILL[result.confidence]}`}>
              <span className="dot" />
              {result.confidence} confidence
            </span>
          </div>

          {headline ? (
            <>
              <div className="answer-headline markdown-body" style={{ marginTop: 12 }}>
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
            </>
          ) : (
            <div className="markdown-body" style={{ marginTop: 12 }}>
              <ReactMarkdown>{result.answer}</ReactMarkdown>
            </div>
          )}

          {result.sources.length > 0 && (
            <details className="details-toggle">
              <summary>
                Show sources ({result.sources.length} source{result.sources.length === 1 ? "" : "s"})
              </summary>
              <div className="details-body">
                {result.sources.map((s, i) => (
                  <SourceCard source={s} key={`${s.title}-${i}`} />
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      <div className="illustrative-note">
        <strong>Illustrative content, honest scope.</strong>
        Every answer and source here is retrieved from a small set of generic, clearly-labeled example
        implementation patterns — not real vendor documentation. In production this would retrieve from the
        client&apos;s own verified configuration guides, with the same SME escalation whenever confidence is low.
      </div>
    </div>
  );
}
