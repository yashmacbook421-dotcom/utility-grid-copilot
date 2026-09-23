import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { config, estimateCostUsd } from "@/lib/config";
import { getSupabaseServer } from "@/lib/supabase-server";
import { runCustomerServiceTurn, runCustomerServiceTurnRouted } from "@/lib/customer-service-agent";
import { extractCitations } from "@/lib/rag";
import { enforceBudget } from "@/lib/budget";
import { logRequest } from "@/lib/observability";
import { RateLimitError, rateLimitCheck } from "@/lib/rate-limiter";

export async function POST(req: NextRequest, { params }: { params: { case_id: string } }) {
  try { rateLimitCheck(req.headers.get("x-forwarded-for") ?? "unknown"); } catch (e) {
    if (e instanceof RateLimitError) return NextResponse.json({ detail: e.message }, { status: 429, headers: { "Retry-After": String(e.retryAfter) } });
    throw e;
  }

  const body = await req.json();
  const { question, mode = "standard" } = body;

  if (!config.anthropicApiKey) return NextResponse.json({ detail: "ANTHROPIC_API_KEY is not configured." }, { status: 503 });
  try { await enforceBudget(); } catch (e) { return NextResponse.json({ detail: (e as Error).message }, { status: 503 }); }

  const supabase = getSupabaseServer();
  const { data: caseRow, error: caseError } = await supabase
    .from("customer_cases")
    .select("*")
    .eq("id", params.case_id)
    .single();
  if (caseError || !caseRow) return NextResponse.json({ detail: `No case with id '${params.case_id}'.` }, { status: 404 });
  if (caseRow.status === "closed") return NextResponse.json({ detail: "This case is closed. Open a new case to continue." }, { status: 409 });

  const client = new Anthropic({ apiKey: config.anthropicApiKey, timeout: 45000 });
  const start = performance.now();

  try {
    let result;
    if (mode === "routed") {
      result = await runCustomerServiceTurnRouted(client, config.claudeRouterModel, config.claudeModel, question, caseRow.customer_id, caseRow.service_area);
    } else {
      result = await runCustomerServiceTurn(client, config.claudeModel, params.case_id, question, caseRow.customer_id, caseRow.service_area);
    }
    const totalMs = (performance.now() - start) * 1000;

    const warnings: string[] = [];
    const [, fabricated] = extractCitations(result.rawAnswer, result.sources.map((s) => s.title));
    if (fabricated.length > 0)
      warnings.push("This answer cites a source that wasn't in the retrieved documents — verify it manually before repeating it to the customer.");

    if (result.escalation.required && result.escalation.reason === "safety" && !result.sources.some((s) => s.document_type === "safety_procedure"))
      warnings.push("This question was flagged as safety-related, but no approved safety procedure was retrieved to ground the answer — verify manually before responding.");

    if (result.escalation.required && !caseRow.escalated) {
      await supabase.from("customer_cases").update({ escalated: true, escalation_reason: result.escalation.reason }).eq("id", params.case_id);
    }

    let cost: number | null;
    if (mode === "routed" && result.routerModel && result.answerModel) {
      const routerCost = estimateCostUsd(result.routerModel, result.routerInputTokens ?? 0, result.routerOutputTokens ?? 0);
      const answerCost = estimateCostUsd(result.answerModel, result.answerInputTokens ?? 0, result.answerOutputTokens ?? 0);
      cost = routerCost !== null && answerCost !== null ? routerCost + answerCost : null;
    } else {
      cost = estimateCostUsd(config.claudeModel, result.inputTokens, result.outputTokens);
    }

    const requestLogId = await logRequest({
      endpoint: "/api/customer-service/ask",
      region: caseRow.service_area,
      question,
      generationMs: totalMs, totalMs,
      retrievedSources: result.sources.map((s) => ({ title: s.title, similarity: s.similarity, page_number: s.page_number, section: s.section, organization: s.organization, document_type: s.document_type })),
      inputTokens: result.inputTokens, outputTokens: result.outputTokens, estimatedCostUsd: cost, status: "ok",
    });

    const updatedLogIds = [...(caseRow.request_log_ids ?? []), requestLogId];
    await supabase.from("customer_cases").update({ request_log_ids: updatedLogIds }).eq("id", params.case_id);

    return NextResponse.json({
      case_id: params.case_id, question, mode,
      internal_analysis: result.internalAnalysis,
      customer_response: result.customerResponse,
      confidence: result.confidence,
      sources: result.sources,
      tool_calls: result.toolCalls,
      escalation: { required: result.escalation.required, reason: result.escalation.reason },
      warnings,
      iterations: result.iterations,
      input_tokens: result.inputTokens,
      output_tokens: result.outputTokens,
      estimated_cost_usd: cost,
      request_log_id: requestLogId,
    });
  } catch (e) {
    await logRequest({ endpoint: "/api/customer-service/ask", region: caseRow.service_area, question, totalMs: (performance.now() - start) * 1000, status: "error", errorMessage: e instanceof Error ? e.message : String(e) });
    throw e;
  }
}
