"""Simulated billing-system tool — synthetic customer bill lookups (see
outage_tool.py for the same pattern/rationale applied to outage data).
"""

from app.data.customer_service_demo_data import BILLS


def get_customer_bill(customer_id: str) -> dict | None:
    """Returns None if this customer has no bill on file — the agent must
    say so rather than inventing billing figures.
    """
    record = BILLS.get(customer_id.strip().upper())
    if record is None:
        return None

    usage_change_pct = None
    if record["previous_usage_kwh"]:
        usage_change_pct = round(
            (record["current_usage_kwh"] - record["previous_usage_kwh"]) / record["previous_usage_kwh"] * 100, 1
        )

    return {"customer_id": customer_id.strip().upper(), **record, "usage_change_pct": usage_change_pct}
