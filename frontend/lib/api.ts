import { ForecastResponse, RecommendationResponse } from "./types";

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
