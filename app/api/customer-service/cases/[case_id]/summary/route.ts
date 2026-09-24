import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { config, estimateCostUsd } from "@/lib/config";
import { getSupabaseServer } from "@/lib/supabase-server";
import { generateCaseSummary } from "@/lib/customer-service-agent";
import { enforceBudget } from "@/lib/budget";
import { logRequest } from "@/lib/observability";
import { RateLimitError, rateLimitCheck } from "@/lib/rate-limiter";

export async function POST(req: NextRequest, { params }: { params: { case_id: string } }) {
  try { rateLimitCheck(req.headers.get("x-forwarded-for") ?? "unknown"); } catch (e) {
    if (e instanceof RateLimitError) return NextResponse.json({ detail: e.message }, { status: 429 });
    throw e;
  }

  if (!config.anthropicApiKey) return NextResponse.json({ detail: "ANTHROPIC_API_KEY is not configured." }, { status: 503 });
  try { await enforceBudget(); } catch (e) { return NextResponse.json({ detail: (e as Error).message }, { status: 503 }); }

  const supabase = getSupabaseServer();
  const { data: caseRow, error } = await supabase.from("customer_cases").select("*").eq("id", params.case_id).single();
  if (error || !caseRow) return NextResponse.json({ detail: `No case with id '${params.case_id}'.` }, { status: 404 });

  const client = new Anthropic({ apiKey: config.anthropicApiKey, timeout: 45000 });
  const start = performance.now();
  try {
    const result = await generateCaseSummary(client, config.claudeModel, params.case_id);
    const totalMs = (performance.now() - start) * 1000;
    const cost = estimateCostUsd(config.claudeModel, result.inputTokens, result.outputTokens);

    await logRequest({
      endpoint: "/api/customer-service/summary", region: caseRow.service_area,
      totalMs, generationMs: totalMs, inputTokens: result.inputTokens, outputTokens: result.outputTokens,
      estimatedCostUsd: cost, status: "ok",
    });

    await supabase.from("customer_cases").update({ summary: result.summary, status: "closed" }).eq("id", params.case_id);

    return NextResponse.json({ case_id: params.case_id, summary: result.summary, status: "closed" });
  } catch (e) {
    await logRequest({ endpoint: "/api/customer-service/summary", region: caseRow.service_area, totalMs: (performance.now() - start) * 1000, status: "error", errorMessage: e instanceof Error ? e.message : String(e) });
    throw e;
  }
}
