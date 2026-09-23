import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { config, estimateCostUsd } from "@/lib/config";
import { REGION_PROFILES } from "@/lib/regions";
import { retrieve, generateAnswer, summarizeForecast, extractCitations, type SourceCitation } from "@/lib/rag";
import { forecast, type ForecastData } from "@/lib/forecasting";
import { enforceBudget } from "@/lib/budget";
import { logRequest } from "@/lib/observability";
import { cacheGet, cacheSet, makeKey } from "@/lib/cache";
import { RateLimitError, rateLimitCheck } from "@/lib/rate-limiter";

function getClient(): Anthropic | null {
  return config.anthropicApiKey ? new Anthropic({ apiKey: config.anthropicApiKey, timeout: 45000 }) : null;
}

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

  const cacheKey = makeKey(region, question, String(top_k));
  const cached = cacheGet(cacheKey);
  if (cached) {
    await logRequest({ endpoint: "/api/recommend", region, question, totalMs: 0, status: "cache_hit" });
    return NextResponse.json(cached);
  }

  const client = getClient();
  if (!client) return NextResponse.json({ detail: "ANTHROPIC_API_KEY is not configured." }, { status: 503 });

  try {
    await enforceBudget();
  } catch (e) {
    return NextResponse.json({ detail: (e as Error).message }, { status: 503 });
  }

  if (!(region in REGION_PROFILES))
    return NextResponse.json({ detail: `Unknown region '${region}'.` }, { status: 404 });

  const start = performance.now();
  try {
    const timing: { embeddingMs?: number; searchMs?: number } = {};
    const sources = await retrieve(question, top_k, timing);
    const embeddingMs = timing.embeddingMs;
    const retrievalMs = timing.searchMs;

    let forecastData: ForecastData | null = null;
    let forecastSummary: string | null = null;
    const forecastStart = performance.now();
    try {
      forecastData = await forecast(region, REGION_PROFILES[region], 24);
      forecastSummary = summarizeForecast(forecastData);
    } catch { /* no seeded demand data */ }
    const forecastMs = (performance.now() - forecastStart) * 1000;

    const genStart = performance.now();
    const generation = await generateAnswer(client, config.claudeModel, question, region, sources, forecastSummary);
    const generationMs = (performance.now() - genStart) * 1000;

    const warnings: string[] = [];
    const [, fabricated] = extractCitations(generation.answer, sources.map((s) => s.title));
    if (fabricated.length > 0)
      warnings.push("This answer cites a source that wasn't in the retrieved procedures — verify it manually before acting on it.");

    const totalMs = (performance.now() - start) * 1000;
    const cost = estimateCostUsd(config.claudeModel, generation.inputTokens, generation.outputTokens);
    const requestLogId = await logRequest({
      endpoint: "/api/recommend", region, question, embeddingMs, retrievalMs, forecastMs, generationMs, totalMs,
      retrievedSources: sources.map((s) => ({ title: s.title, similarity: s.similarity, page_number: s.page_number, section: s.section, organization: s.organization })),
      inputTokens: generation.inputTokens, outputTokens: generation.outputTokens, estimatedCostUsd: cost, status: "ok",
    });

    const response = {
      region, question, answer: generation.answer, sources,
      forecast_context: forecastData, warnings, request_log_id: requestLogId,
    };
    cacheSet(cacheKey, response);
    return NextResponse.json(response);
  } catch (e) {
    await logRequest({ endpoint: "/api/recommend", region, question, totalMs: (performance.now() - start) * 1000, status: "error", errorMessage: e instanceof Error ? e.message : String(e) });
    throw e;
  }
}
