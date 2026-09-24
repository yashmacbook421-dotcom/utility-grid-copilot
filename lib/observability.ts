import { getSupabaseServer } from "./supabase-server";
import { estimateCostUsd } from "./config";

export async function logRequest(params: {
  endpoint: string;
  region?: string | null;
  question?: string | null;
  embeddingMs?: number | null;
  retrievalMs?: number | null;
  forecastMs?: number | null;
  generationMs?: number | null;
  totalMs?: number | null;
  retrievedSources?: unknown[];
  inputTokens?: number | null;
  outputTokens?: number | null;
  estimatedCostUsd?: number | null;
  status: string;
  errorMessage?: string | null;
}): Promise<string> {
  const supabase = getSupabaseServer();
  const { data, error } = await supabase
    .from("request_logs")
    .insert({
      endpoint: params.endpoint,
      region: params.region ?? null,
      question: params.question ?? null,
      embedding_ms: params.embeddingMs ?? null,
      retrieval_ms: params.retrievalMs ?? null,
      forecast_ms: params.forecastMs ?? null,
      generation_ms: params.generationMs ?? null,
      total_ms: params.totalMs ?? null,
      retrieved_sources: params.retrievedSources ?? [],
      input_tokens: params.inputTokens ?? null,
      output_tokens: params.outputTokens ?? null,
      estimated_cost_usd: params.estimatedCostUsd ?? null,
      status: params.status,
      error_message: params.errorMessage ?? null,
    })
    .select("id")
    .single();

  if (error) throw error;
  return data.id;
}

export { estimateCostUsd };
