import {
  AgenticRecommendationResponse,
  AskCaseResponse,
  CaseSummaryResponse,
  CustomerCase,
  CustomerDetail,
  CustomerInfo,
  ForecastResponse,
  MonitoringDashboard,
  OutageStatus,
  RecommendationResponse,
  RegionStatus,
  SourceCitation,
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

export async function streamRecommendation(
  region: string,
  question: string,
  handlers: { onDelta?: (text: string) => void; onSources?: (sources: SourceCitation[]) => void },
  topK = 4
): Promise<RecommendationResponse> {
  const res = await fetch(`${API_BASE_URL}/api/recommend/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region, question, top_k: topK }),
  });
  if (!res.ok || !res.body) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sources: SourceCitation[] = [];
  let answer = "";
  let warnings: string[] = [];
  let forecastContext: ForecastResponse | null = null;
  let requestLogId: string | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex: number;
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);

      const eventMatch = rawEvent.match(/^event: (.+)$/m);
      const dataMatch = rawEvent.match(/^data: (.+)$/m);
      if (!eventMatch || !dataMatch) continue;
      const data = JSON.parse(dataMatch[1]);

      switch (eventMatch[1]) {
        case "sources":
          sources = data.sources;
          handlers.onSources?.(sources);
          break;
        case "delta":
          answer += data.text;
          handlers.onDelta?.(data.text);
          break;
        case "done":
          answer = data.answer;
          warnings = data.warnings;
          forecastContext = data.forecast_context;
          requestLogId = data.request_log_id;
          break;
        case "error":
          throw new Error(data.message);
      }
    }
  }

  return {
    region,
    question,
    answer,
    sources,
    forecast_context: forecastContext,
    warnings,
    request_log_id: requestLogId,
  };
}

export async function getAgenticRecommendation(
  region: string,
  question: string,
  topK = 4
): Promise<AgenticRecommendationResponse> {
  const res = await fetch(`${API_BASE_URL}/api/recommend/agentic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region, question, top_k: topK }),
  });
  return handleResponse<AgenticRecommendationResponse>(res);
}

export async function listPendingSurges(region: string): Promise<SurgeEvent[]> {
  const params = new URLSearchParams({ status: "pending", region });
  const res = await fetch(`${API_BASE_URL}/api/surges?${params.toString()}`, { cache: "no-store" });
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

// ---- Customer Service Agent Assist ----

export async function listCustomers(): Promise<CustomerInfo[]> {
  const res = await fetch(`${API_BASE_URL}/api/customer-service/customers`, { cache: "no-store" });
  return handleResponse<CustomerInfo[]>(res);
}

export async function getCustomer(customerId: string): Promise<CustomerDetail> {
  const res = await fetch(`${API_BASE_URL}/api/customer-service/customers/${encodeURIComponent(customerId)}`, {
    cache: "no-store",
  });
  return handleResponse<CustomerDetail>(res);
}

export async function getOutageStatus(serviceArea: string): Promise<OutageStatus> {
  const res = await fetch(`${API_BASE_URL}/api/outages/${encodeURIComponent(serviceArea)}`, { cache: "no-store" });
  return handleResponse<OutageStatus>(res);
}

export async function openCase(
  agentId: string,
  customerId?: string,
  serviceArea?: string
): Promise<CustomerCase> {
  const res = await fetch(`${API_BASE_URL}/api/customer-service/cases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId, customer_id: customerId ?? null, service_area: serviceArea ?? null }),
  });
  return handleResponse<CustomerCase>(res);
}

export async function askCustomerService(
  caseId: string,
  question: string,
  mode: "standard" | "routed" = "standard"
): Promise<AskCaseResponse> {
  const res = await fetch(`${API_BASE_URL}/api/customer-service/cases/${caseId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, mode }),
  });
  return handleResponse<AskCaseResponse>(res);
}

export async function summarizeCase(caseId: string): Promise<CaseSummaryResponse> {
  const res = await fetch(`${API_BASE_URL}/api/customer-service/cases/${caseId}/summary`, { method: "POST" });
  return handleResponse<CaseSummaryResponse>(res);
}

export async function listCases(): Promise<CustomerCase[]> {
  const res = await fetch(`${API_BASE_URL}/api/customer-service/cases`, { cache: "no-store" });
  return handleResponse<CustomerCase[]>(res);
}
