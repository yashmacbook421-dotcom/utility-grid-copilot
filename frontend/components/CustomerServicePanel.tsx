"use client";

import { useEffect, useState } from "react";
import {
  askCustomerService,
  getOutageStatus,
  listCustomers,
  openCase,
  summarizeCase,
} from "@/lib/api";
import { AskCaseResponse, CustomerInfo, OutageStatus } from "@/lib/types";
import SourceCard from "@/components/SourceCard";

const CONFIDENCE_LABEL: Record<AskCaseResponse["confidence"], string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

interface Turn {
  question: string;
  response: AskCaseResponse;
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });
}

export default function CustomerServicePanel() {
  const [agentId, setAgentId] = useState("rep-demo");
  const [customers, setCustomers] = useState<CustomerInfo[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");
  const [serviceArea, setServiceArea] = useState<string>("");

  const [caseId, setCaseId] = useState<string | null>(null);
  const [caseStatus, setCaseStatus] = useState<string>("open");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"standard" | "routed">("standard");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [outage, setOutage] = useState<OutageStatus | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);

  const selectedCustomer = customers.find((c) => c.customer_id === selectedCustomerId) ?? null;

  useEffect(() => {
    listCustomers()
      .then(setCustomers)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load customers."));
  }, []);

  useEffect(() => {
    if (selectedCustomer) setServiceArea(selectedCustomer.service_area);
  }, [selectedCustomer]);

  useEffect(() => {
    if (!serviceArea) {
      setOutage(null);
      return;
    }
    let cancelled = false;
    getOutageStatus(serviceArea)
      .then((data) => {
        if (!cancelled) setOutage(data);
      })
      .catch(() => {
        if (!cancelled) setOutage(null);
      });
    return () => {
      cancelled = true;
    };
  }, [serviceArea]);

  function resetCase() {
    setCaseId(null);
    setCaseStatus("open");
    setTurns([]);
    setSummary(null);
    setError(null);
  }

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      let activeCaseId = caseId;
      if (!activeCaseId) {
        const opened = await openCase(agentId || "rep-demo", selectedCustomerId || undefined, serviceArea || undefined);
        activeCaseId = opened.id;
        setCaseId(opened.id);
      }
      const response = await askCustomerService(activeCaseId, question.trim(), mode);
      setTurns((prev) => [...prev, { question: question.trim(), response }]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get a response.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSummarize() {
    if (!caseId || summarizing) return;
    setSummarizing(true);
    setError(null);
    try {
      const result = await summarizeCase(caseId);
      setSummary(result.summary);
      setCaseStatus(result.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate a case summary.");
    } finally {
      setSummarizing(false);
    }
  }

  const lastEscalation = [...turns].reverse().find((t) => t.response.escalation.required)?.response.escalation;

  return (
    <div className="cs-workspace">
      <div className="card">
        <p className="step-label">Step 1 · Identify the case</p>
        <div className="cs-identify-grid">
          <label className="cs-field">
            <span>Representative ID</span>
            <input className="recommend-input" value={agentId} onChange={(e) => setAgentId(e.target.value)} />
          </label>
          <label className="cs-field">
            <span>Customer</span>
            <select
              className="select"
              value={selectedCustomerId}
              onChange={(e) => {
                setSelectedCustomerId(e.target.value);
                resetCase();
              }}
            >
              <option value="">— No customer selected —</option>
              {customers.map((c) => (
                <option key={c.customer_id} value={c.customer_id}>
                  {c.name} ({c.customer_id})
                </option>
              ))}
            </select>
          </label>
          <label className="cs-field">
            <span>Service area</span>
            <input
              className="recommend-input"
              value={serviceArea}
              onChange={(e) => {
                setServiceArea(e.target.value);
                resetCase();
              }}
              placeholder="e.g. Folsom"
            />
          </label>
        </div>

        {selectedCustomer && (
          <div className="cs-customer-info">
            <div>
              <span className="why-alert-label">Customer ID</span>
              <span className="why-alert-value">{selectedCustomer.customer_id}</span>
            </div>
            <div>
              <span className="why-alert-label">Name</span>
              <span className="why-alert-value">{selectedCustomer.name}</span>
            </div>
            <div>
              <span className="why-alert-label">Address</span>
              <span className="why-alert-value">
                {selectedCustomer.address}, {selectedCustomer.zip}
              </span>
            </div>
            <div>
              <span className="why-alert-label">Service status</span>
              <span className="why-alert-value">{selectedCustomer.service_status}</span>
            </div>
            <div>
              <span className="why-alert-label">Account status</span>
              <span className="why-alert-value">{selectedCustomer.account_status}</span>
            </div>
          </div>
        )}

        {outage && (
          <div className={`cs-outage-card cs-outage-${outage.status}`}>
            <p className="step-label" style={{ margin: "0 0 8px" }}>
              Outage status — {outage.area}
            </p>
            <div className="cs-outage-grid">
              <div>
                <span className="why-alert-label">Status</span>
                <span className="why-alert-value">{outage.status}</span>
              </div>
              <div>
                <span className="why-alert-label">Customers affected</span>
                <span className="why-alert-value">{outage.customers_affected}</span>
              </div>
              {outage.cause && (
                <div>
                  <span className="why-alert-label">Cause</span>
                  <span className="why-alert-value">{outage.cause}</span>
                </div>
              )}
              {outage.crew_status && (
                <div>
                  <span className="why-alert-label">Crew status</span>
                  <span className="why-alert-value">{outage.crew_status}</span>
                </div>
              )}
              {outage.estimated_restoration && (
                <div>
                  <span className="why-alert-label">Estimated restoration</span>
                  <span className="why-alert-value">{formatTime(outage.estimated_restoration)}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <p className="step-label">Step 2 · Customer question</p>
        <p className="card-subtitle">e.g. &ldquo;My customer says their power is out. When will it be restored?&rdquo;</p>

        {lastEscalation && (
          <div className="cs-escalation-banner">
            <strong>Escalation required</strong> — reason: {lastEscalation.reason ?? "unspecified"}. Follow the
            escalation procedure in Customer Service SOPs before closing this case.
          </div>
        )}

        <div className="mode-toggle" role="radiogroup" aria-label="Answer mode">
          <button
            type="button"
            className={`mode-toggle-button${mode === "standard" ? " mode-toggle-active" : ""}`}
            onClick={() => setMode("standard")}
            aria-pressed={mode === "standard"}
          >
            Standard
          </button>
          <button
            type="button"
            className={`mode-toggle-button${mode === "routed" ? " mode-toggle-active" : ""}`}
            onClick={() => setMode("routed")}
            aria-pressed={mode === "routed"}
          >
            Cost-routed (cheap model gathers, strong model answers)
          </button>
        </div>
        <p className="mode-toggle-hint">
          {mode === "routed"
            ? "A cheaper model decides which tools to call; the stronger model only writes the final answer. Usually cheaper, occasionally misses a document the standard mode would have found — shown here to demonstrate the tradeoff."
            : "One model handles tool selection and the final answer end to end — the more thorough, more expensive default."}
        </p>

        <form className="recommend-form" onSubmit={handleAsk}>
          <input
            className="recommend-input"
            type="text"
            placeholder="Type the customer's question here"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            spellCheck
          />
          <button className="button" type="submit" disabled={loading || !question.trim() || caseStatus === "closed"}>
            {loading ? "Thinking…" : "Ask"}
          </button>
        </form>

        {error && <div className="error-banner">{error}</div>}
        {caseStatus === "closed" && <p className="empty-state">This case is closed. Select a new customer or area to start another.</p>}
        {!error && turns.length === 0 && !loading && <p className="empty-state">Ask a question above to get a grounded answer.</p>}

        {turns.map((turn, i) => (
          <div key={i} className="cs-turn">
            <p className="cs-turn-question">&ldquo;{turn.question}&rdquo;</p>

            <div className="cs-confidence-row">
              <span className={`cs-confidence-badge cs-confidence-${turn.response.confidence}`}>
                {CONFIDENCE_LABEL[turn.response.confidence]}
              </span>
              {turn.response.escalation.required && (
                <span className="severity-badge severity-high">Escalation: {turn.response.escalation.reason}</span>
              )}
              <span className="cs-mode-cost-badge">
                {turn.response.mode === "routed" ? "Cost-routed" : "Standard"}
                {turn.response.estimated_cost_usd !== null && ` · $${turn.response.estimated_cost_usd.toFixed(5)}`}
              </span>
            </div>

            {turn.response.warnings.length > 0 && (
              <div className="error-banner">
                {turn.response.warnings.map((w, wi) => (
                  <p key={wi}>{w}</p>
                ))}
              </div>
            )}

            <div className="answer-headline markdown-body">
              <p>{turn.response.customer_response}</p>
            </div>

            <details className="details-toggle">
              <summary>Show internal analysis (not for the customer)</summary>
              <div className="details-body markdown-body">
                <p>{turn.response.internal_analysis || "—"}</p>
              </div>
            </details>

            {turn.response.tool_calls.length > 0 && (
              <details className="details-toggle">
                <summary>
                  Show tool-use trace ({turn.response.tool_calls.length} call
                  {turn.response.tool_calls.length === 1 ? "" : "s"}, {turn.response.iterations} iteration
                  {turn.response.iterations === 1 ? "" : "s"})
                </summary>
                <div className="details-body">
                  <ol className="tool-call-trace">
                    {turn.response.tool_calls.map((call, ci) => (
                      <li key={ci}>
                        <span className="tool-call-name">{call.tool}</span>
                        <code className="tool-call-input">{JSON.stringify(call.input)}</code>
                        <span className="tool-call-summary">{call.summary}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              </details>
            )}

            {turn.response.sources.length > 0 && (
              <details className="details-toggle">
                <summary>
                  Show sources ({turn.response.sources.length} source{turn.response.sources.length === 1 ? "" : "s"})
                </summary>
                <div className="details-body">
                  {turn.response.sources.map((source, si) => (
                    <SourceCard source={source} key={`${source.source}-${si}`} />
                  ))}
                </div>
              </details>
            )}
          </div>
        ))}

        {caseId && turns.length > 0 && caseStatus !== "closed" && (
          <div className="cs-summary-row">
            <button className="button button-outline" onClick={handleSummarize} disabled={summarizing}>
              {summarizing ? "Generating…" : "Generate case summary"}
            </button>
          </div>
        )}

        {summary && (
          <div className="cs-summary-block">
            <p className="step-label">Case summary (saved, case closed)</p>
            <pre className="cs-summary-text">{summary}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
