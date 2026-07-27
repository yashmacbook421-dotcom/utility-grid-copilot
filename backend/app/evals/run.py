"""Eval suite entrypoint. Run after the DB is seeded (see app.data.seed):

    cd backend && python -m app.evals.run
    cd backend && python -m app.evals.run --no-judge   # retrieval only, no Anthropic calls

Prints a per-question report to stdout and writes the same data as JSON to
app/evals/reports/latest.json.
"""

import argparse
import json
import os
from datetime import datetime, timezone

from anthropic import Anthropic

from app.config import get_settings
from app.db import SessionLocal
from app.evals.answer_eval import AnswerReport, evaluate_answers
from app.evals.retrieval_eval import RetrievalReport, evaluate_retrieval

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")


def _print_retrieval_report(report: RetrievalReport) -> None:
    print("\n=== Retrieval eval ===")
    for r in report.results:
        expected = ", ".join(r.item.expected_sources) or "(none — out of scope)"
        retrieved = ", ".join(r.retrieved_titles) or "(none)"
        marker = "PASS" if (r.hit or not r.item.expected_sources) else "FAIL"
        print(f"[{marker}] {r.item.id}: expected=[{expected}] retrieved=[{retrieved}] "
              f"precision@k={r.precision_at_k:.2f} rr={r.reciprocal_rank:.2f}")

    print(f"\nRecall@k (in-scope):        {report.recall_at_k:.2%}")
    print(f"Mean precision@k (in-scope): {report.mean_precision_at_k:.2%}")
    print(f"Mean reciprocal rank:        {report.mean_reciprocal_rank:.2f}")
    print(f"Out-of-scope false-positive rate: {report.false_positive_rate:.2%}")


def _print_answer_report(report: AnswerReport) -> None:
    print("\n=== Answer eval ===")
    for r in report.results:
        g = r.groundedness if r.groundedness is not None else "-"
        rel = r.relevance if r.relevance is not None else "-"
        fab = f" FABRICATED={r.fabricated_citations}" if r.fabricated_citations else ""
        inj = ""
        if r.item.category == "injection":
            marker = "PASS" if r.injection_resisted else "FAIL"
            inj = f" [{marker}] injection_resisted={r.injection_resisted}"
        print(f"{r.item.id}: citation_faithfulness={r.citation_faithfulness:.2f} "
              f"groundedness={g} relevance={rel}{fab}{inj}")

    print(f"\nMean citation faithfulness: {report.mean_citation_faithfulness:.2%}")
    if report.mean_groundedness is not None:
        print(f"Mean groundedness (1-5):    {report.mean_groundedness:.2f}")
        print(f"Mean relevance (1-5):       {report.mean_relevance:.2f}")
    if report.injection_resistance_rate is not None:
        print(f"Injection resistance rate:  {report.injection_resistance_rate:.2%}")


def _to_json(retrieval_report: RetrievalReport, answer_report: AnswerReport | None) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "retrieval": {
            "recall_at_k": retrieval_report.recall_at_k,
            "mean_precision_at_k": retrieval_report.mean_precision_at_k,
            "mean_reciprocal_rank": retrieval_report.mean_reciprocal_rank,
            "false_positive_rate": retrieval_report.false_positive_rate,
            "results": [
                {
                    "id": r.item.id,
                    "question": r.item.question,
                    "expected_sources": r.item.expected_sources,
                    "retrieved_titles": r.retrieved_titles,
                    "hit": r.hit,
                    "precision_at_k": r.precision_at_k,
                    "reciprocal_rank": r.reciprocal_rank,
                }
                for r in retrieval_report.results
            ],
        },
        "answers": None
        if answer_report is None
        else {
            "mean_citation_faithfulness": answer_report.mean_citation_faithfulness,
            "mean_groundedness": answer_report.mean_groundedness,
            "mean_relevance": answer_report.mean_relevance,
            "injection_resistance_rate": answer_report.injection_resistance_rate,
            "results": [
                {
                    "id": r.item.id,
                    "category": r.item.category,
                    "question": r.item.question,
                    "answer": r.answer,
                    "retrieved_titles": r.retrieved_titles,
                    "cited_titles": r.cited_titles,
                    "fabricated_citations": r.fabricated_citations,
                    "citation_faithfulness": r.citation_faithfulness,
                    "groundedness": r.groundedness,
                    "relevance": r.relevance,
                    "judge_reasoning": r.judge_reasoning,
                    "injection_resisted": r.injection_resisted,
                    "injection_reasoning": r.injection_reasoning,
                }
                for r in answer_report.results
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip the answer-generation + LLM-judge stage (retrieval eval only, no Anthropic API calls).",
    )
    args = parser.parse_args()

    settings = get_settings()
    db = SessionLocal()

    try:
        retrieval_report = evaluate_retrieval(db)
        _print_retrieval_report(retrieval_report)

        answer_report = None
        if not args.no_judge:
            if not settings.anthropic_api_key:
                print("\nANTHROPIC_API_KEY not set — skipping answer eval.")
            else:
                client = Anthropic(api_key=settings.anthropic_api_key)
                answer_report = evaluate_answers(db, client, settings.claude_model)
                _print_answer_report(answer_report)
    finally:
        db.close()

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(REPORTS_DIR, "latest.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(_to_json(retrieval_report, answer_report), f, indent=2)
    print(f"\nWrote report to {report_path}")


if __name__ == "__main__":
    main()
