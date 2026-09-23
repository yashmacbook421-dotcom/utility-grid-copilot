import { NextRequest, NextResponse } from "next/server";
import { forecastWhatIf } from "@/lib/forecasting";
import { REGION_PROFILES } from "@/lib/regions";
import { loadHistory } from "@/lib/forecasting";
import { retrieve, generateAnswer, summarizeForecast, extractCitations, type SourceCitation } from "@/lib/rag";
import { config, estimateCostUsd } from "@/lib/config";
import { enforceBudget } from "@/lib/budget";
import { logRequest } from "@/lib/observability";
import { BASELINE_WINDOW_DAYS, SURGE_THRESHOLD_RATIO } from "@/lib/surge-watcher";
import Anthropic from "@anthropic-ai/sdk";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { region, demand_multiplier, horizon_hours } = body;

  if (!region || !(region in REGION_PROFILES))
    return NextResponse.json({ detail: `Unknown region '${region}'.` }, { status: 404 });

  try {
    const result = await forecastWhatIf(region, REGION_PROFILES[region], demand_multiplier, horizon_hours ?? 24);
    const history = await loadHistory(region, BASELINE_WINDOW_DAYS);
    const demands = history.map((r) => r.demand_mw).sort((a, b) => a - b);
    const baselineP95 = demands.length > 0 ? demands[Math.floor((demands.length - 1) * 0.95)] : 0;
    const wouldExceed = baselineP95 > 0 && result.peak_forecast_mw >= baselineP95 * SURGE_THRESHOLD_RATIO;

    let explanation: string | null = null;
    let sources: SourceCitation[] = [];

    if (wouldExceed && config.anthropicApiKey) {
      try {
        await enforceBudget();
        const question =
          `A what-if scenario projects demand up to ${Math.round(result.peak_forecast_mw)} MW at ` +
          `${result.peak_forecast_time} for ${region} (a ${demand_multiplier}x demand ` +
          `scenario), above the typical range (this region's normal high end is around ` +
          `${Math.round(baselineP95)} MW). What should the operator do to prepare?`;
        sources = await retrieve(question, 4);
        const forecastSummary = summarizeForecast(result);
        const client = new Anthropic({ apiKey: config.anthropicApiKey, timeout: 45000 });
        const generation = await generateAnswer(client, config.claudeModel, question, region, sources, forecastSummary);
        explanation = generation.answer;
      } catch (e) {
        if (e instanceof Error && "status" in e && (e as { status: number }).status === 503) {
          // budget exceeded, skip explanation
        } else {
          throw e;
        }
      }
    }

    return NextResponse.json({
      region,
      demand_multiplier,
      forecast: result.forecast,
      peak_forecast_mw: result.peak_forecast_mw,
      peak_forecast_time: result.peak_forecast_time,
      baseline_p95_mw: baselineP95,
      would_exceed_baseline: wouldExceed,
      explanation,
      sources,
    });
  } catch (e) {
    return NextResponse.json({ detail: e instanceof Error ? e.message : String(e) }, { status: 404 });
  }
}
