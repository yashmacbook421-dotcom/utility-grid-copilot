"""Synthetic reference data for the Customer Service Agent Assist module.

Small, fixed lookup dicts — same pattern as REGION_PROFILES (app/data/regions.py)
and EIA_RESPONDENTS (app/services/eia_ingest.py): this is demo fixture data,
not something that needs a DB table, joins, or growth over time.

All customers, addresses, and bills below are invented for this prototype.
No real customer PII. Service areas (Sacramento, Folsom, Carmichael, Rancho
Cordova, Elk Grove, Citrus Heights, Natomas) are real Sacramento-area city
names, chosen because they sit within SMUD's real service territory (see
app/data/regions.py's "smud" region) — but the outage/customer/billing data
itself is entirely synthetic, generated for this demo.
"""

SERVICE_AREAS = [
    "Sacramento",
    "Folsom",
    "Carmichael",
    "Rancho Cordova",
    "Elk Grove",
    "Citrus Heights",
    "Natomas",
]

CUSTOMERS: dict[str, dict] = {
    "CUST-1001": {
        "customer_id": "CUST-1001",
        "name": "Maria Delgado",
        "address": "482 Fremont St",
        "zip": "95630",
        "service_area": "Folsom",
        "service_status": "active",
        "account_status": "current",
    },
    "CUST-1002": {
        "customer_id": "CUST-1002",
        "name": "James Okafor",
        "address": "119 Maple Ave",
        "zip": "95608",
        "service_area": "Carmichael",
        "service_status": "active",
        "account_status": "current",
    },
    "CUST-1003": {
        "customer_id": "CUST-1003",
        "name": "Linh Tran",
        "address": "2207 Natomas Crossing Dr",
        "zip": "95834",
        "service_area": "Natomas",
        "service_status": "active",
        "account_status": "past_due",
    },
    "CUST-1004": {
        "customer_id": "CUST-1004",
        "name": "David Kowalski",
        "address": "3390 Elkhorn Blvd",
        "zip": "95758",
        "service_area": "Elk Grove",
        "service_status": "active",
        "account_status": "current",
    },
    "CUST-1005": {
        "customer_id": "CUST-1005",
        "name": "Priya Nair",
        "address": "7710 Greenback Ln",
        "zip": "95610",
        "service_area": "Citrus Heights",
        "service_status": "active",
        "account_status": "current",
    },
    "CUST-1006": {
        "customer_id": "CUST-1006",
        "name": "Robert Chen",
        "address": "5521 Folsom Blvd",
        "zip": "95819",
        "service_area": "Sacramento",
        "service_status": "active",
        "account_status": "credit_hold",
    },
    "CUST-1007": {
        "customer_id": "CUST-1007",
        "name": "Angela Reyes",
        "address": "10112 Coloma Rd",
        "zip": "95670",
        "service_area": "Rancho Cordova",
        "service_status": "active",
        "account_status": "current",
    },
    "CUST-1008": {
        "customer_id": "CUST-1008",
        "name": "Samuel Whitfield",
        "address": "861 Riley St",
        "zip": "95630",
        "service_area": "Folsom",
        "service_status": "active",
        "account_status": "current",
    },
    "CUST-1009": {
        "customer_id": "CUST-1009",
        "name": "Hana Kobayashi",
        "address": "4488 Truxel Rd",
        "zip": "95834",
        "service_area": "Natomas",
        "service_status": "disconnected",
        "account_status": "past_due",
    },
    "CUST-1010": {
        "customer_id": "CUST-1010",
        "name": "Marcus Webb",
        "address": "6203 Watt Ave",
        "zip": "95842",
        "service_area": "Carmichael",
        "service_status": "active",
        "account_status": "current",
    },
    "CUST-1011": {
        "customer_id": "CUST-1011",
        "name": "Sofia Marchetti",
        "address": "9027 Bond Rd",
        "zip": "95624",
        "service_area": "Elk Grove",
        "service_status": "active",
        "account_status": "current",
    },
    "CUST-1012": {
        "customer_id": "CUST-1012",
        "name": "Elijah Thompson",
        "address": "1140 Fulton Ave",
        "zip": "95825",
        "service_area": "Sacramento",
        "service_status": "active",
        "account_status": "current",
    },
}

# `restoration_eta_minutes`/`reported_minutes_ago` are offsets from "now" —
# outage_tool.get_outage_status() resolves these to real timestamps at call
# time, so the demo always looks current regardless of when it's run,
# without needing a live outage-management-system feed (see ARCHITECTURE
# note in outage_tool.py).
OUTAGES: dict[str, dict] = {
    "Folsom": {
        "status": "active",
        "customers_affected": 247,
        "cause": "Equipment failure",
        "crew_status": "Dispatched",
        "restoration_eta_minutes": 165,
        "reported_minutes_ago": 52,
    },
    "Natomas": {
        "status": "active",
        "customers_affected": 89,
        "cause": "Vehicle collision with utility pole",
        "crew_status": "On site",
        "restoration_eta_minutes": 45,
        "reported_minutes_ago": 70,
    },
    "Sacramento": {
        "status": "active",
        "customers_affected": 1240,
        "cause": "Transmission line fault",
        "crew_status": "Assessing damage",
        "restoration_eta_minutes": 210,
        "reported_minutes_ago": 35,
    },
    "Carmichael": {
        "status": "resolved",
        "customers_affected": 0,
        "cause": "Scheduled maintenance",
        "crew_status": "Completed",
        "restoration_eta_minutes": None,
        "reported_minutes_ago": 300,
        "resolved_minutes_ago": 20,
    },
    "Elk Grove": {
        "status": "resolved",
        "customers_affected": 0,
        "cause": "Tree contact with line",
        "crew_status": "Completed",
        "restoration_eta_minutes": None,
        "reported_minutes_ago": 180,
        "resolved_minutes_ago": 40,
    },
    "Rancho Cordova": {
        "status": "none",
        "customers_affected": 0,
        "cause": None,
        "crew_status": None,
        "restoration_eta_minutes": None,
        "reported_minutes_ago": None,
    },
    "Citrus Heights": {
        "status": "none",
        "customers_affected": 0,
        "cause": None,
        "crew_status": None,
        "restoration_eta_minutes": None,
        "reported_minutes_ago": None,
    },
}

BILLS: dict[str, dict] = {
    "CUST-1001": {
        "current_bill_usd": 280.14,
        "previous_bill_usd": 189.62,
        "current_usage_kwh": 1120,
        "previous_usage_kwh": 848,
        "billing_period": "2026-07-15 to 2026-08-14",
        "rate_plan": "Residential Tiered",
    },
    "CUST-1002": {
        "current_bill_usd": 142.30,
        "previous_bill_usd": 138.90,
        "current_usage_kwh": 610,
        "previous_usage_kwh": 598,
        "billing_period": "2026-07-15 to 2026-08-14",
        "rate_plan": "Residential Baseline",
    },
    "CUST-1003": {
        "current_bill_usd": 96.40,
        "previous_bill_usd": 101.10,
        "current_usage_kwh": 402,
        "previous_usage_kwh": 419,
        "billing_period": "2026-07-15 to 2026-08-14",
        "rate_plan": "Time-of-Use",
    },
    "CUST-1004": {
        "current_bill_usd": 315.88,
        "previous_bill_usd": 210.55,
        "current_usage_kwh": 1340,
        "previous_usage_kwh": 967,
        "billing_period": "2026-07-15 to 2026-08-14",
        "rate_plan": "Residential Tiered",
    },
    "CUST-1006": {
        "current_bill_usd": 204.77,
        "previous_bill_usd": 199.02,
        "current_usage_kwh": 855,
        "previous_usage_kwh": 840,
        "billing_period": "2026-07-15 to 2026-08-14",
        "rate_plan": "Time-of-Use",
    },
    "CUST-1012": {
        "current_bill_usd": 118.20,
        "previous_bill_usd": 121.05,
        "current_usage_kwh": 495,
        "previous_usage_kwh": 508,
        "billing_period": "2026-07-15 to 2026-08-14",
        "rate_plan": "Residential Baseline",
    },
}
