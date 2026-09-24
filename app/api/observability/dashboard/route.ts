import { NextRequest, NextResponse } from "next/server";
import { getSupabaseServer } from "@/lib/supabase-server";
import { config } from "@/lib/config";
import { todaySpendUsd, isOverBudget } from "@/lib/budget";

function mean(values: number[]): number | null {
  return values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

export async function GET(req: NextRequest) {
  const limit = parseInt(req.nextUrl.searchParams.get("limit") ?? "200", 10);
  const supabase = getSupabaseServer();

  const { data: logRows } = await supabase
    .from("request_logs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(Math.min(limit, 2000));

  const { data: surgeRows } = await supabase.from("surge_events").select("*");
  const { data: feedbackRows } = await supabase.from("answer_feedback").select("rating, reason");

  const okRows = (logRows ?? []).filter((r: Record<string, unknown>) => r["status"] === "ok");
  const costs = okRows.map((r: Record<string, unknown>) => r["estimated_cost_usd"] as number).filter((c) => c != null);

  const ragStats = {
    queries: logRows?.length ?? 0,
    errors: (logRows ?? []).filter((r: Record<string, unknown>) => r["status"] === "error").length,
    cache_hits: (logRows ?? []).filter((r: Record<string, unknown>) => r["status"] === "cache_hit").length,
    avg_latency_ms: mean(okRows.map((r: Record<string, unknown>) => r["total_ms"] as number).filter((v) => v != null)),
    total_input_tokens: okRows.reduce((s: number, r: Record<string, unknown>) => s + (r["input_tokens"] as number ?? 0), 0),
    total_output_tokens: okRows.reduce((s: number, r: Record<string, unknown>) => s + (r["output_tokens"] as number ?? 0), 0),
    total_estimated_cost_usd: costs.length > 0 ? Math.round(costs.reduce((a, b) => a + b, 0) * 10000) / 10000 : 0,
    avg_cost_per_query_usd: costs.length > 0 ? Math.round((costs.reduce((a, b) => a + b, 0) / costs.length) * 1000000) / 1000000 : null,
  };

  const surges = surgeRows ?? [];
  const alertsStats = {
    surges_detected: surges.length,
    pending: surges.filter((s: Record<string, unknown>) => s["status"] === "pending").length,
    approved: surges.filter((s: Record<string, unknown>) => s["status"] === "approved").length,
    rejected: surges.filter((s: Record<string, unknown>) => s["status"] === "rejected").length,
    high_severity: surges.filter((s: Record<string, unknown>) => s["severity"] === "high").length,
    notifications_sent: surges.filter((s: Record<string, unknown>) => s["notified"]).length,
    notifications_failed: surges.filter((s: Record<string, unknown>) => !s["notified"] && s["notification_error"]).length,
  };

  const feedback = feedbackRows ?? [];
  const feedbackStats = {
    total: feedback.length,
    up: feedback.filter((f: Record<string, unknown>) => f["rating"] === "up").length,
    down: feedback.filter((f: Record<string, unknown>) => f["rating"] === "down").length,
  };

  const cap = config.dailySpendCapUsd;
  const spentToday = await todaySpendUsd();
  const budgetStats = {
    daily_cap_usd: cap > 0 ? cap : null,
    spent_today_usd: Math.round(spentToday * 10000) / 10000,
    over_cap: await isOverBudget(),
  };

  return NextResponse.json({ rag: ragStats, alerts: alertsStats, feedback: feedbackStats, budget: budgetStats });
}
