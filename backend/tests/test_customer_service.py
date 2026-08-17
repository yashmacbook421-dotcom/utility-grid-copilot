"""Customer Service Agent Assist scenarios (spec section 17). Real Claude
calls, real DB — same convention as test_guardrails.py, skipped automatically
if ANTHROPIC_API_KEY isn't configured. Each test opens its own case and
deletes it afterward, matching test_api.py's ingest-test cleanup pattern.
"""

import pytest
from sqlalchemy import delete

from app.config import get_settings
from app.models import CustomerCase
from app.services.customer_service_agent import _LOW_CONFIDENCE_REFUSAL

settings = get_settings()

pytestmark = pytest.mark.skipif(not settings.anthropic_api_key, reason="ANTHROPIC_API_KEY not configured")


def _open_case(client, **kwargs):
    payload = {"agent_id": "test-rep"} | kwargs
    response = client.post("/api/customer-service/cases", json=payload)
    assert response.status_code == 200
    return response.json()["id"]


def _ask(client, case_id, question):
    response = client.post(f"/api/customer-service/cases/{case_id}/ask", json={"question": question})
    assert response.status_code == 200
    return response.json()


def _cleanup(db, case_id):
    db.execute(delete(CustomerCase).where(CustomerCase.id == case_id))
    db.commit()


def test_outage_question_calls_outage_tool(client, db):
    case_id = _open_case(client, service_area="Folsom")
    try:
        result = _ask(client, case_id, "Is there an outage in Folsom right now?")
        tool_names = [t["tool"] for t in result["tool_calls"]]
        assert "get_outage_status" in tool_names
    finally:
        _cleanup(db, case_id)


def test_restoration_question_retrieves_live_data(client, db):
    case_id = _open_case(client, service_area="Folsom")
    try:
        result = _ask(client, case_id, "My customer says their power is out. When will it be restored?")
        tool_names = [t["tool"] for t in result["tool_calls"]]
        assert "get_outage_status" in tool_names
        assert result["customer_response"] != _LOW_CONFIDENCE_REFUSAL
        assert result["confidence"] in ("high", "medium")
    finally:
        _cleanup(db, case_id)


def test_billing_question_uses_billing_tool_and_rag(client, db):
    case_id = _open_case(client, customer_id="CUST-1001")
    try:
        result = _ask(client, case_id, "Why is my bill $280 this month?")
        tool_names = [t["tool"] for t in result["tool_calls"]]
        assert "get_customer_bill" in tool_names
        assert len(result["sources"]) > 0
    finally:
        _cleanup(db, case_id)


def test_question_not_supported_by_documents_does_not_hallucinate(client, db):
    case_id = _open_case(client)
    try:
        result = _ask(
            client, case_id, "What's the interconnection process for a new 500 MW offshore wind farm?"
        )
        assert result["confidence"] == "low"
        assert result["customer_response"] == _LOW_CONFIDENCE_REFUSAL
    finally:
        _cleanup(db, case_id)


def test_downed_power_line_triggers_safety_escalation(client, db):
    case_id = _open_case(client, service_area="Sacramento")
    try:
        result = _ask(client, case_id, "There is a downed power line in the customer's yard. What should I tell them?")
        assert result["escalation"]["required"] is True
        assert result["escalation"]["reason"] == "safety"
        assert any(s["document_type"] == "safety_procedure" for s in result["sources"])

        case_response = client.get(f"/api/customer-service/cases/{case_id}")
        assert case_response.json()["escalated"] is True
        assert case_response.json()["escalation_reason"] == "safety"
    finally:
        _cleanup(db, case_id)


def test_unknown_service_area_degrades_confidence(client, db):
    case_id = _open_case(client)
    try:
        result = _ask(client, case_id, "Is there an outage in Roseville right now?")
        tool_names = [t["tool"] for t in result["tool_calls"]]
        assert "get_outage_status" in tool_names
        assert result["confidence"] != "high"
    finally:
        _cleanup(db, case_id)


def test_off_topic_question_declines_without_escalating_as_safety(client, db):
    case_id = _open_case(client)
    try:
        result = _ask(client, case_id, "What's a good recipe for banana bread?")
        assert result["sources"] == []
        assert result["confidence"] == "low"
        assert result["escalation"]["reason"] != "safety"
    finally:
        _cleanup(db, case_id)


def test_conversation_memory_resolves_pronoun_reference(client, db):
    """Spec section 13's exact example: 'Folsom' then 'how should I explain
    this to them' — 'this' must resolve to the Folsom outage from the prior
    turn without the rep restating it.
    """
    case_id = _open_case(client, service_area="Folsom")
    try:
        _ask(client, case_id, "Customer says their power is out. Which area — Folsom.")
        result = _ask(client, case_id, "How should I explain this to them?")
        assert result["customer_response"] != _LOW_CONFIDENCE_REFUSAL
        assert len(result["customer_response"]) > 0
    finally:
        _cleanup(db, case_id)
