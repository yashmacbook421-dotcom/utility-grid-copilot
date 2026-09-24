import { NextRequest, NextResponse } from "next/server";
import { getSupabaseServer } from "@/lib/supabase-server";

function mean(values: number[]): number | null {
  return values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

export async function GET(req: NextRequest) {
  const limit = parseInt(req.nextUrl.searchParams.get("limit") ?? "20", 10);
  const supabase = getSupabaseServer();
  const { data: rows, error } = await supabase
    .from("request_logs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(Math.min(Math.max(limit, 1), 100));
  if (error) return NextResponse.json({ detail: error.message }, { status: 500 });

  const okRows = (rows ?? []).filter((r: Record<string, unknown>) => r["status"] === "ok");
  const summary = {
    count: rows?.length ?? 0,
    error_count: (rows ?? []).filter((r: Record<string, unknown>) => r["status"] === "error").length,
    cache_hit_count: (rows ?? []).filter((r: Record<string, unknown>) => r["status"] === "cache_hit").length,
    avg_total_ms: mean(okRows.map((r: Record<string, unknown>) => r["total_ms"] as number).filter((v) => v != null)),
    avg_retrieval_ms: mean(okRows.map((r: Record<string, unknown>) => r["retrieval_ms"] as number).filter((v) => v != null)),
    avg_generation_ms: mean(okRows.map((r: Record<string, unknown>) => r["generation_ms"] as number).filter((v) => v != null)),
    total_input_tokens: (rows ?? []).reduce((s: number, r: Record<string, unknown>) => s + (r["input_tokens"] as number ?? 0), 0),
    total_output_tokens: (rows ?? []).reduce((s: number, r: Record<string, unknown>) => s + (r["output_tokens"] as number ?? 0), 0),
    total_estimated_cost_usd: (rows ?? []).reduce((s: number, r: Record<string, unknown>) => s + (r["estimated_cost_usd"] as number ?? 0), 0),
  };

  const requests = (rows ?? []).map((r: Record<string, unknown>) => ({
    id: r["id"],
    created_at: r["created_at"],
    region: r["region"],
    question: r["question"] ? (r["question"] as string).slice(0, 120) + ((r["question"] as string).length > 120 ? "…" : "") : null,
    retrieval_ms: r["retrieval_ms"],
    forecast_ms: r["forecast_ms"],
    generation_ms: r["generation_ms"],
    total_ms: r["total_ms"],
    retrieved_sources: r["retrieved_sources"],
    input_tokens: r["input_tokens"],
    output_tokens: r["output_tokens"],
    estimated_cost_usd: r["estimated_cost_usd"],
    status: r["status"],
    error_message: r["error_message"],
  }));

  return NextResponse.json({ summary, requests });
}
