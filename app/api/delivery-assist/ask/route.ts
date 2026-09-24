import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { config, estimateCostUsd } from "@/lib/config";
import { answerQuestion, AREA_DOCUMENT_TYPES } from "@/lib/delivery-assist";
import { extractCitations } from "@/lib/rag";
import { enforceBudget } from "@/lib/budget";
import { logRequest } from "@/lib/observability";
import { RateLimitError, rateLimitCheck } from "@/lib/rate-limiter";

export async function POST(req: NextRequest) {
  try { rateLimitCheck(req.headers.get("x-forwarded-for") ?? "unknown"); } catch (e) {
    if (e instanceof RateLimitError) return NextResponse.json({ detail: e.message }, { status: 429, headers: { "Retry-After": String(e.retryAfter) } });
    throw e;
  }

  const body = await req.json();
  const { area, question } = body;

  if (!config.anthropicApiKey) return NextResponse.json({ detail: "ANTHROPIC_API_KEY is not configured." }, { status: 503 });
  if (!(area in AREA_DOCUMENT_TYPES)) return NextResponse.json({ detail: `Unknown area '${area}'. Known areas: ${Object.keys(AREA_DOCUMENT_TYPES)}` }, { status: 422 });
  try { await enforceBudget(); } catch (e) { return NextResponse.json({ detail: (e as Error).message }, { status: 503 }); }

  const client = new Anthropic({ apiKey: config.anthropicApiKey, timeout: 45000 });
  const start = performance.now();

  try {
    const result = await answerQuestion(client, config.claudeModel, area, question);
    const totalMs = (performance.now() - start) * 1000;

    const warnings: string[] = [];
    const [, fabricated] = extractCitations(result.answer, result.sources.map((s) => s.title));
    if (fabricated.length > 0)
      warnings.push("This answer cites a source that was not retrieved — verify it with a subject-matter expert before using it with a client.");

    const cost = estimateCostUsd(config.claudeModel, result.inputTokens, result.outputTokens);
    const requestLogId = await logRequest({
      endpoint: "/api/delivery-assist/ask", question,
      generationMs: totalMs, totalMs,
      retrievedSources: result.sources.map((s) => ({ title: s.title, similarity: s.similarity, document_type: s.document_type })),
      inputTokens: result.inputTokens, outputTokens: result.outputTokens, estimatedCostUsd: cost, status: "ok",
    });

    return NextResponse.json({
      area, question, answer: result.answer,
      confidence: result.confidence, sources: result.sources,
      escalation: { required: result.escalation.required, reason: result.escalation.reason },
      warnings, input_tokens: result.inputTokens, output_tokens: result.outputTokens,
      estimated_cost_usd: cost, request_log_id: requestLogId,
    });
  } catch (e) {
    await logRequest({ endpoint: "/api/delivery-assist/ask", question, totalMs: (performance.now() - start) * 1000, status: "error", errorMessage: e instanceof Error ? e.message : String(e) });
    throw e;
  }
}
