"""Simulated customer-information-system tool — synthetic customer lookups
(see outage_tool.py for the same pattern/rationale)."""

from app.data.customer_service_demo_data import CUSTOMERS


def get_customer(customer_id: str) -> dict | None:
    return CUSTOMERS.get(customer_id.strip().upper())


def list_customers() -> list[dict]:
    return list(CUSTOMERS.values())
