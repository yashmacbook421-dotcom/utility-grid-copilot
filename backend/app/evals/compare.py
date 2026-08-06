"""Compares retrieval strategies and pipeline patterns against the golden
set — a separate entrypoint from run.py (which stays the CI-friendly
single-strategy gate, unchanged). Run after the DB is seeded:

    cd backend && python -m app.evals.compare
    cd backend && python -m app.evals.compare --no-judge   # skip judge + pipeline calls, retrieval only

Two independent comparisons, both against the same 16-item golden set:
1. Retrieval strategy: dense (pgvector) vs sparse (Postgres full-text) vs
   hybrid (reciprocal rank fusion) — see app/services/retrieval_strategies.py.
2. Pipeline pattern: no-RAG baseline vs deterministic RAG vs agentic
   tool-use — see app/evals/pipelines.py. Scored on answer quality
   (citation faithfulness, LLM-judge groundedness/relevance), latency, and
   cost, since "does agentic's cost buy anything" is the real question.

Caveat worth stating, not hiding: 11 procedure chunks and 16 golden
questions is a small corpus — this demonstrates the comparison *method*,
not a statistically powerful result.
"""

import argparse
import json
import os
from datetime import datetime, timezone

from anthropic import Anthropic

from app.config import get_settings
from app.db import SessionLocal
from app.evals.answer_eval import _judge_answer, _score_citation_faithfulness
from app.evals.golden_set import GOLDEN_SET
from app.evals.pipelines import PIPELINES
from app.evals.retrieval_eval import evaluate_retrieval
from app.services import observability
from app.services.retrieval_strategies import STRATEGIES

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")


def compare_retrieval_strategies() -> dict:
    db = SessionLocal()
    try:
        results = {}
        for name, fn in STRATEGIES.items():
            report = evaluate_retrieval(db, retrieve_fn=fn)
            results[name] = {
                "recall_at_k": report.recall_at_k,
                "mean_precision_at_k": report.mean_precision_at_k,
                "mean_reciprocal_rank": report.mean_reciprocal_rank,
                "false_positive_rate": report.false_positive_rate,
            }
        return results
    finally:
        db.close()


def compare_pipelines(client: Anthropic, model: str, use_judge: bool) -> dict:
    db = SessionLocal()
    try:
        results = {}
        for name, fn in PIPELINES.items():
            faithfulness_scores: list[float] = []
            groundedness_scores: list[int] = []
            relevance_scores: list[int] = []
            latencies: list[float] = []
            total_input_tokens = 0
            total_output_tokens = 0

            for item in GOLDEN_SET:
                result = fn(db, client, model, item)
                latencies.append(result.latency_ms)
                total_input_tokens += result.input_tokens
                total_output_tokens += result.output_tokens

                retrieved_titles = [s.title for s in result.sources]
                _, _, faithfulness = _score_citation_faithfulness(result.answer, retrieved_titles)
                faithfulness_scores.append(faithfulness)

                if use_judge:
                    groundedness, relevance, _ = _judge_answer(
                        client, model, item, result.answer, result.sources, result.forecast_summary
                    )
                    if groundedness is not None:
                        groundedness_scores.append(groundedness)
                    if relevance is not None:
                        relevance_scores.append(relevance)

            cost = observability.estimate_cost_usd(model, total_input_tokens, total_output_tokens)
            results[name] = {
                "mean_citation_faithfulness": sum(faithfulness_scores) / len(faithfulness_scores),
                "mean_groundedness": (sum(groundedness_scores) / len(groundedness_scores)) if groundedness_scores else None,
                "mean_relevance": (sum(relevance_scores) / len(relevance_scores)) if relevance_scores else None,
                "mean_latency_ms": sum(latencies) / len(latencies),
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_estimated_cost_usd": cost,
            }
        return results
    finally:
        db.close()


def _print_retrieval_table(results: dict) -> None:
    print("\n=== Retrieval strategy comparison ===")
    print(f"{'strategy':<10} {'recall@k':>10} {'precision@k':>13} {'MRR':>8} {'false-pos rate':>15}")
    for name, m in results.items():
        print(
            f"{name:<10} {m['recall_at_k']:>9.1%} {m['mean_precision_at_k']:>12.1%} "
            f"{m['mean_reciprocal_rank']:>8.2f} {m['false_positive_rate']:>14.1%}"
        )


def _print_pipeline_table(results: dict) -> None:
    print("\n=== Pipeline pattern comparison ===")
    print(
        f"{'pipeline':<18} {'faithfulness':>13} {'groundedness':>13} {'relevance':>10} "
        f"{'latency (ms)':>13} {'cost ($)':>10}"
    )
    for name, m in results.items():
        g = f"{m['mean_groundedness']:.2f}" if m["mean_groundedness"] is not None else "-"
        rel = f"{m['mean_relevance']:.2f}" if m["mean_relevance"] is not None else "-"
        cost = f"{m['total_estimated_cost_usd']:.4f}" if m["total_estimated_cost_usd"] is not None else "-"
        print(
            f"{name:<18} {m['mean_citation_faithfulness']:>12.1%} {g:>13} {rel:>10} "
            f"{m['mean_latency_ms']:>13.0f} {cost:>10}"
        )


def _write_markdown(retrieval_results: dict, pipeline_results: dict | None, path: str) -> None:
    lines = ["# RAG / tool-stack comparison\n", "## Retrieval strategies\n"]
    lines.append("| strategy | recall@k | precision@k | MRR | false-positive rate |")
    lines.append("|---|---|---|---|---|")
    for name, m in retrieval_results.items():
        lines.append(
            f"| {name} | {m['recall_at_k']:.1%} | {m['mean_precision_at_k']:.1%} | "
            f"{m['mean_reciprocal_rank']:.2f} | {m['false_positive_rate']:.1%} |"
        )

    if pipeline_results is not None:
        lines.append("\n## Pipeline patterns\n")
        lines.append("| pipeline | citation faithfulness | groundedness | relevance | latency (ms) | cost ($) |")
        lines.append("|---|---|---|---|---|---|")
        for name, m in pipeline_results.items():
            g = f"{m['mean_groundedness']:.2f}" if m["mean_groundedness"] is not None else "-"
            rel = f"{m['mean_relevance']:.2f}" if m["mean_relevance"] is not None else "-"
            cost = f"{m['total_estimated_cost_usd']:.4f}" if m["total_estimated_cost_usd"] is not None else "-"
            lines.append(
                f"| {name} | {m['mean_citation_faithfulness']:.1%} | {g} | {rel} | "
                f"{m['mean_latency_ms']:.0f} | {cost} |"
            )

    lines.append(
        "\n_Corpus: 11 procedure chunks, 16 golden questions — demonstrates the comparison "
        "method, not a statistically powerful result._\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip the pipeline comparison entirely (retrieval strategies only, no Anthropic API calls).",
    )
    args = parser.parse_args()

    settings = get_settings()

    retrieval_results = compare_retrieval_strategies()
    _print_retrieval_table(retrieval_results)

    pipeline_results = None
    if not args.no_judge:
        if not settings.anthropic_api_key:
            print("\nANTHROPIC_API_KEY not set — skipping pipeline comparison.")
        else:
            client = Anthropic(api_key=settings.anthropic_api_key)
            pipeline_results = compare_pipelines(client, settings.claude_model, use_judge=True)
            _print_pipeline_table(pipeline_results)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    json_path = os.path.join(REPORTS_DIR, "comparison.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "retrieval_strategies": retrieval_results,
                "pipelines": pipeline_results,
            },
            f,
            indent=2,
        )
    md_path = os.path.join(REPORTS_DIR, "comparison.md")
    _write_markdown(retrieval_results, pipeline_results, md_path)
    print(f"\nWrote {json_path} and {md_path}")


if __name__ == "__main__":
    main()
