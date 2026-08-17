# Utility Grid Copilot

A demand-forecasting and grid-operations copilot for utility operators.
Combines a trained ML forecasting model with a Claude-powered RAG pipeline
grounded in real regulatory/reliability documents (NERC, CAISO, FERC, CPUC)
plus a set of hand-written procedures, so every recommendation is traceable
back to a specific document, page, and section — not a black box.

Built as a working demonstration of the full AI-engineering stack: RAG,
retrieval evaluation, guardrails, agentic patterns, observability, and
production hardening — see [ARCHITECTURE.md](ARCHITECTURE.md) for the "why"
behind every non-obvious decision.

## Quickstart

```bash
git clone <this repo>
cd utility-grid-copilot
cp backend/.env.example backend/.env   # fill in ANTHROPIC_API_KEY at minimum
docker compose up -d --build
```

That starts the database, backend, and frontend, and self-seeds real demand
history (via the EIA API, for California/SMUD/Georgia), the hand-written
grid-ops procedure documents, and the customer-service knowledge base
automatically on first boot. Open **http://localhost:3000**.

### Adding the real document corpus

The self-seeding on startup only covers the synthetic procedures. To pull
in the real NERC/CAISO/FERC/CPUC documents (see
[knowledge_base/README.md](backend/knowledge_base/README.md)):

```bash
docker compose exec backend python -m knowledge_base.download_and_ingest
```

This downloads each document listed in `knowledge_base/download_manifest.py`
(only once — safe to re-run, it skips anything already ingested), extracts
text page-by-page, detects section headings, chunks, embeds, and stores
everything with full citation metadata (page number, section, source URL).

### Running the eval suite

```bash
cd backend
python -m app.evals.run              # retrieval + LLM-judged answer quality
python -m app.evals.run --no-judge    # retrieval only, no Claude calls, free
python -m app.evals.compare           # retrieval strategy + pipeline comparison, real measured numbers
```

### Running tests

```bash
cd backend
pytest tests/ -v
```

## What's in here

| Topic | Where |
|---|---|
| Demand forecasting (gradient-boosted quantile regression) | `backend/app/services/forecasting.py` |
| RAG pipeline (chunk, embed, retrieve, cite, ground) | `backend/app/services/rag.py` |
| Real document ingestion (PDF, page/section-aware) | `backend/app/services/pdf_ingest.py` |
| Agentic tool-use loop | `backend/app/services/agentic.py` |
| Proactive surge-watching agent (human approval gate) | `backend/app/services/surge_watcher.py` |
| Eval harness (golden set, retrieval + answer metrics) | `backend/app/evals/` |
| Retrieval strategy / pipeline comparison (real measured results) | `backend/app/evals/compare.py` |
| Guardrails (citation faithfulness, injection resistance) | `backend/app/services/rag.py`, `backend/app/evals/golden_set.py` |
| Observability (per-request cost/latency logging) | `backend/app/services/observability.py` |
| Regional demand data (real EIA data: California, SMUD, Georgia) | `backend/app/services/eia_ingest.py`, `backend/app/data/regions.py` |
| Customer Service Agent Assist (outage/billing tools, confidence + escalation guardrails, case summaries) | `backend/app/services/customer_service_agent.py`, `backend/app/routers/customer_service.py` |
| Cost-routed mode (cheap model gathers tool data, strong model writes the final answer) | `backend/app/services/customer_service_agent.py` (`run_customer_service_turn_routed`), `backend/app/evals/customer_service_cost_comparison.py` |

Full reasoning behind each decision — why no reranker in production, why
the similarity threshold is what it is, what's been measured vs. assumed —
is in [ARCHITECTURE.md](ARCHITECTURE.md), not just the code comments.

## Known limitations

- The hand-written grid-ops procedure documents are stand-ins, not real
  vetted utility SOPs — labeled `organization="synthetic"` throughout so
  this is never ambiguous. Same is true of the customer-service knowledge
  base (`organization="customer_service"`).
- Section detection on real PDFs is regex-based heuristics, tuned against
  the actual documents in this corpus — not guaranteed to generalize to
  arbitrarily different document layouts without further tuning.
- Deployment is documented ([DEPLOYMENT.md](DEPLOYMENT.md)) but not
  currently live — this runs locally via Docker Compose only.
- Customer Service Agent Assist's customer/outage/billing data
  (`backend/app/data/customer_service_demo_data.py`) is static synthetic
  fixtures, not a live CIS/OMS integration — confidence and escalation are
  deterministic rules, not a separate model-graded judgment.

See ARCHITECTURE.md's "Scaling notes" section for the full, honest list.
