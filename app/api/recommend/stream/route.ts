import { NextRequest } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { config, estimateCostUsd } from "@/lib/config";
import { REGION_PROFILES } from "@/lib/regions";
import { retrieve, streamAnswer, summarizeForecast, extractCitations } from "@/lib/rag";
import { forecast } from "@/lib/forecasting";
import { enforceBudget } from "@/lib/budget";
import { logRequest } from "@/lib/observability";
import { RateLimitError, rateLimitCheck } from "@/lib/rate-limiter";

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export async function POST(req: NextRequest) {
  try { rateLimitCheck(req.headers.get("x-forwarded-for") ?? "unknown"); } catch (e) {
    if (e instanceof RateLimitError) return new Response(JSON.stringify({ detail: e.message }), { status: 429, headers: { "Content-Type": "application/json", "Retry-After": String(e.retryAfter) } });
    throw e;
  }

  const body = await req.json();
  const { region, question, top_k = 4 } = body;

  if (!config.anthropicApiKey) return new Response(JSON.stringify({ detail: "ANTHROPIC_API_KEY is not configured." }), { status: 503, headers: { "Content-Type": "application/json" } });
  try { await enforceBudget(); } catch (e) { return new Response(JSON.stringify({ detail: (e as Error).message }), { status: 503, headers: { "Content-Type": "application/json" } }); }
  if (!(region in REGION_PROFILES)) return new Response(JSON.stringify({ detail: `Unknown region '${region}'.` }), { status: 404, headers: { "Content-Type": "application/json" } });

  const client = new Anthropic({ apiKey: config.anthropicApiKey, timeout: 45000 });
  const start = performance.now();
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      try {
        const timing: { embeddingMs?: number; searchMs?: number } = {};
        const sources = await retrieve(question, top_k, timing);
        controller.enqueue(encoder.encode(sse("sources", { sources })));

        let forecastData: unknown = null;
        let forecastSummary: string | null = null;
        try {
          forecastData = await forecast(region, REGION_PROFILES[region], 24);
          forecastSummary = summarizeForecast(forecastData as Record<string, unknown> as any);
        } catch { /* no seeded demand data */ }

        const result = await streamAnswer(client, config.claudeModel, question, region, sources, forecastSummary);
        for (const delta of result.deltas) {
          controller.enqueue(encoder.encode(sse("delta", { text: delta })));
        }

        const warnings: string[] = [];
        const [, fabricated] = extractCitations(result.answer, sources.map((s) => s.title));
        if (fabricated.length > 0)
          warnings.push("This answer cites a source that wasn't in the retrieved procedures — verify it manually before acting on it.");

        const totalMs = (performance.now() - start) * 1000;
        const cost = estimateCostUsd(config.claudeModel, result.inputTokens, result.outputTokens);
        const requestLogId = await logRequest({
          endpoint: "/api/recommend/stream", region, question,
          embeddingMs: timing.embeddingMs, retrievalMs: timing.searchMs, totalMs,
          retrievedSources: sources.map((s) => ({ title: s.title, similarity: s.similarity, page_number: s.page_number, section: s.section, organization: s.organization })),
          inputTokens: result.inputTokens, outputTokens: result.outputTokens, estimatedCostUsd: cost, status: "ok",
        });

        controller.enqueue(encoder.encode(sse("done", { answer: result.answer, warnings, forecast_context: forecastData, request_log_id: requestLogId })));
        controller.close();
      } catch (e) {
        await logRequest({ endpoint: "/api/recommend/stream", region, question, totalMs: (performance.now() - start) * 1000, status: "error", errorMessage: e instanceof Error ? e.message : String(e) });
        controller.enqueue(encoder.encode(sse("error", { message: e instanceof Error ? e.message : String(e) })));
        controller.close();
      }
    },
  });

  return new Response(stream, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive" } });
}
