import { getSupabaseServer } from "./supabase-server";
import { config } from "./config";
import { REGION_PROFILES } from "./regions";
import { forecast, loadHistory, type ForecastData } from "./forecasting";
import { retrieve, generateAnswer, summarizeForecast, type SourceCitation } from "./rag";
import { isOverBudget } from "./budget";
import { notifySlack, notifySms } from "./notify";
import Anthropic from "@anthropic-ai/sdk";

const SURGE_THRESHOLD_RATIO = 1.0;
const BASELINE_WINDOW_DAYS = 30;
const HIGH_SEVERITY_RATIO = 1.05;
const STATUS_NORMAL_RATIO = 0.9;
const STATUS_ELEVATED_RATIO = SURGE_THRESHOLD_RATIO;

function quantile(sorted: number[], q: number): number {
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  if (sorted[base + 1] !== undefined) {
    return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
  }
  return sorted[base];
}

async function hasPendingEvent(region: string): Promise<boolean> {
  const supabase = getSupabaseServer();
  const { data } = await supabase
    .from("surge_events")
    .select("id")
    .eq("region", region)
    .eq("status", "pending")
    .limit(1);
  return (data ?? []).length > 0;
}

export async function checkRegionForSurge(
  region: string,
  regionProfile: { has_temperature: boolean },
  force = false,
): Promise<Record<string, unknown> | null> {
  if (await hasPendingEvent(region)) return null;

  let forecastData: ForecastData;
  try {
    forecastData = await forecast(region, regionProfile, 24);
  } catch {
    return null;
  }

  const history = await loadHistory(region, BASELINE_WINDOW_DAYS);
  if (history.length === 0) return null;

  const demands = history.map((r) => r.demand_mw).sort((a, b) => a - b);
  const baselineP95 = quantile(demands, 0.95);
  const peak = forecastData.peak_forecast_mw;

  if (!force && peak < baselineP95 * SURGE_THRESHOLD_RATIO) return null;

  const question =
    `We're forecasting a demand surge to ${Math.round(peak)} MW at ${forecastData.peak_forecast_time} ` +
    `for ${region}, above the typical range (this region's normal high end is around ` +
    `${Math.round(baselineP95)} MW). What should the operator do?`;

  const sources = await retrieve(question, 4);
  const forecastSummary = summarizeForecast(forecastData);

  if (!config.anthropicApiKey) return null;
  if (await isOverBudget()) return null;

  const client = new Anthropic({ apiKey: config.anthropicApiKey, timeout: 45000 });
  const generation = await generateAnswer(
    client, config.claudeModel, question, region, sources, forecastSummary,
  );

  const ratio = peak / baselineP95;
  const severity = ratio >= HIGH_SEVERITY_RATIO ? "high" : "medium";

  const supabase = getSupabaseServer();
  const { data: event, error } = await supabase
    .from("surge_events")
    .insert({
      region,
      forecast_peak_mw: peak,
      baseline_p95_mw: baselineP95,
      peak_forecast_time: forecastData.peak_forecast_time,
      recommended_action: generation.answer,
      sources: sources.map((s) => ({
        title: s.title, source: s.source, excerpt: s.excerpt, similarity: s.similarity,
      })),
      status: "pending",
      severity,
    })
    .select("*")
    .single();

  if (error) return null;

  const [slackSent, slackError] = await notifySlack(
    `:rotating_light: *[${severity.toUpperCase()}] Demand surge forecast for ${region}*\n` +
    `Peak ${Math.round(peak)} MW at ${forecastData.peak_forecast_time} ` +
    `(normal high end ~${Math.round(baselineP95)} MW). A recommendation is waiting for approval ` +
    `in the Grid Copilot dashboard.`,
  );
  const [smsSent, smsError] = await notifySms(
    `[Grid Copilot] ${severity.toUpperCase()} surge forecast for ${region}: ` +
    `${Math.round(peak)} MW (normal high end ~${Math.round(baselineP95)} MW). ` +
    `Recommendation waiting for your approval in the dashboard.`,
  );

  const notified = slackSent || smsSent;
  const notificationError = !notified
    ? [slackError, smsError].filter(Boolean).join("; ") || null
    : null;

  await supabase
    .from("surge_events")
    .update({ notified, notification_error: notificationError })
    .eq("id", event.id);

  return { ...event, notified, notification_error: notificationError };
}

export async function computeRegionStatus(
  region: string,
  regionProfile: { has_temperature: boolean },
): Promise<Record<string, unknown> | null> {
  let forecastData: ForecastData;
  try {
    forecastData = await forecast(region, regionProfile, 24);
  } catch {
    return null;
  }

  const history = await loadHistory(region, BASELINE_WINDOW_DAYS);
  if (history.length === 0) return null;

  const demands = history.map((r) => r.demand_mw).sort((a, b) => a - b);
  const baselineP95 = quantile(demands, 0.95);
  const peak = forecastData.peak_forecast_mw;
  const ratio = baselineP95 > 0 ? peak / baselineP95 : 0;

  let status: string;
  if (ratio >= STATUS_ELEVATED_RATIO) status = "surge";
  else if (ratio >= STATUS_NORMAL_RATIO) status = "elevated";
  else status = "normal";

  const latestRow = history[history.length - 1];
  const latestSolar = latestRow?.solar_generation_mw ?? null;
  const latestTempC = latestRow?.temperature_c ?? null;

  return {
    region,
    status,
    forecast_peak_mw: peak,
    baseline_p95_mw: baselineP95,
    ratio: Math.round(ratio * 10000) / 10000,
    latest_solar_generation_mw: latestSolar,
    latest_temp_c: latestTempC,
  };
}

export async function runSurgeCheckAllRegions(): Promise<void> {
  for (const [region, profile] of Object.entries(REGION_PROFILES)) {
    try {
      await checkRegionForSurge(region, profile);
    } catch (e) {
      console.error(`Surge check failed for ${region}:`, e);
    }
  }
}

export { BASELINE_WINDOW_DAYS, SURGE_THRESHOLD_RATIO };
