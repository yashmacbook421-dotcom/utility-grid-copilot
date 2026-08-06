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
}

export interface ChartRow {
  time: string;
  label: string;
  actual?: number;
  predicted?: number;
  lower?: number;
  upper?: number;
}
