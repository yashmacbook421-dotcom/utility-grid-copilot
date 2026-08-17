export interface DemandPoint {
  time: string;
  demand_mw: number;
  temperature_c?: number;
  solar_generation_mw?: number;
  ev_load_mw?: number;
}

export interface ForecastPoint {
  time: string;
  predicted_demand_mw: number;
  lower_bound_mw: number;
  upper_bound_mw: number;
}

export interface ForecastResponse {
  region: string;
  generated_at: string;
  history: DemandPoint[];
  forecast: ForecastPoint[];
  peak_forecast_mw: number;
  peak_forecast_time: string;
}

export interface SourceCitation {
  title: string;
  source: string;
  excerpt: string;
  similarity: number;
  document_id?: string | null;
  page_number?: number | null;
  section?: string | null;
  source_url?: string | null;
  organization?: string | null;
  document_type?: string | null;
}

export interface RecommendationResponse {
  region: string;
  question: string;
  answer: string;
  sources: SourceCitation[];
  forecast_context: ForecastResponse | null;
  warnings: string[];
  request_log_id: string | null;
}

export interface ToolCallSummary {
  tool: string;
  input: Record<string, unknown>;
  summary: string;
}

export interface AgenticRecommendationResponse {
  region: string;
  question: string;
  answer: string;
  tool_calls: ToolCallSummary[];
  sources: SourceCitation[];
  forecast_context: ForecastResponse | null;
  warnings: string[];
  iterations: number;
  request_log_id: string | null;
}

export interface SurgeEvent {
  id: string;
  created_at: string;
  region: string;
  forecast_peak_mw: number;
  baseline_p95_mw: number;
  peak_forecast_time: string;
  recommended_action: string;
  sources: SourceCitation[];
  status: string;
  severity: string;
  notified: boolean;
  notification_error: string | null;
  resolved_at: string | null;
  resolved_note: string | null;
}

export interface RegionStatus {
  region: string;
  status: "normal" | "elevated" | "surge";
  forecast_peak_mw: number;
  baseline_p95_mw: number;
  ratio: number;
  latest_solar_generation_mw: number | null;
}

export interface WhatIfResponse {
  region: string;
  demand_multiplier: number;
  forecast: ForecastPoint[];
  peak_forecast_mw: number;
  peak_forecast_time: string;
  baseline_p95_mw: number;
  would_exceed_baseline: boolean;
  explanation: string | null;
  sources: SourceCitation[];
}

export interface MonitoringDashboard {
  rag: {
    queries: number;
    errors: number;
    cache_hits: number;
    avg_latency_ms: number | null;
    total_input_tokens: number;
    total_output_tokens: number;
    total_estimated_cost_usd: number;
    avg_cost_per_query_usd: number | null;
  };
  alerts: {
    surges_detected: number;
    pending: number;
    approved: number;
    rejected: number;
    high_severity: number;
    notifications_sent: number;
    notifications_failed: number;
  };
  feedback: {
    total: number;
    up: number;
    down: number;
  };
  budget: {
    daily_cap_usd: number | null;
    spent_today_usd: number;
    over_cap: boolean;
  };
}

// ---- Customer Service Agent Assist ----

export interface CustomerInfo {
  customer_id: string;
  name: string;
  address: string;
  zip: string;
  service_area: string;
  service_status: string;
  account_status: string;
}

export interface BillInfo {
  customer_id: string;
  current_bill_usd: number;
  previous_bill_usd: number;
  current_usage_kwh: number;
  previous_usage_kwh: number;
  billing_period: string;
  rate_plan: string;
  usage_change_pct: number | null;
}

export interface CustomerDetail {
  customer: CustomerInfo;
  bill: BillInfo | null;
}

export interface OutageStatus {
  area: string;
  status: string;
  customers_affected: number;
  cause: string | null;
  crew_status: string | null;
  estimated_restoration: string | null;
  last_updated: string | null;
  resolved_at: string | null;
}

export interface CustomerCase {
  id: string;
  created_at: string;
  updated_at: string;
  agent_id: string;
  customer_id: string | null;
  service_area: string | null;
  status: string;
  escalated: boolean;
  escalation_reason: string | null;
  summary: string | null;
}

export interface EscalationInfo {
  required: boolean;
  reason: string | null;
}

export interface AskCaseResponse {
  case_id: string;
  question: string;
  mode: "standard" | "routed";
  internal_analysis: string;
  customer_response: string;
  confidence: "high" | "medium" | "low";
  sources: SourceCitation[];
  tool_calls: ToolCallSummary[];
  escalation: EscalationInfo;
  warnings: string[];
  iterations: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
  request_log_id: string | null;
}

export interface CaseSummaryResponse {
  case_id: string;
  summary: string;
  status: string;
}

export interface ChartRow {
  time: string;
  label: string;
  actual?: number;
  predicted?: number;
  lower?: number;
  upper?: number;
}
