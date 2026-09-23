import { CUSTOMERS, OUTAGES, BILLS, SERVICE_AREAS } from "./demo-data";

export function normalizeServiceArea(serviceArea: string): string | null {
  const target = serviceArea.trim().toLowerCase();
  for (const area of SERVICE_AREAS) {
    if (area.toLowerCase() === target) return area;
  }
  return null;
}

export function getOutageStatus(serviceArea: string): Record<string, unknown> | null {
  const area = normalizeServiceArea(serviceArea);
  if (!area) return null;

  const record = OUTAGES[area] as Record<string, unknown>;
  const now = new Date();

  const reportedAgo = record["reported_minutes_ago"] as number | null;
  const etaMinutes = record["restoration_eta_minutes"] as number | null;
  const resolvedAgo = record["resolved_minutes_ago"] as number | null;

  const lastUpdated = reportedAgo != null
    ? new Date(now.getTime() - reportedAgo * 60_000).toISOString()
    : null;
  const estimatedRestoration = etaMinutes != null
    ? new Date(now.getTime() + etaMinutes * 60_000).toISOString()
    : null;
  const resolvedAt = resolvedAgo != null
    ? new Date(now.getTime() - resolvedAgo * 60_000).toISOString()
    : null;

  return {
    area,
    status: record["status"],
    customers_affected: record["customers_affected"],
    cause: record["cause"],
    crew_status: record["crew_status"],
    estimated_restoration: estimatedRestoration,
    last_updated: lastUpdated,
    resolved_at: resolvedAt,
  };
}

export function getCustomerBill(customerId: string): Record<string, unknown> | null {
  const record = BILLS[customerId.trim().toUpperCase()];
  if (!record) return null;

  const prevUsage = record["previous_usage_kwh"] as number;
  const currUsage = record["current_usage_kwh"] as number;
  const usageChangePct = prevUsage
    ? Math.round(((currUsage - prevUsage) / prevUsage) * 1000) / 10
    : null;

  return { ...record, usage_change_pct: usageChangePct };
}

export function getCustomer(customerId: string): Record<string, unknown> | null {
  return CUSTOMERS[customerId.trim().toUpperCase()] ?? null;
}

export function listCustomers(): Record<string, unknown>[] {
  return Object.values(CUSTOMERS);
}
