import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { config, estimateCostUsd } from "@/lib/config";
import { REGION_PROFILES } from "@/lib/regions";
import { retrieve, generateAnswer, summarizeForecast, extractCitations } from "@/lib/rag";
import { forecast } from "@/lib/forecasting";
import { enforceBudget } from "@/lib/budget";
import { logRequest } from "@/lib/observability";
import { RateLimitError, rateLimitCheck } from "@/lib/rate-limiter";

export async function POST(req: NextRequest) {
  try {
    rateLimitCheck(req.headers.get("x-forwarded-for") ?? "unknown");
  } catch (e) {
    if (e instanceof RateLimitError)
      return NextResponse.json({ detail: e.message }, { status: 429, headers: { "Retry-After": String(e.retryAfter) } });
    throw e;
  }

  const body = await req.json();
  const { region, question, top_k = 4 } = body;

  if (!config.anthropicApiKey) return NextResponse.json({ detail: "ANTHROPIC_API_KEY is not configured." }, { status: 503 });
  try { await enforceBudget(); } catch (e) { return NextResponse.json({ detail: (e as Error).message }, { status: 503 }); }
  if (!(region in REGION_PROFILES)) return NextResponse.json({ detail: `Unknown region '${region}'.` }, { status: 404 });

  const client = new Anthropic({ apiKey: config.anthropicApiKey, timeout: 45000 });
  const start = performance.now();

  try {
    const { runAgenticRecommend } = await import("@/lib/agentic");
    const result = await runAgenticRecommend(client, config.claudeModel, region, question);
    const totalMs = (performance.now() - start) * 1000;

    const deduped: Record<string, typeof result.sources[0]> = {};
    for (const s of result.sources) deduped[s.title] = s;
    const sources = Object.values(deduped);

    const warnings: string[] = [];
    const [, fabricated] = extractCitations(result.answer, sources.map((s) => s.title));
    if (fabricated.length > 0)
      warnings.push("This answer cites a source that wasn't in the retrieved procedures — verify it manually before acting on it.");

    const cost = estimateCostUsd(config.claudeModel, result.inputTokens, result.outputTokens);
    const requestLogId = await logRequest({
      endpoint: "/api/recommend/agentic", region, question, generationMs: totalMs, totalMs,
      retrievedSources: sources.map((s) => ({ title: s.title, similarity: s.similarity, page_number: s.page_number, section: s.section, organization: s.organization })),
      inputTokens: result.inputTokens, outputTokens: result.outputTokens, estimatedCostUsd: cost, status: "ok",
    });

    return NextResponse.json({
      region, question, answer: result.answer,
      tool_calls: result.toolCalls, sources,
      forecast_context: result.forecastContext, warnings,
      iterations: result.iterations, request_log_id: requestLogId,
    });
  } catch (e) {
    await logRequest({ endpoint: "/api/recommend/agentic", region, question, totalMs: (performance.now() - start) * 1000, status: "error", errorMessage: e instanceof Error ? e.message : String(e) });
    throw e;
  }
}
