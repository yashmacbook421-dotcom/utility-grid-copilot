"""Delivery Assist scenarios — real Claude calls, real DB, same convention as
test_customer_service.py: skipped automatically if ANTHROPIC_API_KEY isn't
configured. No case object here (see routers/delivery_assist.py), so there's
no per-test cleanup needed beyond what request_logs already accumulates.
"""

import pytest

from app.config import get_settings

settings = get_settings()

pytestmark = pytest.mark.skipif(not settings.anthropic_api_key, reason="ANTHROPIC_API_KEY not configured")


def _ask(client, area, question):
    response = client.post("/api/delivery-assist/ask", json={"area": area, "question": question})
    assert response.status_code == 200
    return response.json()


def test_billing_question_finds_grounded_answer(client):
    result = _ask(
        client,
        "Billing & Payments",
        "What's the standard approach for a fixed monthly service charge?",
    )
    assert result["confidence"] in ("high", "medium")
    assert len(result["sources"]) > 0
    assert all(s["document_type"] == "billing_configuration" for s in result["sources"])
    assert not result["escalation"]["required"]


def test_rate_configuration_question_finds_grounded_answer(client):
    result = _ask(client, "Rate Configuration", "How is a mid-cycle rate schedule change typically handled?")
    assert result["confidence"] in ("high", "medium")
    assert len(result["sources"]) > 0
    assert all(s["document_type"] == "rate_configuration" for s in result["sources"])


def test_out_of_scope_question_escalates_instead_of_guessing(client):
    # work-order-prioritization-basics.md explicitly scopes itself away from
    # crew-shift/union questions — this should come back empty-handed, not
    # with a confidently invented answer.
    result = _ask(
        client,
        "Work & Asset Management",
        "How do we configure crew shift patterns across overlapping emergency work orders?",
    )
    assert result["confidence"] == "low"
    assert result["escalation"]["required"] is True
    assert result["escalation"]["reason"] == "insufficient_information"


def test_unknown_area_is_rejected(client):
    response = client.post(
        "/api/delivery-assist/ask", json={"area": "Not A Real Area", "question": "anything"}
    )
    assert response.status_code == 422


def test_list_areas_returns_all_four(client):
    response = client.get("/api/delivery-assist/areas")
    assert response.status_code == 200
    areas = response.json()
    assert set(areas) == {
        "Billing & Payments",
        "Rate Configuration",
        "Meter Data Management",
        "Work & Asset Management",
    }
