import {
  ForecastResponse,
  MonitoringDashboard,
  RecommendationResponse,
  RegionStatus,
  SurgeEvent,
  WhatIfResponse,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export async function listRegions(): Promise<string[]> {
  const res = await fetch(`${API_BASE_URL}/api/forecast/regions`, { cache: "no-store" });
  const data = await handleResponse<{ regions: string[] }>(res);
  return data.regions;
}

export async function getForecast(region: string, horizonHours = 24): Promise<ForecastResponse> {
  const params = new URLSearchParams({ region, horizon_hours: String(horizonHours) });
  const res = await fetch(`${API_BASE_URL}/api/forecast?${params.toString()}`, { cache: "no-store" });
  return handleResponse<ForecastResponse>(res);
}

export async function getRecommendation(
  region: string,
  question: string,
  topK = 4
): Promise<RecommendationResponse> {
  const res = await fetch(`${API_BASE_URL}/api/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region, question, top_k: topK }),
  });
  return handleResponse<RecommendationResponse>(res);
}

export async function listPendingSurges(): Promise<SurgeEvent[]> {
  const res = await fetch(`${API_BASE_URL}/api/surges?status=pending`, { cache: "no-store" });
  return handleResponse<SurgeEvent[]>(res);
}

export async function approveSurge(id: string): Promise<SurgeEvent> {
  const res = await fetch(`${API_BASE_URL}/api/surges/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  return handleResponse<SurgeEvent>(res);
}

export async function rejectSurge(id: string): Promise<SurgeEvent> {
  const res = await fetch(`${API_BASE_URL}/api/surges/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  return handleResponse<SurgeEvent>(res);
}

export async function triggerDemoSurge(region: string): Promise<SurgeEvent> {
  const params = new URLSearchParams({ region });
  const res = await fetch(`${API_BASE_URL}/api/surges/demo-trigger?${params.toString()}`, {
    method: "POST",
  });
  return handleResponse<SurgeEvent>(res);
}

export async function getRegionStatuses(): Promise<RegionStatus[]> {
  const res = await fetch(`${API_BASE_URL}/api/dashboard/regions`, { cache: "no-store" });
  const data = await handleResponse<{ regions: RegionStatus[] }>(res);
  return data.regions;
}

export async function getWhatIfForecast(
  region: string,
  demandMultiplier: number,
  horizonHours = 24
): Promise<WhatIfResponse> {
  const res = await fetch(`${API_BASE_URL}/api/forecast/whatif`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region, demand_multiplier: demandMultiplier, horizon_hours: horizonHours }),
  });
  return handleResponse<WhatIfResponse>(res);
}

export async function submitFeedback(
  requestLogId: string,
  rating: "up" | "down",
  reason?: string
): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_log_id: requestLogId, rating, reason: reason ?? null }),
  });
  await handleResponse<unknown>(res);
}

export async function getMonitoringDashboard(): Promise<MonitoringDashboard> {
  const res = await fetch(`${API_BASE_URL}/api/observability/dashboard`, { cache: "no-store" });
  return handleResponse<MonitoringDashboard>(res);
}
