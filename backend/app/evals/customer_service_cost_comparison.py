"""Cost/quality comparison: standard (single-model) vs routed (cheap model
for tool-selection, strong model for the final answer) customer-service
paths. Same golden-set idea as evals/run.py, scoped to this one question:
does routing actually save money, and what does it cost in quality?

    cd backend && python -m app.evals.customer_service_cost_comparison

Writes a report to app/evals/reports/customer_service_cost_comparison.json
and prints a summary table to stdout.
"""

import json
import os
from dataclasses import dataclass

from anthropic import Anthropic

from app.config import get_settings
from app.db import SessionLocal
from app.models import CustomerCase
from app.services import customer_service_agent, observability

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")


@dataclass
class Scenario:
    id: str
    question: str
    customer_id: str | None = None
    service_area: str | None = None
    # What "good" looks like for this scenario — checked against both modes'
    # results so a cost win that breaks correctness shows up as a failure,
    # not a quiet win.
    expect_tool: str | None = None
    expect_min_confidence: str | None = None  # "medium" or "high"
    expect_safety_escalation: bool = False
    expect_low_confidence: bool = False


SCENARIOS = [
    Scenario(
        id="outage-restoration",
        question="My customer says their power is out. When will it be restored?",
        service_area="Folsom",
        expect_tool="get_outage_status",
        expect_min_confidence="medium",
    ),
    Scenario(
        id="billing-explanation",
        question="Why is my bill $280 this month?",
        customer_id="CUST-1001",
        expect_tool="get_customer_bill",
        expect_min_confidence="medium",
    ),
    Scenario(
        id="downed-line-safety",
        question="There is a downed power line in the customer's yard. What should I tell them?",
        service_area="Sacramento",
        expect_safety_escalation=True,
    ),
    Scenario(
        id="off-topic",
        question="What's a good recipe for banana bread?",
        expect_low_confidence=True,
    ),
    Scenario(
        id="outage-credit-policy",
        question="Is this customer eligible for an outage credit?",
        customer_id="CUST-1001",
        service_area="Folsom",
        expect_min_confidence="medium",
    ),
]

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _check(scenario: Scenario, tool_names: list[str], confidence: str, escalation_required: bool, escalation_reason: str | None) -> tuple[bool, str]:
    if scenario.expect_tool and scenario.expect_tool not in tool_names:
        return False, f"expected tool '{scenario.expect_tool}' not called (called: {tool_names})"
    if scenario.expect_min_confidence and _CONFIDENCE_RANK[confidence] < _CONFIDENCE_RANK[scenario.expect_min_confidence]:
        return False, f"confidence '{confidence}' below expected minimum '{scenario.expect_min_confidence}'"
    if scenario.expect_safety_escalation and not (escalation_required and escalation_reason == "safety"):
        return False, f"expected safety escalation, got required={escalation_required} reason={escalation_reason}"
    if scenario.expect_low_confidence and confidence != "low":
        return False, f"expected low confidence (refusal), got '{confidence}'"
    return True, "ok"


def run() -> dict:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY not configured — this comparison makes real Claude calls.")

    client = Anthropic(api_key=settings.anthropic_api_key)
    db = SessionLocal()
    results = {"standard": [], "routed": []}

    try:
        for scenario in SCENARIOS:
            # --- standard: single model, matches the CustomerCase-based API path ---
            # Built in memory only, never added to the session — nothing here
            # needs a persisted row, and evals shouldn't leave scratch rows behind.
            case = CustomerCase(
                agent_id="eval-cost-comparison",
                customer_id=scenario.customer_id,
                service_area=scenario.service_area,
                messages=[],
            )
            standard = customer_service_agent.run_customer_service_turn(
                db, client, settings.claude_model, case, scenario.question
            )
            standard_cost = observability.estimate_cost_usd(
                settings.claude_model, standard.input_tokens, standard.output_tokens
            )
            standard_tools = [t.tool for t in standard.tool_calls]
            ok, reason = _check(
                scenario, standard_tools, standard.confidence, standard.escalation.required, standard.escalation.reason
            )
            results["standard"].append(
                {
                    "scenario": scenario.id,
                    "model": settings.claude_model,
                    "confidence": standard.confidence,
                    "escalation": {"required": standard.escalation.required, "reason": standard.escalation.reason},
                    "tool_calls": standard_tools,
                    "input_tokens": standard.input_tokens,
                    "output_tokens": standard.output_tokens,
                    "estimated_cost_usd": standard_cost,
                    "pass": ok,
                    "check_detail": reason,
                }
            )

            # --- routed: cheap model gathers, strong model answers ---
            routed = customer_service_agent.run_customer_service_turn_routed(
                db,
                client,
                settings.claude_router_model,
                settings.claude_model,
                scenario.question,
                customer_id=scenario.customer_id,
                service_area=scenario.service_area,
            )
            router_cost = observability.estimate_cost_usd(
                routed.router_model, routed.router_input_tokens, routed.router_output_tokens
            )
            answer_cost = observability.estimate_cost_usd(
                routed.answer_model, routed.answer_input_tokens, routed.answer_output_tokens
            )
            routed_cost = None if router_cost is None or answer_cost is None else router_cost + answer_cost
            routed_tools = [t.tool for t in routed.tool_calls]
            ok, reason = _check(
                scenario, routed_tools, routed.confidence, routed.escalation.required, routed.escalation.reason
            )
            results["routed"].append(
                {
                    "scenario": scenario.id,
                    "router_model": routed.router_model,
                    "answer_model": routed.answer_model,
                    "confidence": routed.confidence,
                    "escalation": {"required": routed.escalation.required, "reason": routed.escalation.reason},
                    "tool_calls": routed_tools,
                    "input_tokens": routed.input_tokens,
                    "output_tokens": routed.output_tokens,
                    "estimated_cost_usd": routed_cost,
                    "pass": ok,
                    "check_detail": reason,
                }
            )
    finally:
        db.rollback()
        db.close()

    return results


def _print_report(results: dict) -> None:
    print(f"\n{'Scenario':<24} {'Mode':<10} {'Pass':<6} {'Confidence':<10} {'Cost ($)':<10} {'Tools called'}")
    print("-" * 100)
    total_cost = {"standard": 0.0, "routed": 0.0}
    pass_count = {"standard": 0, "routed": 0}
    for mode in ("standard", "routed"):
        for row in results[mode]:
            cost = row["estimated_cost_usd"] or 0.0
            total_cost[mode] += cost
            pass_count[mode] += 1 if row["pass"] else 0
            mark = "PASS" if row["pass"] else "FAIL"
            print(f"{row['scenario']:<24} {mode:<10} {mark:<6} {row['confidence']:<10} {cost:<10.5f} {row['tool_calls']}")
            if not row["pass"]:
                print(f"   -> {row['check_detail']}")

    n = len(SCENARIOS)
    print("\n=== Summary ===")
    print(f"Standard: {pass_count['standard']}/{n} passed, total cost ${total_cost['standard']:.5f}")
    print(f"Routed:   {pass_count['routed']}/{n} passed, total cost ${total_cost['routed']:.5f}")
    if total_cost["standard"] > 0:
        savings_pct = (1 - total_cost["routed"] / total_cost["standard"]) * 100
        print(f"Routed cost is {savings_pct:.1f}% {'lower' if savings_pct >= 0 else 'higher'} than standard")


def main() -> None:
    results = run()
    _print_report(results)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(REPORTS_DIR, "customer_service_cost_comparison.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote report to {report_path}")


if __name__ == "__main__":
    main()
