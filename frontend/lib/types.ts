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
}

export interface RecommendationResponse {
  region: string;
  question: string;
  answer: string;
  sources: SourceCitation[];
  forecast_context: ForecastResponse | null;
  warnings: string[];
}

export interface ChartRow {
  time: string;
  label: string;
  actual?: number;
  predicted?: number;
  lower?: number;
  upper?: number;
}
